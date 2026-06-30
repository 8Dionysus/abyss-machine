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
DerivedRefreshSummaryBuilder = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
EpisodesRefreshBuilder = Callable[..., dict[str, Any]]
EventsRefreshBuilder = Callable[..., dict[str, Any]]
FreshnessReader = Callable[..., dict[str, Any]]
InitializeDb = Callable[..., str | None]
LatestReader = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
LineCounter = Callable[[Path], int | None]
LockFactory = Callable[[Path], Any]
MetaReader = Callable[[Path], dict[str, Any]]
ModeApplier = Callable[..., None]
NowReader = Callable[[], str]
ProjectionBuilder = Callable[..., dict[str, Any]]
RedactText = Callable[[str], tuple[str, int]]
ReplaceContents = Callable[..., None]
ScanReader = Callable[..., dict[str, Any]]
SearchOptionsBuilder = Callable[..., dict[str, Any]]
SearchRefusalBuilder = Callable[..., dict[str, Any]]
SearchRunner = Callable[..., dict[str, Any]]
SemanticLockActive = Callable[[], bool]
SqliteMemoryConnect = Callable[[], Any]
SourceFilesReader = Callable[[tuple[Path, ...]], list[Path]]
SourceRecordsLoader = Callable[[list[Path]], tuple[list[dict[str, Any]], list[dict[str, Any]]]]
SymlinkTailProbe = Callable[..., bool]
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


def sqlite_fts5_ok(
    connect: SqliteMemoryConnect = lambda: sqlite3.connect(":memory:"),
) -> tuple[bool, str | None]:
    conn = None
    try:
        conn = connect()
        conn.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(body)")
        conn.execute("INSERT INTO fts_probe(body) VALUES (?)", ("thermal battery storage",))
        row = conn.execute("SELECT count(*) FROM fts_probe WHERE fts_probe MATCH ?", ("thermal",)).fetchone()
        return bool(row and row[0] == 1), None
    except sqlite3.Error as exc:
        return False, str(exc)
    finally:
        if conn is not None:
            conn.close()


def path_has_symlink_tail(path: Path, *, stop_at: Path | None = None) -> bool:
    try:
        resolved_stop = stop_at.resolve() if stop_at else None
    except OSError:
        resolved_stop = None
    current = path
    checked: list[Path] = []
    while True:
        checked.append(current)
        if current.parent == current:
            break
        if resolved_stop is not None:
            try:
                if current.resolve() == resolved_stop:
                    break
            except OSError:
                pass
        current = current.parent
    return any(item.exists() and item.is_symlink() for item in checked)


def db_counts(db_path: Path, count: CountDb = nervous_index.counts) -> dict[str, Any]:
    return count(db_path)


def search_from_ports(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    db_path: Path,
    query: str,
    config: dict[str, Any],
    privacy: dict[str, Any],
    requested_limit: int | None,
    requested_order: str,
    dedupe: bool,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    freshness_reader: FreshnessReader,
    meta_reader: MetaReader = nervous_index.read_meta,
    options_builder: SearchOptionsBuilder = nervous_index.search_options,
    refusal_builder: SearchRefusalBuilder = nervous_index.search_refused_result,
    search_runner: SearchRunner = nervous_index.search_index,
) -> dict[str, Any]:
    options = options_builder(
        config,
        requested_limit=requested_limit,
        requested_order=requested_order,
    )
    if bool(privacy.get("global_pause")):
        return refusal_builder(
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )
    freshness = None
    if db_path.exists():
        freshness = freshness_reader(meta=meta_reader(db_path), config=config)
    return search_runner(
        db_path=db_path,
        query=query,
        final_limit=options["final_limit"],
        dedupe=dedupe,
        order=options["order"],
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        snippet_tokens=options["snippet_tokens"],
        scan_limit=options["scan_limit"],
        freshness=freshness,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


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


def path_is_routed_under(db_path: Path, storage_root: Path) -> bool:
    try:
        resolved_storage_root = storage_root.resolve()
        db_resolved = db_path.resolve() if db_path.exists() else db_path.parent.resolve() / db_path.name
        return str(db_resolved) == str(resolved_storage_root) or str(db_resolved).startswith(str(resolved_storage_root) + os.sep)
    except OSError:
        return False


def validation_document_from_ports(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    db_path: Path,
    storage_root: Path,
    config: dict[str, Any],
    config_path: Path,
    sources: dict[str, Any],
    fts_ok: bool,
    fts_error: Any,
    event_files: list[Path],
    episode_files: list[Path],
    counts_reader: CountsReader,
    freshness_reader: FreshnessReader,
    scan_reader: ScanReader,
    line_counter: LineCounter,
    symlink_tail_probe: SymlinkTailProbe,
    smoke_match_query: str = '"nervous" OR "storage" OR "thermal" OR "episode"',
) -> dict[str, Any]:
    db_exists = db_path.exists()
    storage_routed = path_is_routed_under(db_path, storage_root)
    symlink_tail = symlink_tail_probe(db_path, stop_at=storage_root)
    counts = counts_reader()
    meta = counts.get("meta") if isinstance(counts.get("meta"), dict) else {}
    freshness = freshness_reader(meta=meta, config=config)

    scan: dict[str, Any] | None = None
    scan_error: str | None = None
    try:
        if db_exists:
            scan = scan_reader(db_path, smoke_match_query=smoke_match_query)
    except sqlite3.Error as exc:
        scan_error = str(exc)
    event_records = sum(line_counter(path) or 0 for path in event_files)
    episode_records = sum(line_counter(path) or 0 for path in episode_files)
    return nervous_index.validation_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        db_path=db_path,
        config=config,
        config_path=config_path,
        config_exists=config_path.exists(),
        fts_ok=fts_ok,
        fts_error=fts_error,
        storage_routed=storage_routed,
        storage_root=storage_root,
        symlink_tail=symlink_tail,
        db_exists=db_exists,
        counts=counts,
        freshness=freshness,
        allowed_source_ids=nervous_index.allowed_source_ids(sources),
        scan=scan,
        scan_error=scan_error,
        private_source_ids=nervous_index.deferred_source_ids(sources),
        event_records=event_records,
        episode_records=episode_records,
    )


def derived_refresh_from_ports(
    *,
    refresh_enabled: bool,
    events_builder: EventsRefreshBuilder,
    episodes_builder: EpisodesRefreshBuilder,
    summary_builder: DerivedRefreshSummaryBuilder = nervous_index.build_index_derived_refresh_summary,
) -> dict[str, Any]:
    if not refresh_enabled:
        return {}
    events_refresh = events_builder(write_latest=True)
    episodes_refresh = episodes_builder(write_latest=True, refresh_events=False)
    return summary_builder(events_refresh, episodes_refresh)


def build_document_from_source_roots(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    started_at: str,
    db_path: Path,
    config_path: Path,
    privacy: dict[str, Any],
    sources: dict[str, Any],
    source_roots: tuple[Path, ...],
    derived_refresh: dict[str, Any],
    redact_text: RedactText,
    source_files_reader: SourceFilesReader = nervous_index.index_source_files,
    source_records_loader: SourceRecordsLoader = nervous_index.load_source_records,
    projection_builder: ProjectionBuilder = nervous_index.build_index_projection,
) -> dict[str, Any]:
    enabled_sources = nervous_index.enabled_index_source_ids(sources)
    source_files = source_files_reader(source_roots)
    source_records, parse_errors = source_records_loader(source_files)
    projection = projection_builder(
        source_records,
        sources,
        enabled_sources,
        started_at=started_at,
        schema_prefix=schema_prefix,
        redact_text=redact_text,
    )
    data = nervous_index.build_index_build_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        run_id=run_id,
        started_at=started_at,
        db_path=db_path,
        config_path=config_path,
        privacy=privacy,
        sources=sources,
        enabled_sources=enabled_sources,
        source_files=source_files,
        projection=projection,
        parse_errors=parse_errors,
        derived_refresh=derived_refresh,
    )
    return {
        "data": data,
        "source_files": source_files,
        "projection": projection,
        "parse_errors": parse_errors,
        "enabled_sources": sorted(enabled_sources),
    }


def write_build_projection(
    data: dict[str, Any],
    *,
    db_path: Path,
    root: Path,
    schema_path: Path,
    schema_sql: str,
    schema_prefix: str,
    version: str,
    group: str,
    run_id: str,
    started_at: str,
    source_files: list[Path],
    projection: dict[str, Any],
    parse_errors: list[dict[str, Any]],
    facts_root: Path,
    events_root: Path,
    episodes_root: Path,
    source_state_change_id: Any,
    privacy_state_change_id: Any,
    semantic_lock_active: SemanticLockActive,
    now: NowReader,
    counts_reader: CountsReader,
    lock: LockFactory = index_lock,
    connect: ConnectDb = connect_db,
    initialize: InitializeDb = initialize_db,
    replace_contents: ReplaceContents = nervous_index.replace_index_contents,
    apply_mode: ModeApplier = apply_state_file_mode,
) -> dict[str, Any]:
    documents = projection["documents"]
    all_chunks = projection["chunks"]
    skipped_records = projection["skipped_records"]
    projection_summary = projection["summary"]
    try:
        with lock(root):
            if semantic_lock_active():
                return nervous_index.with_index_semantic_lock_deferred(data, checked_at="pre_write")
            conn = connect(db_path, True)
            try:
                initialize(
                    conn,
                    schema_path=schema_path,
                    schema_sql=schema_sql,
                    schema_prefix=schema_prefix,
                    version=version,
                    group=group,
                )
                conn.commit()
                meta_values = nervous_index.build_index_meta_values(
                    schema_prefix=schema_prefix,
                    version=version,
                    run_id=run_id,
                    built_at=now(),
                    source_files=source_files,
                    projection=projection,
                    facts_root=facts_root,
                    events_root=events_root,
                    episodes_root=episodes_root,
                    source_state_change_id=source_state_change_id,
                    privacy_state_change_id=privacy_state_change_id,
                )
                finished_at = now()
                replace_contents(
                    conn,
                    documents=documents,
                    chunks=all_chunks,
                    meta_values=meta_values,
                    run_id=run_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    ok=not parse_errors,
                    source_files=len(source_files),
                    records_seen=int(projection_summary["records_seen"]),
                    records_indexed=len(documents),
                    documents_indexed=len(documents),
                    chunks_indexed=len(all_chunks),
                    errors={"parse_errors": parse_errors[:20], "skipped_records": skipped_records[:20]},
                )
                apply_mode(db_path, group=group)
            finally:
                conn.close()
        return nervous_index.with_index_write_success(
            data,
            finished_at=finished_at,
            counts=counts_reader(),
            parse_errors=parse_errors,
        )
    except BlockingIOError:
        return nervous_index.with_index_error(data, "another index build is already running")
    except (OSError, sqlite3.Error) as exc:
        return nervous_index.with_index_error(data, exc)


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
