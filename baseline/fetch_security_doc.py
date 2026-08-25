#!/usr/bin/env python3
"""Claude Code 公式ドキュメントを取得し、変化の有無を報告する。

要件ファイルの基準となる原文を取得し、SHA256 をスナップショットと比較して
変化を検出する。要件エントリーの起こし直しは行わない。それは
`baseline/generate.md` の手順に従って Claude が担当する。

出典は複数ある。それぞれの役割は `baseline/generate.md` が定める。
どれか 1 つでも変われば要件の起こし直しが必要になるため、基準バージョンは
全出典を束ねたハッシュから決める。

Usage:
    python3 fetch_security_doc.py --check
    python3 fetch_security_doc.py --write

`--check` は取得結果を標準出力へ JSON で書くだけで、スナップショットを
更新しない。`--write` は変化があった出典だけスナップショットを更新する。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

DOCS_BASE_URL = "https://code.claude.com/docs/en/"
DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent
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


@dataclass(frozen=True)
class Source:
    """要件ファイルの出典 1 件。

    Attributes:
        url: 取得先の URL。
        snapshot_name: スナップショットディレクトリー内の保存名。
    """

    url: str
    snapshot_name: str


@dataclass(frozen=True)
class FetchedSource:
    """出典 1 件の取得結果。

    Attributes:
        url: 取得先の URL。
        snapshot_path: スナップショットの保存先。
        text: 取得した本文。
        content_sha256: 本文の SHA256（16 進 64 桁）。
        changed: スナップショットと異なる場合は True。
    """

    url: str
    snapshot_path: Path
    text: str
    content_sha256: str
    changed: bool


DEFAULT_SOURCES = (
    Source(url=f"{DOCS_BASE_URL}security.md", snapshot_name="security.md"),
    Source(url=f"{DOCS_BASE_URL}sandboxing.md", snapshot_name="sandboxing.md"),
)


def compute_sha256(text: str) -> str:
    """`text` を UTF-8 として符号化した内容の SHA256 を 16 進で返す。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_combined_sha256(fetched: list[FetchedSource]) -> str:
    """全出典を束ねたハッシュを 16 進で返す。

    出典の URL とその本文ハッシュを並べた文字列をハッシュする。本文を直接
    連結しないのは、出典の入れ替えや並び順の変更も改訂として検出するため。

    Args:
        fetched: 取得結果。渡された順序がハッシュに影響する。

    Returns:
        束ねたハッシュ（16 進 64 桁）。
    """
    digest_lines = "".join(f"{item.url} {item.content_sha256}\n" for item in fetched)
    return compute_sha256(digest_lines)


def build_baseline_version(retrieved_at: str, content_sha256: str) -> str:
    """要件ファイルのフロントマターに書く基準バージョンを組み立てる。

    Args:
        retrieved_at: 取得日（`YYYY-MM-DD`）。
        content_sha256: 全出典を束ねたハッシュ（16 進 64 桁）。

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


def fetch_sources(
    sources: tuple[Source, ...], snapshot_dir: Path
) -> list[FetchedSource]:
    """全出典を取得し、スナップショットとの差分を添えて返す。

    Args:
        sources: 取得する出典。
        snapshot_dir: スナップショットを置くディレクトリー。

    Returns:
        `sources` と同じ順序の取得結果。

    Raises:
        urllib.error.URLError: いずれかの取得に失敗した場合。
    """
    fetched: list[FetchedSource] = []
    for source in sources:
        text = fetch_document(source.url)
        snapshot_path = snapshot_dir / source.snapshot_name
        fetched.append(
            FetchedSource(
                url=source.url,
                snapshot_path=snapshot_path,
                text=text,
                content_sha256=compute_sha256(text),
                changed=detect_change(text, snapshot_path),
            )
        )
    return fetched


def build_report(fetched: list[FetchedSource]) -> dict[str, Any]:
    """取得結果を要約した辞書を返す。

    Args:
        fetched: 全出典の取得結果。

    Returns:
        `retrieved_at` / `content_sha256` / `baseline_version` / `changed` と、
        出典ごとの内訳 `sources` を持つ辞書。`changed` はいずれかの出典が
        変化していれば True。
    """
    retrieved_at = date.today().isoformat()
    content_sha256 = compute_combined_sha256(fetched)
    return {
        "retrieved_at": retrieved_at,
        "content_sha256": content_sha256,
        "baseline_version": build_baseline_version(retrieved_at, content_sha256),
        "changed": any(item.changed for item in fetched),
        "sources": [
            {
                "url": item.url,
                "snapshot_path": str(item.snapshot_path),
                "content_sha256": item.content_sha256,
                "changed": item.changed,
            }
            for item in fetched
        ],
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
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help="前回取得した原文を置くディレクトリー",
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
        help="変化があった出典のスナップショットを更新する",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """取得結果を標準出力へ JSON で書く。`--write` 時はスナップショットも更新する。"""
    args = parse_args(argv)
    fetched = fetch_sources(DEFAULT_SOURCES, args.snapshot_dir)
    report = build_report(fetched)
    if args.write:
        for item in fetched:
            if item.changed:
                write_snapshot(item.snapshot_path, item.text)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as error:
        print(f"公式ドキュメントの取得に失敗しました: {error}", file=sys.stderr)
        raise SystemExit(1) from error
