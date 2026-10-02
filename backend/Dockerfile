# syntax=docker/dockerfile:1.7
#
# Targets:
#   dev      - all dependencies (incl. test/lint tools), code bind-mounted, hot reload
#   runtime  - production image: runtime dependencies only, non-root, no build tools
#
# The same runtime image runs the API, the job worker and the one-shot migration job;
# only the command differs (see docker-compose*.yml).

ARG PYTHON_VERSION=3.12

FROM ghcr.io/astral-sh/uv:0.12.22 AS uv

# ---------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /home/app --create-home app

WORKDIR /app

# ---------------------------------------------------------------------------------------
FROM base AS builder

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Dependencies first, in their own layer, so code changes do not reinstall them.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# ---------------------------------------------------------------------------------------
FROM builder AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

# Keep tool caches out of the bind-mounted source tree.
ENV MYPY_CACHE_DIR=/tmp/.mypy_cache \
    RUFF_CACHE_DIR=/tmp/.ruff_cache \
    COVERAGE_FILE=/tmp/.coverage \
    PYTEST_ADDOPTS="-p no:cacheprovider"

COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--no-access-log"]

# ---------------------------------------------------------------------------------------
FROM base AS runtime

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

COPY --from=builder /opt/venv /opt/venv
COPY --chown=root:root alembic.ini ./
COPY --chown=root:root migrations ./migrations
COPY --chown=root:root app ./app

# The embedding model (bge-small-en-v1.5, about 67 MB; ADR 0007) is baked into the image so
# nothing is downloaded at runtime. Files are root-owned and read-only to the process user.
ENV EMBEDDING_CACHE_DIR=/opt/models     HF_HUB_OFFLINE=1
RUN HF_HUB_OFFLINE=0 python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/models')"     && chmod -R a+rX /opt/models

# Source is owned by root and read-only to the process user.
USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health' % os.environ.get('PORT', '8000'), timeout=4)"]

# Listens on $PORT when the host sets one (Render does), else 8000. Scale with replicas or
# WEB_CONCURRENCY. Trusted proxy IPs come from FORWARDED_ALLOW_IPS.
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port \"${PORT:-8000}\" --no-access-log"]
