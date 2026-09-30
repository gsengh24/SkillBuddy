from __future__ import annotations

import re

from app.core.security import constant_time_equals, generate_token


def test_generate_token_is_random_and_url_safe() -> None:
    tokens = {generate_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", token) for token in tokens)


def test_constant_time_equals() -> None:
    assert constant_time_equals("123456", "123456")
    assert not constant_time_equals("123456", "123457")
    assert not constant_time_equals("123456", "12345")
