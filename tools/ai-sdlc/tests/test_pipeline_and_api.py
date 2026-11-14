"""Integration tests for FastAPI AI SDLC workbench API and SDD/TDD state guards."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_app.config import WorkbenchSettings
from sdlc_app.main import create_app


class FakeLLMClient:
    """Deterministic fake LLM client for offline pipeline testing."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        for key, payload in self.responses.items():
            if key in user_prompt:
                return json.dumps(payload)
        return json.dumps({"summary": "default response", "patches": []})


def _seed_mini_repo(repo_root: Path) -> None:
    (repo_root / "AGENTS.md").write_text("# AGENTS\nEnglish only.\n", encoding="utf-8")
    (repo_root / "specs" / "api").mkdir(parents=True)
    (repo_root / "specs" / "constitution.md").write_text("# Constitution\n", encoding="utf-8")
    (repo_root / "specs" / "product-spec.md").write_text(
        "# Product Spec\n## 7. Non-Goals\n- No pricing\n",
        encoding="utf-8",
    )
    (repo_root / "specs" / "data-model.md").write_text("# Data Model\n", encoding="utf-8")
    (repo_root / "specs" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (repo_root / "specs" / "api" / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    (repo_root / "docs").mkdir(parents=True)
    (repo_root / "docs" / "architecture.md").write_text("# Arch\n", encoding="utf-8")
    (repo_root / ".agents" / "roles").mkdir(parents=True)
    for role in ("spec", "architect", "backend", "frontend", "qa", "reviewer"):
        (repo_root / ".agents" / "roles" / f"{role}.md").write_text(
            f"# Role: {role}\n", encoding="utf-8"
        )


def test_health_and_config_mask_secrets(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)
    settings = WorkbenchSettings(
        repo_root=tmp_path,
        gemini_api_key="AIzaSuperSecret9876",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
    )
    client = TestClient(create_app(settings=settings))

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    stages = client.get("/api/stages")
    assert stages.status_code == 200
    assert [s["stage"] for s in stages.json()][0] == "intake"

    cfg = client.get("/api/config")
    assert cfg.status_code == 200
    body = cfg.json()
    assert body["has_api_key"] is True
    assert "AIzaSuperSecret9876" not in json.dumps(body)
    assert body["masked_key"] == "AIza...9876"


def test_sdd_pipeline_enforces_spec_approval_before_architect_and_tdd_patch_apply(
    tmp_path: Path,
) -> None:
    _seed_mini_repo(tmp_path)
    fake_llm = FakeLLMClient(
        {
            "[STAGE:intake]": {
                "in_scope": True,
                "non_goal_conflicts": [],
                "clarifications": ["Should session notes max out at 280 chars?"],
                "suggested_branch": "feat/33-session-notes",
                "summary": "Adding optional short session note fits studio scheduling scope.",
            },
            "[STAGE:spec]": {
                "summary": "Added BR-10 and AC-2.9 for optional session note.",
                "spec_markdown": "## Notes AC-2.9\nOptional note max 280 chars.",
                "clarifications_resolved": ["Max length 280 chars"],
                "patches": [
                    {
                        "path": "specs/product-spec.md",
                        "content": (
                            "# Product Spec\n## 7. Non-Goals\n- No pricing\n"
                            "## AC-2.9 Optional note\n"
                        ),
                        "rationale": "Define AC-2.9 before design",
                    }
                ],
            },
            "[STAGE:architect]": {
                "summary": "Add note field to SessionCreate/Session schema.",
                "migration_notes": "Expand-only nullable varchar(280) column.",
                "issue_draft": {
                    "title": "[F2] Add optional session note",
                    "labels": ["agent:backend", "type:feature"],
                    "body": "Closes AC-2.9",
                },
                "patches": [],
            },
            "[STAGE:tdd_tests]": {
                "summary": "Failing test for AC-2.9 note persistence.",
                "patches": [
                    {
                        "path": "backend/tests/unit/test_note.py",
                        "content": "def test_note_length():\n    assert True\n",
                        "rationale": "TDD red test first",
                    }
                ],
            },
            "[STAGE:review]": {
                "verdict": "approve",
                "blocking": [],
                "non_blocking": ["Add README note"],
                "summary": "All 10 checklist items pass.",
            },
        }
    )

    settings = WorkbenchSettings(repo_root=tmp_path, gemini_api_key="AIzaTest123456")
    assert settings.repo_root == tmp_path
    client = TestClient(create_app(settings=settings, llm_factory=lambda _cfg: fake_llm))

    # 1. Create Run
    create_resp = client.post(
        "/api/runs",
        json={"title": "Optional session note", "prompt": "Add optional note on bookings"},
    )
    assert create_resp.status_code == 201
    run_id = create_resp.json()["id"]

    # 2. Intake Stage
    intake = client.post(f"/api/runs/{run_id}/stages/intake", json={"guidance": ""})
    assert intake.status_code == 200
    assert intake.json()["intake"]["in_scope"] is True

    # 3. Spec-First Gate: Architect / TDD / Implement MUST fail with 409 before spec is approved
    for blocked_stage in ("architect", "tdd_tests", "implement"):
        blocked_resp = client.post(
            f"/api/runs/{run_id}/stages/{blocked_stage}",
            json={"guidance": ""},
        )
        assert blocked_resp.status_code == 409

    # 4. Run Spec Stage & Apply nothing when paths=[] is passed
    spec_res = client.post(f"/api/runs/{run_id}/stages/spec", json={"guidance": "Max 280 chars"})
    assert spec_res.status_code == 200
    assert len(spec_res.json()["pending_patches"]) == 1

    apply_empty = client.post(f"/api/runs/{run_id}/apply", json={"paths": []})
    assert apply_empty.status_code == 200
    assert apply_empty.json()["applied_paths"] == []
    assert "AC-2.9" not in (tmp_path / "specs" / "product-spec.md").read_text()

    apply_spec = client.post(
        f"/api/runs/{run_id}/apply",
        json={"paths": ["specs/product-spec.md"]},
    )
    assert apply_spec.status_code == 200
    assert "AC-2.9 Optional note" in (tmp_path / "specs" / "product-spec.md").read_text()

    # 5. Approve Spec -> Architect now succeeds
    approve = client.post(f"/api/runs/{run_id}/approve-spec")
    assert approve.status_code == 200
    assert approve.json()["spec_approved"] is True

    arch_res = client.post(f"/api/runs/{run_id}/stages/architect", json={"guidance": ""})
    assert arch_res.status_code == 200
    assert arch_res.json()["architect"]["issue_draft"]["title"] == "[F2] Add optional session note"

    # 6. TDD Tests stage -> apply test file cleanly
    tdd_res = client.post(f"/api/runs/{run_id}/stages/tdd_tests", json={"guidance": ""})
    assert tdd_res.status_code == 200
    apply_test = client.post(
        f"/api/runs/{run_id}/apply",
        json={"paths": ["backend/tests/unit/test_note.py"]},
    )
    assert apply_test.status_code == 200
    assert (tmp_path / "backend" / "tests" / "unit" / "test_note.py").exists()

    # 7. Reject applying Cyrillic content cleanly with 422
    bad_apply = client.post(
        f"/api/runs/{run_id}/apply",
        json={
            "custom_patches": [
                {
                    "path": "specs/product-spec.md",
                    "content": "\u041e\u0448\u0438\u0431\u043a\u0430",
                    "rationale": "bad",
                }
            ]
        },
    )
    assert bad_apply.status_code == 422

    # 8. Reviewer stage succeeds with approve verdict
    rev_res = client.post(f"/api/runs/{run_id}/stages/review", json={"guidance": ""})
    assert rev_res.status_code == 200
    assert rev_res.json()["review"]["verdict"] == "approve"


def test_update_config_and_hygiene_gate_execution(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    real_hygiene = Path(__file__).resolve().parents[3] / "scripts" / "check_repo_hygiene.py"
    (scripts_dir / "check_repo_hygiene.py").write_text(
        real_hygiene.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    client = TestClient(create_app(settings=WorkbenchSettings(repo_root=tmp_path)))

    upd = client.put(
        "/api/config",
        json={
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "openai_base_url": "http://localhost:11434/v1",
            "api_key": "sk-updated-secret-9999",
        },
    )
    assert upd.status_code == 200
    assert upd.json()["llm_provider"] == "openai"
    assert upd.json()["masked_key"] == "sk-u...9999"
    assert "sk-updated-secret-9999" not in json.dumps(upd.json())

    run_resp = client.post(
        "/api/runs",
        json={"title": "Check gate runner", "prompt": "Verify hygiene gate inside temp repo"},
    )
    run_id = run_resp.json()["id"]

    gate_resp = client.post(f"/api/runs/{run_id}/gates", json={"gates": ["hygiene"]})
    assert gate_resp.status_code == 200
    results = gate_resp.json()["gate_results"]
    assert len(results) == 1
    assert results[0]["gate"] == "hygiene"
    assert results[0]["passed"] is True
    assert results[0]["exit_code"] == 0


def test_source_context_injection_and_surgical_search_replace_edits(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)
    (tmp_path / "backend" / "app" / "routers").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "routers" / "sessions.py").write_text(
        "def list_sessions():\n    return []\n", encoding="utf-8"
    )
    (tmp_path / "frontend" / "src" / "components").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "App.tsx").write_text(
        "export function App() { return <div>SessionBoard</div>; }\n",
        encoding="utf-8",
    )
    custom_file = tmp_path / "frontend" / "src" / "components" / "BookingModal.tsx"
    custom_file.write_text(
        "// HEADER STAY INTACT\nconst TITLE = 'Book Session';\n// FOOTER STAY INTACT\n",
        encoding="utf-8",
    )

    captured_prompts: list[tuple[str, str]] = []

    class SurgicalEditLLM:
        def complete(self, system_prompt: str, user_prompt: str) -> str:
            captured_prompts.append((system_prompt, user_prompt))
            return json.dumps(
                {
                    "summary": "Updated BookingModal title via surgical search/replace edit.",
                    "patches": [
                        {
                            "path": "frontend/src/components/BookingModal.tsx",
                            "edits": [
                                {
                                    "search": "const TITLE = 'Book Session';",
                                    "replace": "const TITLE = 'Book Studio Session';",
                                }
                            ],
                            "rationale": "Preserve header and footer via surgical edit",
                        }
                    ],
                }
            )

    settings = WorkbenchSettings(repo_root=tmp_path, gemini_api_key="AIzaTest123456")
    client = TestClient(create_app(settings=settings, llm_factory=lambda _cfg: SurgicalEditLLM()))

    create_resp = client.post(
        "/api/runs",
        json={"title": "Surgical UI update", "prompt": "Update BookingModal title safely"},
    )
    assert create_resp.status_code == 201
    run_id = create_resp.json()["id"]
    assert client.post(f"/api/runs/{run_id}/approve-spec").status_code == 200

    impl_resp = client.post(
        f"/api/runs/{run_id}/stages/implement",
        json={
            "guidance": "Use surgical edits",
            "context_files": ["frontend/src/components/BookingModal.tsx"],
        },
    )
    assert impl_resp.status_code == 200
    body = impl_resp.json()

    # Prompt included both backend+frontend roles, file tree, default source files, and target file
    sys_prompt, usr_prompt = captured_prompts[-1]
    assert "# Role: backend" in sys_prompt
    assert "# Role: frontend" in sys_prompt
    assert "=== Repository File Tree ===" in usr_prompt
    assert "backend/app/routers/sessions.py" in usr_prompt
    assert "frontend/src/App.tsx" in usr_prompt
    assert "// HEADER STAY INTACT" in usr_prompt

    patches = body["pending_patches"]
    assert len(patches) == 1
    assert "-const TITLE = 'Book Session';" in patches[0]["diff_preview"]
    assert "+const TITLE = 'Book Studio Session';" in patches[0]["diff_preview"]

    apply_resp = client.post(
        f"/api/runs/{run_id}/apply",
        json={"paths": ["frontend/src/components/BookingModal.tsx"]},
    )
    assert apply_resp.status_code == 200
    updated_text = custom_file.read_text(encoding="utf-8")
    assert "// HEADER STAY INTACT" in updated_text
    assert "const TITLE = 'Book Studio Session';" in updated_text
    assert "// FOOTER STAY INTACT" in updated_text
