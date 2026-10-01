from tests.helpers import session_token
"""Real PostgreSQL admission, rollback, and reconciliation regression tests."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

import docs_service
import limits
import main
import models
import usage_service
from database import SessionLocal
from tests.helpers import create_user, cleanup_user


REPLY = {"content": "ok", "prompt_tokens": 3, "completion_tokens": 2,
         "docs_fetch_ms": 0.0, "llm_call_ms": 0.0}


@pytest.fixture
def account(db, monkeypatch):
    monkeypatch.setattr(limits, "MAX_MESSAGES_PER_DAY", 2)
    # These tests exercise message admission/races. The provider prompt is
    # larger than 100 tokens, so use a realistic token budget and reserve
    # intentionally small budgets for dedicated token-cap tests instead.
    monkeypatch.setattr(limits, "MAX_TOKENS_PER_DAY", 1000)
    monkeypatch.setattr(limits, "RATE_LIMIT_MAX_REQUESTS", 100)
    user = create_user(db)
    uid = str(user.id)
    conv = models.Conversation(user_id=uid, title="Quota tests")
    db.add(conv)
    db.commit()
    cid = str(conv.id)
    db.close()
    yield uid, cid
    cleanup_user(uid)


def seed_counter(uid, messages=0, tokens=0):
    with SessionLocal() as db:
        row = usage_service.get_or_create_today_counter(db, uid)
        row.messages_today = messages
        row.tokens_today = tokens
        db.commit()


def snapshot(uid):
    with SessionLocal() as db:
        return [(r.date_str, r.messages_today, r.tokens_today, r.est_spend_today)
                for r in db.query(models.UsageCounter).filter_by(user_id=uid).all()]


def send(client, account):
    uid, cid = account
    if not client.cookies.get("session_token"):
        client.cookies.set("session_token", session_token(uid))
    return client.post(f"/conversations/{cid}/messages", json={"content": "hello"})


@pytest.mark.parametrize("iteration", range(5))
@pytest.mark.parametrize("initial,cap,expected", [
    (None, 1, [200, 429]),  # first-ever requests, only one slot
    (None, 2, [200, 200]),  # first-ever requests, both slots must be counted
    (1, 2, [200, 429]),     # existing row at cap-1
])
@pytest.mark.asyncio
async def test_concurrent_admission(account, monkeypatch, iteration, initial, cap, expected):
    uid, cid = account
    monkeypatch.setattr(limits, "MAX_MESSAGES_PER_DAY", cap)
    if initial is not None:
        seed_counter(uid, messages=initial)
    else:
        assert snapshot(uid) == []

    # Both real requests reach get-or-create before either attempts its INSERT.
    barrier = Barrier(2, timeout=10)
    original = usage_service.get_or_create_today_counter

    def simultaneous_insert(db, user_id):
        barrier.wait()
        return original(db, user_id)

    monkeypatch.setattr(usage_service, "get_or_create_today_counter", simultaneous_insert)
    provider = AsyncMock(return_value=REPLY)
    monkeypatch.setattr(main, "generate_llm_response", provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                 base_url="http://test", headers={"Origin": "http://localhost:5173"}) as client:
        client.cookies.set("session_token", session_token(uid))
        responses = await asyncio.wait_for(asyncio.gather(*[
            client.post(f"/conversations/{cid}/messages", json={"content": "hello"})
            for _ in range(2)
        ]), timeout=20)

    assert sorted(r.status_code for r in responses) == expected
    successes = expected.count(200)
    assert provider.await_count == successes
    rows = snapshot(uid)
    assert len(rows) == 1
    assert rows[0][1] == (initial or 0) + successes == cap
    assert rows[0][2] == successes * 5
    assert rows[0][3] == pytest.approx(successes * main.estimate_cost(3, 2))
    with SessionLocal() as db:
        assert db.query(models.Message).filter_by(conversation_id=cid).count() == successes * 2


@pytest.mark.parametrize("existing", [False, True])
def test_rate_blocked_requests_consume_no_daily_quota(account, client, monkeypatch, existing):
    uid, _ = account
    if existing:
        seed_counter(uid, messages=1, tokens=7)
    before = snapshot(uid)
    limits._request_log[uid] = [time.monotonic()] * limits.RATE_LIMIT_MAX_REQUESTS
    provider = AsyncMock(return_value=REPLY)
    monkeypatch.setattr(main, "generate_llm_response", provider)
    for _ in range(3):
        response = send(client, account)
        assert response.status_code == 429
        assert response.json()["detail"]["reason"] == "rate"
    assert snapshot(uid) == before
    provider.assert_not_awaited()


@pytest.mark.parametrize("messages,tokens,expected", [(1, 0, 200), (2, 0, 429),
                                                       (3, 0, 429), (0, 1000, 429)])
def test_exact_cap_boundary(account, client, monkeypatch, messages, tokens, expected):
    uid, _ = account
    seed_counter(uid, messages=messages, tokens=tokens)
    provider = AsyncMock(return_value=REPLY)
    monkeypatch.setattr(main, "generate_llm_response", provider)
    response = send(client, account)
    assert response.status_code == expected
    assert snapshot(uid)[0][1] == messages + (expected == 200)
    if expected == 429:
        assert response.json()["detail"]["reason"] == "cap"
        provider.assert_not_awaited()
    else:
        assert send(client, account).status_code == 429
        assert snapshot(uid)[0][1] == 2
        provider.assert_awaited_once()


def test_unique_constraint_rejects_duplicate_daily_counter(account):
    uid, _ = account
    seed_counter(uid)
    with SessionLocal() as db:
        db.add(models.UsageCounter(user_id=uid, date_str=usage_service._today_str()))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert len(snapshot(uid)) == 1


def test_admission_commit_failure_rolls_back_quota_and_turn(account, client, monkeypatch):
    uid, cid = account
    client.cookies.set("session_token", session_token(uid))
    provider = AsyncMock(return_value=REPLY)
    monkeypatch.setattr(main, "generate_llm_response", provider)
    with monkeypatch.context() as context:
        def fail_commit(self):
            raise OperationalError("admission commit", None, Exception("lost connection"))
        context.setattr(Session, "commit", fail_commit)
        assert send(client, account).status_code == 503
    assert snapshot(uid) == []
    with SessionLocal() as db:
        assert db.query(models.Message).filter_by(conversation_id=cid).count() == 0
    provider.assert_not_awaited()
    assert send(client, account).status_code == 200


def test_doc_failure_releases_slot_and_preserves_error_turn(account, client, monkeypatch):
    uid, cid = account
    # Docs are now fetched before token reservation, so inject the failure at
    # the docs boundary rather than making the provider mock raise a docs error.
    async def fail_context(**_kwargs):
        raise docs_service.DocsServiceError("no prompt")
    monkeypatch.setattr(docs_service, "get_advisor_context", fail_context)
    for _ in range(3):
        assert send(client, account).status_code == 502
        assert snapshot(uid)[0][1:3] == (0, 0)
    with SessionLocal() as db:
        assert db.query(models.Message).filter_by(conversation_id=cid, status="error").count() == 3
    async def good_context(**_kwargs):
        return {"system_prompt": "Synthetic advisor context", "grounding_document": ""}
    monkeypatch.setattr(docs_service, "get_advisor_context", good_context)
    monkeypatch.setattr(main, "generate_llm_response", AsyncMock(return_value=REPLY))
    assert send(client, account).status_code == 200
    assert snapshot(uid)[0][1] == 1


def test_provider_timeout_conservatively_retains_slot(account, client, monkeypatch):
    uid, _ = account
    monkeypatch.setattr(main, "generate_llm_response", AsyncMock(side_effect=TimeoutError()))
    assert send(client, account).status_code == 502
    assert snapshot(uid)[0][1:3] == (1, 0)


@pytest.mark.parametrize("release", [False, True])
def test_finish_is_once_only_and_uses_reserved_day(account, monkeypatch, release):
    uid, cid = account
    monkeypatch.setattr(usage_service, "_today_str", lambda: "2026-09-23")
    with SessionLocal() as db:
        conv = db.get(models.Conversation, cid)
        reservation, assistant_id, _ = main.prepare_reserved_turn(db, conv, uid, "hello")
    monkeypatch.setattr(usage_service, "_today_str", lambda: "2026-09-24")
    barrier = Barrier(2, timeout=10)

    def finish():
        with SessionLocal() as db:
            barrier.wait()
            return main.finish_reserved_turn(db, reservation, assistant_id,
                                             result=None if release else REPLY, release=release)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: finish(), range(2)))
    assert results[0] == results[1]
    rows = snapshot(uid)
    assert len(rows) == 1
    assert rows[0][:3] == ("2026-09-23", 0 if release else 1, 0 if release else 5)


def test_counter_lock_refreshes_previously_loaded_state(account):
    uid, _ = account
    seed_counter(uid)
    with SessionLocal() as stale:
        old = stale.query(models.UsageCounter).filter_by(user_id=uid).one()
        assert old.messages_today == 0
        with SessionLocal() as other:
            limits.reserve_daily_quota(other, uid)
            other.commit()
        limits.reserve_daily_quota(stale, uid)
        stale.commit()
    assert snapshot(uid)[0][1] == 2


@pytest.mark.parametrize("release", [False, True])
def test_finalization_rollback_does_not_partially_update_quota(account, monkeypatch, release):
    uid, cid = account
    with SessionLocal() as db:
        reservation, assistant_id, _ = main.prepare_reserved_turn(
            db, db.get(models.Conversation, cid), uid, "hello",
        )
    with SessionLocal() as db:
        with monkeypatch.context() as context:
            def fail_commit():
                # Force SQL to execute before simulating a failed COMMIT.
                db.flush()
                raise OperationalError("completion commit", None, Exception("lost connection"))
            context.setattr(db, "commit", fail_commit)
            with pytest.raises(OperationalError):
                main.finish_reserved_turn(db, reservation, assistant_id,
                                          result=None if release else REPLY, release=release)
    assert snapshot(uid)[0][1:3] == (1, 0)
    with SessionLocal() as db:
        assert db.get(models.Message, assistant_id).status == "pending"
        main.finish_reserved_turn(db, reservation, assistant_id,
                                  result=None if release else REPLY, release=release)
    assert snapshot(uid)[0][1:3] == ((0, 0) if release else (1, 5))
