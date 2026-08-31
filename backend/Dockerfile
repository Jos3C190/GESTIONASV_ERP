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
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

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
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------- prod ----------------
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

CMD ["uv", "run", "arq", "app.infrastructure.ocr_worker.WorkerSettings"]
