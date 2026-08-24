#!/usr/bin/env python3
"""Claude Code の設定を読み取り専用で収集し、JSON で出力する。

収集対象:

- managed-settings.json（組織強制設定）
- ~/.claude/settings.json（ユーザー設定）
- <project>/.claude/settings.json（プロジェクト共有設定）
- <project>/.claude/settings.local.json（ローカル設定）
- <project>/.mcp.json（プロジェクト MCP サーバー定義）
- managed-mcp.json（組織配布の MCP サーバー定義）
- ~/.claude.json（ユーザー状態: MCP サーバー・プロジェクト別承認状態・契約種別）
- claude --version

一切の書き込みを行わない。判定もしない。事実の収集のみを担い、
判定は要件ファイルと突合して Claude が行う。

Usage:
    python3 collect_config.py [project_dir]

project_dir を省略した場合はカレントディレクトリーを対象にする。
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# セキュリティ判定に関係する設定キー。設定ファイルの全量ではなくこれだけを
# 出力するのは、収集結果が監査に無関係な情報まで持ち出さないようにするため。
SECURITY_KEYS = (
    "permissions",
    "env",
    "apiKeyHelper",
    "cleanupPeriodDays",
    "disableBypassPermissionsMode",
    "enableAllProjectMcpServers",
    "enabledMcpjsonServers",
    "disabledMcpjsonServers",
    "allowedMcpServers",
    "deniedMcpServers",
    "forceLoginMethod",
    "forceLoginOrgUUID",
    "sandbox",
    "allowManagedHooksOnly",
    "strictKnownMarketplaces",
    "extraKnownMarketplaces",
    "otelHeadersHelper",
)

# ~/.claude.json のプロジェクト別状態から取り出すキー。同ファイルは会話履歴を
# 含み巨大なため、必要な鍵だけを抽出する。
PROJECT_STATE_KEYS = (
    "enabledMcpjsonServers",
    "disabledMcpjsonServers",
    "enableAllProjectMcpServers",
    "allowedTools",
)

# 契約の種別を判定するために取り出す項目。識別子（UUID、メールアドレス、
# 氏名、組織名）は監査に不要なので持ち出さない。
ACCOUNT_KEYS = (
    "billingType",
    "organizationType",
    "seatTier",
    "organizationRole",
    "workspaceRole",
    "organizationRateLimitTier",
    "userRateLimitTier",
)

VERSION_COMMAND_TIMEOUT_SECONDS = 15

# OS 依存のパスはコードに持たず、この表から読む。上流でパスが変わったときに
# 直すのがコードではなくデータで済むようにするため。
PATHS_FILE = Path(__file__).resolve().parent.parent / "references" / "paths.json"


def read_json(path: Path) -> dict[str, Any]:
    """JSON ファイルを読み取り、読み取り結果を返す。

    Args:
        path: 読み取り対象のパス。

    Returns:
        `path` / `exists` / `parse_ok` / `content` / `error` を持つ辞書。
        ファイルが無い場合は `exists` が False、`parse_ok` は None になる。
    """
    result: dict[str, Any] = {
        "path": str(path),
        "exists": False,
        "parse_ok": None,
        "content": None,
        "error": None,
    }
    if not path.is_file():
        return result

    result["exists"] = True
    try:
        result["content"] = json.loads(path.read_text(encoding="utf-8"))
        result["parse_ok"] = True
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        result["parse_ok"] = False
        result["error"] = str(error)
    except OSError as error:
        result["error"] = str(error)
    return result


def load_paths() -> dict[str, Any]:
    """OS 依存パスの表を読む。"""
    return json.loads(PATHS_FILE.read_text(encoding="utf-8"))


def platform_paths() -> dict[str, str]:
    """実行中のプラットフォーム向けのパス一式を返す。

    Returns:
        `managed_settings` / `managed_settings_dir` / `managed_mcp` の辞書。

    Raises:
        KeyError: 表に載っていないプラットフォームで実行された場合。パスが
            分からないことを「ファイルが無い」と混同すると誤判定になるため、
            黙って空を返さずに失敗させる。
    """
    system = platform.system()
    platforms = load_paths()["platforms"]
    if system not in platforms:
        raise KeyError(f"{system} 向けのパスが {PATHS_FILE} にありません")
    return platforms[system]


def read_json_directory(directory: Path) -> list[dict[str, Any]]:
    """ディレクトリー内の JSON ファイルを名前順に読む。

    Args:
        directory: 読み取り対象のディレクトリー。

    Returns:
        `read_json` の結果の一覧。ディレクトリーが無ければ空。
    """
    if not directory.is_dir():
        return []
    return [read_json(path) for path in sorted(directory.glob("*.json"))]


def managed_settings_path() -> Path:
    """組織強制設定のパスを返す。"""
    return Path(platform_paths()["managed_settings"])


def managed_settings_dir_path() -> Path:
    """組織強制設定の断片を置くディレクトリーのパスを返す。"""
    return Path(platform_paths()["managed_settings_dir"])


def managed_mcp_path() -> Path:
    """組織配布 MCP 定義のパスを返す。"""
    return Path(platform_paths()["managed_mcp"])


@dataclass(frozen=True)
class ManagedPaths:
    """組織が配布する設定ファイルの場所。

    Attributes:
        settings: `managed-settings.json` のパス。
        settings_dir: `managed-settings.d` のパス。
        mcp: `managed-mcp.json` のパス。
    """

    settings: Path
    settings_dir: Path
    mcp: Path

    @classmethod
    def for_current_platform(cls) -> ManagedPaths:
        """実行中のプラットフォーム向けの一式を作る。"""
        return cls(
            settings=managed_settings_path(),
            settings_dir=managed_settings_dir_path(),
            mcp=managed_mcp_path(),
        )


def claude_version() -> dict[str, Any]:
    """`claude --version` の実行結果を返す。

    Returns:
        `available` / `version` / `error` を持つ辞書。コマンドが見つからない
        場合や失敗した場合は `available` が False になり、`error` に理由が入る。
    """
    result: dict[str, Any] = {"available": False, "version": None, "error": None}
    if shutil.which("claude") is None:
        result["error"] = "claude command not found in PATH"
        return result

    try:
        completed = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=VERSION_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        result["error"] = str(error)
        return result

    if completed.returncode != 0:
        result["error"] = completed.stderr.strip()
        return result

    result["available"] = True
    result["version"] = completed.stdout.strip()
    return result


def summarize_hooks(settings_content: Any) -> list[dict[str, Any]]:
    """設定内の hooks 定義をイベント名・matcher・コマンドの一覧へ平坦化する。

    Args:
        settings_content: 設定ファイルの内容。辞書以外は空の一覧として扱う。

    Returns:
        `event` / `matcher` / `type` / `command` を持つ辞書の一覧。
    """
    if not isinstance(settings_content, dict):
        return []

    hooks: list[dict[str, Any]] = []
    for event, entries in (settings_content.get("hooks") or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks") or []:
                hooks.append(
                    {
                        "event": event,
                        "matcher": entry.get("matcher"),
                        "type": hook.get("type"),
                        "command": hook.get("command"),
                    }
                )
    return hooks


def extract_security_keys(settings_content: Any) -> dict[str, Any]:
    """設定内容から `SECURITY_KEYS` に含まれるキーだけを抜き出す。

    Args:
        settings_content: 設定ファイルの内容。辞書以外は空の辞書として扱う。

    Returns:
        存在したセキュリティ関連キーとその値。
    """
    if not isinstance(settings_content, dict):
        return {}
    return {
        key: settings_content[key] for key in SECURITY_KEYS if key in settings_content
    }


def extract_account(account: Any) -> dict[str, Any]:
    """`oauthAccount` から契約の判定に要る項目だけを取り出す。

    Args:
        account: `~/.claude.json` の `oauthAccount`。辞書以外は空として扱う。

    Returns:
        `ACCOUNT_KEYS` の各項目。識別子や氏名は含めない。
    """
    if not isinstance(account, dict):
        return {}
    return {key: account.get(key) for key in ACCOUNT_KEYS}


def extract_user_state(user_state: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    """`~/.claude.json` から監査に必要な鍵だけを抽出する。

    Args:
        user_state: `read_json` が返した `~/.claude.json` の読み取り結果。
        project_dir: 監査対象プロジェクトの絶対パス。

    Returns:
        `path` / `exists` / `parse_ok` に加え、読めた場合は
        `global_mcp_servers` と `project_state` を持つ辞書。
    """
    extracted: dict[str, Any] = {
        "path": user_state["path"],
        "exists": user_state["exists"],
        "parse_ok": user_state["parse_ok"],
    }
    if not user_state["parse_ok"]:
        return extracted

    content = user_state["content"]
    extracted["global_mcp_servers"] = sorted((content.get("mcpServers") or {}).keys())
    project = (content.get("projects") or {}).get(str(project_dir), {})
    project_state = {key: project.get(key) for key in PROJECT_STATE_KEYS}
    project_state["mcpServers"] = sorted((project.get("mcpServers") or {}).keys())
    extracted["project_state"] = project_state
    return extracted


def collect(project_dir: Path, home: Path, managed: ManagedPaths) -> dict[str, Any]:
    """設定を収集して JSON 化可能な辞書を返す。

    Args:
        project_dir: 監査対象プロジェクトの絶対パス。
        home: ユーザー設定を探すホームディレクトリー。
        managed: 組織が配布する設定ファイルの場所。

    Returns:
        収集結果。読めなかったファイルは `exists` や `parse_ok` で表現され、
        欠落として黙殺されることはない。
    """
    scopes = {
        "managed": read_json(managed.settings),
        "user": read_json(home / ".claude" / "settings.json"),
        "project": read_json(project_dir / ".claude" / "settings.json"),
        "local": read_json(project_dir / ".claude" / "settings.local.json"),
    }
    readable = {name: scope for name, scope in scopes.items() if scope["parse_ok"]}
    user_state = read_json(home / ".claude.json")

    return {
        "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": platform.system(),
        "project_dir": str(project_dir),
        "claude_version": claude_version(),
        "settings_files": {
            name: {key: value for key, value in scope.items() if key != "content"}
            for name, scope in scopes.items()
        },
        "security_relevant_settings": {
            name: extract_security_keys(scope["content"])
            for name, scope in readable.items()
        },
        "hooks": {
            name: summarize_hooks(scope["content"]) for name, scope in readable.items()
        },
        "mcp_project_file": read_json(project_dir / ".mcp.json"),
        "managed_mcp_file": read_json(managed.mcp),
        "managed_settings_fragments": read_json_directory(managed.settings_dir),
        "user_state": extract_user_state(user_state, project_dir),
        "account": extract_account((user_state["content"] or {}).get("oauthAccount"))
        if user_state["parse_ok"]
        else {},
    }


def main() -> None:
    """コマンドライン引数を読み、収集結果を標準出力へ JSON で書く。"""
    # シンボリックリンクは解決しない。PowerShell 版の GetFullPath と挙動を
    # 揃えるためと、Claude Code が記録する作業ディレクトリーの表記に合わせるため。
    argument = sys.argv[1] if len(sys.argv) > 1 else "."
    project_dir = Path(os.path.abspath(argument))
    output = collect(project_dir, Path.home(), ManagedPaths.for_current_platform())
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
