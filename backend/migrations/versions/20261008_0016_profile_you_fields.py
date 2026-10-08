"""Profile fields for the You page (design spec section 13).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-08 11:00:00+00:00

Additive only: new columns on ``profiles``, each nullable or with a default that keeps
today's behaviour (location shown at city level, though no one has a city yet;
last-active on; the existing intro emails unchanged; the three emails that aren't built
yet off). The ``visibility`` check widens to allow ``after_intro``; no existing value
changes, so the deployed code keeps working while this runs.

Downgrade turns ``after_intro`` back into ``paused`` (the nearest older value that shows
no less), restores the narrower check and drops the new columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the allowed values at this revision.
VISIBILITY_BEFORE = ("matchable", "paused")
VISIBILITY_AFTER = ("matchable", "after_intro", "paused")
EXPERIENCE_LEVELS = ("just_starting", "1_3_years", "3_7_years", "7_plus_years")
WORKING_STYLES = ("async", "mix", "live")
WEEKLY_HOURS = ("1_3", "4_6", "7_10", "10_plus")
INTENTS = (
    "build_together",
    "skill_exchange",
    "interest_buddy",
    "accountability",
    "mentor",
    "explore",
)
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
LOCATION_PRECISIONS = ("city", "country", "hidden")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _array(values: Sequence[str]) -> str:
    return f"ARRAY[{_in(values)}]::varchar[]"


CHECKS = {
    "city_length": "char_length(city) <= 80",
    "headline_length": "char_length(headline) <= 80",
    "goal_length": "char_length(goal) <= 300",
    "experience_level_valid": (
        f"experience_level IS NULL OR experience_level IN ({_in(EXPERIENCE_LEVELS)})"
    ),
    "working_style_valid": f"working_style IS NULL OR working_style IN ({_in(WORKING_STYLES)})",
    "weekly_hours_valid": f"weekly_hours IS NULL OR weekly_hours IN ({_in(WEEKLY_HOURS)})",
    "intents_valid": f"intents <@ {_array(INTENTS)}",
    "available_days_valid": f"available_days <@ {_array(WEEKDAYS)}",
    "location_precision_valid": f"location_precision IN ({_in(LOCATION_PRECISIONS)})",
}

EMPTY_ARRAY = sa.text("'{}'::varchar[]")


def upgrade() -> None:
    op.add_column(
        "profiles", sa.Column("city", sa.String(80), server_default=sa.text("''"), nullable=False)
    )
    op.add_column(
        "profiles",
        sa.Column("headline", sa.String(80), server_default=sa.text("''"), nullable=False),
    )
    op.add_column("profiles", sa.Column("experience_level", sa.String(16), nullable=True))
    op.add_column(
        "profiles",
        sa.Column(
            "intents", postgresql.ARRAY(sa.String(32)), server_default=EMPTY_ARRAY, nullable=False
        ),
    )
    op.add_column(
        "profiles", sa.Column("goal", sa.Text(), server_default=sa.text("''"), nullable=False)
    )
    op.add_column("profiles", sa.Column("working_style", sa.String(8), nullable=True))
    op.add_column("profiles", sa.Column("weekly_hours", sa.String(8), nullable=True))
    op.add_column(
        "profiles",
        sa.Column(
            "available_days",
            postgresql.ARRAY(sa.String(3)),
            server_default=EMPTY_ARRAY,
            nullable=False,
        ),
    )
    op.add_column("profiles", sa.Column("available_from", sa.Time(), nullable=True))
    op.add_column("profiles", sa.Column("available_until", sa.Time(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column(
            "location_precision", sa.String(8), server_default=sa.text("'city'"), nullable=False
        ),
    )
    for column, default in (
        ("show_last_active", "true"),
        ("intros_only_from_strong_matches", "false"),
        ("email_daily_digest", "false"),
        ("email_match_suggestions", "false"),
        ("email_product_updates", "false"),
    ):
        op.add_column(
            "profiles",
            sa.Column(column, sa.Boolean(), server_default=sa.text(default), nullable=False),
        )
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_profiles_{name}"), "profiles", condition)
    op.drop_constraint(op.f("ck_profiles_visibility_valid"), "profiles", type_="check")
    op.create_check_constraint(
        op.f("ck_profiles_visibility_valid"),
        "profiles",
        f"visibility IN ({_in(VISIBILITY_AFTER)})",
    )


def downgrade() -> None:
    op.execute("UPDATE profiles SET visibility = 'paused' WHERE visibility = 'after_intro'")
    op.drop_constraint(op.f("ck_profiles_visibility_valid"), "profiles", type_="check")
    op.create_check_constraint(
        op.f("ck_profiles_visibility_valid"),
        "profiles",
        f"visibility IN ({_in(VISIBILITY_BEFORE)})",
    )
    for name in CHECKS:
        op.drop_constraint(op.f(f"ck_profiles_{name}"), "profiles", type_="check")
    for column in (
        "email_product_updates",
        "email_match_suggestions",
        "email_daily_digest",
        "intros_only_from_strong_matches",
        "show_last_active",
        "location_precision",
        "available_until",
        "available_from",
        "available_days",
        "weekly_hours",
        "working_style",
        "goal",
        "intents",
        "experience_level",
        "headline",
        "city",
    ):
        op.drop_column("profiles", column)
