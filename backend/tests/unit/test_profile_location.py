"""What others see of a person's location: only what their location precision allows."""

from __future__ import annotations

import uuid

import pytest

from app.models import Match, Profile
from app.schemas.matching import MatchOut
from app.schemas.social import PersonOut


def profile(city: str, precision: str) -> Profile:
    return Profile(
        user_id=uuid.uuid4(),
        display_name="Asha",
        raw_about_text="",
        structured={},
        languages=[],
        links=[],
        city=city,
        location_precision=precision,
    )


@pytest.mark.parametrize(
    ("city", "precision", "shown"),
    [
        ("Bengaluru", "city", "Bengaluru"),
        ("Bengaluru", "hidden", None),
        # Only the city is stored, so "country" can't show more than nothing yet.
        ("Bengaluru", "country", None),
        ("", "city", None),
    ],
)
def test_location_follows_the_chosen_precision(
    city: str, precision: str, shown: str | None
) -> None:
    person = profile(city, precision)
    match = Match(
        id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        candidate_id=person.user_id,
        rank=1,
        score=0.9,
        reason="Both build budgeting apps.",
        status="shown",
    )

    assert person.shown_location() == shown
    assert MatchOut.build(match, person).candidate.location == shown
    for connected in (False, True):
        assert PersonOut.build(person.user_id, person, connected=connected).location == shown
    assert PersonOut.build(person.user_id, None, connected=True).location is None
