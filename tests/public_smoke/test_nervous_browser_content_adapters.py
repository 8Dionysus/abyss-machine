from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_browser_content_adapters as adapters


def parse_time(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    return dt.datetime.fromisoformat(str(value))


def test_browser_content_jsonl_path_uses_local_day_projection(tmp_path: Path) -> None:
    path = adapters.browser_content_jsonl_path(
        tmp_path,
        "2026-06-30T12:40:00+00:00",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )

    assert path == tmp_path / "2026" / "06" / "2026-06-30.jsonl"


def test_browser_content_store_appends_record_and_writes_latest(tmp_path: Path) -> None:
    now_values = iter([
        "2026-06-30T12:40:00+00:00",
        "2026-06-30T12:40:01+00:00",
        "2026-06-30T12:40:02+00:00",
        "2026-06-30T12:40:03+00:00",
    ])
    appends: list[tuple[Path, dict[str, Any], int]] = []
    writes: list[tuple[Path, dict[str, Any], int]] = []

    def append_jsonl(path: Path, data: dict[str, Any], mode: int):
        appends.append((path, data, mode))
        return None

    def write_json(path: Path, data: dict[str, Any], mode: int):
        writes.append((path, data, mode))
        return None

    data = adapters.browser_content_store(
        {"url": "https://example.test/docs", "title": "Docs", "text": "Useful browser text"},
        "fixture_atspi",
        content_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        context_id="ctx",
        schema_prefix="abyss_machine",
        version="test",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 6, 30, 12, 40, tzinfo=dt.timezone.utc),
        now_iso=lambda: next(now_values),
        max_text_chars=200,
        uid=1000,
        gid=1000,
        append_jsonl=append_jsonl,
        write_json=write_json,
    )

    assert data["ok"] is True
    assert data["schema"] == "abyss_machine_nervous_browser_content_ingest_v1"
    assert data["dedupe"] == {"duplicate": False}
    assert data["record"]["title"] == "Docs"
    assert data["record"]["text_length"] == len("Useful browser text")
    assert appends[0][0] == tmp_path / "browser-content" / "2026" / "06" / "2026-06-30.jsonl"
    assert appends[0][2] == 0o664
    assert writes[0][0] == tmp_path / "latest.json"
    assert writes[0][1] is data
    assert writes[0][2] == 0o664


def test_browser_content_store_suppresses_recent_duplicate_append(tmp_path: Path) -> None:
    root = tmp_path / "browser-content"
    path = root / "2026" / "06" / "2026-06-30.jsonl"
    path.parent.mkdir(parents=True)
    page = {
        "url": "https://example.test/docs",
        "title": "Docs",
        "text": "Duplicate browser text",
        "captured_at": "2026-06-30T12:41:00+00:00",
    }
    previous = adapters.browser_content_record_from_page(
        page,
        "fixture_atspi",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T12:41:00+00:00",
        max_text_chars=200,
        uid=1000,
        gid=1000,
    )
    path.write_text(json.dumps(previous) + "\n", encoding="utf-8")

    data = adapters.browser_content_store(
        page,
        "fixture_atspi",
        content_root=root,
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 6, 30, 12, 41, tzinfo=dt.timezone.utc),
        now_iso=lambda: "2026-06-30T12:41:01+00:00",
        max_text_chars=200,
        uid=1000,
        gid=1000,
        append_jsonl=lambda *_args: (_ for _ in ()).throw(AssertionError("duplicate should not append")),
        write_json=lambda *_args: None,
    )

    assert data["ok"] is True
    assert data["dedupe"]["duplicate"] is True
    assert data["dedupe"]["matched_recent_line_from_end"] == 1


def test_browser_content_store_reports_latest_write_error(tmp_path: Path) -> None:
    data = adapters.browser_content_store(
        {"url": "https://example.test/docs", "title": "Docs", "text": "Text"},
        "fixture_atspi",
        content_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 6, 30, 12, 42, tzinfo=dt.timezone.utc),
        now_iso=lambda: "2026-06-30T12:42:00+00:00",
        max_text_chars=200,
        uid=1000,
        gid=1000,
        append_jsonl=lambda *_args: None,
        write_json=lambda path, _data, _mode: {"path": str(path), "error": "readonly"},
    )

    assert data["ok"] is False
    assert data["write_errors"] == [{"path": str(tmp_path / "latest.json"), "error": "readonly"}]


def test_cli_browser_content_store_binds_adapter_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_store(*args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return {"ok": True, "capture_source": args[1]}

    monkeypatch.setattr(cli.nervous_browser_content_adapters, "browser_content_store", fake_store)

    data = cli.nervous_browser_content_store({"title": "Docs"}, "fixture", context_id="ctx-cli", write_latest=False)

    assert data == {"ok": True, "capture_source": "fixture"}
    assert captured["content_root"] == cli.NERVOUS_BROWSER_CONTENT_ROOT
    assert captured["latest_path"] == cli.NERVOUS_BROWSER_CONTENT_LATEST_PATH
    assert captured["context_id"] == "ctx-cli"
    assert captured["write_latest"] is False
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["parse_time"] is cli.parse_time
    assert captured["now_iso"] is cli.now_iso
    assert captured["append_jsonl"] is cli.safe_append_jsonl
    assert captured["write_json"] is cli.safe_atomic_write_json
