# syntax=docker/dockerfile:1
# Standalone Linux container for pdf2study.
# Includes Python 3.12, Node.js + Marp CLI, Chromium (PDF render), fonts, and OCR.
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    CHROME_PATH=/usr/bin/chromium \
    CHROME_NO_SANDBOX=1 \
    PATH="/app/.venv/bin:/usr/local/bin:${PATH}"

# System deps: Node/npm (Marp), Chromium (Marp --pdf), fonts, and OCR toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git \
        nodejs npm \
        chromium \
        fonts-dejavu-core fonts-liberation fonts-noto-color-emoji \
        tesseract-ocr ghostscript qpdf pngquant \
    && rm -rf /var/lib/apt/lists/*

# Install Marp CLI globally (so no npx download at runtime).
RUN npm install -g @marp-team/marp-cli && npm cache clean --force

# Install uv (static binary).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY pdf2study ./pdf2study

# Reproducible install from the lockfile, including optional OCR support.
RUN uv sync --frozen --extra ocr

# Run as a non-root user (override with `--user $(id -u):$(id -g)` if needed).
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /work \
    && chown -R app:app /app /work

USER app
ENV HOME=/home/app

WORKDIR /work
ENTRYPOINT ["pdf2study"]
CMD ["--help"]
