# Reproducing the baseline

Requirements: Python 3.12, Node.js 24, and Docker (or a disposable local
PostgreSQL 16 database). Run commands from the repository root unless noted.

## Credential-free unit checks

```text
python -m pytest backend/unit_tests eval -q
```

These tests need no PostgreSQL or live Google/OpenRouter credentials. Service
imports suppress dotenv loading in this test directory. The full `pytest` suite
also includes PostgreSQL tests below; it is not a database-free command.
No backend lint/type-check tool or frontend test runner is configured. Use Python
syntax compilation, frontend ESLint and the TypeScript build alongside tests.

## Backend

Create and activate a Python environment, then install dependencies:

```text
python -m venv .venv
```

PowerShell activation: `.\.venv\Scripts\Activate.ps1`

Linux/macOS activation: `source .venv/bin/activate`

```text
python -m pip install -r backend/requirements.txt
docker run --detach --rm --name advisor-phase0-postgres -e POSTGRES_USER=advisor_test -e POSTGRES_PASSWORD=advisor_test -e POSTGRES_DB=advisor_test -p 127.0.0.1:55432:5432 postgres:16
docker exec advisor-phase0-postgres pg_isready -U advisor_test -d advisor_test
```

Wait until `pg_isready` reports accepting connections, then:

```text
python -m pytest -q
```

`pytest` also works after activating the environment. The session fixture runs
the real Alembic migrations before testing. Tests use real PostgreSQL row locks;
SQLite and mocked database locking are not substitutes for the race tests.

The default test URL is
`postgresql://advisor_test:advisor_test@127.0.0.1:55432/advisor_test`.
To use another local port, set `TEST_DATABASE_URL` explicitly. Only loopback
PostgreSQL with database **and user** named `advisor_test` is accepted, without
URL query options. This database is disposable: tables are truncated before
each test. Do not run separate pytest processes against the same database.

The fixture overrides `DATABASE_URL`, disables application `.env` loading during
imports, supplies a dummy provider key, and resets cache/rate state between tests.
Google Sheets rows and Google Docs fetching use synthetic data. Provider calls are mocked by the tests;
an unmocked external HTTP attempt fails fixture teardown even if the application
catches its exception. No Google, OpenRouter, or production database secret is
required. This suite does not verify real Google Sheets/Docs/model behavior.

Stop and remove the disposable container when done:

```text
docker stop advisor-phase0-postgres
```

## Frontend

```text
cd frontend
npm ci
npm run lint
npm run build
```

The build command runs `tsc -b` before `vite build`; TypeScript errors fail it.
The build does not contact the configured API. No production frontend secrets
are required. `npm ci` uses the committed lockfile.

## GitHub Actions

`.github/workflows/ci.yml` runs three required-to-pass jobs on pushes and pull
requests: Backend tests, Frontend lint, and Frontend TypeScript and build.
It also permits manual dispatch once the workflow exists on the default branch.
PostgreSQL is an ephemeral service container with public test-only credentials.
Backend runs print installed dependency versions and upload JUnit results even
on failure. Python direct dependencies follow `backend/requirements.txt`; its
Google packages and transitive dependencies are not fully locked, so use the
recorded versions when investigating a changed result.

No tests are skipped or marked expected-failure to obtain a green baseline.
Branch protection is a separate repository setting; this workflow does not
configure it. See `BASELINE.md` for original failures and the limits of the checks.
