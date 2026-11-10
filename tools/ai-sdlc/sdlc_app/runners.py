"""Allowlisted gate, git, GitHub CLI, and Gemini CLI subprocess runners."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from sdlc_app.hygiene import validate_text_hygiene
from sdlc_app.schemas import GateCheckResult, GateName


def _resolve_tool(names: tuple[str, ...]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_step(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int = 300,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str, int]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        combined = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
        return proc.returncode, combined, duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        return 124, f"Command timed out after {timeout}s: {' '.join(cmd)}", duration_ms
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return 127, f"Executable not found: {exc}", duration_ms


def run_gate(repo_root: Path, gate: GateName) -> GateCheckResult:
    """Execute one deterministic SessionBoard verification gate."""
    uv_bin = _resolve_tool(("uv", "uv.exe")) or "uv"
    npm_bin = _resolve_tool(("npm.cmd", "npm")) or "npm"
    npx_bin = _resolve_tool(("npx.cmd", "npx")) or "npx"

    if gate == "hygiene":
        cmd = [sys.executable, str(repo_root / "scripts" / "check_repo_hygiene.py")]
        code, out, ms = _run_step(cmd, cwd=repo_root, timeout=120)
        return GateCheckResult(
            gate=gate,
            command="python scripts/check_repo_hygiene.py",
            passed=code == 0,
            exit_code=code,
            duration_ms=ms,
            output=out or "(no output)",
        )

    if gate == "openapi_lint":
        cmd = [npx_bin, "-y", "@redocly/cli", "lint", "specs/api/openapi.yaml"]
        code, out, ms = _run_step(cmd, cwd=repo_root, timeout=180)
        return GateCheckResult(
            gate=gate,
            command="npx @redocly/cli lint specs/api/openapi.yaml",
            passed=code == 0,
            exit_code=code,
            duration_ms=ms,
            output=out or "(no output)",
        )

    if gate == "openapi_sync":
        fe_dir = repo_root / "frontend"
        code, out, ms = _run_step([npm_bin, "run", "gen:api"], cwd=fe_dir, timeout=120)
        return GateCheckResult(
            gate=gate,
            command="cd frontend && npm run gen:api",
            passed=code == 0,
            exit_code=code,
            duration_ms=ms,
            output=out or "(no output)",
        )

    if gate == "backend_lint":
        be_dir = repo_root / "backend"
        c1, o1, ms1 = _run_step([uv_bin, "run", "ruff", "check", "."], cwd=be_dir, timeout=120)
        c2, o2, ms2 = _run_step(
            [uv_bin, "run", "ruff", "format", "--check", "."], cwd=be_dir, timeout=120
        )
        code = 0 if (c1 == 0 and c2 == 0) else (c1 or c2)
        combined = f"[ruff check]\n{o1}\n\n[ruff format --check]\n{o2}".strip()
        return GateCheckResult(
            gate=gate,
            command="cd backend && uv run ruff check . && uv run ruff format --check .",
            passed=code == 0,
            exit_code=code,
            duration_ms=ms1 + ms2,
            output=combined,
        )

    if gate == "backend_tests":
        be_dir = repo_root / "backend"
        code, out, ms = _run_step(
            [uv_bin, "run", "pytest", "-v"],
            cwd=be_dir,
            timeout=300,
            extra_env={"OTEL_SDK_DISABLED": "true"},
        )
        return GateCheckResult(
            gate=gate,
            command="cd backend && uv run pytest -v",
            passed=code == 0,
            exit_code=code,
            duration_ms=ms,
            output=out or "(no output)",
        )

    if gate == "frontend_checks":
        fe_dir = repo_root / "frontend"
        c1, o1, ms1 = _run_step([npm_bin, "run", "typecheck"], cwd=fe_dir, timeout=120)
        c2, o2, ms2 = _run_step([npm_bin, "test"], cwd=fe_dir, timeout=180)
        code = 0 if (c1 == 0 and c2 == 0) else (c1 or c2)
        combined = f"[typecheck]\n{o1}\n\n[vitest]\n{o2}".strip()
        return GateCheckResult(
            gate=gate,
            command="cd frontend && npm run typecheck && npm test",
            passed=code == 0,
            exit_code=code,
            duration_ms=ms1 + ms2,
            output=combined,
        )

    # ai_sdlc_tests
    tools_dir = repo_root / "tools" / "ai-sdlc"
    code, out, ms = _run_step([uv_bin, "run", "pytest", "-v"], cwd=tools_dir, timeout=120)
    return GateCheckResult(
        gate=gate,
        command="cd tools/ai-sdlc && uv run pytest -v",
        passed=code == 0,
        exit_code=code,
        duration_ms=ms,
        output=out or "(no output)",
    )


def get_git_overview(repo_root: Path) -> dict[str, object]:
    """Return active branch, working tree status, gh auth, and gemini CLI presence."""
    _, branch_out, _ = _run_step(["git", "branch", "--show-current"], cwd=repo_root, timeout=10)
    _, status_out, _ = _run_step(["git", "status", "--short"], cwd=repo_root, timeout=10)
    gh_bin = _resolve_tool(("gh", "gh.exe"))
    gh_ok = False
    if gh_bin:
        gh_code, _, _ = _run_step([gh_bin, "auth", "status"], cwd=repo_root, timeout=15)
        gh_ok = gh_code == 0
    gemini_bin = _resolve_tool(("gemini.cmd", "gemini"))
    return {
        "branch": branch_out.strip() or "unknown",
        "dirty_files": [line for line in status_out.splitlines() if line.strip()],
        "gh_authenticated": gh_ok,
        "gemini_cli_available": gemini_bin is not None,
    }


def create_feature_branch(repo_root: Path, branch_name: str) -> str:
    validate_text_hygiene(branch_name, rel_path="git-branch", repo_root=repo_root)
    if not re.fullmatch(r"[a-zA-Z0-9._/-]+", branch_name):
        raise ValueError("Branch name contains invalid characters.")
    code, out, _ = _run_step(["git", "switch", "-c", branch_name], cwd=repo_root, timeout=20)
    if code != 0:
        raise RuntimeError(out or f"Failed to create branch {branch_name}")
    return branch_name


def create_github_issue(
    repo_root: Path, *, title: str, labels: list[str], body: str
) -> tuple[int, str]:
    validate_text_hygiene(f"{title}\n{body}", rel_path="github-issue", repo_root=repo_root)
    gh_bin = _resolve_tool(("gh", "gh.exe"))
    if not gh_bin:
        raise RuntimeError("GitHub CLI ('gh') is not installed or on PATH.")

    cmd = [gh_bin, "issue", "create", "--title", title, "--body", body]
    for lbl in labels:
        if lbl.strip():
            cmd.extend(["--label", lbl.strip()])
    code, out, _ = _run_step(cmd, cwd=repo_root, timeout=30)
    if code != 0:
        raise RuntimeError(out or "gh issue create failed")
    match = re.search(r"/issues/(\d+)", out)
    if not match:
        raise RuntimeError(f"Could not parse issue number from gh output: {out}")
    return int(match.group(1)), out.strip().splitlines()[-1]


def commit_changes(
    repo_root: Path, *, message: str, agent_role: str, issue_number: int | None
) -> str:
    validate_text_hygiene(message, rel_path="commit-message", repo_root=repo_root)
    _, branch_out, _ = _run_step(["git", "branch", "--show-current"], cwd=repo_root, timeout=10)
    current_branch = branch_out.strip()
    if current_branch in {"main", "master", ""}:
        raise RuntimeError(
            "Direct commits to 'main' are blocked by branch protection. "
            "Create a feature branch first."
        )

    trailers = [f"Agent: {agent_role}"]
    if issue_number is not None:
        trailers.append(f"Refs: #{issue_number}")
    full_msg = f"{message.strip()}\n\n" + "\n".join(trailers)

    c1, o1, _ = _run_step(["git", "add", "-A"], cwd=repo_root, timeout=20)
    if c1 != 0:
        raise RuntimeError(o1 or "git add failed")
    c2, o2, _ = _run_step(["git", "commit", "-m", full_msg], cwd=repo_root, timeout=30)
    if c2 != 0:
        raise RuntimeError(o2 or "git commit failed")
    return o2


def create_pull_request(
    repo_root: Path,
    *,
    title: str,
    body: str,
    issue_number: int | None,
) -> str:
    validate_text_hygiene(f"{title}\n{body}", rel_path="pull-request", repo_root=repo_root)
    gh_bin = _resolve_tool(("gh", "gh.exe"))
    if not gh_bin:
        raise RuntimeError("GitHub CLI ('gh') is not installed or on PATH.")

    c_push, o_push, _ = _run_step(
        ["git", "push", "-u", "origin", "HEAD"], cwd=repo_root, timeout=60
    )
    if c_push != 0:
        raise RuntimeError(o_push or "git push failed")

    cmd = [gh_bin, "pr", "create", "--title", title, "--body", body]
    c_pr, o_pr, _ = _run_step(cmd, cwd=repo_root, timeout=30)
    if c_pr != 0:
        raise RuntimeError(o_pr or "gh pr create failed")

    if issue_number is not None:
        _run_step(
            [
                gh_bin,
                "issue",
                "comment",
                str(issue_number),
                "--body",
                f"[ai-sdlc-workbench] Done. PR opened: {o_pr.strip().splitlines()[-1]}",
            ],
            cwd=repo_root,
            timeout=20,
        )
    return o_pr.strip().splitlines()[-1]


def run_gemini_cli_headless(
    repo_root: Path,
    *,
    instruction: str,
    model: str,
    api_key: str,
) -> tuple[int, str]:
    validate_text_hygiene(instruction, rel_path="gemini-cli-prompt", repo_root=repo_root)
    gemini_bin = _resolve_tool(("gemini.cmd", "gemini"))
    if not gemini_bin:
        return (
            127,
            "Local 'gemini' CLI binary was not found on PATH. "
            "Install @google/gemini-cli or use the built-in API stages above.",
        )

    extra_env = {"GEMINI_CLI_TRUST_WORKSPACE": "true"}
    if api_key.strip():
        extra_env["GEMINI_API_KEY"] = api_key.strip()

    code, out, _ = _run_step(
        [gemini_bin, "--yolo", "-m", model, "-p", instruction],
        cwd=repo_root,
        timeout=300,
        extra_env=extra_env,
    )
    if api_key.strip():
        out = out.replace(api_key.strip(), "<redacted-key>")
    return code, out
