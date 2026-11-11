"""Remember when the matcher last searched for a request, so empty ones can be retried.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-11 12:00:00+00:00

``match_requests.searched_at``: when the matcher last ran for the request. The daily retry
of requests that found nobody runs the judge again only for people who joined or changed
their profile after this time. Existing rows start from ``matched_at``.

Retention: unchanged (the column goes with its request). Storage: 8 bytes per request.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | Sequence[str] | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_requests", sa.Column("searched_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE match_requests SET searched_at = matched_at")


def downgrade() -> None:
    op.drop_column("match_requests", "searched_at")
