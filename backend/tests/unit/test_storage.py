"""Storage thresholds (docs/storage-budget.md)."""

from __future__ import annotations

import pytest

from app.services.storage import classify
from tests.conftest import SettingsFactory


@pytest.mark.parametrize(
    ("used_mb", "level"),
    [
        (0, "ok"),
        (349, "ok"),
        (350, "warning"),
        (449, "warning"),
        (450, "critical"),
        (600, "critical"),
    ],
)
def test_levels_follow_the_70_and_90_percent_thresholds(
    make_settings: SettingsFactory, used_mb: int, level: str
) -> None:
    status = classify(make_settings(), used_mb * 1_000_000)

    assert status.level == level
    assert status.limit_bytes == 500_000_000


def test_used_percent_is_rounded(make_settings: SettingsFactory) -> None:
    assert classify(make_settings(), 123_456_789).used_percent == 24.7
