from __future__ import annotations

import re

import pytest
from pydantic import SecretStr

from app.core.security import (
    constant_time_equals,
    generate_numeric_code,
    generate_token,
    hash_token,
    keyed_hash,
    mask_email,
)

SECRET = SecretStr("unit-test-secret-key-with-at-least-32-chars")


def test_generate_token_is_random_and_url_safe() -> None:
    tokens = {generate_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", token) for token in tokens)


def test_constant_time_equals() -> None:
    assert constant_time_equals("123456", "123456")
    assert not constant_time_equals("123456", "123457")
    assert not constant_time_equals("123456", "12345")


def test_numeric_codes_are_six_zero_padded_digits() -> None:
    codes = {generate_numeric_code() for _ in range(200)}

    assert all(re.fullmatch(r"\d{6}", code) for code in codes)
    assert len(codes) > 190


def test_keyed_hash_depends_on_purpose_secret_and_value() -> None:
    digest = keyed_hash(SECRET, "otp", "a@example.com:123456")

    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == keyed_hash(SECRET, "otp", "a@example.com:123456")
    assert digest != keyed_hash(SECRET, "csrf", "a@example.com:123456")
    assert digest != keyed_hash(SecretStr("x" * 40), "otp", "a@example.com:123456")
    assert digest != keyed_hash(SECRET, "otp", "a@example.com:123457")


def test_hash_token_is_sha256_hex() -> None:
    assert hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.mark.parametrize(
    ("email", "masked"),
    [("ananya@example.com", "a***@example.com"), ("x@y.in", "x***@y.in"), ("broken", "***")],
)
def test_mask_email_keeps_only_first_letter_and_domain(email: str, masked: str) -> None:
    assert mask_email(email) == masked
