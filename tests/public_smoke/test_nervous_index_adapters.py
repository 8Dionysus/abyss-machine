from __future__ import annotations

from contextlib import contextmanager
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
