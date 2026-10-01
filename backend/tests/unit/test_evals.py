"""The offline evaluation set loads, validates and rejects malformed data."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from evals.dataset import PAIRS_FILE, PROFILES_FILE, load_eval_set
from evals.run import main
from evals.schema import EvalSet, Intent, Label, LabelledPair, ReviewStatus, SyntheticProfile


def _profile(**overrides: Any) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "id": "p01",
        "name": "Test Person",
        "age": 30,
        "city": "Pune",
        "country": "India",
        "timezone": "Asia/Kolkata",
        "languages": ["en", "mr"],
        "about": "A synthetic test profile. " * 5,
        "request": "Someone to build a small app with.",
        "request_intent": "build_together",
    }
    return profile | overrides


def _pair(**overrides: Any) -> dict[str, Any]:
    pair: dict[str, Any] = {
        "id": "pair-001",
        "profile_a": "p01",
        "profile_b": "p02",
        "intent": "build_together",
        "label": "good",
        "rationale": "Complementary skills and the same schedule.",
        "review_status": "draft",
    }
    return pair | overrides


def _eval_set(pairs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    profiles = [_profile(), _profile(id="p02", request_intent="skill_exchange")]
    return {"profiles": profiles, "pairs": pairs if pairs is not None else [_pair()]}


# --- the committed dataset --------------------------------------------------------------


def test_committed_dataset_is_valid_and_complete() -> None:
    eval_set = load_eval_set()

    assert len(eval_set.profiles) == 40
    assert len(eval_set.pairs) == 100
    assert {pair.intent for pair in eval_set.pairs} == set(Intent)
    assert all(1 <= profile.age <= 100 for profile in eval_set.profiles)


def test_committed_pairs_are_all_unreviewed_drafts() -> None:
    eval_set = load_eval_set()

    assert {pair.review_status for pair in eval_set.pairs} == {ReviewStatus.DRAFT}


def test_committed_labels_are_roughly_balanced() -> None:
    labels = Counter(pair.label for pair in load_eval_set().pairs)

    assert set(labels) == set(Label)
    assert all(25 <= count <= 40 for count in labels.values()), labels


def test_every_profile_appears_in_a_pair() -> None:
    eval_set = load_eval_set()
    used = {ref for pair in eval_set.pairs for ref in (pair.profile_a, pair.profile_b)}

    assert used == {profile.id for profile in eval_set.profiles}


# --- record validation ------------------------------------------------------------------


def test_profile_may_be_under_18() -> None:
    assert SyntheticProfile.model_validate(_profile(age=16)).age == 16


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"age": 0}, "greater than or equal to 1"),
        ({"age": 101}, "less than or equal to 100"),
        ({"timezone": "Mars/Olympus_Mons"}, "unknown IANA timezone"),
        ({"about": "too short"}, "at least 100 characters"),
        ({"about": "x" * 2001}, "at most 2000 characters"),
        ({"languages": []}, "at least 1 item"),
        ({"languages": ["English"]}, "should match pattern"),
        ({"id": "profile-1"}, "should match pattern"),
        ({"request_intent": "dating"}, "Input should be"),
        ({"nickname": "x"}, "Extra inputs are not permitted"),
    ],
)
def test_profile_rejects_invalid_values(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        SyntheticProfile.model_validate(_profile(**overrides))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"profile_b": "p01"}, "must be different profiles"),
        ({"label": "great"}, "Input should be"),
        ({"review_status": "approved"}, "Input should be"),
        ({"rationale": "ok"}, "at least 20 characters"),
        ({"id": "1"}, "should match pattern"),
    ],
)
def test_pair_rejects_invalid_values(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        LabelledPair.model_validate(_pair(**overrides))


# --- dataset validation -----------------------------------------------------------------


def test_minimal_eval_set_is_valid() -> None:
    eval_set = EvalSet.model_validate(_eval_set())

    assert eval_set.pairs[0].label is Label.GOOD


def test_rejects_unknown_profile_reference() -> None:
    with pytest.raises(ValidationError, match="unknown profile 'p99'"):
        EvalSet.model_validate(_eval_set([_pair(profile_b="p99")]))


def test_rejects_intent_that_differs_from_requesters_intent() -> None:
    with pytest.raises(ValidationError, match="does not match p01's request intent"):
        EvalSet.model_validate(_eval_set([_pair(intent="mentor")]))


def test_rejects_same_pair_labelled_twice_for_one_intent() -> None:
    pairs = [_pair(), _pair(id="pair-002", label="poor")]

    with pytest.raises(ValidationError, match="already labelled"):
        EvalSet.model_validate(_eval_set(pairs))


def test_rejects_duplicate_ids() -> None:
    data = _eval_set()
    data["profiles"].append(_profile())

    with pytest.raises(ValidationError, match="duplicate profile id"):
        EvalSet.model_validate(data)


# --- runner -----------------------------------------------------------------------------


def test_runner_prints_counts_per_intent_and_label(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    out = capsys.readouterr().out
    assert "Profiles: 40    Pairs: 100" in out
    for intent in Intent:
        assert intent.value in out
    assert "draft: 100, reviewed: 0" in out


def test_runner_fails_on_invalid_data(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = _eval_set([_pair(profile_b="p99")])
    (tmp_path / PROFILES_FILE).write_text(json.dumps(data["profiles"]), encoding="utf-8")
    (tmp_path / PAIRS_FILE).write_text(json.dumps(data["pairs"]), encoding="utf-8")

    assert main([str(tmp_path)]) == 1
    assert "unknown profile 'p99'" in capsys.readouterr().err
