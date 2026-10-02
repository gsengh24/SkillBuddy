"""Match requests and matches (ARCHITECTURE.md §5; ADR 0007 stages 2-4).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03 09:00:00+00:00

New tables only; no existing data is touched.

Retention: a request is open for 30 days, then expires. The daily purge deletes requests
older than MATCH_REQUEST_RETENTION_DAYS (90 by default), and their matches with them
(ON DELETE CASCADE). Account deletion removes both.

Storage: a request is about 1.2 KB (text up to 1,000 characters plus the parsed JSON) and
each of its at most 5 matches about 0.4 KB, so about 3 KB per request. At about one request
per user per week kept for 90 days, about 42 KB per active user (docs/storage-budget.md).
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the model values at this revision.
INTENTS = (
    "build_together",
    "skill_exchange",
    "interest_buddy",
    "accountability",
    "mentor",
    "explore",
)
REQUEST_STATUSES = ("pending", "ready", "closed", "expired")
MATCH_STATUSES = ("shown", "viewed", "intro_sent", "accepted", "declined", "expired")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "match_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("requested_intent", sa.String(length=32), nullable=True),
        sa.Column("intent", sa.String(length=32), nullable=True),
        sa.Column(
            "structured",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("explanation_source", sa.String(length=16), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_requests")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_match_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"status IN ({_in(REQUEST_STATUSES)})", name=op.f("ck_match_requests_status_valid")
        ),
        sa.CheckConstraint(
            f"intent IS NULL OR intent IN ({_in(INTENTS)})",
            name=op.f("ck_match_requests_intent_valid"),
        ),
        sa.CheckConstraint(
            f"requested_intent IS NULL OR requested_intent IN ({_in(INTENTS)})",
            name=op.f("ck_match_requests_requested_intent_valid"),
        ),
        sa.CheckConstraint(
            "char_length(raw_text) <= 1000", name=op.f("ck_match_requests_raw_text_length")
        ),
        sa.CheckConstraint(
            "explanation_source IS NULL OR explanation_source IN ('llm', 'template')",
            name=op.f("ck_match_requests_explanation_source_valid"),
        ),
    )
    op.create_index(
        "ix_match_requests_user_id_created_at", "match_requests", ["user_id", "created_at"]
    )
    op.create_index(op.f("ix_match_requests_expires_at"), "match_requests", ["expires_at"])

    op.create_table(
        "matches",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'shown'"), nullable=False
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matches")),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["match_requests.id"],
            name=op.f("fk_matches_request_id_match_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name=op.f("fk_matches_candidate_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "request_id", "candidate_id", name=op.f("uq_matches_request_id_candidate_id")
        ),
        sa.CheckConstraint(
            f"status IN ({_in(MATCH_STATUSES)})", name=op.f("ck_matches_status_valid")
        ),
        sa.CheckConstraint("rank >= 1", name=op.f("ck_matches_rank_positive")),
        sa.CheckConstraint("char_length(reason) <= 300", name=op.f("ck_matches_reason_length")),
    )
    op.create_index(op.f("ix_matches_request_id"), "matches", ["request_id"])
    op.create_index("ix_matches_candidate_id_created_at", "matches", ["candidate_id", "created_at"])


def downgrade() -> None:
    # The match jobs need these tables; drop any that are still queued.
    op.execute("DELETE FROM jobs WHERE kind = 'match_request'")
    op.drop_index("ix_matches_candidate_id_created_at", table_name="matches")
    op.drop_index(op.f("ix_matches_request_id"), table_name="matches")
    op.drop_table("matches")
    op.drop_index(op.f("ix_match_requests_expires_at"), table_name="match_requests")
    op.drop_index("ix_match_requests_user_id_created_at", table_name="match_requests")
    op.drop_table("match_requests")
