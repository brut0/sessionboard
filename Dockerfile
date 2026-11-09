# Stage 1: Build React 19 Frontend SPA
FROM node:22-alpine AS frontend-builder
WORKDIR /build

COPY specs /build/specs
COPY frontend/package.json frontend/package-lock.json* /build/frontend/
WORKDIR /build/frontend
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ /build/frontend/
RUN npm run gen:api && npm run build

# Stage 2: Python 3.12 Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install uv from official binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/pyproject.toml backend/uv.lock* /app/backend/
WORKDIR /app/backend
RUN if [ -f uv.lock ]; then uv sync --frozen --no-dev; else uv sync --no-dev; fi

# Copy backend application and database migrations
COPY backend/ /app/backend/

# Copy compiled frontend assets into FastAPI static directory
COPY --from=frontend-builder /build/frontend/dist /app/backend/app/static

ARG GIT_SHA=unknown
ENV APP_VERSION=$GIT_SHA \
    PYTHONUNBUFFERED=1 \
    PATH="/app/backend/.venv/bin:$PATH"

RUN chmod +x /app/backend/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
