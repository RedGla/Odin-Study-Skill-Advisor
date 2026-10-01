from fastapi.testclient import TestClient
from main import app
import pytest


DEV_ORIGIN = "http://localhost:5173"
PROD_ORIGIN = "https://advisor.example.com"


def authenticated_mutation(path: str, method: str = "post", **kwargs):
    client = TestClient(app)
    return getattr(client, method)(
        path,
        cookies={"session_token": "opaque"},
        **kwargs,
    )


def test_authenticated_mutation_requires_origin_or_referer():
    response = authenticated_mutation("/auth/logout")
    assert response.status_code == 403
    response = authenticated_mutation("/auth/logout", headers={"Origin": DEV_ORIGIN})
    assert response.status_code == 200



def test_valid_production_origin_is_accepted(monkeypatch):
    monkeypatch.setattr("main.ALLOWED_ORIGINS", [PROD_ORIGIN])
    response = authenticated_mutation("/auth/logout", headers={"Origin": PROD_ORIGIN})
    assert response.status_code == 200


def test_valid_development_origin_is_accepted():
    response = authenticated_mutation("/auth/logout", headers={"Origin": DEV_ORIGIN})
    assert response.status_code == 200


def test_hostile_origin_is_rejected_even_when_referer_is_allowed():
    response = authenticated_mutation(
        "/auth/logout",
        headers={"Origin": "https://evil.example", "Referer": f"{DEV_ORIGIN}/settings"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("referer", [f"{DEV_ORIGIN}/settings", f"{DEV_ORIGIN}/"])
def test_matching_referer_is_accepted_only_when_origin_is_absent(referer):
    response = authenticated_mutation("/auth/logout", headers={"Referer": referer})
    assert response.status_code == 200


@pytest.mark.parametrize("referer", ["not a URL", "https:///missing-host", "javascript:alert(1)"])
def test_malformed_referer_is_rejected(referer):
    response = authenticated_mutation("/auth/logout", headers={"Referer": referer})
    assert response.status_code == 403


def test_safe_get_is_not_blocked():
    client = TestClient(app)
    response = client.get("/health", cookies={"session_token": "opaque"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 200


@pytest.mark.parametrize("path,payload", [
    ("/auth/login", {"email": "nobody@example.com", "password": "password123"}),
    ("/auth/register", {"email": "newperson@acme.org", "password": "password123"}),
])
def test_login_and_registration_require_allowed_origin_without_session(path, payload):
    client = TestClient(app)
    response = client.post(path, json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF origin validation failed"

    response = client.post(path, json=payload, headers={"Origin": DEV_ORIGIN})
    assert response.status_code != 403


@pytest.mark.parametrize(("method", "path", "payload"), [
    ("post", "/auth/logout", None),
    ("post", "/auth/change-password", {"current_password": "x", "new_password": "password123"}),
    ("put", "/admin/config", {"daily_message_cap": 1, "daily_token_cap": 1, "rate_limit_requests": 1, "rate_limit_window_seconds": 1}),
    ("post", "/conversations", {"title": "CSRF test"}),
    ("patch", "/conversations/missing", {"title": "CSRF test"}),
    ("delete", "/conversations/missing", None),
    ("post", "/conversations/missing/messages", {"content": "CSRF test"}),
])
def test_every_authenticated_mutation_requires_allowed_origin(method, path, payload):
    kwargs = {"headers": {"Origin": "https://evil.example"}}
    if payload is not None:
        kwargs["json"] = payload
    rejected = authenticated_mutation(path, method, **kwargs)
    assert rejected.status_code == 403

    kwargs["headers"] = {"Origin": DEV_ORIGIN}
    allowed = authenticated_mutation(path, method, **kwargs)
    assert allowed.status_code != 403
