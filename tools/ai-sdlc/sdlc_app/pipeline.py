"""Pipeline stage execution, unified diff previews, and safe patch application."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Protocol

from sdlc_app.hygiene import HygieneViolationError, validate_patch_target, validate_text_hygiene
from sdlc_app.llm import extract_json_object
from sdlc_app.prompts import build_prompts_for_stage
from sdlc_app.schemas import FilePatch, RunState, SearchReplaceEdit, StageName


class CompletionLLM(Protocol):
    def complete(
        self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2
    ) -> str: ...


class SpecApprovalRequiredError(RuntimeError):
    """Raised if Architect / Implement is invoked before Spec approval."""


def _compute_diff_preview(repo_root: Path, rel_path: str, new_content: str) -> str:
    try:
        target = validate_patch_target(repo_root, rel_path)
    except HygieneViolationError as exc:
        return f"BLOCKED PATH: {exc}"

    old_lines: list[str] = []
    if target.is_file():
        old_lines = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
    )
    rendered = "".join(diff)
    return rendered or "(no textual diff vs disk)"


def _resolve_surgical_edits(
    repo_root: Path,
    rel_path: str,
    raw_edits: list[Any],
) -> tuple[str, list[SearchReplaceEdit], str | None]:
    """Apply ordered search/replace hunks against an existing file on disk."""
    try:
        target = validate_patch_target(repo_root, rel_path)
    except HygieneViolationError as exc:
        return "", [], f"BLOCKED PATH: {exc}"

    if not target.is_file():
        return "", [], f"EDIT ERROR: target file does not exist yet on disk: {rel_path}"

    existing = target.read_text(encoding="utf-8", errors="replace")
    resolved = existing
    parsed_edits: list[SearchReplaceEdit] = []
    for raw_edit in raw_edits:
        if not isinstance(raw_edit, dict):
            continue
        search = str(raw_edit.get("search", ""))
        replace = str(raw_edit.get("replace", ""))
        if not search:
            continue
        parsed_edits.append(SearchReplaceEdit(search=search, replace=replace))
        if search not in resolved:
            snippet = search[:80].replace("\n", "\\n")
            return (
                existing,
                parsed_edits,
                f"EDIT MISMATCH: search block not found in {rel_path}: {snippet!r}",
            )
        resolved = resolved.replace(search, replace, 1)

    return resolved, parsed_edits, None


def _normalize_patches(repo_root: Path, raw_patches: Any) -> list[FilePatch]:
    if not isinstance(raw_patches, list):
        return []
    patches: list[FilePatch] = []
    for item in raw_patches:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue

        content = str(item.get("content", ""))
        rationale = str(item.get("rationale", ""))
        raw_edits = item.get("edits")
        edits: list[SearchReplaceEdit] = []
        diff_error: str | None = None

        if isinstance(raw_edits, list) and raw_edits:
            resolved_content, edits, diff_error = _resolve_surgical_edits(
                repo_root, path, raw_edits
            )
            if diff_error is None:
                content = resolved_content
            elif not content:
                content = resolved_content

        diff_preview = diff_error if diff_error else _compute_diff_preview(repo_root, path, content)
        patches.append(
            FilePatch(
                path=path,
                content=content,
                rationale=rationale,
                diff_preview=diff_preview,
                applied=False,
                edits=edits,
            )
        )
    return patches


def execute_stage(
    *,
    repo_root: Path,
    run: RunState,
    stage: StageName,
    llm: CompletionLLM,
    guidance: str = "",
    failing_output: str = "",
    context_files: list[str] | None = None,
) -> RunState:
    """Execute one LLM-driven AI SDLC stage and record outputs onto RunState."""
    if stage in {"architect", "tdd_tests", "implement"} and not run.spec_approved:
        raise SpecApprovalRequiredError(
            f"Spec-First rule: review and approve the specification before running '{stage}'."
        )

    merged_context = list(context_files or [])
    for patch in run.pending_patches:
        if patch.path not in merged_context:
            merged_context.append(patch.path)

    sys_prompt, usr_prompt = build_prompts_for_stage(
        repo_root,
        run,
        stage,
        guidance=guidance,
        failing_output=failing_output,
        context_files=merged_context,
    )
    raw = llm.complete(system_prompt=sys_prompt, user_prompt=usr_prompt)
    parsed = extract_json_object(raw)

    if stage == "intake":
        run.intake = parsed
    elif stage == "spec":
        run.spec = parsed
    elif stage == "architect":
        run.architect = parsed
    elif stage == "tdd_tests":
        run.tdd_tests = parsed
    elif stage == "implement":
        run.implement = parsed
    elif stage == "fix_failure":
        run.fix_failure = parsed
    elif stage == "review":
        run.review = parsed

    if "patches" in parsed:
        new_patches = _normalize_patches(repo_root, parsed.get("patches"))
        # Merge / replace pending patches with the same path so the UI stays tidy
        by_path = {p.path: p for p in run.pending_patches if not p.applied}
        for patch in new_patches:
            by_path[patch.path] = patch
        run.pending_patches = list(by_path.values())

    run.current_stage = stage
    return run


def apply_patches_to_repo(
    *,
    repo_root: Path,
    run: RunState,
    paths: list[str] | None = None,
    custom_patches: list[FilePatch] | None = None,
) -> tuple[list[str], RunState]:
    """Validate path safety + hygiene before writing approved AI patches to disk."""
    to_apply: list[FilePatch] = []
    if custom_patches:
        to_apply = [
            FilePatch(
                path=p.path,
                content=p.content,
                rationale=p.rationale,
                diff_preview=_compute_diff_preview(repo_root, p.path, p.content),
            )
            for p in custom_patches
        ]
    else:
        wanted = set(paths) if paths is not None else None
        for p in run.pending_patches:
            if wanted is None or p.path in wanted:
                to_apply.append(p)

    # Validate ALL patches BEFORE writing ANY file (atomic validation)
    validated_writes: list[tuple[FilePatch, Path]] = []
    for patch in to_apply:
        if patch.diff_preview.startswith(("EDIT MISMATCH:", "EDIT ERROR:")):
            raise HygieneViolationError(patch.diff_preview)
        target = validate_patch_target(repo_root, patch.path)
        validate_text_hygiene(patch.content, rel_path=patch.path, repo_root=repo_root)
        validated_writes.append((patch, target))

    applied_paths: list[str] = []
    for patch, target in validated_writes:
        target.parent.mkdir(parents=True, exist_ok=True)
        content = patch.content
        if content and not content.endswith("\n"):
            content += "\n"
        target.write_text(content, encoding="utf-8")
        patch.applied = True
        applied_paths.append(patch.path)

    if not custom_patches:
        applied_set = set(applied_paths)
        for pending in run.pending_patches:
            if pending.path in applied_set:
                pending.applied = True

    return applied_paths, run
