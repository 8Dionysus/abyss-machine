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
