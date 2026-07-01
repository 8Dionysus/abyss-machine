from __future__ import annotations

import datetime as dt
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from . import typing_capture_contracts


SAVED_TEXT_SOURCE = "saved_text_snapshot"
WriteJson = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
IndexDocument = Callable[[], dict[str, Any]]
IngestItem = Callable[[Mapping[str, Any]], Mapping[str, Any]]
AgeSeconds = Callable[[Any], float | None]


def nested_get(data: Mapping[str, Any] | None, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def saved_text_decode(path: Path, max_bytes: int) -> tuple[str, int, str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return "", 0, f"read_failed: {exc}"
    size = len(raw)
    if size > max_bytes:
        return "", size, "too_large"
    if b"\x00" in raw[:4096]:
        return "", size, "binary_or_nul_bytes"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return "", size, "empty_or_whitespace"
    printable = sum(1 for ch in text[:4000] if ch.isprintable() or ch in "\n\r\t")
    sample_len = max(1, min(len(text), 4000))
    if printable / sample_len < 0.82:
        return "", size, "low_text_ratio"
    return text, size, None


def saved_text_scan_limits(saved_policy: Mapping[str, Any]) -> dict[str, int]:
    return {
        "changed_within_sec": max(60, safe_int(saved_policy.get("changed_within_sec"), 1800)),
        "max_file_bytes": max(1024, safe_int(saved_policy.get("max_file_bytes"), 262144)),
        "max_files_per_scan": max(1, min(safe_int(saved_policy.get("max_files_per_scan"), 80), 500)),
        "max_roots": max(1, min(safe_int(saved_policy.get("max_roots"), 8), 32)),
    }


def saved_text_scan_report_limits(saved_policy: Mapping[str, Any]) -> dict[str, int]:
    return {
        "changed_within_sec": safe_int(saved_policy.get("changed_within_sec"), 1800),
        "max_file_bytes": safe_int(saved_policy.get("max_file_bytes"), 262144),
        "max_files_per_scan": safe_int(saved_policy.get("max_files_per_scan"), 80),
    }


def saved_text_scan_roots(saved_policy: Mapping[str, Any]) -> list[Path]:
    limits = saved_text_scan_limits(saved_policy)
    return [
        Path(str(item)).expanduser()
        for item in saved_policy.get("roots", [])
        if str(item).strip()
    ][: limits["max_roots"]]


def _previous_file_state(state: Mapping[str, Any], path: Path) -> Mapping[str, Any]:
    previous_files = state.get("files") if isinstance(state.get("files"), Mapping) else {}
    previous = previous_files.get(str(path)) if isinstance(previous_files, Mapping) else None
    return previous if isinstance(previous, Mapping) else {}


def _policy_path_matches(path: Path, saved_policy: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    excluded = typing_capture_contracts.saved_text_path_excluded(path, saved_policy)
    if excluded:
        return "excluded_generated_path", excluded[:5]
    low_signal = typing_capture_contracts.saved_text_low_signal_artifact(path, saved_policy)
    if low_signal:
        return "excluded_low_signal_artifact_path", low_signal[:5]
    denied = typing_capture_contracts.saved_text_path_denied(path, saved_policy)
    if denied:
        return "sensitive_path", denied[:5]
    return None, []


def saved_text_scan_candidates(
    saved_policy: dict[str, Any],
    state: Mapping[str, Any],
    *,
    now_ts: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_ts = time.time() if now_ts is None else float(now_ts)
    limits = saved_text_scan_limits(saved_policy)
    exclude_dirs = {str(item) for item in saved_policy.get("exclude_dir_names", []) if str(item).strip()}
    candidates: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    seen_files = 0

    for root in saved_text_scan_roots(saved_policy):
        if len(candidates) >= limits["max_files_per_scan"]:
            break
        if not root.exists() or not root.is_dir():
            skips.append({"path": str(root), "reason": "root_missing"})
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                if len(candidates) >= limits["max_files_per_scan"]:
                    break
                dirnames[:] = [
                    name for name in dirnames
                    if name not in exclude_dirs
                    and not typing_capture_contracts.saved_text_path_excluded(Path(dirpath) / name, saved_policy)
                    and not typing_capture_contracts.saved_text_path_denied(Path(dirpath) / name, saved_policy)
                ]
                for filename in filenames:
                    if len(candidates) >= limits["max_files_per_scan"]:
                        break
                    path = Path(dirpath) / filename
                    seen_files += 1
                    skip_reason, matches = _policy_path_matches(path, saved_policy)
                    if skip_reason:
                        skips.append({"path": str(path), "reason": skip_reason, "matches": matches})
                        continue
                    if not typing_capture_contracts.saved_text_file_allowed(path, saved_policy):
                        continue
                    try:
                        stat = path.stat()
                    except OSError as exc:
                        skips.append({"path": str(path), "reason": f"stat_failed: {exc}"[:180]})
                        continue
                    if not stat or not stat.st_mtime or current_ts - float(stat.st_mtime) > limits["changed_within_sec"]:
                        continue
                    if int(stat.st_size) > limits["max_file_bytes"]:
                        skips.append({"path": str(path), "reason": "too_large", "size_bytes": int(stat.st_size)})
                        continue
                    text, size, read_error = saved_text_decode(path, limits["max_file_bytes"])
                    if read_error:
                        skips.append({"path": str(path), "reason": read_error, "size_bytes": size})
                        continue
                    sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                    previous = _previous_file_state(state, path)
                    if previous.get("sha256") == sha:
                        continue
                    candidates.append({
                        "path": str(path),
                        "root": str(root),
                        "name": path.name,
                        "suffix": path.suffix.lower(),
                        "size_bytes": int(stat.st_size),
                        "mtime": dt.datetime.fromtimestamp(float(stat.st_mtime), dt.timezone.utc).isoformat(),
                        "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
                        "sha256": sha,
                        "text": text,
                    })
        except OSError as exc:
            skips.append({"path": str(root), "reason": f"walk_failed: {exc}"[:180]})

    skips.append({"reason": "scan_seen_files", "count": seen_files})
    return candidates, skips


def saved_text_disabled_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_saved_text_scan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "status": "disabled",
        "source_adapter": SAVED_TEXT_SOURCE,
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }


def saved_text_item_metadata(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in ("path", "root", "name", "suffix", "size_bytes", "mtime", "sha256")}


def saved_text_ingest_kwargs(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "text": str(item.get("text") or ""),
        "source": SAVED_TEXT_SOURCE,
        "app": "filesystem",
        "window_title": str(item.get("name") or ""),
        "context": f"saved_text path={item.get('path')} root={item.get('root')}",
        "skip_duplicate": True,
        "metadata": {"file": saved_text_item_metadata(item)},
        "include_text_in_context_probe": False,
    }


def saved_text_event_summary(item: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "status": event.get("status"),
        "path": item.get("path"),
        "size_bytes": item.get("size_bytes"),
        "text_length": nested_get(event, ["text", "text_length"]),
        "stored_chars": nested_get(event, ["text", "text_chars_stored"]),
        "redaction": nested_get(event, ["text", "redaction"]),
        "duplicate": event.get("duplicate"),
        "capture_gate": event.get("capture_gate") if isinstance(event.get("capture_gate"), Mapping) else {},
        "causal_context": event.get("causal_context") if isinstance(event.get("causal_context"), Mapping) else {},
    }


def saved_text_state_entry(
    item: Mapping[str, Any],
    *,
    generated_at: str,
    primed: bool = False,
) -> dict[str, Any]:
    entry = {
        "sha256": item.get("sha256"),
        "mtime": item.get("mtime"),
        "mtime_ns": item.get("mtime_ns"),
        "last_seen_at": generated_at,
    }
    if primed:
        entry["primed"] = True
    return entry


def saved_text_state_document(
    state: Mapping[str, Any] | None,
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    file_updates: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    data = dict(state) if isinstance(state, Mapping) else {}
    files = data.get("files") if isinstance(data.get("files"), Mapping) else {}
    data["schema"] = f"{schema_prefix}_typing_saved_text_state_v1"
    data["version"] = version
    data["updated_at"] = generated_at
    data["files"] = {str(path): dict(entry) for path, entry in files.items()}
    for path, entry in (file_updates or {}).items():
        data["files"][str(path)] = dict(entry)
    return data


def saved_text_process_scan_candidates(
    candidates: list[Mapping[str, Any]],
    *,
    generated_at: str,
    prime_state: bool,
    ingest_item: IngestItem,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    file_updates: dict[str, dict[str, Any]] = {}
    for item in candidates:
        path = str(item.get("path"))
        if prime_state:
            file_updates[path] = saved_text_state_entry(
                item,
                generated_at=generated_at,
                primed=True,
            )
            continue
        event = ingest_item(item)
        events.append(saved_text_event_summary(item, event))
        file_updates[path] = saved_text_state_entry(
            item,
            generated_at=generated_at,
        )
    return events, file_updates


def saved_text_scan_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    candidates: list[Mapping[str, Any]],
    events: list[dict[str, Any]],
    skips: list[dict[str, Any]],
    saved_policy: Mapping[str, Any],
    state_error: str | None,
    paths: Mapping[str, Any],
    prime_state: bool = False,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_saved_text_scan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "status": "ok",
        "source_adapter": SAVED_TEXT_SOURCE,
        "summary": {
            "candidates": len(candidates),
            "events": len(events),
            "primed": len(candidates) if prime_state else 0,
            "skips": len(skips),
            "state_error": state_error,
        },
        "events": events,
        "skips": skips[:80],
        "roots": saved_policy.get("roots", []),
        "limits": saved_text_scan_report_limits(saved_policy),
        "policy": {
            "raw_keylogging": False,
            "committed_text_only": True,
            "password_fields_captured": False,
            "global_keyboard_hook": False,
            "automatic_action": False,
            "deny_sensitive_paths": True,
            "redaction": "typing_ingest",
        },
        "paths": dict(paths),
        "non_claims": [
            "Saved-text scan reads recently saved text files only; it does not observe keystrokes.",
            "Sensitive path filters prevent known secret-path reads but are not a complete DLP proof.",
        ],
    }


def saved_text_write_scan_outputs(
    *,
    state: dict[str, Any],
    data: dict[str, Any],
    state_path: Path,
    latest_path: Path,
    index_path: Path,
    write_json: WriteJson,
    index_document: IndexDocument,
    mode: int = 0o664,
) -> dict[str, Any]:
    errors = [
        error for error in (
            write_json(state_path, state, mode),
            write_json(latest_path, data, mode),
            write_json(index_path, index_document(), mode),
        )
        if error
    ]
    if errors:
        data = dict(data)
        data["ok"] = False
        data["write_errors"] = errors
    return data


def saved_text_scan_latest_status_document(
    *,
    latest: Mapping[str, Any] | None,
    latest_error: str | None,
    timer: Mapping[str, Any],
    service: Mapping[str, Any],
    generated_at: str,
    max_age_sec: float,
    latest_path: Path,
    schema_prefix: str,
    version: str,
    age_seconds_from_iso: AgeSeconds,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    latest_summary = latest_data.get("summary") if isinstance(latest_data.get("summary"), Mapping) else {}
    latest_policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    latest_age_sec = age_seconds_from_iso(latest_data.get("generated_at"))
    latest_status = str(latest_data.get("status") or "missing")
    healthy_statuses = {"ok", "disabled"}
    timer_ok = bool(timer.get("is_active") and timer.get("is_enabled"))
    policy_ok = bool(
        latest_policy.get("raw_keylogging") is False
        and latest_policy.get("password_fields_captured") is False
        and latest_policy.get("global_keyboard_hook") is False
        and latest_policy.get("automatic_action") is False
        and latest_policy.get("deny_sensitive_paths") is True
    )
    latest_ok = bool(isinstance(latest, Mapping) and latest_data.get("ok") is True and latest_status in healthy_statuses)
    latest_fresh = bool(latest_age_sec is not None and latest_age_sec <= float(max_age_sec))
    state_error = latest_summary.get("state_error")
    if not isinstance(latest, Mapping):
        status = "missing"
    elif latest_error:
        status = "unreadable"
    elif not timer_ok:
        status = "timer_inactive"
    elif not policy_ok:
        status = "policy_violation"
    elif not latest_ok:
        status = latest_status if latest_status != "missing" else "degraded"
    elif state_error:
        status = "state_error"
    elif not latest_fresh:
        status = "stale"
    else:
        status = latest_status
    return {
        "schema": f"{schema_prefix}_typing_saved_text_scan_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(status in healthy_statuses),
        "status": status,
        "summary": {
            "latest_exists": isinstance(latest, Mapping),
            "latest_error": latest_error,
            "latest_ok": latest_data.get("ok") if isinstance(latest, Mapping) else None,
            "latest_status": latest_data.get("status") if isinstance(latest, Mapping) else None,
            "latest_generated_at": latest_data.get("generated_at") if isinstance(latest, Mapping) else None,
            "latest_age_sec": latest_age_sec,
            "max_age_sec": float(max_age_sec),
            "timer_active": timer.get("is_active"),
            "timer_enabled": timer.get("is_enabled"),
            "service_active": service.get("is_active"),
            "candidates": latest_summary.get("candidates"),
            "events": latest_summary.get("events"),
            "primed": latest_summary.get("primed"),
            "skips": latest_summary.get("skips"),
            "state_error": state_error,
        },
        "latest": {
            "path": str(latest_path),
            "generated_at": latest_data.get("generated_at") if isinstance(latest, Mapping) else None,
            "status": latest_data.get("status") if isinstance(latest, Mapping) else None,
            "ok": latest_data.get("ok") if isinstance(latest, Mapping) else None,
            "summary": latest_summary,
            "events": latest_data.get("events") if isinstance(latest_data.get("events"), list) else [],
            "roots": latest_data.get("roots") if isinstance(latest_data.get("roots"), list) else [],
            "limits": latest_data.get("limits") if isinstance(latest_data.get("limits"), Mapping) else {},
        },
        "timer": dict(timer),
        "service": dict(service),
        "policy": {
            "raw_keylogging": latest_policy.get("raw_keylogging"),
            "committed_text_only": latest_policy.get("committed_text_only"),
            "password_fields_captured": latest_policy.get("password_fields_captured"),
            "global_keyboard_hook": latest_policy.get("global_keyboard_hook"),
            "automatic_action": latest_policy.get("automatic_action"),
            "deny_sensitive_paths": latest_policy.get("deny_sensitive_paths"),
            "redaction": latest_policy.get("redaction"),
        },
    }
