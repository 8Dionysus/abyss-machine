from __future__ import annotations

import datetime as dt
import json
import os

from abyss_machine import typing_nervous_adapters


def test_store_latest_history_and_index_writes_public_safe_files(tmp_path):
    latest = tmp_path / "typing" / "latest.json"
    history_root = tmp_path / "typing" / "history"
    index_path = tmp_path / "typing" / "index.json"
    payload = {"schema": "test_typing_payload_v1", "ok": True, "status": "captured"}
    index = {"schema": "test_typing_index_v1", "paths": {"latest": str(latest)}}
    when = dt.datetime(2026, 6, 27, 12, 0, tzinfo=dt.timezone.utc)

    returned = typing_nervous_adapters.store_latest_history_and_index(
        payload,
        write_latest=True,
        latest_path=latest,
        history_root=history_root,
        index_path=index_path,
        index_document=index,
        when=when,
        group="definitely-missing-abyss-test-group",
    )

    assert returned is payload
    assert "write_errors" not in returned
    assert json.loads(latest.read_text(encoding="utf-8")) == payload
    assert json.loads(index_path.read_text(encoding="utf-8")) == index
    daily_path = typing_nervous_adapters.daily_jsonl_path(history_root, when)
    history_lines = daily_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in history_lines] == [payload]


def test_store_latest_history_and_index_respects_write_disabled(tmp_path):
    latest = tmp_path / "typing" / "latest.json"
    payload = {"schema": "test_typing_payload_v1", "ok": True}

    returned = typing_nervous_adapters.store_latest_history_and_index(
        payload,
        write_latest=False,
        latest_path=latest,
        history_root=tmp_path / "typing" / "history",
    )

    assert returned == payload
    assert not latest.exists()


def test_read_latest_document_reports_missing_with_read_schema(tmp_path):
    path = tmp_path / "missing.json"

    document = typing_nervous_adapters.read_latest_document(
        path,
        "test_read_schema_v1",
        version="0.test",
        now=lambda: "2026-06-27T12:00:00+00:00",
    )

    assert document == {
        "schema": "test_read_schema_v1",
        "version": "0.test",
        "generated_at": "2026-06-27T12:00:00+00:00",
        "ok": False,
        "path": str(path),
        "error": "missing",
    }


def test_read_latest_document_preserves_typing_ok_absence_when_requested(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"schema": "source_v1", "status": "captured"}) + "\n", encoding="utf-8")

    document = typing_nervous_adapters.read_latest_document(
        path,
        "test_typing_latest_read_v1",
        version="0.test",
        now=lambda: "2026-06-27T12:01:00+00:00",
        default_existing_ok=None,
    )

    assert document == {
        "schema": "source_v1",
        "status": "captured",
        "read_schema": "test_typing_latest_read_v1",
        "read_at": "2026-06-27T12:01:00+00:00",
    }


def test_read_recent_jsonl_records_reads_newest_files_and_preserves_parse_errors(tmp_path):
    root = tmp_path / "typing-events"
    older = root / "2026" / "06" / "2026-06-26.jsonl"
    newer = root / "2026" / "06" / "2026-06-27.jsonl"
    older.parent.mkdir(parents=True)
    older.write_text(
        "\n".join([
            json.dumps({"event_id": "old-1", "generated_at": "2026-06-26T10:00:00+00:00"}),
            json.dumps({"event_id": "old-2", "generated_at": "2026-06-26T11:00:00+00:00"}),
        ])
        + "\n",
        encoding="utf-8",
    )
    newer.write_text(
        "\n".join([
            json.dumps({"event_id": "new-1", "generated_at": "2026-06-27T10:00:00+00:00"}),
            "{not-json",
            json.dumps({"event_id": "new-2", "generated_at": "2026-06-27T11:00:00+00:00"}),
        ])
        + "\n",
        encoding="utf-8",
    )

    records, errors = typing_nervous_adapters.read_recent_jsonl_records(root, limit=3)

    assert [record["event_id"] for record in records] == ["new-2", "new-1", "old-2"]
    assert len(errors) == 1
    assert errors[0]["path"] == str(newer)
    assert errors[0]["line"] == 2


def test_read_recent_jsonl_records_for_source_tracks_scan_exhaustion(tmp_path):
    root = tmp_path / "typing-events"
    path = root / "2026" / "06" / "2026-06-27.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join([
            json.dumps({"event_id": "one", "source_adapter": "other"}),
            json.dumps({"event_id": "two", "source_adapter": "target"}),
            json.dumps({"event_id": "three", "source_adapter": "other"}),
        ])
        + "\n",
        encoding="utf-8",
    )

    records, errors, scan = typing_nervous_adapters.read_recent_jsonl_records_for_source(
        root,
        "target",
        limit=2,
        max_scan_records=2,
    )

    assert records == [{"event_id": "two", "source_adapter": "target"}]
    assert errors == []
    assert scan == {
        "source_adapter": "target",
        "limit": 2,
        "max_scan_records": 2,
        "scanned_records": 2,
        "files_scanned": 1,
        "exhausted": True,
    }


def test_codex_session_tail_files_includes_recent_state_files_inside_sessions_root(tmp_path):
    root = tmp_path / ".codex" / "sessions"
    recent = root / "2026" / "06" / "session-new-11111111-1111-1111-1111-111111111111.jsonl"
    state_kept = root / "2026" / "06" / "session-old-22222222-2222-2222-2222-222222222222.jsonl"
    outside = tmp_path / "outside-33333333-3333-3333-3333-333333333333.jsonl"
    recent.parent.mkdir(parents=True)
    recent.write_text("{}\n", encoding="utf-8")
    state_kept.write_text("{}\n", encoding="utf-8")
    outside.write_text("{}\n", encoding="utf-8")
    os.utime(state_kept, (100.0, 100.0))
    os.utime(recent, (200.0, 200.0))
    now = dt.datetime(2026, 6, 27, 12, 0, tzinfo=dt.timezone.utc)
    state = {
        "files": {
            str(state_kept): {"last_user_timestamp": "2026-06-27T11:59:00+00:00"},
            str(outside): {"last_user_timestamp": "2026-06-27T11:59:00+00:00"},
            str(root / "missing.jsonl"): {"last_user_timestamp": "2026-06-27T11:59:00+00:00"},
            str(root / "stale.jsonl"): {"last_user_timestamp": "2026-06-25T11:59:00+00:00"},
        }
    }

    selected = typing_nervous_adapters.codex_session_tail_files(root, limit=1, state=state, now=now)

    assert selected == [recent, state_kept]


def test_codex_session_tail_path_candidates_reads_incremental_bytes(tmp_path):
    path = tmp_path / "session-44444444-4444-4444-4444-444444444444.jsonl"
    first = json.dumps({"type": "turn_context"}) + "\n"
    second = json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "hello"}}) + "\n"
    third = json.dumps({"type": "event_msg", "payload": {"type": "agent_message", "message": "ignored"}}) + "\n"
    path.write_text(first + second + third, encoding="utf-8")
    stat = path.stat()
    previous = {
        "line_count": 1,
        "file_size": len(first.encode("utf-8")),
        "mtime_ns": stat.st_mtime_ns - 1,
        "byte_offset": len(first.encode("utf-8")),
    }

    candidates, report, errors = typing_nervous_adapters.codex_session_tail_path_candidates(
        path,
        previous,
        initial_tail_lines=20,
        recovery_tail_lines=20,
    )

    assert errors == []
    assert [line_no for line_no, _ in candidates] == [2, 3]
    assert json.loads(candidates[0][1])["payload"]["message"] == "hello"
    assert report["scan_mode"] == "incremental_bytes"
    assert report["line_count"] == 3
    assert report["since_line"] == 1
    assert report["byte_offset"] == stat.st_size
    assert report["candidate_lines"] == 2


def test_codex_session_tail_path_candidates_reports_stat_failure(tmp_path):
    missing = tmp_path / "missing-session.jsonl"

    candidates, report, errors = typing_nervous_adapters.codex_session_tail_path_candidates(
        missing,
        {"line_count": 7},
        initial_tail_lines=20,
        recovery_tail_lines=20,
    )

    assert candidates == []
    assert len(errors) == 1
    assert errors[0]["path"] == str(missing)
    assert report["scan_mode"] == "stat_failed"
    assert report["line_count"] == 7
    assert report["candidate_lines"] == 0
