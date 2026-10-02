"""Text embeddings (ADR 0007): BAAI/bge-small-en-v1.5, 384 dimensions, run locally.

The model runs with fastembed (ONNX Runtime) inside the process that runs jobs: the API
process on free hosting (ADR 0008). No text leaves the server to be embedded. The model is
loaded lazily on first use, kept for the life of the process, and limited to one ONNX
thread and small batches so it fits a 512 MB host (the CI memory check enforces 400 MB).

Tests and CI use ``FakeEmbedder``, which needs no model download.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import threading
import time
from collections.abc import Sequence
from functools import cache
from typing import Any, Final, Literal, Protocol

from app.core.config import Settings
from app.models.profile_embedding import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

EmbedKind = Literal["query", "passage"]

BGE_SMALL: Final = "BAAI/bge-small-en-v1.5"
# bge's instruction for queries (retrieval side); documents are embedded without it.
BGE_QUERY_PREFIX: Final = "Represent this sentence for searching relevant passages: "
# About 256 tokens of English; longer text is cut before embedding.
MAX_EMBED_CHARS: Final = 1200


class Embedder(Protocol):
    @property
    def model_version(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed(self, texts: Sequence[str], *, kind: EmbedKind) -> list[list[float]]:
        """One unit-length vector per text, in order."""
        ...


def _prepare(texts: Sequence[str], kind: EmbedKind) -> list[str]:
    prefix = BGE_QUERY_PREFIX if kind == "query" else ""
    return [prefix + " ".join(text.split())[:MAX_EMBED_CHARS] for text in texts]


class FastEmbedEmbedder:
    """bge-small-en-v1.5 through fastembed. Thread-safe; one model per process."""

    def __init__(
        self, model_name: str, *, cache_dir: str | None, threads: int, batch_size: int
    ) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._threads = threads
        self._batch_size = batch_size
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def model_version(self) -> str:
        return f"{self._model_name}@fastembed-onnx"

    @property
    def dimensions(self) -> int:
        return EMBEDDING_DIMENSIONS

    def load(self) -> Any:
        """Load the model now (otherwise it loads on first use)."""
        with self._lock:
            if self._model is None:
                # Imported here so processes that never embed (and tests) skip ONNX Runtime.
                from fastembed import TextEmbedding

                started = time.monotonic()
                self._model = TextEmbedding(
                    model_name=self._model_name,
                    cache_dir=self._cache_dir,
                    threads=self._threads,
                )
                logger.info(
                    "embedding_model_loaded",
                    extra={
                        "model": self._model_name,
                        "seconds": round(time.monotonic() - started, 2),
                    },
                )
            return self._model

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        model = self.load()
        vectors = model.embed(texts, batch_size=self._batch_size)
        return [[float(value) for value in vector] for vector in vectors]

    async def embed(self, texts: Sequence[str], *, kind: EmbedKind) -> list[list[float]]:
        if not texts:
            return []
        # CPU-bound: keep it off the event loop so the API keeps answering requests.
        return await asyncio.to_thread(self._embed_sync, _prepare(texts, kind))


class FakeEmbedder:
    """Deterministic stand-in for tests: same text, same unit vector. No model, no network."""

    model_version: Final = "fake-embedder@1"
    dimensions: Final = EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str], *, kind: EmbedKind) -> list[list[float]]:
        return [self._vector(text) for text in _prepare(texts, kind)]

    @staticmethod
    def _vector(text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < EMBEDDING_DIMENSIONS:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend((byte - 127.5) / 127.5 for byte in digest)
            counter += 1
        values = values[:EMBEDDING_DIMENSIONS]
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values]


@cache
def _fastembed(model: str, cache_dir: str | None, threads: int, batch_size: int) -> Embedder:
    return FastEmbedEmbedder(model, cache_dir=cache_dir, threads=threads, batch_size=batch_size)


def get_embedder(settings: Settings) -> Embedder:
    """The process-wide embedder for these settings (the model loads once per process)."""
    if settings.embedding_backend == "fake":
        return FakeEmbedder()
    return _fastembed(
        settings.embedding_model,
        settings.embedding_cache_dir,
        settings.embedding_threads,
        settings.embedding_batch_size,
    )
