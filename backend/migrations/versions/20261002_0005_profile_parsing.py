"""Profiles: display name, links, parse state and AI-processing consent (ADR 0007, stage 1).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02 12:00:00+00:00

Adds columns only; no existing value is changed or deleted. Profiles that already have
text are marked ``pending`` and one ``parse_pending_profiles`` job is queued, which queues a
``parse_profile`` job for each. Text caps become CHECK constraints.

Storage: no new table. About 200 bytes more per profile (name, links, hash, versions),
so about 0.2 MB per 1,000 users (docs/storage-budget.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the values at this revision.
BACKFILL_JOB = "parse_pending_profiles"
BACKFILL_DEDUPE_KEY = "parse_pending_profiles:migration-0005"
CHECKS = {
    "parse_status_valid": "parse_status IN ('empty', 'pending', 'parsed')",
    "parse_source_valid": "parse_source IS NULL OR parse_source IN ('llm', 'template', 'user')",
    "about_text_length": "char_length(raw_about_text) <= 2000",
    "display_name_length": "char_length(display_name) <= 60",
    "links_count": "cardinality(links) <= 3",
    "languages_count": "cardinality(languages) <= 10",
}


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "display_name", sa.String(length=60), server_default=sa.text("''"), nullable=False
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "links",
            postgresql.ARRAY(sa.String(length=200)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "parse_status", sa.String(length=16), server_default=sa.text("'empty'"), nullable=False
        ),
    )
    op.add_column("profiles", sa.Column("parse_source", sa.String(length=16), nullable=True))
    op.add_column(
        "profiles", sa.Column("parse_prompt_version", sa.String(length=32), nullable=True)
    )
    op.add_column("profiles", sa.Column("parsed_text_hash", sa.String(length=64), nullable=True))
    op.add_column("profiles", sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("profiles", sa.Column("ai_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("profiles", sa.Column("ai_consent_version", sa.String(length=32), nullable=True))
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_profiles_{name}"), "profiles", condition)

    op.execute("UPDATE profiles SET parse_status = 'pending' WHERE btrim(raw_about_text) <> ''")
    op.execute(
        sa.text(
            "INSERT INTO jobs (kind, priority, dedupe_key) SELECT :kind, 300, :key "
            "WHERE EXISTS (SELECT 1 FROM profiles WHERE parse_status = 'pending') "
            "ON CONFLICT (dedupe_key) DO NOTHING"
        ).bindparams(kind=BACKFILL_JOB, key=BACKFILL_DEDUPE_KEY)
    )


def downgrade() -> None:
    # These job kinds need the columns removed below; a finished backfill row would also
    # stop a later re-upgrade from queueing it again.
    op.execute(
        sa.text("DELETE FROM jobs WHERE kind IN (:a, :b)").bindparams(
            a=BACKFILL_JOB, b="parse_profile"
        )
    )
    for name in CHECKS:
        op.drop_constraint(op.f(f"ck_profiles_{name}"), "profiles", type_="check")
    for column in (
        "ai_consent_version",
        "ai_consent_at",
        "parsed_at",
        "parsed_text_hash",
        "parse_prompt_version",
        "parse_source",
        "parse_status",
        "links",
        "display_name",
    ):
        op.drop_column("profiles", column)
