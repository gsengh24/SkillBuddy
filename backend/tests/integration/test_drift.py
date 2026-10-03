"""The staging drift check against real PostgreSQL databases."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text

from app.db.drift import DriftStatus, check, describe, main
from tests.conftest import SettingsFactory
from tests.integration.conftest import alembic_config


@pytest.fixture
def engine(empty_database_url: str) -> Iterator[Engine]:
    engine = create_engine(empty_database_url)
    yield engine
    engine.dispose()


def _check(url: str, engine: Engine) -> tuple[DriftStatus, str, tuple[str, ...]]:
    script = ScriptDirectory.from_config(alembic_config(url))
    with engine.connect() as connection:
        drift = check(script, connection)
    return drift.status, describe(drift), drift.pending


def test_reports_each_state(empty_database_url: str, engine: Engine) -> None:
    url = empty_database_url
    config = alembic_config(url)
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None

    status, message, _ = _check(url, engine)
    assert status is DriftStatus.EMPTY
    assert "Run Migrate staging" in message

    command.upgrade(config, "head")
    status, message, _ = _check(url, engine)
    assert status is DriftStatus.AT_HEAD
    assert head in message

    command.downgrade(config, "-2")
    status, message, pending = _check(url, engine)
    assert status is DriftStatus.BEHIND
    assert len(pending) == 2
    assert pending[-1] == head  # oldest first, the head last
    assert "Run Actions -> Migrate staging" in message

    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'ffff'"))
    status, message, _ = _check(url, engine)
    assert status is DriftStatus.UNKNOWN
    assert "doesn't know" in message


def test_main_exits_non_zero_and_annotates_when_behind(
    empty_database_url: str,
    make_settings: SettingsFactory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")
    settings = make_settings(database_url=empty_database_url)
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    assert main() == 0
    assert "::notice title=Staging migrations::" in capsys.readouterr().out

    command.downgrade(config, "-1")
    assert main() == 1
    out = capsys.readouterr().out
    assert "::error title=Staging migrations::Staging is behind" in out
    assert "Migrate staging" in summary.read_text(encoding="utf-8")
    assert empty_database_url not in out  # the connection string is never printed
