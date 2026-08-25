"""fetch_security_doc.py のテスト。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import fetch_security_doc

SAMPLE_DOCUMENT = "# Security\n\nSample body.\n"
SAMPLE_SHA256 = "32b8af7562f6007425ab22cab9801d2f2aa93898f3449afd32ee09ca171e396c"
SANDBOXING_DOCUMENT = "# Sandboxing\n\nSample body.\n"
SANDBOXING_SHA256 = "94ec1d246ffe0a6f33841fd29262baaecbe2dc906fb62b6aeb1fd17c72b4c69b"

SAMPLE_SOURCES = (
    fetch_security_doc.Source(
        url="https://example.com/security.md", snapshot_name="security.md"
    ),
    fetch_security_doc.Source(
        url="https://example.com/sandboxing.md", snapshot_name="sandboxing.md"
    ),
)
DOCUMENTS_BY_URL = {
    "https://example.com/security.md": SAMPLE_DOCUMENT,
    "https://example.com/sandboxing.md": SANDBOXING_DOCUMENT,
}


def fake_fetch_document(url: str) -> str:
    """出典ごとに異なる本文を返す `fetch_document` の代役。"""
    return DOCUMENTS_BY_URL[url]


def build_fetched(
    url: str, text: str, snapshot_path: Path
) -> fetch_security_doc.FetchedSource:
    """テスト用の取得結果を組み立てる。"""
    return fetch_security_doc.FetchedSource(
        url=url,
        snapshot_path=snapshot_path,
        text=text,
        content_sha256=fetch_security_doc.compute_sha256(text),
        changed=True,
    )


def test_compute_sha256_hashes_utf8_bytes() -> None:
    assert fetch_security_doc.compute_sha256(SAMPLE_DOCUMENT) == SAMPLE_SHA256


def test_default_sources_cover_security_and_sandboxing() -> None:
    """要件の出典は security だけでなく sandboxing も含む。"""
    urls = [source.url for source in fetch_security_doc.DEFAULT_SOURCES]

    assert urls == [
        "https://code.claude.com/docs/en/security.md",
        "https://code.claude.com/docs/en/sandboxing.md",
    ]


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


def test_compute_combined_sha256_covers_every_source(tmp_path: Path) -> None:
    fetched = [
        build_fetched(
            "https://example.com/security.md", SAMPLE_DOCUMENT, tmp_path / "a.md"
        ),
        build_fetched(
            "https://example.com/sandboxing.md",
            SANDBOXING_DOCUMENT,
            tmp_path / "b.md",
        ),
    ]

    assert fetch_security_doc.compute_combined_sha256(fetched) == (
        "843a95bc84a923aff3f21944073bcf6cd4cc19ca8c9775422ec6324d867dd003"
    )


def test_compute_combined_sha256_changes_when_one_source_changes(
    tmp_path: Path,
) -> None:
    """sandboxing だけが変わっても基準バージョンが動くことを保証する。"""
    unchanged = build_fetched(
        "https://example.com/security.md", SAMPLE_DOCUMENT, tmp_path / "a.md"
    )
    before = build_fetched(
        "https://example.com/sandboxing.md", SANDBOXING_DOCUMENT, tmp_path / "b.md"
    )
    after = build_fetched(
        "https://example.com/sandboxing.md",
        "# Sandboxing\n\nRewritten body.\n",
        tmp_path / "b.md",
    )

    assert fetch_security_doc.compute_combined_sha256(
        [unchanged, before]
    ) != fetch_security_doc.compute_combined_sha256([unchanged, after])


def test_fetch_sources_returns_one_result_per_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_security_doc, "fetch_document", fake_fetch_document)

    fetched = fetch_security_doc.fetch_sources(SAMPLE_SOURCES, tmp_path)

    assert [item.url for item in fetched] == [
        "https://example.com/security.md",
        "https://example.com/sandboxing.md",
    ]
    assert fetched[0].snapshot_path == tmp_path / "security.md"
    assert fetched[1].content_sha256 == SANDBOXING_SHA256
    assert fetched[1].changed is True


def test_build_report_describes_every_fetched_source(tmp_path: Path) -> None:
    fetched = [
        build_fetched(
            "https://example.com/security.md",
            SAMPLE_DOCUMENT,
            tmp_path / "security.md",
        ),
        build_fetched(
            "https://example.com/sandboxing.md",
            SANDBOXING_DOCUMENT,
            tmp_path / "sandboxing.md",
        ),
    ]

    report = fetch_security_doc.build_report(fetched)

    assert report["content_sha256"] == (
        "843a95bc84a923aff3f21944073bcf6cd4cc19ca8c9775422ec6324d867dd003"
    )
    assert report["changed"] is True
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", report["retrieved_at"])
    assert report["baseline_version"] == f"{report['retrieved_at']}-843a95bc"
    assert [source["url"] for source in report["sources"]] == [
        "https://example.com/security.md",
        "https://example.com/sandboxing.md",
    ]
    assert report["sources"][1]["snapshot_path"] == str(tmp_path / "sandboxing.md")


def test_build_report_reports_no_change_when_every_source_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "security.md").write_text(SAMPLE_DOCUMENT, encoding="utf-8")
    (tmp_path / "sandboxing.md").write_text(SANDBOXING_DOCUMENT, encoding="utf-8")
    monkeypatch.setattr(fetch_security_doc, "fetch_document", fake_fetch_document)

    report = fetch_security_doc.build_report(
        fetch_security_doc.fetch_sources(SAMPLE_SOURCES, tmp_path)
    )

    assert report["changed"] is False


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


def test_main_check_prints_report_without_writing_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(fetch_security_doc, "DEFAULT_SOURCES", SAMPLE_SOURCES)
    monkeypatch.setattr(fetch_security_doc, "fetch_document", fake_fetch_document)

    fetch_security_doc.main(["--check", "--snapshot-dir", str(tmp_path)])

    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is True
    assert list(tmp_path.iterdir()) == []


def test_main_write_updates_every_changed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "security.md").write_text("# Security\n\nOld body.\n", encoding="utf-8")
    monkeypatch.setattr(fetch_security_doc, "DEFAULT_SOURCES", SAMPLE_SOURCES)
    monkeypatch.setattr(fetch_security_doc, "fetch_document", fake_fetch_document)

    fetch_security_doc.main(["--write", "--snapshot-dir", str(tmp_path)])

    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is True
    assert (tmp_path / "security.md").read_text(encoding="utf-8") == SAMPLE_DOCUMENT
    assert (tmp_path / "sandboxing.md").read_text(encoding="utf-8") == (
        SANDBOXING_DOCUMENT
    )


def test_main_write_keeps_snapshots_when_content_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot = tmp_path / "security.md"
    snapshot.write_text(SAMPLE_DOCUMENT, encoding="utf-8")
    (tmp_path / "sandboxing.md").write_text(SANDBOXING_DOCUMENT, encoding="utf-8")
    before = snapshot.stat().st_mtime_ns
    monkeypatch.setattr(fetch_security_doc, "DEFAULT_SOURCES", SAMPLE_SOURCES)
    monkeypatch.setattr(fetch_security_doc, "fetch_document", fake_fetch_document)

    fetch_security_doc.main(["--write", "--snapshot-dir", str(tmp_path)])

    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is False
    assert snapshot.stat().st_mtime_ns == before
