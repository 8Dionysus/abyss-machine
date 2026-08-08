from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any, Mapping

from . import resource_admission_adapters, resource_adapters


_HEAVY_COMMAND = re.compile(
    r"(?:^|[;&|]\s*)(?:python\d*|pytest|cargo|ninja|make|cmake|npm|pnpm|yarn|podman|docker|ollama|llama-server)\b",
    re.IGNORECASE,
)
_INDEX_COMMAND = re.compile(r"(?:^|[^A-Za-z0-9])(?:index|embedding|rerank|benchmark|train|convert|quantiz)\w*\b", re.IGNORECASE)
_BROAD_SCAN = re.compile(r"(?:^|[;&|]\s*)(?:rg|find|du)\b", re.IGNORECASE)
_EXPLICIT_DEMAND = re.compile(r"(?:^|\s)ABYSS_MEMORY_DEMAND_MIB=(\d+(?:\.\d+)?)\b")


def command_demand(command: str) -> dict[str, Any]:
    explicit = _EXPLICIT_DEMAND.search(command)
    if explicit:
        demand = max(64.0, min(float(explicit.group(1)), 32768.0))
        return {"memory_demand_mib": demand, "class": "sustained", "kind": "generic", "source": "owner_explicit"}
    if _INDEX_COMMAND.search(command):
        return {"memory_demand_mib": 8192.0, "class": "sustained", "kind": "indexing", "source": "codex_command_shape"}
    if _HEAVY_COMMAND.search(command):
        return {"memory_demand_mib": 4096.0, "class": "heavy", "kind": "agent", "source": "codex_command_shape"}
    if _BROAD_SCAN.search(command):
        return {"memory_demand_mib": 2048.0, "class": "medium", "kind": "indexing", "source": "codex_command_shape"}
    return {"memory_demand_mib": 1024.0, "class": "medium", "kind": "generic", "source": "codex_conservative_default"}


def _cgroup_path(pid: int | str = "self") -> str | None:
    try:
        lines = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        hierarchy, controllers, path = line.split(":", 2)
        if hierarchy == "0" and not controllers and path.startswith("/"):
            return path
    return None


def _process_parent(pid: int) -> int:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        return int(fields[3])
    except (OSError, ValueError, IndexError):
        return 0


def owner_process() -> tuple[int, str | None]:
    cgroup = _cgroup_path()
    pid = os.getppid()
    fallback = pid
    visited: set[int] = set()
    while pid > 1 and pid not in visited:
        visited.add(pid)
        if _cgroup_path(pid) != cgroup:
            break
        fallback = pid
        try:
            comm = Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip().lower()
        except OSError:
            comm = ""
        if "codex" in comm:
            return pid, cgroup
        pid = _process_parent(pid)
    return fallback, cgroup


def _identity(event: Mapping[str, Any]) -> tuple[str, str, str]:
    session_id = str(event.get("session_id") or "").strip()
    turn_id = str(event.get("turn_id") or "").strip()
    tool_use_id = str(event.get("tool_use_id") or "").strip()
    if not session_id or not turn_id or not tool_use_id:
        raise ValueError("missing stable Codex hook identity")
    return session_id, turn_id, tool_use_id


def capability_path(event: Mapping[str, Any], environ: Mapping[str, str] | None = None) -> Path:
    session_id, _turn_id, tool_use_id = _identity(event)
    digest = hashlib.sha256(f"{session_id}\0{tool_use_id}".encode("utf-8")).hexdigest()
    return resource_adapters.runtime_root(environ) / "abyss-machine" / "resource" / "codex-hooks" / f"{digest}.json"


def pre_tool(event: Mapping[str, Any], *, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    session_id, turn_id, tool_use_id = _identity(event)
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    command = str(tool_input.get("command") or "")
    demand = command_demand(command)
    owner_pid, owner_cgroup = owner_process()
    if not owner_cgroup:
        raise ValueError("Codex owner cgroup unavailable")
    token = secrets.token_urlsafe(32)
    command_shape = hashlib.sha256(command.encode("utf-8")).hexdigest()[:20]
    request = {
        "owner": "codex",
        "operation": "workload_start",
        "workload_id": f"{session_id}:{tool_use_id}",
        "request_id": tool_use_id,
        "release_token": token,
        "activity": "foreground",
        "importance_class": "protected",
        "data_risk": True,
        "recoverability": "preserve",
        "owner_pid": owner_pid,
        "owner_cgroup": owner_cgroup,
        "class": demand["class"],
        "kind": demand["kind"],
        "latency": "interactive",
        "memory_demand_mib": demand["memory_demand_mib"],
        "demand_key": f"codex:{demand['kind']}:{command_shape}",
        "estimate_source": demand["source"],
        "estimate_confidence": "structural_conservative",
    }
    response = resource_admission_adapters.client_request(
        {"command": "reserve", "request": request},
        path=resource_admission_adapters.socket_path(environ),
        timeout_sec=3.0,
    )
    if response.get("decision") != "allow" or not response.get("ok"):
        reasons = response.get("blocked_reasons") or response.get("denied_reasons") or [response.get("error") or "admission_denied"]
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Abyss memory admission deferred this new command: " + ", ".join(map(str, reasons)),
            }
        }
    lease = response.get("lease") if isinstance(response.get("lease"), dict) else {}
    path = capability_path(event, environ)
    resource_adapters.atomic_write_json(
        path,
        {
            "schema": "abyss_machine_codex_hook_capability_v1",
            "lease_id": lease.get("id"),
            "release_token": token,
            "session_id": session_id,
            "turn_id": turn_id,
            "tool_use_id": tool_use_id,
            "runtime_only": True,
        },
    )
    return {}


def post_tool(event: Mapping[str, Any], *, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    path = capability_path(event, environ)
    try:
        capability = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    try:
        resource_admission_adapters.client_request(
            {
                "command": "release",
                "request": {
                    "lease_id": capability.get("lease_id"),
                    "release_token": capability.get("release_token"),
                },
            },
            path=resource_admission_adapters.socket_path(environ),
            timeout_sec=3.0,
        )
    finally:
        path.unlink(missing_ok=True)
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event", choices=("pre", "post"))
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Codex hook input too large")
        event = json.loads(raw.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("Codex hook input must be an object")
        output = pre_tool(event) if args.event == "pre" else post_tool(event)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.event == "pre":
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Abyss memory admission unavailable: {type(exc).__name__}",
                }
            }
        else:
            output = {}
    sys.stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
