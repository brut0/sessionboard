"""TDD tests for fail-closed owner authentication, security headers, and workspace bootstrap."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from sdlc_app.bootstrap import bootstrap_workspace, sanitize_secrets
from sdlc_app.config import WorkbenchSettings
from sdlc_app.main import create_app


def _seed_mini_repo(repo_root: Path) -> None:
    (repo_root / "AGENTS.md").write_text("# AGENTS\nEnglish only.\n", encoding="utf-8")
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "constitution.md").write_text("# Constitution\n", encoding="utf-8")


def test_fail_closed_when_auth_required_and_password_missing_or_short(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)

    for bad_pw, env, render in [
        ("", "local", ""),
        ("too-short", "local", ""),
        ("", "prod", ""),
        ("", "local", "true"),
    ]:
        settings = WorkbenchSettings(
            repo_root=tmp_path,
            require_auth=True if (env == "local" and not render) else False,
            app_env=env,
            render_env=render,
            owner_password=bad_pw,
        )
        client = TestClient(create_app(settings=settings))

        # Minimal unauthenticated health & session check succeed without leaking metadata
        health = client.get("/api/health")
        assert health.status_code == 200
        h_body = health.json()
        assert h_body["auth_required"] is True
        assert h_body["auth_configured"] is False
        assert h_body["authenticated"] is False
        assert h_body["repo_root"] is None
        assert h_body["git_branch"] is None
        assert h_body["gh_authenticated"] is None
        assert h_body["gemini_cli_available"] is None

        sess = client.get("/api/auth/session")
        assert sess.status_code == 200
        assert sess.json() == {
            "auth_required": True,
            "configured": False,
            "authenticated": False,
        }

        # Every functional endpoint fails closed with 503
        for method, path in [
            ("GET", "/api/config"),
            ("GET", "/api/runs"),
            ("GET", "/api/stages"),
            ("GET", "/api/git-status"),
            ("POST", "/api/runs"),
            ("POST", "/api/auth/login"),
        ]:
            res = client.request(method, path, json={"password": bad_pw or "x"})
            assert res.status_code == 503, f"Expected 503 on {method} {path}, got {res.status_code}"


def test_owner_login_cookie_lifecycle_and_fail_closed_routes(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)
    secret_pw = "owner-strong-passphrase-2026"
    settings = WorkbenchSettings(
        repo_root=tmp_path,
        require_auth=True,
        owner_password=secret_pw,
        session_secret="signing-secret-material-xyz-987654",
        gemini_api_key="AIzaOwnerSecretKey123456",
    )
    client = TestClient(create_app(settings=settings))

    # 1. Unauthenticated API & OpenAPI docs are blocked with 401
    for path in (
        "/api/config",
        "/api/runs",
        "/api/stages",
        "/api/git-status",
        "/openapi.json",
        "/docs",
        "/redoc",
    ):
        resp = client.get(path)
        assert resp.status_code == 401, f"Expected 401 on {path}, got {resp.status_code}"

    # 2. Health leaks zero repo paths/branch/key info while unauthenticated
    health_anon = client.get("/api/health")
    assert health_anon.status_code == 200
    assert health_anon.json()["auth_required"] is True
    assert health_anon.json()["auth_configured"] is True
    assert health_anon.json()["authenticated"] is False
    assert health_anon.json()["repo_root"] is None
    assert str(tmp_path) not in health_anon.text

    # 3. Wrong password returns 401
    bad_login = client.post("/api/auth/login", json={"password": "wrong-password-attempt"})
    assert bad_login.status_code == 401

    # 4. Valid password returns 200 and sets HttpOnly SameSite=Lax cookie
    good_login = client.post("/api/auth/login", json={"password": secret_pw})
    assert good_login.status_code == 200
    assert good_login.json()["authenticated"] is True
    set_cookie = good_login.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()

    # 5. Authenticated requests succeed
    sess = client.get("/api/auth/session")
    assert sess.status_code == 200
    assert sess.json()["authenticated"] is True

    cfg = client.get("/api/config")
    assert cfg.status_code == 200
    assert cfg.json()["masked_key"] == "AIza...3456"

    health_authed = client.get("/api/health")
    assert health_authed.status_code == 200
    assert health_authed.json()["authenticated"] is True
    assert health_authed.json()["repo_root"] == str(tmp_path.resolve())

    # 6. Cross-site mutating request blocked by Fetch Metadata policy
    csrf_attempt = client.put(
        "/api/config",
        json={"llm_model": "evil-model"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert csrf_attempt.status_code == 403

    # 7. Saving config never persists auth credentials to disk
    save_cfg = client.put("/api/config", json={"llm_model": "gemini-2.5-flash"})
    assert save_cfg.status_code == 200
    saved_text = settings.runtime_config_file.read_text(encoding="utf-8")
    assert secret_pw not in saved_text
    assert "signing-secret-material" not in saved_text
    assert "owner_password" not in json.loads(saved_text)

    # 8. Logout invalidates cookie & sends Clear-Site-Data
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert "cookies" in logout.headers.get("clear-site-data", "").lower()
    assert client.get("/api/config").status_code == 401


def test_https_sets_host_prefixed_secure_cookie_and_supports_bearer_auth(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)
    secret_pw = "https-owner-passphrase-2026"
    settings = WorkbenchSettings(
        repo_root=tmp_path,
        app_env="prod",
        owner_password=secret_pw,
    )
    app = create_app(settings=settings)
    https_client = TestClient(app, base_url="https://sessionboard-ai-sdlc.onrender.com")

    login = https_client.post("/api/auth/login", json={"password": secret_pw})
    assert login.status_code == 200
    cookie_header = login.headers.get("set-cookie", "")
    assert "__Host-sdlc_session=" in cookie_header
    assert "; secure" in cookie_header.lower()
    assert "; httponly" in cookie_header.lower()

    assert https_client.get("/api/runs").status_code == 200

    # Tampered cookie rejected
    tampered_client = TestClient(app, base_url="https://sessionboard-ai-sdlc.onrender.com")
    tampered_client.cookies.set("__Host-sdlc_session", "9999999999.nonce.invalidsig")
    assert tampered_client.get("/api/runs").status_code == 401

    # Bearer token works cleanly for automation without cookies
    bearer_client = TestClient(app, base_url="https://sessionboard-ai-sdlc.onrender.com")
    res = bearer_client.get("/api/runs", headers={"Authorization": f"Bearer {secret_pw}"})
    assert res.status_code == 200


def test_login_rate_limits_after_repeated_failures(tmp_path: Path) -> None:
    _seed_mini_repo(tmp_path)
    secret_pw = "rate-limit-passphrase-9999"
    settings = WorkbenchSettings(
        repo_root=tmp_path,
        require_auth=True,
        owner_password=secret_pw,
    )
    client = TestClient(create_app(settings=settings))

    for _ in range(5):
        res = client.post("/api/auth/login", json={"password": "wrong-attempt-value"})
        assert res.status_code == 401

    locked = client.post("/api/auth/login", json={"password": secret_pw})
    assert locked.status_code == 429
    assert "retry-after" in {k.lower(): v for k, v in locked.headers.items()}


def test_sanitize_secrets_and_workspace_bootstrap_never_leaks_tokens(tmp_path: Path) -> None:
    raw = (
        "fatal: could not read https://ghp_1234567890abcdef@github.com/brut0/sessionboard.git "
        "token=github_pat_ABC123456 key=AIzaSyTestSecret9999 pw=my-owner-secret"
    )
    cleaned = sanitize_secrets(raw, extra_secrets=["my-owner-secret"])
    assert "ghp_1234567890abcdef" not in cleaned
    assert "github_pat_ABC123456" not in cleaned
    assert "AIzaSyTestSecret9999" not in cleaned
    assert "my-owner-secret" not in cleaned

    # Create a real local bare repo + seed commit to test genuine git clone bootstrap
    work_seed = tmp_path / "seed_src"
    bare_origin = tmp_path / "origin.git"
    work_seed.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=work_seed, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Tester"], cwd=work_seed, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"],
        cwd=work_seed,
        check=True,
        capture_output=True,
    )
    (work_seed / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    subprocess.run(["git", "add", "AGENTS.md"], cwd=work_seed, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--no-gpg-sign", "-m", "init"],
        cwd=work_seed,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clone", "--bare", str(work_seed), str(bare_origin)],
        check=True,
        capture_output=True,
    )

    # Embedded credential URL MUST be rejected
    bad_target = tmp_path / "bad_ws"
    res_bad = bootstrap_workspace(
        bad_target,
        clone_repo_url="https://ghp_secretToken@github.com/brut0/sessionboard.git",
    )
    assert res_bad["ok"] is False
    assert not (bad_target / ".git").exists()

    # Clean URL clones safely and configures non-interactive git defaults
    target_ws = tmp_path / "workspace"
    res_ok = bootstrap_workspace(target_ws, clone_repo_url=str(bare_origin))
    assert res_ok["ok"] is True
    assert (target_ws / ".git").is_dir()
    assert (target_ws / "AGENTS.md").is_file()
    git_cfg = (target_ws / ".git" / "config").read_text(encoding="utf-8")
    assert "ghp_" not in git_cfg

    # Verify create_app() runs bootstrap_workspace end-to-end and surfaces failures as degraded
    boot_ws = tmp_path / "app_boot_ws"
    app_ok = create_app(
        settings=WorkbenchSettings(
            repo_root=boot_ws,
            clone_repo_url=str(bare_origin),
            app_version="abc1234",
        )
    )
    ok_client = TestClient(app_ok)
    h_ok = ok_client.get("/api/health").json()
    assert h_ok["status"] == "ok"
    assert h_ok["workspace_ready"] is True
    assert h_ok["version"] == "abc1234"
    assert (boot_ws / "AGENTS.md").is_file()

    degraded_app = create_app(
        settings=WorkbenchSettings(
            repo_root=tmp_path / "degraded_ws",
            clone_repo_url="https://ghp_secret@github.com/brut0/sessionboard.git",
        )
    )
    h_deg = TestClient(degraded_app).get("/api/health").json()
    assert h_deg["status"] == "degraded"
    assert h_deg["workspace_ready"] is False


def test_render_proxy_xff_spoof_uses_rightmost_hop(tmp_path: Path, monkeypatch) -> None:
    _seed_mini_repo(tmp_path)
    monkeypatch.setenv("RENDER", "true")
    secret_pw = "render-xff-owner-pass-2026"
    client = TestClient(
        create_app(settings=WorkbenchSettings(repo_root=tmp_path, owner_password=secret_pw))
    )

    # Spoof leftmost XFF entries per attempt while the rightmost proxy hop stays constant
    for idx in range(5):
        res = client.post(
            "/api/auth/login",
            json={"password": "wrong-password-guess"},
            headers={"X-Forwarded-For": f"10.0.0.{idx}, 203.0.113.50"},
        )
        assert res.status_code == 401

    blocked = client.post(
        "/api/auth/login",
        json={"password": secret_pw},
        headers={"X-Forwarded-For": "198.51.100.99, 203.0.113.50"},
    )
    assert blocked.status_code == 429
