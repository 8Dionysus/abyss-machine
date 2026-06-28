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
