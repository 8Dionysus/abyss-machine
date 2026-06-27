from __future__ import annotations

import array
import base64
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from . import resource_planning


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vectors (
  chunk_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  document_schema TEXT,
  title TEXT NOT NULL,
  body_sha256 TEXT NOT NULL,
  body_preview TEXT NOT NULL,
  generated_at TEXT,
  document_generated_at TEXT,
  privacy_mode TEXT NOT NULL,
  provenance_json TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,
  indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_source_id ON vectors(source_id);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_schema ON vectors(document_schema);
CREATE INDEX IF NOT EXISTS idx_semantic_vectors_generated_at ON vectors(generated_at);
CREATE TABLE IF NOT EXISTS build_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  ok INTEGER NOT NULL,
  source_chunks INTEGER NOT NULL,
  pending_chunks INTEGER NOT NULL,
  vectors_indexed INTEGER NOT NULL,
  partial INTEGER NOT NULL,
  errors_json TEXT NOT NULL
);
""".strip()


def connect_db(db_path: Path, create: bool = False) -> sqlite3.Connection:
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    if create:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def initialize_db(
    conn: sqlite3.Connection,
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
) -> None:
    conn.executescript(schema_sql())
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("schema", f"{schema_prefix}_nervous_semantic_index_v1"))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("backend", "sqlite_float32_sidecar"))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("tool_version", version))


def _build_run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    errors_raw = str(row["errors_json"] or "{}")
    try:
        errors_json = json.loads(errors_raw)
    except json.JSONDecodeError:
        errors_json = {"raw": errors_raw}
    return {
        "run_id": row["run_id"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "ok": bool(row["ok"]),
        "source_chunks": int(row["source_chunks"] or 0),
        "pending_chunks": int(row["pending_chunks"] or 0),
        "vectors_indexed": int(row["vectors_indexed"] or 0),
        "partial": bool(row["partial"]),
        "details": errors_json,
    }


def counts(db_path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else None,
    }
    if not db_path.exists():
        return data
    try:
        conn = connect_db(db_path, create=False)
        for table in ("vectors", "build_runs"):
            try:
                row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
                data[table] = int(row[0]) if row else None
            except sqlite3.Error as exc:
                data[f"{table}_error"] = str(exc)
        meta: dict[str, Any] = {}
        try:
            for row in conn.execute("SELECT key, value FROM meta"):
                meta[str(row["key"])] = row["value"]
        except sqlite3.Error as exc:
            data["meta_error"] = str(exc)
        data["meta"] = meta
        try:
            row = conn.execute(
                """
                SELECT run_id, started_at, finished_at, ok, source_chunks, pending_chunks, vectors_indexed, partial, errors_json
                FROM build_runs
                ORDER BY COALESCE(finished_at, started_at) DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                data["last_build_run"] = _build_run_from_row(row)
            row = conn.execute(
                """
                SELECT run_id, started_at, finished_at, ok, source_chunks, pending_chunks, vectors_indexed, partial, errors_json
                FROM build_runs
                WHERE ok = 1
                ORDER BY COALESCE(finished_at, started_at) DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                data["last_successful_build_run"] = _build_run_from_row(row)
        except sqlite3.Error as exc:
            data["last_build_run_error"] = str(exc)
        conn.close()
    except sqlite3.Error as exc:
        data["error"] = str(exc)
    return data


def source_chunks_query(max_chunks: int | None = None) -> tuple[str, list[Any]]:
    sql = """
        SELECT
          chunks.chunk_id AS chunk_id,
          chunks.doc_id AS doc_id,
          chunks.source_id AS source_id,
          chunks.title AS title,
          chunks.body AS body,
          chunks.generated_at AS generated_at,
          chunks.privacy_mode AS privacy_mode,
          chunks.provenance_json AS provenance_json,
          documents.generated_at AS document_generated_at,
          documents.schema AS document_schema,
          documents.capture_trigger AS capture_trigger,
          documents.source_path AS source_path,
          documents.source_line AS source_line
        FROM chunks
        JOIN documents ON documents.doc_id = chunks.doc_id
        ORDER BY COALESCE(chunks.generated_at, documents.generated_at, '') DESC, chunks.chunk_id
    """
    params: list[Any] = []
    if max_chunks is not None and max_chunks > 0:
        sql += " LIMIT ?"
        params.append(int(max_chunks))
    return sql, params


def source_rows_to_chunks(rows: list[Any], *, max_input_chars: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        title = str(item.get("title") or "")
        body = str(item.get("body") or "")
        raw = f"{title}\n{body}"
        item["body_sha256"] = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
        item["embedding_text"] = embedding_text(title, body, max_input_chars)
        item["body_preview"] = body_preview(body)
        chunks.append(item)
    return chunks


def age_minutes(value: Any, *, now: dt.datetime | None = None) -> float | None:
    parsed = parse_time(value)
    if not parsed:
        return None
    basis = now or dt.datetime.now(dt.timezone.utc).astimezone()
    return max(0.0, (basis - parsed.astimezone(basis.tzinfo)).total_seconds() / 60.0)


def build_status(
    *,
    semantic: dict[str, Any],
    counts: dict[str, Any],
    source_counts: dict[str, Any],
    model_dir: str,
    model_exists: bool,
    cache_dir: str,
    cache_exists: bool,
    source_index_db_exists: bool,
    semantic_index_db_exists: bool,
    paths: dict[str, str],
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    embedding = semantic.get("embedding") if isinstance(semantic.get("embedding"), dict) else {}
    source_meta = source_counts.get("meta") if isinstance(source_counts.get("meta"), dict) else {}
    semantic_meta = counts.get("meta") if isinstance(counts.get("meta"), dict) else {}
    last_build = counts.get("last_build_run") if isinstance(counts.get("last_build_run"), dict) else {}
    last_successful_build = counts.get("last_successful_build_run") if isinstance(counts.get("last_successful_build_run"), dict) else {}
    last_build_details = last_build.get("details") if isinstance(last_build.get("details"), dict) else {}
    last_successful_details = last_successful_build.get("details") if isinstance(last_successful_build.get("details"), dict) else {}
    last_build_provenance = last_build_details.get("provenance") if isinstance(last_build_details.get("provenance"), dict) else {}
    last_successful_provenance = last_successful_details.get("provenance") if isinstance(last_successful_details.get("provenance"), dict) else {}
    warnings: list[str] = []
    if not bool(semantic.get("enabled", True)):
        warnings.append("semantic index disabled by config")
    if not source_index_db_exists:
        warnings.append("source SQLite/FTS index database missing")
    if not semantic_index_db_exists:
        warnings.append("semantic sidecar database missing")
    if not model_exists:
        warnings.append("embedding model directory missing")
    source_run_id = source_meta.get("run_id")
    semantic_source_run_id = semantic_meta.get("source_index_run_id")
    source_chunks = _safe_int(source_counts.get("chunks"), 0)
    semantic_vectors = _safe_int(counts.get("vectors"), 0)
    configured_pooling = str(embedding.get("pooling") or "last_token")
    configured_padding_side = str(embedding.get("padding_side") or "left")
    indexed_pooling = str(semantic_meta.get("pooling") or "mean")
    indexed_padding_side = str(semantic_meta.get("padding_side") or "right")
    embedding_config_stale = bool(
        counts.get("db_exists")
        and semantic_vectors > 0
        and (indexed_pooling != configured_pooling or indexed_padding_side != configured_padding_side)
    )
    partial = str(semantic_meta.get("partial") or "").lower() in {"1", "true", "yes"}
    if embedding_config_stale:
        warnings.append("semantic index was built with a different embedding pooling or padding policy")
    maintain = semantic.get("maintain") if isinstance(semantic.get("maintain"), dict) else {}
    min_delta_chunks = max(1, _safe_int(maintain.get("min_delta_chunks"), 128))
    max_stale_minutes = _safe_float(maintain.get("max_stale_minutes") or 90, 90.0)
    source_index_changed = bool(source_run_id and semantic_source_run_id and source_run_id != semantic_source_run_id)
    delta_chunks = max(source_chunks - semantic_vectors, 0)
    semantic_age = age_minutes(semantic_meta.get("built_at"), now=now)
    stale_by_delta = bool(source_index_changed and delta_chunks >= min_delta_chunks)
    stale_by_age = bool(
        source_index_changed
        and semantic_age is not None
        and semantic_age >= max(0.0, max_stale_minutes)
    )
    bounded_source_drift = bool(source_index_changed and not stale_by_delta and not stale_by_age)
    effective_stale = bool(embedding_config_stale or partial or stale_by_delta or stale_by_age)
    notices: list[str] = []
    if stale_by_delta or stale_by_age:
        warnings.append("semantic index drift exceeds maintenance thresholds")
    elif bounded_source_drift:
        notices.append("semantic source-index drift is below maintenance thresholds")
    if source_chunks and semantic_vectors and semantic_vectors < source_chunks and not partial and delta_chunks >= min_delta_chunks:
        warnings.append("semantic vector count is lower than source chunk count beyond maintenance threshold")
    return {
        "schema": f"{schema_prefix}_nervous_semantic_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(semantic.get("enabled", True)) and model_exists and not counts.get("error"),
        "ready": semantic_index_db_exists and semantic_vectors > 0 and not counts.get("error"),
        "warnings": warnings,
        "notices": notices,
        "config": {
            "enabled": bool(semantic.get("enabled", True)),
            "backend": semantic.get("backend"),
            "automation": semantic.get("automation"),
            "maintain": semantic.get("maintain"),
        },
        "paths": paths,
        "embedding": {
            "model_dir": model_dir,
            "model_exists": model_exists,
            "device": embedding.get("device"),
            "cache_dir": cache_dir,
            "cache_exists": cache_exists,
            "dimension": embedding.get("dimension"),
            "max_tokens": embedding.get("max_tokens"),
            "max_input_chars": embedding.get("max_input_chars"),
            "batch_size": embedding.get("batch_size"),
            "pooling": configured_pooling,
            "padding_side": configured_padding_side,
        },
        "counts": counts,
        "source_index": {
            "db": paths.get("source_index_db"),
            "chunks": source_chunks,
            "run_id": source_run_id,
            "built_at": source_meta.get("built_at"),
        },
        "freshness": {
            "source_index_run_id": source_run_id,
            "semantic_source_index_run_id": semantic_source_run_id,
            "partial": partial,
            "vectors": semantic_vectors,
            "source_chunks": source_chunks,
            "delta_chunks": delta_chunks,
            "min_delta_chunks": min_delta_chunks,
            "max_stale_minutes": max_stale_minutes,
            "source_index_changed": source_index_changed,
            "bounded_source_drift": bounded_source_drift,
            "stale_by_delta": stale_by_delta,
            "stale_by_age": stale_by_age,
            "embedding_config_stale": embedding_config_stale,
            "indexed_pooling": indexed_pooling,
            "configured_pooling": configured_pooling,
            "indexed_padding_side": indexed_padding_side,
            "configured_padding_side": configured_padding_side,
            "stale": effective_stale,
        },
        "provenance": {
            "backend": semantic.get("backend"),
            "model_dir": model_dir,
            "cache_dir": cache_dir,
            "device": embedding.get("device"),
            "vector_count": semantic_vectors,
            "last_successful_build": last_successful_build or (last_build if last_build.get("ok") else None),
            "last_successful_build_provenance": last_successful_provenance or (last_build_provenance if last_build.get("ok") else {}),
            "last_build": last_build,
            "last_build_provenance": last_build_provenance,
            "last_probe_result": last_build_provenance.get("probe") if isinstance(last_build_provenance, dict) else None,
            "compile_cache": last_build_provenance.get("compile_cache") if isinstance(last_build_provenance, dict) else None,
        },
    }


def maintain_assess(
    status: dict[str, Any],
    min_delta_chunks: int,
    max_stale_minutes: float,
    force_refresh: bool = False,
    *,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    freshness = status.get("freshness") if isinstance(status.get("freshness"), dict) else {}
    counts = status.get("counts") if isinstance(status.get("counts"), dict) else {}
    meta = counts.get("meta") if isinstance(counts.get("meta"), dict) else {}
    source_index = status.get("source_index") if isinstance(status.get("source_index"), dict) else {}
    source_run_id = freshness.get("source_index_run_id") or source_index.get("run_id")
    semantic_source_run_id = freshness.get("semantic_source_index_run_id") or meta.get("source_index_run_id")
    source_chunks = _safe_int(freshness.get("source_chunks") or source_index.get("chunks"), 0)
    vectors = _safe_int(freshness.get("vectors") or counts.get("vectors"), 0)
    vector_gap = max(source_chunks - vectors, 0)
    partial = bool(freshness.get("partial"))
    embedding_config_stale = bool(freshness.get("embedding_config_stale"))
    semantic_built_at = meta.get("built_at")
    source_built_at = source_index.get("built_at") or meta.get("source_index_built_at")
    semantic_age = age_minutes(semantic_built_at, now=now)
    source_age = age_minutes(source_built_at, now=now)
    source_index_changed = bool(freshness.get("source_index_changed") or (source_run_id and semantic_source_run_id and source_run_id != semantic_source_run_id))
    stale_by_delta = bool(source_index_changed and vector_gap >= max(1, int(min_delta_chunks)))
    stale_by_age = bool(
        source_index_changed
        and semantic_age is not None
        and semantic_age >= max(0.0, float(max_stale_minutes))
    )
    stale = bool(freshness.get("stale") or embedding_config_stale or partial or stale_by_delta or stale_by_age)
    bounded_source_drift = bool(source_index_changed and not stale_by_delta and not stale_by_age)
    reasons: list[str] = []
    if force_refresh:
        reasons.append("force_refresh")
    if source_chunks <= 0:
        reasons.append("source_index_has_no_chunks")
    if not bool(status.get("ready")):
        reasons.append("semantic_not_ready")
    if partial:
        reasons.append("semantic_index_is_partial")
    if embedding_config_stale:
        reasons.append("embedding_config_changed")
    if source_index_changed and vector_gap >= max(1, int(min_delta_chunks)):
        reasons.append(f"stale_delta_chunks={vector_gap}")
    elif vector_gap >= max(1, int(min_delta_chunks)):
        reasons.append(f"vector_gap_chunks={vector_gap}")
    if source_index_changed and semantic_age is not None and semantic_age >= max(0.0, float(max_stale_minutes)):
        reasons.append(f"stale_age_minutes={round(semantic_age, 1)}")
    needed = source_chunks > 0 and any(reason != "source_index_has_no_chunks" for reason in reasons)
    return {
        "needed": bool(needed),
        "reasons": reasons,
        "stale": stale,
        "source_index_changed": source_index_changed,
        "bounded_source_drift": bounded_source_drift,
        "embedding_config_stale": embedding_config_stale,
        "partial": partial,
        "source_index_run_id": source_run_id,
        "semantic_source_index_run_id": semantic_source_run_id,
        "source_chunks": source_chunks,
        "vectors": vectors,
        "delta_chunks": vector_gap,
        "min_delta_chunks": int(min_delta_chunks),
        "max_stale_minutes": float(max_stale_minutes),
        "semantic_built_at": semantic_built_at,
        "semantic_age_minutes": round(semantic_age, 2) if semantic_age is not None else None,
        "source_index_built_at": source_built_at,
        "source_index_age_minutes": round(source_age, 2) if source_age is not None else None,
    }


def maintain_index_refresh_assess(index_status: dict[str, Any], enabled: bool) -> dict[str, Any]:
    freshness = index_status.get("freshness") if isinstance(index_status.get("freshness"), dict) else {}
    counts = index_status.get("counts") if isinstance(index_status.get("counts"), dict) else {}
    reasons: list[str] = []
    if not enabled:
        return {
            "needed": False,
            "enabled": False,
            "reasons": ["refresh_index_first_disabled"],
            "ready": bool(index_status.get("ready")),
            "stale": bool(freshness.get("stale")),
            "records_lag": freshness.get("records_lag"),
            "chunks": counts.get("chunks"),
            "run_id": _nested_get(index_status, ["counts", "meta", "run_id"]),
            "built_at": _nested_get(index_status, ["counts", "meta", "built_at"]),
        }
    if not bool(index_status.get("ok")):
        reasons.append("source_index_status_not_ok")
    if not bool(index_status.get("ready")):
        reasons.append("source_index_not_ready")
    if bool(freshness.get("stale")):
        reasons.append("source_index_stale")
    records_lag = _safe_int(freshness.get("records_lag"), 0)
    if bool(freshness.get("records_lag_stale")) and "source_index_stale" not in reasons:
        reasons.append("source_index_records_lag")
    return {
        "needed": bool(reasons),
        "enabled": True,
        "reasons": reasons,
        "ready": bool(index_status.get("ready")),
        "stale": bool(freshness.get("stale")),
        "records_lag": records_lag,
        "chunks": counts.get("chunks"),
        "run_id": _nested_get(index_status, ["counts", "meta", "run_id"]),
        "built_at": _nested_get(index_status, ["counts", "meta", "built_at"]),
    }


def batch_policy(
    semantic_status: dict[str, Any],
    maintain: dict[str, Any],
    explicit_batch_size: int | None,
    resource_class: str,
    unattended: bool,
    memory: dict[str, Any],
) -> dict[str, Any]:
    embedding = semantic_status.get("embedding") if isinstance(semantic_status.get("embedding"), dict) else {}
    configured_batch_size = _safe_int(embedding.get("batch_size") or 16, 16)
    loaded_batch_size = max(1, _safe_int(maintain.get("loaded_batch_size") or 8, 8))
    loaded_zram_resident_mib = _safe_float(maintain.get("loaded_batch_zram_resident_mib") or 8192, 8192.0)
    summary = _nested_get(memory, ["pressure", "summary"])
    summary = summary if isinstance(summary, dict) else {}
    game_guard = memory.get("game_guard") if isinstance(memory.get("game_guard"), dict) else {}
    recommended = _nested_get(memory, ["recommended_new_work", resource_planning.normalize_class(resource_class)])
    recommended = recommended if isinstance(recommended, dict) else {}
    reasons: list[str] = []
    if bool(game_guard.get("active")):
        reasons.append("game_guard_active")
    if unattended and not bool(recommended.get("unattended_allowed", True)):
        reasons.extend(str(item) for item in recommended.get("unattended_blocked_reasons", []) or ["unattended_resource_gate_not_allowed"])
    memory_class = str(memory.get("class") or summary.get("class") or "")
    if memory_class in {"hot", "critical"}:
        reasons.append(f"memory_class_{memory_class}")
    zram_resident_mib = _safe_float(summary.get("zram_resident_mib"), 0.0)
    if zram_resident_mib >= loaded_zram_resident_mib:
        reasons.append("zram_resident_high")
    psi_some = _safe_float(summary.get("psi_some_avg10"), 0.0)
    psi_full = _safe_float(summary.get("psi_full_avg10"), 0.0)
    if psi_some > 2.0 or psi_full > 0.5:
        reasons.append("memory_psi_active_stalls")
    unique_reasons = list(dict.fromkeys(reasons))
    explicit = explicit_batch_size is not None and explicit_batch_size > 0
    adjusted_batch_size = None
    if unique_reasons and not explicit and configured_batch_size > loaded_batch_size:
        adjusted_batch_size = loaded_batch_size
    return {
        "configured_batch_size": configured_batch_size,
        "explicit_batch_size": int(explicit_batch_size) if explicit else None,
        "loaded_batch_size": loaded_batch_size,
        "effective_batch_size": int(explicit_batch_size) if explicit else int(adjusted_batch_size or configured_batch_size),
        "pass_batch_override": adjusted_batch_size,
        "load_detected": bool(unique_reasons),
        "load_reasons": unique_reasons,
        "memory": {
            "class": memory_class,
            "summary": {
                "mem_available_mib": summary.get("mem_available_mib"),
                "swap_used_percent": summary.get("swap_used_percent"),
                "zram_resident_mib": summary.get("zram_resident_mib"),
                "zram_data_mib": summary.get("zram_data_mib"),
                "psi_some_avg10": summary.get("psi_some_avg10"),
                "psi_full_avg10": summary.get("psi_full_avg10"),
            },
            "recommended": recommended,
        },
        "game_guard": {
            "active": game_guard.get("active"),
            "platform_present": game_guard.get("platform_present"),
            "summary": game_guard.get("summary"),
        },
    }


def build_command(
    *,
    max_chunks: int | None = None,
    explicit_batch_size: int | None = None,
    batch_override: Any = None,
    rebuild: bool = False,
) -> list[str]:
    command = ["abyss-machine", "nervous", "semantic-build", "--json"]
    if max_chunks is not None and max_chunks > 0:
        command.extend(["--max-chunks", str(int(max_chunks))])
    if explicit_batch_size is not None and explicit_batch_size > 0:
        command.extend(["--batch-size", str(int(explicit_batch_size))])
    elif batch_override is not None:
        command.extend(["--batch-size", str(int(batch_override))])
    if rebuild:
        command.append("--rebuild")
    return command


def embedding_text(title: str, body: str, max_chars: int) -> str:
    text = f"{title}\n{body}".strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f" ... [truncated {len(text) - max_chars} chars]"
    return text


def body_preview(body: str, max_chars: int = 520) -> str:
    preview = re.sub(r"\s+", " ", str(body or "")).strip()
    if len(preview) > max_chars:
        preview = preview[:max_chars] + " ..."
    return preview


def embedding_window_size(semantic: dict[str, Any]) -> int:
    maintain = semantic.get("maintain") if isinstance(semantic.get("maintain"), dict) else {}
    embedding = semantic.get("embedding") if isinstance(semantic.get("embedding"), dict) else {}
    for value in (maintain.get("embedding_window_chunks"), embedding.get("subprocess_max_items")):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return max(1, min(parsed, 8192))
    return 1024


def embedding_runtime_options(embedding: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_size": max(1, _safe_int(embedding.get("batch_size") or 16, 16)),
        "max_tokens": max(32, _safe_int(embedding.get("max_tokens") or 512, 512)),
        "pooling": str(embedding.get("pooling") or "last_token"),
        "padding_side": str(embedding.get("padding_side") or "left"),
        "timeout_sec": _safe_float(embedding.get("timeout_sec") or 1800, 1800.0),
    }


def embedding_input_jsonl(text_items: list[dict[str, str]]) -> str:
    lines = []
    for item in text_items:
        lines.append(json.dumps({"id": item["id"], "text": item["text"]}, ensure_ascii=False, sort_keys=False))
    return "\n".join(lines) + ("\n" if lines else "")


def embedding_subprocess_script() -> str:
    return r'''
import base64
import json
import os
import sys
import time

saved_stdout = os.dup(1)
os.dup2(2, 1)

def emit(data):
    os.write(saved_stdout, json.dumps(data, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n")
    os.close(saved_stdout)

input_path, output_path, model_dir, device, cache_dir, batch_size_raw, max_tokens_raw, pooling, padding_side = sys.argv[1:10]
batch_size = max(1, int(batch_size_raw))
max_tokens = max(32, int(max_tokens_raw))
pooling = str(pooling or "last_token")
padding_side = str(padding_side or "left")

def mean_pool(hidden, mask):
    mask = mask.astype(np.float32)
    return (hidden * mask[..., None]).sum(axis=1) / np.maximum(mask.sum(axis=1, keepdims=True), 1.0)

def last_token_pool(hidden, mask):
    left_padding = bool(mask[:, -1].sum() == mask.shape[0])
    if left_padding:
        return hidden[:, -1]
    sequence_lengths = mask.sum(axis=1).astype(np.int64) - 1
    return hidden[np.arange(hidden.shape[0]), sequence_lengths]
try:
    import numpy as np
    from transformers import AutoTokenizer
    from optimum.intel.openvino import OVModelForFeatureExtraction

    items = []
    with open(input_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                items.append({"id": str(item.get("id") or ""), "text": str(item.get("text") or "")})

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    tokenizer.padding_side = padding_side
    tokenizer_sec = time.perf_counter() - started
    load_started = time.perf_counter()
    model = OVModelForFeatureExtraction.from_pretrained(
        model_dir,
        device=device,
        ov_config={"CACHE_DIR": cache_dir},
        local_files_only=True,
    )
    load_sec = time.perf_counter() - load_started
    infer_sec = 0.0
    dim = None
    vectors = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for start in range(0, len(items), batch_size):
            batch = items[start:start + batch_size]
            texts = [item["text"] for item in batch]
            inputs = tokenizer(texts, padding=True, truncation=True, max_length=max_tokens, return_tensors="pt")
            infer_started = time.perf_counter()
            outputs = model(**inputs)
            infer_sec += time.perf_counter() - infer_started
            hidden = outputs.last_hidden_state.detach().cpu().numpy()
            mask = inputs["attention_mask"].detach().cpu().numpy()
            pooled = last_token_pool(hidden, mask) if pooling == "last_token" else mean_pool(hidden, mask)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            normalized = (pooled / np.maximum(norms, 1e-9)).astype("float32", copy=False)
            dim = int(normalized.shape[1])
            for item, vector in zip(batch, normalized):
                payload = {
                    "id": item["id"],
                    "dim": dim,
                    "vector_b64": base64.b64encode(vector.tobytes()).decode("ascii"),
                }
                out.write(json.dumps(payload, ensure_ascii=False, sort_keys=False) + "\n")
                vectors += 1
    emit({
        "ok": True,
        "items": len(items),
        "vectors": vectors,
        "dim": dim,
        "device": device,
        "model_dir": model_dir,
        "cache_dir": cache_dir,
        "tokenizer_sec": round(tokenizer_sec, 3),
        "load_sec": round(load_sec, 3),
        "infer_sec": round(infer_sec, 3),
        "batch_size": batch_size,
        "max_tokens": max_tokens,
        "pooling": pooling,
        "padding_side": padding_side,
    })
except Exception as exc:
    emit({"ok": False, "error": repr(exc), "model_dir": model_dir, "device": device, "cache_dir": cache_dir, "pooling": pooling, "padding_side": padding_side})
    raise SystemExit(1)
'''


def embedding_subprocess_command(
    *,
    python: str,
    input_path: str,
    output_path: str,
    model_dir: str,
    device: str,
    cache_dir: str,
    options: dict[str, Any],
) -> list[str]:
    return [
        str(python),
        "-c",
        embedding_subprocess_script(),
        str(input_path),
        str(output_path),
        str(model_dir),
        str(device),
        str(cache_dir),
        str(options.get("batch_size")),
        str(options.get("max_tokens")),
        str(options.get("pooling")),
        str(options.get("padding_side")),
    ]


def parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    stdout = str(stdout or "").strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            return data if isinstance(data, dict) else None
        marker = stdout.rfind("\n{")
        if marker < 0:
            return None
        try:
            data = json.loads(stdout[marker + 1 :])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def parse_embedding_vectors_jsonl(output_jsonl: str) -> dict[str, dict[str, Any]]:
    vectors: dict[str, dict[str, Any]] = {}
    for line in str(output_jsonl or "").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        chunk_id = str(item.get("id") or "")
        blob = base64.b64decode(str(item.get("vector_b64") or ""))
        vectors[chunk_id] = {"dim": _safe_int(item.get("dim"), 0), "blob": blob}
    return vectors


def embedding_subprocess_result(
    *,
    stdout: str,
    stderr: str,
    returncode: int | None,
    output_jsonl: str,
    expected_items: int,
    resource_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = parse_json_stdout(stdout)
    if not isinstance(status, dict):
        status = {"ok": False, "error": "embedding subprocess returned invalid JSON", "stdout_tail": str(stdout or "")[-1000:]}
    vectors = parse_embedding_vectors_jsonl(output_jsonl)
    status.update({
        "returncode": returncode,
        "stderr_tail": str(stderr or "")[-2000:],
        "resource_profile": resource_profile,
        "vectors": vectors,
    })
    status["ok"] = bool(status.get("ok") and returncode == 0 and len(vectors) == int(expected_items))
    return status


def insert_vectors(
    conn: sqlite3.Connection,
    vectors: dict[str, dict[str, Any]],
    pending_by_id: dict[str, dict[str, Any]],
    started_at: str,
) -> int:
    indexed = 0
    conn.execute("BEGIN")
    try:
        for chunk_id, vector in vectors.items():
            item = pending_by_id.get(str(chunk_id))
            if not item:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO vectors (
                  chunk_id, doc_id, source_id, document_schema, title, body_sha256, body_preview,
                  generated_at, document_generated_at, privacy_mode, provenance_json, dim, vector, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(item.get("chunk_id")),
                    str(item.get("doc_id")),
                    str(item.get("source_id")),
                    item.get("document_schema"),
                    str(item.get("title") or ""),
                    str(item.get("body_sha256")),
                    str(item.get("body_preview") or ""),
                    item.get("generated_at"),
                    item.get("document_generated_at"),
                    str(item.get("privacy_mode") or "normal"),
                    str(item.get("provenance_json") or "{}"),
                    int(vector.get("dim") or 0),
                    sqlite3.Binary(vector.get("blob") or b""),
                    started_at,
                ),
            )
            indexed += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return indexed


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
    conn.execute(
        """
        INSERT OR REPLACE INTO build_runs (
          run_id, started_at, finished_at, ok, source_chunks, pending_chunks, vectors_indexed, partial, errors_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            started_at,
            finished_at,
            1 if ok else 0,
            int(source_chunks),
            int(pending_chunks),
            int(vectors_indexed),
            1 if partial else 0,
            json.dumps(errors, ensure_ascii=False, sort_keys=True),
        ),
    )


def existing_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    hashes: dict[str, str] = {}
    try:
        for row in conn.execute("SELECT chunk_id, body_sha256 FROM vectors"):
            hashes[str(row["chunk_id"])] = str(row["body_sha256"])
    except sqlite3.Error:
        pass
    return hashes


def existing_vectors_by_hash(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    vectors: dict[str, dict[str, Any]] = {}
    try:
        rows = conn.execute(
            """
            SELECT body_sha256, dim, vector, indexed_at
            FROM vectors
            ORDER BY indexed_at DESC
            """
        ).fetchall()
    except sqlite3.Error:
        return vectors
    for row in rows:
        body_sha256 = str(row["body_sha256"] or "")
        if not body_sha256 or body_sha256 in vectors:
            continue
        vectors[body_sha256] = {
            "dim": int(row["dim"] or 0),
            "blob": bytes(row["vector"] or b""),
            "reused_from_body_sha256": body_sha256,
        }
    return vectors


def put_meta(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    for key, value in values.items():
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))


def delete_stale_vectors(conn: sqlite3.Connection, current_chunk_ids: set[str], *, partial: bool) -> int:
    if partial:
        return 0
    deleted = 0
    for row in conn.execute("SELECT chunk_id FROM vectors").fetchall():
        chunk_id = str(row["chunk_id"])
        if chunk_id not in current_chunk_ids:
            conn.execute("DELETE FROM vectors WHERE chunk_id = ?", (chunk_id,))
            deleted += 1
    return deleted


def vector_from_blob(blob: bytes) -> array.array:
    vector = array.array("f")
    vector.frombytes(blob)
    return vector


def dot(left: array.array, right: array.array) -> float:
    count = min(len(left), len(right))
    if count <= 0:
        return 0.0
    return float(sum(float(left[index]) * float(right[index]) for index in range(count)))


def search_sort_key(item: dict[str, Any]) -> tuple[float, float]:
    parsed = parse_time(item.get("chunk_generated_at") or item.get("document_generated_at"))
    timestamp = parsed.timestamp() if parsed else 0.0
    return (-float(item.get("score") or 0.0), -timestamp)


def search_dedupe_key(item: dict[str, Any]) -> tuple[str, str]:
    title = str(item.get("title") or "")
    normalized_title = re.sub(r"\bnervous snapshot \d{4}-\d{2}-\d{2}T[^\s]+", "nervous snapshot", title)
    return (str(item.get("source_id") or ""), normalized_title)


def dedupe_results(rows: list[dict[str, Any]], limit: int, dedupe: bool) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=search_sort_key)
    if not dedupe:
        return sorted_rows[:limit]
    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []
    for item in sorted_rows:
        key = search_dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def query_text(query: str) -> str:
    return (
        "Instruct: Given a local machine memory search query, retrieve relevant evidence chunks that answer the query\n"
        f"Query: {query}"
    )


def search_with_vector(
    *,
    db_path: Path,
    query: str,
    query_vector_blob: bytes,
    query_vector_result: dict[str, Any],
    final_limit: int,
    dedupe: bool = True,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    query_vector = vector_from_blob(query_vector_blob)
    since_time = parse_time(since) if since else None
    until_time = parse_time(until) if until else None
    rows: list[dict[str, Any]] = []
    filtered_out = 0
    try:
        conn = connect_db(db_path, create=False)
        db_rows = conn.execute(
            """
            SELECT
              chunk_id, doc_id, source_id, document_schema, title, body_preview, generated_at,
              document_generated_at, privacy_mode, provenance_json, dim, vector, indexed_at
            FROM vectors
            """
        ).fetchall()
        meta = {str(row["key"]): row["value"] for row in conn.execute("SELECT key, value FROM meta")}
        conn.close()
        for row in db_rows:
            item = dict(row)
            try:
                provenance = json.loads(str(item.get("provenance_json") or "{}"))
                if not isinstance(provenance, dict):
                    provenance = {}
            except json.JSONDecodeError:
                provenance = {}
            item["severity"] = provenance.get("severity")
            item["sensitivity"] = provenance.get("sensitivity")
            timestamp = parse_time(item.get("generated_at") or item.get("document_generated_at"))
            keep = True
            if source and item.get("source_id") != source:
                keep = False
            if schema and item.get("document_schema") != schema:
                keep = False
            if since_time is not None and (timestamp is None or timestamp < since_time):
                keep = False
            if until_time is not None and (timestamp is None or timestamp > until_time):
                keep = False
            if severity and item.get("severity") != severity:
                keep = False
            if sensitivity and item.get("sensitivity") != sensitivity:
                keep = False
            if not keep:
                filtered_out += 1
                continue
            vector = vector_from_blob(bytes(item.pop("vector")))
            score = dot(query_vector, vector)
            item["score"] = score
            item["semantic_score"] = score
            item["snippet"] = item.get("body_preview")
            item["chunk_generated_at"] = item.get("generated_at")
            item["provenance"] = {
                key: provenance.get(key)
                for key in ("event_id", "episode_id", "event_type", "category", "severity", "sensitivity", "source_ids")
                if key in provenance
            }
            item.pop("provenance_json", None)
            rows.append(item)
        results = dedupe_results(rows, final_limit, dedupe=dedupe)
        return {
            "schema": f"{schema_prefix}_nervous_semantic_search_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": True,
            "query": query,
            "limit": final_limit,
            "dedupe": dedupe,
            "filters": {
                "source": source,
                "schema": schema,
                "since": since,
                "until": until,
                "severity": severity,
                "sensitivity": sensitivity,
            },
            "db_path": str(db_path),
            "results": results,
            "summary": {
                "results": len(results),
                "raw_results": len(rows),
                "filtered_out": filtered_out,
                "deduped": max(len(rows) - len(results), 0) if dedupe else 0,
                "semantic_run_id": meta.get("run_id"),
                "source_index_run_id": meta.get("source_index_run_id"),
                "built_at": meta.get("built_at"),
                "partial": str(meta.get("partial") or "").lower() in {"1", "true", "yes"},
            },
            "embedding_status": query_vector_result.get("embedding_status"),
            "policy_gate": query_vector_result.get("policy_gate"),
        }
    except (OSError, sqlite3.Error) as exc:
        return {
            "schema": f"{schema_prefix}_nervous_semantic_search_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "query": query,
            "db_path": str(db_path),
            "error": str(exc),
        }
