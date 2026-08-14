from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import hashlib
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
from abyss_machine import nervous_events
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


def test_index_adapter_bounded_counts_disables_expensive_fts_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    captured: dict[str, Any] = {}

    def fake_count(path: Path, **kwargs: Any) -> dict[str, Any]:
        captured["path"] = path
        captured.update(kwargs)
        return {"fts_chunks": 7}

    result = nervous_index_adapters.db_counts_bounded(
        db_path,
        busy_timeout_ms=75,
        count=fake_count,
    )

    assert result == {"fts_chunks": 7}
    assert captured == {
        "path": db_path,
        "busy_timeout_ms": 75,
        "allow_expensive_fts_fallback": False,
    }


def test_index_adapter_source_present_uses_bounded_target_probe(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    captured: dict[str, Any] = {}

    def fake_probe(path: Path, source_id: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"path": path, "source_id": source_id, **kwargs})
        return {"present": True}

    result = nervous_index_adapters.source_present(
        db_path,
        "typed_text_autolog",
        busy_timeout_ms=80,
        probe=fake_probe,
    )

    assert result == {"present": True}
    assert captured == {
        "path": db_path,
        "source_id": "typed_text_autolog",
        "busy_timeout_ms": 80,
    }


def test_index_adapter_scan_index_uses_scan_port(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    calls: list[dict[str, Any]] = []

    def fake_scan(path: Path, *, smoke_match_query: str) -> dict[str, Any]:
        calls.append({"path": path, "query": smoke_match_query})
        return {"indexed_source_ids": ["abyss_machine_facts"], "smoke_results": 4}

    result = nervous_index_adapters.scan_index(
        db_path,
        smoke_match_query='"thermal" OR "zram"',
        scan=fake_scan,
    )

    assert result == {"indexed_source_ids": ["abyss_machine_facts"], "smoke_results": 4}
    assert calls == [{"path": db_path, "query": '"thermal" OR "zram"'}]


def test_index_adapter_search_reads_meta_freshness_and_dispatches_search_runner(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    db_path.write_text("", encoding="utf-8")
    config = {"search": {"max_limit": 20, "default_limit": 7, "snippet_tokens": 9}}
    privacy = {"global_pause": False}
    meta = {"built_at": "2026-06-25T13:00:00+00:00"}
    freshness = {"stale": False, "lag_sec": 0}
    calls: list[tuple[str, Any]] = []

    def meta_reader(path: Path) -> dict[str, Any]:
        calls.append(("meta", path))
        return meta

    def freshness_reader(**kwargs: Any) -> dict[str, Any]:
        calls.append(("freshness", kwargs))
        return freshness

    def search_runner(**kwargs: Any) -> dict[str, Any]:
        calls.append(("search", kwargs))
        return {"ok": True, "captured": kwargs}

    result = nervous_index_adapters.search_from_ports(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:25:00+00:00",
        db_path=db_path,
        query="thermal",
        config=config,
        privacy=privacy,
        requested_limit=50,
        requested_order="ranked",
        dedupe=False,
        source="nervous_events",
        severity="warn",
        freshness_reader=freshness_reader,
        meta_reader=meta_reader,
        search_runner=search_runner,
    )

    assert result["ok"] is True
    assert calls[0] == ("meta", db_path)
    assert calls[1] == ("freshness", {"meta": meta, "config": config})
    search_call = calls[2][1]
    assert search_call["db_path"] == db_path
    assert search_call["query"] == "thermal"
    assert search_call["final_limit"] == 20
    assert search_call["order"] == "ranked"
    assert search_call["dedupe"] is False
    assert search_call["source"] == "nervous_events"
    assert search_call["severity"] == "warn"
    assert search_call["snippet_tokens"] == 9
    assert search_call["scan_limit"] == 320
    assert search_call["freshness"] == freshness
    assert search_call["schema_prefix"] == "abyss_machine"
    assert search_call["version"] == "test-version"
    assert search_call["generated_at"] == "2026-06-25T13:25:00+00:00"


def test_index_adapter_search_refuses_before_live_reads_when_paused(tmp_path: Path) -> None:
    db_path = tmp_path / "nervous.db"
    db_path.write_text("", encoding="utf-8")

    def forbidden_meta_reader(path: Path) -> dict[str, Any]:
        raise AssertionError(f"paused search must not read index metadata: {path}")

    def forbidden_freshness_reader(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("paused search must not read freshness")

    def forbidden_search_runner(**kwargs: Any) -> dict[str, Any]:
        raise AssertionError("paused search must not run SQLite search")

    result = nervous_index_adapters.search_from_ports(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:25:00+00:00",
        db_path=db_path,
        query="thermal",
        config={"search": {"default_limit": 7}},
        privacy={"global_pause": True},
        requested_limit=None,
        requested_order="latest",
        dedupe=True,
        freshness_reader=forbidden_freshness_reader,
        meta_reader=forbidden_meta_reader,
        search_runner=forbidden_search_runner,
    )

    assert result == nervous_index.search_refused_result(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T13:25:00+00:00",
    )


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


def test_index_adapter_freshness_batches_counts_after_latest_snapshot(tmp_path: Path) -> None:
    facts_latest_path = tmp_path / "facts-latest.json"
    events_latest_path = tmp_path / "events-latest.json"
    episodes_latest_path = tmp_path / "episodes-latest.json"
    fact_path = tmp_path / "facts.jsonl"
    event_path = tmp_path / "events.jsonl"
    episode_path = tmp_path / "episodes.jsonl"
    calls: list[tuple[str, Any]] = []

    def latest_reader(path: Path) -> tuple[dict[str, Any], None]:
        calls.append(("latest", path))
        return {"generated_at": "2026-06-25T12:00:00+00:00"}, None

    def line_counts_reader(paths: list[Path]) -> tuple[dict[Path, int | None], str]:
        calls.append(("counts", paths))
        return {fact_path: 2, event_path: 3, episode_path: 4}, "batched_wc_l_exact"

    result = nervous_index_adapters.freshness_document_from_paths(
        meta={"built_at": "2026-06-25T12:00:00+00:00", "records_seen": "5"},
        config={"automation": {"interval": "45m"}},
        facts_latest_path=facts_latest_path,
        events_latest_path=events_latest_path,
        episodes_latest_path=episodes_latest_path,
        fact_files=[fact_path],
        event_files=[event_path],
        episode_files=[episode_path],
        now=dt.datetime(2026, 6, 25, 13, 0, tzinfo=dt.timezone.utc),
        latest_reader=latest_reader,
        line_counter=lambda path: (_ for _ in ()).throw(AssertionError(f"unexpected fallback: {path}")),
        line_counts_reader=line_counts_reader,
    )

    assert calls == [
        ("latest", facts_latest_path),
        ("latest", events_latest_path),
        ("latest", episodes_latest_path),
        ("counts", [fact_path, event_path, episode_path]),
    ]
    assert result["history_records"] == 9
    assert result["history_records_by_layer"] == {"facts": 2, "events": 3, "episodes": 4}
    assert result["history_count_method"] == "batched_wc_l_exact"


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
    freshness = {
        "stale": False,
        "lag_sec": 0,
        "history_records_by_layer": {"facts": 3, "events": 1, "episodes": 2},
    }
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
        ("events", {"write_latest": True, "force_full": False}),
        (
            "episodes",
            {"write_latest": True, "refresh_events": False, "force_full": False},
        ),
        ("summary", {"events": events_result, "episodes": episodes_result}),
    ]


def test_index_derived_refresh_exposes_attestations_only_on_internal_route() -> None:
    attestation = {"schema": "attestation", "path": "/facts/current.jsonl"}

    def events_builder(**_kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "summary": {"events": 1},
            "incremental": {"delta_attestations": [attestation]},
        }

    def episodes_builder(**_kwargs: Any) -> dict[str, Any]:
        return {"ok": True, "summary": {"episodes": 1}}

    public = nervous_index_adapters.derived_refresh_from_ports(
        refresh_enabled=True,
        events_builder=events_builder,
        episodes_builder=episodes_builder,
    )
    internal = nervous_index_adapters.derived_refresh_from_ports(
        refresh_enabled=True,
        include_internal_attestations=True,
        events_builder=events_builder,
        episodes_builder=episodes_builder,
    )

    assert "_internal_source_delta_attestations" not in public
    assert internal["_internal_source_delta_attestations"] == [attestation]


def test_index_derived_refresh_rejects_attestation_from_failed_event_stage() -> None:
    attestation = {"schema": "attestation", "path": "/facts/current.jsonl"}

    result = nervous_index_adapters.derived_refresh_from_ports(
        refresh_enabled=True,
        include_internal_attestations=True,
        events_builder=lambda **_kwargs: {
            "ok": False,
            "incremental": {"delta_attestations": [attestation]},
        },
        episodes_builder=lambda **_kwargs: {"ok": True},
    )

    assert result["_internal_source_delta_attestations"] == []


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

    assert result["ok"] is True
    assert result["finished_at"] == "2026-06-25T12:02:00+00:00"
    assert result["counts"] == counts_doc
    assert result["execution"]["write_mode"] == "full"
    assert set(result["execution"]["timings_ms"]) == {
        "write_lock_wait",
        "db_initialize",
        "db_write",
        "post_write_counts",
        "write_stage_total",
    }
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

    def fake_scan(path: Path, *, smoke_match_query: str) -> dict[str, Any]:
        captured["scan"] = {"path": path, "query": smoke_match_query}
        return {"smoke_results": 3}

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
    monkeypatch.setattr(cli.nervous_index_adapters, "scan_index", fake_scan)

    assert cli.nervous_index_connect(create=True) is fake_conn
    cli.nervous_index_initialize(fake_conn)
    with cli.nervous_index_lock():
        pass
    assert cli.nervous_index_lock_active() is True
    assert cli.nervous_index_write_latest({"ok": True}) == {"ok": True, "from_adapter": True}
    assert cli.nervous_sqlite_fts5_ok() == (True, None)
    assert cli.nervous_path_has_symlink_tail(db_path, stop_at=root) is True
    assert cli.nervous_index_db_counts() == {"documents": 7}
    assert cli.nervous_index_scan(db_path, smoke_match_query='"thermal"') == {"smoke_results": 3}

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
    assert captured["scan"] == {"path": db_path, "query": '"thermal"'}


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

    line_counts = {fact_path: 1, event_path: 2, episode_path: 3}

    def fake_line_count_snapshot(paths: list[Path]) -> tuple[dict[Path, int | None], str]:
        captured["line_count_paths"] = paths
        return line_counts, "batched_wc_l_exact"

    monkeypatch.setattr(cli, "NERVOUS_FACTS_LATEST_PATH", facts_latest)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_LATEST_PATH", events_latest)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_LATEST_PATH", episodes_latest)
    monkeypatch.setattr(cli, "nervous_fact_jsonl_files", lambda: [fact_path])
    monkeypatch.setattr(cli, "nervous_event_jsonl_files", lambda: [event_path])
    monkeypatch.setattr(cli, "nervous_episode_jsonl_files", lambda: [episode_path])
    monkeypatch.setattr(cli, "load_json_document", forbidden_latest_reader)
    monkeypatch.setattr(
        cli,
        "count_file_lines",
        lambda path: (_ for _ in ()).throw(AssertionError(f"batched line-count route must own {path}")),
    )
    monkeypatch.setattr(cli, "count_file_lines_snapshot", fake_line_count_snapshot)
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
    assert captured["line_counter"] is cli.count_file_lines
    assert captured["line_counts_reader"] is fake_line_count_snapshot


def test_cli_line_count_snapshot_batches_exact_wc_output(monkeypatch, tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second file.jsonl"
    first.write_text("a\nb", encoding="utf-8")
    second.write_text("c\n", encoding="utf-8")
    calls: list[dict[str, Any]] = []

    def fake_run(cmd: list[str], timeout: float = 3.0, env: dict[str, str] | None = None) -> dict[str, Any]:
        calls.append({"cmd": cmd, "timeout": timeout, "env": env})
        return {
            "ok": True,
            "returncode": 0,
            "stdout": f"1 {first}\n1 {second}\n2 total",
            "stderr": "",
        }

    monkeypatch.setattr(cli, "run", fake_run)

    counts, method = cli.count_file_lines_snapshot([second, first], batch_size=10)

    assert counts == {first: 2, second: 1}
    assert method == "batched_wc_l_exact"
    assert calls == [
        {
            "cmd": ["wc", "-l", "--", str(first), str(second)],
            "timeout": 30.0,
            "env": None,
        }
    ]


def test_cli_line_count_snapshot_preserves_exact_per_file_fallback(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("a\nb\n", encoding="utf-8")
    fallback_calls: list[Path] = []

    monkeypatch.setattr(
        cli,
        "run",
        lambda cmd, timeout=3.0, env=None: {"ok": False, "stdout": "", "stderr": "wc failed"},
    )
    monkeypatch.setattr(
        cli,
        "count_file_lines",
        lambda item: fallback_calls.append(item) or 2,
    )

    counts, method = cli.count_file_lines_snapshot([path])

    assert counts == {path: 2}
    assert method == "batched_wc_l_with_per_file_exact_fallback"
    assert fallback_calls == [path]


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


def test_cli_nervous_index_search_binds_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    db_path = tmp_path / "nervous.db"
    config = {"search": {"max_limit": 20, "default_limit": 7}}
    privacy = {"global_pause": False}

    def fake_search_from_ports(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "nervous_index_config", lambda: config)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: privacy)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T13:25:00+00:00")
    monkeypatch.setattr(cli.nervous_index_adapters, "search_from_ports", fake_search_from_ports)

    result = cli.nervous_index_search(
        "thermal",
        limit=50,
        dedupe=False,
        order="ranked",
        source="nervous_events",
        severity="warn",
    )

    assert result == {"ok": True, "from_adapter": True}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["generated_at"] == "2026-06-25T13:25:00+00:00"
    assert captured["db_path"] == db_path
    assert captured["query"] == "thermal"
    assert captured["config"] == config
    assert captured["privacy"] == privacy
    assert captured["requested_limit"] == 50
    assert captured["requested_order"] == "ranked"
    assert captured["dedupe"] is False
    assert captured["source"] == "nervous_events"
    assert captured["severity"] == "warn"
    assert captured["freshness_reader"] is cli.nervous_index_freshness


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
    monkeypatch.setattr(cli, "nervous_index_scan", forbidden_scan_reader)
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
            "manifest_entries": {str(source_path): {"source_sha256": "source-1"}},
            "projection_identity": "projection-1",
            "changed_source_paths": [str(source_path)],
            "replace_source_paths": [],
            "append_source_paths": [str(source_path)],
            "source_observations": {str(source_path): {"size_bytes": 1}},
            "write_mode": "delta",
            "base_run_id": "index-base-1",
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
    monkeypatch.setattr(cli.nervous_index_adapters, "build_incremental_document_from_source_roots", fake_source_input_stage)
    monkeypatch.setattr(cli.nervous_index_adapters, "write_build_projection", fake_write_stage)

    result = cli.nervous_index_build(write_latest=False, refresh_derived=True)

    assert result["ok"] is True
    assert result["from_adapter"] is True
    assert result["execution"]["timings_ms"]["total_before_latest_write"] >= 0
    assert captured["derived_refresh"]["refresh_enabled"] is True
    assert captured["derived_refresh"]["force_full"] is False
    assert captured["derived_refresh"]["include_internal_attestations"] is True
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
    assert captured["source_input"]["force_full"] is False
    assert captured["source_input"]["source_delta_attestations"] == []
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
    assert captured["manifest_entries"] == {str(source_path): {"source_sha256": "source-1"}}
    assert captured["projection_identity"] == "projection-1"
    assert captured["changed_source_paths"] == [str(source_path)]
    assert captured["replace_source_paths"] == []
    assert captured["append_source_paths"] == [str(source_path)]
    assert captured["source_observations"] == {str(source_path): {"size_bytes": 1}}
    assert captured["write_mode"] == "delta"
    assert captured["base_run_id"] == "index-base-1"


def _incremental_event(event_id: str, observed_at: str, body: str) -> dict[str, Any]:
    return {
        "schema": "abyss_machine_nervous_event_v1",
        "raw_private_content": False,
        "source_ids": ["abyss_machine_facts"],
        "event_id": event_id,
        "observed_at": observed_at,
        "generated_at": observed_at,
        "event_type": "validation.test",
        "category": "validation",
        "severity": "info",
        "sensitivity": "machine_metadata",
        "title": body,
        "summary": body,
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _index_plan(
    *,
    db_path: Path,
    facts_root: Path,
    events_root: Path,
    episodes_root: Path,
    sources: dict[str, Any],
    run_id: str,
    at: str,
    force_full: bool = False,
    source_bytes_reader: Any = None,
    source_delta_attestations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    optional: dict[str, Any] = {}
    if source_bytes_reader is not None:
        optional["source_bytes_reader"] = source_bytes_reader
    if source_delta_attestations is not None:
        optional["source_delta_attestations"] = source_delta_attestations
    return nervous_index_adapters.build_incremental_document_from_source_roots(
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at=at,
        run_id=run_id,
        started_at=at,
        db_path=db_path,
        config_path=db_path.parent / "index.json",
        privacy={"global_pause": False, "private_mode": False},
        sources=sources,
        source_roots=(facts_root, events_root, episodes_root),
        derived_refresh={},
        redact_text=lambda text: (text, 0),
        force_full=force_full,
        **optional,
    )


def _write_index_plan(
    *,
    plan: dict[str, Any],
    db_path: Path,
    facts_root: Path,
    events_root: Path,
    episodes_root: Path,
    run_id: str,
    at: str,
) -> dict[str, Any]:
    return nervous_index_adapters.write_build_projection(
        plan["data"],
        db_path=db_path,
        root=db_path.parent,
        schema_path=db_path.parent / "schema.sql",
        schema_sql=nervous_index.nervous_index_schema_sql(),
        schema_prefix="abyss_machine",
        version="test-version",
        group="missing-test-group",
        run_id=run_id,
        started_at=at,
        source_files=plan["source_files"],
        projection=plan["projection"],
        parse_errors=plan["parse_errors"],
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        source_state_change_id="source-change-1",
        privacy_state_change_id="privacy-change-1",
        semantic_lock_active=lambda: False,
        now=lambda: at,
        counts_reader=lambda: nervous_index.counts(db_path),
        manifest_entries=plan["manifest_entries"],
        projection_identity=plan["projection_identity"],
        changed_source_paths=plan["changed_source_paths"],
        replace_source_paths=plan["replace_source_paths"],
        append_source_paths=plan["append_source_paths"],
        source_observations=plan["source_observations"],
        write_mode=plan["write_mode"],
        base_run_id=plan["base_run_id"],
    )


def _logical_index_rows(db_path: Path) -> dict[str, list[tuple[Any, ...]]]:
    conn = nervous_index.connect_db(db_path, create=False)
    try:
        documents = conn.execute(
            """
            SELECT doc_id, source_path, source_line, source_sha256, record_sha256, schema,
                   generated_at, capture_trigger, global_pause, private_mode, heartbeat,
                   source_ids_json, title, body
            FROM documents ORDER BY doc_id
            """
        ).fetchall()
        chunks = conn.execute(
            """
            SELECT chunk_id, doc_id, chunk_index, source_id, title, body, generated_at,
                   privacy_mode, provenance_json
            FROM chunks ORDER BY chunk_id
            """
        ).fetchall()
        fts = conn.execute(
            "SELECT chunk_id, doc_id, source_id, title, body FROM fts_chunks ORDER BY chunk_id"
        ).fetchall()
        manifest = conn.execute(
            """
            SELECT source_path, source_sha256, source_size_bytes, source_line_count,
                   source_observation_json, projection_identity,
                   summary_json, parse_errors_json, skipped_records_json
            FROM source_manifest ORDER BY source_path
            """
        ).fetchall()
        return {
            "documents": [tuple(row) for row in documents],
            "chunks": [tuple(row) for row in chunks],
            "fts": [tuple(row) for row in fts],
            "manifest": [tuple(row) for row in manifest],
        }
    finally:
        conn.close()


def test_index_append_delta_matches_full_oracle_and_removes_partitions(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    stable_path = events_root / "2026" / "08" / "2026-08-12.jsonl"
    changing_path = events_root / "2026" / "08" / "2026-08-13.jsonl"
    _write_jsonl(stable_path, [_incremental_event("stable-1", "2026-08-12T12:00:00+00:00", "stable alpha")])
    _write_jsonl(changing_path, [_incremental_event("changing-1", "2026-08-13T12:00:00+00:00", "changing beta")])
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
        "state": {"last_change_id": "source-change-1"},
    }
    delta_db = tmp_path / "delta" / "nervous.db"
    full_plan = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="full-seed",
        at="2026-08-13T12:01:00+00:00",
    )
    assert full_plan["write_mode"] == "full"
    seeded = _write_index_plan(
        plan=full_plan,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="full-seed",
        at="2026-08-13T12:01:00+00:00",
    )
    assert seeded["ok"] is True

    _write_jsonl(
        changing_path,
        [
            _incremental_event("changing-1", "2026-08-13T12:00:00+00:00", "changing beta"),
            _incremental_event("changing-2", "2026-08-13T12:02:00+00:00", "delta gamma"),
        ],
    )
    delta_plan = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="delta-1",
        at="2026-08-13T12:03:00+00:00",
    )
    assert delta_plan["write_mode"] == "delta"
    assert delta_plan["data"]["execution"]["strategy"] == "record_append_delta"
    assert delta_plan["data"]["execution"]["source_partitions"] == {
        "total": 2,
        "changed": 1,
        "unchanged": 1,
        "removed": 0,
        "replaced": 0,
        "appended": 1,
        "metadata_refreshed": 0,
    }
    assert delta_plan["data"]["execution"]["delta"] == {"documents": 1, "chunks": 1}
    assert delta_plan["replace_source_paths"] == []
    assert delta_plan["append_source_paths"] == [str(changing_path)]
    delta_result = _write_index_plan(
        plan=delta_plan,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="delta-1",
        at="2026-08-13T12:03:00+00:00",
    )
    assert delta_result["ok"] is True
    assert delta_result["counts"]["documents"] == 3
    assert delta_result["counts"]["chunks"] == 3
    assert delta_result["counts"]["fts_chunks"] == 3
    assert delta_result["execution"]["database_touched"] is True
    assert {
        "db_delta_prepare_replacements",
        "db_delta_delete_fts",
        "db_delta_delete_relational",
        "db_delta_insert_relational",
        "db_delta_insert_fts",
        "db_delta_verify_fts",
        "db_delta_update_manifest",
        "db_delta_update_run_metadata",
        "db_delta_drop_temp_tables",
        "db_delta_commit",
    }.issubset(delta_result["execution"]["timings_ms"])
    conn = nervous_index.connect_db(delta_db, create=False)
    try:
        assert conn.execute(
            "SELECT count(*) FROM documents WHERE source_sha256 IS NOT NULL"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM source_manifest WHERE source_sha256 = ''"
        ).fetchone()[0] == 0
    finally:
        conn.close()

    oracle_db = tmp_path / "oracle" / "nervous.db"
    oracle_plan = _index_plan(
        db_path=oracle_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="full-oracle",
        at="2026-08-13T12:04:00+00:00",
        force_full=True,
    )
    _write_index_plan(
        plan=oracle_plan,
        db_path=oracle_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="full-oracle",
        at="2026-08-13T12:04:00+00:00",
    )
    assert _logical_index_rows(delta_db) == _logical_index_rows(oracle_db)
    delta_search = nervous_index.search_index(
        db_path=delta_db,
        query="gamma",
        final_limit=10,
        dedupe=False,
        order="latest",
        freshness={"stale": False},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-08-13T12:05:00+00:00",
    )
    oracle_search = nervous_index.search_index(
        db_path=oracle_db,
        query="gamma",
        final_limit=10,
        dedupe=False,
        order="latest",
        freshness={"stale": False},
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-08-13T12:05:00+00:00",
    )
    assert delta_search["results"] == oracle_search["results"]

    stable_path.unlink()
    removal_plan = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="delta-remove",
        at="2026-08-13T12:06:00+00:00",
    )
    assert removal_plan["write_mode"] == "delta"
    assert removal_plan["data"]["execution"]["source_partitions"]["removed"] == 1
    removed = _write_index_plan(
        plan=removal_plan,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="delta-remove",
        at="2026-08-13T12:06:00+00:00",
    )
    assert removed["counts"]["documents"] == 2
    assert removed["counts"]["chunks"] == removed["counts"]["fts_chunks"] == 2


def test_index_incremental_plan_falls_back_on_policy_or_manifest_identity_drift(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = events_root / "2026" / "08" / "events.jsonl"
    _write_jsonl(source_path, [_incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha")])
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    db_path = tmp_path / "index" / "nervous.db"
    seed = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:01:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:01:00+00:00",
    )

    changed_policy = {
        **sources,
        "safe_now": {"abyss_machine_facts": {"enabled": False, "allowed": True}},
    }
    policy_plan = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=changed_policy,
        run_id="policy-drift",
        at="2026-08-13T12:02:00+00:00",
    )
    assert policy_plan["write_mode"] == "full"
    assert "projection_identity_mismatch" in policy_plan["eligibility"]["reasons"]

    conn = nervous_index.connect_db(db_path, create=False)
    conn.execute("UPDATE meta SET value = 'tampered' WHERE key = 'source_manifest_identity'")
    conn.commit()
    conn.close()
    tampered_plan = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="manifest-drift",
        at="2026-08-13T12:03:00+00:00",
    )
    assert tampered_plan["write_mode"] == "full"
    assert "source_manifest_identity_mismatch" in tampered_plan["eligibility"]["reasons"]


def test_index_delta_rolls_back_partial_mutation_and_rejects_stale_base(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = events_root / "2026" / "08" / "events.jsonl"
    _write_jsonl(source_path, [_incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha")])
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    db_path = tmp_path / "index" / "nervous.db"
    seed = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:01:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:01:00+00:00",
    )
    before = _logical_index_rows(db_path)

    _write_jsonl(
        source_path,
        [
            _incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha"),
            _incremental_event("event-2", "2026-08-13T12:02:00+00:00", "beta"),
        ],
    )
    broken_plan = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="broken-delta",
        at="2026-08-13T12:03:00+00:00",
    )
    broken_plan["projection"]["chunks"].append(dict(broken_plan["projection"]["chunks"][0]))
    broken = _write_index_plan(
        plan=broken_plan,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="broken-delta",
        at="2026-08-13T12:03:00+00:00",
    )
    assert broken["ok"] is False
    assert "UNIQUE constraint failed" in broken["error"]
    assert _logical_index_rows(db_path) == before

    stale_plan = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="stale-delta",
        at="2026-08-13T12:04:00+00:00",
    )
    conn = nervous_index.connect_db(db_path, create=False)
    conn.execute("UPDATE meta SET value = 'concurrent-run' WHERE key = 'run_id'")
    conn.commit()
    conn.close()
    stale = _write_index_plan(
        plan=stale_plan,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="stale-delta",
        at="2026-08-13T12:04:00+00:00",
    )
    assert stale["ok"] is False
    assert stale["error"] == "incremental index base run changed before write"
    assert _logical_index_rows(db_path) == before


def test_index_modified_partition_uses_replace_delta_and_matches_full_oracle(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = events_root / "2026" / "08" / "events.jsonl"
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    original = [
        _incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha"),
        _incremental_event("event-2", "2026-08-13T12:01:00+00:00", "beta"),
    ]
    _write_jsonl(source_path, original)
    delta_db = tmp_path / "delta" / "nervous.db"
    seed = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:02:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:02:00+00:00",
    )

    modified = [
        _incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha corrected"),
        original[1],
    ]
    _write_jsonl(source_path, modified)
    delta = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="replace-delta",
        at="2026-08-13T12:03:00+00:00",
    )
    assert delta["data"]["execution"]["strategy"] == "file_partition_delta"
    assert delta["replace_source_paths"] == [str(source_path)]
    assert delta["append_source_paths"] == []
    assert delta["data"]["execution"]["delta"] == {"documents": 2, "chunks": 2}
    result = _write_index_plan(
        plan=delta,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="replace-delta",
        at="2026-08-13T12:03:00+00:00",
    )
    assert result["ok"] is True

    oracle_db = tmp_path / "oracle" / "nervous.db"
    oracle = _index_plan(
        db_path=oracle_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="oracle",
        at="2026-08-13T12:04:00+00:00",
        force_full=True,
    )
    _write_index_plan(
        plan=oracle,
        db_path=oracle_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="oracle",
        at="2026-08-13T12:04:00+00:00",
    )
    assert _logical_index_rows(delta_db) == _logical_index_rows(oracle_db)


def test_index_unchanged_partition_reuses_exact_hash_without_content_read(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = events_root / "2026" / "08" / "events.jsonl"
    _write_jsonl(
        source_path,
        [_incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha")],
    )
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    db_path = tmp_path / "index" / "nervous.db"
    seed = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:01:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:01:00+00:00",
    )

    def forbidden_content_read(path: Path) -> bytes:
        raise AssertionError(f"unchanged source content must not be read: {path}")

    fixed_point = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="fixed-point",
        at="2026-08-13T12:02:00+00:00",
        source_bytes_reader=forbidden_content_read,
    )

    assert fixed_point["write_mode"] == "noop"
    assert fixed_point["data"]["execution"]["strategy"] == "fixed_point_noop"
    assert fixed_point["changed_source_paths"] == []
    assert fixed_point["data"]["execution"]["delta"] == {"documents": 0, "chunks": 0}
    assert fixed_point["data"]["execution"]["source_scan"] == {
        "partitions_reused_by_observation": 1,
        "content_bytes_reused": source_path.stat().st_size,
        "content_bytes_hashed": 0,
        "append_prefix_bytes_verified": 0,
        "attested_tail_bytes_read": 0,
        "attested_prefix_bytes_reused": 0,
        "source_delta_attestations_admitted": 0,
        "observation_fields": ["device", "inode", "size_bytes", "mtime_ns", "ctime_ns"],
    }

    db_sha256_before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    fixed_result = _write_index_plan(
        plan=fixed_point,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="fixed-point",
        at="2026-08-13T12:02:00+00:00",
    )
    db_sha256_after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert fixed_result["ok"] is True
    assert fixed_result["execution"]["write_mode"] == "noop"
    assert fixed_result["execution"]["database_touched"] is False
    assert fixed_result["execution"]["timings_ms"]["db_write"] == 0.0
    assert fixed_result["counts"]["meta"]["run_id"] == "seed"
    assert db_sha256_after == db_sha256_before


def test_index_admits_events_append_attestation_and_reads_only_tail(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = facts_root / "2026" / "08" / "facts.jsonl"
    first = _incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha")
    second = _incremental_event("event-2", "2026-08-13T12:01:00+00:00", "beta")
    _write_jsonl(source_path, [first])
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    db_path = tmp_path / "index" / "nervous.db"
    seed = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:02:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:02:00+00:00",
    )
    previous = seed["manifest_entries"][str(source_path)]
    previous_size = int(previous["source_size_bytes"])
    with source_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(second, sort_keys=True) + "\n")
    raw = source_path.read_bytes()
    observation = nervous_index_adapters.source_file_observation(source_path)
    current = {
        "path": str(source_path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "line_count": len(raw.splitlines()),
        "observation": observation,
    }
    attestation = nervous_events.source_delta_attestation(
        path=str(source_path),
        basis="append_only",
        base={
            "sha256": previous["source_sha256"],
            "size_bytes": previous_size,
            "line_count": previous["source_line_count"],
        },
        current=current,
    )

    full_reads: list[Path] = []

    def observed_full_read(path: Path) -> bytes:
        full_reads.append(path)
        return path.read_bytes()

    tampered = {**attestation, "proof_sha256": "0" * 64}
    rejected_attestation = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="tampered-attestation",
        at="2026-08-13T12:03:00+00:00",
        source_bytes_reader=observed_full_read,
        source_delta_attestations=[tampered],
    )
    rejected_scan = rejected_attestation["data"]["execution"]["source_scan"]
    assert full_reads == [source_path]
    assert rejected_scan["content_bytes_hashed"] == len(raw)
    assert rejected_scan["source_delta_attestations_admitted"] == 0

    def forbidden_full_read(path: Path) -> bytes:
        raise AssertionError(f"admitted append attestation must avoid full read: {path}")

    delta = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="attested-delta",
        at="2026-08-13T12:03:00+00:00",
        source_bytes_reader=forbidden_full_read,
        source_delta_attestations=[attestation],
    )
    assert delta["data"]["execution"]["strategy"] == "record_append_delta"
    assert delta["data"]["execution"]["delta"] == {"documents": 1, "chunks": 1}
    scan = delta["data"]["execution"]["source_scan"]
    assert scan["content_bytes_hashed"] == 0
    assert scan["attested_tail_bytes_read"] == len(raw) - previous_size
    assert scan["attested_prefix_bytes_reused"] == previous_size
    assert scan["source_delta_attestations_admitted"] == 1
    result = _write_index_plan(
        plan=delta,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="attested-delta",
        at="2026-08-13T12:03:00+00:00",
    )
    assert result["ok"] is True
    assert result["counts"]["documents"] == 2


def test_index_source_change_after_plan_refuses_write_then_recovers_by_append(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = events_root / "2026" / "08" / "events.jsonl"
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    first = _incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha")
    second = _incremental_event("event-2", "2026-08-13T12:01:00+00:00", "beta")
    third = _incremental_event("event-3", "2026-08-13T12:02:00+00:00", "gamma")
    _write_jsonl(source_path, [first])
    db_path = tmp_path / "delta" / "nervous.db"
    seed = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:03:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:03:00+00:00",
    )
    before = _logical_index_rows(db_path)

    _write_jsonl(source_path, [first, second])
    stale_plan = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="stale-plan",
        at="2026-08-13T12:04:00+00:00",
    )
    _write_jsonl(source_path, [first, second, third])
    refused = _write_index_plan(
        plan=stale_plan,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="stale-plan",
        at="2026-08-13T12:04:00+00:00",
    )
    assert refused["ok"] is False
    assert refused["refused"] is True
    assert refused["decision"] == "source_snapshot_changed"
    assert "changed after index planning" in refused["error"]
    assert _logical_index_rows(db_path) == before

    recovery = _index_plan(
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="recovery",
        at="2026-08-13T12:05:00+00:00",
    )
    assert recovery["data"]["execution"]["strategy"] == "record_append_delta"
    assert recovery["data"]["execution"]["delta"] == {"documents": 2, "chunks": 2}
    recovered = _write_index_plan(
        plan=recovery,
        db_path=db_path,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="recovery",
        at="2026-08-13T12:05:00+00:00",
    )
    assert recovered["ok"] is True
    assert recovered["counts"]["documents"] == 3


def test_index_append_delta_preserves_parse_errors_and_matches_full_oracle(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    source_path = events_root / "2026" / "08" / "events.jsonl"
    sources = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    first = _incremental_event("event-1", "2026-08-13T12:00:00+00:00", "alpha")
    second = _incremental_event("event-2", "2026-08-13T12:01:00+00:00", "beta")
    _write_jsonl(source_path, [first])
    delta_db = tmp_path / "delta" / "nervous.db"
    seed = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="seed",
        at="2026-08-13T12:02:00+00:00",
    )
    _write_index_plan(
        plan=seed,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="seed",
        at="2026-08-13T12:02:00+00:00",
    )

    with source_path.open("a", encoding="utf-8") as stream:
        stream.write("not-json\n")
    malformed = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="malformed",
        at="2026-08-13T12:03:00+00:00",
    )
    assert malformed["data"]["execution"]["strategy"] == "record_append_delta"
    assert malformed["data"]["summary"]["parse_errors"] == 1
    malformed_result = _write_index_plan(
        plan=malformed,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="malformed",
        at="2026-08-13T12:03:00+00:00",
    )
    assert malformed_result["ok"] is False
    assert malformed_result["counts"]["documents"] == 1

    with source_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(second, sort_keys=True) + "\n")
    continued = _index_plan(
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="continued",
        at="2026-08-13T12:04:00+00:00",
    )
    assert continued["data"]["summary"]["parse_errors"] == 1
    continued_result = _write_index_plan(
        plan=continued,
        db_path=delta_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="continued",
        at="2026-08-13T12:04:00+00:00",
    )
    assert continued_result["ok"] is False
    assert continued_result["counts"]["documents"] == 2

    oracle_db = tmp_path / "oracle" / "nervous.db"
    oracle = _index_plan(
        db_path=oracle_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        sources=sources,
        run_id="oracle",
        at="2026-08-13T12:05:00+00:00",
        force_full=True,
    )
    oracle_result = _write_index_plan(
        plan=oracle,
        db_path=oracle_db,
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        run_id="oracle",
        at="2026-08-13T12:05:00+00:00",
    )
    assert oracle_result["ok"] is False
    assert _logical_index_rows(delta_db) == _logical_index_rows(oracle_db)
