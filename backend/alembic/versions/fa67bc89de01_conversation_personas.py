"""Persist conversation personas with an Odin default for legacy rows."""
from alembic import op
import sqlalchemy as sa
revision = "fa67bc89de01"
down_revision = "ef56ab78cd90"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("conversations", sa.Column("persona_id", sa.String(), nullable=False, server_default="odin"))

def downgrade():
    op.drop_column("conversations", "persona_id")
