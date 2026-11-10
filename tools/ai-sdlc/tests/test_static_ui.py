"""Tests for serving the companion AI SDLC static Web UI."""

from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_app.config import WorkbenchSettings
from sdlc_app.main import create_app


def test_root_serves_accessible_workbench_html(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    client = TestClient(create_app(settings=WorkbenchSettings(repo_root=tmp_path)))

    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text
    assert '<html lang="en">' in html
    assert '<meta name="color-scheme" content="light dark">' in html
    assert 'href="#main-content"' in html
    assert "SessionBoard AI SDLC Workbench" in html

    css = client.get("/static/styles.css")
    assert css.status_code == 200

    js = client.get("/static/app.js")
    assert js.status_code == 200
