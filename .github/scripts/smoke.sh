#!/usr/bin/env bash
# Smoke checks against the full docker compose stack (CI job "Smoke").
# Run from the repository root after `docker compose up --build --detach --wait`.
set -euo pipefail

API="http://127.0.0.1:${API_PORT:-8000}"
WEB="http://127.0.0.1:${WEB_PORT:-3000}"
MAILPIT="http://127.0.0.1:${MAILPIT_UI_PORT:-8025}"

fail() {
  echo "::error::Smoke check failed: $*"
  exit 1
}

echo "== 1/5 API readiness: database, pgvector and Redis"
ready=$(curl -fsS --max-time 15 "$API/api/v1/health/ready") \
  || fail "GET /api/v1/health/ready did not return 2xx"
echo "$ready"
python3 - "$ready" <<'PY' || fail "readiness response is not all ok"
import json, sys
body = json.loads(sys.argv[1])
assert body["status"] == "ok", body
for name in ("database", "pgvector", "redis"):
    assert body["checks"][name]["status"] == "ok", (name, body["checks"][name])
PY

echo "== 2/5 Web page loads and shows the API as connected"
# The dev server compiles the page on first request, so allow time for that.
page=$(curl -fsS --max-time 180 "$WEB/") || fail "GET / on the web app did not return 2xx"
grep -q 'data-state="connected"' <<<"$page" \
  || fail "web page loaded but does not show the API as connected"
echo "web page: API connected"

echo "== 3/5 Arq worker runs the ping job"
docker compose exec -T api python - <<'PY' || fail "worker did not complete the ping job"
import asyncio

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings


async def main() -> None:
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url.unicode_string()))
    try:
        job = await redis.enqueue_job("ping")
        assert job is not None, "job was not enqueued"
        result = await job.result(timeout=60)
    finally:
        await redis.aclose()
    assert result == "pong", result
    print("worker: ping job returned", result)


asyncio.run(main())
PY

echo "== 4/5 Database migration applied"
current=$(docker compose exec -T api alembic current 2>/dev/null) \
  || fail "alembic current failed"
echo "alembic current: $current"
grep -q "(head)" <<<"$current" || fail "database is not at the latest migration (head)"
tables=$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA' <<'SQL'
SELECT count(*) FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('users', 'profiles', 'profile_embeddings');
SQL
)
[ "$(echo "$tables" | tr -d '[:space:]')" = "3" ] \
  || fail "expected the 3 Phase 0 tables, found: $tables"
echo "migration: at head, Phase 0 tables present"

echo "== 5/5 Sign-in code is emailed by the worker (via Mailpit) and accepted"
email="smoke-$(date +%s)@example.com"
curl -fsS --max-time 15 -X POST "$API/api/v1/auth/otp/request" \
  -H "Content-Type: application/json" -d "{\"email\": \"$email\"}" >/dev/null \
  || fail "POST /api/v1/auth/otp/request failed"
code=""
for _ in $(seq 1 30); do
  messages=$(curl -fsS --max-time 5 --get "$MAILPIT/api/v1/search" \
    --data-urlencode "query=to:$email" || echo "{}")
  code=$(python3 - "$messages" <<'PY'
import json, re, sys
for message in json.loads(sys.argv[1]).get("messages", []):
    match = re.search(r"\b(\d{6})\b", message.get("Snippet", ""))
    if match:
        print(match.group(1))
        break
PY
)
  [ -n "$code" ] && break
  sleep 2
done
[ -n "$code" ] || fail "no sign-in email reached Mailpit within 60s"
body="{\"email\": \"$email\", \"code\": \"$code\", \"accept_terms\": true}"
status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 -X POST \
  "$API/api/v1/auth/otp/verify" -H "Content-Type: application/json" -d "$body")
[ "$status" = "200" ] || fail "verifying the emailed code returned HTTP $status"
echo "sign-in: code emailed by the worker and accepted by the API"

echo "All smoke checks passed."
