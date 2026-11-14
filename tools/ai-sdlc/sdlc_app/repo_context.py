"""Repository context reader for SessionBoard AI SDLC prompts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from sdlc_app.hygiene import HygieneViolationError, validate_patch_target

DEFAULT_CODE_CONTEXT_FILES = (
    "backend/app/models.py",
    "backend/app/schemas.py",
    "backend/app/domain/conflicts.py",
    "backend/app/routers/sessions.py",
    "backend/app/routers/directory.py",
    "frontend/src/App.tsx",
    "frontend/src/components/DayBoard.tsx",
    "frontend/src/components/WeekBoard.tsx",
    "frontend/src/components/BookingModal.tsx",
    "frontend/src/components/DirectoryPage.tsx",
    "frontend/src/test/mocks/handlers.ts",
)

_TREE_PREFIXES = ("specs/", "docs/", "backend/app/", "backend/tests/", "frontend/src/")
_IGNORED_DIR_PARTS = {
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
}


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


def list_repo_tree(repo_root: Path, max_entries: int = 220) -> str:
    """List relevant tracked or existing repository files for LLM path grounding."""
    entries: list[str] = []
    if (repo_root / ".git").exists():
        try:
            res = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                entries = [
                    line.strip()
                    for line in res.stdout.splitlines()
                    if line.strip().startswith(_TREE_PREFIXES)
                    and not line.strip().startswith("backend/app/static/")
                ]
        except Exception:
            entries = []

    if not entries:
        for base in ("specs", "docs", "backend", "frontend"):
            base_dir = repo_root / base
            if not base_dir.is_dir():
                continue
            for p in sorted(base_dir.rglob("*")):
                if not p.is_file():
                    continue
                if any(part in _IGNORED_DIR_PARTS for part in p.parts):
                    continue
                rel = p.relative_to(repo_root).as_posix()
                if not rel.startswith("backend/app/static/"):
                    entries.append(rel)

    entries = sorted(set(entries))
    if not entries:
        return "(no source files discovered yet)"
    if len(entries) > max_entries:
        shown = entries[:max_entries]
        return "\n".join(shown) + f"\n... ({len(entries) - max_entries} more files)"
    return "\n".join(entries)


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


def build_stage_context(
    repo_root: Path,
    stage: str,
    *,
    context_files: list[str] | None = None,
) -> str:
    """Collect focused, token-efficient SessionBoard context for a given SDLC stage."""
    parts = [
        "=== AGENTS.md ===\n" + _read_bounded(repo_root / "AGENTS.md", 4000),
        "=== specs/constitution.md ===\n"
        + _read_bounded(repo_root / "specs" / "constitution.md", 6000),
        "=== specs/product-spec.md ===\n"
        + _read_bounded(repo_root / "specs" / "product-spec.md", 10000),
    ]

    if stage in {"architect", "tdd_tests", "implement", "fix_failure", "review"}:
        parts.append("=== Repository File Tree ===\n" + list_repo_tree(repo_root))
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

        seen_paths: set[str] = set()
        for rel in context_files or []:
            cleaned = rel.strip().replace("\\", "/")
            if not cleaned or cleaned in seen_paths:
                continue
            seen_paths.add(cleaned)
            try:
                target = validate_patch_target(repo_root, cleaned)
            except HygieneViolationError as exc:
                parts.append(f"=== Target Context File: {cleaned} ===\n(skipped: {exc})")
                continue
            parts.append(
                f"=== Target Context File: {cleaned} ===\n" + _read_bounded(target, max_chars=20000)
            )

        for rel in DEFAULT_CODE_CONTEXT_FILES:
            if rel in seen_paths:
                continue
            target = repo_root / rel
            if target.is_file():
                seen_paths.add(rel)
                parts.append(
                    f"=== Existing Source: {rel} ===\n" + _read_bounded(target, max_chars=12000)
                )

        parts.append("=== git status & diff ===\n" + git_diff_summary(repo_root, 10000))

    return "\n\n".join(parts)
