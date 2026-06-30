from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
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

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_ROOT", root)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli.nervous_index_adapters, "connect_db", fake_connect)
    monkeypatch.setattr(cli.nervous_index_adapters, "initialize_db", fake_initialize)
    monkeypatch.setattr(cli.nervous_index_adapters, "index_lock", fake_lock)
    monkeypatch.setattr(cli.nervous_index_adapters, "index_lock_active", fake_lock_active)
    monkeypatch.setattr(cli.nervous_index_adapters, "write_latest", fake_write_latest)

    assert cli.nervous_index_connect(create=True) is fake_conn
    cli.nervous_index_initialize(fake_conn)
    with cli.nervous_index_lock():
        pass
    assert cli.nervous_index_lock_active() is True
    assert cli.nervous_index_write_latest({"ok": True}) == {"ok": True, "from_adapter": True}

    assert captured["connect"] == {"path": db_path, "create": True}
    assert captured["initialize_conn"] is fake_conn
    assert captured["initialize_kwargs"]["schema_path"] == schema_path
    assert captured["initialize_kwargs"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["initialize_kwargs"]["version"] == cli.VERSION
    assert captured["lock_root"] == root
    assert captured["active_root"] == root
    assert captured["write_latest"]["path"] == latest_path


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
