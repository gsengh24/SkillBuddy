"""Privacy stripping, anonymous candidates, provider HTTP contract and AI settings."""

from __future__ import annotations

import json
import logging
import uuid

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.ai.candidates import MAX_CANDIDATES, CandidateSummary, anonymise
from app.ai.privacy import find_leaks, name_hints_from_email, redact
from app.ai.providers import (
    CLOUDFLARE_BASE_URL,
    GROQ_BASE_URL,
    ChatRequest,
    CostModel,
    OpenAICompatibleProvider,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    build_providers,
)
from tests.conftest import SettingsFactory

FAKE_KEY = "gsk_test_" + "k" * 40
ACCOUNT = "0123456789abcdef0123456789abcdef"

# --- redaction ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mail me at ananya.s@thapar.edu today", "Mail me at [email] today"),
        ("Call +91 98765 43210 or 9876543210.", "Call [phone] or [phone]."),
        ("WhatsApp (987) 654-3210", "WhatsApp [phone]"),
        ("See https://github.com/aarav/app and www.mysite.dev", "See [link] and [link]"),
        ("Portfolio: linkedin.com/in/aarav-s", "Portfolio: [link]"),
        ("DM me on insta @aarav.codes!", "DM me on insta [handle]!"),
        ("I'm Aarav Sharma, aarav for short", "I'm [name] [name], [name] for short"),
    ],
)
def test_contact_details_and_names_are_replaced(text: str, expected: str) -> None:
    assert redact(text, names=["Aarav Sharma"]) == expected


@pytest.mark.parametrize(
    "text",
    [
        "3rd year, batch 2019-2023, 5 hrs a week",
        "I use Node.js, Next.js and C++, e.g. for APIs",
        "Room 1204, about 40 people",
        "Aaravi is a different word",  # names match whole words only
    ],
)
def test_ordinary_text_is_kept(text: str) -> None:
    assert redact(text, names=["Aarav"]) == text
    assert find_leaks(text, names=["Aarav"]) == []


def test_redaction_is_idempotent_and_leaves_no_leaks() -> None:
    text = "ananya@x.in, +91 98765 43210, t.me/ananya, @ananya_s, Ananya"
    once = redact(text, names=["Ananya"])
    assert redact(once, names=["Ananya"]) == once
    assert find_leaks(once, names=["Ananya"]) == []
    assert set(find_leaks(text, names=["Ananya"])) == {"email", "phone", "link", "handle", "name"}


def test_name_hints_from_email() -> None:
    assert name_hints_from_email("ananya.sharma91@thapar.edu") == ["ananya", "sharma"]
    assert name_hints_from_email("ab@x.in") == []


# --- anonymous candidates -------------------------------------------------------------


def test_candidates_become_c1_to_cn_with_no_ids_names_or_contacts() -> None:
    people = [
        CandidateSummary(
            user_id=uuid.uuid4(),
            skills=["Figma", "UX writing, mail rohan@x.in"],
            interests=["civic tech"],
            goals=["Find a backend partner, I'm Rohan"],
            availability="weekends",
            name_hints=["Rohan"],
        ),
        CandidateSummary(user_id=uuid.uuid4(), skills=["Go"]),
    ]
    summaries, aliases = anonymise(people)

    assert [s["id"] for s in summaries] == ["C1", "C2"]
    assert aliases == {"C1": people[0].user_id, "C2": people[1].user_id}
    sent = json.dumps(summaries)
    assert str(people[0].user_id) not in sent
    assert "rohan" not in sent.lower()
    assert "[email]" in sent
    assert "[name]" in sent


def test_at_most_fifteen_candidates() -> None:
    many = [CandidateSummary(user_id=uuid.uuid4()) for _ in range(MAX_CANDIDATES + 1)]
    assert len(anonymise(many[:MAX_CANDIDATES])[0]) == 15
    with pytest.raises(ValueError, match="at most 15"):
        anonymise(many)


# --- provider HTTP contract -----------------------------------------------------------


def _provider(handler: httpx.MockTransport) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        provider="groq",
        base_url=GROQ_BASE_URL,
        api_key=SecretStr(FAKE_KEY),
        model="openai/gpt-oss-120b",
        cost=CostModel("tokens", 1, 1, 1000),
        client=httpx.AsyncClient(transport=handler),
        extra_body={"reasoning_effort": "low"},
    )


async def test_request_shape_and_key_only_in_the_authorization_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            },
        )

    result = await _provider(httpx.MockTransport(handler)).complete_json(
        ChatRequest(system="sys", user='{"text": "[email]"}')
    )

    request = seen[0]
    assert str(request.url) == f"{GROQ_BASE_URL}/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = json.loads(request.content)
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "low"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert FAKE_KEY not in request.content.decode()
    assert (result.content, result.input_tokens, result.output_tokens) == ('{"ok": true}', 120, 30)


@pytest.mark.parametrize(
    ("response", "error", "retry_after"),
    [
        (httpx.Response(429, headers={"retry-after": "7"}), ProviderRateLimitedError, 7.0),
        (httpx.Response(429), ProviderRateLimitedError, None),
        (httpx.Response(500, text=f"echo {FAKE_KEY}"), ProviderUnavailableError, None),
        (httpx.Response(200, text="not json"), ProviderUnavailableError, None),
        (httpx.Response(200, json={"choices": []}), ProviderUnavailableError, None),
    ],
)
async def test_provider_errors_carry_no_secrets(
    response: httpx.Response,
    error: type[Exception],
    retry_after: float | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = _provider(httpx.MockTransport(lambda _: response))
    with caplog.at_level(logging.DEBUG), pytest.raises(error) as raised:
        await provider.complete_json(ChatRequest(system="s", user="u"))

    assert FAKE_KEY not in str(raised.value)
    assert FAKE_KEY not in repr(provider)
    assert FAKE_KEY not in caplog.text
    if isinstance(raised.value, ProviderRateLimitedError):
        assert raised.value.retry_after_seconds == retry_after


async def test_network_errors_become_unavailable() -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(ProviderUnavailableError, match="ConnectError"):
        await _provider(httpx.MockTransport(fail)).complete_json(ChatRequest(system="s", user="u"))


# --- settings and provider wiring -----------------------------------------------------


def test_ai_defaults(make_settings: SettingsFactory) -> None:
    settings = make_settings()
    assert settings.ai_llm_enabled is True
    assert settings.ai_llm_providers == ["groq", "cloudflare"]
    assert settings.ai_llm_timeout_seconds == 20
    assert settings.groq_models == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert settings.cloudflare_model == "@cf/openai/gpt-oss-20b"


def test_lists_parse_from_env_and_keys_are_hidden(
    make_settings: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_LLM_PROVIDERS", "cloudflare, groq")
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    settings = make_settings()
    assert settings.ai_llm_providers == ["cloudflare", "groq"]
    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings.model_dump())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ai_llm_providers": ["openai"]}, "ai_llm_providers"),
        ({"cloudflare_account_id": "not-hex"}, "cloudflare_account_id"),
        ({"groq_api_key": "short"}, "groq_api_key"),
        ({"ai_llm_timeout_seconds": 0}, "ai_llm_timeout_seconds"),
    ],
)
def test_invalid_ai_settings_are_rejected(
    make_settings: SettingsFactory, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_settings(**overrides)


async def test_providers_follow_the_configured_order_and_need_their_keys(
    make_settings: SettingsFactory,
) -> None:
    async with httpx.AsyncClient() as client:
        none = build_providers(make_settings(), client)
        both = build_providers(
            make_settings(
                groq_api_key=FAKE_KEY,
                cloudflare_account_id=ACCOUNT,
                cloudflare_api_token="cf_" + "t" * 37,
            ),
            client,
        )
        cloudflare_first = build_providers(
            make_settings(
                ai_llm_providers=["cloudflare", "groq"],
                groq_api_key=FAKE_KEY,
                cloudflare_account_id=ACCOUNT,
                cloudflare_api_token="cf_" + "t" * 37,
            ),
            client,
        )

    assert none == []
    assert [p.name for p in both] == [
        "groq:openai/gpt-oss-120b",
        "groq:openai/gpt-oss-20b",
        "cloudflare:@cf/openai/gpt-oss-20b",
    ]
    assert cloudflare_first[0].name.startswith("cloudflare:")
    cloudflare = both[2]
    assert cloudflare.cost.unit == "neurons"
    assert CLOUDFLARE_BASE_URL.format(account_id=ACCOUNT) in repr(vars(cloudflare))
