"""Google account picture: its address on the account, and the copy a profile shows (ADR 0017).

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-11 01:00:00+00:00

Additive only: two nullable columns, both null for every existing row, so nobody's picture
shows until they sign in with Google again and switch it on. The deployed code keeps
working while this runs.

- ``users.google_picture_url``: the address Google sent at the last Google sign-in.
- ``profiles.photo_url``: a copy of it while the person has "show my Google photo" on.

Only addresses are stored; the pictures stay on Google's servers.

Retention: both columns go with their rows (the account, and its profile by cascade), so
they follow the 30-day account deletion. No new table.

Storage: at most 300 characters each, about 100 in practice: about 0.2 KB per person who
shows a picture (docs/storage-budget.md).

Downgrade drops both columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A frozen copy of the model value at this revision.
GOOGLE_PICTURE_URL_MAX_LENGTH = 300


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "google_picture_url", sa.String(length=GOOGLE_PICTURE_URL_MAX_LENGTH), nullable=True
        ),
    )
    op.add_column(
        "profiles",
        sa.Column("photo_url", sa.String(length=GOOGLE_PICTURE_URL_MAX_LENGTH), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "photo_url")
    op.drop_column("users", "google_picture_url")
