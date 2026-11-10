.PHONY: all up down test test-backend test-frontend test-ai-sdlc lint openapi seed hygiene ai-sdlc

all: lint test

up:
	docker compose up --build -d

down:
	docker compose down

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

test-ai-sdlc:
	cd tools/ai-sdlc && uv run pytest -v

ai-sdlc:
	cd tools/ai-sdlc && uv run uvicorn sdlc_app.main:app --host 127.0.0.1 --port 8090 --reload

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run typecheck

openapi:
	cd frontend && npm run gen:api

seed:
	cd backend && uv run python -m app.seed

hygiene:
	python scripts/check_repo_hygiene.py
