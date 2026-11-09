#!/usr/bin/env python3
"""Repository hygiene check for SessionBoard.

Fails with exit code 1 if any tracked or untracked non-ignored text file,
or any git commit message, contains:
1. Any Cyrillic character (U+0400..U+04FF).
2. Any forbidden term regex loaded from the FORBIDDEN_TERMS environment
   variable (newline-separated) or from .local/forbidden-terms.txt.

Never prints the matched forbidden pattern or matched substring in output
so CI logs cannot leak private prototype terms.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_TERMS_FILE = REPO_ROOT / ".local" / "forbidden-terms.txt"


def load_forbidden_patterns() -> list[re.Pattern[str]]:
    raw = os.environ.get("FORBIDDEN_TERMS", "")
    if not raw.strip() and LOCAL_TERMS_FILE.is_file():
        raw = LOCAL_TERMS_FILE.read_text(encoding="utf-8")

    patterns: list[re.Pattern[str]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(re.compile(stripped, re.IGNORECASE))
    if not patterns:
        print(
            "WARNING: No forbidden-term patterns loaded (only Cyrillic check active).",
            file=sys.stderr,
        )
    return patterns


def list_candidate_files() -> list[Path]:
    try:
        res = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        paths = [REPO_ROOT / p for p in res.stdout.splitlines() if p.strip()]
        if paths:
            return paths
    except Exception:
        pass

    ignored_dirs = {".git", ".local", "node_modules", ".venv", "__pycache__", "dist"}
    out: list[Path] = []
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in ignored_dirs for part in p.relative_to(REPO_ROOT).parts):
            continue
        out.append(p)
    return out


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def scan_files(patterns: list[re.Pattern[str]]) -> list[str]:
    violations: list[str] = []
    for path in list_candidate_files():
        if not path.is_file() or is_binary(path):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if CYRILLIC_RE.search(line):
                violations.append(f"{rel}:{lineno}: contains Cyrillic characters")
            for idx, pat in enumerate(patterns, start=1):
                if pat.search(line):
                    violations.append(
                        f"{rel}:{lineno}: matched forbidden pattern #{idx} (<redacted>)"
                    )
    return violations


def scan_commits(patterns: list[re.Pattern[str]]) -> list[str]:
    violations: list[str] = []
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return violations
        log = subprocess.run(
            ["git", "log", "--all", "--format=%H%x00%B%x1e"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return violations

    for entry in log.stdout.split("\x1e"):
        if "\x00" not in entry:
            continue
        sha, body = entry.strip().split("\x00", 1)
        short = sha[:8]
        if CYRILLIC_RE.search(body):
            violations.append(f"commit {short}: message contains Cyrillic characters")
        for idx, pat in enumerate(patterns, start=1):
            if pat.search(body):
                violations.append(
                    f"commit {short}: message matched forbidden pattern #{idx} (<redacted>)"
                )
    return violations


def main() -> int:
    patterns = load_forbidden_patterns()
    violations = scan_files(patterns) + scan_commits(patterns)
    if violations:
        for v in violations:
            print(f"HYGIENE FAIL: {v}", file=sys.stderr)
        return 1
    print(f"OK: 0 violations ({len(patterns)} forbidden patterns checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
