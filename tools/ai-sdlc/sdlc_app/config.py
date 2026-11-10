"""Configuration management for the SessionBoard AI SDLC Workbench."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def detect_repo_root(start: Path | None = None) -> Path:
    """Locate the SessionBoard repository root by looking for AGENTS.md or .git."""
    env_root = os.environ.get("SDLC_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    cursor = (start or Path(__file__)).resolve()
    for parent in [cursor, *cursor.parents]:
        if (parent / "AGENTS.md").is_file() and (parent / "specs").is_dir():
            return parent
    # Fallback three levels above sdlc_app/ (tools/ai-sdlc -> repo root)
    return Path(__file__).resolve().parents[3]


class WorkbenchSettings(BaseSettings):
    """Runtime settings sourced from environment or git-ignored .local config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    repo_root: Path = Field(default_factory=detect_repo_root, alias="SDLC_REPO_ROOT")
    app_version: str = Field(default="local", alias="SDLC_APP_VERSION")
    app_env: str = Field(default="local", alias="APP_ENV")
    render_env: str = Field(default="", alias="RENDER")
    require_auth: bool = Field(default=False, alias="SDLC_REQUIRE_AUTH")
    owner_password: str = Field(default="", alias="SDLC_OWNER_PASSWORD")
    session_secret: str = Field(default="", alias="SDLC_SESSION_SECRET")
    session_ttl_seconds: int = Field(default=43200, alias="SDLC_SESSION_TTL_SECONDS")
    clone_repo_url: str = Field(default="", alias="SDLC_CLONE_REPO_URL")
    state_dir_override: Path | None = Field(default=None, alias="SDLC_STATE_DIR")
    non_interactive: bool = Field(default=False, alias="SDLC_NON_INTERACTIVE")

    llm_provider: Literal["gemini", "openai"] = Field(default="gemini", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-2.5-flash", alias="LLM_MODEL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="OPENAI_BASE_URL",
    )

    @property
    def auth_required(self) -> bool:
        """Fail closed whenever auth is requested, password set, or deployed non-locally."""
        if self.require_auth:
            return True
        if self.owner_password.strip():
            return True
        if self.app_env.strip().lower() != "local":
            return True
        return self.render_env.strip().lower() in {"1", "true", "yes"}

    @property
    def auth_configured(self) -> bool:
        """Require at least a 12-character non-blank owner passphrase when auth is active."""
        if not self.auth_required:
            return True
        return len(self.owner_password) >= 12 and bool(self.owner_password.strip())

    @property
    def state_dir(self) -> Path:
        if self.state_dir_override is not None:
            return self.state_dir_override.resolve()
        return self.repo_root / ".local" / "ai-sdlc"

    @property
    def runs_dir(self) -> Path:
        return self.state_dir / "runs"

    @property
    def runtime_config_file(self) -> Path:
        return self.state_dir / "config.json"

    def effective_api_key(self) -> str:
        return self.gemini_api_key if self.llm_provider == "gemini" else self.openai_api_key

    def load_persisted_overrides(self) -> WorkbenchSettings:
        """Apply git-ignored LLM runtime overrides saved from the Web UI if present."""
        cfg_file = self.runtime_config_file
        if not cfg_file.is_file():
            return self
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self

        updates: dict[str, object] = {}
        for field_name in (
            "llm_provider",
            "llm_model",
            "gemini_api_key",
            "openai_api_key",
            "openai_base_url",
        ):
            val = data.get(field_name)
            if isinstance(val, str) and val.strip():
                updates[field_name] = val.strip()
        return self.model_copy(update=updates)

    def save_persisted_overrides(self) -> None:
        """Save UI-updated LLM config only (never persisting auth credentials to disk)."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "gemini_api_key": self.gemini_api_key,
            "openai_api_key": self.openai_api_key,
            "openai_base_url": self.openai_base_url,
        }
        self.runtime_config_file.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )


@lru_cache
def get_settings() -> WorkbenchSettings:
    return WorkbenchSettings().load_persisted_overrides()
