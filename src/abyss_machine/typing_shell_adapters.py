from __future__ import annotations

import hashlib
from pathlib import Path
import shlex
from typing import Any, Mapping


ZSH_HOOK_SELFTEST_TEXT = "print abyss-zsh-hook-selftest"


def _nested_get(data: Mapping[str, Any] | None, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def zsh_hook_expected_markers() -> list[str]:
    return [
        "Abyss typing committed shell-command adapter",
        "_abyss_typing_preexec",
        "--source zsh_preexec",
        "shell_command cwd=",
        "abyss-typing-zsh-v1",
        "ABYSS_TYPING_HOOK_DISABLE_REGISTER",
    ]


def zshrc_sources_hook(text: str) -> bool:
    lowered = str(text or "").lower()
    return "source" in lowered and ".config/zsh/abyss-typing.zsh" in lowered


def zsh_hook_function_probe_plan(
    *,
    hook_path: str | Path,
    zsh_available: bool,
    hook_exists: bool,
) -> dict[str, Any]:
    if not zsh_available:
        return {"run": False, "result": {"ok": False, "returncode": 127, "error": "zsh not found"}}
    if not hook_exists:
        return {"run": False, "result": {"ok": False, "returncode": 66, "error": "hook file missing"}}
    script = "\n".join(
        [
            f"source {shlex.quote(str(hook_path))}",
            "typeset -f _abyss_typing_preexec >/dev/null",
        ]
    )
    return {
        "run": True,
        "command": ["env", "ABYSS_TYPING_HOOK_DISABLE_REGISTER=1", "zsh", "-fic", script],
        "timeout_sec": 3.0,
    }


def zsh_hook_function_probe_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(raw.get("ok")),
        "returncode": raw.get("returncode"),
        "stderr": str(raw.get("stderr") or "")[-500:],
    }


def zsh_hook_status_document(
    *,
    generated_at: str,
    hook_path: str | Path,
    hook_exists: bool,
    hook_size_bytes: int,
    hook_text: str,
    hook_read_error: str | None,
    zshrc_path: str | Path,
    zshrc_exists: bool,
    zshrc_text: str,
    zshrc_read_error: str | None,
    function_probe: Mapping[str, Any],
    latest_selftest: Mapping[str, Any] | None,
    latest_selftest_error: str | None,
    latest_event: Mapping[str, Any],
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    markers = zsh_hook_expected_markers()
    missing_markers = [marker for marker in markers if marker not in str(hook_text or "")]
    source_declared = zshrc_sources_hook(zshrc_text)
    ok = bool(hook_exists and zshrc_exists and source_declared and not missing_markers and function_probe.get("ok"))
    return {
        "schema": f"{schema_prefix}_typing_zsh_hook_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "ready" if ok else "needs_attention",
        "hook": {
            "path": str(hook_path),
            "exists": hook_exists,
            "size_bytes": hook_size_bytes if hook_exists else 0,
            "read_error": hook_read_error,
            "expected_markers": markers,
            "missing_markers": missing_markers,
            "function_probe": dict(function_probe),
        },
        "zshrc": {
            "path": str(zshrc_path),
            "exists": zshrc_exists,
            "read_error": zshrc_read_error,
            "sources_hook": source_declared,
        },
        "latest_selftest": {
            "exists": isinstance(latest_selftest, Mapping),
            "ok": latest_selftest.get("ok") if isinstance(latest_selftest, Mapping) else None,
            "generated_at": latest_selftest.get("generated_at") if isinstance(latest_selftest, Mapping) else None,
            "event_detected": _nested_get(latest_selftest, ["summary", "event_detected"]) if isinstance(latest_selftest, Mapping) else None,
            "error": latest_selftest_error,
        },
        "latest_typing_event": {
            "ok": latest_event.get("ok"),
            "generated_at": latest_event.get("generated_at"),
            "source_adapter": latest_event.get("source_adapter"),
            "status": latest_event.get("status"),
        },
        "policy": {
            "adapter": "zsh_preexec",
            "committed_shell_commands_only": True,
            "raw_keylogging": False,
            "terminal_output_captured": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
        "commands": {
            "status": "abyss-machine typing zsh-hook-status --json",
            "selftest": "abyss-machine typing zsh-hook-selftest --json",
        },
        "non_claims": [
            "zsh hook status proves the hook file and shell function load; it does not prove every active terminal already re-sourced .zshrc.",
            "The hook observes submitted shell commands only, not keystrokes or command output.",
        ],
    }


def zsh_hook_probe_event_from_records(
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    text_sha256: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    for record in records:
        if not isinstance(record, dict):
            continue
        text_payload = record.get("text") if isinstance(record.get("text"), Mapping) else {}
        if record.get("source_adapter") == "zsh_preexec" and text_payload.get("text_sha256") == text_sha256:
            return {
                "event_id": record.get("event_id"),
                "generated_at": record.get("generated_at"),
                "status": record.get("status"),
                "source_adapter": record.get("source_adapter"),
                "capture_gate_decision": _nested_get(record, ["capture_gate", "decision"]),
                "recipient": _nested_get(record, ["causal_context", "recipient", "kind"]),
                "project": _nested_get(record, ["causal_context", "where", "project", "id"]),
            }, errors
    return None, errors


def zsh_hook_selftest_plan(*, hook_path: str | Path, probe_text: str = ZSH_HOOK_SELFTEST_TEXT) -> dict[str, Any]:
    probe_hash = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    script = "\n".join(
        [
            f"source {shlex.quote(str(hook_path))}",
            "typeset -f _abyss_typing_preexec >/dev/null || exit 17",
            f"_abyss_typing_preexec {shlex.quote(probe_text)}",
            "sleep 1.0",
        ]
    )
    return {
        "probe": {
            "source_adapter": "zsh_preexec",
            "text": probe_text,
            "text_sha256": probe_hash,
            "text_length": len(probe_text),
        },
        "command": ["env", "ABYSS_TYPING_HOOK_DISABLE_REGISTER=1", "zsh", "-fic", script],
        "timeout_sec": 5.0,
    }


def zsh_hook_selftest_not_ready_result() -> dict[str, Any]:
    return {"ok": False, "returncode": 66, "error": "zsh hook status is not ready"}


def zsh_hook_selftest_run_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(raw.get("ok")),
        "returncode": raw.get("returncode"),
        "stderr": str(raw.get("stderr") or "")[-500:],
    }


def zsh_hook_selftest_document(
    *,
    generated_at: str,
    status_before: Mapping[str, Any],
    plan: Mapping[str, Any],
    run_result: Mapping[str, Any],
    event: dict[str, Any] | None,
    parse_errors: list[dict[str, Any]],
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    probe = plan.get("probe") if isinstance(plan.get("probe"), Mapping) else {}
    event_detected = isinstance(event, dict)
    ok = bool(status_before.get("ok")) and bool(run_result.get("ok")) and event_detected and not parse_errors
    return {
        "schema": f"{schema_prefix}_typing_zsh_hook_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "summary": {
            "hook_ready_before": bool(status_before.get("ok")),
            "function_invoked": bool(run_result.get("ok")),
            "event_detected": event_detected,
            "parse_errors": len(parse_errors),
        },
        "probe": {
            "source_adapter": "zsh_preexec",
            "text_sha256": probe.get("text_sha256"),
            "text_length": probe.get("text_length"),
            "text_omitted": True,
        },
        "hook_status": {
            "status": status_before.get("status"),
            "hook": status_before.get("hook"),
            "zshrc": status_before.get("zshrc"),
        },
        "run": dict(run_result),
        "event": event,
        "parse_errors": parse_errors[:20],
        "policy": {
            "committed_shell_commands_only": True,
            "raw_keylogging": False,
            "terminal_output_captured": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
        "non_claims": [
            "This selftest submits a harmless synthetic shell command through the zsh_preexec adapter.",
            "Passing selftest proves the adapter path can ingest now; old terminal sessions may still need a new shell or re-source .zshrc.",
        ],
    }
