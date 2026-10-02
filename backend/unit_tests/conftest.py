"""Keep service unit tests independent of private .env and live credentials."""
import os
from unittest.mock import patch

# Import integrations under this guard before test module collection.
with patch("dotenv.load_dotenv", return_value=False):
    import docs_service
    import personas_service
    import llm_service

# Endpoint-handler mocks need models but never open a database connection.
with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, {
    "DATABASE_URL": "postgresql://advisor_test:advisor_test@127.0.0.1:55432/advisor_test",
    "ENVIRONMENT": "development", "COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax",
}):
    import main
