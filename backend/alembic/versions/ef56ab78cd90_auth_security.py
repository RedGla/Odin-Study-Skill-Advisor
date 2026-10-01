"""Verified identities, single-use auth tokens and shared auth throttles."""
from alembic import op
import sqlalchemy as sa

revision = "ef56ab78cd90"
down_revision = "ef56ab67bc90"
branch_labels = None
depends_on = None


def upgrade():
    # Abort rather than merge identities if legacy case variants collide.
    connection = op.get_bind()
    duplicates = connection.execute(sa.text(
        "SELECT 1 FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicates:
        raise RuntimeError("Resolve duplicate case-insensitive user emails before migrating")
    op.execute("UPDATE users SET email = lower(trim(email))")
    op.create_index("uq_users_normalized_email", "users", [sa.text("lower(trim(email))")], unique=True)
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("google_subject", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_google_subject", "users", ["google_subject"])
    for name in ("registration_enabled", "chat_enabled"):
        op.add_column("app_config", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("auth_tokens",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"])
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_table("auth_rate_limits",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_auth_rate_limits_expires_at", "auth_rate_limits", ["expires_at"])
    # These are backend-only tables; browser Supabase clients must never read them.
    for table in ("auth_tokens", "auth_rate_limits"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(sa.text(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON {table} FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON {table} FROM authenticated;
            END IF;
        END $$"""))


def downgrade():
    op.drop_table("auth_rate_limits")
    op.drop_table("auth_tokens")
    for name in ("registration_enabled", "chat_enabled"):
        op.drop_column("app_config", name)
    op.drop_constraint("uq_users_google_subject", "users", type_="unique")
    for name in ("google_subject", "email_verified", "is_active"):
        op.drop_column("users", name)
    op.drop_index("uq_users_normalized_email", table_name="users")
