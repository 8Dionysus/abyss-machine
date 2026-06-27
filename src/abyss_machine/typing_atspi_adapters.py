from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping
import warnings


AT_SPI_TEXT_EVENT_SOURCE = "atspi_text_changed_event"
FOCUSED_SNAPSHOT_SOURCE = "atspi_focused_text_snapshot"

AtspiEventHandler = Callable[[Any, Any, dict[str, dict[str, Any]], bool], dict[str, Any]]
StoreLatestHistory = Callable[[dict[str, Any], bool], dict[str, Any]]
WriteLatestOnly = Callable[[dict[str, Any]], list[dict[str, Any]]]
AppendCompactHistory = Callable[[dict[str, Any], dict[str, Any] | None, str, str | None], dict[str, Any] | None]
FocusedCandidateBuilder = Callable[[Any, Any, dict[str, Any]], dict[str, Any] | None]


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


def import_pyatspi_module() -> tuple[Any | None, str | None]:
    try:
        import pyatspi  # type: ignore
    except Exception as exc:
        return None, f"pyatspi_unavailable: {exc}"
    return pyatspi, None


def import_gi_atspi_module() -> tuple[Any | None, str | None]:
    try:
        import gi  # type: ignore

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi  # type: ignore
    except Exception as exc:
        return None, f"AT-SPI import failed: {exc}"
    return Atspi, None


def load_pyatspi_desktop(
    *,
    timeout_ms: int | None = None,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
) -> tuple[Any | None, Any | None, dict[str, Any] | None]:
    pyatspi = pyatspi_module
    if pyatspi is None:
        pyatspi, import_error = load_pyatspi()
        if import_error or pyatspi is None:
            return None, None, {"status": "pyatspi_unavailable", "error": import_error or "pyatspi_unavailable"}
    if timeout_ms is not None:
        try:
            if hasattr(pyatspi, "setTimeout"):
                pyatspi.setTimeout(int(timeout_ms))
        except Exception:
            pass
    try:
        desktop = pyatspi.Registry.getDesktop(0)
    except Exception as exc:
        return pyatspi, None, {"status": "desktop_unreadable", "error": f"desktop_unreadable: {exc}"}
    return pyatspi, desktop, None


def atspi_text_event_types(events_policy: Mapping[str, Any]) -> list[str]:
    event_types = [str(item) for item in events_policy.get("event_types", []) if str(item).strip()]
    return event_types or ["object:text-changed:insert", "object:text-changed:delete"]


def atspi_text_events_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    seconds: float | None,
    forever: bool,
    source: str = AT_SPI_TEXT_EVENT_SOURCE,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_atspi_text_events_v1",
        "version": version,
        "generated_at": generated_at,
        "started_at": generated_at,
        "heartbeat_at": generated_at,
        "last_event_at": None,
        "ok": False,
        "status": "starting",
        "source_adapter": source,
        "read_only": True,
        "raw_keylogging": False,
        "password_fields_captured": False,
        "forever": bool(forever),
        "seconds": None if forever else seconds,
        "summary": {
            "events_seen": 0,
            "captured": 0,
            "metadata_only_or_skipped": 0,
            "debounced": 0,
            "errors": 0,
        },
        "samples": [],
        "errors": [],
        "policy": {
            "committed_text_only": True,
            "capture_gate_before_text_read": True,
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }


def atspi_text_events_disabled_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    source: str = AT_SPI_TEXT_EVENT_SOURCE,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_atspi_text_events_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "status": "disabled",
        "source_adapter": source,
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
    }


def run_atspi_text_events_listener(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    events_policy: Mapping[str, Any],
    seconds: float | None,
    forever: bool,
    write_latest: bool,
    handle_event: AtspiEventHandler,
    store_latest_history: StoreLatestHistory,
    write_latest_only: WriteLatestOnly,
    append_compact_history: AppendCompactHistory,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
    now_iso: Callable[[], str] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    timer_factory: Callable[[float, Callable[[], None]], Any] = threading.Timer,
    thread_factory: Callable[..., Any] = threading.Thread,
    event_factory: Callable[[], Any] = threading.Event,
    lock_factory: Callable[[], Any] = threading.RLock,
) -> dict[str, Any]:
    now = now_iso or (lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    source = AT_SPI_TEXT_EVENT_SOURCE
    data = atspi_text_events_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        seconds=seconds,
        forever=forever,
        source=source,
    )
    pyatspi = pyatspi_module
    if pyatspi is None:
        pyatspi, import_error = load_pyatspi()
        if import_error or pyatspi is None:
            data["status"] = "pyatspi_unavailable"
            data["error"] = import_error or "pyatspi_unavailable"
            return store_latest_history(data, write_latest)

    last_by_context: dict[str, dict[str, Any]] = {}
    event_types = atspi_text_event_types(events_policy)
    max_events = 0 if forever else max(1, min(safe_int(events_policy.get("max_events_per_run"), 400), 5000))
    started = monotonic()
    heartbeat_interval = max(10.0, min(float(events_policy.get("heartbeat_interval_sec") or 30.0), 300.0))
    history_checkpoint_events = max(100, min(safe_int(events_policy.get("history_checkpoint_events"), 1000), 100000))
    data_lock = lock_factory()
    stop_heartbeat = event_factory()

    def refresh_latest(status: str, append_history: bool = True) -> None:
        with data_lock:
            stamp = now()
            data["generated_at"] = stamp
            data["heartbeat_at"] = stamp
            data["ok"] = True
            data["status"] = status
            data["elapsed_sec"] = round(monotonic() - started, 3)
            data["heartbeat_interval_sec"] = heartbeat_interval if forever else None
            if write_latest:
                if append_history:
                    store_latest_history(data, True)
                else:
                    errors = write_latest_only(data)
                    if errors:
                        data["ok"] = False
                        data["write_errors"] = errors

    def heartbeat_loop() -> None:
        while not stop_heartbeat.wait(heartbeat_interval):
            refresh_latest("running", append_history=False)

    def on_event(event: Any) -> None:
        if max_events and int(nested_get(data, ["summary", "events_seen"]) or 0) >= max_events:
            try:
                pyatspi.Registry.stop()
            except Exception:
                pass
            return
        try:
            sample = handle_event(event, pyatspi, last_by_context, write_latest)
        except Exception as exc:
            compact_history_error = None
            with data_lock:
                data["last_event_at"] = now()
                data["summary"]["errors"] = int(data["summary"].get("errors") or 0) + 1
                errors_seen = int(data["summary"].get("errors") or 0)
                events_seen = int(data["summary"].get("events_seen") or 0)
                if len(data["errors"]) < 20:
                    data["errors"].append({"error": repr(exc)[:240]})
                append_history = errors_seen <= 3 or errors_seen % 100 == 0 or (
                    events_seen > 0 and events_seen % history_checkpoint_events == 0
                )
                error_record_text = repr(exc)[:500]
            if write_latest:
                compact_history_error = append_compact_history(data, None, "running_with_errors", error_record_text)
            if compact_history_error:
                with data_lock:
                    data["ok"] = False
                    write_errors = data.get("write_errors") if isinstance(data.get("write_errors"), list) else []
                    if len(write_errors) < 20:
                        write_errors.append(compact_history_error)
                    data["write_errors"] = write_errors
            refresh_latest("running_with_errors", append_history=append_history)
            return

        compact_history_error = None
        with data_lock:
            data["last_event_at"] = sample.get("generated_at") or now()
            data["summary"]["events_seen"] = int(data["summary"].get("events_seen") or 0) + 1
            events_seen = int(data["summary"].get("events_seen") or 0)
            status = str(sample.get("status") or "unknown")
            if status == "captured":
                data["summary"]["captured"] = int(data["summary"].get("captured") or 0) + 1
            elif status == "debounced":
                data["summary"]["debounced"] = int(data["summary"].get("debounced") or 0) + 1
            else:
                data["summary"]["metadata_only_or_skipped"] = int(data["summary"].get("metadata_only_or_skipped") or 0) + 1
            typing_event = sample.get("typing_event") if isinstance(sample.get("typing_event"), dict) else {}
            if typing_event.get("event_id"):
                data["last_typing_event_id"] = typing_event.get("event_id")
                data["last_typing_event_status"] = typing_event.get("status")
            samples = data.get("samples") if isinstance(data.get("samples"), list) else []
            if len(samples) < 40 and status != "debounced":
                samples.append(sample)
                data["samples"] = samples
            append_history = events_seen == 1 or events_seen % history_checkpoint_events == 0
        if write_latest:
            compact_history_error = append_compact_history(data, sample, "running", None)
        if compact_history_error:
            with data_lock:
                data["ok"] = False
                write_errors = data.get("write_errors") if isinstance(data.get("write_errors"), list) else []
                if len(write_errors) < 20:
                    write_errors.append(compact_history_error)
                data["write_errors"] = write_errors
        refresh_latest("running", append_history=append_history)

    timer: Any | None = None
    heartbeat_thread: Any | None = None
    try:
        for event_type in event_types:
            pyatspi.Registry.registerEventListener(on_event, event_type)
        refresh_latest("running")
        if forever:
            heartbeat_thread = thread_factory(target=heartbeat_loop, daemon=True)
            heartbeat_thread.start()
        if not forever:
            sample_seconds = max(1.0, min(float(seconds or 5.0), 120.0))
            timer = timer_factory(sample_seconds, pyatspi.Registry.stop)
            timer.daemon = True
            timer.start()
        try:
            pyatspi.Registry.start()
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=1.0)
            if timer is not None:
                timer.cancel()
    except KeyboardInterrupt:
        data["status"] = "interrupted"
    except Exception as exc:
        data["ok"] = False
        data["status"] = "listener_failed"
        data["error"] = f"atspi_text_event_listener_failed: {exc}"
        return store_latest_history(data, write_latest)

    data["ok"] = True
    data["status"] = "stopped" if forever else "sample_complete"
    data["generated_at"] = now()
    data["heartbeat_at"] = data["generated_at"]
    data["elapsed_sec"] = round(monotonic() - started, 3)
    data["non_claims"] = [
        "AT-SPI text events are accessibility committed-text events, not raw key events.",
        "Capture-gate runs before text read; denied contexts are skipped or metadata-only.",
        "Browser contexts require a safe URL; generic app text requires focused/visible editable text-role evidence.",
    ]
    return store_latest_history(data, write_latest)


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


def atspi_children(obj: Any, errors: list[dict[str, Any]] | None = None, *, max_errors: int = 10) -> list[Any]:
    try:
        return list(obj)
    except Exception as exc:
        if errors is not None and len(errors) < max_errors:
            errors.append({"kind": "children_unreadable", "error": str(exc)[:160]})
        return []


def atspi_role_name(obj: Any, limit: int = 120) -> str:
    try:
        return safe_string(obj.getRoleName(), limit)
    except Exception:
        return "<role_unreadable>"


def atspi_node_name(obj: Any, limit: int = 240) -> str:
    try:
        return safe_string(obj.name, limit)
    except Exception:
        return "<name_unreadable>"


def atspi_node_description(obj: Any, limit: int = 240) -> str:
    try:
        return safe_string(obj.description, limit)
    except Exception:
        return ""


def focus_accessible_with_pyatspi(
    obj: Any,
    pyatspi_module: Any,
    *,
    sleep: Callable[[float], None] = time.sleep,
    action_names: set[str] | None = None,
    sleep_sec: float = 0.25,
) -> dict[str, Any]:
    result: dict[str, Any] = {"component_grab_focus": None, "actions": []}
    allowed_actions = action_names or {"focus", "click", "press"}
    try:
        component = obj.queryComponent()
        try:
            result["component_grab_focus"] = bool(component.grabFocus())
        except Exception as exc:
            result["component_grab_focus_error"] = str(exc)[:180]
    except Exception as exc:
        result["component_error"] = str(exc)[:180]
    try:
        action = obj.queryAction()
        action_count = int(getattr(action, "nActions", 0))
        for action_index in range(min(action_count, 8)):
            try:
                action_name = str(action.getName(action_index) or "").lower()
            except Exception:
                action_name = ""
            if action_name not in allowed_actions:
                continue
            try:
                action_ok = bool(action.doAction(action_index))
            except Exception as exc:
                result["actions"].append({"name": action_name, "ok": False, "error": str(exc)[:160]})
                continue
            result["actions"].append({"name": action_name, "ok": action_ok})
    except Exception:
        pass
    sleep(sleep_sec)
    result["states_after"] = atspi_state_flags(obj, pyatspi_module)
    return result


def parse_atspi_path(source_path: str) -> tuple[list[int], dict[str, Any] | None]:
    path_parts: list[int] = []
    for item in str(source_path or "").split("."):
        if item == "":
            continue
        try:
            path_parts.append(int(item))
        except ValueError:
            return [], {"status": "bad_path", "error": f"bad path component: {item}"}
    if not path_parts:
        return [], {"status": "missing_path"}
    return path_parts, None


def atspi_focused_candidate_walk(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    max_nodes: int,
    max_depth: int,
    timeout_sec: float,
    build_candidate: FocusedCandidateBuilder,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_typing_atspi_focused_candidate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "source_adapter": FOCUSED_SNAPSHOT_SOURCE,
        "read_only": True,
        "raw_keylogging": False,
        "password_fields_captured": False,
        "nodes_seen": 0,
        "errors": [],
    }
    timeout = max(1.0, min(float(timeout_sec or 3.0), 10.0))
    timeout_ms = int(timeout * 1000 / 3)
    pyatspi, desktop, load_error = load_pyatspi_desktop(
        timeout_ms=timeout_ms,
        pyatspi_module=pyatspi_module,
        load_pyatspi=load_pyatspi,
    )
    if load_error is not None or pyatspi is None or desktop is None:
        data["error"] = str((load_error or {}).get("error") or "pyatspi_unavailable")
        return data
    deadline = monotonic() + timeout
    focused: list[dict[str, Any]] = []
    window_roles = {"frame", "window", "dialog", "alert", "terminal", "document frame"}

    def app_name_for(obj: Any, fallback: str) -> str:
        app_context = atspi_application_context(obj)
        return str(app_context.get("name") or fallback)

    def walk(obj: Any, path: str, app_name: str, window_title: str, depth: int) -> None:
        if len(focused) >= 8 or data["nodes_seen"] >= max_nodes or depth > max_depth or monotonic() > deadline:
            return
        data["nodes_seen"] += 1
        role = atspi_role_name(obj, 120)
        name = atspi_node_name(obj, 240)
        desc = atspi_node_description(obj, 240)
        states = atspi_state_flags(obj, pyatspi)
        current_window = name if role.lower() in window_roles and name else window_title
        current_app = app_name_for(obj, app_name)
        if states.get("focused"):
            document_attrs = atspi_document_attributes(obj)
            snapshot = {
                "app": current_app,
                "window_title": current_window,
                "role": role,
                "name": name,
                "description": desc,
                "path": path,
                "states": states,
                "document_attrs": document_attrs,
            }
            candidate = build_candidate(obj, pyatspi, snapshot)
            if isinstance(candidate, dict):
                focused.append(candidate)
                if candidate.get("text_role") or candidate.get("sensitive_context"):
                    return
            if role.lower() in window_roles:
                return
        for child_index, child in enumerate(atspi_children(obj, data["errors"])[:120]):
            walk(child, f"{path}/{child_index}", current_app, current_window, depth + 1)

    try:
        apps = atspi_children(desktop, data["errors"])
        prioritized_apps: list[tuple[int, int, Any, str]] = []
        for app_index, app in enumerate(apps[:80]):
            app_name = atspi_node_name(app, 240)
            app_lower = app_name.lower()
            priority = 4
            if any(token in app_lower for token in ("firefox", "chrome", "chromium")):
                priority = 0
            elif any(token in app_lower for token in ("code", "codium", "terminal", "kitty", "wezterm")):
                priority = 1
            elif "gnome-shell" in app_lower or app_lower == "main stage":
                priority = 9
            prioritized_apps.append((priority, app_index, app, app_name))
        for _priority, app_index, app, app_name in sorted(prioritized_apps, key=lambda item: (item[0], item[1])):
            if monotonic() > deadline or data["nodes_seen"] >= max_nodes:
                break
            walk(app, str(app_index), app_name, "", 0)
            if any(item.get("text_role") or item.get("sensitive_context") for item in focused):
                break
    except Exception as exc:
        data["error"] = f"focused_walk_failed: {exc}"
        return data
    data["candidates"] = focused
    return data


def atspi_focus_metadata_by_path(
    source_path: str,
    url: str,
    *,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "not_found",
        "source_path": source_path,
        "url": url,
        "attempts": [],
        "errors": [],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "accessibility_focus_action_only": True,
            "text_read": False,
        },
    }
    path_parts, path_error = parse_atspi_path(source_path)
    if path_error:
        data.update(path_error)
        return data
    relative_parts = path_parts[1:] if path_parts and path_parts[0] == 0 else path_parts
    pyatspi, desktop, load_error = load_pyatspi_desktop(pyatspi_module=pyatspi_module, load_pyatspi=load_pyatspi)
    if load_error is not None or pyatspi is None or desktop is None:
        data.update(load_error or {"status": "pyatspi_unavailable", "error": "pyatspi_unavailable"})
        return data
    for app_index, app in enumerate(atspi_children(desktop, data["errors"])[:80]):
        obj = app
        traversed = []
        ok_path = True
        for part in relative_parts:
            kids = atspi_children(obj, data["errors"])
            if part < 0 or part >= len(kids):
                ok_path = False
                break
            obj = kids[part]
            traversed.append(part)
        if not ok_path:
            continue
        attrs = atspi_document_attributes(obj)
        document_url = str(attrs.get("url") or "")
        app_context = atspi_application_context(obj)
        states_before = atspi_state_flags(obj, pyatspi)
        url_matches_target = document_url == url
        attempt = {
            "app_index": app_index,
            "app": app_context.get("name"),
            "traversed": traversed,
            "role": atspi_role_name(obj, 120),
            "name": atspi_node_name(obj, 180),
            "description": atspi_node_description(obj, 240),
            "url": document_url if url_matches_target else None,
            "url_present": bool(document_url),
            "url_matches_target": url_matches_target,
            "raw_url_omitted": not url_matches_target,
            "document_title": attrs.get("document_title") if url_matches_target else None,
            "content_type": attrs.get("content_type") if url_matches_target else None,
            "document_path": attrs.get("document_path") if url_matches_target else None,
            "states_before": states_before,
            "text_read": False,
        }
        data["attempts"].append(attempt)
        data["attempts"] = data["attempts"][-8:]
        if not url_matches_target:
            continue
        focus = focus_accessible_with_pyatspi(obj, pyatspi, sleep=sleep)
        states_after = focus.get("states_after") if isinstance(focus.get("states_after"), dict) else {}
        data.update({
            "ok": bool(states_after.get("focused") is True),
            "status": "focused" if states_after.get("focused") is True else "matched_focus_not_confirmed",
            "matched": {**attempt, "focus": focus, "states_after": states_after},
        })
        return data
    return data


def atspi_focus_text_by_path(
    source_path: str,
    url: str,
    expected_text_sha256: str,
    *,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "not_found",
        "source_path": source_path,
        "url": url,
        "attempts": [],
        "errors": [],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "accessibility_focus_action_only": True,
        },
    }
    path_parts, path_error = parse_atspi_path(source_path)
    if path_error:
        data.update(path_error)
        return data
    relative_parts = path_parts[1:] if path_parts and path_parts[0] == 0 else path_parts
    pyatspi, desktop, load_error = load_pyatspi_desktop(pyatspi_module=pyatspi_module, load_pyatspi=load_pyatspi)
    if load_error is not None or pyatspi is None or desktop is None:
        data.update(load_error or {"status": "pyatspi_unavailable", "error": "pyatspi_unavailable"})
        return data
    for app_index, app in enumerate(atspi_children(desktop, data["errors"])[:80]):
        obj = app
        traversed = []
        ok_path = True
        for part in relative_parts:
            kids = atspi_children(obj, data["errors"])
            if part < 0 or part >= len(kids):
                ok_path = False
                break
            obj = kids[part]
            traversed.append(part)
        if not ok_path:
            continue
        attrs = atspi_document_attributes(obj)
        document_url = str(attrs.get("url") or "")
        text, text_length, caret, text_error = atspi_text_payload(obj, max_chars=12000)
        text_sha = text_sha256(text) if text else None
        attempt = {
            "app_index": app_index,
            "traversed": traversed,
            "role": atspi_role_name(obj, 120),
            "name": atspi_node_name(obj, 180),
            "url": document_url,
            "document_title": attrs.get("document_title"),
            "text_length": text_length,
            "text_sha256": text_sha,
            "expected_text_match": bool(text_sha == expected_text_sha256),
            "states_before": atspi_state_flags(obj, pyatspi),
            "text_error": text_error,
            "_text": text,
            "_caret_offset": caret,
            "_document_attrs": attrs,
        }
        data["attempts"].append(attempt)
        data["attempts"] = data["attempts"][-8:]
        if document_url != url or text_sha != expected_text_sha256:
            continue
        focus = focus_accessible_with_pyatspi(obj, pyatspi, sleep=sleep)
        states_after = focus.get("states_after") if isinstance(focus.get("states_after"), dict) else {}
        data.update({
            "ok": bool(states_after.get("focused") is True),
            "status": "focused" if states_after.get("focused") is True else "matched_focus_not_confirmed",
            "matched": {**attempt, "focus": focus},
        })
        return data
    return data


def atspi_insert_text_by_path(
    source_path: str,
    url: str,
    expected_current_sha256: str,
    insert_text: str,
    *,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "not_found",
        "source_path": source_path,
        "url": url,
        "insert_text_length": len(insert_text),
        "attempts": [],
        "errors": [],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "accessibility_targeted_edit_only": True,
            "global_virtual_keyboard": False,
            "requires_url_match": True,
            "requires_expected_current_text_hash": True,
            "sensitive_state_override_limited_to_expected_selftest_text": True,
        },
    }
    path_parts, path_error = parse_atspi_path(source_path)
    if path_error:
        data.update(path_error)
        return data
    relative_parts = path_parts[1:] if path_parts and path_parts[0] == 0 else path_parts
    pyatspi, desktop, load_error = load_pyatspi_desktop(pyatspi_module=pyatspi_module, load_pyatspi=load_pyatspi)
    if load_error is not None or pyatspi is None or desktop is None:
        data.update(load_error or {"status": "pyatspi_unavailable", "error": "pyatspi_unavailable"})
        return data
    for app_index, app in enumerate(atspi_children(desktop, data["errors"])[:80]):
        obj = app
        traversed = []
        ok_path = True
        for part in relative_parts:
            kids = atspi_children(obj, data["errors"])
            if part < 0 or part >= len(kids):
                ok_path = False
                break
            obj = kids[part]
            traversed.append(part)
        if not ok_path:
            continue
        attrs = atspi_document_attributes(obj)
        document_url = str(attrs.get("url") or "")
        states_before = atspi_state_flags(obj, pyatspi)
        text, text_length, caret, text_error = atspi_text_payload(obj, max_chars=12000)
        text_sha = text_sha256(text) if text else None
        role = atspi_role_name(obj, 120)
        name = atspi_node_name(obj, 180)
        attempt = {
            "app_index": app_index,
            "traversed": traversed,
            "role": role,
            "name": name,
            "url": document_url,
            "document_title": attrs.get("document_title"),
            "content_type": attrs.get("content_type"),
            "text_length": text_length,
            "text_sha256": text_sha,
            "expected_current_text_match": bool(text_sha == expected_current_sha256),
            "states_before": states_before,
            "text_error": text_error,
            "text_read": True,
            "_text": text,
            "_caret_offset": caret,
            "_document_attrs": attrs,
        }
        data["attempts"].append(attempt)
        data["attempts"] = data["attempts"][-8:]
        if document_url != url:
            continue
        low_shape = f"{role} {name}".lower()
        expected_selftest_text = text_sha == expected_current_sha256
        sensitive_selftest_override = bool(
            states_before.get("sensitive")
            and expected_selftest_text
            and "password" not in low_shape
            and "passwd" not in low_shape
            and "secret" not in low_shape
            and "token" not in low_shape
        )
        if states_before.get("sensitive") and not sensitive_selftest_override:
            data["status"] = "matched_sensitive_refused"
            data["matched"] = attempt
            return data
        if sensitive_selftest_override:
            attempt["sensitive_state_overridden_by_expected_selftest_text"] = True
        if not expected_selftest_text:
            data["status"] = "matched_unexpected_current_text"
            data["matched"] = attempt
            return data
        try:
            editable = obj.queryEditableText()
        except Exception as exc:
            data["status"] = "editable_text_unavailable"
            data["matched"] = attempt
            data["error"] = f"query_editable_text_failed: {exc}"
            return data
        insert_offset = caret if isinstance(caret, int) and caret >= 0 else text_length
        field_focus: dict[str, Any] = {}
        try:
            component = obj.queryComponent()
            field_focus["component_grab_focus"] = bool(component.grabFocus())
        except Exception as exc:
            field_focus["component_error"] = str(exc)[:180]
        try:
            text_iface = obj.queryText()
            if hasattr(text_iface, "setCaretOffset"):
                text_iface.setCaretOffset(insert_offset)
        except Exception:
            pass
        try:
            insert_ok = bool(editable.insertText(insert_offset, insert_text, len(insert_text)))
        except Exception as exc:
            data["status"] = "insert_failed"
            data["matched"] = attempt
            data["error"] = f"insert_text_failed: {exc}"
            return data
        sleep(0.2)
        after_text, after_length, after_caret, after_error = atspi_text_payload(obj, max_chars=12000)
        after_sha = text_sha256(after_text) if after_text else None
        expected_after = text[:insert_offset] + insert_text + text[insert_offset:]
        expected_after_sha = text_sha256(expected_after)
        set_contents_ok: bool | None = None
        if after_sha != expected_after_sha:
            try:
                set_contents_ok = bool(editable.setTextContents(expected_after))
            except Exception as exc:
                data.setdefault("errors", []).append({"kind": "set_text_contents_failed", "error": str(exc)[:180]})
                set_contents_ok = False
            sleep(0.2)
            after_text, after_length, after_caret, after_error = atspi_text_payload(obj, max_chars=12000)
            after_sha = text_sha256(after_text) if after_text else None
        data.update({
            "ok": bool((insert_ok or set_contents_ok) and after_sha == expected_after_sha),
            "status": "inserted" if (insert_ok or set_contents_ok) and after_sha == expected_after_sha else "insert_unconfirmed",
            "method": "atspi_editable_text_insert",
            "matched": {
                **attempt,
                "field_focus": field_focus,
                "insert_offset": insert_offset,
                "insert_ok": insert_ok,
                "set_text_contents_fallback_ok": set_contents_ok,
                "after_text_length": after_length,
                "after_text_sha256": after_sha,
                "after_expected_match": bool(after_sha == expected_after_sha),
                "after_caret_offset": after_caret,
                "after_text_error": after_error,
                "_after_text": after_text,
            },
        })
        return data
    return data


def gi_atspi_state_contains(node: Any, state: Any) -> bool:
    try:
        state_set = node.get_state_set()
        return bool(state_set and state_set.contains(state))
    except Exception:
        return False


def gi_atspi_document_attributes(atspi_module: Any, document: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for target_key, atspi_key in (
        ("url", "DocURL"),
        ("content_type", "MimeType"),
        ("title", "Title"),
    ):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                value = atspi_module.Accessible.get_document_attribute_value(document, atspi_key)
        except Exception:
            value = None
        if value:
            values[target_key] = str(value)
    return values


def gi_atspi_firefox_documents(
    atspi_module: Any,
    app: Any,
    max_nodes: int = 20000,
    max_children: int = 180,
    max_depth: int = 16,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    roles = {
        atspi_module.Role.DOCUMENT_WEB,
        atspi_module.Role.DOCUMENT_FRAME,
        atspi_module.Role.DOCUMENT_TEXT,
        atspi_module.Role.DOCUMENT_EMAIL,
    }
    stack: list[tuple[Any, int, str]] = [(app, 0, "0")]
    nodes_seen = 0
    while stack and nodes_seen < max_nodes:
        node, depth, path = stack.pop()
        nodes_seen += 1
        try:
            role = atspi_module.Accessible.get_role(node)
            role_name = str(atspi_module.Accessible.get_role_name(node) or "")
            name = str(atspi_module.Accessible.get_name(node) or "")
            child_count = int(atspi_module.Accessible.get_child_count(node) or 0)
        except Exception:
            continue
        if role in roles:
            documents.append({
                "node": node,
                "path": path,
                "role": role_name,
                "name": name,
                "showing": gi_atspi_state_contains(node, atspi_module.StateType.SHOWING),
                "visible": gi_atspi_state_contains(node, atspi_module.StateType.VISIBLE),
                "focused": gi_atspi_state_contains(node, atspi_module.StateType.FOCUSED),
            })
        if depth < max_depth:
            for index in range(min(child_count, max_children) - 1, -1, -1):
                try:
                    stack.append((atspi_module.Accessible.get_child_at_index(node, index), depth + 1, f"{path}.{index}"))
                except Exception:
                    continue
    return documents


def gi_atspi_document_priority(document: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        1 if document.get("focused") else 0,
        1 if document.get("showing") else 0,
        1 if document.get("visible") else 0,
        -len(str(document.get("path") or "")),
    )


def atspi_insert_text_by_url(
    url: str,
    expected_current_sha256: str,
    insert_text: str,
    timeout_sec: float = 10.0,
    *,
    atspi_module: Any | None = None,
    load_atspi: Callable[[], tuple[Any | None, str | None]] = import_gi_atspi_module,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "not_found",
        "url": url,
        "nodes_seen": 0,
        "attempts": [],
        "errors": [],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "accessibility_targeted_edit_only": True,
            "global_virtual_keyboard": False,
            "requires_url_match": True,
            "requires_expected_current_text_hash": True,
            "sensitive_state_override_limited_to_expected_selftest_text": True,
        },
    }
    atspi = atspi_module
    if atspi is None:
        atspi, import_error = load_atspi()
        if import_error or atspi is None:
            data["status"] = "atspi_unavailable"
            data["error"] = import_error or "AT-SPI import failed"
            return data
    deadline = monotonic() + max(1.0, min(float(timeout_sec or 10.0), 20.0))
    editable_roles = {atspi.Role.ENTRY, atspi.Role.TEXT}
    text_roles = {atspi.Role.ENTRY, atspi.Role.TEXT, atspi.Role.PARAGRAPH}

    def role_name(obj: Any) -> str:
        try:
            return safe_string(atspi.Accessible.get_role_name(obj), 120)
        except Exception:
            return "<role_unreadable>"

    def node_name(obj: Any) -> str:
        try:
            return safe_string(atspi.Accessible.get_name(obj), 180)
        except Exception:
            return "<name_unreadable>"

    def node_text(obj: Any) -> tuple[str, int, int | None, str | None]:
        try:
            text_iface = atspi.Accessible.get_text_iface(obj)
            if not text_iface:
                return "", 0, None, None
            count = int(atspi.Text.get_character_count(text_iface) or 0)
            caret = int(atspi.Text.get_caret_offset(text_iface) or 0)
            text = str(atspi.Text.get_text(text_iface, 0, min(count, 12000)) or "") if count > 0 else ""
            return text, count, caret, None
        except Exception as exc:
            return "", 0, None, f"read_text_failed: {exc}"

    def child_count(obj: Any) -> int:
        try:
            return int(atspi.Accessible.get_child_count(obj) or 0)
        except Exception:
            return 0

    def child_at(obj: Any, index: int) -> Any | None:
        try:
            return atspi.Accessible.get_child_at_index(obj, index)
        except Exception as exc:
            if len(data["errors"]) < 10:
                data["errors"].append({"kind": "child_unreadable", "error": str(exc)[:160]})
            return None

    def attempt_insert(node: Any, path: str, document_path: str, document_attrs: dict[str, Any]) -> dict[str, Any] | None:
        try:
            role = atspi.Accessible.get_role(node)
        except Exception:
            return None
        editable_state = gi_atspi_state_contains(node, atspi.StateType.EDITABLE)
        if role not in text_roles and not editable_state:
            return None
        states = {
            "focused": gi_atspi_state_contains(node, atspi.StateType.FOCUSED),
            "editable": editable_state,
            "showing": gi_atspi_state_contains(node, atspi.StateType.SHOWING),
            "visible": gi_atspi_state_contains(node, atspi.StateType.VISIBLE),
            "sensitive": gi_atspi_state_contains(node, atspi.StateType.SENSITIVE),
            "enabled": gi_atspi_state_contains(node, atspi.StateType.ENABLED),
        }
        text, text_length, caret, text_error = node_text(node)
        text_sha = text_sha256(text) if text else None
        attempt = {
            "role": role_name(node),
            "name": node_name(node),
            "path": path,
            "document_path": document_path,
            "url": document_attrs.get("url"),
            "document_title": document_attrs.get("title"),
            "content_type": document_attrs.get("content_type"),
            "text_length": text_length,
            "text_sha256": text_sha,
            "expected_current_text_match": bool(text_sha == expected_current_sha256),
            "states_before": states,
            "text_error": text_error,
            "text_read": True,
            "_text": text,
        }
        data["attempts"].append(attempt)
        data["attempts"] = data["attempts"][-12:]
        low_shape = f"{attempt['role']} {attempt['name']}".lower()
        expected_selftest_text = text_sha == expected_current_sha256
        sensitive_selftest_override = bool(
            states.get("sensitive")
            and expected_selftest_text
            and "password" not in low_shape
            and "passwd" not in low_shape
            and "secret" not in low_shape
            and "token" not in low_shape
        )
        if states.get("sensitive") and not sensitive_selftest_override:
            return {**attempt, "status": "matched_sensitive_refused"}
        if sensitive_selftest_override:
            attempt["sensitive_state_overridden_by_expected_selftest_text"] = True
        if role not in editable_roles and not states.get("editable"):
            return None
        if not expected_selftest_text:
            return {**attempt, "status": "matched_unexpected_current_text"}
        try:
            editable = atspi.Accessible.get_editable_text_iface(node)
            if not editable:
                return {**attempt, "status": "editable_text_unavailable"}
        except Exception as exc:
            return {**attempt, "status": "editable_text_unavailable", "error": str(exc)[:180]}
        insert_offset = caret if isinstance(caret, int) and caret >= 0 else text_length
        field_focus: dict[str, Any] = {}
        try:
            component = atspi.Accessible.get_component_iface(node)
            if component:
                field_focus["component_grab_focus"] = bool(atspi.Component.grab_focus(component))
        except Exception as exc:
            field_focus["component_error"] = str(exc)[:180]
        try:
            text_iface = atspi.Accessible.get_text_iface(node)
            if text_iface:
                atspi.Text.set_caret_offset(text_iface, insert_offset)
        except Exception:
            pass
        try:
            insert_ok = bool(atspi.EditableText.insert_text(editable, insert_offset, insert_text, len(insert_text)))
        except Exception as exc:
            return {**attempt, "status": "insert_failed", "insert_error": str(exc)[:180]}
        sleep(0.2)
        after_text, after_length, after_caret, after_error = node_text(node)
        after_sha = text_sha256(after_text) if after_text else None
        expected_after = text[:insert_offset] + insert_text + text[insert_offset:]
        expected_after_sha = text_sha256(expected_after)
        set_contents_ok: bool | None = None
        if after_sha != expected_after_sha:
            try:
                set_contents_ok = bool(atspi.EditableText.set_text_contents(editable, expected_after))
            except Exception as exc:
                data.setdefault("errors", []).append({"kind": "set_text_contents_failed", "error": str(exc)[:180]})
                set_contents_ok = False
            sleep(0.2)
            after_text, after_length, after_caret, after_error = node_text(node)
            after_sha = text_sha256(after_text) if after_text else None
        return {
            **attempt,
            "status": "inserted" if (insert_ok or set_contents_ok) and after_sha == expected_after_sha else "insert_unconfirmed",
            "field_focus": field_focus,
            "insert_offset": insert_offset,
            "insert_ok": insert_ok,
            "set_text_contents_fallback_ok": set_contents_ok,
            "after_text_length": after_length,
            "after_text_sha256": after_sha,
            "after_expected_match": bool(after_sha == expected_after_sha),
            "after_caret_offset": after_caret,
            "after_text_error": after_error,
            "_after_text": after_text,
        }

    while monotonic() < deadline:
        try:
            desktop = atspi.get_desktop(0)
            app_count = int(atspi.Accessible.get_child_count(desktop) or 0)
        except Exception as exc:
            data["status"] = "desktop_unreadable"
            data["error"] = f"desktop_unreadable: {exc}"
            return data
        firefox_apps: list[Any] = []
        for index in range(min(app_count, 80)):
            app = child_at(desktop, index)
            if app is None:
                continue
            try:
                app_name = str(atspi.Accessible.get_name(app) or "")
            except Exception:
                app_name = ""
            if "firefox" in app_name.lower():
                firefox_apps.append(app)
        for app in firefox_apps[:8]:
            documents = gi_atspi_firefox_documents(atspi, app, max_nodes=20000, max_children=180)
            documents = sorted(documents, key=gi_atspi_document_priority, reverse=True)
            for document in documents[:48]:
                node = document.get("node")
                if node is None:
                    continue
                attrs = gi_atspi_document_attributes(atspi, node)
                if str(attrs.get("url") or "") != url:
                    continue
                document_path = str(document.get("path") or "")
                stack: list[tuple[Any, str, int]] = [(node, document_path, 0)]
                while stack and data["nodes_seen"] < 12000 and monotonic() < deadline:
                    current, path, depth = stack.pop()
                    data["nodes_seen"] += 1
                    matched = attempt_insert(current, path, document_path, attrs)
                    if isinstance(matched, dict) and matched.get("status") in {
                        "matched_sensitive_refused",
                        "matched_unexpected_current_text",
                        "editable_text_unavailable",
                        "insert_failed",
                        "inserted",
                        "insert_unconfirmed",
                    }:
                        data.update({
                            "ok": bool(matched.get("status") == "inserted" and matched.get("after_expected_match") is True),
                            "status": str(matched.get("status") or "matched"),
                            "method": "atspi_editable_text_insert",
                            "matched": matched,
                        })
                        return data
                    if depth < 12:
                        for child_index in range(min(child_count(current), 180) - 1, -1, -1):
                            child = child_at(current, child_index)
                            if child is not None:
                                stack.append((child, f"{path}.{child_index}", depth + 1))
        sleep(0.5)
    return data


def atspi_focus_firefox_frame_by_title(
    title: str,
    timeout_sec: float = 5.0,
    *,
    atspi_module: Any | None = None,
    load_atspi: Callable[[], tuple[Any | None, str | None]] = import_gi_atspi_module,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "not_found",
        "title": title,
        "attempts": [],
        "errors": [],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "window_focus_only": True,
        },
    }
    atspi = atspi_module
    if atspi is None:
        atspi, import_error = load_atspi()
        if import_error or atspi is None:
            data["status"] = "atspi_unavailable"
            data["error"] = import_error or "AT-SPI import failed"
            return data
    title_token = str(title or "").lower()
    deadline = monotonic() + max(1.0, min(float(timeout_sec or 5.0), 10.0))

    def focus_accessible(obj: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"component_grab_focus": None, "actions": []}
        try:
            component = atspi.Accessible.get_component_iface(obj)
            if component:
                try:
                    result["component_grab_focus"] = bool(atspi.Component.grab_focus(component))
                except Exception as exc:
                    result["component_grab_focus_error"] = str(exc)[:180]
        except Exception as exc:
            result["component_error"] = str(exc)[:180]
        try:
            action = atspi.Accessible.get_action_iface(obj)
            if action:
                action_count = int(atspi.Action.get_n_actions(action) or 0)
                for action_index in range(min(action_count, 8)):
                    try:
                        action_name = str(atspi.Action.get_action_name(action, action_index) or "").lower()
                    except Exception:
                        action_name = ""
                    if action_name not in {"focus", "click", "press", "activate"}:
                        continue
                    try:
                        action_ok = bool(atspi.Action.do_action(action, action_index))
                    except Exception as exc:
                        result["actions"].append({"name": action_name, "ok": False, "error": str(exc)[:160]})
                        continue
                    result["actions"].append({"name": action_name, "ok": action_ok})
        except Exception:
            pass
        sleep(0.25)
        result["states_after"] = {
            "focused": gi_atspi_state_contains(obj, atspi.StateType.FOCUSED),
            "showing": gi_atspi_state_contains(obj, atspi.StateType.SHOWING),
            "visible": gi_atspi_state_contains(obj, atspi.StateType.VISIBLE),
            "active": gi_atspi_state_contains(obj, atspi.StateType.ACTIVE),
        }
        return result

    while monotonic() < deadline:
        try:
            desktop = atspi.get_desktop(0)
            app_count = int(atspi.Accessible.get_child_count(desktop) or 0)
        except Exception as exc:
            data["status"] = "desktop_unreadable"
            data["error"] = f"desktop_unreadable: {exc}"
            return data
        for app_index in range(min(app_count, 80)):
            try:
                app = atspi.Accessible.get_child_at_index(desktop, app_index)
                app_name = str(atspi.Accessible.get_name(app) or "")
            except Exception:
                continue
            if "firefox" not in app_name.lower():
                continue
            try:
                child_count = int(atspi.Accessible.get_child_count(app) or 0)
            except Exception:
                child_count = 0
            for child_index in range(min(child_count, 20)):
                try:
                    child = atspi.Accessible.get_child_at_index(app, child_index)
                    role = str(atspi.Accessible.get_role_name(child) or "")
                    name = str(atspi.Accessible.get_name(child) or "")
                except Exception:
                    continue
                attempt = {
                    "app_index": app_index,
                    "child_index": child_index,
                    "app": app_name,
                    "role": role,
                    "name": safe_string(name, 220),
                    "title_match": bool(title_token and title_token in name.lower()),
                    "states_before": {
                        "focused": gi_atspi_state_contains(child, atspi.StateType.FOCUSED),
                        "showing": gi_atspi_state_contains(child, atspi.StateType.SHOWING),
                        "visible": gi_atspi_state_contains(child, atspi.StateType.VISIBLE),
                        "active": gi_atspi_state_contains(child, atspi.StateType.ACTIVE),
                    },
                }
                data["attempts"].append(attempt)
                data["attempts"] = data["attempts"][-10:]
                if not attempt["title_match"]:
                    continue
                focus = focus_accessible(child)
                states_after = focus.get("states_after") if isinstance(focus.get("states_after"), dict) else {}
                focused = bool(states_after.get("focused") or states_after.get("active") or states_after.get("showing"))
                data.update({
                    "ok": focused,
                    "status": "focused" if focused else "matched_focus_not_confirmed",
                    "matched": {**attempt, "focus": focus},
                })
                return data
        sleep(0.3)
    return data


def atspi_focus_metadata_by_url(
    url: str,
    timeout_sec: float = 6.0,
    *,
    pyatspi_module: Any | None = None,
    load_pyatspi: Callable[[], tuple[Any | None, str | None]] = import_pyatspi_module,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "not_found",
        "url": url,
        "nodes_seen": 0,
        "attempts": [],
        "errors": [],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "accessibility_focus_action_only": True,
            "text_read": False,
        },
    }
    pyatspi, desktop, load_error = load_pyatspi_desktop(
        timeout_ms=700,
        pyatspi_module=pyatspi_module,
        load_pyatspi=load_pyatspi,
    )
    if load_error is not None or pyatspi is None or desktop is None:
        data.update(load_error or {"status": "pyatspi_unavailable", "error": "pyatspi_unavailable"})
        return data
    deadline = monotonic() + max(1.0, min(float(timeout_sec or 6.0), 12.0))
    max_nodes = 3000
    max_depth = 24
    focus_roles = {"entry", "text", "paragraph", "document web", "document frame", "document text"}

    def focus_targets(document: Any, document_path: str) -> list[tuple[Any, str, str]]:
        editable: list[tuple[Any, str, str]] = []
        fallback: list[tuple[Any, str, str]] = [(document, document_path, "document")]
        stack: list[tuple[Any, str, int]] = [(document, document_path, 0)]
        local_nodes = 0
        while stack and local_nodes < 900 and monotonic() <= deadline:
            obj, path, depth = stack.pop()
            local_nodes += 1
            role = atspi_role_name(obj, 120)
            role_lower = role.lower()
            states = atspi_state_flags(obj, pyatspi)
            if not states.get("sensitive") and (states.get("editable") or role_lower in focus_roles):
                kind = "editable_or_text" if states.get("editable") or role_lower in {"entry", "text"} else "document_text"
                editable.append((obj, path, kind))
            if depth < 10:
                for child_index, child in enumerate(atspi_children(obj, data["errors"])[:120]):
                    stack.append((child, f"{path}.{child_index}", depth + 1))
        return editable[:12] + fallback

    matched: dict[str, Any] | None = None

    def walk(obj: Any, path: str, app_name: str, depth: int) -> None:
        nonlocal matched
        if matched is not None or depth > max_depth or data["nodes_seen"] >= max_nodes or monotonic() > deadline:
            return
        data["nodes_seen"] += 1
        current_app = app_name
        try:
            app_context = atspi_application_context(obj)
            if app_context.get("name"):
                current_app = str(app_context.get("name") or current_app)
        except Exception:
            pass
        attrs = atspi_document_attributes(obj)
        document_url = str(attrs.get("url") or "")
        if document_url == url:
            for target_obj, target_path, target_kind in focus_targets(obj, path):
                states_before = atspi_state_flags(target_obj, pyatspi)
                role = atspi_role_name(target_obj, 120)
                attempt = {
                    "app": current_app,
                    "role": role,
                    "name": atspi_node_name(target_obj, 180),
                    "path": target_path,
                    "target_kind": target_kind,
                    "url": document_url,
                    "document_title": attrs.get("document_title"),
                    "content_type": attrs.get("content_type"),
                    "document_path": attrs.get("document_path"),
                    "states_before": states_before,
                    "text_read": False,
                }
                data["attempts"].append(attempt)
                data["attempts"] = data["attempts"][-12:]
                if states_before.get("sensitive"):
                    continue
                focus = focus_accessible_with_pyatspi(target_obj, pyatspi, sleep=sleep)
                states_after = focus.get("states_after") if isinstance(focus.get("states_after"), dict) else {}
                focus_attempt = {**attempt, "focus": focus, "states_after": states_after}
                if states_after.get("focused") is True:
                    matched = focus_attempt
                    return
                matched = focus_attempt if matched is None else matched
        for child_index, child in enumerate(atspi_children(obj, data["errors"])[:150]):
            walk(child, f"{path}.{child_index}", current_app, depth + 1)

    try:
        for app_index, app in enumerate(atspi_children(desktop, data["errors"])[:80]):
            if matched is not None and nested_get(matched, ["states_after", "focused"]) is True:
                break
            if monotonic() > deadline:
                break
            walk(app, str(app_index), atspi_node_name(app, 180), 0)
    except Exception as exc:
        data["status"] = "walk_failed"
        data["error"] = f"walk_failed: {exc}"
        return data
    if matched is not None:
        states_after = matched.get("states_after") if isinstance(matched.get("states_after"), dict) else {}
        data.update({
            "ok": bool(states_after.get("focused") is True),
            "status": "focused" if states_after.get("focused") is True else "matched_focus_not_confirmed",
            "matched": matched,
        })
    return data


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
