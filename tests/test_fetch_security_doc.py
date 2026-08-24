"""fetch_security_doc.py のテスト。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import fetch_security_doc

SAMPLE_DOCUMENT = "# Security\n\nSample body.\n"
SAMPLE_SHA256 = "32b8af7562f6007425ab22cab9801d2f2aa93898f3449afd32ee09ca171e396c"


def test_compute_sha256_hashes_utf8_bytes() -> None:
    assert fetch_security_doc.compute_sha256(SAMPLE_DOCUMENT) == SAMPLE_SHA256


def test_detect_change_reports_change_when_snapshot_is_absent(tmp_path: Path) -> None:
    assert (
        fetch_security_doc.detect_change(SAMPLE_DOCUMENT, tmp_path / "absent.md")
        is True
    )


def test_detect_change_reports_no_change_for_identical_snapshot(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "security.md"
    snapshot.write_text(SAMPLE_DOCUMENT, encoding="utf-8")

    assert fetch_security_doc.detect_change(SAMPLE_DOCUMENT, snapshot) is False


def test_detect_change_reports_change_for_modified_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "security.md"
    snapshot.write_text("# Security\n\nOld body.\n", encoding="utf-8")

    assert fetch_security_doc.detect_change(SAMPLE_DOCUMENT, snapshot) is True


def test_build_baseline_version_joins_date_and_hash_prefix() -> None:
    version = fetch_security_doc.build_baseline_version("2026-08-21", SAMPLE_SHA256)

    assert version == "2026-08-21-32b8af75"


def test_build_report_describes_the_fetched_document(tmp_path: Path) -> None:
    snapshot = tmp_path / "security.md"

    report = fetch_security_doc.build_report(
        "https://example.com/security.md", SAMPLE_DOCUMENT, snapshot
    )

    assert report["url"] == "https://example.com/security.md"
    assert report["content_sha256"] == SAMPLE_SHA256
    assert report["changed"] is True
    assert report["snapshot_path"] == str(snapshot)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", report["retrieved_at"])
    assert report["baseline_version"] == f"{report['retrieved_at']}-32b8af75"


def test_write_snapshot_creates_parent_directories(tmp_path: Path) -> None:
    snapshot = tmp_path / "nested" / "security.md"

    fetch_security_doc.write_snapshot(snapshot, SAMPLE_DOCUMENT)

    assert snapshot.read_text(encoding="utf-8") == SAMPLE_DOCUMENT


def test_fetch_document_decodes_response_as_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return SAMPLE_DOCUMENT.encode("utf-8")

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(
        fetch_security_doc.urllib.request, "urlopen", lambda *_, **__: FakeResponse()
    )

    assert fetch_security_doc.fetch_document("https://example.com/security.md") == (
        SAMPLE_DOCUMENT
    )


def test_fetch_document_identifies_itself_with_a_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """既定の User-Agent は取得先に 403 で拒否されるため、明示が必要。"""
    captured: dict[str, str] = {}

    class FakeResponse:
        def read(self) -> bytes:
            return SAMPLE_DOCUMENT.encode("utf-8")

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def fake_urlopen(request: object, **_: object) -> FakeResponse:
        captured.update(request.headers)  # type: ignore[attr-defined]
        return FakeResponse()

    monkeypatch.setattr(fetch_security_doc.urllib.request, "urlopen", fake_urlopen)

    fetch_security_doc.fetch_document("https://example.com/security.md")

    assert "python-urllib" not in captured["User-agent"].lower()
    assert "claude-code-security-audit" in captured["User-agent"]


def test_main_check_prints_report_without_writing_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "security.md"
    monkeypatch.setattr(fetch_security_doc, "fetch_document", lambda _: SAMPLE_DOCUMENT)

    fetch_security_doc.main(["--check", "--snapshot", str(snapshot)])

    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is True
    assert snapshot.exists() is False


def test_main_write_updates_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "security.md"
    snapshot.write_text("# Security\n\nOld body.\n", encoding="utf-8")
    monkeypatch.setattr(fetch_security_doc, "fetch_document", lambda _: SAMPLE_DOCUMENT)

    fetch_security_doc.main(["--write", "--snapshot", str(snapshot)])

    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is True
    assert snapshot.read_text(encoding="utf-8") == SAMPLE_DOCUMENT


def test_main_write_keeps_snapshot_when_content_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "security.md"
    snapshot.write_text(SAMPLE_DOCUMENT, encoding="utf-8")
    before = snapshot.stat().st_mtime_ns
    monkeypatch.setattr(fetch_security_doc, "fetch_document", lambda _: SAMPLE_DOCUMENT)

    fetch_security_doc.main(["--write", "--snapshot", str(snapshot)])

    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is False
    assert snapshot.stat().st_mtime_ns == before
