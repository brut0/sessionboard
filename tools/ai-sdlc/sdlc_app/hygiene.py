"""Path containment and SessionBoard repository hygiene guards."""

from __future__ import annotations

import os
import re
from pathlib import Path

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")

FORBIDDEN_PATH_PREFIXES = (
    ".git",
    ".local",
    ".venv",
    ".pytest_cache",
    "tools/ai-sdlc/.venv",
    "node_modules",
    "backend/app/static",
    "frontend/dist",
)

FORBIDDEN_EXACT_NAMES = {
    ".env",
}


class HygieneViolationError(ValueError):
    """Raised when a proposed file path or text violates repository guardrails."""


def validate_patch_target(repo_root: Path, rel_path: str) -> Path:
    """Ensure target path stays strictly inside repo_root and out of protected paths."""
    cleaned = rel_path.strip().replace("\\", "/")
    if not cleaned:
        raise HygieneViolationError("Patch path must not be empty.")
    if cleaned.startswith("/") or (len(cleaned) >= 2 and cleaned[1] == ":"):
        raise HygieneViolationError(f"Absolute paths are forbidden: {cleaned}")

    candidate = Path(cleaned)
    if ".." in candidate.parts:
        raise HygieneViolationError(f"Path traversal ('..') is forbidden: {cleaned}")

    first_part = candidate.parts[0] if candidate.parts else ""
    if first_part in FORBIDDEN_EXACT_NAMES or first_part.startswith(".env."):
        raise HygieneViolationError(f"Protected dotfile cannot be modified: {cleaned}")

    normalized = candidate.as_posix()
    for prefix in FORBIDDEN_PATH_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            raise HygieneViolationError(f"Protected directory cannot be modified: {cleaned}")

    root_resolved = repo_root.resolve()
    target_resolved = (root_resolved / candidate).resolve()
    if not target_resolved.is_relative_to(root_resolved):
        raise HygieneViolationError(f"Resolved path escapes repository root: {cleaned}")

    return target_resolved


def _load_forbidden_patterns(repo_root: Path | None) -> list[re.Pattern[str]]:
    raw = os.environ.get("FORBIDDEN_TERMS", "")
    if not raw.strip() and repo_root is not None:
        terms_file = repo_root / ".local" / "forbidden-terms.txt"
        if terms_file.is_file():
            raw = terms_file.read_text(encoding="utf-8")

    patterns: list[re.Pattern[str]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(re.compile(stripped, re.IGNORECASE))
    return patterns


def validate_text_hygiene(
    content: str,
    *,
    rel_path: str,
    repo_root: Path | None = None,
) -> None:
    """Enforce English-only text and zero matches against .local/forbidden-terms.txt."""
    patterns = _load_forbidden_patterns(repo_root)
    for lineno, line in enumerate(content.splitlines(), start=1):
        if CYRILLIC_RE.search(line):
            raise HygieneViolationError(
                f"{rel_path}:{lineno}: contains Cyrillic characters (English only policy)"
            )
        for idx, pat in enumerate(patterns, start=1):
            if pat.search(line):
                raise HygieneViolationError(
                    f"{rel_path}:{lineno}: matched forbidden pattern #{idx} (<redacted>)"
                )
