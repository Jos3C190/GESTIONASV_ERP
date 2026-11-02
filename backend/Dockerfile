# syntax=docker/dockerfile:1.7
# Backend image — multi-stage. dev = hot reload + tools, prod = slim + non-root.

ARG PYTHON_VERSION=3.12

# ---------------- base ----------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast resolver/runner)
ADD --chmod=755 https://astral.sh/uv/install.sh /tmp/uv-install.sh
RUN /tmp/uv-install.sh && rm /tmp/uv-install.sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    mv /root/.local/bin/uvx /usr/local/bin/uvx

# ---------------- dev ----------------
FROM base AS dev
COPY pyproject.toml uv.lock ./
# Sync dependencies (no project code yet) so the layer is cached
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen
EXPOSE 8000
# Keep the development watcher scoped to application code. Running Uvicorn
# through `uv run` on every reload can update `/app/.venv`, which is inside the
# bind mount and causes watchfiles to reload the server continuously.
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]

# ---------------- OCR worker ----------------
FROM base AS ocr

RUN apt-get update && apt-get install -y --no-install-recommends \
        ghostscript \
        libmagic1 \
        pngquant \
        qpdf \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-osd \
        tesseract-ocr-spa \
        unpaper \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra ocr
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra ocr

RUN groupadd --system --gid 1001 erp && \
    useradd --system --uid 1001 --gid erp --home-dir /app --shell /usr/sbin/nologin erp && \
    chown -R erp:erp /app
USER erp

# The OCR image already contains its frozen environment in /opt/venv.
# Running through uv run at container startup makes uv revalidate the bind-mounted
# project and rewrite the editable-install metadata, which is not writable by
# the non-root worker user in CI. Invoke the installed worker directly.
CMD ["/opt/venv/bin/arq", "app.infrastructure.ocr_worker.WorkerSettings"]

# ---------------- Vision model worker ----------------
# Starts from the official llama.cpp build for CUDA 12, pinned by digest: its
# libraries need that image's Ubuntu glibc. The CUDA 13 variant asks for a newer
# driver than the RTX 4060 host runs. The engine stays in /app, so the project
# lives in /srv/erp. Model weights are mounted read-only, never baked in.
FROM ghcr.io/ggml-org/llama.cpp@sha256:0a9f6c7cfe5a6b90b6c048b7a86865bf55a88af34bada927482eab2ef5f25b4a AS vlm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON=/usr/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

COPY --from=base /usr/local/bin/uv /usr/local/bin/uv
WORKDIR /srv/erp
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra vlm
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra vlm

RUN groupadd --system --gid 1001 erp && \
    useradd --system --uid 1001 --gid erp --home-dir /srv/erp --shell /usr/sbin/nologin erp && \
    chown -R erp:erp /srv/erp
USER erp

# The engine only finds its libraries from /app, and the worker runs from /srv/erp.
ENV LD_LIBRARY_PATH=/app:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64
ENTRYPOINT []
HEALTHCHECK NONE
CMD ["/opt/venv/bin/arq", "app.infrastructure.vlm.worker.WorkerSettings"]

# ---------------- prod (default/Render target) ----------------
# Keep this stage last: Render builds the Dockerfile without an explicit target.
FROM base AS prod
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# Non-root user
RUN groupadd --system --gid 1001 erp && \
    useradd --system --uid 1001 --gid erp --home-dir /app --shell /usr/sbin/nologin erp && \
    chown -R erp:erp /app
USER erp

EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${BACKEND_WORKERS:-1}"]
