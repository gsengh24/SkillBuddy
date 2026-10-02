"""The CI memory check's pass/fail logic, with the model replaced (POSIX only)."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="uses the POSIX resource module")


class _StubEmbedder:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    async def embed(self, texts: Sequence[str], *, kind: str) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]


@pytest.fixture
def memory_check(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.ai import memory_check as module

    monkeypatch.setattr(module, "FastEmbedEmbedder", _StubEmbedder)
    return module


def test_passes_under_the_limit_and_reports(
    memory_check: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    assert memory_check.main(["--limit-mb", "100000"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["dimensions"] == 384
    assert report["peak_rss_mb"] > 0
    assert report["limit_mb"] == 100000


def test_fails_over_the_limit(memory_check: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert memory_check.main(["--limit-mb", "1"]) == 1
    assert "over the 1 MB limit" in capsys.readouterr().err
