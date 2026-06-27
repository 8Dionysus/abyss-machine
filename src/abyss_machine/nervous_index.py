from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable


JSONL_SOURCE_GLOB = "*/*/*.jsonl"


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


def parse_duration_seconds(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hour|hours)?", raw)
    if not match:
        return default
    amount = float(match.group(1))
    unit = match.group(2) or "seconds"
    if unit in {"s", "sec", "secs", "second", "seconds"}:
        return amount
    if unit in {"m", "min", "mins", "minute", "minutes"}:
        return amount * 60.0
    if unit in {"h", "hr", "hour", "hours"}:
        return amount * 3600.0
    return default


def jsonl_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.glob(JSONL_SOURCE_GLOB) if path.is_file())


def index_source_files(roots: list[Path] | tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        files.extend(jsonl_files(root))
    return sorted(files)


def parse_jsonl_records(path: Path | str, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    path_text = str(path)
    for line_no, line in enumerate(text.splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append({"path": path_text, "line": line_no, "error": str(exc)})
            continue
        if isinstance(data, dict):
            records.append(data)
        else:
            errors.append({"path": path_text, "line": line_no, "error": "record is not an object"})
    return records, errors


def parse_jsonl_records_with_metadata(
    path: Path | str,
    text: str,
    *,
    source_sha256: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    path_text = str(path)
    for line_no, line in enumerate(text.splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append({"path": path_text, "line": line_no, "error": str(exc)})
            continue
        if not isinstance(data, dict):
            errors.append({"path": path_text, "line": line_no, "error": "record is not an object"})
            continue
        records.append({
            "path": path_text,
            "line": line_no,
            "record": data,
            "record_sha256": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
            "source_sha256": source_sha256,
        })
    return records, errors


def load_jsonl_records(path: Path | str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_path = Path(path)
    try:
        text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], [{"path": str(source_path), "error": str(exc)}]
    return parse_jsonl_records(source_path, text)


def load_jsonl_records_with_metadata(
    path: Path | str,
    *,
    max_hash_bytes: int = 8 * 1024 * 1024,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_path = Path(path)
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        return [], [{"path": str(source_path), "error": str(exc)}]
    source_sha256 = hashlib.sha256(raw).hexdigest() if len(raw) <= max_hash_bytes else None
    text = raw.decode("utf-8", errors="replace")
    return parse_jsonl_records_with_metadata(source_path, text, source_sha256=source_sha256)


def load_source_records(
    paths: list[Path] | tuple[Path, ...],
    *,
    max_hash_bytes: int = 8 * 1024 * 1024,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_records: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    for path in paths:
        records, errors = load_jsonl_records_with_metadata(path, max_hash_bytes=max_hash_bytes)
        source_records.extend(records)
        parse_errors.extend(errors)
    return sort_source_records(source_records), parse_errors


def load_source_records_from_root(
    root: Path,
    *,
    max_hash_bytes: int = 8 * 1024 * 1024,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return load_source_records(jsonl_files(root), max_hash_bytes=max_hash_bytes)


def source_record_sort_key(item: dict[str, Any]) -> tuple[Any, str, int]:
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    parsed = parse_time(record.get("generated_at") or record.get("observed_at") or record.get("start_at"))
    return (
        parsed or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        str(item.get("path")),
        _safe_int(item.get("line"), 0),
    )


def sort_source_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=source_record_sort_key)


def enabled_safe_source_ids(sources: dict[str, Any]) -> set[str]:
    group = sources.get("safe_now")
    if not isinstance(group, dict):
        return set()
    enabled: set[str] = set()
    for source_id, item in group.items():
        if isinstance(item, dict) and bool(item.get("enabled")) and bool(item.get("allowed", True)):
            enabled.add(str(source_id))
    return enabled


def enabled_index_source_ids(sources: dict[str, Any]) -> set[str]:
    enabled = enabled_safe_source_ids(sources)
    deferred = sources.get("deferred_until_privacy_controls")
    if isinstance(deferred, dict):
        for source_id, item in deferred.items():
            if isinstance(item, dict) and bool(item.get("enabled")) and bool(item.get("allowed", True)):
                enabled.add(str(source_id))
    enabled.update({"nervous_events", "nervous_episodes"})
    return enabled


def deferred_source_ids(sources: dict[str, Any] | None = None) -> set[str]:
    group = sources.get("deferred_until_privacy_controls") if isinstance(sources, dict) else {}
    if not isinstance(group, dict):
        return {"browser_active_tab", "terminal_stdout_stderr", "clipboard", "screenshots", "audio_transcript_autolog"}
    return {str(item) for item in group.keys()}


def allowed_source_ids(sources: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for group_name in ("safe_now", "deferred_until_privacy_controls"):
        group = sources.get(group_name)
        if not isinstance(group, dict):
            continue
        for source_id, item in group.items():
            if isinstance(item, dict) and bool(item.get("enabled")) and bool(item.get("allowed", True)):
                allowed.add(str(source_id))
    allowed.update({"heartbeat", "nervous_events", "nervous_episodes"})
    return allowed


def fact_source_id(fact: dict[str, Any]) -> str:
    if fact.get("source_id"):
        return str(fact.get("source_id"))
    if fact.get("name") == "systemd_unit":
        return "systemd_metadata"
    if fact.get("name") in {
        "storage_latest",
        "storage_inventory_latest",
        "memory_pressure_latest",
        "process_latest",
        "observability_thermal_battery_latest",
        "ai_capabilities_latest",
        "ai_workload_latest",
        "ai_policy_latest",
        "ai_llm_registry_latest",
        "ai_llm_resident_status_latest",
        "dictation_status_live",
        "ai_tts_server_status_live",
    }:
        return "abyss_machine_facts"
    if fact.get("name") in {"manual_note", "manual_notes"}:
        return "manual_notes"
    return "abyss_machine_facts"


def compact_json_for_index(value: Any, max_chars: int = 6000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > max_chars:
        return text[:max_chars] + f" ... [truncated {len(text) - max_chars} chars]"
    return text


def apply_redactor(
    text: str,
    redact_text: Callable[[str], tuple[str, int]] | None = None,
) -> tuple[str, int]:
    if redact_text is None:
        return text, 0
    redacted, count = redact_text(text)
    return str(redacted), _safe_int(count, 0)


def fact_index_payload(fact: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "name",
        "source_id",
        "path",
        "exists",
        "ok",
        "schema",
        "version",
        "generated_at",
        "updated_at",
        "status",
        "phase",
        "freshness",
        "summary",
        "class",
        "thermal",
        "battery",
        "scope",
        "unit",
        "observed_at",
        "state",
        "error",
        "sensitivity",
        "coverage",
        "roots",
        "repositories",
        "containers",
        "images",
        "entries",
        "content_entries",
        "commands",
        "processes",
        "profiles",
        "model",
        "runtime",
        "service",
        "server",
        "server_socket",
        "server_socket_exists",
        "recording_active",
        "default_profile",
        "socket",
        "socket_exists",
        "ping",
        "health",
        "metrics",
        "mime_types",
        "text",
        "text_sha256",
        "text_length",
        "redaction",
        "artifact",
        "jsonl_path",
        "readable_path",
        "parse_errors",
    ):
        if key in fact:
            payload[key] = fact.get(key)
    source = fact.get("source")
    if isinstance(source, dict):
        payload["source"] = {
            "path": source.get("path"),
            "exists": source.get("exists"),
            "sha256": source.get("sha256"),
            "stat": source.get("stat"),
            "read_at": source.get("read_at"),
        }
    return payload


def record_is_safe_for_index(
    record: dict[str, Any],
    sources: dict[str, Any],
    *,
    schema_prefix: str = "abyss_machine",
) -> tuple[bool, str | None]:
    schema = record.get("schema")
    supported = {
        f"{schema_prefix}_nervous_fact_snapshot_v1",
        f"{schema_prefix}_nervous_event_v1",
        f"{schema_prefix}_nervous_episode_v1",
    }
    if schema not in supported:
        return False, f"unsupported schema: {schema}"
    if schema == f"{schema_prefix}_nervous_fact_snapshot_v1":
        capture = record.get("capture") if isinstance(record.get("capture"), dict) else {}
        if capture.get("raw_private_content") is not False:
            return False, "raw_private_content is not explicitly false"
        capture_sources = set(capture.get("sources", [])) if isinstance(capture.get("sources"), list) else set()
        disallowed = sorted(capture_sources - allowed_source_ids(sources))
        if disallowed:
            return False, f"sources not enabled/allowed by policy: {','.join(disallowed)}"
        return True, None
    if record.get("raw_private_content") is not False:
        return False, "raw_private_content is not explicitly false"
    source_ids = set(record.get("source_ids", [])) if isinstance(record.get("source_ids"), list) else set()
    disallowed = sorted(source_ids - allowed_source_ids(sources))
    if disallowed:
        return False, f"sources not enabled/allowed by policy: {','.join(disallowed)}"
    if str(record.get("sensitivity") or "").startswith("raw_private"):
        return False, "raw private sensitivity is not indexable"
    return True, None


def chunks_from_record(
    record: dict[str, Any],
    enabled_sources: set[str],
    *,
    schema_prefix: str = "abyss_machine",
    redact_text: Callable[[str], tuple[str, int]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "disabled_chunks": 0,
        "redactions": 0,
        "source_ids": set(),
    }
    schema = record.get("schema")
    if schema == f"{schema_prefix}_nervous_event_v1":
        source_ids = set(record.get("source_ids", [])) if isinstance(record.get("source_ids"), list) else set()
        if source_ids - (enabled_sources | {"heartbeat"}):
            stats["disabled_chunks"] = int(stats["disabled_chunks"]) + 1
            return chunks, stats
        payload = {
            "event_id": record.get("event_id"),
            "observed_at": record.get("observed_at"),
            "event_type": record.get("event_type"),
            "category": record.get("category"),
            "severity": record.get("severity"),
            "confidence": record.get("confidence"),
            "sensitivity": record.get("sensitivity"),
            "title": record.get("title"),
            "summary": record.get("summary"),
            "subject": record.get("subject"),
            "source_ids": sorted(source_ids),
            "payload": record.get("payload"),
            "evidence": record.get("evidence"),
        }
        body = compact_json_for_index(payload, max_chars=8000)
        redacted, redaction_count = apply_redactor(body, redact_text)
        stats["redactions"] = int(stats["redactions"]) + redaction_count
        stats["source_ids"].add("nervous_events")
        chunks.append({
            "source_id": "nervous_events",
            "title": str(record.get("title") or record.get("event_type") or "nervous event"),
            "body": redacted,
            "generated_at": record.get("observed_at") or record.get("generated_at"),
            "privacy_mode": "normal",
            "provenance": {
                "record_generated_at": record.get("generated_at"),
                "event_id": record.get("event_id"),
                "event_type": record.get("event_type"),
                "category": record.get("category"),
                "severity": record.get("severity"),
                "sensitivity": record.get("sensitivity"),
                "source_ids": sorted(source_ids),
            },
        })
        return chunks, stats
    if schema == f"{schema_prefix}_nervous_episode_v1":
        source_ids = set(record.get("source_ids", [])) if isinstance(record.get("source_ids"), list) else set()
        if source_ids - (enabled_sources | {"heartbeat"}):
            stats["disabled_chunks"] = int(stats["disabled_chunks"]) + 1
            return chunks, stats
        payload = {
            "episode_id": record.get("episode_id"),
            "start_at": record.get("start_at"),
            "end_at": record.get("end_at"),
            "day": record.get("day"),
            "category": record.get("category"),
            "severity": record.get("severity"),
            "confidence": record.get("confidence"),
            "sensitivity": record.get("sensitivity"),
            "title": record.get("title"),
            "summary": record.get("summary"),
            "event_count": record.get("event_count"),
            "event_types": record.get("event_types"),
            "event_ids": record.get("event_ids"),
            "evidence": record.get("evidence"),
        }
        body = compact_json_for_index(payload, max_chars=8000)
        redacted, redaction_count = apply_redactor(body, redact_text)
        stats["redactions"] = int(stats["redactions"]) + redaction_count
        stats["source_ids"].add("nervous_episodes")
        chunks.append({
            "source_id": "nervous_episodes",
            "title": str(record.get("title") or "nervous episode"),
            "body": redacted,
            "generated_at": record.get("start_at") or record.get("generated_at"),
            "privacy_mode": "normal",
            "provenance": {
                "record_generated_at": record.get("generated_at"),
                "episode_id": record.get("episode_id"),
                "category": record.get("category"),
                "severity": record.get("severity"),
                "sensitivity": record.get("sensitivity"),
                "source_ids": sorted(source_ids),
            },
        })
        return chunks, stats

    capture = record.get("capture") if isinstance(record.get("capture"), dict) else {}
    privacy = record.get("privacy") if isinstance(record.get("privacy"), dict) else {}
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    facts = record.get("facts") if isinstance(record.get("facts"), list) else []
    heartbeat = bool(capture.get("heartbeat")) or bool(privacy.get("global_pause")) or bool(privacy.get("private_mode"))
    privacy_mode = "private" if privacy.get("private_mode") else "pause" if privacy.get("global_pause") else "normal"
    summary_source = "heartbeat" if heartbeat else "abyss_machine_facts"
    if summary_source == "heartbeat" or summary_source in enabled_sources:
        visible_fact_names = [
            str(item.get("name"))
            for item in facts
            if isinstance(item, dict) and fact_source_id(item) in enabled_sources
        ]
        disabled_fact_count = sum(
            1
            for item in facts
            if isinstance(item, dict) and fact_source_id(item) not in enabled_sources
        )
        body = "\n".join([
            f"nervous snapshot generated_at={record.get('generated_at')}",
            f"trigger={capture.get('trigger')} heartbeat={heartbeat} privacy_mode={privacy_mode}",
            f"facts={summary.get('facts')} skipped={summary.get('skipped')}",
            "visible_fact_names=" + ",".join(visible_fact_names),
            f"source_policy_hidden_fact_count={disabled_fact_count}",
            compact_json_for_index({"skipped": record.get("skipped", [])}, max_chars=3000),
        ])
        redacted, redaction_count = apply_redactor(body, redact_text)
        stats["redactions"] = int(stats["redactions"]) + redaction_count
        stats["source_ids"].add(summary_source)
        chunks.append({
            "source_id": summary_source,
            "title": f"nervous snapshot {record.get('generated_at')}",
            "body": redacted,
            "generated_at": record.get("generated_at"),
            "privacy_mode": privacy_mode,
            "provenance": {
                "record_generated_at": record.get("generated_at"),
                "capture_trigger": capture.get("trigger"),
                "heartbeat": heartbeat,
                "summary": summary,
            },
        })
    else:
        stats["disabled_chunks"] = int(stats["disabled_chunks"]) + 1

    for fact in facts:
        if not isinstance(fact, dict):
            continue
        source_id = fact_source_id(fact)
        if source_id not in enabled_sources:
            stats["disabled_chunks"] = int(stats["disabled_chunks"]) + 1
            continue
        payload = fact_index_payload(fact)
        title_parts = [str(fact.get("name") or "fact")]
        if fact.get("unit"):
            title_parts.append(str(fact.get("unit")))
        if fact.get("path"):
            title_parts.append(str(fact.get("path")))
        body = compact_json_for_index(payload, max_chars=6000)
        redacted, redaction_count = apply_redactor(body, redact_text)
        stats["redactions"] = int(stats["redactions"]) + redaction_count
        stats["source_ids"].add(source_id)
        chunks.append({
            "source_id": source_id,
            "title": " ".join(title_parts),
            "body": redacted,
            "generated_at": fact.get("generated_at") or fact.get("updated_at") or fact.get("observed_at") or record.get("generated_at"),
            "privacy_mode": privacy_mode,
            "provenance": {
                "record_generated_at": record.get("generated_at"),
                "fact_name": fact.get("name"),
                "fact_path": fact.get("path"),
                "unit": fact.get("unit"),
                "source_sha256": _nested_get(payload, ["source", "sha256"]),
            },
        })
    return chunks, stats


def document_rows_from_record(
    item: dict[str, Any],
    record: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    started_at: str,
    schema_prefix: str = "abyss_machine",
    redact_text: Callable[[str], tuple[str, int]] | None = None,
) -> dict[str, Any]:
    schema = record.get("schema")
    doc_source_ids = sorted({str(chunk["source_id"]) for chunk in chunks})
    capture = record.get("capture") if isinstance(record.get("capture"), dict) else {}
    privacy_record = record.get("privacy") if isinstance(record.get("privacy"), dict) else {}
    if schema == f"{schema_prefix}_nervous_event_v1":
        title = f"nervous event {record.get('event_type')} {record.get('observed_at')}"
        document_generated_at = record.get("observed_at") or record.get("generated_at")
        capture_trigger = "derived_event"
        global_pause = 0
        private_mode = 0
        heartbeat = 0
        body_source = {
            "generated_at": record.get("generated_at"),
            "observed_at": record.get("observed_at"),
            "event_id": record.get("event_id"),
            "event_type": record.get("event_type"),
            "category": record.get("category"),
            "severity": record.get("severity"),
            "sensitivity": record.get("sensitivity"),
            "summary": record.get("summary"),
            "source_ids": doc_source_ids,
        }
    elif schema == f"{schema_prefix}_nervous_episode_v1":
        title = f"nervous episode {record.get('category')} {record.get('day')}"
        document_generated_at = record.get("start_at") or record.get("generated_at")
        capture_trigger = "derived_episode"
        global_pause = 0
        private_mode = 0
        heartbeat = 0
        body_source = {
            "generated_at": record.get("generated_at"),
            "start_at": record.get("start_at"),
            "end_at": record.get("end_at"),
            "episode_id": record.get("episode_id"),
            "category": record.get("category"),
            "severity": record.get("severity"),
            "sensitivity": record.get("sensitivity"),
            "event_count": record.get("event_count"),
            "summary": record.get("summary"),
            "source_ids": doc_source_ids,
        }
    else:
        title = f"nervous snapshot {record.get('generated_at')}"
        document_generated_at = record.get("generated_at")
        capture_trigger = capture.get("trigger")
        global_pause = int(bool(privacy_record.get("global_pause")))
        private_mode = int(bool(privacy_record.get("private_mode")))
        heartbeat = int(bool(capture.get("heartbeat")))
        body_source = {
            "generated_at": record.get("generated_at"),
            "capture": capture,
            "privacy": {
                "mode": privacy_record.get("mode"),
                "global_pause": privacy_record.get("global_pause"),
                "private_mode": privacy_record.get("private_mode"),
            },
            "summary": record.get("summary"),
            "source_ids": doc_source_ids,
        }
    body = compact_json_for_index(body_source, max_chars=4000)
    redacted_body, doc_redactions = apply_redactor(body, redact_text)
    doc_id = hashlib.sha256(f"{item['path']}:{item['line']}:{item['record_sha256']}".encode("utf-8")).hexdigest()
    document = {
        "doc_id": doc_id,
        "source_path": item["path"],
        "source_line": item["line"],
        "source_sha256": item.get("source_sha256"),
        "record_sha256": item["record_sha256"],
        "schema": record.get("schema"),
        "generated_at": document_generated_at,
        "capture_trigger": capture_trigger,
        "global_pause": global_pause,
        "private_mode": private_mode,
        "heartbeat": heartbeat,
        "source_ids_json": json.dumps(doc_source_ids, ensure_ascii=False),
        "title": title,
        "body": redacted_body,
        "indexed_at": started_at,
    }
    db_chunks: list[dict[str, Any]] = []
    for chunk_index, chunk in enumerate(chunks):
        chunk_id_raw = f"{doc_id}:{chunk_index}:{chunk['source_id']}:{chunk['title']}:{chunk['body']}"
        chunk_id = hashlib.sha256(chunk_id_raw.encode("utf-8", errors="replace")).hexdigest()
        db_chunks.append({
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "source_id": chunk["source_id"],
            "title": chunk["title"],
            "body": chunk["body"],
            "generated_at": chunk.get("generated_at"),
            "privacy_mode": chunk.get("privacy_mode") or "normal",
            "provenance_json": json.dumps(chunk.get("provenance", {}), ensure_ascii=False, sort_keys=True),
        })
    return {
        "document": document,
        "chunks": db_chunks,
        "redactions": doc_redactions,
        "source_ids": doc_source_ids,
    }


def build_index_projection(
    source_records: list[dict[str, Any]],
    sources: dict[str, Any],
    enabled_sources: set[str],
    *,
    started_at: str,
    schema_prefix: str = "abyss_machine",
    redact_text: Callable[[str], tuple[str, int]] | None = None,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    all_chunks: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    records_seen_by_schema: dict[str, int] = {}
    records_indexed_by_schema: dict[str, int] = {}
    redactions = 0
    disabled_chunks = 0

    for item in sort_source_records(source_records):
        record = item.get("record") if isinstance(item.get("record"), dict) else None
        if record is None:
            skipped_records.append({"path": item.get("path"), "line": item.get("line"), "reason": "record is not an object"})
            continue
        schema = str(record.get("schema") or "unknown")
        records_seen_by_schema[schema] = records_seen_by_schema.get(schema, 0) + 1
        safe, reason = record_is_safe_for_index(record, sources, schema_prefix=schema_prefix)
        if not safe:
            skipped_records.append({"path": item.get("path"), "line": item.get("line"), "reason": reason})
            continue
        chunks, chunk_stats = chunks_from_record(
            record,
            enabled_sources,
            schema_prefix=schema_prefix,
            redact_text=redact_text,
        )
        disabled_chunks += int(chunk_stats.get("disabled_chunks") or 0)
        redactions += int(chunk_stats.get("redactions") or 0)
        if not chunks:
            skipped_records.append({"path": item.get("path"), "line": item.get("line"), "reason": "no chunks after source policy filtering"})
            continue
        projection = document_rows_from_record(
            item,
            record,
            chunks,
            started_at=started_at,
            schema_prefix=schema_prefix,
            redact_text=redact_text,
        )
        documents.append(projection["document"])
        all_chunks.extend(projection["chunks"])
        redactions += int(projection.get("redactions") or 0)
        records_indexed_by_schema[schema] = records_indexed_by_schema.get(schema, 0) + 1

    return {
        "documents": documents,
        "chunks": all_chunks,
        "skipped_records": skipped_records,
        "summary": {
            "records_seen": len(source_records),
            "records_indexed": len(documents),
            "documents_indexed": len(documents),
            "chunks_indexed": len(all_chunks),
            "skipped_records": len(skipped_records),
            "disabled_chunks": disabled_chunks,
            "redactions": redactions,
            "records_seen_by_schema": records_seen_by_schema,
            "records_indexed_by_schema": records_indexed_by_schema,
        },
    }


def build_index_disabled_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    config_path: Path | str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_index_build_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "run_id": run_id,
        "error": "index disabled by config",
        "config_path": str(config_path),
    }


def build_index_global_pause_refused_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    privacy: dict[str, Any],
    privacy_state_path: Path | str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_index_build_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "run_id": run_id,
        "refused": True,
        "error": "global_pause is active; index build did not touch the database",
        "privacy": {
            "global_pause": True,
            "private_mode": bool(privacy.get("private_mode")),
            "state_path": str(privacy_state_path),
        },
    }


def build_index_fts_unavailable_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    fts_error: Any,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_index_build_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "run_id": run_id,
        "error": f"SQLite FTS5 unavailable: {fts_error}",
    }


def build_index_semantic_lock_deferred_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    db_path: Path | str,
    config_path: Path | str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_index_build_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "run_id": run_id,
        "decision": "deferred_existing_semantic_lock",
        "reason": "semantic index operation is active; lexical index rebuild deferred to avoid source_run drift during semantic-build",
        "db_path": str(db_path),
        "config_path": str(config_path),
        "policy": {
            "does_not_interrupt_semantic_build": True,
            "retry_via_timer": True,
        },
    }


def with_index_semantic_lock_deferred(data: dict[str, Any], *, checked_at: str) -> dict[str, Any]:
    updated = dict(data)
    updated["ok"] = True
    updated["decision"] = "deferred_existing_semantic_lock"
    updated["reason"] = "semantic index operation became active before lexical index write; lexical rebuild deferred to avoid source_run drift during semantic-build"
    updated["policy"] = {
        "does_not_interrupt_semantic_build": True,
        "retry_via_timer": True,
        "checked_at": checked_at,
    }
    return updated


def build_index_derived_refresh_summary(
    events_refresh: dict[str, Any],
    episodes_refresh: dict[str, Any],
) -> dict[str, Any]:
    return {
        "events": {
            "ok": events_refresh.get("ok"),
            "events": _nested_get(events_refresh, ["summary", "events"]),
            "error": events_refresh.get("error"),
        },
        "episodes": {
            "ok": episodes_refresh.get("ok"),
            "episodes": _nested_get(episodes_refresh, ["summary", "episodes"]),
            "error": episodes_refresh.get("error"),
        },
    }


def build_index_build_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_id: str,
    started_at: str,
    db_path: Path | str,
    config_path: Path | str,
    privacy: dict[str, Any],
    sources: dict[str, Any],
    enabled_sources: set[str],
    source_files: list[Path] | tuple[Path, ...],
    projection: dict[str, Any],
    parse_errors: list[dict[str, Any]],
    derived_refresh: dict[str, Any],
) -> dict[str, Any]:
    documents = projection["documents"]
    chunks = projection["chunks"]
    skipped_records = projection["skipped_records"]
    projection_summary = projection["summary"]
    source_state = sources.get("state") if isinstance(sources.get("state"), dict) else {}
    return {
        "schema": f"{schema_prefix}_nervous_index_build_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "run_id": run_id,
        "started_at": started_at,
        "db_path": str(db_path),
        "config_path": str(config_path),
        "privacy": {
            "global_pause": bool(privacy.get("global_pause")),
            "private_mode": bool(privacy.get("private_mode")),
        },
        "sources": {
            "enabled_sources": sorted(enabled_sources),
            "enabled_private_connector_sources": sorted(enabled_sources & deferred_source_ids(sources)),
            "state_change_id": source_state.get("last_change_id"),
        },
        "summary": {
            "source_files": len(source_files),
            "records_seen": projection_summary["records_seen"],
            "records_indexed": len(documents),
            "documents_indexed": len(documents),
            "chunks_indexed": len(chunks),
            "parse_errors": len(parse_errors),
            "skipped_records": len(skipped_records),
            "disabled_chunks": projection_summary["disabled_chunks"],
            "redactions": projection_summary["redactions"],
            "records_seen_by_schema": projection_summary["records_seen_by_schema"],
            "records_indexed_by_schema": projection_summary["records_indexed_by_schema"],
        },
        "derived_refresh": derived_refresh,
        "parse_errors": parse_errors[:20],
        "skipped_records": skipped_records[:20],
    }


def build_index_meta_values(
    *,
    schema_prefix: str,
    version: str,
    run_id: str,
    built_at: str,
    source_files: list[Path] | tuple[Path, ...],
    projection: dict[str, Any],
    facts_root: Path | str,
    events_root: Path | str,
    episodes_root: Path | str,
    source_state_change_id: Any,
    privacy_state_change_id: Any,
) -> dict[str, Any]:
    documents = projection["documents"]
    chunks = projection["chunks"]
    projection_summary = projection["summary"]
    return {
        "schema": f"{schema_prefix}_nervous_search_index_v1",
        "backend": "sqlite_fts5",
        "tool_version": version,
        "run_id": run_id,
        "built_at": built_at,
        "source_files": str(len(source_files)),
        "records_seen": str(projection_summary["records_seen"]),
        "records_indexed": str(len(documents)),
        "chunks_indexed": str(len(chunks)),
        "facts_root": str(facts_root),
        "events_root": str(events_root),
        "episodes_root": str(episodes_root),
        "records_seen_by_schema": json.dumps(projection_summary["records_seen_by_schema"], ensure_ascii=False, sort_keys=True),
        "records_indexed_by_schema": json.dumps(projection_summary["records_indexed_by_schema"], ensure_ascii=False, sort_keys=True),
        "source_state_change_id": str(source_state_change_id),
        "privacy_state_change_id": str(privacy_state_change_id),
    }


def with_index_write_success(
    data: dict[str, Any],
    *,
    finished_at: str,
    counts: dict[str, Any],
    parse_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = dict(data)
    updated["ok"] = len(parse_errors) == 0
    updated["finished_at"] = finished_at
    updated["counts"] = counts
    return updated


def with_index_error(data: dict[str, Any], error: Any) -> dict[str, Any]:
    updated = dict(data)
    updated["error"] = str(error)
    return updated


def vacuum_refused_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_index_vacuum_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; vacuum did not touch the database",
    }


def vacuum_start_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    db_path: Path | str,
    before: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_index_vacuum_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "db_path": str(db_path),
        "before": before,
    }


def vacuum_missing_db_result(data: dict[str, Any]) -> dict[str, Any]:
    updated = dict(data)
    updated["error"] = "index database missing"
    return updated


def vacuum_success_result(data: dict[str, Any], *, after: dict[str, Any]) -> dict[str, Any]:
    updated = dict(data)
    updated["ok"] = True
    updated["after"] = after
    return updated


def vacuum_error_result(data: dict[str, Any], error: Any) -> dict[str, Any]:
    updated = dict(data)
    updated["error"] = str(error)
    return updated


def freshness_document(
    *,
    meta: dict[str, Any] | None,
    config: dict[str, Any] | None,
    latest_fact: dict[str, Any] | None,
    latest_event: dict[str, Any] | None,
    latest_episode: dict[str, Any] | None,
    history_records: int,
    history_records_by_layer: dict[str, int],
    history_parse_errors: int,
    now: dt.datetime,
) -> dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    config = config if isinstance(config, dict) else {}
    automation = config.get("automation", {}) if isinstance(config.get("automation"), dict) else {}
    interval_sec = parse_duration_seconds(automation.get("interval"), default=45 * 60.0)
    tolerance_sec = 5 * 60.0
    records_lag_tolerance = 4
    latest_records = [item for item in (latest_fact, latest_event, latest_episode) if isinstance(item, dict)]
    latest_source_record = max(
        latest_records,
        key=lambda item: parse_time(item.get("generated_at") or item.get("observed_at") or item.get("start_at"))
        or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        default=None,
    )
    try:
        index_records_seen = int(meta.get("records_seen")) if meta.get("records_seen") is not None else None
    except (TypeError, ValueError):
        index_records_seen = None
    records_lag = None
    if index_records_seen is not None:
        records_lag = max(int(history_records) - index_records_seen, 0)
    latest_source_time = parse_time(
        latest_source_record.get("observed_at") or latest_source_record.get("start_at") or latest_source_record.get("generated_at")
        if isinstance(latest_source_record, dict)
        else None
    )
    built_time = parse_time(meta.get("built_at"))
    lag_sec = None
    age_sec = None
    stale = None
    if latest_source_time is not None and built_time is not None:
        lag_sec = round(max((latest_source_time - built_time).total_seconds(), 0.0), 1)
        stale = lag_sec > float(interval_sec or 0) + tolerance_sec
    records_lag_stale = bool(
        records_lag is not None
        and records_lag > records_lag_tolerance
        and (lag_sec is None or lag_sec > tolerance_sec)
    )
    if records_lag_stale:
        stale = True
    if built_time is not None:
        age_sec = round(max((now - built_time).total_seconds(), 0.0), 1)
    return {
        "latest_fact_generated_at": latest_fact.get("generated_at") if isinstance(latest_fact, dict) else None,
        "latest_event_observed_at": latest_event.get("observed_at") if isinstance(latest_event, dict) else None,
        "latest_episode_start_at": latest_episode.get("start_at") if isinstance(latest_episode, dict) else None,
        "latest_source_generated_at": latest_source_record.get("generated_at") if isinstance(latest_source_record, dict) else None,
        "latest_source_observed_at": latest_source_record.get("observed_at") or latest_source_record.get("start_at") if isinstance(latest_source_record, dict) else None,
        "index_built_at": meta.get("built_at"),
        "lag_sec": lag_sec,
        "index_age_sec": age_sec,
        "configured_interval_sec": interval_sec,
        "tolerance_sec": tolerance_sec,
        "stale": bool(stale) if stale is not None else None,
        "latest_fact_schema": latest_fact.get("schema") if isinstance(latest_fact, dict) else None,
        "latest_event_schema": latest_event.get("schema") if isinstance(latest_event, dict) else None,
        "latest_episode_schema": latest_episode.get("schema") if isinstance(latest_episode, dict) else None,
        "history_records": int(history_records),
        "history_records_by_layer": history_records_by_layer,
        "history_parse_errors": int(history_parse_errors),
        "history_count_method": "latest_documents_plus_jsonl_line_counts",
        "index_records_seen": index_records_seen,
        "records_lag": records_lag,
        "records_lag_tolerance": records_lag_tolerance,
        "records_lag_stale": records_lag_stale,
    }


def stale_warning(freshness: dict[str, Any]) -> str:
    return (
        "index stale: "
        f"lag={freshness.get('lag_sec')}s "
        f"records_lag={freshness.get('records_lag')} "
        f"latest_fact={freshness.get('latest_fact_generated_at')} built_at={freshness.get('index_built_at')}"
    )


def status_warnings(
    *,
    fts_ok: bool,
    fts_error: Any,
    config: dict[str, Any],
    configured_db_path: Path | str,
    runtime_db_path: Path | str,
    db_exists: bool,
    freshness: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if not fts_ok:
        warnings.append(f"SQLite FTS5 unavailable: {fts_error}")
    if str(config.get("db_path")) != str(runtime_db_path):
        warnings.append("index config db_path differs from runtime path")
    if not db_exists:
        warnings.append("index database missing")
    if freshness.get("stale"):
        warnings.append(stale_warning(freshness))
    return warnings


def status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    config: dict[str, Any],
    config_path: Path | str,
    config_exists: bool,
    privacy: dict[str, Any],
    sources: dict[str, Any],
    sqlite_version: str,
    fts_ok: bool,
    fts_error: Any,
    latest: dict[str, Any] | None,
    latest_error: str | None,
    counts: dict[str, Any],
    freshness: dict[str, Any],
    db_path: Path | str,
    db_exists: bool,
    root_path: Path | str,
    schema_path: Path | str,
    latest_path: Path | str,
    service_status: dict[str, Any],
    timer_status: dict[str, Any],
) -> dict[str, Any]:
    warnings = status_warnings(
        fts_ok=fts_ok,
        fts_error=fts_error,
        config=config,
        configured_db_path=config.get("db_path"),
        runtime_db_path=db_path,
        db_exists=db_exists,
        freshness=freshness,
    )
    return {
        "schema": f"{schema_prefix}_nervous_index_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fts_ok and config.get("_load_error") is None,
        "ready": db_exists and not counts.get("error"),
        "warnings": warnings,
        "config": {
            "path": str(config_path),
            "exists": bool(config_exists),
            "enabled": bool(config.get("enabled", True)),
            "backend": config.get("backend"),
            "load_error": config.get("_load_error"),
        },
        "paths": {
            "db": str(db_path),
            "root": str(root_path),
            "schema": str(schema_path),
            "latest": str(latest_path),
        },
        "privacy": {
            "global_pause": bool(privacy.get("global_pause")),
            "private_mode": bool(privacy.get("private_mode")),
        },
        "sources": {
            "enabled_safe_sources": sorted(enabled_safe_source_ids(sources)),
            "deferred_sources": sorted(deferred_source_ids(sources)),
        },
        "sqlite": {
            "version": sqlite_version,
            "fts5": fts_ok,
            "error": fts_error,
        },
        "counts": counts,
        "freshness": freshness,
        "latest": latest if isinstance(latest, dict) else {"path": str(latest_path), "error": latest_error},
        "timer": {
            "service": service_status,
            "timer": timer_status,
            "scope": "user",
        },
    }


def nervous_index_schema_sql() -> str:
    return """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  ok INTEGER NOT NULL,
  source_files INTEGER NOT NULL,
  records_seen INTEGER NOT NULL,
  records_indexed INTEGER NOT NULL,
  documents_indexed INTEGER NOT NULL,
  chunks_indexed INTEGER NOT NULL,
  errors_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  source_line INTEGER NOT NULL,
  source_sha256 TEXT,
  record_sha256 TEXT NOT NULL,
  schema TEXT,
  generated_at TEXT,
  capture_trigger TEXT,
  global_pause INTEGER NOT NULL,
  private_mode INTEGER NOT NULL,
  heartbeat INTEGER NOT NULL,
  source_ids_json TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  indexed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  source_id TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  generated_at TEXT,
  privacy_mode TEXT NOT NULL,
  provenance_json TEXT NOT NULL,
  FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_documents_generated_at ON documents(generated_at);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
  chunk_id UNINDEXED,
  doc_id UNINDEXED,
  source_id UNINDEXED,
  title,
  body,
  tokenize='unicode61'
);
""".strip()


def connect_db(db_path: Path, create: bool = False) -> sqlite3.Connection:
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
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
    conn.executescript(nervous_index_schema_sql())
    put_meta(
        conn,
        {
            "schema": f"{schema_prefix}_nervous_search_index_v1",
            "backend": "sqlite_fts5",
            "tool_version": version,
        },
    )


def put_meta(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    for key, value in values.items():
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))


def read_meta(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {}
    conn = connect_db(db_path, create=False)
    try:
        return {str(row["key"]): row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def _index_run_from_row(row: sqlite3.Row) -> dict[str, Any]:
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
        "source_files": _safe_int(row["source_files"], 0),
        "records_seen": _safe_int(row["records_seen"], 0),
        "records_indexed": _safe_int(row["records_indexed"], 0),
        "documents_indexed": _safe_int(row["documents_indexed"], 0),
        "chunks_indexed": _safe_int(row["chunks_indexed"], 0),
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
        try:
            for table in ("documents", "chunks", "fts_chunks", "index_runs"):
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
                    SELECT run_id, started_at, finished_at, ok, source_files, records_seen, records_indexed,
                           documents_indexed, chunks_indexed, errors_json
                    FROM index_runs
                    ORDER BY COALESCE(finished_at, started_at) DESC
                    LIMIT 1
                    """
                ).fetchone()
                if row:
                    data["last_index_run"] = _index_run_from_row(row)
                row = conn.execute(
                    """
                    SELECT run_id, started_at, finished_at, ok, source_files, records_seen, records_indexed,
                           documents_indexed, chunks_indexed, errors_json
                    FROM index_runs
                    WHERE ok = 1
                    ORDER BY COALESCE(finished_at, started_at) DESC
                    LIMIT 1
                    """
                ).fetchone()
                if row:
                    data["last_successful_index_run"] = _index_run_from_row(row)
            except sqlite3.Error as exc:
                data["last_index_run_error"] = str(exc)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        data["error"] = str(exc)
    return data


def replace_index_contents(
    conn: sqlite3.Connection,
    *,
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    meta_values: dict[str, Any],
    run_id: str,
    started_at: str,
    finished_at: str,
    ok: bool,
    source_files: int,
    records_seen: int,
    records_indexed: int,
    documents_indexed: int,
    chunks_indexed: int,
    errors: dict[str, Any],
) -> None:
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM fts_chunks")
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM documents")
        for doc in documents:
            conn.execute(
                """
                INSERT INTO documents (
                  doc_id, source_path, source_line, source_sha256, record_sha256, schema, generated_at,
                  capture_trigger, global_pause, private_mode, heartbeat, source_ids_json, title, body, indexed_at
                ) VALUES (
                  :doc_id, :source_path, :source_line, :source_sha256, :record_sha256, :schema, :generated_at,
                  :capture_trigger, :global_pause, :private_mode, :heartbeat, :source_ids_json, :title, :body, :indexed_at
                )
                """,
                doc,
            )
        for chunk in chunks:
            conn.execute(
                """
                INSERT INTO chunks (
                  chunk_id, doc_id, chunk_index, source_id, title, body, generated_at, privacy_mode, provenance_json
                ) VALUES (
                  :chunk_id, :doc_id, :chunk_index, :source_id, :title, :body, :generated_at, :privacy_mode, :provenance_json
                )
                """,
                chunk,
            )
            conn.execute(
                "INSERT INTO fts_chunks(chunk_id, doc_id, source_id, title, body) VALUES (?, ?, ?, ?, ?)",
                (chunk["chunk_id"], chunk["doc_id"], chunk["source_id"], chunk["title"], chunk["body"]),
            )
        put_meta(conn, meta_values)
        record_index_run(
            conn,
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            ok=ok,
            source_files=source_files,
            records_seen=records_seen,
            records_indexed=records_indexed,
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
            errors=errors,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def record_index_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    ok: bool,
    source_files: int,
    records_seen: int,
    records_indexed: int,
    documents_indexed: int,
    chunks_indexed: int,
    errors: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO index_runs (
          run_id, started_at, finished_at, ok, source_files, records_seen, records_indexed,
          documents_indexed, chunks_indexed, errors_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            started_at,
            finished_at,
            1 if ok else 0,
            int(source_files),
            int(records_seen),
            int(records_indexed),
            int(documents_indexed),
            int(chunks_indexed),
            json.dumps(errors, ensure_ascii=False, sort_keys=True),
        ),
    )


def search_match_query(query: str) -> str:
    tokens = [token for token in re.findall(r"\w+", query, flags=re.UNICODE) if token]
    tokens = tokens[:16]
    return " OR ".join(f'"{token}"' for token in tokens)


def search_sort_key(item: dict[str, Any], order: str) -> tuple[Any, ...]:
    parsed = parse_time(item.get("document_generated_at") or item.get("chunk_generated_at"))
    timestamp = parsed.timestamp() if parsed else 0.0
    score = float(item.get("score") or 0.0)
    if order == "ranked":
        return (score, -timestamp)
    return (-timestamp, score)


def search_dedupe_key(item: dict[str, Any]) -> tuple[str, str]:
    title = str(item.get("title") or "")
    normalized_title = re.sub(r"\bnervous snapshot \d{4}-\d{2}-\d{2}T[^\s]+", "nervous snapshot", title)
    return (str(item.get("source_id") or ""), normalized_title)


def search_dedupe_results(rows: list[dict[str, Any]], limit: int, order: str, dedupe: bool) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=lambda item: search_sort_key(item, order))
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


def search_options(
    config: dict[str, Any],
    *,
    requested_limit: int | None,
    requested_order: str,
) -> dict[str, Any]:
    search_config = config.get("search") if isinstance(config.get("search"), dict) else {}
    max_limit = max(1, _safe_int(search_config.get("max_limit") or 50, 50))
    default_limit = max(1, _safe_int(search_config.get("default_limit") or 12, 12))
    final_limit = max(1, min(_safe_int(requested_limit or default_limit, default_limit), max_limit))
    order = requested_order if requested_order in {"latest", "ranked"} else "latest"
    snippet_tokens = _safe_int(search_config.get("snippet_tokens") or 18, 18)
    return {
        "final_limit": final_limit,
        "order": order,
        "max_limit": max_limit,
        "default_limit": default_limit,
        "snippet_tokens": snippet_tokens,
        "scan_limit": min(max_limit * 16, max(final_limit * 16, final_limit)),
    }


def search_refused_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    error: str = "global_pause is active; search is refused",
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_search_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": error,
    }


def search_index(
    *,
    db_path: Path,
    query: str,
    final_limit: int,
    dedupe: bool = True,
    order: str = "latest",
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    snippet_tokens: int = 18,
    scan_limit: int | None = None,
    freshness: dict[str, Any] | None = None,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "schema": f"{schema_prefix}_nervous_search_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "query": query,
            "error": "index database missing; run abyss-machine nervous index-build --json",
            "db_path": str(db_path),
        }
    match_query = search_match_query(query)
    if not match_query:
        return {
            "schema": f"{schema_prefix}_nervous_search_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "query": query,
            "error": "query produced no searchable tokens",
        }
    order = order if order in {"latest", "ranked"} else "latest"
    since_time = parse_time(since) if since else None
    until_time = parse_time(until) if until else None
    try:
        conn = connect_db(db_path, create=False)
        rows = conn.execute(
            """
            SELECT
              fts_chunks.chunk_id AS chunk_id,
              fts_chunks.doc_id AS doc_id,
              fts_chunks.source_id AS source_id,
              fts_chunks.title AS title,
              snippet(fts_chunks, 4, '[', ']', '...', ?) AS snippet,
              bm25(fts_chunks) AS score,
              documents.generated_at AS document_generated_at,
              documents.schema AS document_schema,
              chunks.generated_at AS chunk_generated_at,
              chunks.privacy_mode AS privacy_mode,
              chunks.provenance_json AS provenance_json,
              documents.capture_trigger AS capture_trigger,
              documents.source_path AS source_path,
              documents.source_line AS source_line
            FROM fts_chunks
            JOIN documents ON documents.doc_id = fts_chunks.doc_id
            JOIN chunks ON chunks.chunk_id = fts_chunks.chunk_id
            WHERE fts_chunks MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (int(snippet_tokens), match_query, int(scan_limit or max(final_limit, 1))),
        ).fetchall()
        raw_results: list[dict[str, Any]] = []
        filtered_out = 0
        for row in rows:
            item = dict(row)
            try:
                provenance = json.loads(str(item.get("provenance_json") or "{}"))
                if not isinstance(provenance, dict):
                    provenance = {}
            except json.JSONDecodeError:
                provenance = {}
            item["severity"] = provenance.get("severity")
            item["sensitivity"] = provenance.get("sensitivity")
            item["provenance"] = {
                key: provenance.get(key)
                for key in ("event_id", "episode_id", "event_type", "category", "severity", "sensitivity", "source_ids")
                if key in provenance
            }
            item.pop("provenance_json", None)
            timestamp = parse_time(item.get("chunk_generated_at") or item.get("document_generated_at"))
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
            if keep:
                raw_results.append(item)
            else:
                filtered_out += 1
        results = search_dedupe_results(raw_results, final_limit, order=order, dedupe=dedupe)
        meta = {str(row["key"]): row["value"] for row in conn.execute("SELECT key, value FROM meta")}
        conn.close()
        summary: dict[str, Any] = {
            "results": len(results),
            "raw_results": len(raw_results),
            "filtered_out": filtered_out,
            "deduped": max(len(raw_results) - len(results), 0) if dedupe else 0,
            "index_run_id": meta.get("run_id"),
            "built_at": meta.get("built_at"),
        }
        if freshness is not None:
            summary["freshness"] = freshness
        return {
            "schema": f"{schema_prefix}_nervous_search_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": True,
            "query": query,
            "match_query": match_query,
            "limit": final_limit,
            "order": order,
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
            "summary": summary,
        }
    except sqlite3.Error as exc:
        return {
            "schema": f"{schema_prefix}_nervous_search_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "query": query,
            "match_query": match_query,
            "db_path": str(db_path),
            "error": str(exc),
        }


def scan_index(db_path: Path, *, smoke_match_query: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "indexed_source_ids": [],
        "documents_by_schema": {},
        "smoke_results": 0,
    }
    if not db_path.exists():
        return data
    conn = connect_db(db_path, create=False)
    try:
        rows = conn.execute("SELECT DISTINCT source_id FROM chunks").fetchall()
        data["indexed_source_ids"] = sorted({str(row["source_id"]) for row in rows})
        documents_by_schema: dict[str, int] = {}
        for row in conn.execute("SELECT schema, count(*) AS count FROM documents GROUP BY schema"):
            documents_by_schema[str(row["schema"])] = int(row["count"])
        data["documents_by_schema"] = documents_by_schema
        smoke = conn.execute("SELECT count(*) FROM fts_chunks WHERE fts_chunks MATCH ?", (smoke_match_query,)).fetchone()
        data["smoke_results"] = int(smoke[0]) if smoke else 0
    finally:
        conn.close()
    return data


def validation_check(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["details"] = details
    return item


def validation_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    db_path: Path | str,
    config: dict[str, Any],
    config_path: Path | str,
    config_exists: bool,
    fts_ok: bool,
    fts_error: Any,
    storage_routed: bool,
    storage_root: Path | str,
    symlink_tail: bool,
    db_exists: bool,
    counts: dict[str, Any],
    freshness: dict[str, Any],
    allowed_source_ids: set[str],
    scan: dict[str, Any] | None,
    scan_error: str | None,
    private_source_ids: set[str],
    event_records: int,
    episode_records: int,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
        checks.append(validation_check(level, key, message, details))

    add(
        "ok" if fts_ok else "fail",
        "sqlite_fts5",
        "SQLite FTS5 is available" if fts_ok else "SQLite FTS5 is unavailable",
        {"error": fts_error} if fts_error else None,
    )
    add(
        "ok" if config.get("_load_error") is None else "fail",
        "config_load",
        "index config loaded",
        {"path": str(config_path), "exists": bool(config_exists), "load_error": config.get("_load_error")},
    )
    if not config_exists:
        add("warn", "config_file", "index config file is missing; built-in defaults are active", {"path": str(config_path)})
    add(
        "ok" if storage_routed else "fail",
        "storage_route",
        "index database is routed under the machine-owned storage root",
        {"db": str(db_path), "storage_root": str(storage_root)},
    )
    add(
        "ok" if not symlink_tail else "fail",
        "symlink_tail",
        "index route has no symlink tail",
        {"db": str(db_path)},
    )
    add("ok" if db_exists else "fail", "db_exists", "index database exists", {"db": str(db_path)})

    if counts.get("error"):
        add("fail", "db_open", "index database opens cleanly", {"error": counts.get("error")})
    else:
        add("ok" if db_exists else "fail", "db_open", "index database opens cleanly")
    meta = counts.get("meta") if isinstance(counts.get("meta"), dict) else {}
    add(
        "ok" if meta.get("schema") == f"{schema_prefix}_nervous_search_index_v1" else "fail",
        "schema",
        f"index schema {meta.get('schema')}",
    )
    add(
        "ok" if freshness.get("stale") is False else "warn",
        "freshness",
        "index is fresh enough for configured interval"
        if freshness.get("stale") is False
        else "index freshness is unknown or stale",
        freshness,
    )
    documents = _safe_int(counts.get("documents"), 0)
    chunks = _safe_int(counts.get("chunks"), 0)
    fts_chunks = _safe_int(counts.get("fts_chunks"), 0)
    add("ok" if documents > 0 else "warn", "documents", "documents are indexed", {"documents": documents})
    add("ok" if chunks > 0 else "warn", "chunks", "chunks are indexed", {"chunks": chunks})
    add(
        "ok" if chunks == fts_chunks else "fail",
        "fts_count",
        "FTS row count matches chunk count",
        {"chunks": chunks, "fts_chunks": fts_chunks},
    )

    scan_data = scan if isinstance(scan, dict) else {}
    indexed_source_ids = {str(item) for item in scan_data.get("indexed_source_ids", [])} if scan_data else set()
    allowed = {str(item) for item in allowed_source_ids}
    private_sources = {str(item) for item in private_source_ids}
    disabled_or_unknown = sorted(indexed_source_ids - allowed)
    private_present = sorted(indexed_source_ids & private_sources)
    documents_by_schema = (
        dict(scan_data.get("documents_by_schema", {}))
        if isinstance(scan_data.get("documents_by_schema"), dict)
        else {}
    )
    smoke_results = _safe_int(scan_data.get("smoke_results"), 0) if scan_data else 0
    if scan_error:
        add("fail", "source_scan", "indexed source ids can be scanned", {"error": str(scan_error)})
    add(
        "ok",
        "private_connector_sources",
        "enabled private connector source ids may be indexed after redaction",
        {"private_present": private_present},
    )
    add(
        "ok" if not disabled_or_unknown else "fail",
        "source_policy",
        "indexed source ids match current enabled source policy",
        {"disabled_or_unknown": disabled_or_unknown, "allowed": sorted(allowed)},
    )
    add(
        "ok" if chunks == 0 or smoke_results > 0 else "fail",
        "fts_smoke",
        "FTS smoke query returns indexed material",
        {"results": smoke_results},
    )
    add(
        "ok" if event_records == 0 or documents_by_schema.get(f"{schema_prefix}_nervous_event_v1", 0) > 0 else "fail",
        "events_indexed",
        "event records are present in the index when event JSONL exists",
        {"event_records": int(event_records), "documents_by_schema": documents_by_schema},
    )
    add(
        "ok" if episode_records == 0 or documents_by_schema.get(f"{schema_prefix}_nervous_episode_v1", 0) > 0 else "fail",
        "episodes_indexed",
        "episode records are present in the index when episode JSONL exists",
        {"episode_records": int(episode_records), "documents_by_schema": documents_by_schema},
    )

    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_index_validate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "db_path": str(db_path),
        "freshness": freshness,
        "checks": checks,
        "summary": {
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
            "documents": documents,
            "chunks": chunks,
            "fts_chunks": fts_chunks,
            "documents_by_schema": documents_by_schema,
        },
    }


def nervous_index_bounded_validate_from_status(
    index_status: dict[str, Any],
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    warnings = index_status.get("warnings") if isinstance(index_status.get("warnings"), list) else []
    checks: list[dict[str, Any]] = []
    ready = bool(index_status.get("ready"))
    status_ok = bool(index_status.get("ok"))
    checks.append({
        "level": "ok" if ready else "fail",
        "key": "index_ready",
        "message": "index database is ready" if ready else "index database is not ready",
        "details": {"ready": ready, "paths": index_status.get("paths")},
    })
    checks.append({
        "level": "ok" if status_ok else "fail",
        "key": "index_status",
        "message": "index status is ok" if status_ok else "index status is not ok",
        "details": {"ok": status_ok},
    })
    freshness = index_status.get("freshness") if isinstance(index_status.get("freshness"), dict) else {}
    stale = freshness.get("stale")
    checks.append({
        "level": "ok" if stale is False else "warn",
        "key": "freshness",
        "message": "index freshness is acceptable" if stale is False else "index freshness is unknown or stale",
        "details": freshness,
    })
    if warnings:
        checks.append({
            "level": "warn",
            "key": "index_status_warnings",
            "message": "index status has warnings",
            "details": {"warnings": warnings[:12]},
        })
    fails = sum(1 for item in checks if item["level"] == "fail")
    warn_count = sum(1 for item in checks if item["level"] == "warn")
    counts = index_status.get("counts") if isinstance(index_status.get("counts"), dict) else {}
    return {
        "schema": f"{schema_prefix}_nervous_index_validate_bounded_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "db_path": _nested_get(index_status, ["paths", "db"]),
        "freshness": freshness,
        "checks": checks,
        "summary": {
            "fails": fails,
            "warnings": warn_count,
            "checks": len(checks),
            "documents": _safe_int(counts.get("documents"), 0),
            "chunks": _safe_int(counts.get("chunks"), 0),
            "fts_chunks": _safe_int(counts.get("fts_chunks"), 0),
            "bounded": True,
            "full_scan": False,
        },
        "policy": {
            "bounded_status_read": True,
            "full_index_scan": False,
            "writes_project_roots": False,
        },
    }
