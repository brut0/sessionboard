"""Pytest safeguards isolating AI SDLC tests from the live repository root."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdlc_app.config import get_settings


@pytest.fixture(autouse=True)
def isolate_sdlc_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent any test from inheriting live repo root or cloud auth env variables."""
    monkeypatch.setenv("SDLC_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "local")
    for var in (
        "RENDER",
        "SDLC_REQUIRE_AUTH",
        "SDLC_OWNER_PASSWORD",
        "SDLC_SESSION_SECRET",
        "SDLC_STATE_DIR",
        "SDLC_CLONE_REPO_URL",
        "SDLC_NON_INTERACTIVE",
    ):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
