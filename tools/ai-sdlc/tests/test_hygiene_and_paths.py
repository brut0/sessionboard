"""Unit tests for path containment and repository hygiene guards."""

from pathlib import Path

import pytest

from sdlc_app.hygiene import HygieneViolationError, validate_patch_target, validate_text_hygiene


def test_validate_patch_target_allows_repo_relative_paths(tmp_path: Path) -> None:
    resolved = validate_patch_target(tmp_path, "specs/product-spec.md")
    assert resolved == (tmp_path / "specs" / "product-spec.md").resolve()


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.txt",
        "/etc/passwd",
        ".git/config",
        ".local/forbidden-terms.txt",
        "tools/ai-sdlc/.venv/lib.py",
        ".env",
        ".env.local",
        "backend/app/static/index.html",
        "node_modules/pkg/index.js",
        "",
    ],
)
def test_validate_patch_target_rejects_unsafe_paths(tmp_path: Path, bad_path: str) -> None:
    with pytest.raises(HygieneViolationError):
        validate_patch_target(tmp_path, bad_path)


def test_validate_text_hygiene_blocks_cyrillic_without_literal_in_source() -> None:
    # Construct Cyrillic string via Unicode escapes so repo hygiene stays 100% ASCII/English.
    non_english = "\u041f\u0440\u0438\u0432\u0435\u0442"
    with pytest.raises(HygieneViolationError, match="Cyrillic"):
        validate_text_hygiene(f"title = '{non_english}'", rel_path="backend/app/schemas.py")


def test_validate_text_hygiene_blocks_custom_forbidden_regex(tmp_path: Path) -> None:
    local_dir = tmp_path / ".local"
    local_dir.mkdir()
    (local_dir / "forbidden-terms.txt").write_text(
        "# comment\nforbidden_studio_token\n",
        encoding="utf-8",
    )

    with pytest.raises(HygieneViolationError, match="forbidden pattern"):
        validate_text_hygiene(
            "name = 'FORBIDDEN_STUDIO_TOKEN'",
            rel_path="specs/product-spec.md",
            repo_root=tmp_path,
        )


def test_validate_text_hygiene_allows_clean_english(tmp_path: Path) -> None:
    validate_text_hygiene(
        "SessionBoard daily session scheduler check.",
        rel_path="docs/ai-sdlc.md",
        repo_root=tmp_path,
    )
