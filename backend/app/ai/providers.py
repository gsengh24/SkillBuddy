"""LLM providers behind one small interface (ADR 0007, section 7).

Groq and Cloudflare Workers AI both offer an OpenAI-compatible chat-completions endpoint,
so one class (plain ``httpx``, no vendor SDK) covers both. API keys come only from settings
(environment variables), are sent only in the ``Authorization`` header, and never appear in
logs, errors or ``repr``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

import httpx
from pydantic import SecretStr

from app.core.config import Settings

GROQ_BASE_URL: Final = "https://api.groq.com/openai/v1"
CLOUDFLARE_BASE_URL: Final = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"


@dataclass(frozen=True)
class ChatRequest:
    system: str
    user: str
    max_tokens: int = 1200
    temperature: float = 0.2


@dataclass(frozen=True)
class ChatResult:
    content: str
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """The provider could not answer. ``kind`` is safe to log; nothing else is kept."""

    kind = "error"


class ProviderRateLimitedError(ProviderError):
    kind = "rate_limited"

    def __init__(self, retry_after_seconds: float | None) -> None:
        super().__init__("rate limited")
        self.retry_after_seconds = retry_after_seconds


class ProviderUnavailableError(ProviderError):
    kind = "unavailable"


@dataclass(frozen=True)
class CostModel:
    """How a provider counts against its free daily budget: units per input/output token.

    Groq budgets tokens (1 unit each). Cloudflare budgets neurons, priced per million
    tokens per model.
    """

    unit: str
    per_input_token: float
    per_output_token: float
    daily_budget: float

    def units(self, result: ChatResult) -> float:
        return (
            result.input_tokens * self.per_input_token
            + result.output_tokens * self.per_output_token
        )


class ChatProvider(Protocol):
    @property
    def name(self) -> str:
        """``"<provider>:<model>"``: also the key of its daily budget."""
        ...

    @property
    def cost(self) -> CostModel: ...

    async def complete_json(self, request: ChatRequest) -> ChatResult: ...


class OpenAICompatibleProvider:
    """A chat-completions endpoint in JSON mode."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: SecretStr,
        model: str,
        cost: CostModel,
        client: httpx.AsyncClient,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self._provider = provider
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._cost = cost
        self._client = client
        self._extra = extra_body or {}

    def __repr__(self) -> str:
        return f"OpenAICompatibleProvider(name={self.name!r})"

    @property
    def name(self) -> str:
        return f"{self._provider}:{self._model}"

    @property
    def cost(self) -> CostModel:
        return self._cost

    def request_body(self, request: ChatRequest) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            **self._extra,
        }

    async def complete_json(self, request: ChatRequest) -> ChatResult:
        try:
            response = await self._client.post(
                self._url,
                json=self.request_body(request),
                headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
            )
        except httpx.HTTPError as exc:
            # The message could include request details; keep only the type.
            raise ProviderUnavailableError(type(exc).__name__) from None
        if response.status_code == 429:
            raise ProviderRateLimitedError(_retry_after(response.headers.get("retry-after")))
        if response.status_code >= 400:
            raise ProviderUnavailableError(f"HTTP {response.status_code}")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            return ChatResult(
                content=str(content),
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            )
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderUnavailableError("malformed response") from None


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None


def build_providers(settings: Settings, client: httpx.AsyncClient) -> list[ChatProvider]:
    """The configured providers, in fallback order. A provider without a key is skipped."""
    providers: list[ChatProvider] = []
    for provider in settings.ai_llm_providers:
        if provider == "groq" and settings.groq_api_key is not None:
            for model in settings.groq_models:
                providers.append(
                    OpenAICompatibleProvider(
                        provider="groq",
                        base_url=GROQ_BASE_URL,
                        api_key=settings.groq_api_key,
                        model=model,
                        cost=CostModel("tokens", 1.0, 1.0, settings.groq_daily_token_budget),
                        client=client,
                        # gpt-oss reasoning tokens count against limits; keep them low.
                        extra_body={"reasoning_effort": "low"},
                    )
                )
        if (
            provider == "cloudflare"
            and settings.cloudflare_api_token is not None
            and settings.cloudflare_account_id
        ):
            providers.append(
                OpenAICompatibleProvider(
                    provider="cloudflare",
                    base_url=CLOUDFLARE_BASE_URL.format(account_id=settings.cloudflare_account_id),
                    api_key=settings.cloudflare_api_token,
                    model=settings.cloudflare_model,
                    cost=CostModel(
                        "neurons",
                        settings.cloudflare_neurons_per_m_input / 1_000_000,
                        settings.cloudflare_neurons_per_m_output / 1_000_000,
                        settings.cloudflare_daily_neuron_budget,
                    ),
                    client=client,
                )
            )
    return providers


@dataclass
class FakeProvider:
    """A provider for tests: scripted answers, errors or delays; records every request."""

    name: str
    replies: Sequence[str | Exception | Callable[[ChatRequest], str]] = ()
    delay_seconds: float = 0.0
    cost: CostModel = field(default_factory=lambda: CostModel("tokens", 1.0, 1.0, 1e9))
    tokens: tuple[int, int] = (100, 50)
    requests: list[ChatRequest] = field(default_factory=list)

    async def complete_json(self, request: ChatRequest) -> ChatResult:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        index = min(len(self.requests), len(self.replies)) - 1
        reply = self.replies[index] if self.replies else json.dumps({})
        if isinstance(reply, Exception):
            raise reply
        content = reply(request) if callable(reply) else reply
        return ChatResult(
            content=content, input_tokens=self.tokens[0], output_tokens=self.tokens[1]
        )
