# SessionBoard Companion AI SDLC Web Workbench

Standalone developer tooling running alongside SessionBoard (`http://127.0.0.1:8090`).
Excluded from SessionBoard's core runtime container (`.dockerignore`) and API contract (`specs/api/openapi.yaml`).

## Quick Start

### 1. Local Python Dev Server

```bash
cd tools/ai-sdlc
uv sync
uv run uvicorn sdlc_app.main:app --host 127.0.0.1 --port 8090 --reload
```

Or from the repository root:

```bash
make ai-sdlc
```

Then open **http://127.0.0.1:8090** in your browser.

### 2. Full-Suite Docker Compose (`--profile sdlc`)

Start PostgreSQL 16, SessionBoard (`:8000`), Grafana OTel-LGTM (`:3000`), and `ai-sdlc` (`127.0.0.1:8090`) together:

```bash
docker compose --profile sdlc up --build
```

### 3. Container Build (`tools/ai-sdlc/Dockerfile`)

```bash
docker build -f tools/ai-sdlc/Dockerfile -t sessionboard-ai-sdlc:local tools/ai-sdlc
```

## Owner-Only Security & Cloud Configuration

Inside Docker (`SDLC_REQUIRE_AUTH=true`, `APP_ENV=prod`) or any non-local environment (`RENDER=true`, `APP_ENV!=local`), owner authentication is **enforced and fail-closed**:

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `local` | Non-`local` automatically enforces owner auth |
| `SDLC_REQUIRE_AUTH` | `false` (`true` in Dockerfile) | Require owner session cookie or Bearer token across `/api/*` & `/docs` |
| `SDLC_OWNER_PASSWORD` | empty | Owner passphrase (min 12 chars required when auth active, else `503`) |
| `SDLC_SESSION_SECRET` | empty | HMAC-SHA256 cookie signing secret (derived safely if omitted) |
| `SDLC_SESSION_TTL_SECONDS` | `43200` | Signed `HttpOnly; SameSite=Lax` cookie lifetime (12h) |
| `SDLC_CLONE_REPO_URL` | empty | Token-free HTTPS git URL cloned ephemerally into `SDLC_REPO_ROOT` on boot |
| `SDLC_STATE_DIR` | `<repo>/.local/ai-sdlc` | Override state/runs storage directory (e.g. `/app/state` in cloud containers) |
| `SDLC_NON_INTERACTIVE` | `false` (`true` in Dockerfile) | Forces `--no-gpg-sign` and `GIT_TERMINAL_PROMPT=0` for headless commits |
| `LLM_PROVIDER` | `gemini` | `gemini` (Google AI Studio REST) or `openai` (OpenAI / OpenRouter / Ollama) |
| `LLM_MODEL` | `gemini-2.5-flash` | Model ID (`gemini-2.5-flash`, `gpt-4o-mini`, `qwen2.5-coder`, etc.) |
| `GEMINI_API_KEY` | empty | API key sent via `x-goog-api-key` header |
| `OPENAI_API_KEY` | empty | Bearer token for OpenAI-compatible `/chat/completions` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for local Ollama (`http://localhost:11434/v1`) or OpenRouter |

Keys saved through the Web UI live exclusively inside `SDLC_STATE_DIR/config.json` (default git-ignored `.local/ai-sdlc/config.json`), and auth secrets are never written to disk.

## Tests

```bash
cd tools/ai-sdlc
uv run ruff check . && uv run ruff format --check .
uv run pytest -v
```
