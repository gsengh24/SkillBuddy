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

## Next steps

- Review all 100 drafts.
- Grow towards the 200-500 pairs ARCHITECTURE.md calls for, adding new profiles where
  the set is thin.
- In Phase 1, add the scorer that runs the matcher over the reviewed pairs and reports
  precision at 5 per intent.
