"""The Gmail API sender over a mocked HTTPS transport (no real Google call)."""

from __future__ import annotations

import base64
import email
import json
import logging
from collections.abc import Callable
from email import policy
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings
from app.services.email import senders
from app.services.email.senders import (
    GMAIL_SEND_URL,
    GMAIL_TOKEN_URL,
    EmailDeliveryError,
    EmailMessage,
    GmailApiEmailSender,
    build_email_sender,
)
from tests.conftest import SettingsFactory

SECRET = "gocspx-client-secret-for-tests"
REFRESH = "1//refresh-token-for-tests-xyz"
MESSAGE = EmailMessage(
    to="ananya@thapar.edu", subject="Your code", text="Code: 493817", html="<p>493817</p>"
)


@pytest.fixture
def gmail_settings(make_settings: SettingsFactory) -> Settings:
    senders._access_tokens.clear()
    return make_settings(
        email_backend="gmail_api",
        gmail_client_id="123-abc.apps.googleusercontent.com",
        gmail_client_secret=SECRET,
        gmail_refresh_token=REFRESH,
        gmail_sender="skillbuddy.mail@gmail.com",
    )


def _sender(
    settings: Settings, handler: Callable[[httpx.Request], httpx.Response]
) -> GmailApiEmailSender:
    return GmailApiEmailSender(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_refreshes_a_token_once_and_sends_a_mime_message(gmail_settings: Settings) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if str(request.url) == GMAIL_TOKEN_URL:
            return httpx.Response(200, json={"access_token": "ya29.token", "expires_in": 3599})
        return httpx.Response(200, json={"id": "18c0ffee"})

    sender = _sender(gmail_settings, handler)
    first = await sender.send(MESSAGE)
    await sender.send(MESSAGE)

    assert first == "18c0ffee"
    assert [str(c.url) for c in calls] == [GMAIL_TOKEN_URL, GMAIL_SEND_URL, GMAIL_SEND_URL]
    form = parse_qs(calls[0].content.decode())
    assert form["grant_type"] == ["refresh_token"]
    assert form["refresh_token"] == [REFRESH]
    send = calls[1]
    assert send.headers["authorization"] == "Bearer ya29.token"
    raw = json.loads(send.content)["raw"]
    mail = email.message_from_bytes(
        base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)), policy=policy.default
    )
    assert mail["To"] == "ananya@thapar.edu"
    assert mail["Subject"] == "Your code"
    assert "skillbuddy.mail@gmail.com" in mail["From"]
    assert "Skill Buddy" in mail["From"]
    assert SECRET not in send.content.decode()
    assert REFRESH not in send.content.decode()


@pytest.mark.parametrize(
    ("token_response", "level"),
    [
        (httpx.Response(400, json={"error": "invalid_grant"}), logging.ERROR),
        (httpx.Response(500, text="oops"), logging.WARNING),
    ],
)
async def test_token_failures_are_logged_without_secrets(
    gmail_settings: Settings,
    token_response: httpx.Response,
    level: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = _sender(gmail_settings, lambda _: token_response)
    with caplog.at_level(logging.DEBUG), pytest.raises(EmailDeliveryError) as raised:
        await sender.send(MESSAGE)

    record = next(r for r in caplog.records if r.getMessage() == "gmail_token_failed")
    assert record.levelno == level
    for secret in (SECRET, REFRESH):
        assert secret not in caplog.text
        assert secret not in str(raised.value)
        assert secret not in repr(sender)


async def test_send_failure_and_401_renewal(gmail_settings: Settings) -> None:
    tokens = iter(["first", "second"])
    statuses = iter([401, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == GMAIL_TOKEN_URL:
            return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})
        return httpx.Response(next(statuses), json={"id": "ok"})

    sender = _sender(gmail_settings, handler)
    with pytest.raises(EmailDeliveryError, match="HTTP 401"):
        await sender.send(MESSAGE)
    assert await sender.send(MESSAGE) == "ok"  # a fresh token was fetched


async def test_network_errors_become_delivery_errors(gmail_settings: Settings) -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    with pytest.raises(EmailDeliveryError, match="ConnectTimeout"):
        await _sender(gmail_settings, fail).send(MESSAGE)


def test_gmail_settings_rules(make_settings: SettingsFactory, gmail_settings: Settings) -> None:
    assert isinstance(build_email_sender(gmail_settings), GmailApiEmailSender)
    assert SECRET not in repr(gmail_settings)
    with pytest.raises(ValidationError, match="GMAIL_REFRESH_TOKEN"):
        make_settings(email_backend="gmail_api", gmail_client_id="x")
    with pytest.raises(ValidationError, match="EMAIL_RESERVE_FOR_CODES"):
        make_settings(email_daily_cap=100, email_reserve_for_codes=100)
    deployed = make_settings(
        environment=Environment.STAGING,
        email_backend="gmail_api",
        embedding_backend="fastembed",
        gmail_client_id="123-abc.apps.googleusercontent.com",
        gmail_client_secret=SECRET,
        gmail_refresh_token=REFRESH,
        gmail_sender="skillbuddy.mail@gmail.com",
    )
    assert deployed.email_backend == "gmail_api"
    assert (deployed.email_daily_cap, deployed.email_reserve_for_codes) == (450, 150)
