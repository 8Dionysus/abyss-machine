from __future__ import annotations

from contextlib import contextmanager
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any, Callable

from . import nervous_events
from . import nervous_index


DEFAULT_STATE_GROUP = "wheel"

ConnectDb = Callable[[Path, bool], sqlite3.Connection]
CountDb = Callable[..., dict[str, Any]]
CountsReader = Callable[[], dict[str, Any]]
DerivedRefreshSummaryBuilder = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
EpisodesRefreshBuilder = Callable[..., dict[str, Any]]
EventsRefreshBuilder = Callable[..., dict[str, Any]]
FreshnessReader = Callable[..., dict[str, Any]]
InitializeDb = Callable[..., str | None]
LatestReader = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
LineCounter = Callable[[Path], int | None]
LineCountsReader = Callable[[list[Path]], tuple[dict[Path, int | None], str]]
LockFactory = Callable[[Path], Any]
MetaReader = Callable[[Path], dict[str, Any]]
ModeApplier = Callable[..., None]
NowReader = Callable[[], str]
ProjectionBuilder = Callable[..., dict[str, Any]]
RedactText = Callable[[str], tuple[str, int]]
ReplaceContents = Callable[..., None]
UpdateContents = Callable[..., None]
ScanReader = Callable[..., dict[str, Any]]
SearchOptionsBuilder = Callable[..., dict[str, Any]]
SearchRefusalBuilder = Callable[..., dict[str, Any]]
SearchRunner = Callable[..., dict[str, Any]]
SemanticLockActive = Callable[[], bool]
SqliteMemoryConnect = Callable[[], Any]
SourceFilesReader = Callable[[tuple[Path, ...]], list[Path]]
SourceRecordsLoader = Callable[[list[Path]], tuple[list[dict[str, Any]], list[dict[str, Any]]]]
SourceBytesReader = Callable[[Path], bytes]
SourceTailReader = Callable[[Path, int], bytes]
SourceObservationReader = Callable[[Path], dict[str, int]]
SourceSnapshotValidator = Callable[..., str | None]
SymlinkTailProbe = Callable[..., bool]
UnitStatusReader = Callable[[str], dict[str, Any]]


def _chown_group(path: Path, group: str) -> None:
    try:
        os.chown(path, -1, grp.getgrnam(group).gr_gid)
    except (KeyError, OSError):
        pass


def apply_state_file_mode(path: Path, *, mode: int = 0o664, group: str = DEFAULT_STATE_GROUP) -> None:
    os.chmod(path, mode)
    _chown_group(path, group)


def _discard_temp_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except OSError:
        pass


def connect_db(db_path: Path, create: bool = False) -> sqlite3.Connection:
    return nervous_index.connect_db(db_path, create=create)


def source_file_observation(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {
        "device": int(stat.st_dev),
        "inode": int(stat.st_ino),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "ctime_ns": int(stat.st_ctime_ns),
    }


def source_file_tail(path: Path, offset: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(max(int(offset), 0))
        return stream.read()


def admitted_append_attestation(
    *,
    path: str,
    previous: dict[str, Any],
    observation: dict[str, int],
    attestation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(attestation, dict):
        return None
    core = {
        key: attestation.get(key)
        for key in ("schema", "path", "basis", "base", "current")
    }
    if (
        core["schema"] != nervous_events.EVENT_SOURCE_DELTA_ATTESTATION_ABI
        or core["path"] != path
        or core["basis"] != "append_only"
        or str(attestation.get("proof_sha256") or "")
        != nervous_index.stable_json_sha256(core)
    ):
        return None
    base = core["base"] if isinstance(core["base"], dict) else {}
    current = core["current"] if isinstance(core["current"], dict) else {}
    previous_size = int(previous.get("source_size_bytes") or 0)
    previous_lines = int(previous.get("source_line_count") or 0)
    current_size = int(current.get("size_bytes") or -1)
    current_lines = int(current.get("line_count") or -1)
    current_sha = str(current.get("sha256") or "")
    if (
        str(base.get("sha256") or "") != str(previous.get("source_sha256") or "")
        or int(base.get("size_bytes") or -1) != previous_size
        or int(base.get("line_count") or -1) != previous_lines
        or current.get("observation") != observation
        or str(current.get("path") or "") != path
        or current_size <= previous_size
        or current_lines < previous_lines
        or len(current_sha) != 64
    ):
        return None
    return current


def validate_source_snapshot(
    *,
    source_roots: tuple[Path, ...],
    expected_observations: dict[str, dict[str, int]],
    source_files_reader: SourceFilesReader = nervous_index.index_source_files,
    observation_reader: SourceObservationReader = source_file_observation,
) -> str | None:
    try:
        current_files = source_files_reader(source_roots)
    except OSError as exc:
        return f"source snapshot rescan failed: {exc}"
    current_paths = [str(path) for path in current_files]
    expected_paths = sorted(str(path) for path in expected_observations)
    if current_paths != expected_paths:
        return "source partition set changed after index planning"
    for path in current_files:
        path_text = str(path)
        try:
            current = observation_reader(path)
        except OSError as exc:
            return f"source snapshot observation failed for {path_text}: {exc}"
        if current != expected_observations.get(path_text):
            return f"source partition changed after index planning: {path_text}"
    return None


def write_schema_sql(
    schema_path: Path,
    schema_sql: str,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> str | None:
    tmp_name: Path | None = None
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
        _discard_temp_file(tmp_name)
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


def db_counts_bounded(
    db_path: Path,
    *,
    busy_timeout_ms: int,
    count: CountDb = nervous_index.counts,
) -> dict[str, Any]:
    return count(
        db_path,
        busy_timeout_ms=busy_timeout_ms,
        allow_expensive_fts_fallback=False,
    )


def source_present(
    db_path: Path,
    source_id: str,
    *,
    busy_timeout_ms: int,
    probe: Callable[..., dict[str, Any]] = nervous_index.source_present,
) -> dict[str, Any]:
    return probe(db_path, source_id, busy_timeout_ms=busy_timeout_ms)


def scan_index(
    db_path: Path,
    *,
    smoke_match_query: str,
    scan: ScanReader = nervous_index.scan_index,
) -> dict[str, Any]:
    return scan(db_path, smoke_match_query=smoke_match_query)


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
    tmp_name: Path | None = None
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
        _discard_temp_file(tmp_name)
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
    line_counts_reader: LineCountsReader | None = None,
    history_count_method: str = "latest_documents_plus_jsonl_line_counts",
) -> dict[str, Any]:
    latest_fact, _latest_fact_error = latest_reader(facts_latest_path)
    latest_event, _latest_event_error = latest_reader(events_latest_path)
    latest_episode, _latest_episode_error = latest_reader(episodes_latest_path)
    history_records = 0
    history_parse_errors = 0
    history_records_by_layer = {"facts": 0, "events": 0, "episodes": 0}
    layered_files = (
        ("facts", fact_files),
        ("events", event_files),
        ("episodes", episode_files),
    )
    if line_counts_reader is not None:
        line_counts, history_count_method = line_counts_reader(
            [path for _layer, files in layered_files for path in files]
        )

        def effective_line_counter(path: Path) -> int | None:
            return line_counts.get(path)
    else:
        effective_line_counter = line_counter
    for layer, files in layered_files:
        for path in files:
            lines = effective_line_counter(path)
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
        history_count_method=history_count_method,
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
    history_by_layer = freshness.get("history_records_by_layer")
    if isinstance(history_by_layer, dict):
        event_records = int(history_by_layer.get("events") or 0)
        episode_records = int(history_by_layer.get("episodes") or 0)
    else:
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
    force_full: bool = False,
    include_internal_attestations: bool = False,
    events_builder: EventsRefreshBuilder,
    episodes_builder: EpisodesRefreshBuilder,
    summary_builder: DerivedRefreshSummaryBuilder = nervous_index.build_index_derived_refresh_summary,
) -> dict[str, Any]:
    if not refresh_enabled:
        return {}
    events_refresh = events_builder(write_latest=True, force_full=force_full)
    episodes_refresh = episodes_builder(
        write_latest=True,
        refresh_events=False,
        force_full=force_full,
    )
    summary = summary_builder(events_refresh, episodes_refresh)
    if include_internal_attestations:
        incremental = (
            events_refresh.get("incremental")
            if isinstance(events_refresh.get("incremental"), dict)
            else {}
        )
        attestations = (
            incremental.get("delta_attestations")
            if events_refresh.get("ok") is True
            and isinstance(incremental.get("delta_attestations"), list)
            else []
        )
        summary = {
            **summary,
            "_internal_source_delta_attestations": [
                item for item in attestations if isinstance(item, dict)
            ],
        }
    return summary


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


def build_incremental_document_from_source_roots(
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
    force_full: bool = False,
    allow_append_delta: bool = True,
    source_files_reader: SourceFilesReader = nervous_index.index_source_files,
    source_bytes_reader: SourceBytesReader = lambda path: path.read_bytes(),
    source_tail_reader: SourceTailReader = source_file_tail,
    source_observation_reader: SourceObservationReader = source_file_observation,
    source_delta_attestations: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    manifest_reader: Callable[..., dict[str, Any]] = nervous_index.read_source_manifest,
    counts_reader: Callable[..., dict[str, Any]] = nervous_index.counts,
    projection_builder: ProjectionBuilder = nervous_index.build_index_projection,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    plan_started = monotonic()
    enabled_sources = nervous_index.enabled_index_source_ids(sources)
    projection_identity = nervous_index.index_projection_identity(
        sources,
        enabled_sources,
        schema_prefix=schema_prefix,
    )
    source_files = source_files_reader(source_roots)
    manifest_state = manifest_reader(db_path)
    previous_entries = (
        manifest_state.get("entries")
        if isinstance(manifest_state.get("entries"), dict)
        else {}
    )
    previous_meta = (
        manifest_state.get("meta")
        if isinstance(manifest_state.get("meta"), dict)
        else {}
    )
    if db_path.exists() and not manifest_state.get("error"):
        counts = counts_reader(
            db_path,
            busy_timeout_ms=5000,
            allow_expensive_fts_fallback=False,
        )
    else:
        counts = {}
    eligibility = nervous_index.incremental_index_eligibility(
        meta=previous_meta,
        manifest_entries=previous_entries,
        projection_identity=projection_identity,
        counts=counts,
    )
    incremental = bool(eligibility["eligible"] and not force_full)
    if force_full:
        eligibility = {
            **eligibility,
            "eligible": False,
            "reasons": [*eligibility["reasons"], "full_rebuild_forced"],
        }

    scan_started = monotonic()
    file_identities: dict[str, dict[str, Any]] = {}
    source_observations: dict[str, dict[str, int]] = {}
    source_read_errors: list[dict[str, Any]] = []
    changed_records: list[dict[str, Any]] = []
    changed_parse_errors: list[dict[str, Any]] = []
    changed_paths: list[str] = []
    replace_paths: list[str] = []
    append_paths: list[str] = []
    unchanged_paths: list[str] = []
    metadata_refreshed_paths: list[str] = []
    content_bytes_hashed = 0
    content_bytes_reused = 0
    append_prefix_bytes_verified = 0
    attested_tail_bytes_read = 0
    attested_prefix_bytes_reused = 0
    admitted_attestation_paths: list[str] = []
    attestation_by_path = {
        str(item.get("path")): item
        for item in source_delta_attestations
        if isinstance(item, dict) and item.get("path")
    }
    for source_path in source_files:
        path_text = str(source_path)
        previous = previous_entries.get(path_text) if isinstance(previous_entries.get(path_text), dict) else {}
        try:
            observation = source_observation_reader(source_path)
            source_observations[path_text] = observation
        except OSError as exc:
            observation = None
            read_error = str(exc)
        else:
            read_error = None
        metadata_unchanged = bool(
            incremental
            and read_error is None
            and previous
            and previous.get("source_observation") == observation
            and int(previous.get("source_size_bytes") or 0)
            == int(observation.get("size_bytes", -1))
            and str(previous.get("projection_identity") or "") == projection_identity
        )
        if metadata_unchanged:
            file_identities[path_text] = {
                "source_path": path_text,
                "source_sha256": str(previous.get("source_sha256") or ""),
                "source_size_bytes": int(previous.get("source_size_bytes") or 0),
                "source_line_count": int(previous.get("source_line_count") or 0),
                "source_observation": observation,
            }
            content_bytes_reused += int(previous.get("source_size_bytes") or 0)
            unchanged_paths.append(path_text)
            continue
        attested_current = admitted_append_attestation(
            path=path_text,
            previous=previous,
            observation=observation or {},
            attestation=attestation_by_path.get(path_text),
        )
        if attested_current is not None and observation is not None:
            previous_size = int(previous.get("source_size_bytes") or 0)
            payload: bytes | None = None
            try:
                for _attempt in range(2):
                    before = source_observation_reader(source_path)
                    candidate = source_tail_reader(source_path, previous_size)
                    after = source_observation_reader(source_path)
                    if (
                        before == observation
                        and after == observation
                        and len(candidate)
                        == int(attested_current.get("size_bytes") or -1) - previous_size
                    ):
                        payload = candidate
                        break
            except OSError:
                payload = None
            if payload is not None:
                source_sha256 = str(attested_current["sha256"])
                source_size_bytes = int(attested_current["size_bytes"])
                source_line_count = int(attested_current["line_count"])
                file_identities[path_text] = {
                    "source_path": path_text,
                    "source_sha256": source_sha256,
                    "source_size_bytes": source_size_bytes,
                    "source_line_count": source_line_count,
                    "source_observation": observation,
                }
                changed_paths.append(path_text)
                append_paths.append(path_text)
                attested_tail_bytes_read += len(payload)
                attested_prefix_bytes_reused += previous_size
                admitted_attestation_paths.append(path_text)
                records, errors = nervous_index.parse_jsonl_records_with_metadata(
                    source_path,
                    payload.decode("utf-8", errors="replace"),
                    source_sha256=source_sha256,
                    line_offset=int(previous.get("source_line_count") or 0),
                )
                changed_records.extend(records)
                changed_parse_errors.extend(errors)
                continue
        try:
            if read_error is not None:
                raise OSError(read_error)
            raw: bytes | None = None
            for _attempt in range(2):
                before = source_observation_reader(source_path)
                candidate = source_bytes_reader(source_path)
                after = source_observation_reader(source_path)
                if before == after and int(after.get("size_bytes", -1)) == len(candidate):
                    raw = candidate
                    observation = after
                    break
            if raw is None or observation is None:
                raise OSError("source changed repeatedly while being read")
            source_observations[path_text] = observation
            source_sha256 = hashlib.sha256(raw).hexdigest()
            content_bytes_hashed += len(raw)
            source_size_bytes = len(raw)
            source_line_count = len(raw.splitlines())
            read_error = None
        except OSError as exc:
            raw = b""
            read_error = str(exc)
            source_sha256 = hashlib.sha256(f"unreadable:{read_error}".encode("utf-8")).hexdigest()
            source_size_bytes = -1
            source_line_count = 0
        file_identities[path_text] = {
            "source_path": path_text,
            "source_sha256": source_sha256,
            "source_size_bytes": source_size_bytes,
            "source_line_count": source_line_count,
            "source_observation": observation or {},
        }
        content_unchanged = bool(
            incremental
            and read_error is None
            and previous
            and str(previous.get("source_sha256") or "") == source_sha256
            and int(previous.get("source_size_bytes") or 0) == source_size_bytes
            and int(previous.get("source_line_count") or 0) == source_line_count
            and str(previous.get("projection_identity") or "") == projection_identity
        )
        if content_unchanged:
            unchanged_paths.append(path_text)
            metadata_refreshed_paths.append(path_text)
            continue
        changed_paths.append(path_text)
        if read_error is not None:
            replace_paths.append(path_text)
            error = {"path": path_text, "error": read_error}
            changed_parse_errors.append(error)
            source_read_errors.append(error)
            continue
        previous_size = int(previous.get("source_size_bytes") or 0)
        previous_line_count = int(previous.get("source_line_count") or 0)
        previous_prefix = raw[:previous_size] if 0 <= previous_size < source_size_bytes else b""
        append_only = bool(
            incremental
            and allow_append_delta
            and previous
            and 0 <= previous_size < source_size_bytes
            and (previous_size == 0 or previous_prefix.endswith((b"\n", b"\r")))
            and len(previous_prefix.splitlines()) == previous_line_count
            and hashlib.sha256(previous_prefix).hexdigest()
            == str(previous.get("source_sha256") or "")
        )
        if append_only:
            append_prefix_bytes_verified += previous_size
            append_paths.append(path_text)
            payload = raw[previous_size:]
            line_offset = previous_line_count
        else:
            replace_paths.append(path_text)
            payload = raw
            line_offset = 0
        records, errors = nervous_index.parse_jsonl_records_with_metadata(
            source_path,
            payload.decode("utf-8", errors="replace"),
            source_sha256=source_sha256,
            line_offset=line_offset,
        )
        changed_records.extend(records)
        changed_parse_errors.extend(errors)
    removed_paths = sorted(set(previous_entries) - {str(path) for path in source_files})
    scan_finished = monotonic()

    projection_started = monotonic()
    projection = projection_builder(
        changed_records,
        sources,
        enabled_sources,
        started_at=started_at,
        schema_prefix=schema_prefix,
        redact_text=redact_text,
    )
    changed_identities = {path: file_identities[path] for path in changed_paths}
    changed_entries = nervous_index.build_source_manifest_entries(
        changed_identities,
        projection.get("source_summaries") if isinstance(projection.get("source_summaries"), dict) else {},
        changed_parse_errors,
        projection_identity=projection_identity,
        updated_at=generated_at,
    )
    metadata_entries = {
        path: {
            **previous_entries[path],
            "schema": nervous_index.INDEX_SOURCE_MANIFEST_SCHEMA,
            "source_observation": file_identities[path]["source_observation"],
            "updated_at": generated_at,
        }
        for path in metadata_refreshed_paths
    }
    for path in append_paths:
        previous = previous_entries[path]
        changed = changed_entries[path]
        changed["summary"] = nervous_index.merge_index_summaries([
            previous.get("summary") if isinstance(previous.get("summary"), dict) else {},
            changed.get("summary") if isinstance(changed.get("summary"), dict) else {},
        ])
        changed["parse_errors"] = [
            item
            for item in [
                *(previous.get("parse_errors") if isinstance(previous.get("parse_errors"), list) else []),
                *(changed.get("parse_errors") if isinstance(changed.get("parse_errors"), list) else []),
            ][:20]
            if isinstance(item, dict)
        ]
        changed["skipped_records"] = [
            item
            for item in [
                *(previous.get("skipped_records") if isinstance(previous.get("skipped_records"), list) else []),
                *(changed.get("skipped_records") if isinstance(changed.get("skipped_records"), list) else []),
            ][:20]
            if isinstance(item, dict)
        ]
    if incremental:
        manifest_entries = {
            path: entry
            for path, entry in previous_entries.items()
            if path in file_identities
        }
        manifest_entries.update(changed_entries)
        manifest_entries.update(metadata_entries)
    else:
        manifest_entries = changed_entries
    aggregate = nervous_index.aggregate_manifest_entries(manifest_entries)
    projection["summary"] = aggregate["summary"]
    projection["skipped_records"] = aggregate["skipped_records"]
    parse_errors = aggregate["parse_errors"]
    projection_finished = monotonic()

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
    if source_read_errors:
        strategy = "source_snapshot_refused"
    elif not incremental:
        strategy = "full_rebuild"
    elif not changed_paths and not removed_paths and not metadata_refreshed_paths:
        strategy = "fixed_point_noop"
    elif append_paths and replace_paths:
        strategy = "hybrid_partition_append_delta"
    elif append_paths:
        strategy = "record_append_delta"
    else:
        strategy = "file_partition_delta"
    data["execution"] = {
        "strategy": strategy,
        "full_rebuild_fallback_reasons": [] if incremental else eligibility["reasons"],
        "projection_identity": projection_identity,
        "base_run_id": previous_meta.get("run_id"),
        "source_partitions": {
            "total": len(source_files),
            "changed": len(changed_paths),
            "unchanged": len(unchanged_paths),
            "removed": len(removed_paths),
            "replaced": len(replace_paths),
            "appended": len(append_paths),
            "metadata_refreshed": len(metadata_refreshed_paths),
        },
        "delta": {
            "documents": len(projection["documents"]),
            "chunks": len(projection["chunks"]),
        },
        "timings_ms": {
            "source_scan_and_hash": round((scan_finished - scan_started) * 1000.0, 3),
            "changed_projection": round((projection_finished - projection_started) * 1000.0, 3),
            "plan_total": round((projection_finished - plan_started) * 1000.0, 3),
        },
        "source_scan": {
            "partitions_reused_by_observation": len(unchanged_paths),
            "content_bytes_reused": content_bytes_reused,
            "content_bytes_hashed": content_bytes_hashed,
            "append_prefix_bytes_verified": append_prefix_bytes_verified,
            "attested_tail_bytes_read": attested_tail_bytes_read,
            "attested_prefix_bytes_reused": attested_prefix_bytes_reused,
            "source_delta_attestations_admitted": len(admitted_attestation_paths),
            "observation_fields": ["device", "inode", "size_bytes", "mtime_ns", "ctime_ns"],
        },
        "admission": {
            "write_allowed": not source_read_errors,
            "source_snapshot_stable": not source_read_errors,
            "source_read_errors": source_read_errors[:20],
            "append_delta_enabled": bool(allow_append_delta),
        },
    }
    return {
        "data": data,
        "source_files": source_files,
        "projection": projection,
        "parse_errors": parse_errors,
        "enabled_sources": sorted(enabled_sources),
        "manifest_entries": manifest_entries,
        "projection_identity": projection_identity,
        "changed_source_paths": sorted(set(changed_paths) | set(removed_paths)),
        "replace_source_paths": sorted(set(replace_paths) | set(removed_paths)),
        "append_source_paths": sorted(set(append_paths)),
        "write_mode": (
            "refuse"
            if source_read_errors
            else "full"
            if not incremental
            else "noop"
            if strategy == "fixed_point_noop"
            else "delta"
        ),
        "base_run_id": previous_meta.get("run_id"),
        "eligibility": eligibility,
        "source_observations": source_observations,
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
    manifest_entries: dict[str, dict[str, Any]] | None = None,
    projection_identity: str | None = None,
    changed_source_paths: list[str] | tuple[str, ...] | None = None,
    replace_source_paths: list[str] | tuple[str, ...] | None = None,
    append_source_paths: list[str] | tuple[str, ...] | None = None,
    source_observations: dict[str, dict[str, int]] | None = None,
    write_mode: str = "full",
    base_run_id: Any = None,
    lock: LockFactory = index_lock,
    connect: ConnectDb = connect_db,
    initialize: InitializeDb = initialize_db,
    replace_contents: ReplaceContents = nervous_index.replace_index_contents,
    update_contents: UpdateContents = nervous_index.update_index_contents_delta,
    source_snapshot_validator: SourceSnapshotValidator = validate_source_snapshot,
    apply_mode: ModeApplier = apply_state_file_mode,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    documents = projection["documents"]
    all_chunks = projection["chunks"]
    skipped_records = projection["skipped_records"]
    projection_summary = projection["summary"]
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    timings = execution.get("timings_ms") if isinstance(execution.get("timings_ms"), dict) else {}

    def snapshot_refused(error: str) -> dict[str, Any]:
        refused = nervous_index.with_index_error(data, error)
        refused["refused"] = True
        refused["decision"] = "source_snapshot_changed"
        refused["policy"] = {"database_touched": False, "retry_via_timer": True}
        return refused

    if write_mode == "refuse":
        return snapshot_refused("source snapshot could not be read consistently during index planning")
    if write_mode not in {"full", "delta", "noop"}:
        return snapshot_refused(f"unsupported index write mode: {write_mode}")
    write_started = monotonic()
    try:
        lock_wait_started = monotonic()
        with lock(root):
            lock_acquired = monotonic()
            if semantic_lock_active():
                return nervous_index.with_index_semantic_lock_deferred(data, checked_at="pre_write")
            if source_observations is not None:
                snapshot_error = source_snapshot_validator(
                    source_roots=(facts_root, events_root, episodes_root),
                    expected_observations=source_observations,
                )
                if snapshot_error is not None:
                    return snapshot_refused(snapshot_error)
            if write_mode == "noop":
                verify_started = monotonic()
                conn = connect(db_path, False)
                try:
                    current_meta = {
                        str(row["key"]): row["value"]
                        for row in conn.execute("SELECT key, value FROM meta")
                    }
                    if str(current_meta.get("run_id") or "") != str(base_run_id or ""):
                        raise sqlite3.OperationalError("incremental index base run changed before no-op verification")
                finally:
                    conn.close()
                verify_finished = monotonic()
                counts_started = monotonic()
                final_counts = counts_reader()
                counts_finished = monotonic()
                finished_at = now()
                data = dict(data)
                data["execution"] = {
                    **execution,
                    "write_mode": write_mode,
                    "database_touched": False,
                    "timings_ms": {
                        **timings,
                        "write_lock_wait": round((lock_acquired - lock_wait_started) * 1000.0, 3),
                        "db_initialize": 0.0,
                        "db_write": 0.0,
                        "db_noop_verify": round((verify_finished - verify_started) * 1000.0, 3),
                        "post_write_counts": round((counts_finished - counts_started) * 1000.0, 3),
                        "write_stage_total": round((counts_finished - write_started) * 1000.0, 3),
                    },
                }
                return nervous_index.with_index_write_success(
                    data,
                    finished_at=finished_at,
                    counts=final_counts,
                    parse_errors=parse_errors,
                    parse_error_count=int(projection_summary.get("parse_errors", len(parse_errors))),
                )
            conn = connect(db_path, True)
            try:
                initialize_started = monotonic()
                initialize(
                    conn,
                    schema_path=schema_path,
                    schema_sql=schema_sql,
                    schema_prefix=schema_prefix,
                    version=version,
                    group=group,
                )
                conn.commit()
                initialize_finished = monotonic()
                if write_mode == "delta":
                    current_meta = {
                        str(row["key"]): row["value"]
                        for row in conn.execute("SELECT key, value FROM meta")
                    }
                    if str(current_meta.get("run_id") or "") != str(base_run_id or ""):
                        raise sqlite3.OperationalError("incremental index base run changed before write")
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
                db_write_started = monotonic()
                resolved_finish: dict[str, str] = {}

                def finish_timestamp() -> str:
                    value = now()
                    resolved_finish["value"] = value
                    return value

                common_write = {
                    "conn": conn,
                    "documents": documents,
                    "chunks": all_chunks,
                    "meta_values": meta_values,
                    "run_id": run_id,
                    "started_at": started_at,
                    "finished_at": finish_timestamp,
                    "ok": int(projection_summary.get("parse_errors", len(parse_errors))) == 0,
                    "source_files": len(source_files),
                    "records_seen": int(projection_summary["records_seen"]),
                    "records_indexed": int(projection_summary["records_indexed"]),
                    "documents_indexed": int(projection_summary["documents_indexed"]),
                    "chunks_indexed": int(projection_summary["chunks_indexed"]),
                    "errors": {"parse_errors": parse_errors[:20], "skipped_records": skipped_records[:20]},
                }
                delta_write_timings: dict[str, float] = {}
                if write_mode == "delta":
                    update_result = update_contents(
                        **common_write,
                        changed_source_paths=changed_source_paths or [],
                        replace_source_paths=replace_source_paths,
                        append_source_paths=append_source_paths,
                        source_manifest_entries=manifest_entries or {},
                        projection_identity=str(projection_identity or ""),
                    )
                    if isinstance(update_result, dict):
                        delta_write_timings = {
                            f"db_delta_{key}": float(value)
                            for key, value in update_result.items()
                            if isinstance(key, str) and isinstance(value, (int, float))
                        }
                else:
                    replace_contents(
                        **common_write,
                        source_manifest_entries=manifest_entries,
                        projection_identity=projection_identity,
                    )
                db_write_finished = monotonic()
                apply_mode(db_path, group=group)
                finished_at = resolved_finish.get("value") or now()
            finally:
                conn.close()
        counts_started = monotonic()
        final_counts = counts_reader()
        counts_finished = monotonic()
        data = dict(data)
        data["execution"] = {
            **execution,
            "write_mode": write_mode,
            "database_touched": True,
            "timings_ms": {
                **timings,
                "write_lock_wait": round((lock_acquired - lock_wait_started) * 1000.0, 3),
                "db_initialize": round((initialize_finished - initialize_started) * 1000.0, 3),
                "db_write": round((db_write_finished - db_write_started) * 1000.0, 3),
                **delta_write_timings,
                "post_write_counts": round((counts_finished - counts_started) * 1000.0, 3),
                "write_stage_total": round((counts_finished - write_started) * 1000.0, 3),
            },
        }
        return nervous_index.with_index_write_success(
            data,
            finished_at=finished_at,
            counts=final_counts,
            parse_errors=parse_errors,
            parse_error_count=int(projection_summary.get("parse_errors", len(parse_errors))),
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
