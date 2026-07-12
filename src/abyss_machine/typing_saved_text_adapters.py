from __future__ import annotations

import datetime as dt
import hashlib
import os
import time
from collections import Counter, deque
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
        "max_entries_per_scan": max(100, min(safe_int(saved_policy.get("max_entries_per_scan"), 5000), 100000)),
        "max_directories_per_scan": max(1, min(safe_int(saved_policy.get("max_directories_per_scan"), 500), 10000)),
        "max_scan_seconds": max(1, min(safe_int(saved_policy.get("max_scan_seconds"), 5), 60)),
        "max_skip_records": max(1, min(safe_int(saved_policy.get("max_skip_records"), 80), 500)),
        "max_pending_directories": max(16, min(safe_int(saved_policy.get("max_pending_directories"), 10000), 50000)),
        "max_state_files": max(1000, min(safe_int(saved_policy.get("max_state_files"), 20000), 100000)),
    }


def saved_text_scan_report_limits(saved_policy: Mapping[str, Any]) -> dict[str, int]:
    limits = saved_text_scan_limits(saved_policy)
    return {
        key: limits[key]
        for key in (
            "changed_within_sec",
            "max_file_bytes",
            "max_files_per_scan",
            "max_entries_per_scan",
            "max_directories_per_scan",
            "max_scan_seconds",
            "max_skip_records",
            "max_pending_directories",
            "max_state_files",
        )
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


def _cursor_queue(
    state: Mapping[str, Any],
    roots: list[Path],
    max_pending: int,
) -> tuple[deque[dict[str, str | None]], int]:
    root_strings = [str(root) for root in roots]
    cursor = state.get("scan_cursor") if isinstance(state.get("scan_cursor"), Mapping) else {}
    pending_data = cursor.get("pending_directories") if isinstance(cursor, Mapping) else None
    cycle = safe_int(cursor.get("cycle"), 0) if isinstance(cursor, Mapping) else 0
    pending: deque[dict[str, str | None]] = deque()
    seen: set[tuple[str, str | None]] = set()

    if isinstance(cursor, Mapping) and cursor.get("roots") == root_strings and isinstance(pending_data, list):
        for item in pending_data[:max_pending]:
            if isinstance(item, str):
                path, after = item, None
            elif isinstance(item, Mapping):
                path = str(item.get("path") or "")
                after_value = item.get("after")
                after = str(after_value) if after_value else None
            else:
                continue
            if not path:
                continue
            key = (path, after)
            if key not in seen:
                pending.append({"path": path, "after": after})
                seen.add(key)

    if not pending:
        pending.extend({"path": path, "after": None} for path in root_strings)
        cycle += 1
    return pending, cycle


def _prune_state_files(state: Mapping[str, Any], max_files: int) -> int:
    if not isinstance(state, dict):
        return 0
    files = state.get("files") if isinstance(state.get("files"), Mapping) else {}
    if len(files) <= max_files:
        return 0

    def recency(item: tuple[str, Any]) -> tuple[int, str, str]:
        path, value = item
        entry = value if isinstance(value, Mapping) else {}
        return (
            safe_int(entry.get("mtime_ns"), 0),
            str(entry.get("last_seen_at") or ""),
            str(path),
        )

    retained = sorted(files.items(), key=recency, reverse=True)[:max_files]
    state["files"] = {str(path): dict(entry) for path, entry in retained if isinstance(entry, Mapping)}
    return len(files) - len(state["files"])


def saved_text_scan_candidates(
    saved_policy: dict[str, Any],
    state: Mapping[str, Any],
    *,
    now_ts: float | None = None,
    progress: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_ts = time.time() if now_ts is None else float(now_ts)
    limits = saved_text_scan_limits(saved_policy)
    exclude_dirs = {str(item) for item in saved_policy.get("exclude_dir_names", []) if str(item).strip()}
    candidates: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    skip_counts: Counter[str] = Counter()
    seen_files = 0
    seen_entries = 0
    processed_directories = 0
    queue_deferred = 0
    stop_reason: str | None = None
    started = time.monotonic()
    roots = saved_text_scan_roots(saved_policy)
    state_files_pruned = _prune_state_files(state, limits["max_state_files"])
    pending, cycle = _cursor_queue(state, roots, limits["max_pending_directories"])
    root_strings = [str(root) for root in roots]

    def record_skip(item: dict[str, Any]) -> None:
        reason = str(item.get("reason") or "unknown")
        skip_counts[reason] += 1
        if len(skips) < max(0, limits["max_skip_records"] - 1):
            skips.append(item)

    def root_for(path: Path) -> str:
        for root in roots:
            try:
                path.relative_to(root)
                return str(root)
            except ValueError:
                continue
        return str(path)

    while pending and len(candidates) < limits["max_files_per_scan"]:
        if processed_directories >= limits["max_directories_per_scan"]:
            stop_reason = "directory_budget"
            break
        if seen_entries >= limits["max_entries_per_scan"]:
            stop_reason = "entry_budget"
            break
        if time.monotonic() - started >= limits["max_scan_seconds"]:
            stop_reason = "time_budget"
            break

        work = pending.popleft()
        directory = Path(str(work.get("path") or ""))
        after = str(work.get("after")) if work.get("after") else None
        processed_directories += 1
        if not directory.exists() or not directory.is_dir():
            reason = "root_missing" if str(directory) in root_strings else "directory_missing"
            record_skip({"path": str(directory), "reason": reason})
            continue

        last_processed = after
        directory_incomplete = False
        deferred_for_queue = False
        resume_found = after is None
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if not resume_found:
                        if entry.name == after:
                            resume_found = True
                        if time.monotonic() - started >= limits["max_scan_seconds"]:
                            stop_reason = "time_budget"
                            directory_incomplete = True
                            break
                        continue
                    if seen_entries >= limits["max_entries_per_scan"]:
                        stop_reason = "entry_budget"
                        directory_incomplete = True
                        break
                    if time.monotonic() - started >= limits["max_scan_seconds"]:
                        stop_reason = "time_budget"
                        directory_incomplete = True
                        break

                    previous_processed = last_processed
                    path = Path(entry.path)
                    seen_entries += 1
                    last_processed = entry.name
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError as exc:
                        record_skip({"path": str(path), "reason": f"stat_failed: {exc}"[:180]})
                        continue

                    if is_directory:
                        if entry.name in exclude_dirs:
                            record_skip({"path": str(path), "reason": "excluded_dir_name"})
                            continue
                        skip_reason, matches = _policy_path_matches(path, saved_policy)
                        if skip_reason:
                            record_skip({"path": str(path), "reason": skip_reason, "matches": matches})
                            continue
                        # Reserve one slot for this directory's continuation so
                        # a full queue defers children instead of dropping them.
                        if len(pending) >= limits["max_pending_directories"] - 1:
                            queue_deferred += 1
                            last_processed = previous_processed
                            directory_incomplete = True
                            deferred_for_queue = True
                            break
                        pending.append({"path": str(path), "after": None})
                        continue
                    if not is_file:
                        continue

                    seen_files += 1
                    skip_reason, matches = _policy_path_matches(path, saved_policy)
                    if skip_reason:
                        record_skip({"path": str(path), "reason": skip_reason, "matches": matches})
                        continue
                    if not typing_capture_contracts.saved_text_file_allowed(path, saved_policy):
                        continue
                    try:
                        stat = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        record_skip({"path": str(path), "reason": f"stat_failed: {exc}"[:180]})
                        continue
                    if not stat.st_mtime or current_ts - float(stat.st_mtime) > limits["changed_within_sec"]:
                        continue
                    if int(stat.st_size) > limits["max_file_bytes"]:
                        record_skip({"path": str(path), "reason": "too_large", "size_bytes": int(stat.st_size)})
                        continue
                    text, size, read_error = saved_text_decode(path, limits["max_file_bytes"])
                    if read_error:
                        record_skip({"path": str(path), "reason": read_error, "size_bytes": size})
                        continue
                    sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                    previous = _previous_file_state(state, path)
                    if previous.get("sha256") == sha:
                        continue
                    candidates.append({
                        "path": str(path),
                        "root": root_for(path),
                        "name": path.name,
                        "suffix": path.suffix.lower(),
                        "size_bytes": int(stat.st_size),
                        "mtime": dt.datetime.fromtimestamp(float(stat.st_mtime), dt.timezone.utc).isoformat(),
                        "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
                        "sha256": sha,
                        "text": text,
                    })
                    if len(candidates) >= limits["max_files_per_scan"]:
                        stop_reason = "candidate_budget"
                        directory_incomplete = True
                        break
        except OSError as exc:
            record_skip({"path": str(directory), "reason": f"walk_failed: {exc}"[:180]})
            continue

        if after and not resume_found and not directory_incomplete:
            record_skip({"path": str(directory), "reason": "cursor_marker_missing"})
            pending.append({"path": str(directory), "after": None})
            continue

        if directory_incomplete:
            cursor_item = {"path": str(directory), "after": last_processed}
            if deferred_for_queue:
                pending.append(cursor_item)
                continue
            pending.appendleft(cursor_item)
            break

    cycle_complete = not pending
    if queue_deferred:
        record_skip({"reason": "pending_directory_deferred", "count": queue_deferred})

    elapsed_ms = round((time.monotonic() - started) * 1000.0, 3)
    scan_summary = {
        "cycle": cycle,
        "cycle_complete": cycle_complete,
        "stop_reason": stop_reason or ("cycle_complete" if cycle_complete else "candidate_budget"),
        "elapsed_ms": elapsed_ms,
        "seen_entries": seen_entries,
        "seen_files": seen_files,
        "processed_directories": processed_directories,
        "pending_directories": len(pending),
        "queue_deferred": queue_deferred,
        "state_files_pruned": state_files_pruned,
        "skip_counts": dict(sorted(skip_counts.items())),
    }
    cursor_payload = {
        "version": 1,
        "cycle": cycle,
        "roots": root_strings,
        "pending_directories": list(pending)[: limits["max_pending_directories"]],
    }
    if isinstance(state, dict):
        state["scan_cursor"] = cursor_payload
    if progress is not None:
        progress.clear()
        progress.update({"summary": scan_summary, "cursor": cursor_payload})

    skips.append({"reason": "scan_summary", **scan_summary})
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
    data["files"] = saved_text_state_files(files)
    for path, entry in (file_updates or {}).items():
        data["files"][str(path)] = dict(entry)
    return data


def saved_text_state_files(files: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(path): dict(entry)
        for path, entry in files.items()
        if isinstance(entry, Mapping)
    }


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
    scan = next(
        ({key: value for key, value in item.items() if key != "reason"} for item in skips if item.get("reason") == "scan_summary"),
        {},
    )
    public_skips = [item for item in skips if item.get("reason") != "scan_summary"]
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
            "skips": len(public_skips),
            "state_error": state_error,
        },
        "events": events,
        "skips": public_skips[: saved_text_scan_limits(saved_policy)["max_skip_records"]],
        "scan": scan,
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
