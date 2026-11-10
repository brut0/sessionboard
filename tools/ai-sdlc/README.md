# SessionBoard Companion AI SDLC Web Workbench

Standalone developer tooling running alongside SessionBoard (`http://localhost:8090`).
Excluded from SessionBoard's runtime container (`.dockerignore`) and API contract (`specs/api/openapi.yaml`).

## Quick Start

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

## LLM API Configuration

Click **API Settings** in the top bar or configure environment variables before launching:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` (Google AI Studio REST) or `openai` (OpenAI / OpenRouter / Ollama) |
| `LLM_MODEL` | `gemini-2.5-flash` | Model ID (`gemini-2.5-flash`, `gpt-4o-mini`, `qwen2.5-coder`, etc.) |
| `GEMINI_API_KEY` | empty | API key sent via `x-goog-api-key` header |
| `OPENAI_API_KEY` | empty | Bearer token for OpenAI-compatible `/chat/completions` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for local Ollama (`http://localhost:11434/v1`) or OpenRouter |

Keys saved through the Web UI live exclusively inside git-ignored `.local/ai-sdlc/config.json` and run snapshots live inside `.local/ai-sdlc/runs/`.

## Tests

```bash
cd tools/ai-sdlc
uv run ruff check . && uv run ruff format --check .
uv run pytest -v
```
