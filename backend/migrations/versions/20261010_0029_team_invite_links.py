"""Team invite links (ADR 0016).

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-10 22:00:00+00:00

Additive only: ``teams.invite_code_hash`` (a keyed hash of the link's code, unique; the code
itself is never stored) and ``teams.invite_expires_at``. No existing value is changed.

Retention: the two values are replaced when the owner makes a new link, cleared when the
owner turns the link off, and go with the team. No new table; about 0.1 KB per team with a
link.

Downgrade drops the two columns (every invite link stops working).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("invite_code_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "teams", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint(op.f("uq_teams_invite_code_hash"), "teams", ["invite_code_hash"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_teams_invite_code_hash"), "teams", type_="unique")
    op.drop_column("teams", "invite_expires_at")
    op.drop_column("teams", "invite_code_hash")
