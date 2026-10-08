"""Signup and access (A5): how domains and invite codes are cleaned up before matching."""

from __future__ import annotations

import pytest

from app.services.signup import (
    generate_invite_code,
    normalise_domain,
    normalise_invite_code,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.edu", "example.edu"),
        (" @Example.EDU ", "example.edu"),
        ("mail.thapar.edu", "mail.thapar.edu"),
        ("xn--bcher-kva.example", "xn--bcher-kva.example"),
        ("localhost", None),
        ("not a domain", None),
        ("-bad.example", None),
        ("bad-.example", None),
        ("a..example", None),
        ("user@example.com", None),
        ("", None),
    ],
)
def test_domains_are_lower_case_without_the_at_sign(raw: str, expected: str | None) -> None:
    assert normalise_domain(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cyn-friends", "CYN-FRIENDS"),
        ("  CYN-BETA1 ", "CYN-BETA1"),
        ("abc", None),
        ("has space", None),
        ("x" * 33, None),
        ("", None),
        (None, None),
    ],
)
def test_invite_codes_are_upper_case_letters_digits_and_hyphens(
    raw: str | None, expected: str | None
) -> None:
    assert normalise_invite_code(raw) == expected


def test_generated_codes_are_valid_and_avoid_look_alike_characters() -> None:
    codes = {generate_invite_code() for _ in range(200)}
    assert len(codes) == 200
    for code in codes:
        assert normalise_invite_code(code) == code
        assert not set(code.removeprefix("CYN-")) & set("01OIL")
