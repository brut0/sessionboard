#!/usr/bin/env sh
set -e

# Run database migrations if alembic.ini is present
if [ -f "alembic.ini" ]; then
    echo "Running database migrations..."
    uv run alembic upgrade head || true
fi

# Run seed script if enabled
if [ "$SEED_DEMO_DATA" = "true" ]; then
    echo "Seeding demo data..."
    uv run python -m app.seed || true
fi

PORT="${PORT:-8000}"
echo "Starting SessionBoard on port $PORT..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
