from __future__ import annotations

from contextlib import contextmanager
import fcntl
import grp
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Callable, Mapping

from . import nervous_index
from . import nervous_semantic
from . import typing_nervous_adapters


RunCommand = Callable[[list[str], float, Mapping[str, str] | None], Mapping[str, Any]]
ResourceSnapshot = Callable[[], Mapping[str, Any]]
ResourceProfile = Callable[[Mapping[str, Any], Mapping[str, Any], str, str], Mapping[str, Any]]
ConnectDb = Callable[[Path, bool], sqlite3.Connection]
CountDb = Callable[[Path], dict[str, Any]]
StatusPort = Callable[[], dict[str, Any]]
LockActivePort = Callable[[], bool]
ResourceLaunchPort = Callable[..., dict[str, Any]]
MemoryPlanPort = Callable[[], dict[str, Any]]
LatestWriterPort = Callable[[dict[str, Any]], dict[str, Any]]
JsonParserPort = Callable[[str], dict[str, Any] | None]
EmbedTextsPort = Callable[[list[dict[str, str]], Mapping[str, Any]], dict[str, Any]]
CacheStatsPort = Callable[[Path], dict[str, Any]]
NowPort = Callable[[], str]
InsertVectorsPort = Callable[[sqlite3.Connection, dict[str, dict[str, Any]], dict[str, dict[str, Any]], str], int]
RecordFailedBuildRunPort = Callable[..., None]

DEFAULT_STATE_GROUP = "wheel"


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
    return nervous_semantic.connect_db(db_path, create=create)


def initialize_db(
    conn: sqlite3.Connection,
    *,
    schema_prefix: str,
    version: str,
) -> None:
    nervous_semantic.initialize_db(conn, schema_prefix=schema_prefix, version=version)


@contextmanager
def semantic_lock(root: Path) -> Any:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "semantic.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def semantic_lock_active(root: Path) -> bool:
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "semantic.lock"
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


def write_maintain_latest(
    data: dict[str, Any],
    latest_path: Path,
    daily_root: Path,
) -> dict[str, Any]:
    errors = typing_nervous_adapters.write_latest_and_history(data, latest_path, daily_root, mode=0o664)
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
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


def counts(db_path: Path, *, count_db: CountDb = nervous_semantic.counts) -> dict[str, Any]:
    return count_db(db_path)


def source_chunks(
    source_db_path: Path,
    *,
    max_chunks: int | None,
    max_input_chars: int,
    connect_source: ConnectDb = nervous_index.connect_db,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not source_db_path.exists():
        return [], {"error": "source SQLite/FTS index database missing", "db": str(source_db_path)}
    sql, params = nervous_semantic.source_chunks_query(max_chunks=max_chunks)
    conn: sqlite3.Connection | None = None
    try:
        conn = connect_source(source_db_path, False)
        rows = conn.execute(sql, params).fetchall()
    except (OSError, sqlite3.Error) as exc:
        return [], {"error": str(exc), "db": str(source_db_path)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
    return nervous_semantic.source_rows_to_chunks(rows, max_input_chars=max_input_chars), None


def existing_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    return nervous_semantic.existing_hashes(conn)


def existing_vectors_by_hash(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return nervous_semantic.existing_vectors_by_hash(conn)


def insert_vectors(
    conn: sqlite3.Connection,
    vectors: dict[str, dict[str, Any]],
    pending_by_id: dict[str, dict[str, Any]],
    started_at: str,
) -> int:
    return nervous_semantic.insert_vectors(conn, vectors, pending_by_id, started_at)


def record_build_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    ok: bool,
    source_chunks: int,
    pending_chunks: int,
    vectors_indexed: int,
    partial: bool,
    errors: dict[str, Any],
) -> None:
    nervous_semantic.record_build_run(
        conn,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        ok=ok,
        source_chunks=source_chunks,
        pending_chunks=pending_chunks,
        vectors_indexed=vectors_indexed,
        partial=partial,
        errors=errors,
    )


def record_failed_build_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    source_chunks: int,
    pending_chunks: int,
    vectors_indexed: int,
    partial: bool,
    errors: dict[str, Any],
) -> None:
    conn.execute("BEGIN")
    try:
        record_build_run(
            conn,
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            ok=False,
            source_chunks=source_chunks,
            pending_chunks=pending_chunks,
            vectors_indexed=vectors_indexed,
            partial=partial,
            errors=errors,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def finish_successful_build_run(
    conn: sqlite3.Connection,
    *,
    current_chunk_ids: set[str],
    partial: bool,
    meta_values: dict[str, Any],
    run_id: str,
    started_at: str,
    finished_at: str,
    source_chunks: int,
    pending_chunks: int,
    vectors_indexed: int,
    errors: dict[str, Any],
) -> int:
    conn.execute("BEGIN")
    try:
        stale_deleted = nervous_semantic.delete_stale_vectors(conn, current_chunk_ids, partial=partial)
        nervous_semantic.put_meta(conn, meta_values)
        record_build_run(
            conn,
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            ok=True,
            source_chunks=source_chunks,
            pending_chunks=pending_chunks,
            vectors_indexed=vectors_indexed,
            partial=partial,
            errors=errors,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return stale_deleted


def semantic_build_pending_plan(
    chunks: list[dict[str, Any]],
    *,
    existing: Mapping[str, str],
    existing_vectors_by_hash: Mapping[str, dict[str, Any]],
    rebuild: bool,
) -> dict[str, Any]:
    pending = [
        item for item in chunks
        if rebuild or existing.get(str(item.get("chunk_id"))) != str(item.get("body_sha256"))
    ]
    pending_by_id = {str(item["chunk_id"]): item for item in pending}
    reuse_vectors: dict[str, dict[str, Any]] = {}
    embed_pending: list[dict[str, Any]] = []
    if rebuild:
        embed_pending = list(pending)
    else:
        for item in pending:
            chunk_id = str(item.get("chunk_id"))
            reusable = existing_vectors_by_hash.get(str(item.get("body_sha256") or ""))
            if reusable:
                reuse_vectors[chunk_id] = dict(reusable)
            else:
                embed_pending.append(item)
    return {
        "pending": pending,
        "pending_by_id": pending_by_id,
        "reuse_vectors": reuse_vectors,
        "embed_pending": embed_pending,
        "summary": {
            "source_chunks_selected": len(chunks),
            "existing_vectors": len(existing),
            "pending_chunks": len(pending),
            "embedding_pending_chunks": len(embed_pending),
            "vectors_reused_by_body_hash": len(reuse_vectors),
            "unchanged_chunks": max(len(chunks) - len(pending), 0),
            "vectors_indexed": 0,
            "stale_vectors_deleted": 0,
        },
    }


def semantic_build_embedding_attempts(embedding: Mapping[str, Any]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = [dict(embedding)]
    try:
        configured_batch = int(embedding.get("batch_size") or 16)
    except (TypeError, ValueError):
        configured_batch = 16
    fallback_batch = configured_batch
    while fallback_batch > 8:
        fallback_batch = max(8, fallback_batch // 2)
        if fallback_batch == configured_batch:
            break
        fallback_embedding = dict(embedding)
        fallback_embedding["batch_size"] = fallback_batch
        attempts.append(fallback_embedding)
        if fallback_batch <= 16:
            break
    return attempts


def semantic_build_insert_reused_vectors(
    conn: sqlite3.Connection,
    *,
    reuse_vectors: dict[str, dict[str, Any]],
    pending_by_id: dict[str, dict[str, Any]],
    started_at: str,
    insert_vectors_port: InsertVectorsPort = insert_vectors,
) -> int:
    if not reuse_vectors:
        return 0
    return insert_vectors_port(conn, reuse_vectors, pending_by_id, started_at)


def semantic_build_embedding_windows(
    conn: sqlite3.Connection,
    data: dict[str, Any],
    *,
    semantic_config: Mapping[str, Any],
    embedding: Mapping[str, Any],
    chunks: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    pending_by_id: dict[str, dict[str, Any]],
    embed_pending: list[dict[str, Any]],
    started_at: str,
    run_id: str,
    partial: bool,
    cache_before: Mapping[str, Any],
    cache_dir: Path,
    cache_stats: CacheStatsPort,
    now: NowPort,
    embed_texts: EmbedTextsPort,
    insert_vectors_port: InsertVectorsPort = insert_vectors,
    record_failed_build_run_port: RecordFailedBuildRunPort = record_failed_build_run,
) -> dict[str, Any]:
    indexed = int(_nested_get(data, ["summary", "vectors_indexed"]) or 0)
    window_size = nervous_semantic.embedding_window_size(dict(semantic_config))
    embedding_aggregate: dict[str, Any] = {
        "ok": True,
        "items": len(embed_pending),
        "vectors": 0,
        "windows": 0,
        "window_size": window_size,
        "mode": "windowed_progressive_commit",
        "reused_by_body_hash": int(_nested_get(data, ["summary", "vectors_reused_by_body_hash"]) or 0),
    }
    if not embed_pending:
        data["embedding_status"] = embedding_aggregate
        return {"ok": True, "data": data, "indexed": indexed}

    text_items = [
        {"id": str(item["chunk_id"]), "text": str(item["embedding_text"])}
        for item in embed_pending
    ]
    data["embedding_windows"] = []
    for offset in range(0, len(text_items), window_size):
        window = text_items[offset:offset + window_size]
        embedding_status: dict[str, Any] = {}
        attempt_summaries: list[dict[str, Any]] = []
        for attempt_index, attempt_embedding in enumerate(semantic_build_embedding_attempts(embedding)):
            embedding_status = embed_texts(window, attempt_embedding)
            attempt_summary = {key: value for key, value in embedding_status.items() if key != "vectors"}
            attempt_summary["attempt"] = attempt_index + 1
            attempt_summary["batch_size"] = int(attempt_embedding.get("batch_size") or embedding.get("batch_size") or 16)
            attempt_summaries.append(attempt_summary)
            if embedding_status.get("ok"):
                break
        vectors = embedding_status.get("vectors") if isinstance(embedding_status.get("vectors"), dict) else {}
        window_status = {key: value for key, value in embedding_status.items() if key != "vectors"}
        window_status.update({
            "offset": offset,
            "items": len(window),
            "vectors": len(vectors),
            "attempts": attempt_summaries,
        })
        data["embedding_windows"].append(window_status)
        embedding_aggregate["windows"] = int(embedding_aggregate.get("windows") or 0) + 1
        if not embedding_status.get("ok"):
            embedding_aggregate["ok"] = False
            data["embedding_status"] = embedding_aggregate
            data["error"] = embedding_status.get("error") or "embedding subprocess failed"
            data["summary"]["vectors_indexed"] = indexed
            cache_after = cache_stats(cache_dir)
            compile_cache = data.get("provenance", {}).get("compile_cache") if isinstance(data.get("provenance"), dict) else {}
            if isinstance(compile_cache, dict):
                compile_cache["after"] = cache_after
                compile_cache["mtime_changed"] = cache_before.get("mtime") != cache_after.get("mtime")
                compile_cache["used_or_regenerated"] = bool(cache_after.get("exists"))
            finished_at = now()
            record_failed_build_run_port(
                conn,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                source_chunks=len(chunks),
                pending_chunks=len(pending),
                vectors_indexed=indexed,
                partial=partial,
                errors={"embedding_status": window_status, "provenance": data.get("provenance")},
            )
            return {"ok": False, "data": data, "indexed": indexed}
        window_indexed = insert_vectors_port(conn, vectors, pending_by_id, started_at)
        indexed += window_indexed
        embedding_aggregate["vectors"] = int(embedding_aggregate.get("vectors") or 0) + window_indexed
        data["summary"]["vectors_indexed"] = indexed
    data["embedding_status"] = embedding_aggregate
    return {"ok": True, "data": data, "indexed": indexed}


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _index_status_summary(index_status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": index_status.get("ok"),
        "ready": index_status.get("ready"),
        "warnings": index_status.get("warnings", []),
        "freshness": index_status.get("freshness"),
        "counts": {
            "chunks": _nested_get(index_status, ["counts", "chunks"]),
            "documents": _nested_get(index_status, ["counts", "documents"]),
            "run_id": _nested_get(index_status, ["counts", "meta", "run_id"]),
            "built_at": _nested_get(index_status, ["counts", "meta", "built_at"]),
        },
    }


def semantic_maintain_document(
    *,
    semantic_config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    maintain_latest_path: Path,
    maintain_daily_root: Path,
    semantic_latest_path: Path,
    index_status: StatusPort,
    semantic_status: StatusPort,
    lock_active: LockActivePort,
    resource_launch: ResourceLaunchPort,
    memory_plan: MemoryPlanPort,
    latest_writer: LatestWriterPort,
    json_parser: JsonParserPort,
    min_delta_chunks: int | None = None,
    max_stale_minutes: float | None = None,
    timeout_sec: float | None = None,
    dry_run: bool = False,
    force_refresh: bool = False,
    max_chunks: int | None = None,
    batch_size: int | None = None,
    rebuild: bool = False,
    no_thermal_sample: bool = False,
    refresh_index_first: bool | None = None,
    write_latest: bool = True,
    index_build_command: list[str] | None = None,
) -> dict[str, Any]:
    maintain = semantic_config.get("maintain") if isinstance(semantic_config.get("maintain"), dict) else {}
    min_delta = int(min_delta_chunks if min_delta_chunks is not None else maintain.get("min_delta_chunks") or 128)
    max_stale = float(max_stale_minutes if max_stale_minutes is not None else maintain.get("max_stale_minutes") or 90)
    timeout = float(timeout_sec if timeout_sec is not None and timeout_sec > 0 else maintain.get("timeout_sec") or 1800)
    resource_class = str(maintain.get("resource_class") or "medium")
    resource_kind = str(maintain.get("resource_kind") or "indexing")
    unattended = bool(maintain.get("unattended", True))
    success_on_block = bool(maintain.get("success_on_block", True))
    index_refresh_enabled = bool(maintain.get("refresh_index_first", True) if refresh_index_first is None else refresh_index_first)
    index_refresh_timeout = float(maintain.get("index_refresh_timeout_sec") or min(timeout, 300))
    index_command = list(index_build_command or ["abyss-machine", "nervous", "index-build", "--json"])

    initial_index = index_status()
    index_refresh_assessment = nervous_semantic.maintain_index_refresh_assess(initial_index, index_refresh_enabled)
    before = semantic_status()
    pre_refresh_assessment = nervous_semantic.maintain_assess(
        before,
        min_delta,
        max_stale,
        force_refresh=force_refresh,
    )
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_nervous_semantic_maintain_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "decision": "skip",
        "dry_run": bool(dry_run),
        "before": before,
        "assessment": pre_refresh_assessment,
        "pre_refresh_assessment": pre_refresh_assessment,
        "thresholds": {
            "min_delta_chunks": min_delta,
            "max_stale_minutes": max_stale,
        },
        "index_refresh": {
            "enabled": index_refresh_enabled,
            "timeout_sec": index_refresh_timeout,
            "before": _index_status_summary(initial_index),
            "assessment": index_refresh_assessment,
            "command": index_command,
        },
        "resource": {
            "class": resource_class,
            "kind": resource_kind,
            "unattended": unattended,
            "timeout_sec": timeout,
            "success_on_block": success_on_block,
            "no_thermal_sample": bool(no_thermal_sample),
        },
        "build_command": [],
        "paths": {
            "latest": str(maintain_latest_path),
            "daily_glob": str(maintain_daily_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "semantic_latest": str(semantic_latest_path),
        },
        "policy": {
            "resource_gated": True,
            "resident_service": False,
            "repo_mutation": False,
            "automatic_repo_write": False,
        },
    }

    def finish(document: dict[str, Any]) -> dict[str, Any]:
        return latest_writer(document) if write_latest else document

    if index_refresh_assessment.get("needed"):
        if dry_run:
            index_launch = resource_launch(
                index_command,
                workload_class=resource_class,
                kind=resource_kind,
                unattended=unattended,
                dry_run=True,
                timeout_sec=index_refresh_timeout,
                sample_thermal=False if no_thermal_sample else None,
                write_latest=False,
            )
            data["index_refresh"]["launch"] = index_launch
            data["decision"] = "dry_run_refresh_index"
            if index_launch.get("blocked_reasons"):
                data["decision"] = "dry_run_blocked_index_refresh"
                data["reason"] = "source SQLite/FTS index pre-refresh would be blocked by resource gates"
            elif index_launch.get("denied_reasons"):
                data["decision"] = "dry_run_denied_index_refresh"
                data["reason"] = "source SQLite/FTS index pre-refresh would be denied by resource gates"
            else:
                data["reason"] = "source SQLite/FTS index would refresh before semantic maintenance assessment"
            return finish(data)
        if lock_active():
            data["decision"] = "skip_running"
            data["reason"] = "another semantic index operation is already running"
            return finish(data)
        index_launch = resource_launch(
            index_command,
            workload_class=resource_class,
            kind=resource_kind,
            unattended=unattended,
            dry_run=False,
            timeout_sec=index_refresh_timeout,
            sample_thermal=False if no_thermal_sample else None,
            write_latest=True,
        )
        data["index_refresh"]["launch"] = index_launch
        if index_launch.get("denied_reasons"):
            data["ok"] = False
            data["decision"] = "denied_index_refresh"
            data["reason"] = "resource gate denied source index refresh before semantic maintenance"
            return finish(data)
        if index_launch.get("blocked_reasons"):
            data["ok"] = success_on_block
            data["decision"] = "blocked_index_refresh"
            data["reason"] = "resource gate blocked source index refresh before semantic maintenance"
            return finish(data)
        if not index_launch.get("ok"):
            data["ok"] = False
            data["decision"] = "failed_index_refresh"
            data["reason"] = "source index refresh failed before semantic maintenance"
            return finish(data)
        refreshed_index = index_status()
        data["index_refresh"]["after"] = _index_status_summary(refreshed_index)
        before = semantic_status()
        data["before"] = before

    assessment = nervous_semantic.maintain_assess(before, min_delta, max_stale, force_refresh=force_refresh)
    effective_rebuild = bool(rebuild or assessment.get("embedding_config_stale"))
    batch_policy = nervous_semantic.batch_policy(
        before,
        dict(maintain),
        batch_size,
        resource_class,
        unattended,
        memory_plan(),
    )
    batch_override = batch_policy.get("pass_batch_override")
    build_command = nervous_semantic.build_command(
        max_chunks=max_chunks,
        explicit_batch_size=batch_size,
        batch_override=batch_override,
        rebuild=effective_rebuild,
    )
    data["assessment"] = assessment
    data["batch_policy"] = batch_policy
    data["resource"]["effective_rebuild"] = effective_rebuild
    data["build_command"] = build_command
    if not assessment.get("needed"):
        data["reason"] = "semantic sidecar is fresh enough under maintenance thresholds"
        return finish(data)
    if lock_active():
        data["decision"] = "skip_running"
        data["reason"] = "another semantic index operation is already running"
        return finish(data)

    data["decision"] = "dry_run" if dry_run else "launch"
    launch = resource_launch(
        build_command,
        workload_class=resource_class,
        kind=resource_kind,
        unattended=unattended,
        dry_run=bool(dry_run),
        timeout_sec=timeout,
        sample_thermal=False if no_thermal_sample else None,
        write_latest=not bool(dry_run),
    )
    data["launch"] = launch
    if launch.get("denied_reasons"):
        data["ok"] = False
        data["decision"] = "denied"
        data["reason"] = "resource gate denied semantic maintenance launch"
        return finish(data)
    if launch.get("blocked_reasons"):
        data["ok"] = success_on_block
        data["decision"] = "blocked"
        data["reason"] = "resource gate blocked semantic maintenance launch"
        return finish(data)
    if dry_run:
        data["reason"] = "semantic maintenance would launch"
        return finish(data)

    after = semantic_status()
    data["after"] = after
    after_assessment = nervous_semantic.maintain_assess(after, min_delta, max_stale, force_refresh=False)
    data["after_assessment"] = after_assessment
    launch_payload = json_parser(str(_nested_get(launch, ["execution", "stdout_tail"]) or launch.get("stdout_tail") or ""))
    if not launch.get("ok") and isinstance(launch_payload, dict) and bool(launch_payload.get("deferred")):
        data["ok"] = success_on_block
        data["decision"] = "deferred_source_index_active"
        data["reason"] = "semantic maintenance deferred because source lexical index operation is active"
        data["deferred_build"] = {
            "run_id": launch_payload.get("run_id"),
            "error": launch_payload.get("error"),
            "source_index": launch_payload.get("source_index"),
        }
    else:
        data["ok"] = bool(launch.get("ok")) and not bool(after_assessment.get("needed"))
    if data.get("decision") == "deferred_source_index_active":
        pass
    elif not launch.get("ok"):
        data["reason"] = "semantic maintenance launch failed"
    elif after_assessment.get("needed"):
        data["reason"] = "semantic maintenance completed but sidecar still exceeds maintenance thresholds"
    else:
        data["reason"] = "semantic sidecar is within maintenance thresholds"
    return finish(data)


def embed_texts_with_subprocess(
    text_items: list[dict[str, str]],
    *,
    embedding: Mapping[str, Any],
    model_dir: Path,
    device: str,
    cache_dir: Path,
    python: str,
    tmp_root: Path,
    run_command: RunCommand,
    env: Mapping[str, str] | None,
    resource_snapshot: ResourceSnapshot,
    resource_profile: ResourceProfile,
) -> dict[str, Any]:
    if not text_items:
        return {"ok": True, "vectors": {}, "summary": {"items": 0}}

    if not model_dir.exists():
        return {"ok": False, "error": f"embedding model directory missing: {model_dir}"}
    if not python or not Path(str(python)).exists():
        return {"ok": False, "error": "abyss-openvino-python not found"}

    options = nervous_semantic.embedding_runtime_options(dict(embedding))
    tmp_root.mkdir(parents=True, exist_ok=True)
    input_path: Path | None = None
    output_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(tmp_root),
            prefix="embed-input-",
            suffix=".jsonl",
            delete=False,
        ) as handle:
            input_path = Path(handle.name)
            handle.write(nervous_semantic.embedding_input_jsonl(text_items))
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(tmp_root),
            prefix="embed-output-",
            suffix=".jsonl",
            delete=False,
        ) as handle:
            output_path = Path(handle.name)

        resources_before = dict(resource_snapshot())
        command = nervous_semantic.embedding_subprocess_command(
            python=str(python),
            input_path=str(input_path),
            output_path=str(output_path),
            model_dir=str(model_dir),
            device=str(device),
            cache_dir=str(cache_dir),
            options=options,
        )
        completed = run_command(
            command,
            float(options.get("timeout_sec") or 1800),
            dict(env) if env is not None else None,
        )
        resources_after = dict(resource_snapshot())
        output_jsonl = output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""
        return nervous_semantic.embedding_subprocess_result(
            stdout=str(completed.get("stdout") or ""),
            stderr=str(completed.get("stderr") or ""),
            returncode=completed.get("returncode"),
            output_jsonl=output_jsonl,
            expected_items=len(text_items),
            resource_profile=dict(resource_profile(resources_before, resources_after, "child_process", "semantic embedding batch")),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        for path in (input_path, output_path):
            if isinstance(path, Path):
                try:
                    path.unlink()
                except OSError:
                    pass
