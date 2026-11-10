"""Prompt builders binding SessionBoard agent roles to structured JSON outputs."""

from __future__ import annotations

import json
from pathlib import Path

from sdlc_app.repo_context import build_stage_context, read_role_prompt
from sdlc_app.schemas import RunState, StageName

STAGE_TO_ROLE: dict[StageName, str] = {
    "intake": "spec",
    "spec": "spec",
    "architect": "architect",
    "tdd_tests": "qa",
    "implement": "backend",
    "fix_failure": "backend",
    "review": "reviewer",
}

STAGE_OUTPUT_SCHEMAS: dict[StageName, str] = {
    "intake": """
Return ONLY a valid JSON object with keys:
{
  "in_scope": boolean,
  "non_goal_conflicts": ["conflict with specs/product-spec.md Non-Goals, if any"],
  "clarifications": ["concise question needing human input, or empty"],
  "suggested_branch": "feat/<short-kebab-slug>",
  "summary": "2-4 sentence architectural & scope assessment"
}
""".strip(),
    "spec": """
Return ONLY a valid JSON object with keys:
{
  "summary": "1-3 sentences summarizing spec updates",
  "spec_markdown": "Markdown additions (User Story / BR / Given-When-Then ACs / matrix)",
  "clarifications_resolved": ["bullets of decisions baked into ACs"],
  "patches": [
    {
      "path": "specs/product-spec.md",
      "content": "FULL updated file content (100% English, preserve existing sections)",
      "rationale": "Why this spec edit is needed"
    }
  ]
}
""".strip(),
    "architect": """
Return ONLY a valid JSON object with keys:
{
  "summary": "1-3 sentences covering contract, data model, and expand-only migration plan",
  "migration_notes": "Expand-Migrate-Contract notes or 'No DB schema changes'",
  "issue_draft": {
    "title": "[F-NEW] Short imperative title",
    "labels": ["agent:backend", "type:feature"],
    "body": "Task markdown (Summary, Spec reference, AC checkboxes, Test plan, Out of scope)"
  },
  "patches": [
    {
      "path": "specs/api/openapi.yaml or specs/tasks.md or specs/data-model.md",
      "content": "FULL updated file content (100% English)",
      "rationale": "Contract/task alignment"
    }
  ]
}
""".strip(),
    "tdd_tests": """
Write FAILING tests FIRST covering every new Acceptance Criterion
(backend pytest unit/integration and/or frontend Vitest/RTL).
Never invent production application files in this stage — tests only!
Return ONLY a valid JSON object with keys:
{
  "summary": "Tests written and which ACs they verify",
  "patches": [
    {
      "path": "backend/tests/... or frontend/src/...test.tsx",
      "content": "FULL file content (100% English, deterministic, no real PII)",
      "rationale": "AC test coverage"
    }
  ]
}
""".strip(),
    "implement": """
Write minimal clean production code to pass TDD tests matching specs/api/openapi.yaml & AGENTS.md:
- backend/app/domain/ MUST NOT import sqlalchemy or fastapi; use integer minutes since midnight.
- No PII in spans, metrics, or logs.
- Frontend uses openapi-fetch types (npm run gen:api).
- Never add features unrelated to the approved spec.
Return ONLY a valid JSON object with keys:
{
  "summary": "Implementation overview across backend and/or frontend",
  "patches": [
    {
      "path": "backend/app/... or frontend/src/...",
      "content": "FULL updated file content (100% English)",
      "rationale": "Minimal code satisfying failing TDD tests"
    }
  ]
}
""".strip(),
    "fix_failure": """
Analyze the failing lint/test/hygiene output and propose the smallest targeted patch
to make the suite pass without deleting or skipping tests.
Return ONLY a valid JSON object with keys:
{
  "summary": "Root cause and minimal fix",
  "patches": [
    {
      "path": "repo-relative path",
      "content": "FULL fixed file content (100% English)",
      "rationale": "Fix root cause"
    }
  ]
}
""".strip(),
    "review": """
Audit the changes strictly against .agents/roles/reviewer.md 10-point checklist.
Return ONLY a valid JSON object with keys:
{
  "verdict": "approve" | "request_changes",
  "blocking": ["file:line violation description"],
  "non_blocking": ["optional polish items"],
  "summary": "Concise review summary"
}
""".strip(),
}


def build_prompts_for_stage(
    repo_root: Path,
    run: RunState,
    stage: StageName,
    *,
    guidance: str = "",
    failing_output: str = "",
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the requested AI SDLC stage."""
    role = STAGE_TO_ROLE[stage]
    role_prompt = read_role_prompt(repo_root, role)
    repo_ctx = build_stage_context(repo_root, stage)

    system_prompt = (
        f"You are executing SessionBoard AI SDLC stage '{stage}'.\n"
        f"Enforce 100% English-only output across all text and code.\n\n"
        f"{role_prompt}\n\n"
        f"{STAGE_OUTPUT_SCHEMAS[stage]}"
    )

    prior_state = {
        "run_title": run.title,
        "feature_request": run.prompt,
        "spec_approved": run.spec_approved,
        "issue_number": run.issue_number,
        "intake": run.intake,
        "spec_summary": run.spec.get("summary") if run.spec else None,
        "spec_markdown": run.spec.get("spec_markdown") if run.spec else None,
        "architect_summary": run.architect.get("summary") if run.architect else None,
        "tdd_tests_summary": run.tdd_tests.get("summary") if run.tdd_tests else None,
        "latest_gates": [g.model_dump() for g in run.gate_results[-6:]],
    }

    extra_blocks = []
    if guidance.strip():
        extra_blocks.append(f"Human guidance / clarifications:\n{guidance.strip()}")
    if failing_output.strip():
        extra_blocks.append(f"Failing command output:\n{failing_output.strip()[:6000]}")
    extra_text = "\n\n".join(extra_blocks) if extra_blocks else "(none)"

    user_prompt = (
        f"[STAGE:{stage}]\n\n"
        f"=== Current Run State ===\n{json.dumps(prior_state, indent=2)}\n\n"
        f"=== Stage Specific Instructions ===\n{extra_text}\n\n"
        f"=== Repository Ground Truth ===\n{repo_ctx}"
    )
    return system_prompt, user_prompt
