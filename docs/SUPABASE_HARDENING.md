# Supabase hardening runbook

## Migration

`ef56ab67bc90_lock_down_public_schema` enables RLS on every current public
application table, including `alembic_version`. It intentionally creates no
`anon` or `authenticated` policies because application traffic uses the
server-side PostgreSQL `postgres` role. The migration revokes direct public,
`anon`, `authenticated`, and `service_role` table and sequence privileges, then
sets matching default privileges for future application tables. It also adds
indexes for `conversations(user_id)` and `messages(conversation_id)`.

## Production preflight

1. Take a Supabase production backup and retain its restore identifier.
2. Record deployed backend commit and health response.
3. Schedule a short write pause for migration application and verification.
4. Confirm backend `DATABASE_URL` connects as `postgres`; it must not use
   `anon`, `authenticated`, or `service_role`.
5. Review the migration against a disposable PostgreSQL database or Supabase
   staging branch. Do not apply it to production before this succeeds.

## Advisor baseline — 2026-09-23

Security: RLS disabled on `alembic_version`, `users`, `conversations`,
`usage_counters`, `messages`, `telemetry_events`, `app_config`, and `sessions`.

Performance: missing covering indexes on `conversations.user_id` and
`messages.conversation_id`. The advisor also reports an unused
`ix_telemetry_events_event` index; it is not changed by this migration.

## Disposable database validation — 2026-09-23

- PostgreSQL 16: upgrade succeeded; all eight tables had RLS enabled; both
  indexes existed; `anon` and `authenticated` had zero table grants; all 83
  backend tests passed.
- PostgreSQL 16: downgrade to `de45fa67bc89` disabled RLS and removed both
  indexes; re-upgrade restored the hardened state.
- PostgreSQL 17.11: full upgrade, downgrade, and re-upgrade succeeded. Final
  revision was `ef56ab67bc90`, all eight tables had RLS enabled, both indexes
  existed, and `anon` and `authenticated` had zero table grants.
- PostgreSQL 17.11: a temporary table with an identity sequence inherited zero
  grants for `anon`, `authenticated`, and `service_role`, proving safe future
  default privileges. The probe table was removed afterward.

## Free-tier logical backup — 2026-09-23

Supabase Free does not provide scheduled backups or PITR. Before production
deployment, a PostgreSQL 17 logical backup of `public` was created in custom
format, together with a separate schema-only SQL export. The files are stored
outside the repository and contain production data; they must be copied to
durable, access-controlled off-site storage before the write pause begins.

The custom dump restored successfully into fresh PostgreSQL 17. Restored row
counts matched production, and all public tables, pre-migration RLS state,
grants, constraints, indexes, and the Alembic revision were verified. Exact
backup paths, checksums, and production row counts are intentionally excluded
from version control.

## Post-deployment verification

1. Verify all eight tables report RLS enabled.
2. Verify `anon` and `authenticated` lack every table and sequence privilege.
3. Verify both foreign-key index warnings are gone.
4. Verify backend health, login, conversation CRUD, message send, admin pages,
   and Alembic revision `ef56ab67bc90`.
5. Re-run Supabase security and performance advisors and append dated output.

## Production deployment — 2026-09-23

Migration `ef56ab67bc90` was applied during an approved write pause after the
logical backup and restore test. Verification reported 8/8 public tables with
RLS enabled, zero table and sequence grants for `anon` and `authenticated`,
both required indexes, and backend ownership by `postgres`.

Security Advisor now reports only the expected informational finding that RLS
is enabled without policies on all eight tables. This is intentional because
the application uses a direct server-side PostgreSQL connection. Performance
Advisor no longer reports either unindexed foreign key; the two new indexes
appear as unused immediately after creation, which is expected until production
queries exercise them.

## Rollback

Pause writes first. Run `alembic downgrade de45fa67bc89` only when restoring
the prior direct-API posture is an explicit incident decision; that downgrade
removes the two indexes, disables RLS, and restores pre-migration Supabase
default grants. If data or schema integrity is in doubt, restore the recorded
Supabase backup instead, then redeploy the last known-good backend commit.
