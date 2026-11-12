"""Profile fields for the chip-first onboarding flow (ADR 0022).

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-12 12:00:00+00:00

Additive only: new columns on ``profiles``, each nullable or with an empty default.

- ``offer_skills``, ``want_skills``, ``interest_tags``: the chips picked on steps 2 and 3
  (at most 20 each, 60 characters each).
- ``want_note``: the optional "anything specific?" line (140 characters).
- ``study_year``, ``branch``: step 4, both optional.
- ``onboarding_saved``, ``onboarding_skipped``: which steps were saved or skipped, so a
  person who leaves comes back to the right step.
- ``onboarding_completed_at``: when onboarding was finished. Every existing profile was
  made through the old onboarding, so it is backfilled with ``created_at``; nobody who has
  a profile today is sent back through onboarding.

Retention: the columns go with the profile (deleted with the account). No growing table.
Storage: a few hundred bytes per profile at most.

Downgrade drops the columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the allowed values at this revision.
STUDY_YEARS = ("1", "2", "3", "4", "postgrad")
BRANCHES = (
    "computer",
    "electronics",
    "electrical",
    "mechanical",
    "chemical",
    "civil",
    "biotechnology",
    "other",
)
STEPS = ("intents", "offers", "wants", "about")
SKIPPABLE_STEPS = ("offers", "wants", "about")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _array(values: Sequence[str]) -> str:
    return f"ARRAY[{_in(values)}]::varchar[]"


CHECKS = {
    "offer_skills_count": "cardinality(offer_skills) <= 20",
    "want_skills_count": "cardinality(want_skills) <= 20",
    "interest_tags_count": "cardinality(interest_tags) <= 20",
    "want_note_length": "char_length(want_note) <= 140",
    "study_year_valid": f"study_year IS NULL OR study_year IN ({_in(STUDY_YEARS)})",
    "branch_valid": f"branch IS NULL OR branch IN ({_in(BRANCHES)})",
    "onboarding_saved_valid": f"onboarding_saved <@ {_array(STEPS)}",
    "onboarding_skipped_valid": f"onboarding_skipped <@ {_array(SKIPPABLE_STEPS)}",
}

EMPTY_ARRAY = sa.text("'{}'::varchar[]")
ARRAY_COLUMNS = (
    ("offer_skills", 60),
    ("want_skills", 60),
    ("interest_tags", 60),
    ("onboarding_saved", 8),
    ("onboarding_skipped", 8),
)


def upgrade() -> None:
    for column, length in ARRAY_COLUMNS:
        op.add_column(
            "profiles",
            sa.Column(
                column,
                postgresql.ARRAY(sa.String(length)),
                server_default=EMPTY_ARRAY,
                nullable=False,
            ),
        )
    op.add_column(
        "profiles",
        sa.Column("want_note", sa.String(140), server_default=sa.text("''"), nullable=False),
    )
    op.add_column("profiles", sa.Column("study_year", sa.String(8), nullable=True))
    op.add_column("profiles", sa.Column("branch", sa.String(16), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_profiles_{name}"), "profiles", condition)
    op.execute("UPDATE profiles SET onboarding_completed_at = created_at")


def downgrade() -> None:
    for name in CHECKS:
        op.drop_constraint(op.f(f"ck_profiles_{name}"), "profiles", type_="check")
    for column in (
        "onboarding_completed_at",
        "branch",
        "study_year",
        "want_note",
        *(name for name, _ in reversed(ARRAY_COLUMNS)),
    ):
        op.drop_column("profiles", column)
