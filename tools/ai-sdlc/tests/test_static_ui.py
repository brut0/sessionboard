"""Tests for serving the companion AI SDLC static Web UI and security headers."""

from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_app.config import WorkbenchSettings
from sdlc_app.main import create_app


def test_root_serves_accessible_workbench_html_and_security_headers(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    client = TestClient(create_app(settings=WorkbenchSettings(repo_root=tmp_path)))

    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in res.headers.get("content-security-policy", "")

    html = res.text
    assert '<html lang="en">' in html
    assert '<meta name="color-scheme" content="light dark">' in html
    assert 'href="#main-content"' in html
    assert "SessionBoard AI SDLC Workbench" in html
    assert 'id="auth-gate"' in html
    assert 'id="owner-login-form"' in html
    assert 'autocomplete="username"' in html
    assert 'autocomplete="current-password"' in html
    assert 'id="toggle-login-password"' in html
    assert 'id="logout-btn"' in html

    css = client.get("/static/styles.css")
    assert css.status_code == 200

    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "e.currentTarget.reset()" not in js.text
    assert "const form = e.currentTarget;" in js.text
    assert "form.reset();" in js.text
