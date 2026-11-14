"""FastAPI entrypoint for the SessionBoard Companion AI SDLC Web Workbench."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sdlc_app.auth import (
    HTTP_SESSION_COOKIE,
    HTTPS_SESSION_COOKIE,
    LoginRateLimiter,
    constant_time_equal,
    create_session_token,
    extract_client_ip,
    is_https_request,
    is_request_authenticated,
)
from sdlc_app.bootstrap import bootstrap_workspace
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
    LoginRequest,
    PipelineRunSummary,
    RunState,
    SessionStatus,
    StageName,
    StageRequest,
)
from sdlc_app.store import RunStore

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

PUBLIC_AUTH_ROUTES = {
    "/",
    "/favicon.ico",
    "/api/health",
    "/api/auth/session",
    "/api/auth/login",
    "/api/auth/logout",
}

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "connect-src 'self'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


def _with_security_headers(response: Response, request: Request) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), geolocation=(), microphone=()",
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", CSP_POLICY)
    response.headers.setdefault("Vary", "Sec-Fetch-Dest, Sec-Fetch-Mode, Sec-Fetch-Site")
    if is_https_request(request):
        response.headers.setdefault("Strict-Transport-Security", "max-age=300")
    return response


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
    bootstrap_status: dict[str, object] = {"ok": True, "action": "skipped"}
    if active_settings.clone_repo_url.strip():
        bootstrap_status = bootstrap_workspace(
            active_settings.repo_root,
            clone_repo_url=active_settings.clone_repo_url,
            gh_token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""),
        )

    state: dict[str, WorkbenchSettings] = {"settings": active_settings}
    store = RunStore(active_settings.runs_dir)
    build_llm = llm_factory or _build_llm_from_settings
    rate_limiter = LoginRateLimiter()

    app = FastAPI(
        title="SessionBoard AI SDLC Workbench",
        version="0.1.0",
        description="Companion SDD/TDD Web Workbench alongside SessionBoard",
    )

    @app.middleware("http")
    async def security_and_auth_middleware(request: Request, call_next: Callable) -> Response:
        cfg = state["settings"]

        if cfg.auth_required and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            sec_site = request.headers.get("sec-fetch-site")
            if sec_site and sec_site.strip().lower() not in {"same-origin", "none"}:
                resp = JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cross-site mutating requests are forbidden."},
                )
                return _with_security_headers(resp, request)

        path = request.url.path
        requires_owner = path in {"/docs", "/redoc", "/openapi.json"} or (
            path.startswith("/api/") and path not in PUBLIC_AUTH_ROUTES
        )
        if cfg.auth_required and requires_owner:
            if not cfg.auth_configured:
                resp = JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": (
                            "Workbench fail-closed: SDLC_OWNER_PASSWORD (min 12 chars) "
                            "is not configured."
                        )
                    },
                )
                return _with_security_headers(resp, request)
            if not is_request_authenticated(request, cfg):
                resp = JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Owner authentication required."},
                    headers={"WWW-Authenticate": "Bearer"},
                )
                return _with_security_headers(resp, request)

        response = await call_next(request)
        return _with_security_headers(response, request)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/auth/session", response_model=SessionStatus)
    def get_auth_session(request: Request) -> SessionStatus:
        cfg = state["settings"]
        return SessionStatus(
            auth_required=cfg.auth_required,
            configured=cfg.auth_configured,
            authenticated=is_request_authenticated(request, cfg),
        )

    @app.post("/api/auth/login", response_model=SessionStatus)
    def owner_login(body: LoginRequest, request: Request, response: Response) -> Any:
        cfg = state["settings"]
        if not cfg.auth_required:
            return SessionStatus(auth_required=False, configured=True, authenticated=True)
        if not cfg.auth_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Workbench fail-closed: SDLC_OWNER_PASSWORD (min 12 chars) is not configured."
                ),
            )

        client_ip = extract_client_ip(request)
        retry_after = rate_limiter.check_locked(client_ip)
        if retry_after is not None:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": f"Too many failed login attempts. Retry in {retry_after}s."},
                headers={"Retry-After": str(retry_after)},
            )

        if not constant_time_equal(body.password, cfg.owner_password):
            rate_limiter.record_failure(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid owner password.",
            )

        rate_limiter.reset(client_ip)
        token = create_session_token(cfg)
        secure_cookie = is_https_request(request)
        cookie_name = HTTPS_SESSION_COOKIE if secure_cookie else HTTP_SESSION_COOKIE
        response.set_cookie(
            key=cookie_name,
            value=token,
            max_age=cfg.session_ttl_seconds,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/",
        )
        return SessionStatus(auth_required=True, configured=True, authenticated=True)

    @app.post("/api/auth/logout", response_model=SessionStatus)
    def owner_logout(request: Request, response: Response) -> SessionStatus:
        cfg = state["settings"]
        secure_cookie = is_https_request(request)
        response.delete_cookie(key=HTTP_SESSION_COOKIE, path="/")
        response.delete_cookie(key=HTTPS_SESSION_COOKIE, path="/", secure=secure_cookie)
        response.headers["Clear-Site-Data"] = '"cookies", "storage", "cache"'
        return SessionStatus(
            auth_required=cfg.auth_required,
            configured=cfg.auth_configured,
            authenticated=not cfg.auth_required,
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        cfg = state["settings"]
        authed = is_request_authenticated(request, cfg)
        workspace_ready = bool(bootstrap_status.get("ok", True))
        if not workspace_ready:
            overall_status = "degraded"
        elif cfg.auth_required and not cfg.auth_configured:
            overall_status = "unconfigured"
        else:
            overall_status = "ok"

        if cfg.auth_required and not authed:
            return HealthResponse(
                status=overall_status,
                version=cfg.app_version,
                auth_required=True,
                auth_configured=cfg.auth_configured,
                authenticated=False,
                workspace_ready=workspace_ready,
            )

        git_info = get_git_overview(cfg.repo_root)
        return HealthResponse(
            status=overall_status,
            version=cfg.app_version,
            auth_required=cfg.auth_required,
            auth_configured=cfg.auth_configured,
            authenticated=True,
            workspace_ready=workspace_ready,
            repo_root=str(cfg.repo_root),
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
                context_files=body.context_files,
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
