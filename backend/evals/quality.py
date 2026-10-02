"""First quality check of the matcher's no-AI path against the labelled pairs.

Usage (from ``backend/``)::

    uv run python -m evals.quality                       # word-overlap scorer (CI)
    uv run python -m evals.quality --embedder fastembed  # also the real embedding model

It reports, for the template path that runs when the AI is off:

- intent accuracy of ``understand_template`` on the 40 requests;
- how well each scorer separates labels: mean score per label, and AUC (the chance a
  good pair scores above a poor one; 0.5 is random);
- per requester, how often candidates with different labels are ordered correctly, and
  how often the top-scored candidate is labelled good;
- how often the template's reason for a good pair is specific rather than generic.

**Every label is still a draft** (see the README): numbers are a baseline to compare
changes against, not a measure of real quality, until the pairs are reviewed.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations

from app.ai.candidates import CandidateSummary
from app.ai.stages.explain import _words, template_reason
from app.ai.stages.understand import Understanding, understand_template
from evals.dataset import load_eval_set
from evals.schema import EvalSet, LabelledPair, ReviewStatus

LABEL_ORDER = {"poor": 0, "acceptable": 1, "good": 2}
GENERIC_REASON = "A close match for what you described."


@dataclass(frozen=True)
class Report:
    pairs: int
    unreviewed: int
    unreviewed_by_intent: dict[str, int]
    intent_accuracy: float
    intent_misses: list[tuple[str, str, str | None]]
    scorers: dict[str, dict[str, float]]
    specific_reason_rate: float


def _summary(person_id: str, understanding: Understanding) -> CandidateSummary:
    return CandidateSummary(
        user_id=uuid.uuid5(uuid.NAMESPACE_URL, person_id),
        skills=understanding.offers,
        interests=understanding.interests,
        goals=understanding.seeks,
        availability=understanding.availability,
    )


def overlap_score(request: Understanding, request_text: str, about: str) -> float:
    """Cosine of word sets: what A asks for against everything B wrote."""
    mine = _words([*request.seeks, request_text])
    theirs = _words([about])
    if not mine or not theirs:
        return 0.0
    return len(mine & theirs) / math.sqrt(len(mine) * len(theirs))


def auc(positives: Sequence[float], negatives: Sequence[float]) -> float:
    if not positives or not negatives:
        return float("nan")
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def _scorer_metrics(
    pairs: Sequence[LabelledPair], score: Callable[[LabelledPair], float]
) -> dict[str, float]:
    scores = {pair.id: score(pair) for pair in pairs}
    by_label: dict[str, list[float]] = defaultdict(list)
    for pair in pairs:
        by_label[pair.label.value].append(scores[pair.id])
    by_requester: dict[str, list[LabelledPair]] = defaultdict(list)
    for pair in pairs:
        by_requester[pair.profile_a].append(pair)
    ordered = comparable = top_good = groups = 0
    for group in by_requester.values():
        for a, b in combinations(group, 2):
            if LABEL_ORDER[a.label.value] == LABEL_ORDER[b.label.value]:
                continue
            comparable += 1
            better, worse = (
                (a, b) if LABEL_ORDER[a.label.value] > LABEL_ORDER[b.label.value] else (b, a)
            )
            ordered += scores[better.id] > scores[worse.id]
        if len(group) >= 2:
            groups += 1
            top_good += max(group, key=lambda p: scores[p.id]).label.value == "good"
    return {
        **{f"mean_{label}": sum(v) / len(v) for label, v in sorted(by_label.items())},
        "auc_good_vs_poor": auc(by_label["good"], by_label["poor"]),
        "auc_good_or_acceptable_vs_poor": auc(
            by_label["good"] + by_label["acceptable"], by_label["poor"]
        ),
        "pairwise_order_accuracy": ordered / comparable if comparable else float("nan"),
        "comparable_pairs": float(comparable),
        "top1_good_rate": top_good / groups if groups else float("nan"),
        "requesters_with_2plus": float(groups),
    }


def evaluate(eval_set: EvalSet, *, embedder: str = "none") -> Report:
    profiles = {p.id: p for p in eval_set.profiles}
    requests = {pid: understand_template(p.request) for pid, p in profiles.items()}
    abouts = {pid: understand_template(p.about) for pid, p in profiles.items()}

    detected = {pid: (u.intent.value if u.intent else None) for pid, u in requests.items()}
    misses = [
        (pid, p.request_intent.value, detected[pid])
        for pid, p in profiles.items()
        if detected[pid] != p.request_intent.value
    ]
    pairs = list(eval_set.pairs)

    scorers = {
        "word_overlap": _scorer_metrics(
            pairs,
            lambda pair: overlap_score(
                requests[pair.profile_a],
                profiles[pair.profile_a].request,
                profiles[pair.profile_b].about,
            ),
        )
    }
    if embedder == "fastembed":
        scorers["bge_small_cosine"] = _scorer_metrics(pairs, _embedding_scores(eval_set))

    good = [p for p in pairs if p.label.value == "good"]
    specific = sum(
        template_reason(requests[p.profile_a], _summary(p.profile_b, abouts[p.profile_b]))
        != GENERIC_REASON
        for p in good
    )
    unreviewed = [p for p in pairs if p.review_status is ReviewStatus.DRAFT]
    return Report(
        pairs=len(pairs),
        unreviewed=len(unreviewed),
        unreviewed_by_intent=dict(sorted(Counter(p.intent.value for p in unreviewed).items())),
        intent_accuracy=(len(profiles) - len(misses)) / len(profiles),
        intent_misses=misses,
        scorers=scorers,
        specific_reason_rate=specific / len(good) if good else float("nan"),
    )


def _embedding_scores(eval_set: EvalSet) -> Callable[[LabelledPair], float]:
    """Cosine of bge-small embeddings: A's request (query) against B's about (passage)."""
    from app.ai.embeddings import FastEmbedEmbedder

    embedder = FastEmbedEmbedder("BAAI/bge-small-en-v1.5", cache_dir=None, threads=1, batch_size=2)
    profiles = list(eval_set.profiles)

    async def embed() -> tuple[list[list[float]], list[list[float]]]:
        queries = await embedder.embed([p.request for p in profiles], kind="query")
        passages = await embedder.embed([p.about for p in profiles], kind="passage")
        return queries, passages

    queries, passages = asyncio.run(embed())
    q = {p.id: v for p, v in zip(profiles, queries, strict=True)}
    d = {p.id: v for p, v in zip(profiles, passages, strict=True)}
    return lambda pair: sum(
        a * b for a, b in zip(q[pair.profile_a], d[pair.profile_b], strict=True)
    )


def format_report(report: Report) -> str:
    lines = [
        f"Pairs: {report.pairs}    Unreviewed (draft): {report.unreviewed}",
        "Unreviewed by intent: "
        + ", ".join(f"{k} {v}" for k, v in report.unreviewed_by_intent.items()),
        "",
        f"Intent accuracy (template, 40 requests): {report.intent_accuracy:.2f}",
    ]
    for pid, expected, got in report.intent_misses:
        lines.append(f"  {pid}: expected {expected}, got {got}")
    for name, metrics in report.scorers.items():
        lines.append("")
        lines.append(f"Scorer: {name}")
        for key, value in metrics.items():
            shown = (
                f"{value:.0f}"
                if key in {"comparable_pairs", "requesters_with_2plus"}
                else f"{value:.3f}"
            )
            lines.append(f"  {key}: {shown}")
    lines.append("")
    lines.append(
        f"Template reasons for good pairs that are specific: {report.specific_reason_rate:.2f}"
    )
    lines.append("")
    lines.append("All labels are drafts: treat these numbers as a baseline, not as quality.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="First quality check on the eval pairs.")
    parser.add_argument("--embedder", choices=["none", "fastembed"], default="none")
    args = parser.parse_args(argv)
    report = evaluate(load_eval_set(), embedder=args.embedder)
    sys.stdout.write(format_report(report) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
