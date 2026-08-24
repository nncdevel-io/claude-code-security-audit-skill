"""scripts/install.sh のテスト。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install.sh"
SKILL_NAME = "security-audit"


def run_install(
    *arguments: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """install.sh を実行する。"""
    return subprocess.run(
        ["bash", str(INSTALL_SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


def test_install_copies_the_skill_into_the_target(tmp_path: Path) -> None:
    result = run_install("--target", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / SKILL_NAME / "SKILL.md").is_file()
    assert (tmp_path / SKILL_NAME / "scripts" / "collect_config.py").is_file()
    assert (tmp_path / SKILL_NAME / "references" / "requirements.md").is_file()


def test_install_prints_the_destination(tmp_path: Path) -> None:
    result = run_install("--target", str(tmp_path))

    assert str(tmp_path / SKILL_NAME) in result.stdout


def test_install_excludes_python_cache_directories(tmp_path: Path) -> None:
    run_install("--target", str(tmp_path))

    assert list((tmp_path / SKILL_NAME).rglob("__pycache__")) == []


def test_install_creates_a_symlink_with_link_option(tmp_path: Path) -> None:
    result = run_install("--target", str(tmp_path), "--link")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / SKILL_NAME).is_symlink()


def test_install_refuses_to_replace_an_existing_skill(tmp_path: Path) -> None:
    run_install("--target", str(tmp_path))

    result = run_install("--target", str(tmp_path))

    assert result.returncode != 0
    assert "--force" in result.stderr


def test_install_replaces_an_existing_skill_with_force(tmp_path: Path) -> None:
    run_install("--target", str(tmp_path))
    (tmp_path / SKILL_NAME / "stale.md").write_text("古い成果物", encoding="utf-8")

    result = run_install("--target", str(tmp_path), "--force")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / SKILL_NAME / "stale.md").exists() is False


def test_install_uses_the_claude_skills_dir_environment_variable(
    tmp_path: Path,
) -> None:
    result = run_install(env={"CLAUDE_SKILLS_DIR": str(tmp_path)})

    assert result.returncode == 0, result.stderr
    assert (tmp_path / SKILL_NAME / "SKILL.md").is_file()


def test_install_creates_the_target_directory_when_missing(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "skills"

    result = run_install("--target", str(target))

    assert result.returncode == 0, result.stderr
    assert (target / SKILL_NAME / "SKILL.md").is_file()


def test_install_rejects_an_unknown_argument(tmp_path: Path) -> None:
    result = run_install("--target", str(tmp_path), "--unknown")

    assert result.returncode != 0
    assert "Usage" in result.stderr
