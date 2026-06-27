from __future__ import annotations

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
        item.get("path") == str(low_signal)
        and item.get("reason") == "excluded_low_signal_artifact_path"
        for item in skips
    )


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
