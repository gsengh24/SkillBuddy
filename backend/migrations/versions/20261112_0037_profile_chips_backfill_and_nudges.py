"""Chip columns for older profiles, and in-context nudges (ADR 0022, onboarding P4).

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-12 18:00:00+00:00

1. Backfill: profiles made before ADR 0022 have their skills only in ``structured`` (what
   was read from the about text). The You page now edits the chip columns, and sending an
   intro or joining a team needs three offered skills, so empty ``offer_skills``,
   ``want_skills`` and ``interest_tags`` are filled from ``structured`` offers, seeks and
   interests: in order, trimmed, cut to 60 characters, repeats (ignoring case) dropped, at
   most 20. Profiles that already have chips are left alone.
2. New columns on ``profiles`` for the Home nudges: ``nudges_shown`` and
   ``nudges_dismissed`` (kinds, bounded by the number of kinds) and ``nudge_shown_at``.

Retention: the columns go with the profile (deleted with the account). No growing table.
Storage: a few dozen bytes per profile.

Downgrade drops the nudge columns. The backfilled chips stay: they are the same skills
``structured`` already holds, in columns that exist at revision 0036.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: str | Sequence[str] | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the nudge kinds at this revision.
NUDGE_KINDS = ("team_skill", "availability")
KINDS = "ARRAY[" + ", ".join(f"'{kind}'" for kind in NUDGE_KINDS) + "]::varchar[]"
CHECKS = {
    "nudges_shown_valid": f"nudges_shown <@ {KINDS}",
    "nudges_dismissed_valid": f"nudges_dismissed <@ {KINDS}",
}
BACKFILL = (("offer_skills", "offers"), ("want_skills", "seeks"), ("interest_tags", "interests"))


def _backfill(column: str, key: str) -> str:
    return f"""
        UPDATE profiles AS p
        SET {column} = ARRAY(
            SELECT kept.tag FROM (
                SELECT DISTINCT ON (lower(left(btrim(item.value), 60)))
                    left(btrim(item.value), 60) AS tag, item.n
                FROM jsonb_array_elements_text(p.structured -> '{key}')
                    WITH ORDINALITY AS item(value, n)
                WHERE btrim(item.value) <> ''
                ORDER BY lower(left(btrim(item.value), 60)), item.n
            ) AS kept
            ORDER BY kept.n
            LIMIT 20
        )::varchar(60)[]
        WHERE cardinality(p.{column}) = 0
          AND jsonb_typeof(p.structured -> '{key}') = 'array'
    """  # noqa: S608  # fixed names from BACKFILL above


def upgrade() -> None:
    for column in ("nudges_shown", "nudges_dismissed"):
        op.add_column(
            "profiles",
            sa.Column(
                column,
                postgresql.ARRAY(sa.String(16)),
                server_default=sa.text("'{}'::varchar[]"),
                nullable=False,
            ),
        )
    op.add_column("profiles", sa.Column("nudge_shown_at", sa.DateTime(timezone=True)))
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_profiles_{name}"), "profiles", condition)
    for column, key in BACKFILL:
        op.execute(_backfill(column, key))


def downgrade() -> None:
    for name in CHECKS:
        op.drop_constraint(op.f(f"ck_profiles_{name}"), "profiles", type_="check")
    for column in ("nudge_shown_at", "nudges_dismissed", "nudges_shown"):
        op.drop_column("profiles", column)
