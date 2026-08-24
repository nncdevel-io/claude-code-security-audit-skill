"""プラグイン定義と scripts/package.sh のテスト。"""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package.sh"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_NAME = "claude-code-security-audit"
SKILL_DIR_NAME = "security-audit"


def read_json(path: Path) -> dict:
    """JSON ファイルを読む。"""
    return json.loads(path.read_text(encoding="utf-8"))


def run_package(*arguments: str) -> subprocess.CompletedProcess[str]:
    """package.sh を実行する。"""
    return subprocess.run(
        ["bash", str(PACKAGE_SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        env=dict(os.environ),
    )


def test_plugin_manifest_declares_name_version_and_description() -> None:
    manifest = read_json(PLUGIN_MANIFEST)

    assert manifest["name"] == PLUGIN_NAME
    assert manifest["version"]
    assert manifest["description"]


def test_plugin_ships_the_skill_directory_it_declares() -> None:
    assert (REPO_ROOT / "skills" / SKILL_DIR_NAME / "SKILL.md").is_file()


def test_marketplace_manifest_lists_the_plugin_from_the_repository_root() -> None:
    marketplace = read_json(MARKETPLACE_MANIFEST)

    assert marketplace["owner"]["name"]
    assert [plugin["name"] for plugin in marketplace["plugins"]] == [PLUGIN_NAME]
    assert marketplace["plugins"][0]["source"].startswith("./")


def test_marketplace_name_is_not_a_reserved_anthropic_name() -> None:
    reserved = {
        "claude-code-marketplace",
        "claude-code-plugins",
        "claude-plugins-official",
        "claude-plugins-community",
        "anthropic-marketplace",
        "anthropic-plugins",
    }

    assert read_json(MARKETPLACE_MANIFEST)["name"] not in reserved


def test_package_creates_an_archive_named_after_the_plugin_version(
    tmp_path: Path,
) -> None:
    version = read_json(PLUGIN_MANIFEST)["version"]

    result = run_package("--output", str(tmp_path), "--skip-check")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / f"{PLUGIN_NAME}-{version}.zip").is_file()


def test_package_archive_contains_the_manifests_skill_and_baseline(
    tmp_path: Path,
) -> None:
    version = read_json(PLUGIN_MANIFEST)["version"]

    run_package("--output", str(tmp_path), "--skip-check")

    with zipfile.ZipFile(tmp_path / f"{PLUGIN_NAME}-{version}.zip") as archive:
        names = set(archive.namelist())
    assert f"{PLUGIN_NAME}/.claude-plugin/plugin.json" in names
    assert f"{PLUGIN_NAME}/skills/{SKILL_DIR_NAME}/SKILL.md" in names
    assert f"{PLUGIN_NAME}/skills/{SKILL_DIR_NAME}/scripts/collect_config.py" in names
    assert f"{PLUGIN_NAME}/skills/{SKILL_DIR_NAME}/references/requirements.md" in names


def test_package_archive_excludes_python_cache_and_generation_side_files(
    tmp_path: Path,
) -> None:
    version = read_json(PLUGIN_MANIFEST)["version"]

    run_package("--output", str(tmp_path), "--skip-check")

    with zipfile.ZipFile(tmp_path / f"{PLUGIN_NAME}-{version}.zip") as archive:
        names = archive.namelist()
    assert [name for name in names if "__pycache__" in name] == []
    assert [name for name in names if "baseline/" in name] == []


def test_package_leaves_no_staging_directory_behind(tmp_path: Path) -> None:
    run_package("--output", str(tmp_path), "--skip-check")

    assert [path.name for path in tmp_path.iterdir() if path.is_dir()] == []


def test_package_rejects_an_unknown_argument(tmp_path: Path) -> None:
    result = run_package("--output", str(tmp_path), "--unknown")

    assert result.returncode != 0
    assert "Usage" in result.stderr
