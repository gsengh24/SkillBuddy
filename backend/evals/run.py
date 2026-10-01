"""Validate the evaluation set and print counts per intent and label.

Usage (from ``backend/``):  ``uv run python -m evals.run [DATA_DIR]``
Exits with status 1 if the data does not validate.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from evals.dataset import DATA_DIR, load_eval_set
from evals.schema import EvalSet, Intent, Label, ReviewStatus


def format_report(eval_set: EvalSet) -> str:
    counts = Counter((pair.intent, pair.label) for pair in eval_set.pairs)
    labels = list(Label)
    width = max(len(intent.value) for intent in Intent)

    header = f"{'intent':<{width}}  " + "  ".join(f"{label.value:>10}" for label in labels)
    lines = [header + f"  {'total':>6}", "-" * (len(header) + 8)]
    for intent in Intent:
        row = [counts[(intent, label)] for label in labels]
        cells = "  ".join(f"{n:>10}" for n in row)
        lines.append(f"{intent.value:<{width}}  {cells}  {sum(row):>6}")
    totals = [sum(counts[(intent, label)] for intent in Intent) for label in labels]
    cells = "  ".join(f"{n:>10}" for n in totals)
    lines.append(f"{'total':<{width}}  {cells}  {sum(totals):>6}")

    status = Counter(pair.review_status for pair in eval_set.pairs)
    summary = ", ".join(f"{s.value}: {status[s]}" for s in ReviewStatus)
    return "\n".join(
        [
            f"Profiles: {len(eval_set.profiles)}    Pairs: {len(eval_set.pairs)}",
            "",
            *lines,
            "",
            f"Review status: {summary}",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    data_dir = Path(args[0]) if args else DATA_DIR
    try:
        eval_set = load_eval_set(data_dir)
    except ValidationError as exc:
        sys.stderr.write(f"Evaluation data in {data_dir} is invalid:\n{exc}\n")
        return 1
    sys.stdout.write(format_report(eval_set) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
