"""Is a database at the migration head of this checkout? (the staging drift check).

Run from ``backend/`` with ``DATABASE_URL`` set: ``python -m app.db.drift``. Exits 0 when
the database is at the head, 1 when it is behind, empty or on a revision this code doesn't
know (for example after a migration was reverted). Inside GitHub Actions it also writes an
annotation and a step summary saying what to do.

The "Staging migrations" workflow runs it against staging with the same repository secret
the "Migrate staging" workflow uses, so a merged migration that hasn't been applied to
staging shows up as a red run instead of a broken site (it happened after #39).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import Connection, create_engine, pool

BACKEND_DIR = Path(__file__).resolve().parents[2]


class DriftStatus(StrEnum):
    AT_HEAD = "at_head"
    BEHIND = "behind"
    EMPTY = "empty"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Drift:
    status: DriftStatus
    current: tuple[str, ...]
    heads: tuple[str, ...]
    # Revisions the database still needs, oldest first (only when behind).
    pending: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is DriftStatus.AT_HEAD


def check(script: ScriptDirectory, connection: Connection) -> Drift:
    """Compare the database's revision with the migration head(s) of this checkout."""
    current = tuple(sorted(MigrationContext.configure(connection).get_current_heads()))
    heads = tuple(sorted(script.get_heads()))
    if not current:
        return Drift(DriftStatus.EMPTY, current, heads)
    for revision in current:
        try:
            script.get_revision(revision)
        except CommandError:
            return Drift(DriftStatus.UNKNOWN, current, heads)
    if set(current) == set(heads):
        return Drift(DriftStatus.AT_HEAD, current, heads)
    pending = tuple(
        reversed(
            [
                item.revision
                for item in script.iterate_revisions("heads", current)
                if item.revision not in current
            ]
        )
    )
    return Drift(DriftStatus.BEHIND, current, heads, pending)


def describe(drift: Drift) -> str:
    current = ", ".join(drift.current) or "none"
    head = ", ".join(drift.heads)
    if drift.status is DriftStatus.AT_HEAD:
        return f"Staging is at the migration head ({head})."
    if drift.status is DriftStatus.BEHIND:
        return (
            f"Staging is behind: it is at {current}, main is at {head}. Missing: "
            f"{', '.join(drift.pending)}. Run Actions -> Migrate staging."
        )
    if drift.status is DriftStatus.EMPTY:
        return f"Staging has no migrations applied; main is at {head}. Run Migrate staging."
    return (
        f"Staging is at {current}, which this code doesn't know (main is at {head}). A "
        "migration may have been reverted on main; downgrade staging to the head by hand."
    )


def _alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def _github(drift: Drift, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    level = "notice" if drift.ok else "error"
    sys.stdout.write(f"::{level} title=Staging migrations::{message}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"### Staging migrations\n\n{message}\n")


def main() -> int:
    # Reads DATABASE_URL like the migrations do; the value is never printed.
    from app.core.config import get_settings

    url = get_settings().database_url.unicode_string()
    script = ScriptDirectory.from_config(_alembic_config())
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            drift = check(script, connection)
    finally:
        engine.dispose()
    message = describe(drift)
    sys.stdout.write(message + "\n")
    _github(drift, message)
    return 0 if drift.ok else 1


if __name__ == "__main__":
    sys.exit(main())
