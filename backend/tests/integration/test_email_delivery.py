"""Email goes out through real SMTP (Mailpit), sent by a background job, never inline."""

from __future__ import annotations

import os
import uuid

from app.core.config import Settings
from app.services.email import EmailMessage, SmtpEmailSender, build_email_sender
from app.services.email.templates import login_code_email
from tests.conftest import SettingsFactory
from tests.integration.conftest import AUTH_VALKEY_DB, auth_client, redis_url_with_db, run_sql
from tests.integration.mailpit import code_from, wait_for_message


def smtp_settings(make_settings: SettingsFactory, **overrides: object) -> Settings:
    return make_settings(
        email_backend="smtp",
        smtp_host=os.environ.get("SMTP_HOST", "localhost"),
        smtp_port=int(os.environ.get("SMTP_PORT", "1025")),
        smtp_security="none",
        email_from_address="no-reply@example.com",
        **overrides,
    )


def new_email() -> str:
    return f"mail-{uuid.uuid4().hex[:12]}@example.com"


async def test_smtp_sender_delivers_text_and_html(make_settings: SettingsFactory) -> None:
    settings = smtp_settings(make_settings)
    to = new_email()

    await SmtpEmailSender(settings).send(
        EmailMessage(to=to, subject="Hello", text="Plain body", html="<p>HTML body</p>")
    )

    message = await wait_for_message(to)
    assert message["Subject"] == "Hello"
    assert message["From"]["Name"] == settings.app_name
    assert message["From"]["Address"] == "no-reply@example.com"
    assert "Plain body" in message["Text"]
    assert "HTML body" in message["HTML"]


async def test_login_code_email_uses_the_product_name(make_settings: SettingsFactory) -> None:
    settings = smtp_settings(make_settings)
    to = new_email()

    await build_email_sender(settings).send(login_code_email(settings, to, "042917"))

    message = await wait_for_message(to)
    assert message["Subject"] == f"Your {settings.app_name} sign-in code"
    assert code_from(message) == "042917"
    assert settings.app_name in message["HTML"]
    assert "10 minutes" in message["Text"]


async def test_api_emails_the_code_in_the_background_and_it_signs_the_user_in(
    make_settings: SettingsFactory, migrated_database_url: str
) -> None:
    """The full path: the API enqueues the job with the code, its in-process runner sends it
    via SMTP after the request has returned, and the emailed code signs in (ADR 0008)."""
    settings = smtp_settings(
        make_settings,
        database_url=migrated_database_url,
        redis_url=redis_url_with_db(AUTH_VALKEY_DB),
    )
    email = new_email()
    async with auth_client(settings, delivery=None) as client:
        requested = await client.post("/api/v1/auth/otp/request", json={"email": email})
        code = code_from(await wait_for_message(email))
        signed_in = await client.post(
            "/api/v1/auth/otp/verify",
            json={"email": email, "code": code, "age_confirmed": True, "accept_terms": True},
        )

    assert requested.status_code == 202
    assert signed_in.status_code == 200
    assert signed_in.json()["email"] == email
    jobs = run_sql(
        migrated_database_url,
        "SELECT status, payload::text AS payload FROM jobs WHERE kind = 'send_login_code' "
        "AND created_at > now() - interval '1 minute' ORDER BY created_at DESC LIMIT 1",
    )
    assert jobs[0]["status"] == "succeeded"
    assert code not in jobs[0]["payload"]  # the code never reaches the jobs table
    assert email not in jobs[0]["payload"]
