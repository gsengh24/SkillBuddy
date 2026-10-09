"""The no-AI templates of the Understand and Explain stages, and the quality script."""

from __future__ import annotations

import math
import uuid

import pytest
from pydantic import ValidationError

from app.ai.candidates import CandidateSummary
from app.ai.prompts import load_prompt
from app.ai.stages import Candidate, Intent, Understanding, explain_template, understand_template
from app.ai.stages.explain import (
    DEFAULT_MIN_JUDGED,
    Judgement,
    Verdict,
    judged_score,
    template_reason,
)
from app.ai.stages.understand import detect_intent
from evals import quality
from evals.dataset import load_eval_set


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Looking for a mentor in product design.", Intent.MENTOR),
        ("Need a study partner to keep each other on track for GATE.", Intent.ACCOUNTABILITY),
        ("I can teach Spanish in exchange for help with guitar.", Intent.SKILL_EXCHANGE),
        ("Want a co-founder to build a small SaaS app.", Intent.BUILD_TOGETHER),
        ("Anyone up for chess on weekends?", Intent.INTEREST_BUDDY),
        ("Just want to meet people from other fields.", Intent.EXPLORE),
        ("Hello there.", None),
    ],
)
def test_detect_intent(text: str, intent: Intent | None) -> None:
    assert detect_intent(text) is intent


def test_understand_template_extracts_phrases_and_availability() -> None:
    result = understand_template(
        "I can build React apps and write Python. Looking for a designer, a backend dev. "
        "I love hiking and chess. Free 4-6 hours a week, mostly weekends."
    )
    assert result.intent is Intent.BUILD_TOGETHER
    assert result.offers == ["build React apps", "write Python"]
    assert result.seeks == ["designer", "backend dev"]
    assert result.interests == ["hiking", "chess"]
    assert result.availability == "4-6 hours a week"
    assert result.summary == "I can build React apps and write Python."
    assert set(result.facets()) == {"summary", "offers", "seeks", "interests"}


def test_understand_template_handles_empty_and_huge_text() -> None:
    assert understand_template("") == Understanding()
    result = understand_template("I can " + ", ".join(f"skill{i}" for i in range(50)) + ".")
    assert len(result.offers) == 8
    assert len(understand_template("word " * 2000).summary) <= 200


def test_understanding_validates_model_output() -> None:
    with pytest.raises(ValidationError):
        Understanding.model_validate({"intent": "romance"})
    with pytest.raises(ValidationError):
        Understanding.model_validate({"offers": ["x" * 61]})
    extra = Understanding.model_validate({"summary": "ok", "email": "a@b.c"})
    assert "email" not in extra.model_dump()


def test_judgement_rejects_bad_ids_and_values_outside_the_rubric() -> None:
    assert Judgement.model_validate(
        {"verdicts": [{"id": "C3", "need": 3, "shared": 1, "reason": "Both build apps."}]}
    )
    # A reason and a conflict flag are optional.
    assert Verdict.model_validate({"id": "C1", "need": 0, "shared": 0}).reason == ""
    for bad in (
        {"id": "user-1", "need": 2, "shared": 1},
        {"id": "C1", "need": 4, "shared": 1},
        {"id": "C1", "need": 2, "shared": -1},
        {"id": "C1", "shared": 1},
        {"id": "C1", "need": 2, "shared": 1, "reason": "x" * 241},
    ):
        with pytest.raises(ValidationError):
            Verdict.model_validate(bad)


def _verdict(need: int, shared: int, *, conflict: bool = False) -> Verdict:
    return Verdict(id="C1", need=need, shared=shared, conflict=conflict)


def test_judged_score_weighs_the_rubric_in_code() -> None:
    assert judged_score(_verdict(3, 3)) == pytest.approx(1.0)
    assert judged_score(_verdict(0, 0)) == 0.0
    # What was asked for counts for more than what else is shared.
    assert judged_score(_verdict(3, 0)) > judged_score(_verdict(0, 3))
    # A conflict is 0 whatever the other values say.
    assert judged_score(_verdict(3, 3, conflict=True)) == 0.0


def test_the_default_judge_floor_keeps_real_fits_and_drops_vague_ones() -> None:
    for need, shared in ((2, 0), (3, 0), (2, 1)):
        assert judged_score(_verdict(need, shared)) >= DEFAULT_MIN_JUDGED
    for need, shared in ((1, 1), (1, 0), (0, 3), (0, 0)):
        assert judged_score(_verdict(need, shared)) < DEFAULT_MIN_JUDGED


def _candidate(score: float, **fields: object) -> Candidate:
    return Candidate(CandidateSummary(user_id=uuid.uuid4(), **fields), score)  # type: ignore[arg-type]  # test helper passes known field names


def test_template_reason_prefers_what_they_offer() -> None:
    request = Understanding(seeks=["React developer"], interests=["chess"])
    offers = CandidateSummary(user_id=uuid.uuid4(), skills=["React and TypeScript"])
    shared = CandidateSummary(user_id=uuid.uuid4(), interests=["chess openings"])
    neither = CandidateSummary(user_id=uuid.uuid4(), skills=["pottery"])
    assert template_reason(request, offers) == (
        "They offer React and TypeScript, which you are looking for."
    )
    assert template_reason(request, shared) == "You both mention chess openings."
    assert template_reason(request, neither) == quality.GENERIC_REASON


def test_explain_template_keeps_the_top_scores_in_order() -> None:
    request = Understanding(seeks=["python"])
    candidates = [_candidate(0.1), _candidate(0.9, skills=["Python"]), _candidate(0.5)]
    picks = explain_template(request, candidates, max_picks=2)
    assert [p.user_id for p in picks] == [
        candidates[1].summary.user_id,
        candidates[2].summary.user_id,
    ]
    assert picks[0].reason.startswith("They offer Python")


def test_prompts_load_by_id_only() -> None:
    assert "C1" in load_prompt("explain_v1")
    assert "verdicts" in load_prompt("explain_v2")
    assert "intent" in load_prompt("understand_v1")
    with pytest.raises(FileNotFoundError):
        load_prompt("../README")
    with pytest.raises(FileNotFoundError):
        load_prompt("missing_v1")


def test_quality_script_reports_on_every_pair(capsys: pytest.CaptureFixture[str]) -> None:
    report = quality.evaluate(load_eval_set())
    assert report.pairs == 100
    assert report.unreviewed == 100
    assert 0.0 <= report.intent_accuracy <= 1.0
    metrics = report.scorers["word_overlap"]
    assert 0.0 <= metrics["auc_good_vs_poor"] <= 1.0
    assert not math.isnan(metrics["pairwise_order_accuracy"])

    assert quality.main([]) == 0
    out = capsys.readouterr().out
    assert "Unreviewed (draft): 100" in out
    assert "All labels are drafts" in out


def test_auc_counts_ties_as_half() -> None:
    assert quality.auc([1.0, 0.5], [0.5]) == 0.75
    assert math.isnan(quality.auc([], [1.0]))
