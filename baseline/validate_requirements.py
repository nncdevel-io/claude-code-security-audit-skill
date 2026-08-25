#!/usr/bin/env python3
"""セキュリティ要件ファイルがフォーマット仕様どおりかを検証する。

仕様は `baseline/requirements-format.md` にある。要件ファイルは監査レポートの
判定基準そのものなので、生成物を取り込む前にこの検証を通す。

Usage:
    python3 validate_requirements.py <path>

問題が無ければ終了コード 0、あれば見つかった問題を標準エラーへ列挙して 1 を返す。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FRONT_MATTER_DELIMITER = "---"
REQUIRED_FRONT_MATTER_KEYS = (
    "baseline_version",
    "source_urls",
    "retrieved_at",
    "content_sha256",
)
CATEGORIES = frozenset(
    {"permission", "prompt-injection", "mcp", "hooks", "credential", "team"}
)
CHECK_VALUES = frozenset({"config", "manual"})
STATUS_VALUES = frozenset({"active", "deprecated"})
REQUIRED_REQUIREMENT_FIELDS = ("category", "check", "target")

HEADING_PATTERN = re.compile(r"^## (REQ-\d{3}): (.+)$")
FIELD_PATTERN = re.compile(r"^- ([a-z_]+): (.*)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RETRIEVED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# baseline_version の後半に埋め込むハッシュの長さ。
# fetch_security_doc.build_baseline_version と同じ規則。
VERSION_HASH_LENGTH = 8


@dataclass(frozen=True)
class Requirement:
    """要件エントリー 1 件。

    Attributes:
        id: 要件 ID（`REQ-001` 形式）。レポートで突合キーになる。
        title: 見出しに書かれた要件名。
        fields: `- key: value` 形式で書かれた項目。
    """

    id: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)


def parse_front_matter(document: str) -> tuple[dict[str, str], str]:
    """文書の先頭にある YAML フロントマターと本文を分離する。

    Args:
        document: 要件ファイルの全文。

    Returns:
        フロントマターの `key: value` を収めた辞書と、それ以降の本文。
        フロントマターが無い場合は空の辞書と文書全体を返す。
    """
    lines = document.splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        return {}, document

    front_matter: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONT_MATTER_DELIMITER:
            return front_matter, "".join(lines[index + 1 :])
        key, separator, value = line.partition(":")
        if separator:
            front_matter[key.strip()] = value.strip()
    return {}, document


def parse_requirements(body: str) -> list[Requirement]:
    """本文から要件エントリーを読み取る。

    Args:
        body: フロントマターを除いた本文。

    Returns:
        読み取った要件の一覧。字下げされた継続行は直前の項目へ連結される。
    """
    requirements: list[Requirement] = []
    current_field: str | None = None

    for line in body.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            requirements.append(
                Requirement(id=heading.group(1), title=heading.group(2).strip())
            )
            current_field = None
            continue

        if not requirements:
            continue

        fields = requirements[-1].fields
        matched = FIELD_PATTERN.match(line)
        if matched:
            current_field = matched.group(1)
            fields[current_field] = matched.group(2).strip()
            continue

        # 字下げされた行は直前の項目の続き。原文の改行位置は意味を持たないので
        # 空白 1 つで連結する。
        if current_field and line.startswith(" ") and line.strip():
            fields[current_field] = f"{fields[current_field]} {line.strip()}"
            continue

        current_field = None

    return requirements


def validate_front_matter(front_matter: dict[str, str]) -> list[str]:
    """フロントマターの必須項目と整合性を検証する。

    Args:
        front_matter: `parse_front_matter` が返した辞書。

    Returns:
        見つかった問題の一覧。問題が無ければ空。
    """
    if not front_matter:
        return ["フロントマターがありません"]

    errors = [
        f"フロントマターに {key} がありません"
        for key in REQUIRED_FRONT_MATTER_KEYS
        if not front_matter.get(key)
    ]

    content_sha256 = front_matter.get("content_sha256", "")
    if content_sha256 and not SHA256_PATTERN.fullmatch(content_sha256):
        errors.append("content_sha256 が 16 進 64 桁ではありません")

    retrieved_at = front_matter.get("retrieved_at", "")
    if retrieved_at and not RETRIEVED_AT_PATTERN.fullmatch(retrieved_at):
        errors.append("retrieved_at が YYYY-MM-DD 形式ではありません")

    errors.extend(
        _validate_baseline_version(
            front_matter.get("baseline_version", ""), retrieved_at, content_sha256
        )
    )
    return errors


def _validate_baseline_version(
    baseline_version: str, retrieved_at: str, content_sha256: str
) -> list[str]:
    """baseline_version が取得日とハッシュから導ける値かを検証する。"""
    if not (baseline_version and retrieved_at and content_sha256):
        return []

    expected = f"{retrieved_at}-{content_sha256[:VERSION_HASH_LENGTH]}"
    if baseline_version == expected:
        return []
    return [
        "baseline_version が retrieved_at と content_sha256 と整合しません"
        f"（期待値: {expected}）"
    ]


def validate_requirement(requirement: Requirement) -> list[str]:
    """要件エントリー 1 件の必須項目と値域を検証する。

    Args:
        requirement: 検証対象の要件。

    Returns:
        見つかった問題の一覧。問題が無ければ空。
    """
    errors = [
        f"{requirement.id}: {name} がありません"
        for name in REQUIRED_REQUIREMENT_FIELDS
        if not requirement.fields.get(name)
    ]

    category = requirement.fields.get("category")
    if category and category not in CATEGORIES:
        errors.append(
            f"{requirement.id}: category の値 {category} は分類一覧にありません"
        )

    check = requirement.fields.get("check")
    if check and check not in CHECK_VALUES:
        errors.append(
            f"{requirement.id}: check の値 {check} は config か manual のみです"
        )

    status = requirement.fields.get("status")
    if status and status not in STATUS_VALUES:
        errors.append(
            f"{requirement.id}: status の値 {status} は active か deprecated のみです"
        )

    return errors


def find_duplicate_ids(requirements: list[Requirement]) -> list[str]:
    """重複している要件 ID を報告する。"""
    seen: set[str] = set()
    duplicates: list[str] = []
    for requirement in requirements:
        if requirement.id in seen and requirement.id not in duplicates:
            duplicates.append(requirement.id)
        seen.add(requirement.id)
    return [f"要件 ID {duplicate} が重複しています" for duplicate in duplicates]


def validate(document: str) -> list[str]:
    """要件ファイル全体を検証する。

    Args:
        document: 要件ファイルの全文。

    Returns:
        見つかった問題の一覧。問題が無ければ空。
    """
    front_matter, body = parse_front_matter(document)
    errors = validate_front_matter(front_matter)

    requirements = parse_requirements(body)
    if not requirements:
        errors.append("要件が 1 件もありません")
        return errors

    errors.extend(find_duplicate_ids(requirements))
    for requirement in requirements:
        errors.extend(validate_requirement(requirement))
    return errors


def main(argv: list[str] | None = None) -> int:
    """要件ファイルを検証し、終了コードを返す。

    Args:
        argv: コマンドライン引数。省略時は `sys.argv[1:]` を使う。

    Returns:
        問題が無ければ 0、あれば 1。
    """
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Usage: validate_requirements.py <path>", file=sys.stderr)
        return 1

    path = Path(arguments[0])
    if not path.is_file():
        print(f"要件ファイルが見つかりません: {path}", file=sys.stderr)
        return 1

    errors = validate(path.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
