"""Listed teams and requests to join (ADR 0016).

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-11 09:00:00+00:00

Additive only: ``teams.listed`` and ``teams.looking_for`` (up to 200 characters),
``team_invites.note`` (up to 300 characters, what someone asking to join wrote), a partial
index for browsing listed teams, and two more notification kinds (``team_request``,
``team_request_accepted``). No existing value is changed: every team starts unlisted.

Retention: the listing text goes with the team; a request to join is a ``team_invites`` row
and follows its rules (expires after 14 days, deleted 90 days later). No new table: about
0.2 KB per listed team and 0.3 KB per request at most.

Downgrade drops the columns and the index, deletes the two kinds of notification and
restores the narrower check. Requests to join stay as rows of kind ``request``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
TEAM_LOOKING_FOR_MAX_LENGTH = 200
TEAM_REQUEST_NOTE_MAX_LENGTH = 300
KINDS_BEFORE = (
    "intro_received",
    "intro_accepted",
    "matches_ready",
    "report_reviewed",
    "content_removed",
    "team_invite",
    "team_joined",
)
KINDS_AFTER = (*KINDS_BEFORE, "team_request", "team_request_accepted")


def _swap_kinds(kinds: Sequence[str]) -> None:
    values = ", ".join(f"'{kind}'" for kind in kinds)
    op.drop_constraint(op.f("ck_notifications_kind_valid"), "notifications", type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_kind_valid"), "notifications", f"kind IN ({values})"
    )


def upgrade() -> None:
    op.add_column(
        "teams", sa.Column("listed", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column(
        "teams", sa.Column("looking_for", sa.Text(), server_default=sa.text("''"), nullable=False)
    )
    op.create_check_constraint(
        op.f("ck_teams_looking_for_length"),
        "teams",
        f"char_length(looking_for) <= {TEAM_LOOKING_FOR_MAX_LENGTH}",
    )
    op.create_index(
        "ix_teams_listed_created_at",
        "teams",
        ["created_at", "id"],
        postgresql_where=sa.text("listed AND closed_at IS NULL"),
    )
    op.add_column(
        "team_invites", sa.Column("note", sa.Text(), server_default=sa.text("''"), nullable=False)
    )
    op.create_check_constraint(
        op.f("ck_team_invites_note_length"),
        "team_invites",
        f"char_length(note) <= {TEAM_REQUEST_NOTE_MAX_LENGTH}",
    )
    _swap_kinds(KINDS_AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE kind IN ('team_request', 'team_request_accepted')")
    _swap_kinds(KINDS_BEFORE)
    op.drop_constraint(op.f("ck_team_invites_note_length"), "team_invites", type_="check")
    op.drop_column("team_invites", "note")
    op.drop_index("ix_teams_listed_created_at", table_name="teams")
    op.drop_constraint(op.f("ck_teams_looking_for_length"), "teams", type_="check")
    op.drop_column("teams", "looking_for")
    op.drop_column("teams", "listed")
