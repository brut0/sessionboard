"""Secret sanitization and ephemeral cloud workspace bootstrap helpers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

TOKEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{6,}"), "<redacted-gh-token>"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{6,}"), "<redacted-gh-pat>"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{8,}"), "<redacted-gemini-key>"),
    (re.compile(r"sk-[A-Za-z0-9\-_]{10,}"), "<redacted-api-key>"),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]*@"), r"\1<redacted>@"),
    (re.compile(r"(https?://)[^/\s:@]+@"), r"\1<redacted>@"),
)

SECRET_ENV_VARS = (
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "SDLC_OWNER_PASSWORD",
    "SDLC_SESSION_SECRET",
    "GH_TOKEN",
    "GITHUB_TOKEN",
)


def sanitize_secrets(text: str, *, extra_secrets: Iterable[str] = ()) -> str:
    """Scrub known secret values and token patterns from logs and subprocess errors."""
    if not text:
        return text

    redacted = text
    candidates = list(extra_secrets) + [os.environ.get(var, "") for var in SECRET_ENV_VARS]
    for secret in candidates:
        trimmed = secret.strip()
        if trimmed:
            redacted = redacted.replace(trimmed, "<redacted>")

    for pattern, replacement in TOKEN_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _validate_clone_url(clone_repo_url: str) -> str | None:
    """Ensure clone URL contains no embedded HTTP credentials."""
    cleaned = clone_repo_url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https"} and (parsed.username or parsed.password):
        return "Credentials must not be embedded in SDLC_CLONE_REPO_URL."
    if "@" in cleaned and parsed.scheme in {"http", "https"}:
        return "Credentials must not be embedded in SDLC_CLONE_REPO_URL."
    return None


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    gh_token: str = "",
) -> tuple[int, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if gh_token.strip():
        env["GH_TOKEN"] = gh_token.strip()
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    raw_out = "\n".join(p for p in (proc.stdout.strip(), proc.stderr.strip()) if p)
    return proc.returncode, sanitize_secrets(raw_out, extra_secrets=[gh_token])


def bootstrap_workspace(
    repo_root: Path,
    *,
    clone_repo_url: str,
    gh_token: str = "",
) -> dict[str, object]:
    """Initialize an ephemeral git checkout cleanly when running in cloud containers."""
    cleaned_url = clone_repo_url.strip()
    if not cleaned_url:
        return {"ok": True, "action": "skipped", "detail": "No clone URL configured."}

    url_err = _validate_clone_url(cleaned_url)
    if url_err:
        return {"ok": False, "action": "rejected", "detail": url_err}

    repo_root = repo_root.resolve()
    repo_root.parent.mkdir(parents=True, exist_ok=True)

    action = "verified"
    if not (repo_root / ".git").exists():
        action = "cloned"
        clone_args = ["clone", "--depth=50", cleaned_url, str(repo_root)]
        if gh_token.strip() and shutil.which("gh"):
            clone_args = [
                "-c",
                "credential.helper=!gh auth git-credential",
                *clone_args,
            ]
        code, out = _run_git(clone_args, cwd=repo_root.parent, gh_token=gh_token)
        if code != 0:
            return {"ok": False, "action": "clone_failed", "detail": out or "git clone failed"}

    # Ensure non-interactive bot git defaults inside container workspaces
    _run_git(["config", "commit.gpgsign", "false"], cwd=repo_root, gh_token=gh_token)
    c_name, current_name = _run_git(["config", "--get", "user.name"], cwd=repo_root)
    if c_name != 0 or not current_name.strip():
        _run_git(["config", "user.name", "SessionBoard AI SDLC"], cwd=repo_root)
    c_mail, current_mail = _run_git(["config", "--get", "user.email"], cwd=repo_root)
    if c_mail != 0 or not current_mail.strip():
        _run_git(["config", "user.email", "ai-sdlc@sessionboard.local"], cwd=repo_root)

    gh_bin = shutil.which("gh")
    if gh_bin and gh_token.strip():
        env = os.environ.copy()
        env["GH_TOKEN"] = gh_token.strip()
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(
            [gh_bin, "auth", "setup-git"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return {"ok": True, "action": action, "repo_root": str(repo_root)}
