"""The committed OpenAPI file and the exporter (no database needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.openapi_export import build, run
from tests.conftest import SettingsFactory


@pytest.fixture
def text(make_settings: SettingsFactory) -> str:
    return build(make_settings())


def test_the_schema_is_stable_and_versioned_as_v1(
    text: str, make_settings: SettingsFactory
) -> None:
    schema = json.loads(text)
    assert schema["info"]["version"] == "v1"
    assert "/api/v1/messages/updates" in schema["paths"]
    assert "/api/v1/moderation/reports" in schema["paths"]
    assert build(make_settings(app_version="something-else")) == text


def test_check_passes_when_current_and_fails_when_stale(
    text: str, make_settings: SettingsFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "openapi.json"
    out = tmp_path / "generated" / "openapi.json"
    settings = make_settings()

    assert run(settings, check=True, spec=spec, out=out) == 1  # missing counts as stale
    assert "out of date" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == text

    spec.write_text(text, encoding="utf-8")
    assert run(settings, check=True, spec=spec, out=None) == 0

    spec.write_text(text.replace('"v1"', '"v0"', 1), encoding="utf-8")
    assert run(settings, check=True, spec=spec, out=None) == 1
