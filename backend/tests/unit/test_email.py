"""Email templates and transports that need no infrastructure."""

from __future__ import annotations

import io

import pytest

from app.services.email import (
    ConsoleEmailSender,
    EmailDeliveryError,
    EmailMessage,
    SmtpEmailSender,
    build_email_sender,
)
from app.services.email.templates import login_code_email
from tests.conftest import SettingsFactory


def test_login_code_email_contains_code_name_and_expiry(make_settings: SettingsFactory) -> None:
    settings = make_settings()

    message = login_code_email(settings, "a@example.com", "042917")

    assert message.to == "a@example.com"
    assert message.subject == f"Your {settings.app_name} sign-in code"
    assert "042917" not in message.subject  # codes stay out of subject lines / lock screens
    for body in (message.text, message.html):
        assert "042917" in body
        assert "10 minutes" in body


def test_html_template_escapes_the_product_name(make_settings: SettingsFactory) -> None:
    message = login_code_email(make_settings(app_name="Skill <Buddy>"), "a@example.com", "123456")

    assert "Skill &lt;Buddy&gt;" in message.html
    assert "Skill <Buddy>" in message.text


async def test_console_sender_writes_the_message() -> None:
    outbox = io.StringIO()

    await ConsoleEmailSender(outbox).send(
        EmailMessage(to="a@example.com", subject="Hi", text="Body", html="<p>Body</p>")
    )

    assert "a@example.com" in outbox.getvalue()
    assert "Body" in outbox.getvalue()


def test_backend_setting_selects_the_sender(make_settings: SettingsFactory) -> None:
    assert isinstance(build_email_sender(make_settings()), ConsoleEmailSender)
    assert isinstance(build_email_sender(make_settings(email_backend="smtp")), SmtpEmailSender)


@pytest.mark.parametrize("security", ["none", "ssl"])
async def test_smtp_failure_raises_a_retryable_error(
    make_settings: SettingsFactory, security: str
) -> None:
    settings = make_settings(
        email_backend="smtp",
        smtp_host="127.0.0.1",
        smtp_port=1,  # nothing listens here
        smtp_security=security,
        smtp_timeout_seconds=2,
    )

    with pytest.raises(EmailDeliveryError):
        await SmtpEmailSender(settings).send(
            EmailMessage(to="a@example.com", subject="Hi", text="Body", html="<p>Body</p>")
        )
