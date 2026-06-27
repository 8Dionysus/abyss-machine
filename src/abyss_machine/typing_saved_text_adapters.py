from __future__ import annotations

import datetime as dt
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Mapping

from . import typing_capture_contracts


SAVED_TEXT_SOURCE = "saved_text_snapshot"


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
