"""Load the committed evaluation data from JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from evals.schema import EvalSet

DATA_DIR: Final = Path(__file__).parent / "data"
PROFILES_FILE: Final = "profiles.json"
PAIRS_FILE: Final = "pairs.json"


def load_eval_set(data_dir: Path = DATA_DIR) -> EvalSet:
    """Read and validate the dataset; raises ``pydantic.ValidationError`` if invalid."""
    profiles = json.loads((data_dir / PROFILES_FILE).read_text(encoding="utf-8"))
    pairs = json.loads((data_dir / PAIRS_FILE).read_text(encoding="utf-8"))
    return EvalSet.model_validate({"profiles": profiles, "pairs": pairs})
