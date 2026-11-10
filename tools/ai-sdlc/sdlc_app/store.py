"""Git-ignored persistent file storage for AI SDLC pipeline runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sdlc_app.schemas import PipelineRunSummary, RunState


class RunStore:
    """Stores RunState JSON snapshots under .local/ai-sdlc/runs/."""

    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, run_id: str) -> Path:
        safe_id = "".join(ch for ch in run_id if ch.isalnum() or ch in ("-", "_"))
        if not safe_id:
            raise ValueError("Invalid run id.")
        return self.runs_dir / f"{safe_id}.json"

    def save(self, run: RunState) -> RunState:
        run.updated_at = datetime.now(UTC).isoformat()
        target = self._path_for(run.id)
        tmp_path = target.with_suffix(".tmp")
        tmp_path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(target)
        return run

    def get(self, run_id: str) -> RunState | None:
        target = self._path_for(run_id)
        if not target.is_file():
            return None
        return RunState.model_validate_json(target.read_text(encoding="utf-8"))

    def list_summaries(self) -> list[PipelineRunSummary]:
        items: list[RunState] = []
        for path in self.runs_dir.glob("*.json"):
            try:
                items.append(RunState.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        items.sort(key=lambda r: r.updated_at, reverse=True)
        return [
            PipelineRunSummary(
                id=r.id,
                title=r.title,
                created_at=r.created_at,
                updated_at=r.updated_at,
                current_stage=r.current_stage,
                spec_approved=r.spec_approved,
                issue_number=r.issue_number,
                branch_name=r.branch_name,
                pr_url=r.pr_url,
            )
            for r in items
        ]

    def load_raw_dict(self, run_id: str) -> dict | None:
        target = self._path_for(run_id)
        if not target.is_file():
            return None
        return json.loads(target.read_text(encoding="utf-8"))
