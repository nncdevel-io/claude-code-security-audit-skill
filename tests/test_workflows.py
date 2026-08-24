"""GitHub Actions ワークフロー定義のテスト。"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOW_DIR / "ci.yml"
BASELINE_WORKFLOW = WORKFLOW_DIR / "baseline-update.yml"
PACKAGE_WORKFLOW = WORKFLOW_DIR / "package.yml"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"

# YAML 1.1 では裸の `on` が真偽値 True として読まれる。
ON_KEY = True


def load_workflow(path: Path) -> dict[str, Any]:
    """ワークフロー定義を読み込む。"""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def collect_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """全ジョブのステップを平坦化して返す。"""
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


@pytest.mark.parametrize("path", [CI_WORKFLOW, BASELINE_WORKFLOW, PACKAGE_WORKFLOW])
def test_workflow_is_valid_yaml(path: Path) -> None:
    assert isinstance(load_workflow(path), dict)


@pytest.mark.parametrize("path", [CI_WORKFLOW, BASELINE_WORKFLOW, PACKAGE_WORKFLOW])
def test_every_action_reference_is_version_pinned(path: Path) -> None:
    unpinned = [
        step["uses"]
        for step in collect_steps(load_workflow(path))
        if "@" not in step.get("uses", "@")
    ]

    assert unpinned == []


def test_ci_workflow_runs_the_single_verification_entry_point() -> None:
    commands = [
        step.get("run", "") for step in collect_steps(load_workflow(CI_WORKFLOW))
    ]

    assert any("scripts/verify.sh" in command for command in commands)


def test_baseline_workflow_runs_on_demand_only() -> None:
    """定期実行は当面止めてあり、手動起動だけを受け付ける。"""
    triggers = load_workflow(BASELINE_WORKFLOW)[ON_KEY]

    assert "workflow_dispatch" in triggers
    assert "schedule" not in triggers


def test_baseline_workflow_authenticates_with_the_subscription_token() -> None:
    steps = collect_steps(load_workflow(BASELINE_WORKFLOW))
    claude_steps = [
        step for step in steps if step.get("uses", "").startswith("anthropics/")
    ]

    assert len(claude_steps) == 1
    inputs = claude_steps[0]["with"]
    assert "claude_code_oauth_token" in inputs
    assert "anthropic_api_key" not in inputs


def test_baseline_workflow_regenerates_only_after_a_detected_change() -> None:
    steps = collect_steps(load_workflow(BASELINE_WORKFLOW))
    guarded = [step for step in steps if "changed == 'true'" in str(step.get("if", ""))]

    assert [step.get("name") for step in guarded] == [
        "Update the snapshot",
        "Regenerate the baseline with Claude",
        "Validate the regenerated baseline",
        "Open a pull request",
    ]


def test_baseline_workflow_validates_before_opening_a_pull_request() -> None:
    names = [
        step.get("name") for step in collect_steps(load_workflow(BASELINE_WORKFLOW))
    ]

    assert names.index("Validate the regenerated baseline") < names.index(
        "Open a pull request"
    )


def test_baseline_workflow_limits_the_pull_request_to_generated_files() -> None:
    steps = collect_steps(load_workflow(BASELINE_WORKFLOW))
    pull_request = next(
        step for step in steps if step.get("uses", "").startswith("peter-evans/")
    )

    assert sorted(pull_request["with"]["add-paths"].split()) == [
        "baseline/security.md",
        "skills/security-audit/references/requirements.md",
    ]


def find_step(workflow: dict[str, Any], name: str) -> dict[str, Any]:
    """名前でステップを引く。"""
    return next(step for step in collect_steps(workflow) if step.get("name") == name)


def test_baseline_workflow_change_detection_step_publishes_step_outputs(
    tmp_path: Path,
) -> None:
    """取得ステップのシェル処理を定義のまま実行し、出力の受け渡しを確認する。"""
    report = {
        "url": "https://code.claude.com/docs/en/security.md",
        "retrieved_at": "2026-08-21",
        "content_sha256": "0" * 64,
        "baseline_version": "2026-08-21-00000000",
        "changed": True,
        "snapshot_path": "baseline/security.md",
    }
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        f"#!/usr/bin/env bash\ncat <<'JSON'\n{json.dumps(report)}\nJSON\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    github_output = tmp_path / "github-output"
    run_script = find_step(
        load_workflow(BASELINE_WORKFLOW), "Check the upstream document for changes"
    )["run"]

    result = subprocess.run(
        ["bash", "-c", run_script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(github_output),
        },
    )

    assert result.returncode == 0, result.stderr
    assert github_output.read_text(encoding="utf-8").splitlines() == [
        "changed=true",
        "baseline_version=2026-08-21-00000000",
    ]


def test_windows_powershell_step_does_not_branch_on_lastexitcode() -> None:
    """直接呼び出した .ps1 は $LASTEXITCODE を設定しない。

    未設定の $LASTEXITCODE は $null で、`$null -ne 0` は真になる。判定を置くと
    収集が成功しても必ず exit 1 になり、ジョブが常に落ちる。失敗の検知は
    スクリプト内の $ErrorActionPreference = 'Stop' が送出する例外に任せる。
    """
    steps = [
        step
        for step in collect_steps(load_workflow(CI_WORKFLOW))
        if step.get("shell") == "powershell"
    ]

    assert steps
    assert [step for step in steps if "$LASTEXITCODE" in step.get("run", "")] == []


def plugin_version() -> str:
    """配布物に付くバージョンを返す。"""
    return json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))["version"]


def test_package_workflow_is_triggered_only_by_tag_pushes() -> None:
    triggers = load_workflow(PACKAGE_WORKFLOW)[ON_KEY]

    assert list(triggers) == ["push"]
    assert triggers["push"]["tags"] == ["v*"]


def test_package_workflow_builds_with_the_verification_included() -> None:
    """package.sh は既定で verify.sh を通す。--skip-check を渡してはならない。"""
    commands = [
        step.get("run", "") for step in collect_steps(load_workflow(PACKAGE_WORKFLOW))
    ]

    assert any("scripts/package.sh" in command for command in commands)
    assert [command for command in commands if "--skip-check" in command] == []


def test_package_workflow_uploads_the_archive_named_after_the_version() -> None:
    step = find_step(load_workflow(PACKAGE_WORKFLOW), "Upload the distribution archive")

    assert step["uses"].startswith("actions/upload-artifact@")
    assert "${{ steps.version.outputs.version }}" in step["with"]["name"]
    assert "${{ steps.version.outputs.version }}" in step["with"]["path"]
    assert step["with"]["if-no-files-found"] == "error"


def run_tag_check(
    tag: str, tmp_path: Path
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """タグ照合ステップのシェル処理を定義のまま実行する。"""
    github_output = tmp_path / "github-output"
    github_output.touch()
    run_script = find_step(
        load_workflow(PACKAGE_WORKFLOW), "Check the tag against the plugin version"
    )["run"]

    result = subprocess.run(
        ["bash", "-c", run_script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "TAG_NAME": tag,
            "GITHUB_OUTPUT": str(github_output),
        },
    )
    return result, github_output


def test_package_workflow_publishes_the_version_when_the_tag_matches(
    tmp_path: Path,
) -> None:
    version = plugin_version()

    result, github_output = run_tag_check(f"v{version}", tmp_path)

    assert result.returncode == 0, result.stderr
    assert github_output.read_text(encoding="utf-8").splitlines() == [
        f"version={version}"
    ]


def test_package_workflow_stops_when_the_tag_disagrees_with_the_version(
    tmp_path: Path,
) -> None:
    """タグと配布物のバージョンがずれたまま配ると、誤った版が出回る。"""
    result, _ = run_tag_check("v0.0.0", tmp_path)

    assert result.returncode != 0
    assert plugin_version() in result.stderr
