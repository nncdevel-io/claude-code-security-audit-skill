"""validate_requirements.py のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

import validate_requirements

SAMPLE_SHA256 = "32b8af7562f6007425ab22cab9801d2f2aa93898f3449afd32ee09ca171e396c"
BASELINE_VERSION = "2026-08-21-32b8af75"
SOURCE_URLS = (
    "https://code.claude.com/docs/en/security.md, "
    "https://code.claude.com/docs/en/sandboxing.md"
)

VALID_DOCUMENT = f"""---
baseline_version: {BASELINE_VERSION}
source_urls: {SOURCE_URLS}
retrieved_at: 2026-08-21
content_sha256: {SAMPLE_SHA256}
---

# Claude Code セキュリティ要件

## REQ-001: ネットワーク取得コマンドの統制

- category: prompt-injection
- check: config
- target: permissions.deny または permissions.ask に Bash(curl:*) と
  Bash(wget:*) が含まれること
- rationale: Web から任意コンテンツを取得するコマンドは経路になるため

## REQ-002: MCP サーバーの信頼性確認

- category: mcp
- check: manual
- target: 利用中の全 MCP サーバーが信頼できる提供元であること
"""


def replace_line(document: str, old: str, new: str) -> str:
    """`document` 内の 1 行を置き換えた文書を返す。"""
    assert old in document
    return document.replace(old, new)


def test_parse_front_matter_returns_fields_and_body() -> None:
    front_matter, body = validate_requirements.parse_front_matter(VALID_DOCUMENT)

    assert front_matter["baseline_version"] == "2026-08-21-32b8af75"
    assert front_matter["retrieved_at"] == "2026-08-21"
    assert body.lstrip().startswith("# Claude Code セキュリティ要件")


def test_parse_front_matter_returns_nothing_when_delimiter_is_missing() -> None:
    front_matter, body = validate_requirements.parse_front_matter("# 見出しだけ\n")

    assert front_matter == {}
    assert body == "# 見出しだけ\n"


def test_parse_requirements_reads_id_title_and_fields() -> None:
    _, body = validate_requirements.parse_front_matter(VALID_DOCUMENT)

    requirements = validate_requirements.parse_requirements(body)

    assert [requirement.id for requirement in requirements] == [
        "REQ-001",
        "REQ-002",
    ]
    assert requirements[0].title == "ネットワーク取得コマンドの統制"
    assert requirements[1].fields["check"] == "manual"


def test_parse_requirements_joins_continuation_lines_of_a_field() -> None:
    _, body = validate_requirements.parse_front_matter(VALID_DOCUMENT)

    requirements = validate_requirements.parse_requirements(body)

    assert requirements[0].fields["target"] == (
        "permissions.deny または permissions.ask に Bash(curl:*) と "
        "Bash(wget:*) が含まれること"
    )


def test_validate_accepts_a_well_formed_document() -> None:
    assert validate_requirements.validate(VALID_DOCUMENT) == []


def test_validate_rejects_a_document_without_front_matter() -> None:
    errors = validate_requirements.validate("## REQ-001: 何か\n\n- check: manual\n")

    assert any("フロントマター" in error for error in errors)


def test_validate_rejects_a_missing_baseline_version() -> None:
    document = replace_line(
        VALID_DOCUMENT, f"baseline_version: {BASELINE_VERSION}\n", ""
    )

    errors = validate_requirements.validate(document)

    assert any("baseline_version" in error for error in errors)


def test_validate_rejects_a_missing_source_urls() -> None:
    document = replace_line(VALID_DOCUMENT, f"source_urls: {SOURCE_URLS}\n", "")

    errors = validate_requirements.validate(document)

    assert any("source_urls" in error for error in errors)


def test_validate_rejects_a_malformed_content_sha256() -> None:
    document = replace_line(
        VALID_DOCUMENT,
        f"content_sha256: {SAMPLE_SHA256}",
        "content_sha256: not-a-hash",
    )

    errors = validate_requirements.validate(document)

    assert any("content_sha256" in error for error in errors)


def test_validate_rejects_a_baseline_version_inconsistent_with_the_hash() -> None:
    document = replace_line(
        VALID_DOCUMENT,
        f"baseline_version: {BASELINE_VERSION}",
        "baseline_version: 2026-08-21-deadbeef",
    )

    errors = validate_requirements.validate(document)

    assert any("baseline_version" in error for error in errors)


def test_validate_rejects_a_document_without_requirements() -> None:
    _, body = validate_requirements.parse_front_matter(VALID_DOCUMENT)
    document = VALID_DOCUMENT.replace(body, "\n# 要件なし\n")

    errors = validate_requirements.validate(document)

    assert any("要件が 1 件もありません" in error for error in errors)


def test_validate_rejects_duplicate_requirement_ids() -> None:
    document = replace_line(VALID_DOCUMENT, "## REQ-002:", "## REQ-001:")

    errors = validate_requirements.validate(document)

    assert any("REQ-001" in error and "重複" in error for error in errors)


def test_validate_rejects_an_unknown_category() -> None:
    document = replace_line(VALID_DOCUMENT, "- category: mcp", "- category: unknown")

    errors = validate_requirements.validate(document)

    assert any("category" in error and "REQ-002" in error for error in errors)


def test_validate_rejects_an_unknown_check_value() -> None:
    document = replace_line(VALID_DOCUMENT, "- check: manual", "- check: sometimes")

    errors = validate_requirements.validate(document)

    assert any("check" in error and "REQ-002" in error for error in errors)


def test_validate_rejects_a_requirement_without_target() -> None:
    document = replace_line(
        VALID_DOCUMENT,
        "- target: 利用中の全 MCP サーバーが信頼できる提供元であること\n",
        "",
    )

    errors = validate_requirements.validate(document)

    assert any("target" in error and "REQ-002" in error for error in errors)


def test_validate_accepts_a_deprecated_requirement() -> None:
    document = replace_line(
        VALID_DOCUMENT, "- check: manual", "- check: manual\n- status: deprecated"
    )

    assert validate_requirements.validate(document) == []


def test_validate_rejects_an_unknown_status() -> None:
    document = replace_line(
        VALID_DOCUMENT, "- check: manual", "- check: manual\n- status: retired"
    )

    errors = validate_requirements.validate(document)

    assert any("status" in error for error in errors)


def test_main_returns_zero_for_a_valid_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "requirements.md"
    path.write_text(VALID_DOCUMENT, encoding="utf-8")

    assert validate_requirements.main([str(path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_returns_one_and_lists_errors_for_an_invalid_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "requirements.md"
    path.write_text("# 中身なし\n", encoding="utf-8")

    assert validate_requirements.main([str(path)]) == 1
    assert "フロントマター" in capsys.readouterr().err


def test_main_returns_one_when_the_file_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert validate_requirements.main([str(tmp_path / "absent.md")]) == 1
    assert "見つかりません" in capsys.readouterr().err
