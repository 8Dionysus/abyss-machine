from __future__ import annotations

import time
from pathlib import Path

from abyss_machine import typing_saved_text_adapters


def _policy(root: Path) -> dict:
    return {
        "enabled": True,
        "roots": [str(root)],
        "changed_within_sec": 3600,
        "max_file_bytes": 262144,
        "max_files_per_scan": 10,
        "max_roots": 8,
        "include_extensions": [".md", ".txt"],
        "include_names": ["AGENTS.md"],
        "deny_path_tokens": [".env", "secret"],
        "exclude_path_tokens": ["/.git/", "/.aoa/"],
        "low_signal_artifact_path_tokens": ["/node_modules/"],
        "exclude_dir_names": [".git"],
    }


def test_saved_text_scan_candidates_detects_recent_file_and_state_dedupe(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    note = root / "note.md"
    note.write_text("saved text scan fixture", encoding="utf-8")
    now_ts = note.stat().st_mtime + 1

    candidates, skips = typing_saved_text_adapters.saved_text_scan_candidates(
        _policy(root),
        {"files": {}},
        now_ts=now_ts,
    )

    assert [item["path"] for item in candidates] == [str(note)]
    assert candidates[0]["root"] == str(root)
    assert candidates[0]["name"] == "note.md"
    assert candidates[0]["suffix"] == ".md"
    assert candidates[0]["sha256"]
    assert candidates[0]["text"] == "saved text scan fixture"
    assert skips[-1] == {"reason": "scan_seen_files", "count": 1}

    repeated, repeated_skips = typing_saved_text_adapters.saved_text_scan_candidates(
        _policy(root),
        {"files": {str(note): {"sha256": candidates[0]["sha256"]}}},
        now_ts=now_ts,
    )

    assert repeated == []
    assert repeated_skips[-1] == {"reason": "scan_seen_files", "count": 1}


def test_saved_text_scan_denies_sensitive_path_before_read(tmp_path, monkeypatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    secret = root / ".env"
    secret.write_text("OPENAI_API_KEY=synthetic", encoding="utf-8")

    def fail_read_bytes(self: Path) -> bytes:
        raise AssertionError(f"read_bytes should not run for {self}")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)

    candidates, skips = typing_saved_text_adapters.saved_text_scan_candidates(
        _policy(root),
        {"files": {}},
        now_ts=secret.stat().st_mtime + 1,
    )

    assert candidates == []
    assert any(item.get("path") == str(secret) and item.get("reason") == "sensitive_path" for item in skips)


def test_saved_text_scan_respects_file_limit(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    first = root / "a.md"
    second = root / "b.md"
    first.write_text("first fixture", encoding="utf-8")
    second.write_text("second fixture", encoding="utf-8")
    now_ts = max(item.stat().st_mtime for item in (first, second)) + 1
    policy = _policy(root)
    policy["max_files_per_scan"] = 1

    candidates, skips = typing_saved_text_adapters.saved_text_scan_candidates(
        policy,
        {"files": {}},
        now_ts=now_ts,
    )

    assert len(candidates) == 1
    assert candidates[0]["path"] in {str(first), str(second)}
    assert skips[-1]["reason"] == "scan_seen_files"
    assert skips[-1]["count"] >= 1


def test_saved_text_scan_skips_low_signal_paths(tmp_path) -> None:
    root = tmp_path / "workspace"
    low_signal_dir = root / "node_modules"
    low_signal_dir.mkdir(parents=True)
    low_signal = low_signal_dir / "package.txt"
    low_signal.write_text("generated package fixture", encoding="utf-8")

    candidates, skips = typing_saved_text_adapters.saved_text_scan_candidates(
        _policy(root),
        {"files": {}},
        now_ts=low_signal.stat().st_mtime + 1,
    )

    assert candidates == []
    assert any(
        item.get("path") in {str(low_signal_dir), str(low_signal)}
        and item.get("reason") == "excluded_low_signal_artifact_path"
        for item in skips
    )


def test_saved_text_scan_checkpoints_bounded_directory_work(tmp_path) -> None:
    root = tmp_path / "workspace"
    first_dir = root / "a"
    second_dir = root / "b"
    first_dir.mkdir(parents=True)
    second_dir.mkdir()
    first = first_dir / "first.md"
    second = second_dir / "second.md"
    first.write_text("first checkpoint fixture", encoding="utf-8")
    second.write_text("second checkpoint fixture", encoding="utf-8")
    now_ts = max(first.stat().st_mtime, second.stat().st_mtime) + 1
    policy = _policy(root)
    policy.update({
        "max_directories_per_scan": 1,
        "max_entries_per_scan": 100,
        "max_scan_seconds": 30,
        "max_pending_directories": 20,
    })
    state: dict = {"files": {}}
    discovered: set[str] = set()

    for _ in range(5):
        progress: dict = {}
        candidates, _ = typing_saved_text_adapters.saved_text_scan_candidates(
            policy,
            state,
            now_ts=now_ts,
            progress=progress,
        )
        for item in candidates:
            discovered.add(item["path"])
            state["files"][item["path"]] = {"sha256": item["sha256"]}
        assert state["scan_cursor"] == progress["cursor"]
        assert progress["summary"]["processed_directories"] <= 1
        assert progress["summary"]["pending_directories"] <= 20
        if discovered == {str(first), str(second)}:
            break

    assert discovered == {str(first), str(second)}


def test_saved_text_scan_bounds_skip_samples_but_keeps_counts(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    for index in range(20):
        (root / f".env{index}").write_text("synthetic", encoding="utf-8")
    policy = _policy(root)
    policy.update({
        "max_skip_records": 3,
        "max_entries_per_scan": 100,
        "max_scan_seconds": 30,
    })
    progress: dict = {}

    candidates, skips = typing_saved_text_adapters.saved_text_scan_candidates(
        policy,
        {"files": {}},
        now_ts=time.time(),
        progress=progress,
    )

    assert candidates == []
    assert len(skips) == 4  # Two samples, compact scan summary, and seen-files counter.
    assert progress["summary"]["skip_counts"]["sensitive_path"] == 20


def test_saved_text_scan_stops_streaming_directory_at_entry_budget(tmp_path, monkeypatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()

    class FakeEntry:
        def __init__(self, index: int) -> None:
            self.name = f"entry-{index:05d}"
            self.path = str(root / self.name)

        def is_dir(self, *, follow_symlinks: bool) -> bool:
            return False

        def is_file(self, *, follow_symlinks: bool) -> bool:
            return False

    class FakeScandir:
        def __init__(self) -> None:
            self.yielded = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def __iter__(self):
            return self

        def __next__(self):
            if self.yielded >= 1000:
                raise StopIteration
            entry = FakeEntry(self.yielded)
            self.yielded += 1
            return entry

    scandir = FakeScandir()
    monkeypatch.setattr(typing_saved_text_adapters.os, "scandir", lambda path: scandir)
    policy = _policy(root)
    policy.update({"max_entries_per_scan": 100, "max_scan_seconds": 30})
    progress: dict = {}

    candidates, _ = typing_saved_text_adapters.saved_text_scan_candidates(
        policy,
        {"files": {}},
        now_ts=time.time(),
        progress=progress,
    )

    assert candidates == []
    assert scandir.yielded == 101
    assert progress["summary"]["seen_entries"] == 100
    assert progress["summary"]["stop_reason"] == "entry_budget"


def test_saved_text_scan_prunes_state_to_bounded_recent_set(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    policy = _policy(root)
    policy.update({"max_state_files": 1000, "max_scan_seconds": 30})
    state = {
        "files": {
            f"/workspace/{index}.md": {"sha256": str(index), "mtime_ns": index}
            for index in range(1005)
        }
    }
    progress: dict = {}

    typing_saved_text_adapters.saved_text_scan_candidates(
        policy,
        state,
        now_ts=time.time(),
        progress=progress,
    )

    assert len(state["files"]) == 1000
    assert "/workspace/0.md" not in state["files"]
    assert "/workspace/1004.md" in state["files"]
    assert progress["summary"]["state_files_pruned"] == 5


def test_saved_text_decode_rejects_binary_empty_and_large_files(tmp_path) -> None:
    binary = tmp_path / "binary.txt"
    empty = tmp_path / "empty.txt"
    large = tmp_path / "large.txt"
    binary.write_bytes(b"abc\x00def")
    empty.write_text("   \n\t", encoding="utf-8")
    large.write_text("x" * 20, encoding="utf-8")

    assert typing_saved_text_adapters.saved_text_decode(binary, 1024)[2] == "binary_or_nul_bytes"
    assert typing_saved_text_adapters.saved_text_decode(empty, 1024)[2] == "empty_or_whitespace"
    assert typing_saved_text_adapters.saved_text_decode(large, 8)[2] == "too_large"


def test_saved_text_scan_document_and_event_projection_are_public_safe(tmp_path) -> None:
    item = {
        "path": str(tmp_path / "note.md"),
        "root": str(tmp_path),
        "name": "note.md",
        "suffix": ".md",
        "size_bytes": 24,
        "mtime": "2026-06-27T00:00:00+00:00",
        "mtime_ns": 1,
        "sha256": "hash",
        "text": "private fixture text",
    }
    ingest_kwargs = typing_saved_text_adapters.saved_text_ingest_kwargs(item)
    event_summary = typing_saved_text_adapters.saved_text_event_summary(
        item,
        {
            "event_id": "evt",
            "status": "captured",
            "text": {"text_length": 20, "text_chars_stored": 20, "redaction": {"matches": 0}},
            "capture_gate": {"decision": "allow_text"},
            "causal_context": {"recipient": {"kind": "file"}},
        },
    )
    document = typing_saved_text_adapters.saved_text_scan_document(
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-27T00:00:00+00:00",
        candidates=[item],
        events=[event_summary],
        skips=[{"reason": "scan_seen_files", "count": 1}],
        saved_policy={"roots": [str(tmp_path)], "changed_within_sec": 5, "max_file_bytes": 50, "max_files_per_scan": 2},
        state_error=None,
        paths={"latest": "/var/lib/abyss-machine/typing/saved-text/latest.json"},
    )

    assert ingest_kwargs["source"] == typing_saved_text_adapters.SAVED_TEXT_SOURCE
    assert ingest_kwargs["text"] == "private fixture text"
    assert ingest_kwargs["include_text_in_context_probe"] is False
    assert event_summary["capture_gate"]["decision"] == "allow_text"
    assert "text" not in event_summary
    assert document["schema"] == "abyss_machine_typing_saved_text_scan_v1"
    assert document["summary"] == {"candidates": 1, "events": 1, "primed": 0, "skips": 1, "state_error": None}
    assert document["policy"]["raw_keylogging"] is False
    assert document["policy"]["deny_sensitive_paths"] is True
    assert document["events"] == [event_summary]
    assert document["scan"] == {}
    assert all("private fixture text" not in str(value) for value in document.values())


def test_saved_text_disabled_document_preserves_non_capture_policy() -> None:
    document = typing_saved_text_adapters.saved_text_disabled_document(
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-27T00:00:00+00:00",
    )

    assert document["ok"] is True
    assert document["status"] == "disabled"
    assert document["source_adapter"] == typing_saved_text_adapters.SAVED_TEXT_SOURCE
    assert document["policy"] == {
        "raw_keylogging": False,
        "password_fields_captured": False,
        "automatic_action": False,
    }


def test_saved_text_process_scan_candidates_routes_ingest_and_state_updates(tmp_path) -> None:
    item = {
        "path": str(tmp_path / "note.md"),
        "root": str(tmp_path),
        "name": "note.md",
        "suffix": ".md",
        "size_bytes": 24,
        "mtime": "2026-06-27T00:00:00+00:00",
        "mtime_ns": 1,
        "sha256": "hash",
        "text": "private fixture text",
    }
    seen = []

    def ingest(candidate):
        seen.append(dict(candidate))
        return {
            "event_id": "evt",
            "status": "captured",
            "text": {"text_length": 20, "text_chars_stored": 20, "redaction": {"matches": 0}},
            "capture_gate": {"decision": "allow_text"},
            "causal_context": {"recipient": {"kind": "file"}},
        }

    events, updates = typing_saved_text_adapters.saved_text_process_scan_candidates(
        [item],
        generated_at="2026-06-27T00:00:00+00:00",
        prime_state=False,
        ingest_item=ingest,
    )

    assert seen == [item]
    assert events[0]["event_id"] == "evt"
    assert events[0]["path"] == item["path"]
    assert "text" not in events[0]
    assert updates[item["path"]]["sha256"] == "hash"
    assert updates[item["path"]]["last_seen_at"] == "2026-06-27T00:00:00+00:00"

    def fail_ingest(candidate):  # pragma: no cover - assertion path
        raise AssertionError(f"prime-state should not ingest {candidate}")

    primed_events, primed_updates = typing_saved_text_adapters.saved_text_process_scan_candidates(
        [item],
        generated_at="2026-06-27T00:01:00+00:00",
        prime_state=True,
        ingest_item=fail_ingest,
    )

    assert primed_events == []
    assert primed_updates[item["path"]]["primed"] is True


def test_saved_text_state_document_and_write_outputs_use_fakeable_ports(tmp_path) -> None:
    state = typing_saved_text_adapters.saved_text_state_document(
        {"files": {"old.md": {"sha256": "old"}}},
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-27T00:00:00+00:00",
        file_updates={"new.md": {"sha256": "new", "last_seen_at": "2026-06-27T00:00:00+00:00"}},
    )
    writes = []

    def write_json(path, data, mode):
        writes.append((path.name, dict(data), mode))
        if path.name == "latest.json":
            return {"path": str(path), "error": "boom"}
        return None

    result = typing_saved_text_adapters.saved_text_write_scan_outputs(
        state=state,
        data={"schema": "abyss_machine_typing_saved_text_scan_v1", "ok": True},
        state_path=tmp_path / "state.json",
        latest_path=tmp_path / "latest.json",
        index_path=tmp_path / "index.json",
        write_json=write_json,
        index_document=lambda: {"schema": "abyss_machine_typing_index_v1"},
    )

    assert state["files"]["old.md"]["sha256"] == "old"
    assert state["files"]["new.md"]["sha256"] == "new"
    assert [item[0] for item in writes] == ["state.json", "latest.json", "index.json"]
    assert all(item[2] == 0o664 for item in writes)
    assert writes[2][1]["schema"] == "abyss_machine_typing_index_v1"
    assert result["ok"] is False
    assert result["write_errors"] == [{"path": str(tmp_path / "latest.json"), "error": "boom"}]


def test_saved_text_state_document_filters_malformed_stale_file_entries() -> None:
    state = typing_saved_text_adapters.saved_text_state_document(
        {"files": {"old.md": {"sha256": "old"}, "broken.md": None, "string.md": "bad"}},
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-27T00:00:00+00:00",
        file_updates={"new.md": {"sha256": "new", "last_seen_at": "2026-06-27T00:00:00+00:00"}},
    )

    assert state["files"] == {
        "old.md": {"sha256": "old"},
        "new.md": {"sha256": "new", "last_seen_at": "2026-06-27T00:00:00+00:00"},
    }


def test_saved_text_scan_latest_status_document_uses_supplied_live_facts(tmp_path) -> None:
    latest = {
        "ok": True,
        "status": "ok",
        "generated_at": "2026-06-27T00:00:00+00:00",
        "summary": {"candidates": 1, "events": 1, "primed": 0, "skips": 0, "state_error": None},
        "events": [{"event_id": "evt"}],
        "roots": [str(tmp_path)],
        "limits": {"max_files_per_scan": 10},
        "policy": {
            "raw_keylogging": False,
            "committed_text_only": True,
            "password_fields_captured": False,
            "global_keyboard_hook": False,
            "automatic_action": False,
            "deny_sensitive_paths": True,
            "redaction": "typing_ingest",
        },
    }
    active_timer = {"is_active": True, "is_enabled": True}
    service = {"is_active": False}

    status = typing_saved_text_adapters.saved_text_scan_latest_status_document(
        latest=latest,
        latest_error=None,
        timer=active_timer,
        service=service,
        generated_at="2026-06-27T00:00:05+00:00",
        max_age_sec=600,
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="fixture",
        age_seconds_from_iso=lambda _value: 5,
    )

    assert status["ok"] is True
    assert status["status"] == "ok"
    assert status["summary"]["timer_active"] is True
    assert status["latest"]["events"] == [{"event_id": "evt"}]
    assert status["policy"]["automatic_action"] is False

    bad_policy = dict(latest)
    bad_policy["policy"] = dict(latest["policy"], automatic_action=True)
    policy_status = typing_saved_text_adapters.saved_text_scan_latest_status_document(
        latest=bad_policy,
        latest_error=None,
        timer=active_timer,
        service=service,
        generated_at="2026-06-27T00:00:05+00:00",
        max_age_sec=600,
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="fixture",
        age_seconds_from_iso=lambda _value: 5,
    )

    assert policy_status["ok"] is False
    assert policy_status["status"] == "policy_violation"
