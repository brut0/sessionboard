"""Repository context reader for SessionBoard AI SDLC prompts."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _read_bounded(path: Path, max_chars: int = 10000) -> str:
    if not path.is_file():
        return "(not created yet)"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated for prompt budget]"


def read_role_prompt(repo_root: Path, role: str) -> str:
    role_file = repo_root / ".agents" / "roles" / f"{role}.md"
    if role_file.is_file():
        return role_file.read_text(encoding="utf-8", errors="replace")
    return f"# Role: {role}\nFollow AGENTS.md and specs/constitution.md strictly.\n"


def git_diff_summary(repo_root: Path, max_chars: int = 12000) -> str:
    """Return current git status + diff relative to HEAD for AI review/fix stages."""
    try:
        status_res = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        diff_res = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return f"(unable to read git diff: {exc})"

    combined = f"=== git status ===\n{status_res.stdout}\n=== git diff HEAD ===\n{diff_res.stdout}"
    if len(combined) > max_chars:
        return combined[:max_chars] + "\n... [diff truncated]"
    return combined


def build_stage_context(repo_root: Path, stage: str) -> str:
    """Collect focused, token-efficient SessionBoard context for a given SDLC stage."""
    parts = [
        "=== AGENTS.md ===\n" + _read_bounded(repo_root / "AGENTS.md", 4000),
        "=== specs/constitution.md ===\n"
        + _read_bounded(repo_root / "specs" / "constitution.md", 6000),
        "=== specs/product-spec.md ===\n"
        + _read_bounded(repo_root / "specs" / "product-spec.md", 10000),
    ]

    if stage in {"architect", "tdd_tests", "implement", "fix_failure", "review"}:
        parts.append(
            "=== specs/api/openapi.yaml ===\n"
            + _read_bounded(repo_root / "specs" / "api" / "openapi.yaml", 10000)
        )
        parts.append(
            "=== specs/data-model.md ===\n"
            + _read_bounded(repo_root / "specs" / "data-model.md", 5000)
        )
        parts.append(
            "=== specs/tasks.md ===\n" + _read_bounded(repo_root / "specs" / "tasks.md", 5000)
        )

    if stage in {"tdd_tests", "implement", "fix_failure", "review"}:
        parts.append(
            "=== docs/architecture.md ===\n"
            + _read_bounded(repo_root / "docs" / "architecture.md", 5000)
        )
        parts.append("=== git status & diff ===\n" + git_diff_summary(repo_root, 10000))

    return "\n\n".join(parts)
