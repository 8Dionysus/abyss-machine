from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import memory_contracts


def _refs(root: str = "/var/lib/abyss-machine/memory") -> dict[str, str]:
    return {
        "root": root,
        "agent_entrypoint": f"{root}/AGENTS.md",
        "index": f"{root}/index.json",
        "latest": f"{root}/latest.json",
        "policy": "/etc/abyss-machine/memory-policy.json",
        "status_root": f"{root}/status",
        "pressure_root": f"{root}/pressure",
        "pressure_latest": f"{root}/pressure/latest.json",
        "process_root": f"{root}/processes",
        "process_latest": f"{root}/processes/latest.json",
        "plan_root": f"{root}/plan",
        "plan_latest": f"{root}/plan/latest.json",
        "headroom_root": f"{root}/headroom",
        "headroom_latest": f"{root}/headroom/latest.json",
        "residency_root": f"{root}/residency",
        "residency_latest": f"{root}/residency/latest.json",
        "residency_spec": f"{root}/residency/SPEC.md",
        "hotpath_root": f"{root}/hotpath",
        "hotpath_latest": f"{root}/hotpath/latest.json",
        "validate_root": f"{root}/validate",
        "validate_latest": f"{root}/validate/latest.json",
    }


def test_memory_policy_and_paths_contracts_are_module_owned() -> None:
    policy = memory_contracts.default_policy(schema_prefix="abyss_machine", version="0.8.test")
    loaded = memory_contracts.policy_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        loaded={
            "thresholds": {"swap_used_percent": {"critical_above": 1}},
            "actions": {"automatic_kill": True, "launch_gate_only": True, "numeric_workload_gating": True},
            "launch_gates": {"critical": {"block_classes": ["medium"]}},
            "zram_swap_relief": {"enabled": True},
        },
        config_error=None,
    )
    refs = _refs()
    paths = memory_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=refs,
    )

    assert policy["schema"] == "abyss_machine_memory_policy_v1"
    assert policy["actions"]["numeric_workload_gating"] is False
    assert policy["actions"]["owner_offer_required_for_existing_process_action"] is True
    assert loaded["config_exists"] is True
    assert loaded["defaults_applied"] == ["residency", "swap_reserve"]
    assert loaded["swap_reserve"]["enabled"] is True
    assert loaded["actions"]["automatic_kill"] is False
    assert loaded["actions"]["numeric_workload_gating"] is False
    assert "launch_gate_only" not in loaded["actions"]
    assert "launch_gates" not in loaded
    assert "zram_swap_relief" not in loaded
    assert "swap_used_percent" not in loaded["thresholds"]
    assert paths["schema"] == "abyss_machine_memory_paths_v3"
    for lane in ("status", "pressure", "processes", "plan", "headroom", "residency", "hotpath"):
        assert paths[lane]["retention"] == "latest_only"
        assert "today" not in paths[lane]
        assert "daily_glob" not in paths[lane]
    assert "orchestrate" not in paths
    assert all("orchestrate" not in command for command in paths["commands"].values())
    assert paths["policy_contract"]["automatic_kill"] is False
    assert paths["policy_contract"]["repo_mutation"] is False


def test_memory_pressure_swap_reserve_and_importance_are_separate() -> None:
    policy = memory_contracts.default_policy(schema_prefix="abyss_machine", version="0.8.test")
    mem = {"summary": {"mem_available_percent": 35}}
    psi = {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}}
    zram_swap = {"devices": [{"name": "/dev/zram0"}], "summary": {"total_mib": 20000, "used_mib": 19488, "used_percent": 97.44, "free_mib": 512}}
    disk_swap = {"devices": [{"name": "/dev/nvme0n1p3"}], "summary": {"total_mib": 20000, "used_mib": 19488, "used_percent": 97.44, "free_mib": 512}}

    relieved_class, relieved_reasons = memory_contracts.pressure_class(mem, psi, zram_swap, policy)
    hard_class, hard_reasons = memory_contracts.pressure_class(mem, psi, disk_swap, policy)
    reserve = memory_contracts.swap_reserve_status(zram_swap, policy)

    assert memory_contracts.swap_is_zram_only(zram_swap) is True
    assert relieved_class == hard_class == "green"
    assert relieved_reasons == hard_reasons == ["no_active_memory_pressure_observed"]
    assert reserve["state"] == "below_target"
    assert reserve["shortfall_mib"] == 1536.0
    assert reserve["pressure_authority"] is False
    assert reserve["action_authority"] is False


def test_memory_plan_and_headroom_attribution_contracts_are_module_owned() -> None:
    policy = memory_contracts.default_policy(schema_prefix="abyss_machine", version="0.8.test")
    plan = memory_contracts.plan_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        pressure={"ok": True, "class": "watch", "reasons": ["fixture"], "summary": {"class": "watch"}},
        policy=policy,
        mode={"selected_mode": "balanced", "effective_mode": "balanced"},
        game_guard={"active": True, "platform_present": True, "summary": {"games": 1}},
        paths={"latest": "/var/lib/abyss-machine/memory/latest.json"},
        pressure_latest="/var/lib/abyss-machine/memory/pressure/latest.json",
        game_guard_latest="/var/lib/abyss-machine/processes/game-guard/latest.json",
    )
    attribution = memory_contracts.headroom_process_buckets(
        {
            "top": {
                "cgroup_swap": [
                    {
                        "unit": "abyss-tts-server.service",
                        "workload_hint": "normal",
                        "capability_role": "tts",
                        "swap_current_kib": 512 * 1024,
                        "process_pss_rollup_kib": 256 * 1024,
                    },
                    {
                        "unit": "browser.service",
                        "workload_hint": "browser",
                        "capability_role": "none",
                        "swap_current_kib": 128 * 1024,
                        "process_pss_rollup_kib": 512 * 1024,
                    },
                ]
            }
        },
        protected_roles={"tts", "dictation"},
    )

    assert plan["schema"] == "abyss_machine_memory_plan_v1"
    assert "recommended_new_work" not in plan
    assert plan["policy"]["numeric_workload_gating"] is False
    assert plan["policy"]["do_not_kill_existing_processes"] is True
    assert attribution["protected_owner_context_swap_mib"] == 512.0
    assert attribution["owner_state_unknown_swap_mib"] == 128.0
    assert attribution["top_cgroup_swap"][0]["protected"] is True
    assert attribution["top_cgroup_swap"][1]["route"] == "owner_state_required_before_action"
    assert attribution["action_authority"] is False


def test_memory_paths_cli_uses_public_contract_shape_without_live_collection() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "memory", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_memory_paths_v3"
    assert payload["commands"]["plan"] == "abyss-machine memory plan --json"
    assert payload["policy_contract"]["automatic_zram_reconfigure"] is False


def test_memory_cli_does_not_expose_numeric_orchestrate_route() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "memory", "orchestrate", "plan", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )

    assert result.returncode == 2
    assert "invalid choice: 'orchestrate'" in result.stderr
