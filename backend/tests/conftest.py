import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Never inherit DATABASE_URL or .env credentials. Only a disposable local
# PostgreSQL database with the explicit test database/user name is accepted.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://advisor_test:advisor_test@127.0.0.1:55432/advisor_test",
)
test_url = make_url(TEST_DATABASE_URL)
if (
    test_url.drivername not in {"postgresql", "postgresql+psycopg2"}
    or test_url.host not in {"localhost", "127.0.0.1", "::1"}
    or test_url.database != "advisor_test"
    or test_url.username != "advisor_test"
    or test_url.query
):
    raise pytest.UsageError("TEST_DATABASE_URL must target local PostgreSQL advisor_test as advisor_test")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["OPENROUTER_API_KEY"] = "test-only-not-a-real-key"
for secret in ("GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_JSON_B64"):
    os.environ.pop(secret, None)

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from alembic import command
from alembic.config import Config

# python-dotenv versions differ in support for PYTHON_DOTENV_DISABLED.
# Suppress loading explicitly while importing all application modules.
with patch("dotenv.load_dotenv", return_value=False):
    from database import SessionLocal, engine
    from main import app
    import docs_service
    import limits


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    # Mirror Supabase's API roles so privilege migrations are exercised in CI.
    with engine.begin() as connection:
        connection.execute(text("""
            DO $block$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    CREATE ROLE anon NOLOGIN;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    CREATE ROLE authenticated NOLOGIN;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                    CREATE ROLE service_role NOLOGIN;
                END IF;
            END
            $block$
        """))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def isolated_integrations(monkeypatch, migrated_database):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE messages, conversations, usage_counters, users, app_config, auth_tokens, auth_rate_limits CASCADE"))
    import auth_security
    monkeypatch.setattr(auth_security, "mail_configured", lambda: True)
    monkeypatch.setattr(auth_security, "send_account_email", lambda *args: None)
    import personas_service
    personas_service._cache = None
    monkeypatch.setattr(personas_service, "_cache_lock", asyncio.Lock())
    monkeypatch.setattr(personas_service, "_fetch_personas", lambda: [personas_service.odin_fallback()])
    docs_service._cache.clear()
    limits._request_log.clear()
    monkeypatch.setattr(docs_service, "_cache_lock", asyncio.Lock())
    monkeypatch.setattr(docs_service, "_fetch_document", lambda document_id: "Synthetic advisor context for tests.")

    attempted_requests = []

    async def reject_network(self, request):
        attempted_requests.append(request.url.host)
        raise AssertionError("External HTTP must be mocked in backend tests")

    monkeypatch.setattr("httpx.AsyncHTTPTransport.handle_async_request", reject_network)
    yield
    docs_service._cache.clear()
    limits._request_log.clear()
    assert not attempted_requests, "A test attempted unmocked external HTTP"


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app, headers={"Origin": "http://localhost:5173"}) as test_client:
        yield test_client
