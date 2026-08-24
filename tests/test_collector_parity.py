"""collect_config.py と collect_config.ps1 の出力が一致することのテスト。

2 つの実装を持つ以上、片方だけ直して気づかない事態が最大の危険になる。
同じ入力から同じ JSON が出ることを、実行して突き合わせる。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "skills" / "security-audit" / "scripts"
PYTHON_COLLECTOR = SCRIPTS / "collect_config.py"
POWERSHELL_COLLECTOR = SCRIPTS / "collect_config.ps1"

# 実行時刻は毎回変わるので比較から外す。
NON_DETERMINISTIC_KEYS = ("collected_at",)


def find_powershell() -> str | None:
    """利用できる PowerShell を返す。無ければ None。"""
    for name in ("pwsh", "pwsh-preview", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


requires_powershell = pytest.mark.skipif(
    find_powershell() is None,
    reason="PowerShell が無い環境では突き合わせを実行できない",
)


def strip_non_deterministic(payload: dict[str, Any]) -> dict[str, Any]:
    """比較対象から実行ごとに変わる項目を落とす。"""
    return {k: v for k, v in payload.items() if k not in NON_DETERMINISTIC_KEYS}


def run_python_collector(project_dir: Path) -> dict[str, Any]:
    """Python 版を実行して出力を返す。"""
    completed = subprocess.run(
        [sys.executable, str(PYTHON_COLLECTOR), str(project_dir)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ),
    )
    return json.loads(completed.stdout)


def run_powershell_collector(project_dir: Path) -> dict[str, Any]:
    """PowerShell 版を実行して出力を返す。"""
    shell = find_powershell()
    assert shell is not None
    completed = subprocess.run(
        [shell, "-NoProfile", "-File", str(POWERSHELL_COLLECTOR), str(project_dir)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ),
    )
    return json.loads(completed.stdout)


def test_powershell_collector_exists() -> None:
    assert POWERSHELL_COLLECTOR.is_file()


def test_both_collectors_are_shipped_with_the_skill() -> None:
    shipped = sorted(path.name for path in SCRIPTS.iterdir() if path.is_file())

    assert shipped == ["collect_config.ps1", "collect_config.py"]


@requires_powershell
def test_both_implementations_agree_on_the_repository_itself() -> None:
    python_output = run_python_collector(REPO_ROOT)
    powershell_output = run_powershell_collector(REPO_ROOT)

    assert strip_non_deterministic(powershell_output) == strip_non_deterministic(
        python_output
    )


@requires_powershell
def test_both_implementations_agree_on_a_project_without_settings(
    tmp_path: Path,
) -> None:
    python_output = run_python_collector(tmp_path)
    powershell_output = run_powershell_collector(tmp_path)

    assert strip_non_deterministic(powershell_output) == strip_non_deterministic(
        python_output
    )


@requires_powershell
def test_both_implementations_agree_on_a_project_with_settings(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "permissions": {"deny": ["Bash(rm *)"], "allow": ["Bash(ls *)"]},
                "theme": "dark",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "audit.sh"}],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"local": {"command": "node"}}}), encoding="utf-8"
    )

    python_output = run_python_collector(tmp_path)
    powershell_output = run_powershell_collector(tmp_path)

    assert strip_non_deterministic(powershell_output) == strip_non_deterministic(
        python_output
    )


@requires_powershell
def test_both_implementations_agree_on_broken_json(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{ not json", encoding="utf-8")

    python_output = run_python_collector(tmp_path)
    powershell_output = run_powershell_collector(tmp_path)

    # 解析失敗の理由はランタイムごとに文言が違うため、判定に使う真偽値だけ比べる。
    for output in (python_output, powershell_output):
        assert output["settings_files"]["project"]["exists"] is True
        assert output["settings_files"]["project"]["parse_ok"] is False
        assert output["settings_files"]["project"]["error"]
    assert "project" not in powershell_output["security_relevant_settings"]
    assert "project" not in python_output["security_relevant_settings"]
