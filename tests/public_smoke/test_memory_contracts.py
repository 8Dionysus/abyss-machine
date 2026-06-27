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


def _refs(root: str = "/var/lib/abyss-machine/memory") -> tuple[dict[str, str], dict[str, str]]:
    refs = {
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
        "orchestrate_root": f"{root}/orchestrate",
        "orchestrate_latest": f"{root}/orchestrate/latest.json",
        "orchestrate_apply_root": f"{root}/orchestrate/apply",
        "orchestrate_apply_latest": f"{root}/orchestrate/apply/latest.json",
        "orchestrate_idle_root": f"{root}/orchestrate/idle",
        "orchestrate_idle_latest": f"{root}/orchestrate/idle/latest.json",
        "orchestrate_confirm_root": f"{root}/orchestrate/confirm",
        "orchestrate_confirm_latest": f"{root}/orchestrate/confirm/latest.json",
        "orchestrate_executor_root": f"{root}/orchestrate/executor",
        "orchestrate_executor_latest": f"{root}/orchestrate/executor/latest.json",
        "orchestrate_live_root": f"{root}/orchestrate/live",
        "orchestrate_live_latest": f"{root}/orchestrate/live/latest.json",
        "validate_root": f"{root}/validate",
        "validate_latest": f"{root}/validate/latest.json",
    }
    today = {
        "status": f"{root}/status/2026/06/2026-06-25.jsonl",
        "pressure": f"{root}/pressure/2026/06/2026-06-25.jsonl",
        "processes": f"{root}/processes/2026/06/2026-06-25.jsonl",
        "plan": f"{root}/plan/2026/06/2026-06-25.jsonl",
        "headroom": f"{root}/headroom/2026/06/2026-06-25.jsonl",
        "residency": f"{root}/residency/2026/06/2026-06-25.jsonl",
        "hotpath": f"{root}/hotpath/2026/06/2026-06-25.jsonl",
        "orchestrate": f"{root}/orchestrate/2026/06/2026-06-25.jsonl",
        "orchestrate_apply": f"{root}/orchestrate/apply/2026/06/2026-06-25.jsonl",
        "orchestrate_idle": f"{root}/orchestrate/idle/2026/06/2026-06-25.jsonl",
        "orchestrate_confirm": f"{root}/orchestrate/confirm/2026/06/2026-06-25.jsonl",
        "orchestrate_executor": f"{root}/orchestrate/executor/2026/06/2026-06-25.jsonl",
        "orchestrate_live": f"{root}/orchestrate/live/2026/06/2026-06-25.jsonl",
    }
    return refs, today


def test_memory_policy_and_paths_contracts_are_module_owned() -> None:
    policy = memory_contracts.default_policy(schema_prefix="abyss_machine", version="0.8.test")
    loaded = memory_contracts.policy_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        loaded={"thresholds": {}, "actions": {"automatic_kill": False}},
        config_error=None,
    )
    refs, today = _refs()
    paths = memory_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=refs,
        today_paths=today,
    )

    assert policy["schema"] == "abyss_machine_memory_policy_v1"
    assert policy["actions"]["launch_gate_only"] is True
    assert loaded["config_exists"] is True
    assert loaded["defaults_applied"] == ["residency"]
    assert paths["schema"] == "abyss_machine_memory_paths_v1"
    assert paths["commands"]["orchestrate_apply_live"].endswith("--json")
    assert paths["policy_contract"]["automatic_kill"] is False
    assert paths["policy_contract"]["repo_mutation"] is False


def test_memory_pressure_zram_relief_and_launch_gates_are_module_owned() -> None:
    policy = memory_contracts.default_policy(schema_prefix="abyss_machine", version="0.8.test")
    mem = {"summary": {"mem_available_percent": 35}}
    psi = {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}}
    zram_swap = {"devices": [{"name": "/dev/zram0"}], "summary": {"used_percent": 80, "free_mib": 4096}}
    disk_swap = {"devices": [{"name": "/dev/nvme0n1p3"}], "summary": {"used_percent": 80, "free_mib": 4096}}

    relieved_class, relieved_reasons = memory_contracts.pressure_class(mem, psi, zram_swap, policy)
    hard_class, hard_reasons = memory_contracts.pressure_class(mem, psi, disk_swap, policy)
    hot_gate = memory_contracts.launch_gate_for_class("hot", "medium", unattended=True, policy=policy)

    assert memory_contracts.swap_is_zram_only(zram_swap) is True
    assert relieved_class == "warm"
    assert "zram_only_relief_to_warm" in relieved_reasons[0]
    assert hard_class == "critical"
    assert hard_reasons == ["swap_used_percent=80>critical"]
    assert hot_gate["allowed"] is False
    assert hot_gate["blocked_reasons"] == ["memory_hot_blocks_unattended_medium"]


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
    assert plan["recommended_new_work"]["heavy"]["allowed"] is False
    assert plan["recommended_new_work"]["heavy"]["game_guarded"] is True
    assert plan["recommended_new_work"]["medium"]["unattended_allowed"] is False
    assert plan["policy"]["do_not_kill_existing_processes"] is True
    assert attribution["protected_swap_mib"] == 512.0
    assert attribution["operator_review_swap_mib"] == 128.0
    assert attribution["top_cgroup_swap"][0]["protected"] is True


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
    assert payload["schema"] == "abyss_machine_memory_paths_v1"
    assert payload["commands"]["plan"] == "abyss-machine memory plan --json"
    assert payload["policy_contract"]["automatic_zram_reconfigure"] is False
