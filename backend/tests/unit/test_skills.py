"""Skill-name suggestions: the bundled lists and the search over them."""

from __future__ import annotations

import re

from app.services.skills import MAX_LIMIT, load_skills, suggest_skills


def test_the_lists_load_without_blanks_comments_or_duplicates() -> None:
    names = load_skills()

    assert len(names) > 500
    assert all(name == " ".join(name.split()) and not name.startswith("#") for name in names)
    assert len({name.casefold() for name in names}) == len(names)


def test_a_prefix_matches_whatever_the_case_or_spacing() -> None:
    assert suggest_skills("pyth")[0] == "Python"
    assert suggest_skills("  PYTH ")[0] == "Python"


def test_a_name_that_is_in_both_lists_appears_once() -> None:
    assert suggest_skills("python", limit=MAX_LIMIT).count("Python") == 1


def test_whole_name_prefixes_come_first() -> None:
    results = suggest_skills("sql", limit=MAX_LIMIT)

    assert results[0] == "SQL"
    assert "Microsoft SQL Server" in results


def test_the_middle_of_a_word_matches_only_from_three_characters() -> None:
    assert "JavaScript" in suggest_skills("avascr")
    assert "JavaScript" not in suggest_skills("av", limit=MAX_LIMIT)


def test_a_match_on_a_later_word_is_found() -> None:
    assert "Microsoft Excel" in suggest_skills("exc")


def test_short_queries_match_the_start_of_a_word_only() -> None:
    results = suggest_skills("ex", limit=MAX_LIMIT)

    assert results
    assert all(
        any(token.startswith("ex") for token in re.findall(r"[a-z0-9+#.]+", name.casefold()))
        for name in results
    )


def test_blank_and_unknown_queries_find_nothing() -> None:
    assert suggest_skills("") == []
    assert suggest_skills("   ") == []
    assert suggest_skills("zzzzqqqq") == []


def test_the_limit_is_respected_and_capped() -> None:
    assert len(suggest_skills("a", limit=3)) == 3
    assert len(suggest_skills("a", limit=10_000)) == MAX_LIMIT
    assert len(suggest_skills("a", limit=0)) == 1
