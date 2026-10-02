# Matcher evaluation set

The offline evaluation set described in `docs/ARCHITECTURE.md` (sections 3 and 7): synthetic
people and hand-labelled pairs used to measure match quality (precision at 5 per intent)
whenever the matcher, a prompt or a model changes.

> **The labels in this folder are drafts.** Every pair is `"review_status": "draft"`. The
> labels and rationales were proposed to get the set started; they are **not ground truth**
> until the project owner has reviewed each pair, corrected the label or rationale where
> needed, and changed its status to `"reviewed"`. Evaluation results must only count
> reviewed pairs.

## What's here

| File | Contents |
| --- | --- |
| `schema.py` | Pydantic models: `SyntheticProfile`, `LabelledPair`, and `EvalSet`, which checks the whole dataset |
| `data/profiles.json` | 40 synthetic profiles: a free-text "about me", the request they would make, and its intent |
| `data/pairs.json` | 100 pairs across the six intents, each with a draft label and rationale |
| `dataset.py` | `load_eval_set()` reads and validates the JSON |
| `run.py` | Validates the data and prints counts per intent and label |

All people are **fictional**; any resemblance to real people is accidental. No real user
data may ever be added here (ADR 0004): the set is synthetic by design.

## How a pair works

A pair is directional. `profile_a` is the person making the request, and the pair's `intent`
is always A's `request_intent`. `profile_b` is the candidate being judged for that request.

| Field | Values |
| --- | --- |
| `intent` | `build_together`, `skill_exchange`, `interest_buddy`, `accountability`, `mentor`, `explore` |
| `label` | `good` (would happily introduce), `acceptable` (plausible but with a clear gap), `poor` (should not be suggested) |
| `rationale` | One or two sentences citing the specific facts in both profiles |
| `review_status` | `draft` or `reviewed` |

The validator also checks that every referenced profile exists, ids are unique, nobody is
paired with themselves, and the same two people are not labelled twice for one intent.

## Reviewing the drafts

1. Open `data/pairs.json` and the two profiles for a pair in `data/profiles.json`.
2. Ask: would I introduce B to A for A's request? Fix `label` and `rationale` if needed.
3. Set `"review_status": "reviewed"`.
4. Run the validator and commit the change in a PR.

Rough targets per intent: about a third each of good, acceptable and poor, so the matcher
is tested on easy and hard cases.

## Running it

CI validates the set on every pull request (`tests/unit/test_evals.py`). To run it
yourself in a Codespace or with the backend environment installed:

```bash
cd backend
uv run python -m evals.run      # prints counts per intent and label, exits 1 if invalid
uv run pytest tests/unit/test_evals.py
```

## Quality check

`evals/quality.py` is the first quality check of the matcher's no-AI path (the template
that runs when the AI is off). It needs no model and no network by default:

```bash
cd backend
uv run python -m evals.quality                       # word-overlap scorer; CI runs this
uv run python -m evals.quality --embedder fastembed  # also bge-small cosine (downloads the model; local only)
```

It reports intent accuracy of the template on the 40 requests; for each scorer, the mean
score per label, AUC (how often a good pair outscores a poor one; 0.5 is chance), how
often two candidates of the same requester with different labels are ordered correctly,
and how often the top-scored candidate is labelled good; and how often the template's
reason for a good pair is specific rather than generic.

**Baseline, 2 October 2026, on 100 draft (unreviewed) pairs.** These are a baseline for
comparing changes, not a measure of quality, until the labels are reviewed.

| Metric | Word overlap | bge-small cosine |
| --- | --- | --- |
| Mean score: good / acceptable / poor | 0.077 / 0.044 / 0.006 | 0.614 / 0.581 / 0.518 |
| AUC good vs poor | 0.82 | 0.83 |
| AUC good or acceptable vs poor | 0.76 | 0.80 |
| Pairs ordered correctly (76 comparable) | 0.63 | 0.76 |
| Top-scored candidate is good (38 requesters) | 0.61 | 0.55 |

Template intent accuracy: 0.65 (26 of 40; it misses most `interest_buddy` and `explore`
requests, which use no fixed keywords). Template reasons that are specific for good pairs:
0.28. The LLM path is not measured yet: that needs reviewed labels and a provider key
(checklist item 24).

## Next steps

- Review all 100 drafts.
- Grow towards the 200-500 pairs ARCHITECTURE.md calls for, adding new profiles where
  the set is thin.
- Once labels are reviewed and the matching endpoints exist, run the full matcher over
  the pairs and report precision at 5 per intent, for the LLM path and the template path.
