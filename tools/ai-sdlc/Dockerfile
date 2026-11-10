# Companion AI SDLC Web Workbench runtime image (decoupled from SessionBoard core)
FROM python:3.12-slim AS runtime

WORKDIR /app/workbench

# Install uv binary for deterministic dependency sync
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install git, curl, TLS roots, and official GitHub CLI (gh)
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates && \
    mkdir -p -m 755 /usr/share/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/*

# Sync runtime dependencies from lockfile
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Copy workbench source & static UI
COPY sdlc_app ./sdlc_app
COPY static ./static

# Safe system-level git defaults for mounted volumes and headless commits
RUN git config --system commit.gpgsign false && \
    git config --system safe.directory "*"

# Run unprivileged with fail-closed auth defaults
RUN useradd --create-home --shell /bin/bash sdlc && \
    mkdir -p /app/workspace /app/state && \
    chown -R sdlc:sdlc /app/workbench /app/workspace /app/state

ARG GIT_SHA=local
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/workbench/.venv/bin:$PATH" \
    SDLC_APP_VERSION=$GIT_SHA \
    APP_ENV=prod \
    SDLC_REQUIRE_AUTH=true \
    SDLC_NON_INTERACTIVE=true \
    SDLC_REPO_ROOT=/app/workspace/sessionboard \
    SDLC_STATE_DIR=/app/state \
    PORT=8090

USER sdlc

EXPOSE 8090

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-8090}/api/health" || exit 1'

CMD ["sh", "-c", "exec uvicorn sdlc_app.main:app --host 0.0.0.0 --port ${PORT:-8090}"]
