"""Embedders, facet text and embedding settings (no model, no database)."""

from __future__ import annotations

import math
import sys
import types
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

from app.ai import embeddings as embeddings_module
from app.ai.embeddings import (
    BGE_QUERY_PREFIX,
    MAX_EMBED_CHARS,
    FakeEmbedder,
    FastEmbedEmbedder,
    get_embedder,
)
from app.core.config import Environment
from app.jobs.registry import JobGroup
from app.jobs.tasks import EMBED_PROFILE, REEMBED_PROFILES, build_registry
from app.jobs.worker import build_registry as build_worker_registry
from app.models import EMBEDDING_DIMENSIONS, EmbeddingFacet
from app.services.embeddings import FACET_SOURCES, facet_texts
from tests.conftest import SettingsFactory


def test_dimension_is_384() -> None:
    assert EMBEDDING_DIMENSIONS == 384


# --- FakeEmbedder ---------------------------------------------------------------------


async def test_fake_embedder_is_deterministic_unit_length_and_384_d() -> None:
    embedder = FakeEmbedder()
    first, again, other = await embedder.embed(["chess", "chess", "guitar"], kind="passage")

    assert len(first) == 384
    assert first == again
    assert first != other
    assert math.isclose(math.fsum(value * value for value in first), 1.0, rel_tol=1e-9)


async def test_queries_get_bge_instruction_and_text_is_capped() -> None:
    embedder = FakeEmbedder()
    query, passage = (
        await embedder.embed(["chess"], kind="query"),
        await embedder.embed(["chess"], kind="passage"),
    )
    long_a, long_b = await embedder.embed(
        ["x" * MAX_EMBED_CHARS + "a", "x" * MAX_EMBED_CHARS + "b"], kind="passage"
    )

    assert query != passage
    assert long_a == long_b  # anything past the cap is ignored


# --- FastEmbedEmbedder (with a stand-in fastembed module) ------------------------------


class _FakeTextEmbedding:
    instances: ClassVar[list[_FakeTextEmbedding]] = []

    def __init__(self, *, model_name: str, cache_dir: str | None, threads: int) -> None:
        self.model_name, self.cache_dir, self.threads = model_name, cache_dir, threads
        self.calls: list[tuple[list[str], int]] = []
        _FakeTextEmbedding.instances.append(self)

    def embed(self, texts: list[str], batch_size: int) -> Iterator[list[float]]:
        self.calls.append((texts, batch_size))
        return iter([[0.5] * EMBEDDING_DIMENSIONS for _ in texts])


@pytest.fixture
def fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> type[_FakeTextEmbedding]:
    module: Any = types.ModuleType("fastembed")
    module.TextEmbedding = _FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)
    _FakeTextEmbedding.instances.clear()
    return _FakeTextEmbedding


async def test_fastembed_loads_once_with_one_thread_and_small_batches(
    fake_fastembed: type[_FakeTextEmbedding],
) -> None:
    embedder = FastEmbedEmbedder(
        "BAAI/bge-small-en-v1.5", cache_dir="/opt/models", threads=1, batch_size=8
    )
    assert fake_fastembed.instances == []  # lazy: nothing loaded yet

    vectors = await embedder.embed(["one", "two"], kind="passage")
    await embedder.embed(["three"], kind="query")

    assert len(fake_fastembed.instances) == 1
    model = fake_fastembed.instances[0]
    assert (model.model_name, model.cache_dir, model.threads) == (
        "BAAI/bge-small-en-v1.5",
        "/opt/models",
        1,
    )
    assert model.calls == [(["one", "two"], 8), ([BGE_QUERY_PREFIX + "three"], 8)]
    assert [len(vector) for vector in vectors] == [384, 384]
    assert embedder.model_version == "BAAI/bge-small-en-v1.5@fastembed-onnx"
    assert await embedder.embed([], kind="passage") == []


def test_get_embedder_reuses_one_model_per_process(make_settings: SettingsFactory) -> None:
    embeddings_module._fastembed.cache_clear()
    real = make_settings(embedding_backend="fastembed")

    assert isinstance(get_embedder(make_settings(embedding_backend="fake")), FakeEmbedder)
    assert isinstance(get_embedder(real), FastEmbedEmbedder)
    assert get_embedder(real) is get_embedder(real)


# --- facets ---------------------------------------------------------------------------


def test_four_facets() -> None:
    assert set(FACET_SOURCES) == set(EmbeddingFacet)
    assert {facet.value for facet in EmbeddingFacet} == {"identity", "offer", "seek", "interest"}


def test_unparsed_profile_uses_its_own_words_for_every_facet() -> None:
    texts = facet_texts("  I build   backends in Python. ", {})

    assert texts == dict.fromkeys(EmbeddingFacet, "I build backends in Python.")


def test_parsed_fields_feed_their_facets() -> None:
    texts = facet_texts(
        "Raw words.",
        {
            "summary": "Backend developer",
            "offers": ["Python", "APIs"],
            "seeks": "a designer",
            "interests": [],
        },
    )

    assert texts == {
        EmbeddingFacet.IDENTITY: "Backend developer",
        EmbeddingFacet.OFFER: "Python, APIs",
        EmbeddingFacet.SEEK: "a designer",
        EmbeddingFacet.INTEREST: "Raw words.",  # empty list: falls back
    }


def test_parsed_only_profile_still_gets_four_facets_and_empty_gets_none() -> None:
    texts = facet_texts("", {"offers": ["Figma"]})

    assert texts[EmbeddingFacet.OFFER] == "Figma"
    assert set(texts) == set(EmbeddingFacet)
    assert facet_texts("   ", {"other": "ignored", "offers": []}) == {}


# --- settings and jobs ----------------------------------------------------------------


def test_embedding_settings(make_settings: SettingsFactory) -> None:
    settings = make_settings(embedding_backend="fastembed")
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_dimensions == 384
    assert (settings.embedding_threads, settings.embedding_batch_size) == (1, 2)

    with pytest.raises(ValidationError, match="EMBEDDING_DIMENSIONS must be 384"):
        make_settings(embedding_dimensions=768)


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_fake_embeddings_are_refused_when_deployed(
    make_settings: SettingsFactory, environment: Environment
) -> None:
    with pytest.raises(ValidationError, match="EMBEDDING_BACKEND=fake"):
        make_settings(
            environment=environment,
            embedding_backend="fake",
            email_backend="smtp",
            cors_allow_origins=["https://app.example.com"],
        )


def test_embedding_jobs_are_ai_jobs_run_by_either_process() -> None:
    for spec in (EMBED_PROFILE, REEMBED_PROFILES):
        assert spec.group is JobGroup.AI  # one at a time: protects the 512 MB host
        assert spec.needs_secret is False
        assert spec.kind in build_registry().kinds()
        assert spec.kind in build_worker_registry().kinds()
