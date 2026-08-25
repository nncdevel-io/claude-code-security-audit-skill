"""配布するスキルディレクトリーの構造のテスト。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "security-audit"
SKILL_FILE = SKILL_DIR / "SKILL.md"
BUNDLED_REQUIREMENTS = SKILL_DIR / "references" / "requirements.md"

# SKILL.md 内でスキル同梱ファイルを指す記述だけを拾う接頭辞。
# `~/.claude/settings.json` のような環境側のパスは対象外。
BUNDLED_PATH_PREFIXES = ("scripts/", "references/")

sys.path.insert(0, str(REPO_ROOT / "baseline"))

import fetch_security_doc  # noqa: E402
import validate_requirements  # noqa: E402


def read_front_matter(document: str) -> dict[str, str]:
    """SKILL.md のフロントマターを `key: value` の辞書として読む。"""
    front_matter, _ = validate_requirements.parse_front_matter(document)
    return front_matter


def find_bundled_paths(document: str) -> set[str]:
    """バッククォートで囲まれた同梱ファイルへの参照を集める。"""
    return {
        token
        for token in re.findall(r"`([^`]+)`", document)
        if token.startswith(BUNDLED_PATH_PREFIXES)
    }


def test_skill_file_exists() -> None:
    assert SKILL_FILE.is_file()


def test_skill_front_matter_declares_name_and_description() -> None:
    front_matter = read_front_matter(SKILL_FILE.read_text(encoding="utf-8"))

    assert front_matter["name"] == SKILL_DIR.name
    assert front_matter["description"]


def test_skill_name_matches_its_directory_name() -> None:
    front_matter = read_front_matter(SKILL_FILE.read_text(encoding="utf-8"))

    assert front_matter["name"] == SKILL_DIR.name


def test_every_bundled_path_referenced_by_the_skill_exists() -> None:
    referenced = find_bundled_paths(SKILL_FILE.read_text(encoding="utf-8"))

    assert referenced
    missing = sorted(path for path in referenced if not (SKILL_DIR / path).exists())
    assert missing == []


def test_bundled_baseline_passes_validation() -> None:
    errors = validate_requirements.validate(
        BUNDLED_REQUIREMENTS.read_text(encoding="utf-8")
    )

    assert errors == []


def test_skill_ships_both_collector_implementations() -> None:
    """Python が無い環境向けに PowerShell 版も同梱する。"""
    scripts = sorted(
        path.name for path in (SKILL_DIR / "scripts").iterdir() if path.is_file()
    )

    assert scripts == ["collect_config.ps1", "collect_config.py"]


@pytest.mark.parametrize(
    "forbidden_phrase",
    ["requirements-format.md", "baseline/generate.md"],
)
def test_skill_does_not_reference_generation_side_files(forbidden_phrase: str) -> None:
    assert forbidden_phrase not in SKILL_FILE.read_text(encoding="utf-8")


def test_skill_is_invoked_by_command_only() -> None:
    front_matter = read_front_matter(SKILL_FILE.read_text(encoding="utf-8"))

    assert front_matter["disable-model-invocation"] == "true"


def test_skill_declares_its_arguments_for_command_invocation() -> None:
    front_matter = read_front_matter(SKILL_FILE.read_text(encoding="utf-8"))

    assert front_matter["arguments"] == "project_dir requirements_path"
    assert front_matter["argument-hint"]


def read_stored_snapshots() -> list[fetch_security_doc.FetchedSource]:
    """`baseline/` に保存された全出典を取得結果の形で読み出す。"""
    fetched: list[fetch_security_doc.FetchedSource] = []
    for source in fetch_security_doc.DEFAULT_SOURCES:
        snapshot_path = REPO_ROOT / "baseline" / source.snapshot_name
        text = snapshot_path.read_text(encoding="utf-8")
        fetched.append(
            fetch_security_doc.FetchedSource(
                url=source.url,
                snapshot_path=snapshot_path,
                text=text,
                content_sha256=fetch_security_doc.compute_sha256(text),
                changed=False,
            )
        )
    return fetched


def test_bundled_baseline_matches_the_stored_snapshots() -> None:
    front_matter, _ = validate_requirements.parse_front_matter(
        BUNDLED_REQUIREMENTS.read_text(encoding="utf-8")
    )
    expected_version = fetch_security_doc.build_baseline_version(
        front_matter["retrieved_at"], front_matter["content_sha256"]
    )

    assert front_matter["content_sha256"] == (
        fetch_security_doc.compute_combined_sha256(read_stored_snapshots())
    )
    assert front_matter["baseline_version"] == expected_version


def test_bundled_baseline_lists_every_source_it_was_generated_from() -> None:
    front_matter, _ = validate_requirements.parse_front_matter(
        BUNDLED_REQUIREMENTS.read_text(encoding="utf-8")
    )

    listed = [url.strip() for url in front_matter["source_urls"].split(",")]

    assert listed == [source.url for source in fetch_security_doc.DEFAULT_SOURCES]


def test_collector_invocation_always_passes_an_audit_target() -> None:
    """引数を省くと監査対象がスキル自身になるため、必ず引数を渡させる。"""
    lines = [
        line.strip()
        for line in SKILL_FILE.read_text(encoding="utf-8").splitlines()
        if "collect_config.py" in line and line.strip().startswith("python3")
    ]

    assert lines
    for line in lines:
        _, _, after_script = line.partition("collect_config.py")
        assert after_script.strip(' "'), line


def test_skill_does_not_tell_the_agent_to_change_directory() -> None:
    body = SKILL_FILE.read_text(encoding="utf-8")

    assert "cd " not in body
    assert "ディレクトリーで次を実行" not in body
