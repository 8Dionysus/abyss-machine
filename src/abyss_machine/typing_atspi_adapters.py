from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping


AT_SPI_TEXT_EVENT_SOURCE = "atspi_text_changed_event"
FOCUSED_SNAPSHOT_SOURCE = "atspi_focused_text_snapshot"


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


def safe_string(value: Any, limit: int = 240) -> str:
    try:
        text = "" if value is None else str(value)
    except Exception:
        return "<unreadable>"
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def text_sha256(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()


def atspi_state_flags(obj: Any, pyatspi_module: Any) -> dict[str, bool]:
    flags = {
        "focused": False,
        "editable": False,
        "showing": False,
        "visible": False,
        "sensitive": False,
        "enabled": False,
        "single_line": False,
        "multi_line": False,
    }
    try:
        state = obj.getState()
    except Exception:
        return flags
    mapping = {
        "focused": "STATE_FOCUSED",
        "editable": "STATE_EDITABLE",
        "showing": "STATE_SHOWING",
        "visible": "STATE_VISIBLE",
        "sensitive": "STATE_SENSITIVE",
        "enabled": "STATE_ENABLED",
        "single_line": "STATE_SINGLE_LINE",
        "multi_line": "STATE_MULTI_LINE",
    }
    for key, attr in mapping.items():
        try:
            flags[key] = bool(state.contains(getattr(pyatspi_module, attr)))
        except Exception:
            flags[key] = False
    return flags


def atspi_text_payload(obj: Any, max_chars: int) -> tuple[str, int, int | None, str | None]:
    try:
        text_iface = obj.queryText()
    except Exception as exc:
        return "", 0, None, f"query_text_failed: {exc}"
    try:
        count = int(text_iface.characterCount)
    except Exception:
        count = 0
    if count <= 0:
        return "", 0, None, None
    try:
        caret = int(text_iface.caretOffset)
    except Exception:
        caret = None
    try:
        text = str(text_iface.getText(0, min(count, max_chars)) or "")
    except Exception as exc:
        return "", count, caret, f"read_text_failed: {exc}"
    return text, count, caret, None


def atspi_accessible_index_in_parent(obj: Any) -> int | None:
    for attr in ("getIndexInParent",):
        try:
            method = getattr(obj, attr)
        except Exception:
            method = None
        if callable(method):
            try:
                value = int(method())
                if value >= 0:
                    return value
            except Exception:
                pass
    try:
        value = int(getattr(obj, "indexInParent"))
        if value >= 0:
            return value
    except Exception:
        pass
    return None


def atspi_same_accessible(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    try:
        if left == right:
            return True
    except Exception:
        pass
    try:
        left_name = getattr(left, "name", None)
        right_name = getattr(right, "name", None)
        left_role = left.getRoleName()
        right_role = right.getRoleName()
        return bool(left_name == right_name and left_role == right_role and id(left) == id(right))
    except Exception:
        return False


def atspi_object_path(obj: Any, max_depth: int = 36) -> str | None:
    parts: list[str] = []
    target = obj
    try:
        app_obj = obj.getApplication()
    except Exception:
        app_obj = None
    for _ in range(max_depth):
        if target is None:
            break
        if app_obj is not None and atspi_same_accessible(target, app_obj):
            break
        try:
            parent = target.parent
        except Exception:
            break
        if parent is None:
            break
        index = atspi_accessible_index_in_parent(target)
        if index is None:
            break
        parts.append(str(index))
        target = parent
    if not parts:
        return "0"
    return "0." + ".".join(reversed(parts))


def atspi_document_attributes(obj: Any) -> dict[str, str]:
    values: dict[str, str] = {}
    source_path = atspi_object_path(obj)
    if source_path:
        values["atspi_path"] = source_path
    target = obj
    for _ in range(14):
        if target is None:
            break
        document = None
        try:
            document = target.queryDocument()
        except Exception:
            document = None
        if document is not None:
            for target_key, atspi_key in (
                ("url", "DocURL"),
                ("content_type", "MimeType"),
                ("document_title", "Title"),
            ):
                if values.get(target_key):
                    continue
                try:
                    value = document.getAttributeValue(atspi_key)
                except Exception:
                    value = None
                if value:
                    values[target_key] = safe_string(value, 320)
            try:
                attrs = document.getAttributes()
            except Exception:
                attrs = []
            if isinstance(attrs, (list, tuple)):
                for item in attrs:
                    text = str(item or "")
                    if ":" not in text:
                        continue
                    key, value = text.split(":", 1)
                    key = key.strip()
                    mapped = {"DocURL": "url", "MimeType": "content_type", "Title": "document_title"}.get(key)
                    if mapped and value and not values.get(mapped):
                        values[mapped] = safe_string(value, 320)
            document_path = atspi_object_path(target)
            if document_path and not values.get("document_path"):
                values["document_path"] = document_path
            try:
                if not values.get("document_role"):
                    values["document_role"] = safe_string(target.getRoleName(), 120)
            except Exception:
                pass
        try:
            target = target.parent
        except Exception:
            break
    return values


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def atspi_application_context(
    obj: Any,
    *,
    proc_root: Path = Path("/proc"),
    read_text: Callable[[Path], str | None] | None = None,
) -> dict[str, Any]:
    app_obj = None
    app_name = ""
    process_id: int | None = None
    toolkit_name = ""
    toolkit_version = ""
    try:
        app_obj = obj.getApplication()
    except Exception:
        app_obj = None
    if app_obj is not None:
        try:
            app_name = safe_string(app_obj.name, 160)
        except Exception:
            app_name = ""
        try:
            raw_pid = app_obj.get_process_id()
            process_id = int(raw_pid) if raw_pid is not None else None
        except Exception:
            process_id = None
        try:
            toolkit_name = safe_string(getattr(app_obj, "toolkitName", ""), 80)
        except Exception:
            toolkit_name = ""
        try:
            toolkit_version = safe_string(getattr(app_obj, "toolkitVersion", ""), 80)
        except Exception:
            toolkit_version = ""
    reader = read_text or _read_text
    if (not app_name or app_name == "-") and process_id:
        proc_comm = reader(proc_root / str(process_id) / "comm")
        if proc_comm:
            app_name = safe_string(proc_comm, 160)
        else:
            try:
                raw_cmdline = (proc_root / str(process_id) / "cmdline").read_bytes()
                first_arg = raw_cmdline.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
                if first_arg:
                    app_name = safe_string(Path(first_arg).name, 160)
            except Exception:
                pass
    return {
        "name": app_name,
        "process_id": process_id,
        "toolkit_name": toolkit_name,
        "toolkit_version": toolkit_version,
    }


def atspi_object_context(obj: Any, pyatspi_module: Any) -> dict[str, Any]:
    role = "<role_unreadable>"
    name = "<name_unreadable>"
    description = ""
    app = ""
    app_context = atspi_application_context(obj)
    window_title = ""
    document_attrs = atspi_document_attributes(obj)
    try:
        role = safe_string(obj.getRoleName(), 120)
    except Exception:
        pass
    try:
        name = safe_string(obj.name, 240)
    except Exception:
        pass
    try:
        description = safe_string(obj.description, 240)
    except Exception:
        pass
    app = str(app_context.get("name") or "")
    window_roles = {"frame", "window", "dialog", "alert", "terminal", "document frame"}
    parent = obj
    for _ in range(12):
        try:
            parent = parent.parent
        except Exception:
            break
        if parent is None:
            break
        try:
            parent_role = safe_string(parent.getRoleName(), 120).lower()
            parent_name = safe_string(parent.name, 240)
        except Exception:
            continue
        if parent_role in window_roles and parent_name:
            window_title = parent_name
            break
    return {
        "app": app,
        "window_title": window_title,
        "url": document_attrs.get("url", ""),
        "document_title": document_attrs.get("document_title", ""),
        "content_type": document_attrs.get("content_type", ""),
        "atspi_path": document_attrs.get("atspi_path", ""),
        "document_path": document_attrs.get("document_path", ""),
        "document_role": document_attrs.get("document_role", ""),
        "role": role,
        "name": name,
        "description": description,
        "app_process_id": app_context.get("process_id"),
        "app_toolkit_name": app_context.get("toolkit_name", ""),
        "app_toolkit_version": app_context.get("toolkit_version", ""),
        "states": atspi_state_flags(obj, pyatspi_module),
    }


def focused_snapshot_policy_shape(candidate: Mapping[str, Any]) -> dict[str, Any]:
    diagnostic_only = bool(candidate.get("diagnostic_only"))
    return {
        "raw_keylogging": False,
        "committed_text_only": True,
        "password_fields_captured": False,
        "global_keyboard_hook": False,
        "automatic_action": False,
        "metadata_only_on_sensitive_context": True,
        "requires_capture_gate_allow_text": True,
        "diagnostic_only": diagnostic_only,
        "text_capture_enabled": not diagnostic_only,
        "mode": "diagnostic" if diagnostic_only else "safe_text_routes",
        "primary_capture_by": None if diagnostic_only else AT_SPI_TEXT_EVENT_SOURCE,
        "superseded_for_capture_by": AT_SPI_TEXT_EVENT_SOURCE if diagnostic_only else None,
    }


def focused_snapshot_candidate_projection(candidate: Mapping[str, Any]) -> dict[str, Any]:
    path = str(candidate.get("path") or "")
    capture_gate = candidate.get("capture_gate") if isinstance(candidate.get("capture_gate"), Mapping) else {}
    gate_decision = str(capture_gate.get("decision") or candidate.get("capture_gate_decision") or "metadata_only")
    safe_route = str(candidate.get("safe_route") or "")
    return {
        "app": str(candidate.get("app") or ""),
        "window_title": str(candidate.get("window_title") or ""),
        "role": str(candidate.get("role") or ""),
        "path": path,
        "url": str(candidate.get("url") or ""),
        "document_title": str(candidate.get("document_title") or ""),
        "content_type": str(candidate.get("content_type") or ""),
        "atspi_path": str(candidate.get("atspi_path") or path),
        "document_path": str(candidate.get("document_path") or ""),
        "states": candidate.get("states") if isinstance(candidate.get("states"), Mapping) else {},
        "text_role": bool(candidate.get("text_role")),
        "sensitive_context": bool(candidate.get("sensitive_context")),
        "text_read_allowed": bool(candidate.get("text_read_allowed")),
        "diagnostic_only": bool(candidate.get("diagnostic_only")),
        "capture_gate_decision": gate_decision,
        "safe_route": safe_route or None,
        "text_length": candidate.get("text_length"),
        "caret_offset": candidate.get("caret_offset"),
        "sensitive_matches": candidate.get("sensitive_matches") if isinstance(candidate.get("sensitive_matches"), list) else [],
    }


def focused_snapshot_context(candidate: Mapping[str, Any]) -> str:
    projected = focused_snapshot_candidate_projection(candidate)
    states = projected["states"] if isinstance(projected["states"], Mapping) else {}
    return (
        f"focused_text role={projected['role']} path={projected['path']} editable={bool(states.get('editable'))} "
        f"focused={bool(states.get('focused'))} sensitive={bool(projected['sensitive_context'])} "
        f"name={str(candidate.get('name') or '')} url={projected['url']} "
        f"safe_route={projected['safe_route'] or 'none'}"
    )


def focused_snapshot_metadata(candidate: Mapping[str, Any]) -> dict[str, Any]:
    projected = focused_snapshot_candidate_projection(candidate)
    return {
        "atspi": {
            "role": projected["role"],
            "name": str(candidate.get("name") or ""),
            "url": projected["url"],
            "document_title": projected["document_title"],
            "content_type": projected["content_type"],
            "source_path": projected["atspi_path"],
            "document_path": projected["document_path"],
            "url_query_present": candidate.get("url_query_present"),
            "url_fragment_present": candidate.get("url_fragment_present"),
            "raw_url_omitted": candidate.get("raw_url_omitted") is not False,
            "safe_route": projected["safe_route"],
            "safe_route_allowed": bool(candidate.get("safe_route_allowed")),
            "browser_safe_url": bool(candidate.get("browser_safe_url")),
            "browser_context_inference": candidate.get("browser_context_inference")
            if isinstance(candidate.get("browser_context_inference"), Mapping)
            else None,
            "gate_decision": projected["capture_gate_decision"],
            "text_read": bool(projected["text_read_allowed"]),
        }
    }


def focused_snapshot_unavailable_document(
    candidate: Any,
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_focused_snapshot_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": "candidate_unavailable",
        "source_adapter": FOCUSED_SNAPSHOT_SOURCE,
        "error": candidate.get("error") if isinstance(candidate, Mapping) else "candidate missing",
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }


def focused_snapshot_status_document(
    candidate: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    status: str,
    ok: bool = True,
    event: Mapping[str, Any] | None = None,
    non_claims: list[str] | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema": f"{schema_prefix}_typing_focused_snapshot_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(ok),
        "status": status,
        "source_adapter": FOCUSED_SNAPSHOT_SOURCE,
        "candidate": focused_snapshot_candidate_projection(candidate),
        "policy": {**focused_snapshot_policy_shape(candidate), "duplicate_gate": True},
    }
    if event is not None:
        document["event"] = dict(event)
    if non_claims:
        document["non_claims"] = non_claims
    return document


def focused_snapshot_ingest_plan(
    candidate: Any,
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    if not isinstance(candidate, Mapping) or not candidate.get("ok"):
        return {
            "action": "store",
            "document": focused_snapshot_unavailable_document(
                candidate,
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ),
        }
    projected = focused_snapshot_candidate_projection(candidate)
    sensitive = bool(projected["sensitive_context"])
    text_role = bool(projected["text_role"])
    text_read_allowed = bool(projected["text_read_allowed"])
    diagnostic_only = bool(projected["diagnostic_only"])
    gate_decision = str(projected["capture_gate_decision"] or "metadata_only")
    if not text_role and not sensitive:
        return {
            "action": "store",
            "document": focused_snapshot_status_document(
                candidate,
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
                status="skipped_non_text_focus",
                non_claims=[
                    "Focused snapshot reads only focused text-capable accessibility nodes.",
                    "Focused non-text windows are skipped instead of being persisted as empty text.",
                ],
            ),
        }
    if diagnostic_only:
        return {
            "action": "store",
            "document": focused_snapshot_status_document(
                candidate,
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
                status="diagnostic_only",
                non_claims=[
                    "Focused snapshot is diagnostic-only under this policy and does not persist focused text.",
                    "Live committed accessibility text capture is handled by atspi_text_changed_event.",
                ],
            ),
        }
    metadata = focused_snapshot_metadata(candidate)
    context = focused_snapshot_context(candidate)
    if not text_read_allowed:
        metadata_reason = (
            "focused_sensitive_context"
            if sensitive
            else (f"capture_gate:{gate_decision}" if gate_decision != "allow_text" else "focused_safe_route_not_allowed")
        )
        return {
            "action": "ingest",
            "result_status": "metadata_only_or_skipped_before_text_read",
            "candidate": dict(candidate),
            "ingest": {
                "text": "",
                "source": FOCUSED_SNAPSHOT_SOURCE,
                "app": projected["app"],
                "window_title": projected["window_title"],
                "context": context,
                "url": projected["url"],
                "skip_duplicate": True,
                "force_metadata_only_reason": metadata_reason,
                "metadata": metadata,
                "include_text_in_context_probe": False,
            },
            "non_claims": [
                "Focused snapshot did not read focused text unless capture-gate and a safe text route allowed it.",
                "Denied or sensitive focused contexts are persisted as bounded metadata only or skipped.",
            ],
        }
    text = str(candidate.get("text") or "")
    if not text:
        return {
            "action": "store",
            "document": focused_snapshot_status_document(
                candidate,
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
                status="skipped_empty_focused_text",
            ),
        }
    return {
        "action": "ingest",
        "result_status": None,
        "candidate": dict(candidate),
        "ingest": {
            "text": text,
            "source": FOCUSED_SNAPSHOT_SOURCE,
            "app": projected["app"],
            "window_title": projected["window_title"],
            "context": context,
            "url": projected["url"],
            "skip_duplicate": True,
            "force_metadata_only_reason": "focused_sensitive_context" if sensitive else None,
            "metadata": metadata,
            "include_text_in_context_probe": False,
        },
        "non_claims": [
            "Focused snapshot reads the accessibility tree; it is not a global keyboard hook.",
            "Sensitive focused roles are not text-read; uncertain focused contexts are stored as metadata only or skipped.",
        ],
    }


def focused_snapshot_document_from_event(
    plan: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    candidate = plan.get("candidate") if isinstance(plan.get("candidate"), Mapping) else {}
    result_status = plan.get("result_status")
    status = str(result_status or event.get("status") or "ingested")
    return focused_snapshot_status_document(
        candidate,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        status=status,
        ok=bool(event.get("ok")),
        event=event,
        non_claims=plan.get("non_claims") if isinstance(plan.get("non_claims"), list) else None,
    )


def atspi_text_event_context(context_data: Mapping[str, Any], *, event_type: str, url: str | None = None) -> str:
    states = context_data.get("states") if isinstance(context_data.get("states"), Mapping) else {}
    return (
        f"atspi_text_event type={event_type} role={str(context_data.get('role') or '')} "
        f"name={str(context_data.get('name') or '')} editable={bool(states.get('editable'))} "
        f"focused={bool(states.get('focused'))} showing={bool(states.get('showing'))} "
        f"visible={bool(states.get('visible'))} enabled={bool(states.get('enabled'))} "
        f"sensitive={bool(states.get('sensitive'))} url={url if url is not None else str(context_data.get('url') or '')}"
    )


def atspi_browser_context_summary(browser_context_inference: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(browser_context_inference, Mapping) or not browser_context_inference:
        return None
    return {key: value for key, value in browser_context_inference.items() if key not in {"url", "title"}}


def atspi_text_event_metadata(
    context_data: Mapping[str, Any],
    *,
    event_type: str,
    url: str,
    document_title: str,
    content_type: str,
    source_atspi_path: str,
    document_atspi_path: str,
    gate_decision: str | None = None,
    text_read: bool,
    caret_offset: int | None = None,
    controlled_sensitive_override: Mapping[str, Any] | None = None,
    browser_context_inference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    states = context_data.get("states") if isinstance(context_data.get("states"), Mapping) else {}
    override = (
        dict(controlled_sensitive_override)
        if isinstance(controlled_sensitive_override, Mapping) and controlled_sensitive_override.get("allowed")
        else None
    )
    payload: dict[str, Any] = {
        "event_type": event_type,
        "role": str(context_data.get("role") or ""),
        "name": str(context_data.get("name") or ""),
        "url": url,
        "document_title": document_title,
        "content_type": content_type,
        "app_process_id": context_data.get("app_process_id"),
        "app_toolkit_name": str(context_data.get("app_toolkit_name") or ""),
        "app_toolkit_version": str(context_data.get("app_toolkit_version") or ""),
        "source_path": source_atspi_path,
        "document_path": document_atspi_path,
        "states": states,
        "sensitive_state_override": override,
        "browser_context_inference": atspi_browser_context_summary(browser_context_inference),
        "text_read": bool(text_read),
    }
    if gate_decision is not None:
        payload["gate_decision"] = gate_decision
    if caret_offset is not None:
        payload["caret_offset"] = caret_offset
    return {"atspi": payload}


def atspi_text_event_sample_base(
    context_data: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    event_type: str,
    event_detail1: Any,
    event_detail2: Any,
    event_any_data: Any,
    url: str,
    document_title: str,
    content_type: str,
    source_atspi_path: str,
    document_atspi_path: str,
    browser_context_inference: Mapping[str, Any] | None,
    text_role: bool,
    sensitive_context: bool,
    sensitive_matches: list[dict[str, Any]],
    controlled_sensitive_override: Mapping[str, Any] | None,
    capture_gate: Mapping[str, Any],
) -> dict[str, Any]:
    override = (
        dict(controlled_sensitive_override)
        if isinstance(controlled_sensitive_override, Mapping) and controlled_sensitive_override.get("allowed")
        else None
    )
    return {
        "schema": f"{schema_prefix}_typing_atspi_text_event_sample_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "source_adapter": AT_SPI_TEXT_EVENT_SOURCE,
        "event_type": event_type,
        "detail1": event_detail1,
        "detail2": event_detail2,
        "any_data_type": type(event_any_data).__name__,
        "app": str(context_data.get("app") or ""),
        "app_process_id": context_data.get("app_process_id"),
        "app_toolkit_name": str(context_data.get("app_toolkit_name") or ""),
        "app_toolkit_version": str(context_data.get("app_toolkit_version") or ""),
        "window_title": str(context_data.get("window_title") or ""),
        "url": url,
        "document_title": document_title,
        "content_type": content_type,
        "role": str(context_data.get("role") or ""),
        "name": str(context_data.get("name") or ""),
        "atspi_path": source_atspi_path,
        "document_path": document_atspi_path,
        "browser_context_inference": atspi_browser_context_summary(browser_context_inference),
        "states": context_data.get("states") if isinstance(context_data.get("states"), Mapping) else {},
        "text_role": bool(text_role),
        "sensitive_context": bool(sensitive_context),
        "sensitive_matches": sensitive_matches,
        "sensitive_state_override": override,
        "capture_gate": dict(capture_gate),
        "typing_event": None,
    }


def atspi_context_key(context_data: Mapping[str, Any], *, source: str = AT_SPI_TEXT_EVENT_SOURCE) -> str:
    payload = {
        "source": source,
        "app": str(context_data.get("app") or ""),
        "window": str(context_data.get("window_title") or ""),
        "role": str(context_data.get("role") or ""),
        "name": str(context_data.get("name") or ""),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8", errors="replace")).hexdigest()


def atspi_text_event_debounce_status(
    previous: Mapping[str, Any] | None,
    *,
    now_ts: float,
    text_hash: str,
    text_length: int,
    min_interval_sec: float,
    capture_length_change_updates: bool,
) -> str | None:
    previous_data = previous if isinstance(previous, Mapping) else {}
    previous_length = safe_int(previous_data.get("text_length"), -1)
    capture_length_change = bool(capture_length_change_updates and previous_length >= 0 and text_length != previous_length)
    if previous_data.get("sha256") == text_hash:
        return "duplicate_snapshot_skipped"
    if previous_data.get("ts") and now_ts - float(previous_data.get("ts") or 0) < min_interval_sec and not capture_length_change:
        return "debounced"
    return None


def atspi_typing_event_summary(event: Mapping[str, Any], *, include_text: bool = False) -> dict[str, Any]:
    summary = {
        "event_id": event.get("event_id"),
        "status": event.get("status"),
        "capture_gate_decision": nested_get(event, ["capture_gate", "decision"]),
    }
    if include_text:
        summary.update(
            {
                "text_length": nested_get(event, ["text", "text_length"]),
                "text_chars_stored": nested_get(event, ["text", "text_chars_stored"]),
                "duplicate": event.get("duplicate"),
            }
        )
    return summary


def generic_gui_selftest_run_id(generated_at: str, pid: int) -> str:
    digits = "".join(ch for ch in str(generated_at or "") if ch.isdigit())[:14]
    return digits + str(pid)[-5:]


def generic_gui_selftest_plan(run_id: str) -> dict[str, Any]:
    probe_text = f"abyss generic gui committed text {run_id}"
    sensitive_text = f"abyss generic gui sensitive text {run_id}"
    source = AT_SPI_TEXT_EVENT_SOURCE
    safe_metadata = {
        "atspi": {
            "event_type": "selftest",
            "role": "entry",
            "name": "plain-text",
            "states": {
                "editable": True,
                "focused": True,
                "visible": True,
                "showing": True,
                "enabled": True,
                "sensitive": False,
            },
            "text_read": True,
        }
    }
    sensitive_metadata = {
        "atspi": {
            "event_type": "selftest",
            "role": "entry",
            "name": "password",
            "states": {
                "editable": True,
                "focused": True,
                "visible": True,
                "showing": True,
                "enabled": True,
                "sensitive": True,
            },
            "text_read": False,
        }
    }
    return {
        "source_adapter": source,
        "probe_text": probe_text,
        "probe_hash": text_sha256(probe_text),
        "sensitive_text": sensitive_text,
        "safe_ingest": {
            "text": probe_text,
            "source": source,
            "app": "Plainwriter",
            "window_title": "generic-gui-selftest",
            "context": (
                "atspi_text_event role=entry editable=True focused=True visible=True "
                "enabled=True sensitive=False name=plain-text generic_gui_selftest=true"
            ),
            "skip_duplicate": True,
            "metadata": safe_metadata,
        },
        "sensitive_ingest": {
            "text": sensitive_text,
            "source": source,
            "app": "Plainwriter",
            "window_title": "Password",
            "context": (
                "atspi_text_event role=entry editable=True focused=True visible=True "
                "enabled=True sensitive=True name=password generic_gui_selftest=true"
            ),
            "skip_duplicate": True,
            "metadata": sensitive_metadata,
        },
    }


def generic_gui_selftest_document(
    *,
    plan: Mapping[str, Any],
    ingest: Mapping[str, Any],
    sensitive: Mapping[str, Any],
    event: Mapping[str, Any] | None,
    parse_errors: list[dict[str, Any]],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    event_data = event if isinstance(event, Mapping) else {}
    probe_text = str(plan.get("probe_text") or "")
    probe_hash = str(plan.get("probe_hash") or "")
    event_ok = (
        isinstance(event, Mapping)
        and event.get("status") == "captured"
        and event.get("source_adapter") == AT_SPI_TEXT_EVENT_SOURCE
        and event.get("capture_gate_decision") == "allow_text"
        and event.get("capture_gate_confidence") == "atspi_generic_editable_text_allowed"
        and event.get("text_sha256") == probe_hash
        and event.get("text_chars_stored") == len(probe_text)
        and nested_get(event, ["recipient", "kind"]) == "focused_application"
    )
    sensitive_ok = bool(
        sensitive.get("ok")
        and sensitive.get("status") == "metadata_only"
        and nested_get(sensitive, ["capture_gate", "decision"]) == "metadata_only"
        and safe_int(nested_get(sensitive, ["text", "text_chars_stored"]), 0) == 0
    )
    ok = bool(ingest.get("ok") and event_ok and sensitive_ok and not parse_errors)
    return {
        "schema": f"{schema_prefix}_typing_generic_gui_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "source_adapter": AT_SPI_TEXT_EVENT_SOURCE,
        "probe": {
            "text_sha256": probe_hash,
            "text_length": len(probe_text),
            "text_omitted": True,
            "app": "Plainwriter",
            "role": "entry",
        },
        "ingest": {
            "ok": ingest.get("ok"),
            "event_id": ingest.get("event_id"),
            "status": ingest.get("status"),
            "source_adapter": ingest.get("source_adapter"),
            "capture_gate_decision": nested_get(ingest, ["capture_gate", "decision"]),
            "capture_gate_confidence": nested_get(ingest, ["capture_gate", "confidence"]),
            "text_length": nested_get(ingest, ["text", "text_length"]),
            "text_chars_stored": nested_get(ingest, ["text", "text_chars_stored"]),
            "recipient": nested_get(ingest, ["causal_context", "recipient"]),
            "where": nested_get(ingest, ["causal_context", "where"]),
            "task": nested_get(ingest, ["causal_context", "task"]),
        },
        "event": dict(event_data) if event_data else None,
        "sensitive_probe": {
            "ok": sensitive.get("ok"),
            "event_id": sensitive.get("event_id"),
            "status": sensitive.get("status"),
            "capture_gate_decision": nested_get(sensitive, ["capture_gate", "decision"]),
            "capture_gate_confidence": nested_get(sensitive, ["capture_gate", "confidence"]),
            "text_length": nested_get(sensitive, ["text", "text_length"]),
            "text_chars_stored": nested_get(sensitive, ["text", "text_chars_stored"]),
            "metadata_only_reason": nested_get(sensitive, ["text", "metadata_only_reason"]),
        },
        "parse_errors": parse_errors[:20],
        "policy": {
            "raw_keylogging": False,
            "committed_accessibility_text_only": True,
            "requires_editable_text_role": True,
            "requires_capture_gate_allow_text": True,
            "password_fields_captured": False,
            "automatic_action": False,
            "network_access": False,
        },
        "non_claims": [
            "This selftest proves the generic non-browser AT-SPI committed-text ingest and capture-gate route.",
            "It does not install a keyboard hook and does not prove every toolkit emits AT-SPI text-change events.",
            "Sensitive/password-shaped generic text remains metadata-only.",
        ],
    }
