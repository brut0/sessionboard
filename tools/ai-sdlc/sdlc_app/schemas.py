"""Pydantic data contracts for the Companion AI SDLC Web Workbench."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

StageName = Literal[
    "intake",
    "spec",
    "architect",
    "tdd_tests",
    "implement",
    "fix_failure",
    "review",
]

GateName = Literal[
    "hygiene",
    "openapi_lint",
    "openapi_sync",
    "backend_lint",
    "backend_tests",
    "frontend_checks",
    "ai_sdlc_tests",
]


class HealthResponse(BaseModel):
    status: str
    repo_root: str
    git_branch: str
    gh_authenticated: bool
    gemini_cli_available: bool


class ConfigStatus(BaseModel):
    llm_provider: Literal["gemini", "openai"]
    llm_model: str
    openai_base_url: str
    has_api_key: bool
    masked_key: str


class ConfigUpdateRequest(BaseModel):
    llm_provider: Literal["gemini", "openai"] | None = None
    llm_model: str | None = None
    api_key: str | None = None
    openai_base_url: str | None = None


class FilePatch(BaseModel):
    path: str = Field(..., min_length=1)
    content: str
    rationale: str = ""
    diff_preview: str = ""
    applied: bool = False


class CreateRunRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=140)
    prompt: str = Field(..., min_length=5, max_length=8000)


class StageRequest(BaseModel):
    guidance: str = ""
    failing_output: str = ""


class ApplyPatchesRequest(BaseModel):
    paths: list[str] | None = None
    custom_patches: list[FilePatch] | None = None


class ApplyPatchesResult(BaseModel):
    applied_paths: list[str]
    run: RunState


class GateRequest(BaseModel):
    gates: list[GateName] = Field(
        default_factory=lambda: ["hygiene", "backend_lint", "backend_tests", "frontend_checks"]
    )


class GateCheckResult(BaseModel):
    gate: str
    command: str
    passed: bool
    exit_code: int
    duration_ms: int
    output: str


class CreateIssueRequest(BaseModel):
    title: str | None = None
    labels: list[str] | None = None
    body: str | None = None


class BranchRequest(BaseModel):
    branch_name: str = Field(..., min_length=3, max_length=120)


class CommitRequest(BaseModel):
    message: str = Field(..., min_length=5, max_length=200)
    agent_role: str = "devops-agent"


class CreatePRRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=180)
    close_issue: bool = False
    extra_notes: str = ""


class AgentCliRequest(BaseModel):
    instruction: str = Field(..., min_length=5, max_length=6000)


class PipelineRunSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    current_stage: str
    spec_approved: bool
    issue_number: int | None = None
    branch_name: str | None = None
    pr_url: str | None = None


class RunState(BaseModel):
    id: str
    title: str
    prompt: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    current_stage: str = "created"
    spec_approved: bool = False
    issue_number: int | None = None
    issue_url: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    intake: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None
    architect: dict[str, Any] | None = None
    tdd_tests: dict[str, Any] | None = None
    implement: dict[str, Any] | None = None
    fix_failure: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    pending_patches: list[FilePatch] = Field(default_factory=list)
    gate_results: list[GateCheckResult] = Field(default_factory=list)
    cli_log: str = ""


ApplyPatchesResult.model_rebuild()
