from __future__ import annotations

import json
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine.nervous_index import (
    allowed_source_ids,
    build_index_build_document,
    build_index_derived_refresh_summary,
    build_index_disabled_result,
    build_index_fts_unavailable_result,
    build_index_global_pause_refused_result,
    build_index_meta_values,
    build_index_projection,
    build_index_semantic_lock_deferred_result,
    chunks_from_record,
    connect_db,
    counts,
    document_rows_from_record,
    enabled_index_source_ids,
    enabled_safe_source_ids,
    fact_source_id,
    initialize_db,
    index_source_files,
    jsonl_files,
    load_jsonl_records,
    load_jsonl_records_with_metadata,
    load_source_records,
    freshness_document,
    nervous_index_bounded_validate_from_status,
    parse_duration_seconds,
    nervous_index_schema_sql,
    parse_jsonl_records,
    parse_jsonl_records_with_metadata,
    read_meta,
    record_is_safe_for_index,
    replace_index_contents,
    scan_index,
    search_index,
    search_match_query,
    search_options,
    search_refused_result,
    sort_source_records,
    status_document,
    validation_check,
    validation_document,
    vacuum_error_result,
    vacuum_missing_db_result,
    vacuum_refused_result,
    vacuum_start_document,
    vacuum_success_result,
    with_index_error,
    with_index_semantic_lock_deferred,
    with_index_write_success,
)


def test_nervous_index_schema_sql_is_module_owned_contract() -> None:
    schema = nervous_index_schema_sql()

    assert "CREATE TABLE IF NOT EXISTS documents" in schema
    assert "CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5" in schema
    assert "source_ids_json TEXT NOT NULL" in schema


def test_nervous_index_source_discovery_and_jsonl_parsing_are_module_owned(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    fact_path = facts_root / "2026" / "06" / "2026-06-25.jsonl"
    event_path = events_root / "2026" / "06" / "2026-06-25.jsonl"
    ignored_path = facts_root / "2026-06-25.jsonl"
    fact_path.parent.mkdir(parents=True)
    event_path.parent.mkdir(parents=True)
    fact_path.write_text('{"schema":"s","generated_at":"2026-06-25T10:00:00+00:00"}\n', encoding="utf-8")
    event_path.write_text('{"schema":"s","generated_at":"2026-06-25T11:00:00+00:00"}\n', encoding="utf-8")
    ignored_path.write_text('{"schema":"ignored"}\n', encoding="utf-8")

    assert jsonl_files(facts_root) == [fact_path]
    assert index_source_files((events_root, facts_root)) == sorted([event_path, fact_path])

    records, errors = parse_jsonl_records(
        "/tmp/source.jsonl",
        '{"schema":"ok"}\n\n[1,2]\n{broken\n',
    )
    assert records == [{"schema": "ok"}]
    assert [item["line"] for item in errors] == [3, 4]
    assert errors[0]["error"] == "record is not an object"

    loaded, loaded_errors = load_jsonl_records(fact_path)
    assert loaded_errors == []
    assert loaded == [{"schema": "s", "generated_at": "2026-06-25T10:00:00+00:00"}]

    items, metadata_errors = parse_jsonl_records_with_metadata(
        "/tmp/source.jsonl",
        '{"schema":"late","generated_at":"2026-06-25T12:00:00+00:00"}\n'
        '{"schema":"early","generated_at":"2026-06-25T09:00:00+00:00"}\n',
        source_sha256="source-hash",
    )
    assert metadata_errors == []
    assert items[0]["record_sha256"] != items[1]["record_sha256"]
    assert items[0]["source_sha256"] == "source-hash"
    assert [item["record"]["schema"] for item in sort_source_records(items)] == ["early", "late"]

    loaded_items, loaded_metadata_errors = load_jsonl_records_with_metadata(fact_path)
    assert loaded_metadata_errors == []
    assert loaded_items[0]["source_sha256"]
    skipped_hash_items, skipped_hash_errors = load_jsonl_records_with_metadata(fact_path, max_hash_bytes=3)
    assert skipped_hash_errors == []
    assert skipped_hash_items[0]["source_sha256"] is None

    loaded_sources, load_errors = load_source_records([event_path, fact_path])
    assert load_errors == []
    assert [item["record"]["generated_at"] for item in loaded_sources] == [
        "2026-06-25T10:00:00+00:00",
        "2026-06-25T11:00:00+00:00",
    ]


def test_nervous_index_bounded_validation_uses_status_without_full_scan() -> None:
    payload = nervous_index_bounded_validate_from_status(
        {
            "ok": True,
            "ready": True,
            "warnings": ["index stale: fixture"],
            "paths": {"db": "/srv/abyss-machine/nervous/indexes/sqlite/nervous.db"},
            "counts": {"documents": 3, "chunks": 9, "fts_chunks": 9},
            "freshness": {"stale": True, "lag_sec": 120},
        },
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
    )

    assert payload["schema"] == "abyss_machine_nervous_index_validate_bounded_v1"
    assert payload["version"] == "test"
    assert payload["generated_at"] == "2026-06-25T00:00:00+00:00"
    assert payload["ok"] is True
    assert payload["summary"]["bounded"] is True
    assert payload["summary"]["full_scan"] is False
    assert payload["summary"]["warnings"] == 2
    assert payload["summary"]["documents"] == 3
    assert payload["policy"]["full_index_scan"] is False


def test_nervous_index_full_validation_document_is_module_owned_contract() -> None:
    assert validation_check("ok", "sample", "sample check") == {
        "level": "ok",
        "key": "sample",
        "message": "sample check",
    }

    payload = validation_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:20:00+00:00",
        db_path="/srv/abyss-machine/nervous/indexes/sqlite/nervous.db",
        config={"enabled": True},
        config_path="/etc/abyss-machine/nervous-index.json",
        config_exists=True,
        fts_ok=True,
        fts_error=None,
        storage_routed=True,
        storage_root="/srv/abyss-machine",
        symlink_tail=False,
        db_exists=True,
        counts={
            "documents": 2,
            "chunks": 3,
            "fts_chunks": 3,
            "meta": {"schema": "abyss_machine_nervous_search_index_v1"},
        },
        freshness={"stale": False, "lag_sec": 0},
        allowed_source_ids={"heartbeat", "nervous_events", "nervous_episodes", "browser_active_tab"},
        scan={
            "indexed_source_ids": ["browser_active_tab", "nervous_events", "nervous_episodes"],
            "documents_by_schema": {
                "abyss_machine_nervous_event_v1": 1,
                "abyss_machine_nervous_episode_v1": 1,
            },
            "smoke_results": 1,
        },
        scan_error=None,
        private_source_ids={"browser_active_tab"},
        event_records=1,
        episode_records=1,
    )

    checks = {item["key"]: item for item in payload["checks"]}
    assert payload["schema"] == "abyss_machine_nervous_index_validate_v1"
    assert payload["ok"] is True
    assert payload["summary"] == {
        "fails": 0,
        "warnings": 0,
        "checks": 16,
        "documents": 2,
        "chunks": 3,
        "fts_chunks": 3,
        "documents_by_schema": {
            "abyss_machine_nervous_event_v1": 1,
            "abyss_machine_nervous_episode_v1": 1,
        },
    }
    assert checks["private_connector_sources"]["details"] == {"private_present": ["browser_active_tab"]}
    assert checks["source_policy"]["level"] == "ok"
    assert checks["events_indexed"]["level"] == "ok"
    assert checks["episodes_indexed"]["level"] == "ok"


def test_nervous_index_full_validation_document_failure_shape_is_explicit() -> None:
    payload = validation_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:20:00+00:00",
        db_path="/srv/abyss-machine/nervous/indexes/sqlite/nervous.db",
        config={"_load_error": "broken json"},
        config_path="/etc/abyss-machine/nervous-index.json",
        config_exists=False,
        fts_ok=False,
        fts_error="no such module: fts5",
        storage_routed=False,
        storage_root="/srv/abyss-machine",
        symlink_tail=True,
        db_exists=False,
        counts={
            "error": "unable to open database file",
            "documents": 0,
            "chunks": 1,
            "fts_chunks": 0,
            "meta": {"schema": "wrong_schema"},
        },
        freshness={"stale": True, "lag_sec": 9999},
        allowed_source_ids={"heartbeat"},
        scan={
            "indexed_source_ids": ["disabled_source"],
            "documents_by_schema": {},
            "smoke_results": 0,
        },
        scan_error="scan failed",
        private_source_ids=set(),
        event_records=1,
        episode_records=1,
    )

    fail_keys = {item["key"] for item in payload["checks"] if item["level"] == "fail"}
    warn_keys = {item["key"] for item in payload["checks"] if item["level"] == "warn"}
    assert payload["ok"] is False
    assert {
        "sqlite_fts5",
        "config_load",
        "storage_route",
        "symlink_tail",
        "db_exists",
        "db_open",
        "schema",
        "fts_count",
        "source_scan",
        "source_policy",
        "fts_smoke",
        "events_indexed",
        "episodes_indexed",
    }.issubset(fail_keys)
    assert {"config_file", "freshness", "documents"}.issubset(warn_keys)
    assert payload["summary"]["fails"] == len(fail_keys)
    assert payload["summary"]["warnings"] == len(warn_keys)


def test_nervous_index_search_options_and_refusal_are_module_owned_contracts() -> None:
    options = search_options(
        {"search": {"max_limit": 20, "default_limit": 7, "snippet_tokens": 9}},
        requested_limit=50,
        requested_order="ranked",
    )
    defaults = search_options({}, requested_limit=0, requested_order="surprising")
    refusal = search_refused_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:25:00+00:00",
    )

    assert options == {
        "final_limit": 20,
        "order": "ranked",
        "max_limit": 20,
        "default_limit": 7,
        "snippet_tokens": 9,
        "scan_limit": 320,
    }
    assert defaults["final_limit"] == 12
    assert defaults["order"] == "latest"
    assert defaults["snippet_tokens"] == 18
    assert refusal == {
        "schema": "abyss_machine_nervous_search_v1",
        "version": "test-version",
        "generated_at": "2026-06-25T13:25:00+00:00",
        "ok": False,
        "refused": True,
        "error": "global_pause is active; search is refused",
    }


def test_nervous_index_status_and_freshness_contracts_are_module_owned() -> None:
    freshness = freshness_document(
        meta={"built_at": "2026-06-25T11:00:00+00:00", "records_seen": "2"},
        config={"automation": {"interval": "45m"}},
        latest_fact={
            "schema": "abyss_machine_nervous_fact_snapshot_v1",
            "generated_at": "2026-06-25T10:30:00+00:00",
        },
        latest_event={
            "schema": "abyss_machine_nervous_event_v1",
            "generated_at": "2026-06-25T12:00:00+00:00",
            "observed_at": "2026-06-25T12:00:00+00:00",
        },
        latest_episode={
            "schema": "abyss_machine_nervous_episode_v1",
            "generated_at": "2026-06-25T11:40:00+00:00",
            "start_at": "2026-06-25T11:35:00+00:00",
        },
        history_records=9,
        history_records_by_layer={"facts": 2, "events": 4, "episodes": 3},
        history_parse_errors=1,
        now=dt.datetime.fromisoformat("2026-06-25T13:00:00+00:00"),
    )
    status = status_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:01:00+00:00",
        config={"enabled": True, "backend": "sqlite_fts5", "db_path": "/wrong/db.sqlite3"},
        config_path="/etc/abyss-machine/nervous-index.json",
        config_exists=False,
        privacy={"global_pause": False, "private_mode": True},
        sources={
            "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
            "deferred_until_privacy_controls": {"browser_active_tab": {"enabled": True, "allowed": True}},
        },
        sqlite_version="3.test",
        fts_ok=True,
        fts_error=None,
        latest=None,
        latest_error="missing latest",
        counts={"documents": 2, "chunks": 4},
        freshness=freshness,
        db_path="/var/lib/abyss-machine/nervous/indexes/sqlite/nervous.db",
        db_exists=False,
        root_path="/var/lib/abyss-machine/nervous/indexes/sqlite",
        schema_path="/var/lib/abyss-machine/nervous/indexes/sqlite/schema.sql",
        latest_path="/var/lib/abyss-machine/nervous/indexes/sqlite/latest.json",
        service_status={"is_active": False},
        timer_status={"is_active": True},
    )

    assert parse_duration_seconds("45m") == 2700.0
    assert parse_duration_seconds("2h") == 7200.0
    assert parse_duration_seconds("bad", default=12.5) == 12.5
    assert freshness["lag_sec"] == 3600.0
    assert freshness["index_age_sec"] == 7200.0
    assert freshness["stale"] is True
    assert freshness["records_lag"] == 7
    assert freshness["records_lag_stale"] is True
    assert freshness["history_records_by_layer"] == {"facts": 2, "events": 4, "episodes": 3}
    assert status["schema"] == "abyss_machine_nervous_index_status_v1"
    assert status["ok"] is True
    assert status["ready"] is False
    assert status["config"]["exists"] is False
    assert status["privacy"]["private_mode"] is True
    assert status["sources"]["enabled_safe_sources"] == ["abyss_machine_facts"]
    assert status["sources"]["deferred_sources"] == ["browser_active_tab"]
    assert status["sqlite"] == {"version": "3.test", "fts5": True, "error": None}
    assert status["latest"] == {
        "path": "/var/lib/abyss-machine/nervous/indexes/sqlite/latest.json",
        "error": "missing latest",
    }
    assert status["timer"]["scope"] == "user"
    assert "index config db_path differs from runtime path" in status["warnings"]
    assert "index database missing" in status["warnings"]
    assert any(item.startswith("index stale:") for item in status["warnings"])


def test_nervous_index_build_result_envelopes_are_module_owned() -> None:
    disabled = build_index_disabled_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        config_path="/etc/abyss-machine/nervous-index.json",
    )
    pause = build_index_global_pause_refused_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        privacy={"global_pause": True, "private_mode": True},
        privacy_state_path="/var/lib/abyss-machine/nervous/privacy/state.json",
    )
    fts = build_index_fts_unavailable_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        fts_error="no such module: fts5",
    )
    semantic_defer = build_index_semantic_lock_deferred_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        db_path="/var/lib/abyss-machine/nervous/indexes/sqlite/nervous.db",
        config_path="/etc/abyss-machine/nervous-index.json",
    )
    pre_write_defer = with_index_semantic_lock_deferred(
        {"ok": False, "summary": {"records_seen": 3}},
        checked_at="pre_write",
    )
    derived = build_index_derived_refresh_summary(
        {"ok": True, "summary": {"events": 7}},
        {"ok": False, "summary": {"episodes": 2}, "error": "episode refresh failed"},
    )

    assert disabled == {
        "schema": "abyss_machine_nervous_index_build_v1",
        "version": "test-version",
        "generated_at": "2026-06-25T12:00:00+00:00",
        "ok": False,
        "run_id": "index-run-1",
        "error": "index disabled by config",
        "config_path": "/etc/abyss-machine/nervous-index.json",
    }
    assert pause["refused"] is True
    assert pause["privacy"] == {
        "global_pause": True,
        "private_mode": True,
        "state_path": "/var/lib/abyss-machine/nervous/privacy/state.json",
    }
    assert fts["error"] == "SQLite FTS5 unavailable: no such module: fts5"
    assert semantic_defer["ok"] is True
    assert semantic_defer["policy"] == {
        "does_not_interrupt_semantic_build": True,
        "retry_via_timer": True,
    }
    assert pre_write_defer["summary"] == {"records_seen": 3}
    assert pre_write_defer["policy"]["checked_at"] == "pre_write"
    assert "became active before lexical index write" in pre_write_defer["reason"]
    assert derived == {
        "events": {"ok": True, "events": 7, "error": None},
        "episodes": {"ok": False, "episodes": 2, "error": "episode refresh failed"},
    }


def test_nervous_index_build_document_and_meta_contract_are_module_owned() -> None:
    projection = {
        "documents": [{"doc_id": "doc-a"}],
        "chunks": [{"chunk_id": "chunk-a"}],
        "skipped_records": [{"path": "/tmp/source.jsonl", "line": 2, "reason": "policy"}],
        "summary": {
            "records_seen": 2,
            "disabled_chunks": 1,
            "redactions": 3,
            "records_seen_by_schema": {"abyss_machine_nervous_event_v1": 2},
            "records_indexed_by_schema": {"abyss_machine_nervous_event_v1": 1},
        },
    }
    parse_errors = [{"path": "/tmp/source.jsonl", "line": 3, "error": "bad json"}]
    sources = {
        "state": {"last_change_id": "sources-change-1"},
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {"browser_active_tab": {"enabled": True, "allowed": True}},
    }
    data = build_index_build_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        started_at="2026-06-25T11:59:00+00:00",
        db_path="/var/lib/abyss-machine/nervous/indexes/sqlite/nervous.db",
        config_path="/etc/abyss-machine/nervous-index.json",
        privacy={"global_pause": False, "private_mode": True},
        sources=sources,
        enabled_sources={"abyss_machine_facts", "browser_active_tab", "nervous_events"},
        source_files=[Path("/var/lib/abyss-machine/nervous/events/2026/06/source.jsonl")],
        projection=projection,
        parse_errors=parse_errors,
        derived_refresh={"events": {"ok": True}},
    )
    meta = build_index_meta_values(
        schema_prefix="abyss_machine",
        version="test-version",
        run_id="index-run-1",
        built_at="2026-06-25T12:01:00+00:00",
        source_files=[Path("/var/lib/abyss-machine/nervous/events/2026/06/source.jsonl")],
        projection=projection,
        facts_root="/var/lib/abyss-machine/nervous/facts",
        events_root="/var/lib/abyss-machine/nervous/events",
        episodes_root="/var/lib/abyss-machine/nervous/episodes",
        source_state_change_id=data["sources"]["state_change_id"],
        privacy_state_change_id="privacy-change-1",
    )
    success = with_index_write_success(
        data,
        finished_at="2026-06-25T12:02:00+00:00",
        counts={"documents": 1, "chunks": 1},
        parse_errors=[],
    )
    failed_success = with_index_write_success(
        data,
        finished_at="2026-06-25T12:02:00+00:00",
        counts={"documents": 1, "chunks": 1},
        parse_errors=parse_errors,
    )
    errored = with_index_error(data, "another index build is already running")

    assert data["schema"] == "abyss_machine_nervous_index_build_v1"
    assert data["summary"]["source_files"] == 1
    assert data["summary"]["records_seen"] == 2
    assert data["summary"]["records_indexed"] == 1
    assert data["summary"]["chunks_indexed"] == 1
    assert data["summary"]["parse_errors"] == 1
    assert data["sources"]["enabled_sources"] == ["abyss_machine_facts", "browser_active_tab", "nervous_events"]
    assert data["sources"]["enabled_private_connector_sources"] == ["browser_active_tab"]
    assert data["sources"]["state_change_id"] == "sources-change-1"
    assert data["parse_errors"] == parse_errors
    assert data["skipped_records"] == projection["skipped_records"]
    assert meta["schema"] == "abyss_machine_nervous_search_index_v1"
    assert meta["tool_version"] == "test-version"
    assert meta["source_files"] == "1"
    assert meta["records_seen"] == "2"
    assert meta["records_indexed"] == "1"
    assert meta["chunks_indexed"] == "1"
    assert meta["source_state_change_id"] == "sources-change-1"
    assert meta["privacy_state_change_id"] == "privacy-change-1"
    assert json.loads(meta["records_seen_by_schema"]) == {"abyss_machine_nervous_event_v1": 2}
    assert success["ok"] is True
    assert success["finished_at"] == "2026-06-25T12:02:00+00:00"
    assert success["counts"] == {"documents": 1, "chunks": 1}
    assert failed_success["ok"] is False
    assert errored["error"] == "another index build is already running"


def test_nervous_index_vacuum_result_envelopes_are_module_owned() -> None:
    refused = vacuum_refused_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
    )
    started = vacuum_start_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:01:00+00:00",
        db_path="/srv/abyss-machine/storage/nervous/indexes/sqlite/nervous.db",
        before={"documents": 3},
    )
    missing = vacuum_missing_db_result(started)
    success = vacuum_success_result(started, after={"documents": 3, "chunks": 7})
    failed = vacuum_error_result(started, RuntimeError("busy"))

    assert refused == {
        "schema": "abyss_machine_nervous_index_vacuum_v1",
        "version": "test-version",
        "generated_at": "2026-06-25T12:00:00+00:00",
        "ok": False,
        "refused": True,
        "error": "global_pause is active; vacuum did not touch the database",
    }
    assert started == {
        "schema": "abyss_machine_nervous_index_vacuum_v1",
        "version": "test-version",
        "generated_at": "2026-06-25T12:01:00+00:00",
        "ok": False,
        "db_path": "/srv/abyss-machine/storage/nervous/indexes/sqlite/nervous.db",
        "before": {"documents": 3},
    }
    assert missing["error"] == "index database missing"
    assert success["ok"] is True
    assert success["after"] == {"documents": 3, "chunks": 7}
    assert failed["error"] == "busy"


def test_nervous_index_build_disabled_cli_branch_delegates_to_module_contract(monkeypatch) -> None:
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "nervous_change_id", lambda prefix: f"{prefix}-run-1")
    monkeypatch.setattr(cli, "nervous_index_config", lambda: {"enabled": False})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: {})

    result = cli.nervous_index_build(write_latest=False)

    assert result == build_index_disabled_result(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        config_path=cli.NERVOUS_INDEX_CONFIG_PATH,
    )


def test_nervous_index_build_global_pause_cli_branch_preserves_no_latest_write(monkeypatch) -> None:
    def fail_write_latest(data: dict) -> dict:
        raise AssertionError("global_pause refusal must not write latest")

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "nervous_change_id", lambda prefix: f"{prefix}-run-1")
    monkeypatch.setattr(cli, "nervous_index_config", lambda: {"enabled": True, "privacy": {"enforce_global_pause": True}})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": True, "private_mode": True})
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: {})
    monkeypatch.setattr(cli, "nervous_index_write_latest", fail_write_latest)

    result = cli.nervous_index_build(write_latest=True)

    assert result == build_index_global_pause_refused_result(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        privacy={"global_pause": True, "private_mode": True},
        privacy_state_path=cli.NERVOUS_PRIVACY_STATE_PATH,
    )


def test_nervous_index_status_cli_delegates_stable_shape_to_module_contract(monkeypatch, tmp_path: Path) -> None:
    latest = {"schema": "abyss_machine_nervous_index_build_v1", "ok": True}
    counts_doc = {"meta": {"built_at": "2026-06-25T11:00:00+00:00", "records_seen": "2"}, "documents": 1}
    config_path = tmp_path / "nervous-index.json"
    db_path = tmp_path / "nervous.db"
    root_path = tmp_path / "index-root"
    schema_path = tmp_path / "schema.sql"
    latest_path = tmp_path / "latest.json"
    config_path.write_text("{}", encoding="utf-8")
    db_path.write_text("", encoding="utf-8")
    config = {"enabled": True, "backend": "sqlite_fts5", "db_path": str(db_path)}
    privacy = {"global_pause": False, "private_mode": False}
    sources = {"safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}}}
    service_status = {"name": "service", "is_active": False}
    timer_status = {"name": "timer", "is_active": True}

    monkeypatch.setattr(cli, "NERVOUS_INDEX_CONFIG_PATH", config_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_ROOT", root_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: privacy)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: sources)
    monkeypatch.setattr(cli, "nervous_sqlite_fts5_ok", lambda: (True, None))
    monkeypatch.setattr(cli, "load_json_document", lambda path: (latest, None))
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: counts_doc)
    monkeypatch.setattr(cli, "nervous_index_freshness", lambda meta=None, config=None: {"stale": False, "lag_sec": 0})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:01:00+00:00")

    def fake_unit(name: str) -> dict:
        if name == cli.NERVOUS_SEARCH_INDEX_SERVICE:
            return service_status
        if name == cli.NERVOUS_SEARCH_INDEX_TIMER:
            return timer_status
        raise AssertionError(f"unexpected unit {name}")

    monkeypatch.setattr(cli, "user_systemd_unit", fake_unit)

    result = cli.nervous_index_status(write_latest=False)
    expected = status_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T13:01:00+00:00",
        config=config,
        config_path=config_path,
        config_exists=True,
        privacy=privacy,
        sources=sources,
        sqlite_version=cli.sqlite3.sqlite_version,
        fts_ok=True,
        fts_error=None,
        latest=latest,
        latest_error=None,
        counts=counts_doc,
        freshness={"stale": False, "lag_sec": 0},
        db_path=db_path,
        db_exists=True,
        root_path=root_path,
        schema_path=schema_path,
        latest_path=latest_path,
        service_status=service_status,
        timer_status=timer_status,
    )

    assert result == expected


def test_nervous_index_search_cli_delegates_request_shape_to_index_adapter(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    config = {"search": {"max_limit": 20, "default_limit": 7, "snippet_tokens": 9}}
    captured: dict[str, object] = {}

    def fake_search_from_ports(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "captured": kwargs}

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli.nervous_index_adapters, "search_from_ports", fake_search_from_ports)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:25:00+00:00")

    result = cli.nervous_index_search(
        "thermal",
        limit=50,
        order="ranked",
        dedupe=False,
        source="nervous_events",
        severity="warn",
    )

    assert result["ok"] is True
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["generated_at"] == "2026-06-25T13:25:00+00:00"
    assert captured["db_path"] == db_path
    assert captured["query"] == "thermal"
    assert captured["config"] == config
    assert captured["privacy"] == {"global_pause": False}
    assert captured["requested_limit"] == 50
    assert captured["requested_order"] == "ranked"
    assert captured["dedupe"] is False
    assert captured["source"] == "nervous_events"
    assert captured["severity"] == "warn"
    assert captured["freshness_reader"] is cli.nervous_index_freshness


def test_nervous_index_search_cli_uses_adapter_refusal_when_global_pause(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", tmp_path / "missing.db")
    monkeypatch.setattr(cli, "nervous_index_config", lambda: {"search": {"default_limit": 7}})
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": True})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:25:00+00:00")

    assert cli.nervous_index_search("thermal") == search_refused_result(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T13:25:00+00:00",
    )


def test_nervous_index_vacuum_cli_uses_module_refusal_when_paused(monkeypatch) -> None:
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": True})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:30:00+00:00")
    monkeypatch.setattr(
        cli,
        "nervous_index_db_counts",
        lambda: (_ for _ in ()).throw(AssertionError("pause should refuse before db counts")),
    )

    assert cli.nervous_index_vacuum(write_latest=False) == vacuum_refused_result(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T13:30:00+00:00",
    )


def test_nervous_index_vacuum_cli_uses_module_missing_db_result(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: {"documents": 0, "chunks": 0})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:31:00+00:00")

    started = vacuum_start_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T13:31:00+00:00",
        db_path=db_path,
        before={"documents": 0, "chunks": 0},
    )
    assert cli.nervous_index_vacuum(write_latest=False) == vacuum_missing_db_result(started)


def test_nervous_index_vacuum_cli_delegates_sqlite_execution_to_adapter(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    db_path.write_text("", encoding="utf-8")
    after = {"documents": 3, "chunks": 5, "optimized": True}
    captured: dict[str, Path] = {}

    def fake_vacuum(path: Path, root: Path) -> dict:
        captured["db_path"] = path
        captured["root"] = root
        return after

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_ROOT", tmp_path / "index-root")
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: {"documents": 3, "chunks": 5})
    monkeypatch.setattr(cli.nervous_index_adapters, "vacuum_index", fake_vacuum)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:32:00+00:00")

    started = vacuum_start_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T13:32:00+00:00",
        db_path=db_path,
        before={"documents": 3, "chunks": 5},
    )
    expected = vacuum_success_result(started, after={"documents": 3, "chunks": 5, "optimized": True})

    assert cli.nervous_index_vacuum(write_latest=False) == expected
    assert captured == {"db_path": db_path, "root": tmp_path / "index-root"}


def test_nervous_index_validate_cli_delegates_stable_shape_to_module_contract(monkeypatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    db_path = storage_root / "nervous" / "indexes" / "sqlite" / "nervous.db"
    config_path = tmp_path / "nervous-index.json"
    event_path = tmp_path / "events.jsonl"
    episode_path = tmp_path / "episodes.jsonl"
    db_path.parent.mkdir(parents=True)
    storage_root.mkdir(exist_ok=True)
    db_path.write_text("", encoding="utf-8")
    config_path.write_text("{}", encoding="utf-8")
    event_path.write_text("{}\n", encoding="utf-8")
    episode_path.write_text("{}\n", encoding="utf-8")
    config = {"enabled": True, "backend": "sqlite_fts5", "db_path": str(db_path)}
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {"browser_active_tab": {"enabled": True, "allowed": True}},
    }
    counts_doc = {
        "documents": 3,
        "chunks": 4,
        "fts_chunks": 4,
        "meta": {"schema": "abyss_machine_nervous_search_index_v1"},
    }
    freshness = {"stale": False, "lag_sec": 0}
    scan = {
        "indexed_source_ids": ["abyss_machine_facts", "browser_active_tab", "nervous_events", "nervous_episodes"],
        "documents_by_schema": {
            "abyss_machine_nervous_event_v1": 1,
            "abyss_machine_nervous_episode_v1": 1,
        },
        "smoke_results": 1,
    }
    line_counts = {event_path: 1, episode_path: 1}

    monkeypatch.setattr(cli, "ABYSS_MACHINE_STORAGE_ROOT", storage_root)
    monkeypatch.setattr(cli, "NERVOUS_INDEX_CONFIG_PATH", config_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: sources)
    monkeypatch.setattr(cli, "nervous_sqlite_fts5_ok", lambda: (True, None))
    monkeypatch.setattr(cli, "nervous_path_has_symlink_tail", lambda path, stop_at=None: False)
    monkeypatch.setattr(cli, "nervous_index_db_counts", lambda: counts_doc)
    monkeypatch.setattr(cli, "nervous_index_freshness", lambda meta=None, config=None: freshness)
    monkeypatch.setattr(cli, "build_nervous_index_scan", lambda path, smoke_match_query: scan)
    monkeypatch.setattr(cli, "nervous_event_jsonl_files", lambda: [event_path])
    monkeypatch.setattr(cli, "nervous_episode_jsonl_files", lambda: [episode_path])
    monkeypatch.setattr(cli, "count_file_lines", lambda path: line_counts[path])
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:20:00+00:00")

    result = cli.nervous_index_validate(write_latest=False)
    expected = validation_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T13:20:00+00:00",
        db_path=db_path,
        config=config,
        config_path=config_path,
        config_exists=True,
        fts_ok=True,
        fts_error=None,
        storage_routed=True,
        storage_root=storage_root,
        symlink_tail=False,
        db_exists=True,
        counts=counts_doc,
        freshness=freshness,
        allowed_source_ids=cli.nervous_allowed_source_ids(sources),
        scan=scan,
        scan_error=None,
        private_source_ids=cli.nervous_deferred_source_ids(sources),
        event_records=1,
        episode_records=1,
    )

    assert result == expected


def test_nervous_index_record_policy_and_chunk_projection_are_module_owned() -> None:
    def redact(text: str) -> tuple[str, int]:
        return text.replace("secret", "[redacted]"), text.count("secret")

    sources = {
        "safe_now": {
            "abyss_machine_facts": {"enabled": True, "allowed": True},
            "manual_notes": {"enabled": False, "allowed": True},
        },
        "deferred_until_privacy_controls": {
            "browser_active_tab": {"enabled": True, "allowed": True},
            "screenshots": {"enabled": True, "allowed": False},
        },
    }
    event = {
        "schema": "abyss_machine_nervous_event_v1",
        "raw_private_content": False,
        "source_ids": ["abyss_machine_facts"],
        "event_id": "event-1",
        "observed_at": "2026-06-25T11:00:00+00:00",
        "generated_at": "2026-06-25T11:01:00+00:00",
        "event_type": "thermal",
        "category": "resource",
        "severity": "warn",
        "sensitivity": "machine",
        "title": "Thermal route",
        "summary": "secret thermal detail",
    }

    assert enabled_safe_source_ids(sources) == {"abyss_machine_facts"}
    assert enabled_index_source_ids(sources) == {"abyss_machine_facts", "browser_active_tab", "nervous_events", "nervous_episodes"}
    assert allowed_source_ids(sources) == {"abyss_machine_facts", "browser_active_tab", "heartbeat", "nervous_events", "nervous_episodes"}
    assert fact_source_id({"name": "storage_latest"}) == "abyss_machine_facts"
    assert record_is_safe_for_index(event, sources) == (True, None)
    assert record_is_safe_for_index({**event, "source_ids": ["screenshots"]}, sources)[0] is False

    chunks, stats = chunks_from_record(
        event,
        enabled_index_source_ids(sources),
        redact_text=redact,
    )
    projection = document_rows_from_record(
        {
            "path": "/var/lib/abyss-machine/nervous/events/2026-06-25.jsonl",
            "line": 7,
            "source_sha256": "source-hash",
            "record_sha256": "record-hash",
        },
        event,
        chunks,
        started_at="2026-06-25T12:00:00+00:00",
        redact_text=redact,
    )

    assert stats["redactions"] == 1
    assert stats["source_ids"] == {"nervous_events"}
    assert chunks[0]["source_id"] == "nervous_events"
    assert "[redacted]" in chunks[0]["body"]
    assert projection["redactions"] == 1
    assert projection["document"]["schema"] == "abyss_machine_nervous_event_v1"
    assert projection["document"]["source_line"] == 7
    assert projection["document"]["source_ids_json"] == json.dumps(["nervous_events"])
    assert projection["chunks"][0]["doc_id"] == projection["document"]["doc_id"]
    assert json.loads(projection["chunks"][0]["provenance_json"])["event_id"] == "event-1"


def test_nervous_index_build_projection_contract_keeps_cli_as_file_and_write_adapter() -> None:
    def redact(text: str) -> tuple[str, int]:
        return text.replace("secret", "[redacted]"), text.count("secret")

    sources = {
        "safe_now": {
            "abyss_machine_facts": {"enabled": True, "allowed": True},
        },
        "deferred_until_privacy_controls": {
            "browser_active_tab": {"enabled": True, "allowed": True},
        },
    }
    source_records = [
        {
            "path": "/var/lib/abyss-machine/nervous/events/2026/06/2026-06-25.jsonl",
            "line": 1,
            "source_sha256": "source-a",
            "record_sha256": "record-a",
            "record": {
                "schema": "abyss_machine_nervous_event_v1",
                "raw_private_content": False,
                "source_ids": ["abyss_machine_facts"],
                "event_id": "event-a",
                "observed_at": "2026-06-25T11:00:00+00:00",
                "generated_at": "2026-06-25T11:01:00+00:00",
                "event_type": "storage.pressure",
                "category": "storage",
                "severity": "warn",
                "sensitivity": "machine_metadata",
                "title": "Storage pressure",
                "summary": "secret storage pressure detail",
            },
        },
        {
            "path": "/var/lib/abyss-machine/nervous/events/2026/06/2026-06-25.jsonl",
            "line": 2,
            "source_sha256": "source-a",
            "record_sha256": "record-b",
            "record": {
                "schema": "abyss_machine_nervous_event_v1",
                "raw_private_content": False,
                "source_ids": ["screenshots"],
                "event_id": "event-b",
                "observed_at": "2026-06-25T11:02:00+00:00",
                "event_type": "screen",
                "title": "unsafe",
                "summary": "should not index",
            },
        },
    ]

    projection = build_index_projection(
        source_records,
        sources,
        enabled_index_source_ids(sources),
        started_at="2026-06-25T12:00:00+00:00",
        redact_text=redact,
    )

    assert projection["summary"]["records_seen"] == 2
    assert projection["summary"]["records_indexed"] == 1
    assert projection["summary"]["chunks_indexed"] == 1
    assert projection["summary"]["skipped_records"] == 1
    assert projection["summary"]["redactions"] == 2
    assert projection["summary"]["records_seen_by_schema"] == {"abyss_machine_nervous_event_v1": 2}
    assert projection["summary"]["records_indexed_by_schema"] == {"abyss_machine_nervous_event_v1": 1}
    assert projection["documents"][0]["source_path"].endswith("2026-06-25.jsonl")
    assert projection["documents"][0]["source_line"] == 1
    assert projection["chunks"][0]["source_id"] == "nervous_events"
    assert "[redacted]" in projection["chunks"][0]["body"]
    assert projection["skipped_records"][0]["reason"] == "sources not enabled/allowed by policy: screenshots"


def test_nervous_index_store_search_and_scan_contracts_are_module_owned(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    conn = connect_db(db_path, create=True)
    initialize_db(conn, version="test-version")
    conn.commit()

    indexed_at = "2026-06-25T11:10:00+00:00"
    documents = [
        {
            "doc_id": "doc-hot",
            "source_path": "/var/lib/abyss-machine/nervous/events/2026-06-25.jsonl",
            "source_line": 1,
            "source_sha256": "source-hot",
            "record_sha256": "record-hot",
            "schema": "abyss_machine_nervous_event_v1",
            "generated_at": "2026-06-25T11:00:00+00:00",
            "capture_trigger": "derived_event",
            "global_pause": 0,
            "private_mode": 0,
            "heartbeat": 0,
            "source_ids_json": json.dumps(["nervous_events"]),
            "title": "nervous event thermal 2026-06-25T11:00:00+00:00",
            "body": "thermal pressure and zram route",
            "indexed_at": indexed_at,
        },
        {
            "doc_id": "doc-browser",
            "source_path": "/var/lib/abyss-machine/nervous/facts/2026-06-25.jsonl",
            "source_line": 2,
            "source_sha256": "source-browser",
            "record_sha256": "record-browser",
            "schema": "abyss_machine_nervous_fact_snapshot_v1",
            "generated_at": "2026-06-25T10:00:00+00:00",
            "capture_trigger": "focused_snapshot",
            "global_pause": 0,
            "private_mode": 0,
            "heartbeat": 0,
            "source_ids_json": json.dumps(["browser_active_tab"]),
            "title": "nervous snapshot 2026-06-25T10:00:00+00:00",
            "body": "thermal browser context",
            "indexed_at": indexed_at,
        },
    ]
    chunks = [
        {
            "chunk_id": "chunk-hot-a",
            "doc_id": "doc-hot",
            "chunk_index": 0,
            "source_id": "nervous_events",
            "title": "Thermal route",
            "body": "thermal pressure zram route",
            "generated_at": "2026-06-25T11:00:00+00:00",
            "privacy_mode": "normal",
            "provenance_json": json.dumps(
                {
                    "event_id": "event-hot",
                    "event_type": "thermal",
                    "severity": "warn",
                    "sensitivity": "machine",
                    "source_ids": ["nervous_events"],
                },
                sort_keys=True,
            ),
        },
        {
            "chunk_id": "chunk-hot-b",
            "doc_id": "doc-hot",
            "chunk_index": 1,
            "source_id": "nervous_events",
            "title": "Thermal route",
            "body": "thermal route duplicate evidence",
            "generated_at": "2026-06-25T10:50:00+00:00",
            "privacy_mode": "normal",
            "provenance_json": json.dumps(
                {
                    "event_id": "event-hot-older",
                    "event_type": "thermal",
                    "severity": "warn",
                    "sensitivity": "machine",
                    "source_ids": ["nervous_events"],
                },
                sort_keys=True,
            ),
        },
        {
            "chunk_id": "chunk-browser",
            "doc_id": "doc-browser",
            "chunk_index": 0,
            "source_id": "browser_active_tab",
            "title": "Browser context",
            "body": "thermal page context",
            "generated_at": "2026-06-25T10:00:00+00:00",
            "privacy_mode": "normal",
            "provenance_json": json.dumps(
                {
                    "event_id": "browser-context",
                    "severity": "info",
                    "sensitivity": "machine",
                    "source_ids": ["browser_active_tab"],
                },
                sort_keys=True,
            ),
        },
    ]

    replace_index_contents(
        conn,
        documents=documents,
        chunks=chunks,
        meta_values={
            "schema": "abyss_machine_nervous_search_index_v1",
            "backend": "sqlite_fts5",
            "tool_version": "test-version",
            "run_id": "index-run-1",
            "built_at": indexed_at,
            "records_seen": "2",
            "records_indexed": "2",
            "chunks_indexed": "3",
        },
        run_id="index-run-1",
        started_at="2026-06-25T11:09:00+00:00",
        finished_at=indexed_at,
        ok=True,
        source_files=1,
        records_seen=2,
        records_indexed=2,
        documents_indexed=2,
        chunks_indexed=3,
        errors={"parse_errors": [], "skipped_records": []},
    )
    conn.close()

    db_counts = counts(db_path)
    meta = read_meta(db_path)
    scan = scan_index(db_path, smoke_match_query='"thermal" OR "zram"')
    result = search_index(
        db_path=db_path,
        query="thermal",
        final_limit=5,
        dedupe=True,
        order="latest",
        source="nervous_events",
        severity="warn",
        freshness={"stale": False, "lag_sec": 0},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert search_match_query("thermal route") == '"thermal" OR "route"'
    assert db_counts["documents"] == 2
    assert db_counts["chunks"] == 3
    assert db_counts["fts_chunks"] == 3
    assert db_counts["index_runs"] == 1
    assert db_counts["last_successful_index_run"]["run_id"] == "index-run-1"
    assert db_counts["last_successful_index_run"]["details"] == {"parse_errors": [], "skipped_records": []}
    assert meta["backend"] == "sqlite_fts5"
    assert scan["indexed_source_ids"] == ["browser_active_tab", "nervous_events"]
    assert scan["documents_by_schema"]["abyss_machine_nervous_event_v1"] == 1
    assert scan["smoke_results"] == 3
    assert result["ok"] is True
    assert result["schema"] == "abyss_machine_nervous_search_v1"
    assert result["version"] == "test-version"
    assert result["summary"]["index_run_id"] == "index-run-1"
    assert result["summary"]["raw_results"] == 2
    assert result["summary"]["filtered_out"] == 1
    assert result["summary"]["deduped"] == 1
    assert result["summary"]["freshness"]["stale"] is False
    assert result["results"][0]["chunk_id"] == "chunk-hot-a"
    assert result["results"][0]["provenance"]["event_id"] == "event-hot"
