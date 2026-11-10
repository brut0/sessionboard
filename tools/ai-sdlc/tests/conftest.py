"""Pytest safeguards isolating AI SDLC tests from the live repository root."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdlc_app.config import get_settings


@pytest.fixture(autouse=True)
def isolate_sdlc_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent any test from defaulting SDLC_REPO_ROOT to the live repository."""
    monkeypatch.setenv("SDLC_REPO_ROOT", str(tmp_path))
    get_settings.cache_clear()
