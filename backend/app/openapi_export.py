"""The API contract as a file: ``docs/api/openapi.json``.

``python -m app.openapi_export`` writes the OpenAPI schema of the current code there.
``python -m app.openapi_export --check`` fails when the committed file is out of date; CI
runs it in the Backend job and uploads the freshly generated schema as the
``openapi-spec`` artifact, so a stale file can be replaced with that artifact.

The version in the file is fixed ("v1", the API version) rather than the build version,
so the file only changes when the contract does.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.config import Settings

REPO_DIR = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_DIR / "docs" / "api" / "openapi.json"


def build(settings: Settings) -> str:
    """The OpenAPI schema as stable, sorted JSON text."""
    from app.main import create_app

    schema = create_app(settings).openapi()
    schema["info"]["version"] = "v1"
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def run(settings: Settings, *, check: bool, spec: Path, out: Path | None) -> int:
    text = build(settings)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    if not check:
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(text, encoding="utf-8")
        sys.stdout.write(f"Wrote {spec.relative_to(REPO_DIR)}\n")
        return 0
    current = spec.read_text(encoding="utf-8") if spec.exists() else ""
    if current == text:
        sys.stdout.write("docs/api/openapi.json is up to date.\n")
        return 0
    sys.stdout.write(
        "::error title=OpenAPI spec::docs/api/openapi.json is out of date. Regenerate it with "
        "`uv run python -m app.openapi_export` (or use the openapi-spec artifact of this run).\n"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the file is out of date.")
    parser.add_argument("--out", type=Path, help="Also write the generated schema here.")
    args = parser.parse_args(argv)
    from app.core.config import get_settings

    return run(get_settings(), check=args.check, spec=SPEC_PATH, out=args.out)


if __name__ == "__main__":
    sys.exit(main())
