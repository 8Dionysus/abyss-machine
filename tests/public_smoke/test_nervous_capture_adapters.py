from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import nervous_capture_adapters as adapters  # noqa: E402


READ_AT = "2026-07-07T13:00:00+00:00"


def test_capture_status_document_uses_fakeable_ports_without_live_io(tmp_path: Path) -> None:
    capture_latest_path = tmp_path / "var" / "capture-latest.json"
    browser_latest_path = tmp_path / "var" / "browser-latest.json"
    private_root = tmp_path / "srv" / "captures"
    screenshot_root = private_root / "screenshots"
    browser_root = tmp_path / "srv" / "browser-content"
    tmp_root = tmp_path / "tmp" / "browser"
    existing = {capture_latest_path, browser_latest_path, private_root, screenshot_root, browser_root}
    latest_reads: list[Path] = []
    exists_reads: list[Path] = []
    size_reads: list[Path] = []
    count_reads: list[tuple[Path, str]] = []

    def latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        latest_reads.append(path)
        if path == capture_latest_path:
            return {"ok": True, "summary": {"facts": 4}, "sources": ["screenshot"]}, None
        if path == browser_latest_path:
            return {"ok": True, "summary": {"records": 2}}, None
        raise AssertionError(f"unexpected latest path {path}")

    def path_exists(path: Path) -> bool:
        exists_reads.append(path)
        return path in existing

    def directory_size(path: Path) -> int:
        size_reads.append(path)
        return {
            screenshot_root: 1200,
            browser_root: 3400,
            private_root: 5600,
        }[path]

    def file_counter(path: Path, pattern: str) -> int:
        count_reads.append((path, pattern))
        return {
            (screenshot_root, "*.png"): 3,
            (browser_root, "*.jsonl"): 2,
        }[(path, pattern)]

    data = adapters.capture_status_document(
        capture_latest_path=capture_latest_path,
        private_capture_root=private_root,
        screenshot_root=screenshot_root,
        browser_content_root=browser_root,
        browser_content_latest_path=browser_latest_path,
        browser_bidi_url="ws://127.0.0.1:9222/session",
        browser_tmp_root=tmp_root,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
        latest_reader=latest_reader,
        path_exists=path_exists,
        directory_size=directory_size,
        file_counter=file_counter,
    )

    assert data["schema"] == "abyss_machine_nervous_capture_status_v1"
    assert data["ok"] is True
    assert data["generated_at"] == READ_AT
    assert data["latest"] == {"ok": True, "summary": {"facts": 4}, "sources": ["screenshot"]}
    assert data["browser_content_latest"] == {"ok": True, "summary": {"records": 2}}
    assert data["paths"] == {
        "latest": str(capture_latest_path),
        "private_root": str(private_root),
        "screenshots": str(screenshot_root),
        "browser_content": str(browser_root),
        "browser_content_latest": str(browser_latest_path),
        "browser_bidi_url": "ws://127.0.0.1:9222/session",
        "browser_tmp": str(tmp_root),
    }
    assert data["storage"] == {
        "screenshots_count": 3,
        "screenshots_bytes": 1200,
        "browser_content_jsonl_files": 2,
        "browser_content_bytes": 3400,
        "private_root_bytes": 5600,
    }
    assert data["controls"] == {
        "pause": "abyss-machine nervous privacy-set pause on --reason TEXT --json",
        "private_mode": "abyss-machine nervous privacy-set private-mode on --reason TEXT --json",
        "disable_source": "abyss-machine nervous source-disable SOURCE --reason TEXT --json",
        "forget": "abyss-machine nervous forget --minutes N --json",
    }
    assert latest_reads == [capture_latest_path, browser_latest_path]
    assert exists_reads == [screenshot_root, browser_root, private_root]
    assert size_reads == [screenshot_root, browser_root, private_root]
    assert count_reads == [(screenshot_root, "*.png"), (browser_root, "*.jsonl")]


def test_capture_status_document_missing_roots_skip_size_and_count_ports(tmp_path: Path) -> None:
    capture_latest_path = tmp_path / "missing-capture.json"
    browser_latest_path = tmp_path / "missing-browser.json"
    data = adapters.capture_status_document(
        capture_latest_path=capture_latest_path,
        private_capture_root=tmp_path / "captures",
        screenshot_root=tmp_path / "screenshots",
        browser_content_root=tmp_path / "browser",
        browser_content_latest_path=browser_latest_path,
        browser_bidi_url="ws://127.0.0.1:9222",
        browser_tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
        latest_reader=lambda path: (None, "missing"),
        path_exists=lambda path: False,
        directory_size=lambda path: (_ for _ in ()).throw(AssertionError("missing roots must not be sized")),
        file_counter=lambda path, pattern: (_ for _ in ()).throw(AssertionError("missing roots must not be counted")),
    )

    assert data["ok"] is False
    assert data["latest_error"] == "missing"
    assert data["browser_content_latest_error"] == "missing"
    assert data["storage"] == {
        "screenshots_count": 0,
        "screenshots_bytes": 0,
        "browser_content_jsonl_files": 0,
        "browser_content_bytes": 0,
        "private_root_bytes": 0,
    }


def test_capture_default_helpers_measure_only_synthetic_tmp_roots(tmp_path: Path) -> None:
    screenshots = tmp_path / "screenshots"
    browser = tmp_path / "browser"
    screenshots.mkdir()
    browser.mkdir()
    (screenshots / "one.png").write_bytes(b"abcd")
    (screenshots / "two.png").write_bytes(b"ef")
    (screenshots / "ignore.txt").write_text("ignore", encoding="utf-8")
    (browser / "today.jsonl").write_text("{}\n", encoding="utf-8")
    (browser / "nested").mkdir()
    (browser / "nested" / "later.jsonl").write_text("{}\n{}\n", encoding="utf-8")

    assert adapters.count_files(screenshots, "*.png") == 2
    assert adapters.count_files(browser, "*.jsonl") == 2
    assert adapters.directory_size_bytes(screenshots) >= 6
    assert adapters.directory_size_bytes(browser) >= 6
