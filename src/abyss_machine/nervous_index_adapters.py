from __future__ import annotations

from contextlib import contextmanager
import fcntl
import grp
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Callable

from . import nervous_index


DEFAULT_STATE_GROUP = "wheel"

ConnectDb = Callable[[Path, bool], sqlite3.Connection]
CountDb = Callable[[Path], dict[str, Any]]


def _chown_group(path: Path, group: str) -> None:
    try:
        os.chown(path, -1, grp.getgrnam(group).gr_gid)
    except (KeyError, OSError):
        pass


def apply_state_file_mode(path: Path, *, mode: int = 0o664, group: str = DEFAULT_STATE_GROUP) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass
    _chown_group(path, group)


def connect_db(db_path: Path, create: bool = False) -> sqlite3.Connection:
    return nervous_index.connect_db(db_path, create=create)


def write_schema_sql(
    schema_path: Path,
    schema_sql: str,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> str | None:
    try:
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(schema_path.parent),
            prefix=f".{schema_path.name}.",
            delete=False,
        ) as tmp:
            tmp.write(schema_sql)
            tmp.write("\n")
            tmp_name = Path(tmp.name)
        apply_state_file_mode(tmp_name, group=group)
        os.replace(tmp_name, schema_path)
        return None
    except OSError as exc:
        return str(exc)


def initialize_db(
    conn: sqlite3.Connection,
    *,
    schema_path: Path,
    schema_sql: str,
    schema_prefix: str,
    version: str,
    group: str = DEFAULT_STATE_GROUP,
) -> str | None:
    nervous_index.initialize_db(conn, schema_prefix=schema_prefix, version=version)
    return write_schema_sql(schema_path, schema_sql, group=group)


@contextmanager
def index_lock(root: Path) -> Any:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "index.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def index_lock_active(root: Path) -> bool:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "index.lock"
    try:
        with lock_path.open("w", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            finally:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
    except OSError:
        return False
    return False


def write_latest(
    data: dict[str, Any],
    latest_path: Path,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any]:
    error = safe_atomic_write_json(latest_path, data, group=group)
    if error:
        data["write_errors"] = [error]
        data["ok"] = False
    return data


def safe_atomic_write_json(
    path: Path,
    data: dict[str, Any],
    *,
    mode: int = 0o664,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, str] | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            delete=False,
        ) as tmp:
            json.dump(data, tmp, indent=2, sort_keys=False)
            tmp.write("\n")
            tmp_name = Path(tmp.name)
        apply_state_file_mode(tmp_name, mode=mode, group=group)
        os.replace(tmp_name, path)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def vacuum_index(
    db_path: Path,
    root: Path,
    *,
    connect: ConnectDb = connect_db,
    counts: CountDb = nervous_index.counts,
) -> dict[str, Any]:
    with index_lock(root):
        conn = connect(db_path, False)
        try:
            conn.execute("PRAGMA optimize")
            conn.execute("VACUUM")
        finally:
            conn.close()
    return counts(db_path)
