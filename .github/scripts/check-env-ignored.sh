#!/usr/bin/env bash
# Fails if real environment files could be committed (CI job "Secret scan").
set -euo pipefail

status=0

# 1. Every place a real env file would live must be git-ignored.
for path in .env .env.local backend/.env frontend/.env frontend/.env.local infra/production.env; do
  if ! git check-ignore -q "$path"; then
    echo "::error::$path is not ignored by .gitignore"
    status=1
  fi
done

# 2. The example files must stay committable.
for path in .env.example backend/.env.example frontend/.env.example infra/production.env.example; do
  if git check-ignore -q "$path"; then
    echo "::error::$path is ignored but should be committed"
    status=1
  fi
done

# 3. No env file other than *.example is tracked.
tracked=$(git ls-files | grep -E '(^|/)\.env|\.env$' | grep -v '\.example$' || true)
if [ -n "$tracked" ]; then
  echo "::error::Tracked env files found:"
  echo "$tracked"
  status=1
fi

[ "$status" -eq 0 ] && echo ".env files are ignored; only *.example files are tracked."
exit "$status"
