"""Pure parts of onboarding P4 (ADR 0022): strength, chip edits and the team-skill match."""

from __future__ import annotations

import uuid

from app.models import ParseStatus, Profile
from app.services.nudges import skill_named_in
from app.services.profile_parsing import set_chips
from app.services.profile_strength import MIN_OFFERED_SKILLS, StrengthItem, strength_of


def _profile(**fields: object) -> Profile:
    values: dict[str, object] = {
        "user_id": uuid.uuid4(),
        "raw_about_text": "",
        "intents": [],
        "offer_skills": [],
        "want_skills": [],
        "interest_tags": [],
        "available_days": [],
        "headline": "",
        "links": [],
        "structured": {},
        "parse_status": ParseStatus.EMPTY,
    }
    return Profile(**(values | fields))


def test_no_profile_has_everything_missing() -> None:
    nothing = strength_of(None)
    assert (nothing.percent, nothing.done, nothing.total) == (0, 0, len(StrengthItem))
    assert nothing.missing == list(StrengthItem)


def test_strength_counts_each_item_once() -> None:
    full = strength_of(
        _profile(
            raw_about_text="Offers: React.",
            intents=["mentor"],
            offer_skills=["a", "b", "c"],
            interest_tags=["chess"],
            available_days=["sat"],
            headline="Builds React apps",
            links=["https://a.dev"],
        )
    )
    assert (full.percent, full.missing) == (100, [])
    # Two offered skills are not enough for that item; a short headline doesn't count.
    some = strength_of(_profile(offer_skills=["a", "b"], headline="Hi", intents=["mentor"]))
    assert StrengthItem.OFFERS in some.missing
    assert StrengthItem.HEADLINE in some.missing
    assert some.done == 1
    assert MIN_OFFERED_SKILLS == 3


def test_set_chips_follows_the_edit_and_says_when_to_re_embed() -> None:
    parsed = _profile(
        offer_skills=["React"],
        structured={"offers": ["React", "read from text"], "seeks": ["x"], "summary": "s"},
        parse_status=ParseStatus.PARSED,
    )
    assert set_chips(parsed, offers=["Go", "go", "SQL"]) is True
    assert parsed.offer_skills == ["Go", "go", "SQL"]
    # The edit is the person's word: the matcher's view takes it, repeats dropped.
    assert parsed.structured["offers"] == ["Go", "SQL"]
    assert parsed.structured["seeks"] == ["x"]
    assert set_chips(parsed, offers=["Go", "go", "SQL"]) is False
    pending = _profile(parse_status=ParseStatus.PENDING)
    assert set_chips(pending, wants=["Figma"]) is False
    assert pending.want_skills == ["Figma"]


def test_a_team_name_points_at_a_listed_skill_not_yet_offered() -> None:
    assert skill_named_in("ML study circle", set()) == "Machine learning"
    assert skill_named_in("Weekend Python builders", set()) == "Python"
    assert skill_named_in("Weekend Python builders", {"python"}) is None
    # Whole words only: "Pythonistas" isn't "Python".
    assert skill_named_in("Pythonistas", set()) is None
    assert skill_named_in("Hack night", set()) is None
