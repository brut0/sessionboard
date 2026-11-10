"""FastAPI entrypoint for the SessionBoard Companion AI SDLC Web Workbench."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sdlc_app.config import WorkbenchSettings, get_settings
from sdlc_app.hygiene import HygieneViolationError
from sdlc_app.llm import LLMClient, LLMError, mask_secret
from sdlc_app.pipeline import SpecApprovalRequiredError, apply_patches_to_repo, execute_stage
from sdlc_app.runners import (
    commit_changes,
    create_feature_branch,
    create_github_issue,
    create_pull_request,
    get_git_overview,
    run_gate,
    run_gemini_cli_headless,
)
from sdlc_app.schemas import (
    AgentCliRequest,
    ApplyPatchesRequest,
    ApplyPatchesResult,
    BranchRequest,
    CommitRequest,
    ConfigStatus,
    ConfigUpdateRequest,
    CreateIssueRequest,
    CreatePRRequest,
    CreateRunRequest,
    GateRequest,
    HealthResponse,
    PipelineRunSummary,
    RunState,
    StageName,
    StageRequest,
)
from sdlc_app.store import RunStore

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _build_llm_from_settings(settings: WorkbenchSettings) -> LLMClient:
    return LLMClient(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.effective_api_key(),
        base_url=settings.openai_base_url,
    )


def create_app(
    *,
    settings: WorkbenchSettings | None = None,
    llm_factory: Callable[[WorkbenchSettings], Any] | None = None,
) -> FastAPI:
    active_settings = (settings or get_settings()).load_persisted_overrides()
    state: dict[str, WorkbenchSettings] = {"settings": active_settings}
    store = RunStore(active_settings.runs_dir)
    build_llm = llm_factory or _build_llm_from_settings

    app = FastAPI(
        title="SessionBoard AI SDLC Workbench",
        version="0.1.0",
        description="Companion SDD/TDD Web Workbench alongside SessionBoard",
    )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        git_info = get_git_overview(state["settings"].repo_root)
        return HealthResponse(
            status="ok",
            repo_root=str(state["settings"].repo_root),
            git_branch=str(git_info["branch"]),
            gh_authenticated=bool(git_info["gh_authenticated"]),
            gemini_cli_available=bool(git_info["gemini_cli_available"]),
        )

    @app.get("/api/git-status")
    def git_status() -> dict[str, object]:
        return get_git_overview(state["settings"].repo_root)

    @app.get("/api/stages")
    def list_stages() -> list[dict[str, str]]:
        return [
            {
                "stage": "intake",
                "title": "Stage 1 - Intake & Constitution Guard",
                "requires_spec_approval": "false",
            },
            {
                "stage": "spec",
                "title": "Stage 2 - Spec Authoring & Human Approval",
                "requires_spec_approval": "false",
            },
            {
                "stage": "architect",
                "title": "Stage 3 - Architect Plan, OpenAPI & Issue",
                "requires_spec_approval": "true",
            },
            {
                "stage": "tdd_tests",
                "title": "Stage 4a - Generate Failing TDD Tests",
                "requires_spec_approval": "true",
            },
            {
                "stage": "implement",
                "title": "Stage 4b - Implement Minimal Production Code",
                "requires_spec_approval": "true",
            },
            {
                "stage": "fix_failure",
                "title": "Stage 5 - AI Gate Failure Fixer",
                "requires_spec_approval": "false",
            },
            {
                "stage": "review",
                "title": "Stage 6 - Independent 10-Point Code Review",
                "requires_spec_approval": "false",
            },
        ]

    @app.get("/api/config", response_model=ConfigStatus)
    def get_config() -> ConfigStatus:
        cfg = state["settings"]
        key = cfg.effective_api_key()
        return ConfigStatus(
            llm_provider=cfg.llm_provider,
            llm_model=cfg.llm_model,
            openai_base_url=cfg.openai_base_url,
            has_api_key=bool(key.strip()),
            masked_key=mask_secret(key),
        )

    @app.put("/api/config", response_model=ConfigStatus)
    def update_config(body: ConfigUpdateRequest) -> ConfigStatus:
        cfg = state["settings"]
        updates: dict[str, object] = {}
        if body.llm_provider is not None:
            updates["llm_provider"] = body.llm_provider
        if body.llm_model is not None and body.llm_model.strip():
            updates["llm_model"] = body.llm_model.strip()
        if body.openai_base_url is not None and body.openai_base_url.strip():
            updates["openai_base_url"] = body.openai_base_url.strip()

        target_provider = str(updates.get("llm_provider", cfg.llm_provider))
        if body.api_key is not None and body.api_key.strip():
            field = "gemini_api_key" if target_provider == "gemini" else "openai_api_key"
            updates[field] = body.api_key.strip()

        cfg = cfg.model_copy(update=updates)
        cfg.save_persisted_overrides()
        state["settings"] = cfg
        key = cfg.effective_api_key()
        return ConfigStatus(
            llm_provider=cfg.llm_provider,
            llm_model=cfg.llm_model,
            openai_base_url=cfg.openai_base_url,
            has_api_key=bool(key.strip()),
            masked_key=mask_secret(key),
        )

    @app.get("/api/runs", response_model=list[PipelineRunSummary])
    def list_runs() -> list[PipelineRunSummary]:
        return store.list_summaries()

    @app.post("/api/runs", response_model=RunState, status_code=status.HTTP_201_CREATED)
    def create_run(body: CreateRunRequest) -> RunState:
        run = RunState(
            id=uuid.uuid4().hex[:12],
            title=body.title.strip(),
            prompt=body.prompt.strip(),
        )
        return store.save(run)

    @app.get("/api/runs/{run_id}", response_model=RunState)
    def get_run(run_id: str) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.post("/api/runs/{run_id}/approve-spec", response_model=RunState)
    def approve_spec(run_id: str) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        run.spec_approved = True
        return store.save(run)

    @app.post("/api/runs/{run_id}/stages/{stage}", response_model=RunState)
    def run_stage(run_id: str, stage: StageName, body: StageRequest) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        llm = build_llm(state["settings"])
        try:
            updated = execute_stage(
                repo_root=state["settings"].repo_root,
                run=run,
                stage=stage,
                llm=llm,
                guidance=body.guidance,
                failing_output=body.failing_output,
            )
        except SpecApprovalRequiredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return store.save(updated)

    @app.post("/api/runs/{run_id}/apply", response_model=ApplyPatchesResult)
    def apply_patches(run_id: str, body: ApplyPatchesRequest) -> ApplyPatchesResult:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        try:
            applied_paths, updated = apply_patches_to_repo(
                repo_root=state["settings"].repo_root,
                run=run,
                paths=body.paths,
                custom_patches=body.custom_patches,
            )
        except HygieneViolationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        store.save(updated)
        return ApplyPatchesResult(applied_paths=applied_paths, run=updated)

    @app.post("/api/runs/{run_id}/gates", response_model=RunState)
    def run_gates(run_id: str, body: GateRequest) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        results = [run_gate(state["settings"].repo_root, g) for g in body.gates]
        run.gate_results.extend(results)
        return store.save(run)

    @app.post("/api/runs/{run_id}/issue", response_model=RunState)
    def create_issue(run_id: str, body: CreateIssueRequest) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        draft = (run.architect or {}).get("issue_draft", {}) if run.architect else {}
        title = (body.title or draft.get("title") or f"[Feature] {run.title}").strip()
        labels = body.labels if body.labels is not None else draft.get("labels", ["type:feature"])
        issue_body = (body.body or draft.get("body") or run.prompt).strip()
        try:
            num, url = create_github_issue(
                state["settings"].repo_root,
                title=title,
                labels=[str(lbl) for lbl in labels],
                body=issue_body,
            )
        except (HygieneViolationError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        run.issue_number = num
        run.issue_url = url
        return store.save(run)

    @app.post("/api/runs/{run_id}/branch", response_model=RunState)
    def make_branch(run_id: str, body: BranchRequest) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        try:
            branch = create_feature_branch(state["settings"].repo_root, body.branch_name.strip())
        except (HygieneViolationError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        run.branch_name = branch
        return store.save(run)

    @app.post("/api/runs/{run_id}/commit")
    def commit_run(run_id: str, body: CommitRequest) -> dict[str, object]:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        try:
            out = commit_changes(
                state["settings"].repo_root,
                message=body.message,
                agent_role=body.agent_role,
                issue_number=run.issue_number,
            )
        except (HygieneViolationError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"committed": True, "output": out}

    @app.post("/api/runs/{run_id}/pr", response_model=RunState)
    def open_pr(run_id: str, body: CreatePRRequest) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        ref_keyword = "Closes" if body.close_issue else "Refs"
        linked = f"{ref_keyword} #{run.issue_number}" if run.issue_number else "Refs (local)"
        gate_lines = (
            "\n".join(
                f"{g.command} -> {'PASS' if g.passed else 'FAIL'} (exit {g.exit_code})"
                for g in run.gate_results[-6:]
            )
            or "(run gates before merge)"
        )
        pr_body = (
            f"## Summary\n{run.title}\n\n{body.extra_notes}\n\n"
            f"## Linked issue\n{linked}\n\n"
            f"## Gate output\n```text\n{gate_lines}\n```\n"
        )
        try:
            pr_url = create_pull_request(
                state["settings"].repo_root,
                title=body.title,
                body=pr_body,
                issue_number=run.issue_number,
            )
        except (HygieneViolationError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        run.pr_url = pr_url
        return store.save(run)

    @app.post("/api/runs/{run_id}/agent-cli", response_model=RunState)
    def invoke_cli_agent(run_id: str, body: AgentCliRequest) -> RunState:
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        cfg = state["settings"]
        try:
            code, out = run_gemini_cli_headless(
                cfg.repo_root,
                instruction=body.instruction,
                model=cfg.llm_model,
                api_key=cfg.gemini_api_key,
            )
        except HygieneViolationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        run.cli_log = f"[exit {code}]\n{out}"
        return store.save(run)

    return app


app = create_app()
