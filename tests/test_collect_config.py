"""collect_config.py のテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import collect_config


def snapshot_files(root: Path) -> dict[str, tuple[int, int]]:
    """`root` 配下の全ファイルのサイズと更新時刻を返す。"""
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """ユーザー設定と `~/.claude.json` を持つホームディレクトリーを作る。"""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["Bash(wget:*)"]}, "theme": "dark"}),
        encoding="utf-8",
    )
    return home


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    """プロジェクト設定と `.mcp.json` を持つプロジェクトディレクトリーを作る。"""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"ask": ["Bash(curl:*)"]}}),
        encoding="utf-8",
    )
    (project / ".claude" / "settings.local.json").write_text(
        json.dumps({"enableAllProjectMcpServers": True}),
        encoding="utf-8",
    )
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"local-tool": {"command": "node"}}}),
        encoding="utf-8",
    )
    return project


def test_read_json_reports_missing_file(tmp_path: Path) -> None:
    result = collect_config.read_json(tmp_path / "absent.json")

    assert result["exists"] is False
    assert result["parse_ok"] is None
    assert result["content"] is None


def test_read_json_parses_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"permissions": {"deny": ["Bash(curl:*)"]}}', encoding="utf-8")

    result = collect_config.read_json(path)

    assert result["exists"] is True
    assert result["parse_ok"] is True
    assert result["content"] == {"permissions": {"deny": ["Bash(curl:*)"]}}


def test_read_json_reports_broken_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")

    result = collect_config.read_json(path)

    assert result["exists"] is True
    assert result["parse_ok"] is False
    assert result["error"] is not None


def test_summarize_hooks_flattens_event_matcher_and_command() -> None:
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "audit.sh"},
                        {"type": "command", "command": "log.sh"},
                    ],
                }
            ]
        }
    }

    assert collect_config.summarize_hooks(settings) == [
        {
            "event": "PreToolUse",
            "matcher": "Bash",
            "type": "command",
            "command": "audit.sh",
        },
        {
            "event": "PreToolUse",
            "matcher": "Bash",
            "type": "command",
            "command": "log.sh",
        },
    ]


def test_summarize_hooks_returns_empty_when_no_hooks_defined() -> None:
    assert collect_config.summarize_hooks({"permissions": {}}) == []


def test_summarize_hooks_skips_malformed_entries() -> None:
    settings = {"hooks": {"Stop": "not-a-list", "PreToolUse": ["not-a-dict"]}}

    assert collect_config.summarize_hooks(settings) == []


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Darwin", "/Library/Application Support/ClaudeCode/managed-settings.json"),
        ("Windows", r"C:\Program Files\ClaudeCode\managed-settings.json"),
        ("Linux", "/etc/claude-code/managed-settings.json"),
    ],
)
def test_managed_settings_path_depends_on_platform(
    monkeypatch: pytest.MonkeyPatch, system: str, expected: str
) -> None:
    monkeypatch.setattr(collect_config.platform, "system", lambda: system)

    assert str(collect_config.managed_settings_path()) == expected


def test_extract_security_keys_keeps_only_security_relevant_keys() -> None:
    content = {
        "permissions": {"deny": ["Bash(curl:*)"]},
        "theme": "dark",
        "sandbox": {"enabled": True},
    }

    assert collect_config.extract_security_keys(content) == {
        "permissions": {"deny": ["Bash(curl:*)"]},
        "sandbox": {"enabled": True},
    }


def test_extract_security_keys_returns_empty_for_non_mapping() -> None:
    assert collect_config.extract_security_keys("not-a-mapping") == {}


def test_collect_records_every_settings_scope(
    fake_home: Path, fake_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": True, "version": "2.1.238", "error": None},
    )
    managed_path = fake_home / "managed-settings.json"
    managed_path.write_text(
        json.dumps({"permissions": {"deny": ["Bash(rm -rf *)"]}}), encoding="utf-8"
    )

    result = collect_config.collect(
        fake_project,
        fake_home,
        collect_config.ManagedPaths(
            settings=managed_path,
            settings_dir=fake_home / "no-managed-dir",
            mcp=fake_home / "no-mcp.json",
        ),
    )

    assert result["security_relevant_settings"] == {
        "managed": {"permissions": {"deny": ["Bash(rm -rf *)"]}},
        "user": {"permissions": {"deny": ["Bash(wget:*)"]}},
        "project": {"permissions": {"ask": ["Bash(curl:*)"]}},
        "local": {"enableAllProjectMcpServers": True},
    }
    assert result["mcp_project_file"]["content"] == {
        "mcpServers": {"local-tool": {"command": "node"}}
    }
    assert result["claude_version"]["version"] == "2.1.238"
    assert result["project_dir"] == str(fake_project)


def test_collect_reports_absent_settings_files_without_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": False, "version": None, "error": "not found"},
    )
    empty_home = tmp_path / "empty-home"
    empty_project = tmp_path / "empty-project"
    empty_home.mkdir()
    empty_project.mkdir()

    result = collect_config.collect(
        empty_project,
        empty_home,
        collect_config.ManagedPaths(
            settings=tmp_path / "no-managed.json",
            settings_dir=empty_home / "no-managed-dir",
            mcp=tmp_path / "no-mcp.json",
        ),
    )

    assert result["settings_files"]["user"]["exists"] is False
    assert "content" not in result["settings_files"]["user"]
    assert result["security_relevant_settings"] == {}


def test_collect_extracts_only_security_relevant_user_state(
    fake_home: Path, fake_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": True, "version": "2.1.238", "error": None},
    )
    (fake_home / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {"github": {}, "aws": {}},
                "history": ["秘密のプロンプト"],
                "projects": {
                    str(fake_project): {
                        "enabledMcpjsonServers": ["local-tool"],
                        "enableAllProjectMcpServers": False,
                        "mcpServers": {"scoped": {}},
                        "allowedTools": ["Read"],
                        "history": ["秘密のプロンプト"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = collect_config.collect(
        fake_project,
        fake_home,
        collect_config.ManagedPaths(
            settings=fake_home / "no-managed.json",
            settings_dir=fake_home / "no-managed-dir",
            mcp=fake_home / "no-mcp.json",
        ),
    )

    user_state = result["user_state"]
    assert user_state["global_mcp_servers"] == ["aws", "github"]
    assert user_state["project_state"]["enabledMcpjsonServers"] == ["local-tool"]
    assert user_state["project_state"]["mcpServers"] == ["scoped"]
    assert "history" not in user_state
    assert "history" not in user_state["project_state"]


def test_collect_writes_nothing(
    fake_home: Path, fake_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": True, "version": "2.1.238", "error": None},
    )
    before_home = snapshot_files(fake_home)
    before_project = snapshot_files(fake_project)

    collect_config.collect(
        fake_project,
        fake_home,
        collect_config.ManagedPaths(
            settings=fake_home / "no-managed.json",
            settings_dir=fake_home / "no-managed-dir",
            mcp=fake_home / "no-mcp.json",
        ),
    )

    assert snapshot_files(fake_home) == before_home
    assert snapshot_files(fake_project) == before_project


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Darwin", "/Library/Application Support/ClaudeCode/managed-mcp.json"),
        ("Windows", r"C:\Program Files\ClaudeCode\managed-mcp.json"),
        ("Linux", "/etc/claude-code/managed-mcp.json"),
    ],
)
def test_managed_mcp_path_depends_on_platform(
    monkeypatch: pytest.MonkeyPatch, system: str, expected: str
) -> None:
    monkeypatch.setattr(collect_config.platform, "system", lambda: system)

    assert str(collect_config.managed_mcp_path()) == expected


def test_collect_records_managed_mcp_servers(
    fake_home: Path, fake_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """組織配布の MCP 定義を見落とすと、定義済みのサーバーを未定義と誤判定する。"""
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": True, "version": "2.1.238", "error": None},
    )
    managed_mcp = fake_home / "managed-mcp.json"
    managed_mcp.write_text(
        json.dumps({"mcpServers": {"deepwiki": {"type": "http", "url": "https://x"}}}),
        encoding="utf-8",
    )

    result = collect_config.collect(
        fake_project,
        fake_home,
        collect_config.ManagedPaths(
            settings=fake_home / "no-managed.json",
            settings_dir=fake_home / "no-managed-dir",
            mcp=managed_mcp,
        ),
    )

    assert result["managed_mcp_file"]["exists"] is True
    assert result["managed_mcp_file"]["content"] == {
        "mcpServers": {"deepwiki": {"type": "http", "url": "https://x"}}
    }


def test_collect_reports_an_absent_managed_mcp_file(
    fake_home: Path, fake_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": True, "version": "2.1.238", "error": None},
    )

    result = collect_config.collect(
        fake_project,
        fake_home,
        collect_config.ManagedPaths(
            settings=fake_home / "no-managed.json",
            settings_dir=fake_home / "no-managed-dir",
            mcp=fake_home / "absent-mcp.json",
        ),
    )

    assert result["managed_mcp_file"]["exists"] is False


def test_extract_account_keeps_only_non_identifying_fields() -> None:
    """契約の判定に要る項目だけを取り、識別子と氏名は持ち出さない。"""
    account = {
        "accountUuid": "uuid-1",
        "emailAddress": "person@example.com",
        "organizationUuid": "uuid-2",
        "organizationName": "Example Inc",
        "displayName": "Someone",
        "fullName": "Some One",
        "billingType": "stripe_subscription",
        "organizationType": "claude_max",
        "seatTier": None,
        "organizationRole": "admin",
        "workspaceRole": None,
    }

    extracted = collect_config.extract_account(account)

    assert extracted == {
        "billingType": "stripe_subscription",
        "organizationType": "claude_max",
        "seatTier": None,
        "organizationRole": "admin",
        "workspaceRole": None,
        "organizationRateLimitTier": None,
        "userRateLimitTier": None,
    }
    for identifier in (
        "accountUuid",
        "emailAddress",
        "organizationUuid",
        "organizationName",
        "displayName",
        "fullName",
    ):
        assert identifier not in extracted


def test_extract_account_returns_empty_for_non_mapping() -> None:
    assert collect_config.extract_account(None) == {}


def test_collect_records_the_subscription_plan(
    fake_home: Path, fake_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        collect_config,
        "claude_version",
        lambda: {"available": True, "version": "2.1.238", "error": None},
    )
    (fake_home / ".claude.json").write_text(
        json.dumps(
            {"oauthAccount": {"organizationType": "claude_max", "seatTier": None}}
        ),
        encoding="utf-8",
    )

    result = collect_config.collect(
        fake_project,
        fake_home,
        collect_config.ManagedPaths(
            settings=fake_home / "no-managed.json",
            settings_dir=fake_home / "no-managed-dir",
            mcp=fake_home / "no-mcp.json",
        ),
    )

    assert result["account"]["organizationType"] == "claude_max"
