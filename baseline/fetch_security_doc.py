#!/usr/bin/env python3
"""Claude Code 公式セキュリティドキュメントを取得し、変化の有無を報告する。

要件ファイルの基準となる原文を取得し、SHA256 をスナップショットと比較して
変化を検出する。要件エントリーの起こし直しは行わない。それは
`baseline/generate.md` の手順に従って Claude が担当する。

Usage:
    python3 fetch_security_doc.py --check
    python3 fetch_security_doc.py --write

`--check` は取得結果を標準出力へ JSON で書くだけで、スナップショットを
更新しない。`--write` は変化があったときだけスナップショットを更新する。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://code.claude.com/docs/en/security.md"
DEFAULT_SNAPSHOT = Path(__file__).resolve().parent / "security.md"
FETCH_TIMEOUT_SECONDS = 30

# 既定の User-Agent（`Python-urllib/x.y`）は取得先に 403 で拒否されるため、
# 出所の分かる値を明示する。
USER_AGENT = (
    "claude-code-security-audit/0.1.0 "
    "(+https://github.com/t-izuno/claude-code-security-audit-skill)"
)

# baseline_version に埋め込むハッシュの長さ。全 64 桁は読みにくく、
# 取得日と組み合わせれば先頭 8 桁で改訂の識別には足りる。
VERSION_HASH_LENGTH = 8


def compute_sha256(text: str) -> str:
    """`text` を UTF-8 として符号化した内容の SHA256 を 16 進で返す。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_baseline_version(retrieved_at: str, content_sha256: str) -> str:
    """要件ファイルのフロントマターに書く基準バージョンを組み立てる。

    Args:
        retrieved_at: 取得日（`YYYY-MM-DD`）。
        content_sha256: 原文の SHA256（16 進 64 桁）。

    Returns:
        `取得日-ハッシュ先頭8桁` 形式の文字列。
    """
    return f"{retrieved_at}-{content_sha256[:VERSION_HASH_LENGTH]}"


def fetch_document(url: str) -> str:
    """`url` の内容を取得し、UTF-8 として復号した文字列を返す。

    Args:
        url: 取得先の URL。

    Returns:
        取得した本文。

    Raises:
        urllib.error.URLError: 取得に失敗した場合。
    """
    request = urllib.request.Request(
        url, headers={"Accept": "text/plain", "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def detect_change(fetched_text: str, snapshot_path: Path) -> bool:
    """取得した本文がスナップショットと異なるかを返す。

    Args:
        fetched_text: 取得した本文。
        snapshot_path: 前回取得した原文のパス。

    Returns:
        スナップショットが無い場合と内容が異なる場合は True。
    """
    if not snapshot_path.is_file():
        return True
    return snapshot_path.read_text(encoding="utf-8") != fetched_text


def build_report(url: str, fetched_text: str, snapshot_path: Path) -> dict[str, Any]:
    """取得結果を要約した辞書を返す。

    Args:
        url: 取得先の URL。
        fetched_text: 取得した本文。
        snapshot_path: 前回取得した原文のパス。

    Returns:
        `url` / `retrieved_at` / `content_sha256` / `baseline_version` /
        `changed` / `snapshot_path` を持つ辞書。
    """
    retrieved_at = date.today().isoformat()
    content_sha256 = compute_sha256(fetched_text)
    return {
        "url": url,
        "retrieved_at": retrieved_at,
        "content_sha256": content_sha256,
        "baseline_version": build_baseline_version(retrieved_at, content_sha256),
        "changed": detect_change(fetched_text, snapshot_path),
        "snapshot_path": str(snapshot_path),
    }


def write_snapshot(snapshot_path: Path, fetched_text: str) -> None:
    """取得した本文をスナップショットとして保存する。

    Args:
        snapshot_path: 保存先のパス。親ディレクトリーが無ければ作る。
        fetched_text: 保存する本文。
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(fetched_text, encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """コマンドライン引数を解釈する。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="取得先の URL")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="前回取得した原文の保存先",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="取得結果を報告するだけでスナップショットを更新しない（既定）",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="変化があったときにスナップショットを更新する",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """取得結果を標準出力へ JSON で書く。`--write` 時はスナップショットも更新する。"""
    args = parse_args(argv)
    fetched_text = fetch_document(args.url)
    report = build_report(args.url, fetched_text, args.snapshot)
    if args.write and report["changed"]:
        write_snapshot(args.snapshot, fetched_text)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as error:
        print(f"公式ドキュメントの取得に失敗しました: {error}", file=sys.stderr)
        raise SystemExit(1) from error
