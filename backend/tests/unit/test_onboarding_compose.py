"""The step 5 template and availability label (ADR 0022), without a database or AI."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.stages import Chips, Composed, compose_template
from app.services.profile_compose import availability_label
from app.services.profile_parsing import merged_tags


def chips(**over: object) -> Chips:
    base: dict[str, object] = {
        "intents": [],
        "offers": [],
        "wants": [],
        "interests": [],
        "note": "",
        "availability": "",
    }
    return Chips(**(base | over))  # type: ignore[arg-type]  # test helper: loose kwargs


def test_template_lists_the_chips() -> None:
    result = compose_template(
        chips(offers=["React", "Figma"], wants=["Node.js"], interests=["Chess", "Hackathons"])
    )
    assert result.about == "Offers: React, Figma. Wants: Node.js. Into: chess, hackathons."
    assert result.title == "Offers React, wants Node.js"


def test_template_redacts_the_note_and_the_name() -> None:
    result = compose_template(
        chips(note="Aarav here, call 98765 43210 for a gym partner"), names=["Aarav"]
    )
    assert "Aarav" not in result.about
    assert "98765" not in result.about
    assert result.about.startswith("Looking for:")


def test_template_is_never_empty() -> None:
    assert compose_template(chips(intents=["explore"])).about == "Here to see who's out there."
    assert compose_template(chips()).about == "New here."


def test_template_fits_the_about_box() -> None:
    many = [f"Skill number {n}" for n in range(20)]
    result = compose_template(chips(offers=many, wants=many, interests=many, note="x" * 140))
    assert len(result.about) <= 500
    assert len(result.summary) <= 200
    assert len(result.title) <= 60


def test_model_output_is_validated() -> None:
    with pytest.raises(ValidationError):
        Composed.model_validate({"title": "ok", "summary": "ok", "about": ""})
    with pytest.raises(ValidationError):
        Composed.model_validate({"title": "x" * 61, "about": "fine"})


@pytest.mark.parametrize(
    ("days", "hours", "label"),
    [
        (["sat", "sun"], "4_6", "Weekends · 4-6 h/week"),
        (["mon", "tue", "wed", "thu", "fri"], None, "Weekdays"),
        (["wed", "mon"], "10_plus", "Mon, Wed · 10+ h/week"),
        ([], "1_3", "1-3 h/week"),
        ([], None, ""),
    ],
)
def test_availability_label(days: list[str], hours: str | None, label: str) -> None:
    assert availability_label(days, hours) == label


def test_chips_come_first_and_repeats_go() -> None:
    assert merged_tags(["React", "SQL"], ["react", "Docker", ""]) == ["React", "SQL", "Docker"]
