from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import storage_contracts


def test_storage_pressure_classes_and_threshold_bytes_are_stable() -> None:
    assert storage_contracts.pressure_class(None, 80.0, 90.0, 5.0) == "unknown"
    assert storage_contracts.pressure_class(70.0, 80.0, 90.0, 5.0) == "green"
    assert storage_contracts.pressure_class(77.0, 80.0, 90.0, 5.0) == "watch"
    assert storage_contracts.pressure_class(84.0, 80.0, 90.0, 5.0) == "warning"
    assert storage_contracts.pressure_class(92.0, 80.0, 90.0, 5.0) == "critical"

    thresholds = storage_contracts.threshold_bytes(
        {"total_bytes": 1000, "used_bytes": 850},
        80.0,
    )
    assert thresholds["threshold_bytes"] == 800
    assert thresholds["bytes_to_threshold"] == 0
    assert thresholds["bytes_over_threshold"] == 50


def test_storage_policy_env_and_inventory_drift_contracts() -> None:
    values = storage_contracts.parse_policy_env_lines([
        "# ignored",
        "ABYSS_MACHINE_CACHE_ROOT='/srv/abyss-machine/cache'",
        "BROKEN",
        'TMPDIR="/srv/abyss-machine/tmp"',
    ])
    assert values == {
        "ABYSS_MACHINE_CACHE_ROOT": "/srv/abyss-machine/cache",
        "TMPDIR": "/srv/abyss-machine/tmp",
    }

    gib = 1024 * 1024 * 1024
    drift = storage_contracts.inventory_drift(
        [
            {"id": "cache-a", "path": "/var/cache/a", "exists": True, "size_bytes": 2 * gib},
            {"id": "cache-b", "path": "/var/cache/b", "exists": True, "size_bytes": 100},
        ],
        {"items": [{"id": "cache-a", "path": "/var/cache/a", "size_bytes": gib}, {"id": "gone", "path": "/tmp/gone", "size_bytes": 1}]},
    )
    assert drift["baseline"] == "compared"
    assert drift["grown"][0]["id"] == "cache-a"
    assert drift["new"][0]["id"] == "cache-b"
    assert drift["missing"][0]["id"] == "gone"


def test_storage_pressure_recommendations_do_not_authorize_deletion(tmp_path: Path) -> None:
    machine_root = tmp_path / "srv" / "abyss-machine"
    candidates = [
        {
            "id": "root-cache",
            "path": "/var/cache/libdnf5",
            "exists": True,
            "category": "package_cache",
            "size_bytes": 200,
            "tags": ["root"],
            "reason": "package cache",
        },
        {
            "id": "work-project",
            "path": "/srv/work/project",
            "exists": True,
            "category": "cleanup_candidate",
            "size_bytes": 999999,
            "tags": ["work"],
            "reason": "must stay protected",
        },
    ]

    recommendations = storage_contracts.pressure_recommendations(
        candidates,
        "warning",
        "green",
        abyss_machine_root=machine_root,
    )

    assert recommendations[0]["action"] == "review_root_pressure_candidate"
    assert all(item.get("id") != "work-project" for item in recommendations)
    assert recommendations[-1] == {
        "priority": 9,
        "action": "generate_cleanup_plan_before_deletion",
        "command": "abyss-machine storage cleanup-plan --json",
        "reason": "Pressure facts do not authorize deletion; cleanup-plan adds process guard and hook context.",
    }


def test_storage_protection_and_cleanup_actions_are_operator_gated(tmp_path: Path) -> None:
    machine_root = tmp_path / "srv" / "abyss-machine"
    roots = storage_contracts.default_protected_roots(
        abyss_machine_root=machine_root,
        abyss_stack_user_source_root=tmp_path / "src" / "abyss-stack",
    )
    protected = storage_contracts.protected_roots({"document": {}}, roots)

    allowed = storage_contracts.path_protection(machine_root / "cache" / "x", abyss_machine_root=machine_root, protected_roots=protected)
    work = storage_contracts.path_protection(Path("/srv/work/client"), abyss_machine_root=machine_root, protected_roots=protected)
    unknown_srv = storage_contracts.path_protection(Path("/srv/not-allowlisted"), abyss_machine_root=machine_root, protected_roots=protected)

    assert allowed["decision"] == "allow_candidate"
    assert work["decision"] == "deny"
    assert work["owner"] == "operator_work"
    assert unknown_srv["decision"] == "deny"
    assert unknown_srv["class"] == "srv_unknown_protected"

    action = storage_contracts.cleanup_action_for_item(
        {
            "id": "work-project",
            "path": "/srv/work/client",
            "exists": True,
            "category": "cleanup_candidate",
            "size_bytes": 100,
            "tags": ["work"],
        },
        guard_by_path={"/srv/work/client": {"status": "clear", "active": False}},
        abyss_machine_root=machine_root,
    )
    assert action["safe_automatic_cleanup"] is False
    assert action["readiness"] == "blocked"
    assert "work_path_protected" in action["blocked_reasons"]


def test_storage_write_preflight_decision_keeps_large_writes_on_host_owned_routes(tmp_path: Path) -> None:
    decision = storage_contracts.write_preflight_decision(
        kind="model-cache",
        requested_bytes=2 * 1024 * 1024 * 1024,
        protection={"class": "system_root", "decision": "reroute_for_large_generated_data"},
        pressure_summary={"root_pressure_class": "green"},
        target_usage={"free_bytes": 20 * 1024 * 1024 * 1024},
        recommended_usage={"free_bytes": 20 * 1024 * 1024 * 1024},
        large_write_threshold=1024 * 1024 * 1024,
        min_free_after=5 * 1024 * 1024 * 1024,
    )
    assert decision["decision"] == "reroute"
    assert "large_generated_write_on_system_root" in decision["reasons"]

    denied = storage_contracts.write_preflight_decision(
        kind="unknown",
        requested_bytes=1,
        protection={"class": "host_owned_allowed", "decision": "allow_candidate"},
        pressure_summary={},
        target_usage={"free_bytes": 10},
        recommended_usage={"free_bytes": 10},
        large_write_threshold=1024,
        min_free_after=1,
    )
    assert denied["decision"] == "deny"
    assert denied["reasons"] == ["invalid_kind"]

    recommended = storage_contracts.preflight_recommended_target(
        "artifact",
        tmp_path / "unsafe name!.bin",
        routes={"artifact": tmp_path / "artifacts"},
    )
    assert recommended.endswith("/artifacts/unsafe-name-.bin")


def test_vault_archive_routes_are_explicit_and_suffix_bound(tmp_path: Path) -> None:
    source_prefix = tmp_path / "source" / "owner"
    destination_prefix = tmp_path / "vault" / "owner"
    route = {
        "id": "owner-vault",
        "kind": "vault-archive",
        "owner": "fixture-owner",
        "source_prefix": str(source_prefix) + "/",
        "destination_prefix": str(destination_prefix) + "/",
        "required_mount_ref": "vault.mount",
        "device_label_ref": "vault.device_label",
        "luks_mapper_ref": "vault.luks_mapper",
        "uuid_source": "runtime",
    }

    assert storage_contracts.validate_archive_routes([]) == {"ok": True, "routes": [], "errors": []}
    denied = storage_contracts.archive_route_match(destination_prefix / "result.json", [])
    assert denied["decision"] == "deny"
    assert denied["reason"] == "archive_route_not_configured"

    allowed = storage_contracts.archive_route_match(destination_prefix / "result.json", [route])
    assert allowed["decision"] == "allow_candidate"
    assert allowed["class"] == "vault_archive_allowed"
    assert allowed["owner"] == "fixture-owner"

    pair = storage_contracts.archive_route_pair(
        source_prefix / "result.json",
        destination_prefix / "result.json",
        route,
    )
    assert pair["ok"] is True
    mismatch = storage_contracts.archive_route_pair(
        source_prefix / "other.json",
        destination_prefix / "result.json",
        route,
    )
    assert mismatch == {"ok": False, "reason": "archive_route_suffix_mismatch"}
    requested = destination_prefix / "result.json"
    assert storage_contracts.preflight_recommended_target(
        "vault-archive",
        requested,
        routes={"artifact": tmp_path / "artifacts", "vault-archive": destination_prefix},
    ) == str(requested)


def test_vault_archive_preflight_requires_explicit_route_class() -> None:
    allowed = storage_contracts.write_preflight_decision(
        kind="vault-archive",
        requested_bytes=1024,
        protection={"class": "vault_archive_allowed", "decision": "allow_candidate"},
        pressure_summary={"root_pressure_class": "critical"},
        target_usage={"available_to_user_bytes": 20 * 1024 * 1024 * 1024},
        recommended_usage={"available_to_user_bytes": 20 * 1024 * 1024 * 1024},
        large_write_threshold=1024,
        min_free_after=1,
    )
    assert allowed["decision"] == "allow"

    denied = storage_contracts.write_preflight_decision(
        kind="vault-archive",
        requested_bytes=1024,
        protection={"class": "host_owned_allowed", "decision": "allow_candidate"},
        pressure_summary={},
        target_usage={"free_bytes": 20 * 1024 * 1024 * 1024},
        recommended_usage={"free_bytes": 20 * 1024 * 1024 * 1024},
        large_write_threshold=1024,
        min_free_after=1,
    )
    assert denied["decision"] == "deny"
    assert denied["reasons"] == ["archive_route_required"]


def test_storage_paths_cli_surface_is_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "storage", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_storage_paths_v1"
    assert payload["policy"].endswith("storage-policy.json")
    assert payload["large_roots"]["machine"].startswith("/srv/")
    assert payload["apply"]["dry_run_command"] == "abyss-machine storage apply --action-id ID --dry-run --json"
    assert payload["lifecycle"]["root"].endswith("/storage/lifecycle")
    assert payload["lifecycle"]["commands"]["reap"].endswith("--limit 1 --scan-limit 8 --json")


def test_storage_monitor_timer_reserves_measured_startup_memory() -> None:
    unit = (ROOT / "systemd" / "user" / "abyss-storage-monitor.service").read_text(encoding="utf-8")
    lines = unit.splitlines()
    pre_index = next(index for index, line in enumerate(lines) if line.startswith("ExecStartPre="))
    start_index = next(index for index, line in enumerate(lines) if line.startswith("ExecStart="))
    assert pre_index < start_index
    assert lines[pre_index].endswith("/abyss-machine storage capacity --json")
    assert "TimeoutStartSec=3min" in unit

    exec_start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))

    assert " resource launch --class medium --kind indexing --unattended " in exec_start
    assert " --timeout 110 " in exec_start
    assert " --memory-demand-mib 2048 " in exec_start
    assert " --demand-key abyss-machine:storage-monitor:hourly " in exec_start
    assert " --demand-owner abyss-machine-storage " in exec_start
    assert " --estimate-source measured-systemd-unit-p99 " in exec_start
    assert " --estimate-confidence high " in exec_start
    assert " --success-on-block " in exec_start
    assert exec_start.endswith("/abyss-machine storage monitor --json")
    assert "MemoryHigh=" not in unit
    assert "MemoryMax=" not in unit
