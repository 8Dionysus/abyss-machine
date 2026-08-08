from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_codex_hook


HOOK_FRAGMENT = ROOT / "manifests" / "codex-hooks" / "abyss-memory-admission.fragment.json"


def event(command: str = "python index.py") -> dict[str, object]:
    return {
        "session_id": "session-123",
        "turn_id": "turn-456",
        "tool_use_id": "tool-789",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def test_codex_hook_classifies_demand_without_assigning_importance() -> None:
    explicit = resource_codex_hook.command_demand("ABYSS_MEMORY_DEMAND_MIB=12288 python model.py")
    indexing = resource_codex_hook.command_demand("python build_index.py")
    ordinary = resource_codex_hook.command_demand("git status --short")

    assert explicit["memory_demand_mib"] == 12288.0
    assert explicit["source"] == "owner_explicit"
    assert indexing["kind"] == "indexing"
    assert ordinary["memory_demand_mib"] == 1024.0
    assert "importance" not in explicit


def test_codex_hook_owner_fragment_routes_only_bash_pre_and_post() -> None:
    fragment = json.loads(HOOK_FRAGMENT.read_text(encoding="utf-8"))

    assert fragment["owner"] == "abyss-machine"
    assert fragment["bindings"] == []
    assert set(fragment["hooks"]) == {"PreToolUse", "PostToolUse"}
    for event, phase in (("PreToolUse", "pre"), ("PostToolUse", "post")):
        group = fragment["hooks"][event][0]
        assert group["matcher"] == "^Bash$"
        assert group["hooks"][0]["command"] == f"/usr/local/bin/abyss-machine resource codex-hook {phase}"


def test_codex_pre_and_post_hold_only_runtime_capability(tmp_path: Path, monkeypatch: object) -> None:
    requests: list[dict[str, object]] = []

    def client(payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
        requests.append(payload)
        if payload["command"] == "reserve":
            return {"ok": True, "decision": "allow", "lease": {"id": "runtime-workload:fixture"}}
        return {"ok": True, "decision": "allow", "released": True}

    monkeypatch.setattr(resource_codex_hook.resource_admission_adapters, "client_request", client)
    monkeypatch.setattr(resource_codex_hook, "owner_process", lambda: (4242, "/user.slice/session.scope"))
    environ = {"XDG_RUNTIME_DIR": str(tmp_path)}

    assert resource_codex_hook.pre_tool(event(), environ=environ) == {}
    path = resource_codex_hook.capability_path(event(), environ)
    capability = json.loads(path.read_text(encoding="utf-8"))
    assert capability["lease_id"] == "runtime-workload:fixture"
    assert "python index.py" not in path.read_text(encoding="utf-8")
    reserve = requests[0]["request"]
    assert reserve["importance_class"] == "protected"
    assert reserve["data_risk"] is True
    assert reserve["recoverability"] == "preserve"

    assert resource_codex_hook.post_tool(event(), environ=environ) == {}
    assert not path.exists()
    assert requests[1]["command"] == "release"


def test_codex_pre_returns_supported_deny_shape(monkeypatch: object) -> None:
    monkeypatch.setattr(resource_codex_hook, "owner_process", lambda: (4242, "/user.slice/session.scope"))
    monkeypatch.setattr(
        resource_codex_hook.resource_admission_adapters,
        "client_request",
        lambda *_args, **_kwargs: {
            "ok": False,
            "decision": "force_required",
            "blocked_reasons": ["runtime_projected_mem_available_below_hard_reserve"],
        },
    )

    result = resource_codex_hook.pre_tool(event("pytest -q"))

    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert "hard_reserve" in output["permissionDecisionReason"]
