"""Google sign-in attempts: the oauth_states table (ADR 0011).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-02 18:00:00+00:00

One row per "Continue with Google" click: an HMAC of the ``state`` value, where to go
afterwards and the tick-box answers. A row is deleted when its callback arrives, and
unused rows are purged daily by ``purge_auth_data`` once expired (10 minutes).

Storage: about 200 B per row and only unexpired rows remain, so well under 1 MB even
at thousands of sign-ins a day (docs/storage-budget.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("next_path", sa.String(length=200), nullable=False),
        sa.Column("age_confirmed", sa.Boolean(), nullable=False),
        sa.Column("accept_terms", sa.Boolean(), nullable=False),
        sa.Column("created_ip", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_states")),
        sa.UniqueConstraint("state_hash", name=op.f("uq_oauth_states_state_hash")),
    )
    op.create_index(op.f("ix_oauth_states_expires_at"), "oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_oauth_states_expires_at"), table_name="oauth_states")
    op.drop_table("oauth_states")
