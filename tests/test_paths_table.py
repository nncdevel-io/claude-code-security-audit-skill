"""OS 依存パス表（references/paths.json）のテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import collect_config

PATHS_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "security-audit"
    / "references"
    / "paths.json"
)


def test_paths_file_covers_every_supported_platform() -> None:
    table = json.loads(PATHS_FILE.read_text(encoding="utf-8"))

    assert set(table["platforms"]) == {"Darwin", "Linux", "Windows"}
    for entry in table["platforms"].values():
        assert set(entry) == {
            "managed_settings",
            "managed_settings_dir",
            "managed_mcp",
        }


def test_paths_file_records_where_the_values_came_from() -> None:
    table = json.loads(PATHS_FILE.read_text(encoding="utf-8"))

    assert table["source_url"].startswith("https://")
    assert table["retrieved_at"]


def test_windows_paths_do_not_use_the_retired_programdata_location() -> None:
    """C:\\ProgramData\\ClaudeCode は v2.1.75 で廃止された旧パス。"""
    windows = json.loads(PATHS_FILE.read_text(encoding="utf-8"))["platforms"]["Windows"]

    for value in windows.values():
        assert "ProgramData" not in value


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Darwin", "/Library/Application Support/ClaudeCode/managed-settings.json"),
        ("Windows", r"C:\Program Files\ClaudeCode\managed-settings.json"),
        ("Linux", "/etc/claude-code/managed-settings.json"),
    ],
)
def test_managed_settings_path_comes_from_the_table(
    monkeypatch: pytest.MonkeyPatch, system: str, expected: str
) -> None:
    monkeypatch.setattr(collect_config.platform, "system", lambda: system)

    assert str(collect_config.managed_settings_path()) == expected


def test_unknown_platform_raises_instead_of_silently_reporting_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """パスが分からないことを「ファイルが無い」と混同すると誤判定になる。"""
    monkeypatch.setattr(collect_config.platform, "system", lambda: "Plan9")

    with pytest.raises(KeyError, match="Plan9"):
        collect_config.managed_settings_path()


def test_collect_reads_managed_settings_fragments(tmp_path: Path) -> None:
    """managed-settings.d の断片も収集対象に含める。"""
    fragment_dir = tmp_path / "managed-settings.d"
    fragment_dir.mkdir()
    (fragment_dir / "10-network.json").write_text(
        json.dumps({"sandbox": {"enabled": True}}), encoding="utf-8"
    )
    (fragment_dir / "20-permissions.json").write_text(
        json.dumps({"permissions": {"deny": ["Bash(rm *)"]}}), encoding="utf-8"
    )
    (fragment_dir / "notes.txt").write_text("対象外", encoding="utf-8")

    fragments = collect_config.read_json_directory(fragment_dir)

    assert [Path(f["path"]).name for f in fragments] == [
        "10-network.json",
        "20-permissions.json",
    ]
    assert fragments[0]["content"] == {"sandbox": {"enabled": True}}


def test_read_json_directory_returns_empty_when_absent(tmp_path: Path) -> None:
    assert collect_config.read_json_directory(tmp_path / "absent") == []
