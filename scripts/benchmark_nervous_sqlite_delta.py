#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import benchmark_nervous_index_dag as index_benchmark


METHODS: dict[str, dict[str, int | None]] = {
    "wal_default": {"wal_autocheckpoint": 1000, "fts_automerge": None},
    "wal_checkpoint_deferred": {"wal_autocheckpoint": 0, "fts_automerge": None},
    "fts_automerge_16": {"wal_autocheckpoint": 1000, "fts_automerge": 16},
    "fts_automerge_off": {"wal_autocheckpoint": 1000, "fts_automerge": 0},
    "checkpoint_deferred_fts_automerge_16": {
        "wal_autocheckpoint": 0,
        "fts_automerge": 16,
    },
}

DOCUMENT_COLUMNS = (
    "doc_id, source_path, source_line, source_sha256, record_sha256, schema, generated_at, "
    "capture_trigger, global_pause, private_mode, heartbeat, source_ids_json, title, body, indexed_at"
)
CHUNK_COLUMNS = (
    "chunk_id, doc_id, chunk_index, source_id, title, body, generated_at, privacy_mode, provenance_json"
)
MANIFEST_COLUMNS = (
    "source_path, source_sha256, source_size_bytes, source_line_count, source_observation_json, "
    "projection_identity, summary_json, parse_errors_json, skipped_records_json, updated_at"
)


def _stable_digest(rows: list[tuple[Any, ...]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _target_digest(conn: sqlite3.Connection, source_path: str) -> str:
    documents = [
        tuple(row)
        for row in conn.execute(
            f"SELECT {DOCUMENT_COLUMNS} FROM documents WHERE source_path = ? ORDER BY doc_id",
            (source_path,),
        )
    ]
    chunks = [
        tuple(row)
        for row in conn.execute(
            f"""
            SELECT c.rowid, {', '.join(f'c.{column.strip()}' for column in CHUNK_COLUMNS.split(','))}
            FROM chunks AS c
            JOIN documents AS d ON d.doc_id = c.doc_id
            WHERE d.source_path = ?
            ORDER BY c.rowid
            """,
            (source_path,),
        )
    ]
    fts = [
        tuple(row)
        for row in conn.execute(
            """
            SELECT f.rowid, f.chunk_id, f.doc_id, f.source_id, f.title, f.body
            FROM fts_chunks AS f
            JOIN chunks AS c ON c.rowid = f.rowid
            JOIN documents AS d ON d.doc_id = c.doc_id
            WHERE d.source_path = ?
            ORDER BY f.rowid
            """,
            (source_path,),
        )
    ]
    return _stable_digest([("documents", documents), ("chunks", chunks), ("fts", fts)])


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    manifest_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'source_manifest'"
    ).fetchone() is not None
    return {
        "documents": int(conn.execute("SELECT count(*) FROM documents").fetchone()[0]),
        "chunks": int(conn.execute("SELECT count(*) FROM chunks").fetchone()[0]),
        "fts_chunks": int(conn.execute("SELECT count(*) FROM fts_chunks_docsize").fetchone()[0]),
        "manifest": (
            int(conn.execute("SELECT count(*) FROM source_manifest").fetchone()[0])
            if manifest_exists
            else 0
        ),
    }


def _copy_database(source: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cp", "--reflink=auto", "--sparse=auto", str(source), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"database copy failed: {completed.stderr.strip()}")


def _source_snapshot(db_path: Path, lock_path: Path, target: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("source index owner lock is active") from exc
        wal_path = Path(f"{db_path}-wal")
        if wal_path.exists() and wal_path.stat().st_size:
            raise RuntimeError("source index has a live WAL; snapshot refused")
        _copy_database(db_path, target)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _prepare_method(db_path: Path, automerge: int | None) -> None:
    if automerge is None:
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            "INSERT INTO fts_chunks(fts_chunks, rank) VALUES('automerge', ?)",
            (int(automerge),),
        )
        conn.commit()
    finally:
        conn.close()


def _run_method(db_path: Path, source_path: str, config: dict[str, int | None]) -> dict[str, Any]:
    _prepare_method(db_path, config["fts_automerge"])
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA wal_autocheckpoint={int(config['wal_autocheckpoint'] or 0)}")
    conn.execute("PRAGMA temp_store=MEMORY")

    before_counts = _counts(conn)
    before_digest = _target_digest(conn, source_path)
    manifest_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'source_manifest'"
    ).fetchone() is not None
    conn.execute(
        f"CREATE TEMP TABLE saved_documents AS SELECT {DOCUMENT_COLUMNS} FROM documents WHERE source_path = ?",
        (source_path,),
    )
    conn.execute(
        f"""
        CREATE TEMP TABLE saved_chunks AS
        SELECT c.rowid AS saved_rowid, {', '.join(f'c.{column.strip()}' for column in CHUNK_COLUMNS.split(','))}
        FROM chunks AS c
        JOIN documents AS d ON d.doc_id = c.doc_id
        WHERE d.source_path = ?
        """,
        (source_path,),
    )
    if manifest_exists:
        conn.execute(f"CREATE TEMP TABLE saved_manifest AS SELECT {MANIFEST_COLUMNS} FROM source_manifest")
    target_documents = int(conn.execute("SELECT count(*) FROM saved_documents").fetchone()[0])
    target_chunks = int(conn.execute("SELECT count(*) FROM saved_chunks").fetchone()[0])

    timings: dict[str, float] = {}
    total_started = time.perf_counter()
    conn.execute("BEGIN")

    stage = time.perf_counter()
    conn.execute("DELETE FROM fts_chunks WHERE rowid IN (SELECT saved_rowid FROM saved_chunks)")
    timings["delete_fts_ms"] = (time.perf_counter() - stage) * 1000.0

    stage = time.perf_counter()
    conn.execute("DELETE FROM documents WHERE source_path = ?", (source_path,))
    conn.execute(f"INSERT INTO documents ({DOCUMENT_COLUMNS}) SELECT {DOCUMENT_COLUMNS} FROM saved_documents")
    conn.execute(
        f"""
        INSERT INTO chunks (rowid, {CHUNK_COLUMNS})
        SELECT saved_rowid, {CHUNK_COLUMNS} FROM saved_chunks ORDER BY saved_rowid
        """
    )
    timings["relational_replace_ms"] = (time.perf_counter() - stage) * 1000.0

    stage = time.perf_counter()
    conn.execute(
        """
        INSERT INTO fts_chunks(rowid, chunk_id, doc_id, source_id, title, body)
        SELECT saved_rowid, chunk_id, doc_id, source_id, title, body
        FROM saved_chunks ORDER BY saved_rowid
        """
    )
    timings["insert_fts_ms"] = (time.perf_counter() - stage) * 1000.0

    stage = time.perf_counter()
    if manifest_exists:
        conn.execute("DELETE FROM source_manifest")
        conn.execute(f"INSERT INTO source_manifest ({MANIFEST_COLUMNS}) SELECT {MANIFEST_COLUMNS} FROM saved_manifest")
    timings["manifest_replace_ms"] = (time.perf_counter() - stage) * 1000.0

    stage = time.perf_counter()
    conn.commit()
    timings["commit_ms"] = (time.perf_counter() - stage) * 1000.0
    wal_path = Path(f"{db_path}-wal")
    wal_size_after_commit = wal_path.stat().st_size if wal_path.exists() else 0

    stage = time.perf_counter()
    conn.close()
    timings["close_ms"] = (time.perf_counter() - stage) * 1000.0
    timings["total_ms"] = (time.perf_counter() - total_started) * 1000.0
    wal_size_after_close = wal_path.stat().st_size if wal_path.exists() else 0

    verify = sqlite3.connect(db_path)
    try:
        after_counts = _counts(verify)
        after_digest = _target_digest(verify, source_path)
        quick_check = str(verify.execute("PRAGMA quick_check").fetchone()[0])
    finally:
        verify.close()
    parity = before_counts == after_counts and before_digest == after_digest and quick_check == "ok"
    return {
        "parity": parity,
        "target_documents": target_documents,
        "target_chunks": target_chunks,
        "wal_size_after_commit": wal_size_after_commit,
        "wal_size_after_close": wal_size_after_close,
        "timings_ms": {key: round(value, 3) for key, value in timings.items()},
    }


def run_benchmark(db_path: Path, lock_path: Path, work_root: Path, repetitions: int) -> dict[str, Any]:
    source_identity = index_benchmark._git_source()
    work_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="nervous-sqlite-delta-", dir=work_root))
    baseline = run_root / "baseline.db"
    try:
        _source_snapshot(db_path, lock_path, baseline)
        with baseline.open("rb") as stream:
            source_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        inspect = sqlite3.connect(baseline)
        try:
            row = inspect.execute(
                """
                SELECT source_path, count(*) AS documents
                FROM documents
                WHERE schema LIKE '%_nervous_episode_v1'
                GROUP BY source_path
                ORDER BY max(generated_at) DESC, source_path DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                raise RuntimeError("source database has no episode partition")
            source_path = str(row[0])
            source_counts = _counts(inspect)
            sqlite_version = sqlite3.sqlite_version
        finally:
            inspect.close()

        samples: dict[str, list[dict[str, Any]]] = {method: [] for method in METHODS}
        method_names = list(METHODS)
        for method in method_names:
            candidate = run_root / f"{method}.db"
            _copy_database(baseline, candidate)
            try:
                for repetition in range(1, repetitions + 1):
                    result = _run_method(candidate, source_path, METHODS[method])
                    samples[method].append({"repetition": repetition, **result})
            finally:
                candidate.unlink()

        methods: dict[str, Any] = {}
        for method, rows in samples.items():
            methods[method] = {
                "median_total_ms": round(statistics.median(row["timings_ms"]["total_ms"] for row in rows), 3),
                "median_commit_ms": round(statistics.median(row["timings_ms"]["commit_ms"] for row in rows), 3),
                "median_close_ms": round(statistics.median(row["timings_ms"]["close_ms"] for row in rows), 3),
                "samples": rows,
            }
        parity = all(row["parity"] for rows in samples.values() for row in rows)
        selected = min(methods, key=lambda name: methods[name]["median_total_ms"]) if parity else None
        return {
            "schema": "abyss_machine_nervous_sqlite_delta_benchmark_v1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ok": parity,
            "authority": "isolated database-strategy comparison; never authorizes the owner gate",
            "source_code": source_identity,
            "source": {
                "db_sha256": source_sha256,
                "db_size_bytes": baseline.stat().st_size,
                "sqlite_version": sqlite_version,
                "counts": source_counts,
            },
            "fixture": {
                "repetitions": repetitions,
                "target_kind": "latest_episode_partition",
            },
            "comparison": {
                "logical_parity": parity,
                "claims_weakened": False,
                "selected_candidate": selected,
            },
            "methods": methods,
            "workdir": None,
        }
    finally:
        shutil.rmtree(run_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare SQLite/FTS delta maintenance strategies on an isolated real index copy")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--debug-errors", action="store_true")
    args = parser.parse_args()
    try:
        result = run_benchmark(args.db, args.lock, args.work_root, max(args.repetitions, 1))
    except Exception as exc:
        if args.debug_errors:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        result = {
            "schema": "abyss_machine_nervous_sqlite_delta_benchmark_v1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ok": False,
            "error_type": type(exc).__name__,
            "workdir": None,
        }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
