"""GET /skills/suggest, against a running app."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from tests.conftest import SettingsFactory
from tests.integration.conftest import CapturingDelivery, auth_client
from tests.integration.test_auth_codes import error_code
from tests.integration.test_auth_sessions import bearer
from tests.integration.test_profile_api import signed_in

SUGGEST = "/api/v1/skills/suggest"


@pytest.fixture
def settings(make_settings: SettingsFactory, migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url, ai_llm_enabled=False)


async def test_suggestions_need_sign_in(settings: Settings, delivery: CapturingDelivery) -> None:
    async with auth_client(settings, delivery) as client:
        anonymous = await client.get(SUGGEST, params={"q": "py"})

    assert anonymous.status_code == 401
    assert error_code(anonymous) == "authentication_required"


async def test_suggestions_match_a_prefix_and_honour_the_limit(
    settings: Settings, delivery: CapturingDelivery
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        found = await client.get(SUGGEST, params={"q": "pyth"}, headers=bearer(token))
        limited = await client.get(SUGGEST, params={"q": "sql", "limit": 2}, headers=bearer(token))
        none = await client.get(SUGGEST, params={"q": "zzzzqqqq"}, headers=bearer(token))

    assert found.status_code == 200
    assert found.json()["items"][0] == {"name": "Python"}
    assert limited.status_code == 200
    assert len(limited.json()["items"]) == 2
    assert none.status_code == 200
    assert none.json() == {"items": []}


@pytest.mark.parametrize(
    "params",
    [{}, {"q": ""}, {"q": "x" * 61}, {"q": "py", "limit": 0}, {"q": "py", "limit": 21}],
)
async def test_bad_queries_are_validation_errors(
    settings: Settings, delivery: CapturingDelivery, params: dict[str, str | int]
) -> None:
    async with auth_client(settings, delivery) as client:
        token = await signed_in(client, settings, delivery)
        response = await client.get(SUGGEST, params=params, headers=bearer(token))

    assert response.status_code == 422
