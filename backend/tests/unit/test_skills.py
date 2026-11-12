"""Skill-name suggestions: the bundled lists and the search over them."""

from __future__ import annotations

import re

from app.ai.stages import Understanding, understand_template
from app.services.profile_parsing import vet_template_skills
from app.services.skills import MAX_LIMIT, known_skills_in, load_skills, suggest_skills


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


def test_known_skills_are_picked_out_of_loose_phrases_in_the_lists_spelling() -> None:
    phrases = ["lot of reading in my free time", "machine learning with pytorch", "node.js"]
    assert known_skills_in(phrases, 8) == ["Reading", "Machine learning", "PyTorch", "Node.js"]


def test_phrases_naming_no_skill_give_nothing() -> None:
    phrases = ["find people for a hackathon", "I need someone who is good at stuff"]
    assert known_skills_in(phrases, 8) == []


def test_everyday_words_count_only_when_written_as_the_name() -> None:
    assert known_skills_in(["Go", "Swift"], 8) == ["Go", "Swift"]
    assert known_skills_in(["a go-getter who will zoom ahead", "swift replies"], 8) == []


def test_known_skills_are_listed_once_and_capped() -> None:
    assert known_skills_in(["Python", "python and Python"], 8) == ["Python"]
    assert len(known_skills_in(["Python, React, SQL, Figma, Chess, Guitar"], 3)) == 3


def test_a_reading_without_ai_keeps_only_skill_names_in_the_skill_columns() -> None:
    reading = understand_template(
        "I know Python and some React. I want to find people for a hackathon and I need "
        "someone who is good at design. I do a lot of reading. I would like to learn guitar "
        "or maybe chess. I enjoy long walks."
    )
    vetted = vet_template_skills(reading)
    assert vetted.offers == ["Python", "React", "Reading"]
    assert vetted.seeks == ["Guitar", "Chess"]
    # Interests and the rest are left as the template read them.
    assert vetted.interests == reading.interests
    assert vetted.summary == reading.summary


def test_vetting_an_empty_reading_changes_nothing() -> None:
    assert vet_template_skills(Understanding()) == Understanding()
