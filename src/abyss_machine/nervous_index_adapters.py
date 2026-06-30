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
CountsReader = Callable[[], dict[str, Any]]
FreshnessReader = Callable[..., dict[str, Any]]
LatestReader = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
LineCounter = Callable[[Path], int | None]
UnitStatusReader = Callable[[str], dict[str, Any]]


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


def freshness_document_from_paths(
    *,
    meta: dict[str, Any] | None,
    config: dict[str, Any] | None,
    facts_latest_path: Path,
    events_latest_path: Path,
    episodes_latest_path: Path,
    fact_files: list[Path],
    event_files: list[Path],
    episode_files: list[Path],
    now: Any,
    latest_reader: LatestReader,
    line_counter: LineCounter,
) -> dict[str, Any]:
    latest_fact, _latest_fact_error = latest_reader(facts_latest_path)
    latest_event, _latest_event_error = latest_reader(events_latest_path)
    latest_episode, _latest_episode_error = latest_reader(episodes_latest_path)
    history_records = 0
    history_parse_errors = 0
    history_records_by_layer = {"facts": 0, "events": 0, "episodes": 0}
    for layer, files in (
        ("facts", fact_files),
        ("events", event_files),
        ("episodes", episode_files),
    ):
        for path in files:
            lines = line_counter(path)
            if lines is None:
                history_parse_errors += 1
                continue
            history_records += int(lines)
            history_records_by_layer[layer] += int(lines)
    return nervous_index.freshness_document(
        meta=meta,
        config=config,
        latest_fact=latest_fact,
        latest_event=latest_event,
        latest_episode=latest_episode,
        history_records=history_records,
        history_records_by_layer=history_records_by_layer,
        history_parse_errors=history_parse_errors,
        now=now,
    )


def status_document_from_ports(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    config: dict[str, Any],
    config_path: Path,
    privacy: dict[str, Any],
    sources: dict[str, Any],
    sqlite_version: str,
    fts_ok: bool,
    fts_error: Any,
    db_path: Path,
    root_path: Path,
    schema_path: Path,
    latest_path: Path,
    service_name: str,
    timer_name: str,
    latest_reader: LatestReader,
    counts_reader: CountsReader,
    freshness_reader: FreshnessReader,
    unit_status_reader: UnitStatusReader,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(latest_path)
    counts = counts_reader()
    meta_for_freshness = counts.get("meta") if isinstance(counts.get("meta"), dict) else {}
    freshness = freshness_reader(meta=meta_for_freshness, config=config)
    return nervous_index.status_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        config=config,
        config_path=config_path,
        config_exists=config_path.exists(),
        privacy=privacy,
        sources=sources,
        sqlite_version=sqlite_version,
        fts_ok=fts_ok,
        fts_error=fts_error,
        latest=latest,
        latest_error=latest_error,
        counts=counts,
        freshness=freshness,
        db_path=db_path,
        db_exists=db_path.exists(),
        root_path=root_path,
        schema_path=schema_path,
        latest_path=latest_path,
        service_status=unit_status_reader(service_name),
        timer_status=unit_status_reader(timer_name),
    )


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
