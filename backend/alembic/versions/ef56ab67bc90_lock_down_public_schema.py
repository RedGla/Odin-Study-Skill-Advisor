"""Lock down public application tables and add foreign-key indexes.

Revision ID: ef56ab67bc90
Revises: de45fa67bc89
"""

from alembic import op


revision = "ef56ab67bc90"
down_revision = "de45fa67bc89"
branch_labels = None
depends_on = None


APPLICATION_TABLES = (
    "alembic_version",
    "users",
    "conversations",
    "usage_counters",
    "messages",
    "telemetry_events",
    "app_config",
    "sessions",
)
API_ROLES = "PUBLIC, anon, authenticated, service_role"


def upgrade() -> None:
    # This service connects as the table-owning postgres role.  Enable RLS but
    # create no client policies: direct Data API access is intentionally denied.
    for table in APPLICATION_TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')

    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {API_ROLES}")
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {API_ROLES}")

    # Apply defaults to the role running Alembic. In production this is the
    # table-owning postgres backend role; disposable databases may use another
    # owner role.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON TABLES FROM {API_ROLES}"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE ALL PRIVILEGES ON SEQUENCES FROM {API_ROLES}"
    )

    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")

    # Restore the project's pre-migration Supabase defaults for a deliberate
    # rollback. This re-exposes the schema and must only be used during an
    # incident with the Data API disabled or after an explicit risk decision.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT TRUNCATE, REFERENCES, TRIGGER ON TABLES "
        "TO anon, authenticated, service_role"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO anon, authenticated, service_role"
    )

    op.execute(
        "GRANT TRUNCATE, REFERENCES, TRIGGER "
        "ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role"
    )
    # MAINTAIN was added in PostgreSQL 17. Restore it when supported without
    # making this migration unparsable on the PostgreSQL 16 test database.
    op.execute("""
        DO $block$
        BEGIN
            IF current_setting('server_version_num')::integer >= 170000 THEN
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'GRANT MAINTAIN ON TABLES TO anon, authenticated, service_role';
                EXECUTE 'GRANT MAINTAIN ON ALL TABLES IN SCHEMA public '
                        'TO anon, authenticated, service_role';
            END IF;
        END
        $block$
    """)
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public "
        "TO anon, authenticated, service_role"
    )
    for table in APPLICATION_TABLES:
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
