from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from typing import Any, Callable, Mapping


ProbeEventFinder = Callable[[str, int], tuple[dict[str, Any] | None, list[dict[str, Any]]]]
WriteText = Callable[[Path, str, int], dict[str, Any] | None]
TerminateProcesses = Callable[[str], list[dict[str, Any]]]
PopenFactory = Callable[..., Any]


def _nested_get(data: Mapping[str, Any] | None, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def editor_extension_selftest_run_id(generated_at: str, pid: int) -> str:
    return re.sub(r"[^0-9]", "", str(generated_at or ""))[:14] + str(pid)[-5:]


def editor_extension_selftest_plan(
    *,
    generated_at: str,
    pid: int,
    extension_id: str,
    probe_path: str = "/srv/work/abyss-machine/editor-extension-selftest.txt",
) -> dict[str, Any]:
    run_id = editor_extension_selftest_run_id(generated_at, pid)
    probe_text = f"abyss editor extension selftest {run_id}"
    probe_hash = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    probe_name = Path(probe_path).name
    return {
        "run_id": run_id,
        "probe": {
            "text": probe_text,
            "text_sha256": probe_hash,
            "text_length": len(probe_text),
            "path": probe_path,
        },
        "ingest": {
            "text": probe_text,
            "source": "editor_extension_explicit",
            "app": "code",
            "window_title": probe_name,
            "context": " ".join(
                [
                    "editor_extension",
                    "selftest=true",
                    f"path={probe_path}",
                    "language=plaintext",
                    "version=0",
                    "app=code",
                ]
            ),
            "skip_duplicate": True,
            "metadata": {
                "file": {
                    "path": probe_path,
                    "root": "/srv/work",
                    "name": probe_name,
                },
                "editor": {
                    "extension_id": extension_id,
                    "selftest": True,
                    "ui_callback_proven": False,
                },
            },
        },
    }


def editor_extension_probe_event_from_records(
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    text_sha256: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    for record in records:
        if not isinstance(record, dict):
            continue
        text_payload = record.get("text") if isinstance(record.get("text"), Mapping) else {}
        if record.get("source_adapter") != "editor_extension_explicit":
            continue
        if text_payload.get("text_sha256") != text_sha256:
            continue
        return {
            "event_id": record.get("event_id"),
            "generated_at": record.get("generated_at"),
            "status": record.get("status"),
            "source_adapter": record.get("source_adapter"),
            "capture_gate_decision": _nested_get(record, ["capture_gate", "decision"]),
            "capture_gate_confidence": _nested_get(record, ["capture_gate", "confidence"]),
            "text_length": text_payload.get("text_length"),
            "text_chars_stored": text_payload.get("text_chars_stored"),
            "text_sha256": text_payload.get("text_sha256"),
            "recipient": _nested_get(record, ["causal_context", "recipient"]),
            "where": _nested_get(record, ["causal_context", "where"]),
            "task": _nested_get(record, ["causal_context", "task"]),
        }, errors
    return None, errors


def _editor_extension_event_ok(event: dict[str, Any] | None, probe: Mapping[str, Any]) -> bool:
    return bool(
        isinstance(event, dict)
        and event.get("status") == "captured"
        and event.get("source_adapter") == "editor_extension_explicit"
        and event.get("capture_gate_decision") == "allow_text"
        and event.get("capture_gate_confidence") == "editor_path_allowed"
        and event.get("text_sha256") == probe.get("text_sha256")
        and event.get("text_chars_stored") == probe.get("text_length")
        and _nested_get(event, ["recipient", "kind"]) == "editor_extension"
    )


def _ingest_summary(ingest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": ingest.get("ok"),
        "event_id": ingest.get("event_id"),
        "status": ingest.get("status"),
        "source_adapter": ingest.get("source_adapter"),
        "capture_gate_decision": _nested_get(ingest, ["capture_gate", "decision"]),
        "capture_gate_confidence": _nested_get(ingest, ["capture_gate", "confidence"]),
        "text_length": _nested_get(ingest, ["text", "text_length"]),
        "text_chars_stored": _nested_get(ingest, ["text", "text_chars_stored"]),
        "recipient": _nested_get(ingest, ["causal_context", "recipient"]),
        "where": _nested_get(ingest, ["causal_context", "where"]),
        "task": _nested_get(ingest, ["causal_context", "task"]),
    }


def editor_extension_selftest_document(
    *,
    plan: Mapping[str, Any],
    ingest: Mapping[str, Any],
    event: dict[str, Any] | None,
    parse_errors: list[dict[str, Any]],
    latest_status: Mapping[str, Any] | None,
    latest_status_error: str | None,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    probe = plan.get("probe") if isinstance(plan.get("probe"), Mapping) else {}
    event_ok = _editor_extension_event_ok(event, probe)
    ok = bool(ingest.get("ok") and event_ok and not parse_errors)
    return {
        "schema": f"{schema_prefix}_typing_editor_extension_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "source_adapter": "editor_extension_explicit",
        "probe": {
            "text_sha256": probe.get("text_sha256"),
            "text_length": probe.get("text_length"),
            "text_omitted": True,
            "path": probe.get("path"),
        },
        "latest_extension_status": {
            "exists": isinstance(latest_status, Mapping),
            "ok": latest_status.get("ok") if isinstance(latest_status, Mapping) else None,
            "status": latest_status.get("status") if isinstance(latest_status, Mapping) else None,
            "generated_at": latest_status.get("generated_at") if isinstance(latest_status, Mapping) else None,
            "error": latest_status_error,
        },
        "ingest": _ingest_summary(ingest),
        "event": event,
        "parse_errors": parse_errors[:20],
        "policy": {
            "raw_keylogging": False,
            "committed_editor_changes_only": True,
            "password_fields_captured": False,
            "automatic_action": False,
            "network_access": False,
            "ui_callback_required": False,
        },
        "non_claims": [
            "This selftest proves the editor_extension_explicit ingest, capture-gate, and causal-context route.",
            "It does not prove a live VS Code UI text-change callback fired from a user keystroke.",
            "It does not read editor buffers and does not collect raw key events.",
        ],
    }


def editor_extension_latest_status_document(
    *,
    latest: Mapping[str, Any] | None,
    latest_error: str | None,
    selftest: Mapping[str, Any] | None,
    selftest_error: str | None,
    callback: Mapping[str, Any] | None,
    callback_error: str | None,
    extension_path_exists: bool,
    max_age_sec: float,
    generated_at: str,
    age_seconds_from_iso: Callable[[Any], float | None],
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    selftest_data = selftest if isinstance(selftest, Mapping) else {}
    callback_data = callback if isinstance(callback, Mapping) else {}
    selftest_event = selftest_data.get("event") if isinstance(selftest_data.get("event"), Mapping) else {}
    callback_event = callback_data.get("event") if isinstance(callback_data.get("event"), Mapping) else {}
    latest_policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    selftest_policy = selftest_data.get("policy") if isinstance(selftest_data.get("policy"), Mapping) else {}
    callback_policy = callback_data.get("policy") if isinstance(callback_data.get("policy"), Mapping) else {}
    latest_age_sec = age_seconds_from_iso(latest_data.get("generated_at"))
    selftest_age_sec = age_seconds_from_iso(selftest_data.get("generated_at"))
    callback_age_sec = age_seconds_from_iso(callback_data.get("generated_at"))
    activation_ok = bool(
        isinstance(latest, Mapping)
        and latest_data.get("ok") is True
        and latest_data.get("status") in {"activated", "sent", "skipped", "selftest_edit_applied"}
    )
    selftest_ok = bool(
        isinstance(selftest, Mapping)
        and selftest_data.get("ok") is True
        and selftest_data.get("status") == "passed"
        and selftest_event.get("source_adapter") == "editor_extension_explicit"
        and selftest_event.get("status") == "captured"
        and selftest_event.get("capture_gate_decision") == "allow_text"
        and selftest_event.get("capture_gate_confidence") == "editor_path_allowed"
        and selftest_event.get("text_length") == selftest_event.get("text_chars_stored")
        and selftest_policy.get("raw_keylogging") is False
        and selftest_policy.get("password_fields_captured") is False
        and selftest_policy.get("network_access") is False
    )
    callback_ok = bool(
        isinstance(callback, Mapping)
        and callback_data.get("ok") is True
        and callback_data.get("status") == "passed"
        and callback_event.get("source_adapter") == "editor_extension_explicit"
        and callback_event.get("status") == "captured"
        and callback_event.get("capture_gate_decision") == "allow_text"
        and callback_event.get("capture_gate_confidence") == "editor_path_allowed"
        and callback_event.get("text_length") == callback_event.get("text_chars_stored")
        and callback_policy.get("raw_keylogging") is False
        and callback_policy.get("password_fields_captured") is False
        and callback_policy.get("live_vscode_extension_callback") is True
    )
    policy_ok = bool(
        latest_policy.get("raw_keylogging") in {False, None}
        and latest_policy.get("password_fields_captured") in {False, None}
        and latest_policy.get("automatic_action") in {False, None}
        and selftest_policy.get("raw_keylogging") is False
        and selftest_policy.get("password_fields_captured") is False
        and callback_policy.get("raw_keylogging") is False
        and callback_policy.get("password_fields_captured") is False
    )
    proof_times = [item for item in (selftest_age_sec, callback_age_sec) if isinstance(item, (int, float))]
    proof_age_sec = max(proof_times) if proof_times else None
    proofs_fresh = bool(proof_age_sec is not None and proof_age_sec <= float(max_age_sec))
    if not extension_path_exists:
        status = "extension_missing"
    elif not activation_ok:
        status = "activation_missing"
    elif not selftest_ok:
        status = "selftest_failed"
    elif not callback_ok:
        status = "callback_selftest_failed"
    elif not policy_ok:
        status = "policy_violation"
    elif not proofs_fresh:
        status = "proof_stale"
    else:
        status = "ready"
    return {
        "schema": f"{schema_prefix}_typing_editor_extension_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": status == "ready",
        "status": status,
        "summary": {
            "activation_ok": activation_ok,
            "activation_status": latest_data.get("status") if isinstance(latest, Mapping) else None,
            "activation_generated_at": latest_data.get("generated_at") if isinstance(latest, Mapping) else None,
            "activation_age_sec": latest_age_sec,
            "selftest_ok": selftest_ok,
            "selftest_status": selftest_data.get("status") if isinstance(selftest, Mapping) else None,
            "selftest_generated_at": selftest_data.get("generated_at") if isinstance(selftest, Mapping) else None,
            "selftest_age_sec": selftest_age_sec,
            "callback_ok": callback_ok,
            "callback_status": callback_data.get("status") if isinstance(callback, Mapping) else None,
            "callback_generated_at": callback_data.get("generated_at") if isinstance(callback, Mapping) else None,
            "callback_age_sec": callback_age_sec,
            "proof_age_sec": proof_age_sec,
            "max_age_sec": float(max_age_sec),
            "selftest_event_status": selftest_event.get("status"),
            "callback_event_status": callback_event.get("status"),
        },
        "latest": {
            "status": latest_data.get("status") if isinstance(latest, Mapping) else None,
            "generated_at": latest_data.get("generated_at") if isinstance(latest, Mapping) else None,
            "ok": latest_data.get("ok") if isinstance(latest, Mapping) else None,
            "error": latest_error,
        },
        "selftest": {
            "status": selftest_data.get("status") if isinstance(selftest, Mapping) else None,
            "generated_at": selftest_data.get("generated_at") if isinstance(selftest, Mapping) else None,
            "ok": selftest_data.get("ok") if isinstance(selftest, Mapping) else None,
            "event": {
                "status": selftest_event.get("status"),
                "source_adapter": selftest_event.get("source_adapter"),
                "capture_gate_decision": selftest_event.get("capture_gate_decision"),
                "capture_gate_confidence": selftest_event.get("capture_gate_confidence"),
            },
            "error": selftest_error,
        },
        "callback_selftest": {
            "status": callback_data.get("status") if isinstance(callback, Mapping) else None,
            "generated_at": callback_data.get("generated_at") if isinstance(callback, Mapping) else None,
            "ok": callback_data.get("ok") if isinstance(callback, Mapping) else None,
            "event": {
                "status": callback_event.get("status"),
                "source_adapter": callback_event.get("source_adapter"),
                "capture_gate_decision": callback_event.get("capture_gate_decision"),
                "capture_gate_confidence": callback_event.get("capture_gate_confidence"),
            },
            "error": callback_error,
        },
        "policy": {
            "raw_keylogging": False,
            "committed_editor_changes_only": True,
            "password_fields_captured": False,
            "automatic_action": False,
            "network_access": False,
            "live_vscode_extension_callback": callback_policy.get("live_vscode_extension_callback"),
        },
        "non_claims": [
            "Editor extension proof covers committed document edits only, not raw keystrokes.",
            "The callback selftest opens a disposable VS Code window and does not read terminal output.",
        ],
    }


def editor_callback_selftest_run_id(generated_at: str, pid: int) -> str:
    return re.sub(r"[^0-9]", "", str(generated_at or ""))[:14] + str(pid)[-5:]


def editor_callback_selftest_probe(generated_at: str, pid: int) -> dict[str, Any]:
    run_id = editor_callback_selftest_run_id(generated_at, pid)
    text = f"abyss vscode callback committed text {run_id}"
    return {
        "run_id": run_id,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text_length": len(text),
    }


def _editor_callback_event_ok(event: dict[str, Any] | None, probe: Mapping[str, Any]) -> bool:
    return bool(
        isinstance(event, dict)
        and event.get("status") == "captured"
        and event.get("source_adapter") == "editor_extension_explicit"
        and event.get("capture_gate_decision") == "allow_text"
        and event.get("capture_gate_confidence") == "editor_path_allowed"
        and event.get("text_sha256") == probe.get("text_sha256")
        and event.get("text_chars_stored") == probe.get("text_length")
        and _nested_get(event, ["recipient", "kind"]) == "editor_extension"
    )


def editor_callback_selftest_document(
    *,
    generated_at: str,
    pid: int,
    schema_prefix: str,
    version: str,
    code_bin: str | None,
    file_path: Path,
    tmp_root: Path,
    vscode_extension_path: Path,
    base_env: Mapping[str, str],
    write_text: WriteText,
    find_event: ProbeEventFinder,
    terminate_processes: TerminateProcesses,
    popen: PopenFactory = subprocess.Popen,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    killpg: Callable[[int, int], None] = os.killpg,
    getpgid: Callable[[int], int] = os.getpgid,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    probe = editor_callback_selftest_probe(generated_at, pid)
    user_data_dir = tmp_root / "user-data"
    stdout_tail = ""
    stderr_tail = ""
    code_returncode: int | None = None
    cleanup_actions: list[dict[str, Any]] = []
    event: dict[str, Any] | None = None
    parse_errors: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if not code_bin:
        return {
            "schema": f"{schema_prefix}_typing_editor_callback_selftest_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "code_missing",
            "source_adapter": "editor_extension_explicit",
            "error": "code executable not found",
            "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
        }

    proc: Any = None
    try:
        tmp_root.mkdir(parents=True, exist_ok=True)
        user_data_dir.mkdir(parents=True, exist_ok=True)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        write_error = write_text(file_path, "", 0o664)
        if write_error:
            errors.append(dict(write_error))
        env = dict(base_env)
        env["ABYSS_TYPING_EDITOR_CALLBACK_SELFTEST_PATH"] = str(file_path)
        env["ABYSS_TYPING_EDITOR_CALLBACK_SELFTEST_TEXT"] = str(probe["text"])
        proc = popen(
            [
                code_bin,
                "--new-window",
                "--user-data-dir",
                str(user_data_dir),
                "--extensionDevelopmentPath",
                str(vscode_extension_path),
                "--wait",
                str(file_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=os.setsid,
        )
        deadline = monotonic() + timeout_sec
        while monotonic() < deadline:
            event, parse_errors = find_event(str(probe["text_sha256"]), 520)
            if isinstance(event, dict):
                break
            sleep(0.5)
    except Exception as exc:
        errors.append({"error": repr(exc)[:500]})
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    killpg(getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=5.0)
            except Exception:
                try:
                    if proc.poll() is None:
                        killpg(getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
                try:
                    stdout, stderr = proc.communicate(timeout=2.0)
                except Exception:
                    stdout, stderr = "", ""
            stdout_tail = str(stdout or "")[-1000:]
            stderr_tail = str(stderr or "")[-1000:]
            code_returncode = getattr(proc, "returncode", None)
        cleanup_actions = terminate_processes(str(user_data_dir))

    event_ok = _editor_callback_event_ok(event, probe)
    ok = bool(event_ok and not parse_errors and not errors)
    return {
        "schema": f"{schema_prefix}_typing_editor_callback_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "source_adapter": "editor_extension_explicit",
        "probe": {
            "text_sha256": probe["text_sha256"],
            "text_length": probe["text_length"],
            "text_omitted": True,
        },
        "event": event,
        "code": {
            "binary": code_bin,
            "returncode": code_returncode,
            "user_data_dir": str(user_data_dir),
            "target_file": str(file_path),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "cleanup_actions": cleanup_actions[:40],
        },
        "parse_errors": parse_errors[:20],
        "errors": errors[:20],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "internet_access": False,
            "disposable_user_data_dir": True,
            "live_vscode_extension_callback": True,
            "extension_host_edit_selftest_only": True,
        },
        "non_claims": [
            "This selftest opens a disposable VS Code window and applies a safe document edit through the extension host.",
            "It proves the live onDidChangeTextDocument callback route into typed-input ingest; it does not capture raw keys or terminal output.",
        ],
    }
