from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_index
from abyss_machine import nervous_index_adapters


def test_index_adapter_initializes_db_and_writes_schema_file(tmp_path: Path) -> None:
    db_path = tmp_path / "index" / "nervous.db"
    schema_path = tmp_path / "index" / "schema.sql"

    conn = nervous_index_adapters.connect_db(db_path, create=True)
    error = nervous_index_adapters.initialize_db(
        conn,
        schema_path=schema_path,
        schema_sql=nervous_index.nervous_index_schema_sql(),
        schema_prefix="abyss_machine",
        version="test-version",
        group="missing-test-group",
    )
    conn.commit()
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    conn.close()

    assert error is None
    assert meta["schema"] == "abyss_machine_nervous_search_index_v1"
    assert meta["tool_version"] == "test-version"
    assert "CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5" in schema_path.read_text(encoding="utf-8")


def test_index_adapter_sqlite_fts5_probe_uses_memory_connection_port() -> None:
    calls: list[tuple[str, Any]] = []

    class FakeCursor:
        def fetchone(self) -> tuple[int]:
            calls.append(("fetchone", None))
            return (1,)

    class FakeConnection:
        def execute(self, sql: str, params: tuple[Any, ...] = ()) -> FakeCursor:
            calls.append(("execute", {"sql": sql, "params": params}))
            return FakeCursor()

        def close(self) -> None:
            calls.append(("close", None))

    result = nervous_index_adapters.sqlite_fts5_ok(connect=lambda: FakeConnection())

    assert result == (True, None)
    assert calls == [
        ("execute", {"sql": "CREATE VIRTUAL TABLE fts_probe USING fts5(body)", "params": ()}),
        ("execute", {"sql": "INSERT INTO fts_probe(body) VALUES (?)", "params": ("thermal battery storage",)}),
        ("execute", {"sql": "SELECT count(*) FROM fts_probe WHERE fts_probe MATCH ?", "params": ("thermal",)}),
        ("fetchone", None),
        ("close", None),
    ]


def test_index_adapter_sqlite_fts5_probe_reports_sqlite_error_and_closes() -> None:
    calls: list[str] = []

    class FakeConnection:
        def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
            calls.append(sql)
            raise sqlite3.OperationalError("no such module: fts5")

        def close(self) -> None:
            calls.append("close")

    ok, error = nervous_index_adapters.sqlite_fts5_ok(connect=lambda: FakeConnection())

    assert ok is False
    assert error == "no such module: fts5"
    assert calls == ["CREATE VIRTUAL TABLE fts_probe USING fts5(body)", "close"]


def test_index_adapter_path_has_symlink_tail_detects_symlinked_parent(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    target_root = tmp_path / "real-index-root"
    link_root = storage_root / "linked-index-root"
    db_path = link_root / "nervous.db"
    storage_root.mkdir()
    target_root.mkdir()
    link_root.symlink_to(target_root, target_is_directory=True)
    db_path.write_text("", encoding="utf-8")

    assert nervous_index_adapters.path_has_symlink_tail(db_path, stop_at=storage_root) is True


def test_index_adapter_path_has_symlink_tail_allows_plain_route(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    db_path = storage_root / "nervous" / "indexes" / "sqlite" / "nervous.db"
    db_path.parent.mkdir(parents=True)
    db_path.write_text("", encoding="utf-8")

    assert nervous_index_adapters.path_has_symlink_tail(db_path, stop_at=storage_root) is False


def test_index_adapter_db_counts_uses_count_port(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    calls: list[Path] = []

    def fake_count(path: Path) -> dict[str, Any]:
        calls.append(path)
        return {"db_path": str(path), "documents": 3, "chunks": 5}

    result = nervous_index_adapters.db_counts(db_path, count=fake_count)

    assert result == {"db_path": str(db_path), "documents": 3, "chunks": 5}
    assert calls == [db_path]


def test_index_adapter_write_latest_marks_write_failures(tmp_path: Path) -> None:
    latest_path = tmp_path / "not-a-dir" / "latest.json"
    latest_path.parent.write_text("blocks directory creation", encoding="utf-8")
    data = {"ok": True}

    result = nervous_index_adapters.write_latest(data, latest_path, group="missing-test-group")

    assert result["ok"] is False
    assert result["write_errors"][0]["path"] == str(latest_path)


def test_index_adapter_freshness_reads_latest_and_counts_history_layers(tmp_path: Path) -> None:
    facts_latest_path = tmp_path / "facts-latest.json"
    events_latest_path = tmp_path / "events-latest.json"
    episodes_latest_path = tmp_path / "episodes-latest.json"
    fact_path = tmp_path / "facts.jsonl"
    event_path = tmp_path / "events.jsonl"
    episode_path = tmp_path / "episodes.jsonl"
    now = dt.datetime(2026, 6, 25, 13, 0, tzinfo=dt.timezone.utc)
    meta = {"built_at": "2026-06-25T12:00:00+00:00", "records_seen": "2"}
    config = {"automation": {"interval": "45m"}}
    latest_docs = {
        facts_latest_path: {"schema": "fact", "generated_at": "2026-06-25T12:10:00+00:00"},
        events_latest_path: {"schema": "event", "observed_at": "2026-06-25T12:20:00+00:00"},
        episodes_latest_path: {"schema": "episode", "start_at": "2026-06-25T12:30:00+00:00"},
    }
    line_counts = {fact_path: 2, event_path: None, episode_path: 1}
    latest_calls: list[Path] = []
    line_calls: list[Path] = []

    def latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        latest_calls.append(path)
        return latest_docs[path], None

    def line_counter(path: Path) -> int | None:
        line_calls.append(path)
        return line_counts[path]

    result = nervous_index_adapters.freshness_document_from_paths(
        meta=meta,
        config=config,
        facts_latest_path=facts_latest_path,
        events_latest_path=events_latest_path,
        episodes_latest_path=episodes_latest_path,
        fact_files=[fact_path],
        event_files=[event_path],
        episode_files=[episode_path],
        now=now,
        latest_reader=latest_reader,
        line_counter=line_counter,
    )

    assert result == nervous_index.freshness_document(
        meta=meta,
        config=config,
        latest_fact=latest_docs[facts_latest_path],
        latest_event=latest_docs[events_latest_path],
        latest_episode=latest_docs[episodes_latest_path],
        history_records=3,
        history_records_by_layer={"facts": 2, "events": 0, "episodes": 1},
        history_parse_errors=1,
        now=now,
    )
    assert latest_calls == [facts_latest_path, events_latest_path, episodes_latest_path]
    assert line_calls == [fact_path, event_path, episode_path]


def test_index_adapter_status_collects_latest_counts_freshness_and_timer_ports(tmp_path: Path) -> None:
    config_path = tmp_path / "nervous-index.json"
    db_path = tmp_path / "index" / "nervous.db"
    root_path = tmp_path / "index"
    schema_path = tmp_path / "index" / "schema.sql"
    latest_path = tmp_path / "index" / "latest.json"
    config_path.write_text("{}", encoding="utf-8")
    db_path.parent.mkdir(parents=True)
    db_path.write_text("", encoding="utf-8")
    config = {"enabled": True, "backend": "sqlite_fts5", "db_path": str(db_path)}
    privacy = {"global_pause": False, "private_mode": False}
    sources = {"safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}}}
    latest = {"schema": "abyss_machine_nervous_index_build_v1", "ok": True}
    counts_doc = {"meta": {"built_at": "2026-06-25T12:00:00+00:00"}, "documents": 2}
    freshness = {"stale": False, "lag_sec": 0}
    service_status = {"name": "nervous-index.service", "is_active": False}
    timer_status = {"name": "nervous-index.timer", "is_active": True}
    calls: list[tuple[str, Any]] = []

    def latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        calls.append(("latest", path))
        return latest, None

    def counts_reader() -> dict[str, Any]:
        calls.append(("counts", None))
        return counts_doc

    def freshness_reader(*, meta: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        calls.append(("freshness", {"meta": meta, "config": config}))
        return freshness

    def unit_status_reader(name: str) -> dict[str, Any]:
        calls.append(("unit", name))
        return {
            "nervous-index.service": service_status,
            "nervous-index.timer": timer_status,
        }[name]

    result = nervous_index_adapters.status_document_from_ports(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:00:00+00:00",
        config=config,
        config_path=config_path,
        privacy=privacy,
        sources=sources,
        sqlite_version="3.test",
        fts_ok=True,
        fts_error=None,
        db_path=db_path,
        root_path=root_path,
        schema_path=schema_path,
        latest_path=latest_path,
        service_name="nervous-index.service",
        timer_name="nervous-index.timer",
        latest_reader=latest_reader,
        counts_reader=counts_reader,
        freshness_reader=freshness_reader,
        unit_status_reader=unit_status_reader,
    )

    assert result == nervous_index.status_document(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:00:00+00:00",
        config=config,
        config_path=config_path,
        config_exists=True,
        privacy=privacy,
        sources=sources,
        sqlite_version="3.test",
        fts_ok=True,
        fts_error=None,
        latest=latest,
        latest_error=None,
        counts=counts_doc,
        freshness=freshness,
        db_path=db_path,
        db_exists=True,
        root_path=root_path,
        schema_path=schema_path,
        latest_path=latest_path,
        service_status=service_status,
        timer_status=timer_status,
    )
    assert calls == [
        ("latest", latest_path),
        ("counts", None),
        ("freshness", {"meta": counts_doc["meta"], "config": config}),
        ("unit", "nervous-index.service"),
        ("unit", "nervous-index.timer"),
    ]


def test_index_adapter_validation_collects_storage_scan_and_record_ports(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    db_path = storage_root / "nervous" / "indexes" / "sqlite" / "nervous.db"
    config_path = tmp_path / "nervous-index.json"
    event_path = tmp_path / "events.jsonl"
    episode_path = tmp_path / "episodes.jsonl"
    storage_root.mkdir()
    db_path.parent.mkdir(parents=True)
    db_path.write_text("", encoding="utf-8")
    config_path.write_text("{}", encoding="utf-8")
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
    line_counts = {event_path: 1, episode_path: 2}
    calls: list[tuple[str, Any]] = []

    def counts_reader() -> dict[str, Any]:
        calls.append(("counts", None))
        return counts_doc

    def freshness_reader(*, meta: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        calls.append(("freshness", {"meta": meta, "config": config}))
        return freshness

    def scan_reader(path: Path, smoke_match_query: str) -> dict[str, Any]:
        calls.append(("scan", {"path": path, "query": smoke_match_query}))
        return scan

    def line_counter(path: Path) -> int | None:
        calls.append(("line", path))
        return line_counts[path]

    def symlink_tail_probe(path: Path, *, stop_at: Path) -> bool:
        calls.append(("symlink_tail", {"path": path, "stop_at": stop_at}))
        return False

    result = nervous_index_adapters.validation_document_from_ports(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:20:00+00:00",
        db_path=db_path,
        storage_root=storage_root,
        config=config,
        config_path=config_path,
        sources=sources,
        fts_ok=True,
        fts_error=None,
        event_files=[event_path],
        episode_files=[episode_path],
        counts_reader=counts_reader,
        freshness_reader=freshness_reader,
        scan_reader=scan_reader,
        line_counter=line_counter,
        symlink_tail_probe=symlink_tail_probe,
    )

    assert result == nervous_index.validation_document(
        schema_prefix="abyss_machine",
        version="test-version",
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
        allowed_source_ids=nervous_index.allowed_source_ids(sources),
        scan=scan,
        scan_error=None,
        private_source_ids=nervous_index.deferred_source_ids(sources),
        event_records=1,
        episode_records=2,
    )
    assert calls == [
        ("symlink_tail", {"path": db_path, "stop_at": storage_root}),
        ("counts", None),
        ("freshness", {"meta": counts_doc["meta"], "config": config}),
        ("scan", {"path": db_path, "query": '"nervous" OR "storage" OR "thermal" OR "episode"'}),
        ("line", event_path),
        ("line", episode_path),
    ]


def test_index_adapter_derived_refresh_orchestrates_event_episode_ports() -> None:
    calls: list[tuple[str, Any]] = []
    events_result = {"ok": True, "summary": {"events": 2}}
    episodes_result = {"ok": True, "summary": {"episodes": 1}}
    summary_result = {"events": {"ok": True, "events": 2}, "episodes": {"ok": True, "episodes": 1}}

    def events_builder(**kwargs: Any) -> dict[str, Any]:
        calls.append(("events", kwargs))
        return events_result

    def episodes_builder(**kwargs: Any) -> dict[str, Any]:
        calls.append(("episodes", kwargs))
        return episodes_result

    def summary_builder(events_refresh: dict[str, Any], episodes_refresh: dict[str, Any]) -> dict[str, Any]:
        calls.append(("summary", {"events": events_refresh, "episodes": episodes_refresh}))
        return summary_result

    enabled = nervous_index_adapters.derived_refresh_from_ports(
        refresh_enabled=True,
        events_builder=events_builder,
        episodes_builder=episodes_builder,
        summary_builder=summary_builder,
    )
    disabled = nervous_index_adapters.derived_refresh_from_ports(
        refresh_enabled=False,
        events_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("events port should not be called")),
        episodes_builder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("episodes port should not be called")),
        summary_builder=summary_builder,
    )

    assert enabled == summary_result
    assert disabled == {}
    assert calls == [
        ("events", {"write_latest": True}),
        ("episodes", {"write_latest": True, "refresh_events": False}),
        ("summary", {"events": events_result, "episodes": episodes_result}),
    ]


def test_index_adapter_build_document_collects_source_inputs_through_ports(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = facts_root / "2026" / "06" / "facts.jsonl"
    source_files = [source_path]
    source_records = [{"path": str(source_path), "line": 1, "record": {"schema": "fact"}}]
    parse_errors = [{"path": str(source_path), "line": 2, "error": "bad json"}]
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {"browser_active_tab": {"enabled": True, "allowed": True}},
        "state": {"last_change_id": "source-change-1"},
    }
    projection = {
        "documents": [{"doc_id": "doc-1"}],
        "chunks": [{"chunk_id": "chunk-1"}],
        "skipped_records": [],
        "summary": {
            "records_seen": 1,
            "records_indexed": 1,
            "documents_indexed": 1,
            "chunks_indexed": 1,
            "skipped_records": 0,
            "disabled_chunks": 0,
            "redactions": 0,
            "records_seen_by_schema": {"fact": 1},
            "records_indexed_by_schema": {"fact": 1},
        },
    }
    derived_refresh = {"events": {"ok": True}, "episodes": {"ok": True}}
    calls: list[tuple[str, Any]] = []

    def source_files_reader(roots: tuple[Path, ...]) -> list[Path]:
        calls.append(("source_files", roots))
        return source_files

    def source_records_loader(paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        calls.append(("source_records", paths))
        return source_records, parse_errors

    def projection_builder(
        records: list[dict[str, Any]],
        source_doc: dict[str, Any],
        enabled_sources: set[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        calls.append((
            "projection",
            {
                "records": records,
                "sources": source_doc,
                "enabled_sources": sorted(enabled_sources),
                "kwargs": kwargs,
            },
        ))
        return projection

    def redact_text(text: str) -> tuple[str, int]:
        return text, 0

    result = nervous_index_adapters.build_document_from_source_roots(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
        run_id="index-run-1",
        started_at="2026-06-25T11:59:00+00:00",
        db_path=tmp_path / "index" / "nervous.db",
        config_path=tmp_path / "nervous-index.json",
        privacy={"global_pause": False, "private_mode": True},
        sources=sources,
        source_roots=(facts_root, events_root, episodes_root),
        derived_refresh=derived_refresh,
        redact_text=redact_text,
        source_files_reader=source_files_reader,
        source_records_loader=source_records_loader,
        projection_builder=projection_builder,
    )
    enabled_sources = nervous_index.enabled_index_source_ids(sources)

    assert result == {
        "data": nervous_index.build_index_build_document(
            schema_prefix="abyss_machine",
            version="test-version",
            generated_at="2026-06-25T12:00:00+00:00",
            run_id="index-run-1",
            started_at="2026-06-25T11:59:00+00:00",
            db_path=tmp_path / "index" / "nervous.db",
            config_path=tmp_path / "nervous-index.json",
            privacy={"global_pause": False, "private_mode": True},
            sources=sources,
            enabled_sources=enabled_sources,
            source_files=source_files,
            projection=projection,
            parse_errors=parse_errors,
            derived_refresh=derived_refresh,
        ),
        "source_files": source_files,
        "projection": projection,
        "parse_errors": parse_errors,
        "enabled_sources": sorted(enabled_sources),
    }
    assert calls == [
        ("source_files", (facts_root, events_root, episodes_root)),
        ("source_records", source_files),
        (
            "projection",
            {
                "records": source_records,
                "sources": sources,
                "enabled_sources": sorted(enabled_sources),
                "kwargs": {
                    "started_at": "2026-06-25T11:59:00+00:00",
                    "schema_prefix": "abyss_machine",
                    "redact_text": redact_text,
                },
            },
        ),
    ]


def test_index_adapter_write_build_projection_executes_db_write_stage_through_ports(tmp_path: Path) -> None:
    db_path = tmp_path / "index" / "nervous.db"
    root = tmp_path / "index"
    schema_path = tmp_path / "index" / "schema.sql"
    source_path = tmp_path / "facts.jsonl"
    projection = {
        "documents": [{"doc_id": "doc-1"}],
        "chunks": [{"chunk_id": "chunk-1"}],
        "skipped_records": [{"path": str(source_path), "line": 2, "reason": "filtered"}],
        "summary": {
            "records_seen": 2,
            "records_indexed": 1,
            "documents_indexed": 1,
            "chunks_indexed": 1,
            "skipped_records": 1,
            "disabled_chunks": 0,
            "redactions": 0,
            "records_seen_by_schema": {"fact": 2},
            "records_indexed_by_schema": {"fact": 1},
        },
    }
    data = {"schema": "abyss_machine_nervous_index_build_v1", "ok": False, "sources": {}}
    counts_doc = {"documents": 1, "chunks": 1}
    calls: list[tuple[str, Any]] = []
    times = iter(["2026-06-25T12:01:00+00:00", "2026-06-25T12:02:00+00:00"])

    class FakeConnection:
        def commit(self) -> None:
            calls.append(("commit", None))

        def close(self) -> None:
            calls.append(("close", None))

    @contextmanager
    def fake_lock(path: Path):
        calls.append(("lock", path))
        yield

    def fake_connect(path: Path, create: bool = False) -> FakeConnection:
        calls.append(("connect", {"path": path, "create": create}))
        return FakeConnection()

    def fake_initialize(conn: object, **kwargs: Any) -> None:
        calls.append(("initialize", kwargs))

    def fake_replace(conn: object, **kwargs: Any) -> None:
        calls.append(("replace", kwargs))

    def fake_apply(path: Path, **kwargs: Any) -> None:
        calls.append(("apply_mode", {"path": path, "kwargs": kwargs}))

    result = nervous_index_adapters.write_build_projection(
        data,
        db_path=db_path,
        root=root,
        schema_path=schema_path,
        schema_sql="CREATE TABLE meta(key TEXT, value TEXT);",
        schema_prefix="abyss_machine",
        version="test-version",
        group="missing-test-group",
        run_id="index-run-1",
        started_at="2026-06-25T12:00:00+00:00",
        source_files=[source_path],
        projection=projection,
        parse_errors=[],
        facts_root=tmp_path / "facts",
        events_root=tmp_path / "events",
        episodes_root=tmp_path / "episodes",
        source_state_change_id="source-change-1",
        privacy_state_change_id="privacy-change-1",
        semantic_lock_active=lambda: False,
        now=lambda: next(times),
        counts_reader=lambda: counts_doc,
        lock=fake_lock,
        connect=fake_connect,
        initialize=fake_initialize,
        replace_contents=fake_replace,
        apply_mode=fake_apply,
    )

    assert result == nervous_index.with_index_write_success(
        data,
        finished_at="2026-06-25T12:02:00+00:00",
        counts=counts_doc,
        parse_errors=[],
    )
    replace_call = [item for item in calls if item[0] == "replace"][0][1]
    assert replace_call["documents"] == [{"doc_id": "doc-1"}]
    assert replace_call["chunks"] == [{"chunk_id": "chunk-1"}]
    assert replace_call["meta_values"]["built_at"] == "2026-06-25T12:01:00+00:00"
    assert replace_call["meta_values"]["source_state_change_id"] == "source-change-1"
    assert replace_call["meta_values"]["privacy_state_change_id"] == "privacy-change-1"
    assert replace_call["errors"]["skipped_records"] == projection["skipped_records"]
    assert calls[:4] == [
        ("lock", root),
        ("connect", {"path": db_path, "create": True}),
        (
            "initialize",
            {
                "schema_path": schema_path,
                "schema_sql": "CREATE TABLE meta(key TEXT, value TEXT);",
                "schema_prefix": "abyss_machine",
                "version": "test-version",
                "group": "missing-test-group",
            },
        ),
        ("commit", None),
    ]
    assert calls[-2:] == [
        ("apply_mode", {"path": db_path, "kwargs": {"group": "missing-test-group"}}),
        ("close", None),
    ]


def test_index_adapter_write_build_projection_persists_synthetic_sqlite_index(tmp_path: Path) -> None:
    db_path = tmp_path / "index" / "nervous.db"
    schema_path = tmp_path / "index" / "schema.sql"
    source_path = tmp_path / "events.jsonl"
    indexed_at = "2026-06-25T11:10:00+00:00"
    projection = {
        "documents": [
            {
                "doc_id": "doc-hot",
                "source_path": str(source_path),
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
            }
        ],
        "chunks": [
            {
                "chunk_id": "chunk-hot",
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
            }
        ],
        "skipped_records": [],
        "summary": {
            "records_seen": 1,
            "records_indexed": 1,
            "documents_indexed": 1,
            "chunks_indexed": 1,
            "skipped_records": 0,
            "disabled_chunks": 0,
            "redactions": 0,
            "records_seen_by_schema": {"abyss_machine_nervous_event_v1": 1},
            "records_indexed_by_schema": {"abyss_machine_nervous_event_v1": 1},
        },
    }
    times = iter(["2026-06-25T11:10:00+00:00", "2026-06-25T11:10:01+00:00"])

    result = nervous_index_adapters.write_build_projection(
        {"schema": "abyss_machine_nervous_index_build_v1", "ok": False},
        db_path=db_path,
        root=tmp_path / "index",
        schema_path=schema_path,
        schema_sql=nervous_index.nervous_index_schema_sql(),
        schema_prefix="abyss_machine",
        version="test-version",
        group="missing-test-group",
        run_id="index-run-1",
        started_at="2026-06-25T11:09:00+00:00",
        source_files=[source_path],
        projection=projection,
        parse_errors=[],
        facts_root=tmp_path / "facts",
        events_root=tmp_path / "events",
        episodes_root=tmp_path / "episodes",
        source_state_change_id="source-change-1",
        privacy_state_change_id="privacy-change-1",
        semantic_lock_active=lambda: False,
        now=lambda: next(times),
        counts_reader=lambda: nervous_index.counts(db_path),
    )

    db_counts = nervous_index.counts(db_path)
    scan = nervous_index.scan_index(db_path, smoke_match_query='"thermal" OR "zram"')
    assert result["ok"] is True
    assert result["counts"]["documents"] == 1
    assert db_counts["documents"] == 1
    assert db_counts["chunks"] == 1
    assert db_counts["fts_chunks"] == 1
    assert scan["smoke_results"] == 1
    assert schema_path.read_text(encoding="utf-8").startswith("PRAGMA foreign_keys=ON;")


def test_index_adapter_vacuum_executes_sqlite_commands_under_lock(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    root = tmp_path / "index-root"
    executed: list[str] = []

    class FakeConnection:
        def execute(self, sql: str) -> None:
            executed.append(sql)

        def close(self) -> None:
            executed.append("close")

    def fake_connect(path: Path, create: bool = False) -> FakeConnection:
        assert path == db_path
        assert create is False
        return FakeConnection()

    result = nervous_index_adapters.vacuum_index(
        db_path,
        root,
        connect=fake_connect,
        counts=lambda path: {"db_path": str(path), "optimized": True},
    )

    assert result == {"db_path": str(db_path), "optimized": True}
    assert executed == ["PRAGMA optimize", "VACUUM", "close"]
    assert (root / "index.lock").exists()


def test_cli_nervous_index_lifecycle_binds_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    db_path = tmp_path / "nervous.db"
    root = tmp_path / "index-root"
    schema_path = tmp_path / "schema.sql"
    latest_path = tmp_path / "latest.json"
    fake_conn = sqlite3.connect(":memory:")

    @contextmanager
    def fake_lock(path: Path):
        captured["lock_root"] = path
        yield

    def fake_connect(path: Path, create: bool = False):
        captured["connect"] = {"path": path, "create": create}
        return fake_conn

    def fake_initialize(conn: object, **kwargs: object) -> None:
        captured["initialize_conn"] = conn
        captured["initialize_kwargs"] = kwargs

    def fake_write_latest(data: dict[str, Any], path: Path, **kwargs: object) -> dict[str, Any]:
        captured["write_latest"] = {"data": data, "path": path, "kwargs": kwargs}
        return {"ok": True, "from_adapter": True}

    def fake_lock_active(path: Path) -> bool:
        captured["active_root"] = path
        return True

    def fake_fts5_ok() -> tuple[bool, str | None]:
        captured["fts5_ok"] = True
        return True, None

    def fake_path_has_symlink_tail(path: Path, *, stop_at: Path | None = None) -> bool:
        captured["symlink_tail"] = {"path": path, "stop_at": stop_at}
        return True

    def fake_db_counts(path: Path) -> dict[str, Any]:
        captured["db_counts"] = path
        return {"documents": 7}

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_ROOT", root)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli.nervous_index_adapters, "connect_db", fake_connect)
    monkeypatch.setattr(cli.nervous_index_adapters, "initialize_db", fake_initialize)
    monkeypatch.setattr(cli.nervous_index_adapters, "index_lock", fake_lock)
    monkeypatch.setattr(cli.nervous_index_adapters, "index_lock_active", fake_lock_active)
    monkeypatch.setattr(cli.nervous_index_adapters, "write_latest", fake_write_latest)
    monkeypatch.setattr(cli.nervous_index_adapters, "sqlite_fts5_ok", fake_fts5_ok)
    monkeypatch.setattr(cli.nervous_index_adapters, "path_has_symlink_tail", fake_path_has_symlink_tail)
    monkeypatch.setattr(cli.nervous_index_adapters, "db_counts", fake_db_counts)

    assert cli.nervous_index_connect(create=True) is fake_conn
    cli.nervous_index_initialize(fake_conn)
    with cli.nervous_index_lock():
        pass
    assert cli.nervous_index_lock_active() is True
    assert cli.nervous_index_write_latest({"ok": True}) == {"ok": True, "from_adapter": True}
    assert cli.nervous_sqlite_fts5_ok() == (True, None)
    assert cli.nervous_path_has_symlink_tail(db_path, stop_at=root) is True
    assert cli.nervous_index_db_counts() == {"documents": 7}

    assert captured["connect"] == {"path": db_path, "create": True}
    assert captured["initialize_conn"] is fake_conn
    assert captured["initialize_kwargs"]["schema_path"] == schema_path
    assert captured["initialize_kwargs"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["initialize_kwargs"]["version"] == cli.VERSION
    assert captured["lock_root"] == root
    assert captured["active_root"] == root
    assert captured["write_latest"]["path"] == latest_path
    assert captured["fts5_ok"] is True
    assert captured["symlink_tail"] == {"path": db_path, "stop_at": root}
    assert captured["db_counts"] == db_path


def test_cli_nervous_index_freshness_binds_adapter_paths_and_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    facts_latest = tmp_path / "facts-latest.json"
    events_latest = tmp_path / "events-latest.json"
    episodes_latest = tmp_path / "episodes-latest.json"
    fact_path = tmp_path / "facts.jsonl"
    event_path = tmp_path / "events.jsonl"
    episode_path = tmp_path / "episodes.jsonl"
    config = {"automation": {"interval": "45m"}}
    meta = {"built_at": "2026-06-25T12:00:00+00:00"}

    def fake_freshness(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    def forbidden_latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        raise AssertionError(f"CLI must pass latest reader to adapter, not call it directly: {path}")

    def forbidden_line_counter(path: Path) -> int | None:
        raise AssertionError(f"CLI must pass line counter to adapter, not call it directly: {path}")

    monkeypatch.setattr(cli, "NERVOUS_FACTS_LATEST_PATH", facts_latest)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_LATEST_PATH", events_latest)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_LATEST_PATH", episodes_latest)
    monkeypatch.setattr(cli, "nervous_fact_jsonl_files", lambda: [fact_path])
    monkeypatch.setattr(cli, "nervous_event_jsonl_files", lambda: [event_path])
    monkeypatch.setattr(cli, "nervous_episode_jsonl_files", lambda: [episode_path])
    monkeypatch.setattr(cli, "load_json_document", forbidden_latest_reader)
    monkeypatch.setattr(cli, "count_file_lines", forbidden_line_counter)
    monkeypatch.setattr(cli.nervous_index_adapters, "freshness_document_from_paths", fake_freshness)

    result = cli.nervous_index_freshness(meta=meta, config=config)

    assert result == {"ok": True, "from_adapter": True}
    assert captured["meta"] == meta
    assert captured["config"] == config
    assert captured["facts_latest_path"] == facts_latest
    assert captured["events_latest_path"] == events_latest
    assert captured["episodes_latest_path"] == episodes_latest
    assert captured["fact_files"] == [fact_path]
    assert captured["event_files"] == [event_path]
    assert captured["episode_files"] == [episode_path]
    assert captured["latest_reader"] is forbidden_latest_reader
    assert captured["line_counter"] is forbidden_line_counter


def test_cli_nervous_index_status_binds_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    config_path = tmp_path / "nervous-index.json"
    db_path = tmp_path / "nervous.db"
    root_path = tmp_path / "index-root"
    schema_path = tmp_path / "schema.sql"
    latest_path = tmp_path / "latest.json"
    config = {"enabled": True, "db_path": str(db_path)}
    privacy = {"global_pause": False, "private_mode": False}
    sources = {"safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}}}

    def fake_status(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    def forbidden_latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        raise AssertionError(f"CLI must pass latest reader to adapter, not call it directly: {path}")

    def forbidden_counts_reader() -> dict[str, Any]:
        raise AssertionError("CLI must pass counts reader to adapter, not call it directly")

    def forbidden_freshness_reader(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("CLI must pass freshness reader to adapter, not call it directly")

    def forbidden_unit_reader(name: str) -> dict[str, Any]:
        raise AssertionError(f"CLI must pass unit reader to adapter, not call it directly: {name}")

    monkeypatch.setattr(cli, "NERVOUS_INDEX_CONFIG_PATH", config_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_ROOT", root_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_SERVICE", "nervous-index.service")
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_TIMER", "nervous-index.timer")
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: privacy)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: sources)
    monkeypatch.setattr(cli, "nervous_sqlite_fts5_ok", lambda: (True, None))
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:00:00+00:00")
    monkeypatch.setattr(cli, "load_json_document", forbidden_latest_reader)
    monkeypatch.setattr(cli, "nervous_index_db_counts", forbidden_counts_reader)
    monkeypatch.setattr(cli, "nervous_index_freshness", forbidden_freshness_reader)
    monkeypatch.setattr(cli, "user_systemd_unit", forbidden_unit_reader)
    monkeypatch.setattr(cli.nervous_index_adapters, "status_document_from_ports", fake_status)

    result = cli.nervous_index_status(write_latest=False)

    assert result == {"ok": True, "from_adapter": True}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["generated_at"] == "2026-06-25T13:00:00+00:00"
    assert captured["config"] == config
    assert captured["config_path"] == config_path
    assert captured["privacy"] == privacy
    assert captured["sources"] == sources
    assert captured["fts_ok"] is True
    assert captured["db_path"] == db_path
    assert captured["root_path"] == root_path
    assert captured["schema_path"] == schema_path
    assert captured["latest_path"] == latest_path
    assert captured["service_name"] == "nervous-index.service"
    assert captured["timer_name"] == "nervous-index.timer"
    assert captured["latest_reader"] is forbidden_latest_reader
    assert captured["counts_reader"] is forbidden_counts_reader
    assert captured["freshness_reader"] is forbidden_freshness_reader
    assert captured["unit_status_reader"] is forbidden_unit_reader


def test_cli_nervous_index_validate_binds_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    storage_root = tmp_path / "storage"
    db_path = storage_root / "nervous.db"
    config_path = tmp_path / "nervous-index.json"
    event_path = tmp_path / "events.jsonl"
    episode_path = tmp_path / "episodes.jsonl"
    config = {"enabled": True, "db_path": str(db_path)}
    sources = {"safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}}}

    def fake_validate(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    def forbidden_counts_reader() -> dict[str, Any]:
        raise AssertionError("CLI must pass counts reader to adapter, not call it directly")

    def forbidden_freshness_reader(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("CLI must pass freshness reader to adapter, not call it directly")

    def forbidden_scan_reader(path: Path, smoke_match_query: str) -> dict[str, Any]:
        raise AssertionError(f"CLI must pass scan reader to adapter, not call it directly: {path}")

    def forbidden_line_counter(path: Path) -> int | None:
        raise AssertionError(f"CLI must pass line counter to adapter, not call it directly: {path}")

    def forbidden_symlink_tail_probe(path: Path, *, stop_at: Path) -> bool:
        raise AssertionError(f"CLI must pass symlink-tail probe to adapter, not call it directly: {path}")

    monkeypatch.setattr(cli, "ABYSS_MACHINE_STORAGE_ROOT", storage_root)
    monkeypatch.setattr(cli, "NERVOUS_INDEX_CONFIG_PATH", config_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: sources)
    monkeypatch.setattr(cli, "nervous_sqlite_fts5_ok", lambda: (True, None))
    monkeypatch.setattr(cli, "nervous_event_jsonl_files", lambda: [event_path])
    monkeypatch.setattr(cli, "nervous_episode_jsonl_files", lambda: [episode_path])
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:20:00+00:00")
    monkeypatch.setattr(cli, "nervous_index_db_counts", forbidden_counts_reader)
    monkeypatch.setattr(cli, "nervous_index_freshness", forbidden_freshness_reader)
    monkeypatch.setattr(cli, "build_nervous_index_scan", forbidden_scan_reader)
    monkeypatch.setattr(cli, "count_file_lines", forbidden_line_counter)
    monkeypatch.setattr(cli, "nervous_path_has_symlink_tail", forbidden_symlink_tail_probe)
    monkeypatch.setattr(cli.nervous_index_adapters, "validation_document_from_ports", fake_validate)

    result = cli.nervous_index_validate(write_latest=False)

    assert result == {"ok": True, "from_adapter": True}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["generated_at"] == "2026-06-25T13:20:00+00:00"
    assert captured["db_path"] == db_path
    assert captured["storage_root"] == storage_root
    assert captured["config"] == config
    assert captured["config_path"] == config_path
    assert captured["sources"] == sources
    assert captured["fts_ok"] is True
    assert captured["fts_error"] is None
    assert captured["event_files"] == [event_path]
    assert captured["episode_files"] == [episode_path]
    assert captured["counts_reader"] is forbidden_counts_reader
    assert captured["freshness_reader"] is forbidden_freshness_reader
    assert captured["scan_reader"] is forbidden_scan_reader
    assert captured["line_counter"] is forbidden_line_counter
    assert captured["symlink_tail_probe"] is forbidden_symlink_tail_probe


def test_cli_nervous_index_build_binds_write_stage_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    db_path = tmp_path / "nervous.db"
    root = tmp_path / "index-root"
    schema_path = tmp_path / "schema.sql"
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = tmp_path / "facts.jsonl"
    config = {"enabled": True, "privacy": {"enforce_global_pause": True}}
    privacy = {"global_pause": False, "private_mode": False, "state": {"last_change_id": "privacy-change-1"}}
    sources = {"safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}}, "state": {"last_change_id": "source-change-1"}}
    parse_errors: list[dict[str, Any]] = []
    derived_refresh = {"events": {"ok": True, "events": 2}, "episodes": {"ok": True, "episodes": 1}}
    projection = {
        "documents": [{"doc_id": "doc-1"}],
        "chunks": [{"chunk_id": "chunk-1"}],
        "skipped_records": [],
        "summary": {
            "records_seen": 1,
            "records_indexed": 1,
            "documents_indexed": 1,
            "chunks_indexed": 1,
            "skipped_records": 0,
            "disabled_chunks": 0,
            "redactions": 0,
            "records_seen_by_schema": {"fact": 1},
            "records_indexed_by_schema": {"fact": 1},
        },
    }
    build_data = {"schema": "abyss_machine_nervous_index_build_v1", "ok": False, "sources": {"state_change_id": "source-change-1"}}

    def fake_derived_refresh(**kwargs: Any) -> dict[str, Any]:
        captured["derived_refresh"] = kwargs
        return derived_refresh

    def fake_source_input_stage(**kwargs: Any) -> dict[str, Any]:
        captured["source_input"] = kwargs
        return {
            "data": build_data,
            "source_files": [source_path],
            "projection": projection,
            "parse_errors": parse_errors,
            "enabled_sources": ["abyss_machine_facts", "nervous_events", "nervous_episodes"],
        }

    def fake_write_stage(data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        captured["data"] = data
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    def forbidden_write_stage(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("CLI must delegate index build write stage to adapter")

    def forbidden_source_input(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("CLI must delegate index build source input assembly to adapter")

    def forbidden_derived_refresh(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("CLI must delegate index build derived refresh orchestration to adapter")

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_ROOT", root)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(cli, "NERVOUS_FACTS_ROOT", facts_root)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_ROOT", events_root)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_ROOT", episodes_root)
    monkeypatch.setattr(cli, "nervous_change_id", lambda prefix: f"{prefix}-run-1")
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: privacy)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: sources)
    monkeypatch.setattr(cli, "nervous_sqlite_fts5_ok", lambda: (True, None))
    monkeypatch.setattr(cli, "nervous_semantic_lock_active", lambda: False)
    monkeypatch.setattr(cli, "nervous_index_source_files", forbidden_source_input)
    monkeypatch.setattr(cli, "build_nervous_index_load_source_records", forbidden_source_input)
    monkeypatch.setattr(cli, "build_nervous_index_projection", forbidden_source_input)
    monkeypatch.setattr(cli, "nervous_enabled_index_source_ids", forbidden_source_input)
    monkeypatch.setattr(cli, "nervous_events_build", forbidden_derived_refresh)
    monkeypatch.setattr(cli, "nervous_episodes_build", forbidden_derived_refresh)
    monkeypatch.setattr(cli, "build_nervous_index_derived_refresh_summary", forbidden_derived_refresh)
    monkeypatch.setattr(cli, "nervous_index_lock", forbidden_write_stage)
    monkeypatch.setattr(cli, "nervous_index_connect", forbidden_write_stage)
    monkeypatch.setattr(cli, "nervous_index_initialize", forbidden_write_stage)
    monkeypatch.setattr(cli.nervous_index_adapters, "derived_refresh_from_ports", fake_derived_refresh)
    monkeypatch.setattr(cli.nervous_index_adapters, "build_document_from_source_roots", fake_source_input_stage)
    monkeypatch.setattr(cli.nervous_index_adapters, "write_build_projection", fake_write_stage)

    result = cli.nervous_index_build(write_latest=False, refresh_derived=True)

    assert result == {"ok": True, "from_adapter": True}
    assert captured["derived_refresh"]["refresh_enabled"] is True
    assert captured["derived_refresh"]["events_builder"] is forbidden_derived_refresh
    assert captured["derived_refresh"]["episodes_builder"] is forbidden_derived_refresh
    assert captured["source_input"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["source_input"]["version"] == cli.VERSION
    assert captured["source_input"]["generated_at"] == "2026-06-25T12:00:00+00:00"
    assert captured["source_input"]["run_id"] == "index-run-1"
    assert captured["source_input"]["started_at"] == "2026-06-25T12:00:00+00:00"
    assert captured["source_input"]["db_path"] == db_path
    assert captured["source_input"]["config_path"] == cli.NERVOUS_INDEX_CONFIG_PATH
    assert captured["source_input"]["privacy"] == privacy
    assert captured["source_input"]["sources"] == sources
    assert captured["source_input"]["source_roots"] == (facts_root, events_root, episodes_root)
    assert captured["source_input"]["derived_refresh"] == derived_refresh
    assert captured["source_input"]["redact_text"] is cli.nervous_redact_index_text
    assert captured["data"] is build_data
    assert captured["db_path"] == db_path
    assert captured["root"] == root
    assert captured["schema_path"] == schema_path
    assert captured["schema_sql"] == cli.nervous_index_schema_sql()
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["group"] == cli.MODE_STATE_GROUP
    assert captured["run_id"] == "index-run-1"
    assert captured["started_at"] == "2026-06-25T12:00:00+00:00"
    assert captured["source_files"] == [source_path]
    assert captured["projection"] == projection
    assert captured["parse_errors"] == parse_errors
    assert captured["facts_root"] == facts_root
    assert captured["events_root"] == events_root
    assert captured["episodes_root"] == episodes_root
    assert captured["source_state_change_id"] == "source-change-1"
    assert captured["privacy_state_change_id"] == "privacy-change-1"
    assert captured["semantic_lock_active"] is cli.nervous_semantic_lock_active
    assert captured["now"] is cli.now_iso
    assert captured["counts_reader"] is cli.nervous_index_db_counts
