"""CI memory check (ADR 0007, ADR 0008 decision 4): API + embedding model under 400 MB.

Run inside the production image: ``python -m app.ai.memory_check --limit-mb 400``.

It builds the API application (every module the API process imports), loads the real
bge-small-en-v1.5 model, embeds a realistic workload (8 profiles x 4 facets in batches,
plus queries), then reads the process's peak resident memory. Exit status 1 if the peak is
over the limit. Needs no database or network: the model is baked into the image.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import sys
import time
from collections.abc import Sequence

from app.ai.embeddings import FastEmbedEmbedder
from app.core.config import get_settings
from app.jobs.tasks import build_registry
from app.main import create_app

SAMPLE_PROFILE = (
    "Second-year computer science student. I build web backends in Python and FastAPI, "
    "and I am learning product design. Looking for someone who can design interfaces for a "
    "campus lost-and-found app. I like chess, hiking on weekends and civic tech. "
) * 4


def peak_rss_mb() -> float:
    # Linux reports ru_maxrss in kilobytes.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def _workload(embedder: FastEmbedEmbedder) -> tuple[int, float]:
    started = time.monotonic()
    texts = [f"{SAMPLE_PROFILE} Profile {n}." for n in range(32)]  # 8 profiles x 4 facets
    vectors = await embedder.embed(texts, kind="passage")
    vectors += await embedder.embed(["designer for a campus app"] * 4, kind="query")
    return len(vectors[0]), time.monotonic() - started


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-mb", type=float, default=400.0)
    args = parser.parse_args(argv)

    settings = get_settings()
    create_app(settings)  # import and build everything the API process holds
    build_registry()
    baseline = peak_rss_mb()

    embedder = FastEmbedEmbedder(
        settings.embedding_model,
        cache_dir=settings.embedding_cache_dir,
        threads=settings.embedding_threads,
        batch_size=settings.embedding_batch_size,
    )
    load_started = time.monotonic()
    embedder.load()
    load_seconds = time.monotonic() - load_started
    dimensions, embed_seconds = asyncio.run(_workload(embedder))

    peak = peak_rss_mb()
    report = {
        "app_baseline_mb": round(baseline, 1),
        "peak_rss_mb": round(peak, 1),
        "limit_mb": args.limit_mb,
        "model_load_seconds": round(load_seconds, 2),
        "embed_36_texts_seconds": round(embed_seconds, 2),
        "dimensions": dimensions,
        "threads": settings.embedding_threads,
        "batch_size": settings.embedding_batch_size,
    }
    sys.stdout.write(json.dumps(report) + "\n")
    if dimensions != settings.embedding_dimensions:
        sys.stderr.write(f"expected {settings.embedding_dimensions}-d vectors\n")
        return 1
    if peak > args.limit_mb:
        sys.stderr.write(f"peak RSS {peak:.1f} MB is over the {args.limit_mb:g} MB limit\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
