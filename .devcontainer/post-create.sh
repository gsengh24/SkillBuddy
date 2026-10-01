#!/usr/bin/env bash
# Runs once when the Codespace / dev container is created.
# Installs editor-side dependencies; the app stack itself runs via docker compose.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Backend: installing Python dependencies with uv"
(cd backend && uv sync --frozen)

echo "==> Frontend: installing Node dependencies"
(cd frontend && npm ci --no-audit --no-fund)

echo "==> Installing git pre-commit hooks"
(cd backend && uv run pre-commit install)

echo
echo "Done. Start the full stack with:"
echo "  docker compose up --build --detach --wait"
