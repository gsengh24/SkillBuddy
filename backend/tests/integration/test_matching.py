"""Match requests, the matcher and its housekeeping, against real PostgreSQL + pgvector.

No real AI provider is called: most tests run the template stages, and the one that
checks what the judge is sent uses a fake provider. Retrieval tests place unit vectors
by hand so the expected order is known.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.embeddings import EmbedKind
from app.ai.gateway import AIGateway
from app.ai.providers import ChatRequest, FakeProvider
from app.ai.stages import Intent
from app.core.config import Settings
from app.db.engine import create_engine
from app.db.session import create_session_factory
from app.jobs import JobRegistry, JobRunner
from app.jobs.tasks import MATCH_REQUEST
from app.models import EMBEDDING_DIMENSIONS
from app.services.matching.engine import SEARCH, retrieve, run_match_request
from app.services.matching.housekeeping import expire_and_purge_requests
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client, run_sql
from tests.integration.test_auth_codes import error_code
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_profile_api import body as profile_body
from tests.integration.test_profile_api import signed_in

REQUESTS = "/api/v1/requests"
MODEL = "fixed-test-embedder@1"


def unit(*weights: tuple[int, float]) -> list[float]:
    """A unit vector with the given (axis, weight) entries."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for axis, weight in weights:
        vector[axis] = weight
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector]


class FixedEmbedder:
    """Every query embeds to the same vector, so retrieval order is predictable."""

    dimensions = EMBEDDING_DIMENSIONS

    def __init__(self, query: list[float], model_version: str = MODEL) -> None:
        self.query = query
        self.model_version = model_version

    async def embed(self, texts: Sequence[str], *, kind: EmbedKind) -> list[list[float]]:
        return [self.query for _ in texts]


@pytest.fixture
def model() -> str:
    """A model version of this test's own, so retrieval sees only this test's people."""
    return f"fixed-test-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url, ai_llm_enabled=False)


@pytest.fixture
async def session_factory(settings: Settings) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(settings)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def person(
    url: str,
    *,
    offer: list[float] | None = None,
    seek: list[float] | None = None,
    identity: list[float] | None = None,
    status: str = "active",
    visibility: str = "matchable",
    model: str,
    structured: dict[str, Any] | None = None,
    display_name: str = "Test Person",
) -> uuid.UUID:
    user = run_sql(
        url,
        "INSERT INTO users (email, status, last_login_at) VALUES (:e, :s, now()) RETURNING id",
        e=f"m-{uuid.uuid4().hex[:12]}@example.com",
        s=status,
    )[0]["id"]
    run_sql(
        url,
        "INSERT INTO profiles (user_id, display_name, raw_about_text, structured, visibility, "
        "parse_status) VALUES (:u, :n, 'I build things and like chess.', CAST(:s AS jsonb), "
        ":v, 'parsed')",
        u=user,
        n=display_name,
        s=json.dumps(
            structured
            or {"summary": "Builds web apps.", "offers": ["React"], "interests": ["chess"]}
        ),
        v=visibility,
    )
    for facet, vector in (("offer", offer), ("seek", seek), ("identity", identity)):
        if vector is not None:
            run_sql(
                url,
                "INSERT INTO profile_embeddings (user_id, facet, embedding, model_version) "
                "VALUES (:u, :f, CAST(:v AS vector), :m)",
                u=user,
                f=facet,
                v=json.dumps(vector),
                m=model,
            )
    return uuid.UUID(str(user))


def new_request(url: str, user: uuid.UUID, text: str, intent: str | None = None) -> uuid.UUID:
    row = run_sql(
        url,
        "INSERT INTO match_requests (user_id, raw_text, requested_intent, expires_at) "
        "VALUES (:u, :t, :i, now() + interval '30 days') RETURNING id",
        u=user,
        t=text,
        i=intent,
    )[0]
    return uuid.UUID(str(row["id"]))


def matches(url: str, request: uuid.UUID) -> list[dict[str, Any]]:
    return run_sql(
        url,
        "SELECT candidate_id, rank, reason, status FROM matches WHERE request_id = :r "
        "ORDER BY rank",
        r=request,
    )


async def match(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    request: uuid.UUID,
    query: list[float],
    model: str,
) -> bool:
    gateway = AIGateway(settings, session_factory, [], cooling_until={})
    return await run_match_request(
        session_factory, gateway, FixedEmbedder(query, model), settings, request
    )


# --- the matcher -------------------------------------------------------------------------


async def test_build_together_ranks_by_offer_and_applies_hard_filters(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60  # keeps this test's vectors apart from other tests'
    me = person(url, model=model, offer=unit((axis + 1, 1.0)))
    best = person(url, model=model, offer=unit((axis, 1.0)))
    good = person(url, model=model, offer=unit((axis, 0.8), (axis + 2, 0.6)))
    paused = person(url, model=model, offer=unit((axis, 1.0)), visibility="paused")
    after_intro = person(url, model=model, offer=unit((axis, 1.0)), visibility="after_intro")
    suspended = person(url, model=model, offer=unit((axis, 1.0)), status="suspended")
    paused_account = person(url, model=model, offer=unit((axis, 1.0)), status="paused")
    stale_model = person(url, offer=unit((axis, 1.0)), model="old-model@0")
    request = new_request(
        url, me, "Looking for a React developer to build an app.", "build_together"
    )

    assert await match(settings, session_factory, request, unit((axis, 1.0)), model)

    found = [row["candidate_id"] for row in matches(url, request)]
    assert found[:2] == [best, good]
    assert me not in found
    for excluded in (paused, after_intro, suspended, paused_account, stale_model):
        assert excluded not in found
    state = run_sql(
        url,
        "SELECT status, intent, explanation_source, prompt_version FROM match_requests "
        "WHERE id = :r",
        r=request,
    )[0]
    assert state == {
        "status": "ready",
        "intent": "build_together",
        "explanation_source": "template",
        "prompt_version": None,
    }
    assert all(len(row["reason"]) > 0 for row in matches(url, request))
    # Already ready: running again changes nothing (jobs can run twice).
    assert not await match(settings, session_factory, request, unit((axis, 1.0)), model)


async def test_blocks_are_a_hard_filter_both_ways(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60
    me = person(url, model=model, offer=unit((axis + 1, 1.0)))
    i_blocked = person(url, model=model, offer=unit((axis, 1.0)))
    blocked_me = person(url, model=model, offer=unit((axis, 1.0)))
    other = person(url, model=model, offer=unit((axis, 0.9), (axis + 2, 0.4)))
    run_sql(url, "INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)", a=me, b=i_blocked)
    run_sql(url, "INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b)", a=blocked_me, b=me)
    request = new_request(url, me, "Looking for a React developer.", "build_together")

    assert await match(settings, session_factory, request, unit((axis, 1.0)), model)

    found = [row["candidate_id"] for row in matches(url, request)]
    assert other in found
    assert i_blocked not in found
    assert blocked_me not in found


async def test_at_most_matches_per_request_and_names_never_in_reasons(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    model: str,
) -> None:
    url = migrated_database_url
    settings = make_settings(database_url=url, ai_llm_enabled=False, matches_per_request=3)
    axis = 300 + uuid.uuid4().int % 60
    me = person(url, model=model, offer=unit((axis + 1, 1.0)))
    for i in range(6):
        person(
            url,
            model=model,
            offer=unit((axis, 1.0), (axis + 3, 0.1 * i)),
            display_name=f"Zarathustra{i}",
            structured={"summary": "Zarathustra builds apps.", "offers": ["React"]},
        )
    request = new_request(url, me, "Need a React developer.", "build_together")
    await match(settings, session_factory, request, unit((axis, 1.0)), model)

    rows = matches(url, request)
    assert len(rows) == 3
    assert [row["rank"] for row in rows] == [1, 2, 3]
    assert all("Zarathustra" not in row["reason"] for row in rows)


async def test_the_judge_gets_both_profiles_and_nothing_that_says_who_they_are(
    make_settings: SettingsFactory,
    migrated_database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    model: str,
) -> None:
    url = migrated_database_url
    settings = make_settings(database_url=url)
    run_sql(url, "DELETE FROM rate_limit_counters WHERE key LIKE 'ai:%'")
    axis = 300 + uuid.uuid4().int % 60
    me = person(
        url,
        model=model,
        offer=unit((axis + 1, 1.0)),
        display_name="Asha Hiddenname",
        structured={"summary": "Builds apps.", "offers": ["Python"], "seeks": ["Firmware help"]},
    )
    candidate = person(
        url,
        model=model,
        offer=unit((axis, 1.0)),
        display_name="Ishaan Secretname",
        structured={"summary": "Writes firmware.", "offers": ["Firmware"], "seeks": ["A team"]},
    )
    run_sql(
        url,
        "UPDATE profiles SET goal = 'Build a line follower with Ishaan', "
        "available_days = ARRAY['sat', 'sun'], weekly_hours = '4_6', city = 'Secretcity', "
        "experience_level = '1_3_years' WHERE user_id = :u",
        u=candidate,
    )
    run_sql(url, "UPDATE profiles SET goal = 'My private goal' WHERE user_id = :u", u=me)
    request = new_request(url, me, "Need someone for firmware.", "build_together")

    def judge(sent: ChatRequest) -> str:
        # Other tests' people may be candidates too: rate only the one who writes firmware.
        verdicts = [
            {"id": c["id"], "need": 3, "shared": 2, "reason": "They write firmware, as asked."}
            for c in json.loads(sent.user)["candidates"]
            if "Firmware" in c["skills"]
        ]
        return json.dumps({"verdicts": verdicts})

    groq = FakeProvider(
        name=f"groq-{uuid.uuid4().hex[:6]}",
        replies=[json.dumps({"intent": "build_together", "seeks": ["Firmware"]}), judge],
    )
    gateway = AIGateway(settings, session_factory, [groq], cooling_until={})
    await run_match_request(
        session_factory, gateway, FixedEmbedder(unit((axis, 1.0)), model), settings, request
    )

    body = groq.requests[-1].user
    sent = json.loads(body)
    # The requester: only what was read from their description.
    assert sent["student"] == {
        "skills": ["Python"],
        "interests": [],
        "goals": ["Firmware help"],
        "availability": "",
    }
    mine = next(c for c in sent["candidates"] if "Firmware" in c["skills"])
    assert set(mine) == {"id", "skills", "interests", "goals", "availability"}
    # Their goal in their own words (names removed), then the parsed tags.
    assert mine["goals"] == ["Build a line follower with [name]", "A team"]
    assert mine["availability"] == "Sat, Sun; 4 to 6 hours a week"
    for secret in (
        "Ishaan",
        "Secretname",
        "Asha",
        "Hiddenname",
        "Secretcity",
        "1_3_years",
        "private goal",
        str(candidate),
        str(me),
    ):
        assert secret not in body
    assert [row["candidate_id"] for row in matches(url, request)] == [candidate]


async def test_weak_fits_are_not_suggested_unless_their_words_match(
    make_settings: SettingsFactory,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60
    weak_vector = unit((axis, 0.5), (axis + 2, 0.866))  # cosine 0.5 with the query
    potter = {"summary": "Makes pots.", "offers": ["Pottery"]}
    me = person(url, model=model, offer=unit((axis + 1, 1.0)))
    strong = person(url, model=model, offer=unit((axis, 1.0)), structured=potter)
    weak = person(url, model=model, offer=weak_vector, structured=potter)
    weak_with_the_skill = person(
        url,
        model=model,
        offer=weak_vector,
        structured={"summary": "Builds web apps.", "offers": ["React development"]},
    )
    request = new_request(url, me, "Looking for a React developer.", "build_together")

    assert await match(settings, session_factory, request, unit((axis, 1.0)), model)

    assert [row["candidate_id"] for row in matches(url, request)] == [strong, weak_with_the_skill]

    # With the floor off, the weak fit is suggested too, last.
    no_floor = make_settings(database_url=url, ai_llm_enabled=False, match_min_relevance=0)
    again = new_request(url, me, "Looking for a React developer.", "build_together")
    assert await match(no_floor, session_factory, again, unit((axis, 1.0)), model)
    assert [row["candidate_id"] for row in matches(url, again)][-1] == weak


async def test_nobody_good_enough_is_ready_with_no_matches(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60
    me = person(url, model=model, offer=unit((axis + 1, 1.0)))
    person(
        url,
        model=model,
        offer=unit((axis, 0.5), (axis + 2, 0.866)),
        structured={"summary": "Makes pots.", "offers": ["Pottery"]},
    )
    request = new_request(url, me, "Looking for a React developer.", "build_together")

    assert await match(settings, session_factory, request, unit((axis, 1.0)), model)

    assert matches(url, request) == []
    state = run_sql(url, "SELECT status FROM match_requests WHERE id = :r", r=request)
    assert state == [{"status": "ready"}]
    notified = run_sql(url, "SELECT count(*) AS n FROM notifications WHERE user_id = :u", u=me)
    assert notified == [{"n": 0}]


async def test_keyword_search_finds_people_the_vector_search_missed(
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60
    potter = {"summary": "Makes pots.", "offers": ["Pottery"]}
    me = person(url, model=model, offer=unit((axis + 1, 1.0)))
    nearest = person(url, model=model, offer=unit((axis, 1.0)), structured=potter)
    far_with_the_skill = person(
        url,
        model=model,
        offer=unit((axis + 2, 1.0)),
        structured={"summary": "Builds web apps.", "offers": ["React"]},
    )
    person(url, model=model, offer=unit((axis + 3, 1.0)), structured=potter)
    # No parsed offers: the keyword search reads their own words ("... and like chess.").
    unparsed = person(
        url, model=model, offer=unit((axis + 4, 1.0)), structured={"summary": "New here."}
    )

    async def search(keywords: str) -> dict[uuid.UUID, float]:
        async with session_factory() as db:
            found = await retrieve(
                db,
                requester_id=me,
                query_vector=unit((axis, 1.0)),
                keywords=keywords,
                search=SEARCH[Intent.BUILD_TOGETHER],
                model_version=model,
                with_vectors=False,
                limit=1,
            )
        return {candidate.user_id: candidate.keyword for candidate in found}

    # One from each search: the nearest vector, and the best keyword overlap.
    assert await search("React developers") == {nearest: 0.0, far_with_the_skill: 0.5}
    assert await search("chess") == {nearest: 0.0, unparsed: 1.0}
    # Nothing but stop words to look for: the vector search alone.
    assert await search("the and of") == {nearest: 0.0}


async def test_no_candidates_is_ready_with_no_matches(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    me = person(url, model=model)
    request = new_request(url, me, "Someone for underwater basket weaving.", "interest_buddy")
    # The interest facet of nobody matches this test's model version.
    settings_model = FixedEmbedder(unit((5, 1.0)), model_version=f"nobody-{uuid.uuid4().hex[:6]}")
    gateway = AIGateway(settings, session_factory, [], cooling_until={})
    assert await run_match_request(session_factory, gateway, settings_model, settings, request)
    assert matches(url, request) == []
    status = run_sql(url, "SELECT status FROM match_requests WHERE id = :r", r=request)
    assert status == [{"status": "ready"}]


async def test_a_closed_request_is_not_matched(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    me = person(url, model=model)
    request = new_request(url, me, "Anyone to build a game with?")
    run_sql(url, "UPDATE match_requests SET status = 'closed' WHERE id = :r", r=request)
    assert not await match(settings, session_factory, request, unit((7, 1.0)), model)
    assert matches(url, request) == []


# --- housekeeping ------------------------------------------------------------------------


async def test_housekeeping_expires_then_deletes(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    me = person(url, model=model)
    other = person(url, model=model)
    expiring = new_request(url, me, "Old request that has expired.")
    ancient = new_request(url, me, "Very old request to delete.")
    fresh = new_request(url, me, "A request made today.")
    run_sql(
        url,
        "UPDATE match_requests SET status = 'ready', expires_at = now() - interval '1 day' "
        "WHERE id = :r",
        r=expiring,
    )
    run_sql(
        url,
        "INSERT INTO matches (request_id, candidate_id, rank, score, reason) "
        "VALUES (:r, :c, 1, 0.5, 'A reason.')",
        r=expiring,
        c=other,
    )
    run_sql(
        url,
        "UPDATE match_requests SET created_at = now() - interval '200 days' WHERE id = :r",
        r=ancient,
    )
    async with session_factory() as db:
        result = await expire_and_purge_requests(db, settings, datetime.now(UTC))

    assert result.expired >= 1
    assert result.deleted >= 1
    rows = {
        row["id"]: row["status"]
        for row in run_sql(url, "SELECT id, status FROM match_requests WHERE user_id = :u", u=me)
    }
    assert rows[expiring] == "expired"
    assert rows[fresh] == "pending"
    assert ancient not in rows
    assert [row["status"] for row in matches(url, expiring)] == ["expired"]


# --- the API -----------------------------------------------------------------------------


async def test_requests_need_sign_in_and_a_profile(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.post(REQUESTS, json={"text": "Looking for a designer."})
        token = await signed_in(client, settings, delivery)
        no_profile = await client.post(
            REQUESTS, json={"text": "Looking for a designer."}, headers=bearer(token)
        )
    assert anonymous.status_code == 401
    assert no_profile.status_code == 409
    assert error_code(no_profile) == "profile_required"


async def test_create_read_list_close(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put("/api/v1/me/profile", json=profile_body(), headers=bearer(token))
        created = await client.post(
            REQUESTS,
            json={"text": "  Looking for a designer for my app.  ", "intent": "build_together"},
            headers=bearer(token),
        )
        request_id = created.json()["id"]
        fetched = await client.get(f"{REQUESTS}/{request_id}", headers=bearer(token))
        pending_matches = await client.get(
            f"{REQUESTS}/{request_id}/matches", headers=bearer(token)
        )
        listed = await client.get(REQUESTS, headers=bearer(token))
        closed = await client.post(f"{REQUESTS}/{request_id}/close", headers=bearer(token))

    assert created.status_code == 202, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["text"] == "Looking for a designer for my app."
    assert body["requested_intent"] == "build_together"
    # The matcher writes the heading; there is none while the request is pending.
    assert body["title"] == ""
    assert body["match_count"] == 0
    assert fetched.json() == body
    assert pending_matches.json() == {"items": []}
    assert [item["id"] for item in listed.json()["items"]] == [request_id]
    assert closed.json()["status"] == "closed"
    jobs = run_sql(
        migrated_database_url,
        "SELECT status FROM jobs WHERE kind = 'match_request' AND payload->>'request_id' = :r",
        r=request_id,
    )
    assert jobs == [{"status": "queued"}]


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "too short"},
        {"text": "x" * 1001},
        {"text": "Looking for a designer.", "intent": "romance"},
        {"text": "Looking for a designer.", "user_id": str(uuid.uuid4())},
        {},
    ],
)
async def test_create_validation(
    settings: Settings, delivery: CapturingDelivery, payload: dict[str, Any]
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        response = await client.post(REQUESTS, json=payload, headers=bearer(token))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


async def test_someone_elses_request_is_not_found(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        owner = await signed_in(client, settings, delivery)
        await client.put("/api/v1/me/profile", json=profile_body(), headers=bearer(owner))
        request_id = (
            await client.post(
                REQUESTS, json={"text": "Looking for a designer."}, headers=bearer(owner)
            )
        ).json()["id"]
        stranger = await signed_in(client, settings, delivery)
        responses = [
            await client.get(f"{REQUESTS}/{request_id}", headers=bearer(stranger)),
            await client.get(f"{REQUESTS}/{request_id}/matches", headers=bearer(stranger)),
            await client.post(f"{REQUESTS}/{request_id}/close", headers=bearer(stranger)),
            await client.get(f"{REQUESTS}/{uuid.uuid4()}", headers=bearer(stranger)),
        ]
        bad_id = await client.get(f"{REQUESTS}/not-a-uuid", headers=bearer(stranger))
    for response in responses:
        assert response.status_code == 404
        assert error_code(response) == "match_request_not_found"
    assert bad_id.status_code == 422


async def test_open_request_and_daily_limits(
    make_settings: SettingsFactory, migrated_database_url: str, delivery: CapturingDelivery
) -> None:
    settings = make_settings(
        database_url=migrated_database_url,
        ai_llm_enabled=False,
        max_open_match_requests=2,
        match_requests_per_day=3,
    )
    text = {"text": "Looking for a designer."}
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put("/api/v1/me/profile", json=profile_body(), headers=bearer(token))
        first = await client.post(REQUESTS, json=text, headers=bearer(token))
        await client.post(REQUESTS, json=text, headers=bearer(token))
        too_many_open = await client.post(REQUESTS, json=text, headers=bearer(token))
        await client.post(f"{REQUESTS}/{first.json()['id']}/close", headers=bearer(token))
        third = await client.post(REQUESTS, json=text, headers=bearer(token))
        await client.post(f"{REQUESTS}/{third.json()['id']}/close", headers=bearer(token))
        over_daily = await client.post(REQUESTS, json=text, headers=bearer(token))
    assert error_code(too_many_open) == "too_many_open_requests"
    assert third.status_code == 202
    assert over_daily.status_code == 429


async def test_pagination_with_a_cursor(
    settings: Settings, delivery: CapturingDelivery, migrated_database_url: str
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put("/api/v1/me/profile", json=profile_body(), headers=bearer(token))
        me = (await client.get("/api/v1/auth/me", headers=bearer(token))).json()["id"]
        made = [
            new_request(migrated_database_url, uuid.UUID(me), f"Request number {i}.")
            for i in range(5)
        ]
        first = (await client.get(f"{REQUESTS}?limit=2", headers=bearer(token))).json()
        second = (
            await client.get(
                f"{REQUESTS}?limit=2&cursor={first['next_cursor']}", headers=bearer(token)
            )
        ).json()
        third = (
            await client.get(
                f"{REQUESTS}?limit=2&cursor={second['next_cursor']}", headers=bearer(token)
            )
        ).json()
        bad = await client.get(f"{REQUESTS}?cursor=garbage", headers=bearer(token))
    seen = [item["id"] for page in (first, second, third) for item in page["items"]]
    assert sorted(seen) == sorted(str(r) for r in made)
    assert len(set(seen)) == 5
    assert third["next_cursor"] is None
    assert bad.status_code == 400
    assert error_code(bad) == "invalid_cursor"


async def test_matches_show_no_name_links_or_contacts(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    delivery: CapturingDelivery,
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    axis = 300 + uuid.uuid4().int % 60
    candidate = person(
        url,
        model=model,
        offer=unit((axis, 1.0)),
        display_name="Ishaan Secretname",
        structured={"title": "React developer", "summary": "Builds web apps.", "offers": ["React"]},
    )
    run_sql(
        url,
        "UPDATE profiles SET links = ARRAY['https://github.com/ishaan'], languages = ARRAY['en'], "
        "city = 'Secretcity', location_precision = 'hidden' WHERE user_id = :u",
        u=candidate,
    )
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        await client.put("/api/v1/me/profile", json=profile_body(), headers=bearer(token))
        request_id = (
            await client.post(
                REQUESTS,
                json={"text": "Looking for a React developer.", "intent": "build_together"},
                headers=bearer(token),
            )
        ).json()["id"]
        await match(settings, session_factory, uuid.UUID(request_id), unit((axis, 1.0)), model)
        response = await client.get(f"{REQUESTS}/{request_id}/matches", headers=bearer(token))
        request = await client.get(f"{REQUESTS}/{request_id}", headers=bearer(token))

    items = response.json()["items"]
    mine = next(item for item in items if item["candidate"]["user_id"] == str(candidate))
    assert mine["rank"] == 1
    assert mine["candidate"]["offers"] == ["React"]
    assert mine["candidate"]["title"] == "React developer"
    assert mine["candidate"]["languages"] == ["en"]
    assert set(mine["candidate"]) == {
        "user_id",
        "title",
        "summary",
        "offers",
        "seeks",
        "interests",
        "availability",
        "languages",
        # Only as the person's location precision allows: here "hidden", so nothing.
        "location",
    }
    assert mine["candidate"]["location"] is None
    assert "Secretname" not in response.text
    assert "Secretcity" not in response.text
    assert "github.com/ishaan" not in response.text
    assert request.json()["status"] == "ready"
    assert request.json()["match_count"] == len(items)


async def test_the_job_runs_the_matcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    migrated_database_url: str,
    model: str,
) -> None:
    url = migrated_database_url
    me = person(url, model=model)
    request = new_request(url, me, "Anyone up for chess on weekends?")
    run_sql(
        url,
        "INSERT INTO jobs (kind, payload) VALUES ('match_request', CAST(:p AS jsonb))",
        p=json.dumps({"request_id": str(request)}),
    )
    await JobRunner(session_factory, JobRegistry([MATCH_REQUEST]), settings).run_until_idle()
    state = run_sql(url, "SELECT status, intent FROM match_requests WHERE id = :r", r=request)
    assert state == [{"status": "ready", "intent": "interest_buddy"}]
