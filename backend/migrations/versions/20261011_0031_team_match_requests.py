"""A match request can be for a team: the matcher finds teammates (ADR 0016).

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-11 12:00:00+00:00

Additive only: a nullable ``match_requests.team_id``. No existing value is changed.

Retention: unchanged. The value goes with the request (deleted after
MATCH_REQUEST_RETENTION_DAYS) and is cleared if the team is deleted first. 16 bytes per
request for a team; no new table.

Downgrade drops the column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("match_requests", sa.Column("team_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_match_requests_team_id_teams"),
        "match_requests",
        "teams",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_match_requests_team_id_teams"), "match_requests", type_="foreignkey"
    )
    op.drop_column("match_requests", "team_id")
