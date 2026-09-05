from __future__ import annotations

import datetime as dt
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import cli
from abyss_machine import storage_adapters
from abyss_machine import storage_candidate_contracts
from abyss_machine import storage_contracts
from abyss_machine import storage_reservations
from abyss_machine import ai_runtime_contracts


def test_policy_user_binding_does_not_embed_operator_placeholder(monkeypatch) -> None:
    test_home = Path("/home/testing-user")
    monkeypatch.setattr(cli, "ABYSS_USER_HOME", test_home)
    monkeypatch.setattr(cli, "ABYSS_MACHINE_CACHE_ROOT", Path("/srv/abyss-machine/cache"))

    assert cli.rootless_podman_target_graphroot() == Path(
        "/srv/abyss-machine/storage/home/testing-user/containers/storage"
    )
    assert cli.routed_home_cache_path("pip") == Path(
        "/srv/abyss-machine/cache/home/testing-user/cache/pip"
    )
    assert "operator" not in str(cli.routed_home_cache_path("pip"))


def test_ai_subprocess_cache_routes_follow_policy_home() -> None:
    env = ai_runtime_contracts.subprocess_env(
        {"ABYSS_USER_HOME": "/home/testing-user"},
        machine_cache_root=Path("/srv/abyss-machine/cache"),
        ai_cache_root=Path("/srv/abyss-machine/cache/ai"),
        tmp_root=Path("/srv/abyss-machine/tmp"),
        openvino_cache_root=Path("/srv/abyss-machine/cache/ai/openvino"),
    )
    assert env["XDG_CACHE_HOME"] == "/srv/abyss-machine/cache/home/testing-user/cache"
    assert env["PIP_CACHE_DIR"] == "/srv/abyss-machine/cache/home/testing-user/cache/pip"
    assert "operator" not in env["PIP_CACHE_DIR"]


def test_physical_measurement_keeps_du_basis_explicit(tmp_path: Path) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    calls: list[list[str]] = []

    def runner(command, timeout):
        calls.append(list(command))
        return {"ok": True, "stdout": "4096\t" + str(target) + "\n"}

    physical = storage_adapters.measure_path_physical_size_bytes(
        target,
        timeout=3.0,
        command_exists=lambda name: name == "du",
        command_runner=runner,
    )
    assert physical == 4096
    assert calls == [["du", "-sx", "-B1", str(target)]]


def test_disk_capacity_exposes_user_available_and_reserved_blocks(tmp_path: Path) -> None:
    class Stat:
        f_frsize = 100
        f_blocks = 100
        f_bfree = 20
        f_bavail = 12

    summary = storage_adapters.disk_usage_summary(
        tmp_path / "missing",
        disk_usage=lambda path: (8000, 6000, 2000),
        statvfs=lambda path: Stat(),
    )
    assert summary["available_to_user_bytes"] == 1200
    assert summary["reserved_bytes"] == 800
    assert summary["capacity_basis"] == "statvfs"


def test_inventory_reports_physical_primary_and_apparent_companion(tmp_path: Path) -> None:
    target = tmp_path / "cache"
    target.mkdir()
    item = storage_adapters.inventory_item_status(
        {"id": "cache", "path": str(target), "category": "rebuildable_cache"},
        measure=True,
        physical_size_bytes=lambda path, timeout: 8,
        apparent_size_bytes=lambda path, timeout: 12,
    )
    assert item["size_bytes"] == 8
    assert item["physical_size_bytes"] == 8
    assert item["apparent_size_bytes"] == 12
    assert item["size_basis"] == "physical"
    assert item["measurement_ok"] is True


def test_candidate_freshness_and_coverage_separate_runtime_and_pressure() -> None:
    now = dt.datetime(2026, 9, 4, tzinfo=dt.timezone.utc)
    freshness = storage_candidate_contracts.freshness_status(
        generated_at=now.isoformat(),
        last_deep_at=(now - dt.timedelta(days=3)).isoformat(),
        now_time=now,
        max_age_seconds=2 * 86400,
    )
    assert freshness["status"] == "stale"
    coverage = storage_candidate_contracts.coverage_summary([
        {
            "candidate_id": "reclaim-a",
            "path": "/srv/cache/a",
            "physical_bytes": 10,
            "reclaimable_bytes": 10,
            "fingerprint": {"digest": "abc", "complete": True},
            "evidence": {
                "process_refs": {"checked": True},
                "mount_refs": {"checked": True},
                "service_refs": {"checked": False, "error": "probe failed"},
                "container_refs": {"checked": True},
                "config_refs": {"checked": True},
                "runtime_refs": {"checked": True},
                "physical_size": {"ok": True},
            },
        }
    ])
    assert coverage["runtime_error_count"] == 1
    assert coverage["pressure_finding_count"] == 1
    assert coverage["runtime_errors"][0]["surface"] == "service_refs"
    document = storage_candidate_contracts.candidates_document(
        [
            {
                "candidate_id": "reclaim-" + "a" * 24,
                "path": "/srv/cache/a",
                "owner": "cache-owner",
                "kind": "model_cache",
                "source_adapter": "test",
                "source_id": "test:a",
                "exists": True,
                "physical_bytes": 10,
                "reclaimable_bytes": 10,
                "fingerprint": {"digest": "abc", "complete": True},
                "latest_mtime": "2026-08-01T00:00:00+00:00",
                "observed_at": now.isoformat(),
                "executor": {"type": "owner_cache_cleanup", "owner_specific": True},
                "evidence": {
                    "protection": {"decision": "allow_candidate"},
                    "physical_size": {"checked": True, "ok": True},
                    "process_refs": {"checked": True, "active": False},
                    "mount_refs": {"checked": True, "active": False},
                    "service_refs": {"checked": True, "active": False},
                    "container_refs": {"checked": True, "active": False},
                    "config_refs": {"checked": True, "active": False},
                    "runtime_refs": {"checked": True, "active": False},
                    "active_claims": [],
                    "unique_data": {"status": "clear"},
                    "recovery": {"verified": True, "command": "rebuild"},
                },
            }
        ],
        previous_document=None,
        configured_policy=None,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        paths={"latest": "/tmp/latest.json"},
        deep=True,
    )
    assert document["freshness"]["status"] == "fresh"
    assert document["coverage"]["physical_measured"] == 1
    assert document["runtime_errors"] == []
    assert document["pressure_findings"][0]["candidate_id"] == document["candidates"][0]["candidate_id"]


def test_candidate_deep_refresh_preserves_runtime_errors_from_coverage(monkeypatch) -> None:
    runtime_error = {
        "candidate_id": "candidate-a",
        "surface": "service_refs",
        "error": "service probe failed",
    }

    monkeypatch.setattr(cli, "load_json_document", lambda path: ({}, None))
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", lambda **kwargs: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(
        cli.storage_candidate_contracts,
        "candidates_document",
        lambda observations, **kwargs: {
            "ok": True,
            "candidates": [],
            "coverage": {
                "runtime_errors": [runtime_error],
                "pressure_findings": [],
            },
        },
    )
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)

    assert refreshed["ok"] is False
    assert refreshed["runtime_errors"] == [runtime_error]
    assert refreshed["coverage"]["runtime_error_count"] == 1


def test_owner_candidate_adapter_contains_invalid_utf8(monkeypatch, tmp_path: Path) -> None:
    aoa_root = tmp_path / "aoa"
    script = aoa_root / "scripts" / "aoa_session_memory.py"
    script.parent.mkdir(parents=True)
    script.write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setattr(cli, "DEFAULT_AOA_SESSION_MEMORY_ROOT", aoa_root)

    class Completed:
        returncode = 0
        stdout = b'{"status":"ok"}\xff'
        stderr = b"owner diagnostic\xff"

    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, "kwargs": kwargs})
        return Completed()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = cli.storage_candidate_owner_aoa_document()

    assert result["status"] == "owner_adapter_invalid_json"
    assert "UnicodeDecodeError" not in result["error"]
    assert "text" not in calls[0]["kwargs"]
    assert calls[0]["command"][-2:] == ["--session-work-verification-limit", "0"]


def test_owner_candidate_adapter_preserves_structured_nonzero_blocker(monkeypatch, tmp_path: Path) -> None:
    aoa_root = tmp_path / "aoa"
    script = aoa_root / "scripts" / "aoa_session_memory.py"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setattr(cli, "DEFAULT_AOA_SESSION_MEMORY_ROOT", aoa_root)

    class Completed:
        returncode = 1
        # A producer status cannot become successful merely because a
        # malformed wrapper reports ok=true alongside a non-zero exit.
        stdout = (
            b'{"ok":true,"status":"deferred_active_writer",'
            b'"lock_active":true,"diagnostics":['
            b'"maintenance_lock_active_cleanup_deferred"]}'
        )
        stderr = b""

    monkeypatch.setattr(cli.subprocess, "run", lambda command, **kwargs: Completed())

    result = cli.storage_candidate_owner_aoa_document()

    assert result["ok"] is False
    assert result["status"] == "deferred_active_writer"
    assert result["owner_adapter_returncode"] == 1
    assert result["owner_adapter_command"][-2:] == ["--session-work-verification-limit", "0"]
    assert "owner command returned non-zero status: 1" in result["error"]
    assert "--session-work-verification-limit" in result["error"]
    assert not result["status"].startswith("owner_adapter_invalid_json")


def test_candidate_refresh_propagates_owner_adapter_invalid_json(monkeypatch) -> None:
    generated_at = "2026-09-04T19:00:00+00:00"
    last_deep_at = "2026-09-04T18:00:00+00:00"
    previous = {
        "generated_at": last_deep_at,
        "last_deep_at": last_deep_at,
        "snapshot_id": "reclaim-snapshot-last-good",
        "coverage": {
            "discovered": 1,
            "observed": 1,
            "runtime_errors": [],
            "pressure_findings": [],
            "runtime_error_count": 0,
            "pressure_finding_count": 0,
        },
        "summary": {"candidates": 1, "retired": 0, "runtime_error_count": 0},
        "candidates": [{
            "candidate_id": "reclaim-keep",
            "path": "/srv/abyss-machine/tmp/keep",
            "owner": "test-owner",
            "kind": "generated_tmp",
            "verdict": "blocked_unknown",
            "physical_bytes": 10,
            "reclaimable_bytes": 0,
        }],
    }
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "load_json_document", lambda path: (previous, None))
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "direct_child_specs", lambda *args, **kwargs: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "runtime_specs", lambda root: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "artifact_specs", lambda snapshot: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "huggingface_specs", lambda root: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "git_specs", lambda roots: [])
    monkeypatch.setattr(cli, "artifacts_snapshot", lambda **kwargs: {"ok": True, "records": []})
    monkeypatch.setattr(cli, "command_exists", lambda name: False)
    monkeypatch.setattr(
        cli,
        "storage_candidate_owner_aoa_document",
        lambda: {"status": "owner_adapter_invalid_json", "error": "invalid owner JSON"},
    )
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)

    assert refreshed["ok"] is False
    assert [item["candidate_id"] for item in refreshed["candidates"]] == ["reclaim-keep"]
    assert refreshed["retired"] == []
    assert refreshed["last_deep_at"] == last_deep_at
    assert refreshed["runtime_errors"][0]["surface"] == "discovery"
    assert "owner_adapter_invalid_json" in refreshed["runtime_errors"][0]["error"]
    assert refreshed["summary"]["runtime_error_count"] == 1


def test_candidate_discovery_rejects_owner_adapter_error_document(monkeypatch) -> None:
    def patch_empty_producers(patch) -> None:
        patch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "direct_child_specs", lambda *args, **kwargs: [])
        patch.setattr(cli.storage_candidate_adapters, "runtime_specs", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "artifact_specs", lambda snapshot: [])
        patch.setattr(cli.storage_candidate_adapters, "huggingface_specs", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "git_specs", lambda roots: [])
        patch.setattr(cli, "command_exists", lambda name: False)

    patch_empty_producers(monkeypatch)
    monkeypatch.setattr(cli, "artifacts_snapshot", lambda **kwargs: {"ok": True, "records": []})
    monkeypatch.setattr(
        cli,
        "storage_candidate_owner_aoa_document",
        lambda: {"status": "owner_adapter_failed", "error": "owner command failed"},
    )

    try:
        cli.storage_candidate_discover_specs()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("owner adapter failure must not become an empty discovery")

    assert "aoa_owner_adapter_failed" in message
    assert "owner_adapter_failed" in message


def test_candidate_discovery_reports_deferred_aoa_without_erasing_other_producers(monkeypatch) -> None:
    def patch_empty_producers(patch) -> None:
        patch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "direct_child_specs", lambda *args, **kwargs: [])
        patch.setattr(cli.storage_candidate_adapters, "runtime_specs", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "artifact_specs", lambda snapshot: [])
        patch.setattr(cli.storage_candidate_adapters, "huggingface_specs", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "git_specs", lambda roots: [])
        patch.setattr(cli, "command_exists", lambda name: False)

    patch_empty_producers(monkeypatch)
    monkeypatch.setattr(cli, "artifacts_snapshot", lambda **kwargs: {"ok": True, "records": []})
    monkeypatch.setattr(
        cli,
        "storage_candidate_owner_aoa_document",
        lambda: {
            "status": "deferred_active_writer",
            "ok": False,
            "lock_active": True,
            "error": "maintenance writer is active",
            "owner_adapter_returncode": 1,
        },
    )

    producer_status: dict[str, object] = {}
    specs = cli.storage_candidate_discover_specs(producer_status=producer_status)

    assert specs == []
    assert producer_status["aoa_owner_verdict"] == {
        "source_adapter": "aoa_owner_verdict",
        "owner": "aoa-session-memory",
        "status": "deferred_active_writer",
        "ok": False,
        "deferred": True,
        "lock_active": True,
        "reason": "maintenance writer is active",
        "returncode": 1,
    }


def test_candidate_discovery_rejects_required_producer_failures(monkeypatch) -> None:
    def patch_empty_producers(patch) -> None:
        patch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "direct_child_specs", lambda *args, **kwargs: [])
        patch.setattr(cli.storage_candidate_adapters, "runtime_specs", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "artifact_specs", lambda snapshot: [])
        patch.setattr(cli.storage_candidate_adapters, "huggingface_specs", lambda root: [])
        patch.setattr(cli.storage_candidate_adapters, "git_specs", lambda roots: [])
        patch.setattr(cli, "storage_candidate_owner_aoa_document", lambda: {"status": "nothing_to_do", "ok": True})

    with monkeypatch.context() as patch:
        patch_empty_producers(patch)
        patch.setattr(cli, "artifacts_snapshot", lambda **kwargs: {"ok": False, "error": "snapshot producer failed"})
        try:
            cli.storage_candidate_discover_specs()
        except RuntimeError as exc:
            message = str(exc)
        else:
            raise AssertionError("artifact snapshot failure must not become an empty discovery")
        assert "artifact_snapshot_failed" in message

    with monkeypatch.context() as patch:
        patch_empty_producers(patch)
        patch.setattr(cli, "artifacts_snapshot", lambda **kwargs: {"ok": True, "records": []})
        patch.setattr(cli, "command_exists", lambda name: name == "podman")
        patch.setattr(cli, "run", lambda *args, **kwargs: {"ok": False, "stderr": "podman discovery failed"})
        try:
            cli.storage_candidate_discover_specs()
        except RuntimeError as exc:
            message = str(exc)
        else:
            raise AssertionError("podman failure must not become an empty discovery")
        assert "podman_discovery_failed" in message


def test_candidate_deep_refresh_carries_last_good_on_discovery_error(monkeypatch) -> None:
    generated_at = "2026-09-04T19:00:00+00:00"
    last_deep_at = "2026-09-04T18:00:00+00:00"
    previous = {
        "schema": "abyss_machine_storage_candidates_v1",
        "version": "test",
        "generated_at": last_deep_at,
        "ok": True,
        "deep": True,
        "last_deep_at": last_deep_at,
        "snapshot_id": "reclaim-snapshot-last-good",
        "policy": {"automatic_deletion": False},
        "coverage": {
            "discovered": 1,
            "observed": 1,
            "adapters": ["test"],
            "adapter_count": 1,
            "physical_measured": 1,
            "physical_unknown": 0,
            "fingerprint_complete": 1,
            "fingerprint_incomplete": 0,
            "evidence_complete": 1,
            "evidence_incomplete": 0,
            "runtime_errors": [],
            "pressure_findings": [],
            "runtime_error_count": 0,
            "pressure_finding_count": 0,
        },
        "summary": {
            "candidates": 1,
            "ready": 0,
            "delete_ready": 0,
            "archive_ready": 0,
            "changed": 0,
            "retired": 0,
            "physical_bytes": 10,
            "reclaimable_bytes": 0,
        },
        "candidates": [{
            "candidate_id": "reclaim-keep",
            "path": "/srv/abyss-machine/tmp/keep",
            "owner": "test-owner",
            "kind": "generated_tmp",
            "source_adapter": "test",
            "verdict": "blocked_unknown",
            "physical_bytes": 10,
            "reclaimable_bytes": 0,
        }],
        "retired": [],
        "changes": [],
    }

    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "load_json_document", lambda path: (previous, None))

    def fail_discovery(**kwargs):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(cli, "storage_candidate_discover_specs", fail_discovery)
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)

    assert refreshed["ok"] is False
    assert [item["candidate_id"] for item in refreshed["candidates"]] == ["reclaim-keep"]
    assert refreshed["retired"] == []
    assert refreshed["changes"] == []
    assert refreshed["snapshot_id"] == "reclaim-snapshot-last-good"
    assert refreshed["last_deep_at"] == last_deep_at
    assert refreshed["coverage"]["mode"] == "deep_error_carry_forward"
    assert refreshed["coverage"]["discovered"] == 1
    assert refreshed["coverage"]["runtime_error_count"] == 1
    assert refreshed["runtime_errors"][0]["surface"] == "discovery"
    assert refreshed["summary"]["runtime_error_count"] == 1
    assert refreshed["summary"]["retired"] == 0
    assert refreshed["freshness"]["refresh_failed"] is True


def test_candidate_deep_refresh_carries_last_good_on_observation_error(monkeypatch) -> None:
    generated_at = "2026-09-04T19:00:00+00:00"
    last_deep_at = "2026-09-04T18:00:00+00:00"
    previous = {
        "generated_at": last_deep_at,
        "last_deep_at": last_deep_at,
        "snapshot_id": "reclaim-snapshot-last-good",
        "coverage": {"runtime_errors": [], "pressure_findings": [], "runtime_error_count": 0, "pressure_finding_count": 0},
        "summary": {"candidates": 1, "retired": 0},
        "candidates": [{
            "candidate_id": "reclaim-keep",
            "path": "/srv/abyss-machine/tmp/keep",
            "owner": "test-owner",
            "kind": "generated_tmp",
            "verdict": "blocked_unknown",
            "physical_bytes": 10,
            "reclaimable_bytes": 0,
        }],
    }

    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "load_json_document", lambda path: (previous, None))
    monkeypatch.setattr(
        cli,
        "storage_candidate_discover_specs",
        lambda **kwargs: [{"path": "/srv/abyss-machine/tmp/new", "source_adapter": "test"}],
    )
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli, "storage_path_protection", lambda path: {"decision": "allow_candidate"})

    def fail_observation(*args, **kwargs):
        raise OSError("candidate disappeared during observation")

    monkeypatch.setattr(cli.storage_candidate_adapters, "collect_observation", fail_observation)
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)

    assert refreshed["ok"] is False
    assert [item["candidate_id"] for item in refreshed["candidates"]] == ["reclaim-keep"]
    assert refreshed["retired"] == []
    assert refreshed["last_deep_at"] == last_deep_at
    assert refreshed["refresh_result"]["status"] == "deep_error_carry_forward"
    assert refreshed["runtime_errors"][0]["surface"] == "observation"
    assert refreshed["runtime_errors"][0]["path"] == "/srv/abyss-machine/tmp/new"


def test_candidate_deep_refresh_defers_only_aoa_light_preserves_and_recovers_without_false_retirement(monkeypatch) -> None:
    last_good_at = "2026-09-04T18:00:00+00:00"
    partial_at = "2026-09-04T19:00:00+00:00"
    recovered_at = "2026-09-04T19:05:00+00:00"
    aoa_path = "/srv/abyss-machine/tmp/aoa-session-stage"
    old_path = "/srv/abyss-machine/tmp/old-cache"
    current_path = "/srv/abyss-machine/tmp/current-cache"

    def candidate_observation(
        *,
        candidate_id: str,
        path: str,
        owner: str,
        kind: str,
        source_id: str,
        source_adapter: str,
        observed_at: str,
        physical_bytes: int,
    ) -> dict[str, object]:
        evidence = {
            key: {"checked": True, "active": False}
            for key in (
                "process_refs",
                "mount_refs",
                "service_refs",
                "container_refs",
                "config_refs",
                "runtime_refs",
            )
        }
        evidence.update({
            "protection": {"decision": "allow_candidate"},
            "active_claims": [],
            "physical_size": {"checked": True, "ok": True},
            "unique_data": {"status": "clear"},
            "recovery": {"verified": True, "command": "rebuild"},
        })
        return {
            "candidate_id": candidate_id,
            "path": path,
            "owner": owner,
            "kind": kind,
            "source_id": source_id,
            "source_adapter": source_adapter,
            "exists": True,
            "physical_bytes": physical_bytes,
            "reclaimable_bytes": physical_bytes,
            "fingerprint": {"digest": f"digest-{candidate_id}", "complete": True},
            "latest_mtime": last_good_at,
            "observed_at": observed_at,
            "evidence": evidence,
            "executor": {"type": "test-owner-cleanup", "owner_specific": True},
        }

    aoa_id = storage_candidate_contracts.stable_candidate_id(
        owner="aoa-session-memory",
        kind="aoa_owner_debris",
        path=aoa_path,
        source_id="aoa-maintenance:stage:aoa",
    )
    old_id = storage_candidate_contracts.stable_candidate_id(
        owner="cache-owner",
        kind="generated_tmp",
        path=old_path,
        source_id="tmp:old",
    )
    current_id = storage_candidate_contracts.stable_candidate_id(
        owner="cache-owner",
        kind="generated_tmp",
        path=current_path,
        source_id="tmp:current",
    )
    previous = storage_candidate_contracts.candidates_document(
        [
            candidate_observation(
                candidate_id=aoa_id,
                path=aoa_path,
                owner="aoa-session-memory",
                kind="aoa_owner_debris",
                source_id="aoa-maintenance:stage:aoa",
                source_adapter="aoa_owner_verdict",
                observed_at=last_good_at,
                physical_bytes=12,
            ),
            candidate_observation(
                candidate_id=old_id,
                path=old_path,
                owner="cache-owner",
                kind="generated_tmp",
                source_id="tmp:old",
                source_adapter="tmp_children",
                observed_at=last_good_at,
                physical_bytes=8,
            ),
        ],
        previous_document=None,
        configured_policy={"deep_max_age_seconds": 172800},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=last_good_at,
        paths={},
        deep=True,
    )
    previous["last_deep_at"] = last_good_at
    previous["generated_at"] = last_good_at
    previous["ok"] = True

    latest = {"document": previous}
    refresh_times = iter((partial_at, recovered_at))
    discovery_calls = 0

    def fake_discover(**kwargs):
        nonlocal discovery_calls
        producer_status = kwargs["producer_status"]
        if discovery_calls == 0:
            producer_status["aoa_owner_verdict"] = {
                "source_adapter": "aoa_owner_verdict",
                "owner": "aoa-session-memory",
                "status": "deferred_active_writer",
                "ok": False,
                "deferred": True,
                "lock_active": True,
                "reason": "maintenance writer is active",
                "returncode": 1,
            }
            specs = [{
                "candidate_id": current_id,
                "path": current_path,
                "owner": "cache-owner",
                "kind": "generated_tmp",
                "source_id": "tmp:current",
                "source_adapter": "tmp_children",
            }]
        else:
            producer_status["aoa_owner_verdict"] = {
                "source_adapter": "aoa_owner_verdict",
                "owner": "aoa-session-memory",
                "status": "nothing_to_do",
                "ok": True,
                "deferred": False,
                "lock_active": False,
                "reason": "owner writer is free",
            }
            specs = [
                {
                    "candidate_id": current_id,
                    "path": current_path,
                    "owner": "cache-owner",
                    "kind": "generated_tmp",
                    "source_id": "tmp:current",
                    "source_adapter": "tmp_children",
                },
                {
                    "candidate_id": aoa_id,
                    "path": aoa_path,
                    "owner": "aoa-session-memory",
                    "kind": "aoa_owner_debris",
                    "source_id": "aoa-maintenance:stage:aoa",
                    "source_adapter": "aoa_owner_verdict",
                },
            ]
        discovery_calls += 1
        return specs

    def fake_collect(spec, **kwargs):
        return candidate_observation(
            candidate_id=str(spec["candidate_id"]),
            path=str(spec["path"]),
            owner=str(spec["owner"]),
            kind=str(spec["kind"]),
            source_id=str(spec["source_id"]),
            source_adapter=str(spec["source_adapter"]),
            observed_at=str(kwargs["generated_at"]),
            physical_bytes=10 if spec["candidate_id"] == current_id else 14,
        )

    def load_latest(path):
        return latest["document"], None

    monkeypatch.setattr(cli, "now_iso", lambda: next(refresh_times))
    monkeypatch.setattr(cli, "load_json_document", load_latest)
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", fake_discover)
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli.storage_candidate_adapters, "collect_observation", fake_collect)
    monkeypatch.setattr(cli, "storage_path_protection", lambda path: {"decision": "allow_candidate"})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    partial = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    latest["document"] = partial

    partial_ids = [item["candidate_id"] for item in partial["candidates"]]
    assert partial["ok"] is False
    assert partial["partial"] is True
    assert partial["complete"] is False
    assert partial["last_deep_at"] == last_good_at
    assert partial["freshness"]["last_deep_at"] == last_good_at
    assert partial["freshness"]["partial"] is True
    assert partial["freshness"]["complete"] is False
    assert len(partial_ids) == len(set(partial_ids))
    assert set(partial_ids) == {aoa_id, current_id}
    assert aoa_id not in {item["candidate_id"] for item in partial["retired"]}
    assert old_id in {item["candidate_id"] for item in partial["retired"]}
    assert partial["coverage"]["owner_coverage"]["status"] == "deferred_active_writer"
    assert partial["coverage"]["owner_coverage"]["last_good_at"] == last_good_at
    assert partial["coverage"]["owner_coverage"]["carried_forward_count"] == 1
    assert partial["coverage"]["current_results"] == 1

    empty_partial = {**partial, "candidates": [], "snapshot_id": None}
    empty_light = cli.storage_candidate_light_refresh(empty_partial, "2026-09-04T19:03:00+00:00")
    assert empty_light["ok"] is False
    assert empty_light["partial"] is True
    assert empty_light["complete"] is False
    assert empty_light["last_deep_at"] == last_good_at
    assert empty_light["freshness"]["last_deep_at"] == last_good_at
    assert empty_light["freshness"]["reason"] == "aoa_owner_deferred_last_good_preserved"
    assert empty_light["coverage"]["mode"] == "light_carry_forward_aoa_owner_deferred"
    assert empty_light["coverage"]["owner_coverage"]["last_good_at"] == last_good_at
    assert empty_light["producer_coverage"]["aoa_owner_verdict"]["status"] == "deferred_active_writer"

    light = cli.storage_candidate_light_refresh(partial, "2026-09-04T19:02:00+00:00")
    latest["document"] = light
    assert light["ok"] is False
    assert light["partial"] is True
    assert light["complete"] is False
    assert light["last_deep_at"] == last_good_at
    assert light["freshness"]["last_deep_at"] == last_good_at
    assert light["freshness"]["reason"] == "aoa_owner_deferred_last_good_preserved"
    assert light["coverage"]["mode"] == "light_carry_forward_aoa_owner_deferred"
    assert light["coverage"]["owner_coverage"]["status"] == "deferred_active_writer"
    assert light["coverage"]["owner_coverage"]["last_good_at"] == last_good_at
    assert light["summary"]["retired"] == 1
    assert old_id in {item["candidate_id"] for item in light["retired"]}

    recovered = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    recovered_ids = [item["candidate_id"] for item in recovered["candidates"]]
    assert recovered["ok"] is True
    assert recovered.get("partial", False) is False
    assert recovered.get("complete", False) is False
    assert recovered["last_deep_at"] == recovered_at
    assert len(recovered_ids) == len(set(recovered_ids))
    assert set(recovered_ids) == {aoa_id, current_id}
    assert aoa_id not in {item["candidate_id"] for item in recovered["retired"]}
    assert old_id in {item["candidate_id"] for item in recovered["retired"]}
    assert recovered["summary"]["retired"] == 1
    assert recovered["freshness"]["status"] == "fresh"
    assert discovery_calls == 2


def test_reservations_are_atomic_idempotent_and_expire(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    target = tmp_path / "future-write"
    now = dt.datetime(2026, 9, 4, tzinfo=dt.timezone.utc)

    def fake_usage(path, statvfs=None):
        return {
            "ok": True,
            "anchor": str(tmp_path),
            "available_to_user_bytes": 100,
            "free_bytes": 100,
        }

    user_limited = storage_reservations.acquire_reservation(
        tmp_path / "user-limited-reservations",
        reservation_id="user-limited",
        kind="model-cache",
        requested_bytes=30,
        target=target,
        owner="hook",
        ttl_seconds=30,
        now=now,
        disk_usage=lambda path, statvfs=None: {
            "ok": True,
            "anchor": str(tmp_path),
            "available_to_user_bytes": 20,
            "free_bytes": 100,
        },
    )
    assert user_limited["decision"] == "blocked"
    assert user_limited["error"] == "available_capacity_after_reservations_below_policy"

    first = storage_reservations.acquire_reservation(
        root,
        reservation_id="run-1",
        kind="model-cache",
        requested_bytes=70,
        target=target,
        owner="hook",
        ttl_seconds=30,
        now=now,
        disk_usage=fake_usage,
    )
    assert first["ok"] is True
    assert first["decision"] == "reserved"

    second = storage_reservations.acquire_reservation(
        root,
        reservation_id="run-2",
        kind="model-cache",
        requested_bytes=40,
        target=target,
        owner="hook",
        ttl_seconds=30,
        now=now,
        disk_usage=fake_usage,
    )
    assert second["ok"] is False
    assert second["error"] == "available_capacity_after_reservations_below_policy"

    replay = storage_reservations.acquire_reservation(
        root,
        reservation_id="run-1",
        kind="model-cache",
        requested_bytes=70,
        target=target,
        owner="hook",
        ttl_seconds=30,
        now=now,
        disk_usage=fake_usage,
    )
    assert replay["decision"] == "already_reserved"

    released = storage_reservations.release_reservation(root, "run-1", now=now)
    assert released["decision"] == "released"
    replacement = storage_reservations.acquire_reservation(
        root,
        reservation_id="run-2",
        kind="model-cache",
        requested_bytes=40,
        target=target,
        owner="hook",
        ttl_seconds=1,
        now=now,
        disk_usage=fake_usage,
    )
    assert replacement["ok"] is True
    expired = storage_reservations.expire_reservations(root, now=now + dt.timedelta(seconds=2))
    assert expired["expired_count"] == 1
    assert storage_reservations.list_reservations(root, now=now + dt.timedelta(seconds=2))["active_reserved_bytes"] == 0


def test_cli_write_reservation_help_is_registered() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "storage", "write-reservation", "--help"],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    assert "acquire" in result.stdout
    assert "does not create files" in result.stdout


def test_cli_reservation_rejects_reroute_target(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "storage_path_protection",
        lambda path: {"decision": "reroute_for_large_generated_data", "class": "system_root"},
    )
    result = cli.storage_reservation_acquire(
        reservation_id="root-target",
        kind="cache",
        requested_bytes=1,
        target="/",
        owner="test",
        ttl_seconds=60,
    )
    assert result["ok"] is False
    assert result["error"] == "reservation_target_protected_or_unknown"


def test_reservations_fail_closed_on_corrupt_record(tmp_path: Path) -> None:
    root = tmp_path / "reservations"
    records = root / "records"
    records.mkdir(parents=True)
    (records / "corrupt.json").write_text("{\"schema\": \"wrong\"}\n", encoding="utf-8")

    listing = storage_reservations.list_reservations(root)
    assert listing["ok"] is False
    assert listing["state_errors"][0]["error"] == "reservation_schema_invalid"
    blocked = storage_reservations.acquire_reservation(
        root,
        reservation_id="safe-retry",
        kind="cache",
        requested_bytes=1,
        target=tmp_path / "target",
        owner="test",
        ttl_seconds=60,
        disk_usage=lambda path, statvfs=None: {"available_to_user_bytes": 100, "free_bytes": 100},
    )
    assert blocked["error"] == "reservation_state_invalid"


def test_write_preflight_denies_unknown_reservation_state() -> None:
    decision = storage_contracts.write_preflight_decision(
        kind="cache",
        requested_bytes=1,
        protection={"decision": "allow_candidate", "class": "host_owned_allowed"},
        pressure_summary={},
        target_usage={"available_to_user_bytes": 100},
        recommended_usage={"available_to_user_bytes": 100},
        large_write_threshold=1000,
        min_free_after=1,
        reservations_ok=False,
    )
    assert decision["decision"] == "deny"
    assert decision["reasons"] == ["reservation_state_invalid"]


def test_candidate_deep_timer_does_not_hide_resource_blocks() -> None:
    service = (ROOT / "systemd" / "user" / "abyss-storage-candidates-deep.service").read_text(encoding="utf-8")
    assert "storage candidates refresh --deep --if-due --json" in service
    assert "--success-on-block" not in service


def test_bounded_deep_refresh_resumes_without_premature_retirement_or_false_freshness(monkeypatch) -> None:
    generated = iter((
        "2026-09-05T19:00:00+00:00",
        "2026-09-05T19:01:00+00:00",
        "2026-09-05T19:02:00+00:00",
    ))
    old_observed = "2026-09-05T18:00:00+00:00"
    old = {
        "candidate_id": "reclaim-old",
        "path": "/srv/abyss-machine/tmp/old",
        "owner": "test-owner",
        "kind": "generated_tmp",
        "source_adapter": "test",
        "verdict": "blocked_unknown",
        "physical_bytes": 4,
        "reclaimable_bytes": 4,
        "observed_at": old_observed,
        "fingerprint": {"digest": "old", "complete": True},
        "evidence": {key: {"checked": True, "active": False} for key in (
            "process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs",
        )},
        "executor": {"type": "test", "owner_specific": True},
    }
    latest = {
        "generated_at": old_observed,
        "last_deep_at": old_observed,
        "candidates": [old],
        "retired": [],
        "coverage": {"runtime_errors": [], "pressure_findings": []},
    }
    specs = [
        {"candidate_id": f"reclaim-{letter}", "path": f"/srv/abyss-machine/tmp/{letter}", "owner": "test-owner", "kind": "generated_tmp", "source_id": letter, "source_adapter": "test", "executor": {"type": "test", "owner_specific": True}, "unique_data": {"status": "clear"}, "recovery": {"verified": True, "command": "rebuild"}}
        for letter in ("a", "b", "c")
    ]

    def observation(spec, **kwargs):
        return {
            **{key: spec.get(key) for key in ("candidate_id", "path", "owner", "kind", "source_id", "source_adapter")},
            "exists": True,
            "physical_bytes": 10,
            "reclaimable_bytes": 10,
            "fingerprint": {"digest": str(spec["candidate_id"]), "complete": True},
            "latest_mtime": kwargs["generated_at"],
            "observed_at": kwargs["generated_at"],
            "executor": {"type": "test", "owner_specific": True},
            "evidence": {
                "protection": {"decision": "allow_candidate"},
                "physical_size": {"checked": True, "ok": True},
                **{key: {"checked": True, "active": False} for key in (
                    "process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs",
                )},
                "active_claims": [],
                "unique_data": {"status": "clear"},
                "recovery": {"verified": True, "command": "rebuild"},
            },
        }

    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BATCH_LIMIT", 2)
    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BUDGET_SECONDS", 120.0)
    monkeypatch.setattr(cli, "now_iso", lambda: next(generated))
    monkeypatch.setattr(cli, "load_json_document", lambda path: (latest, None))
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", lambda **kwargs: specs)
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli.storage_candidate_adapters, "collect_observation", observation)
    monkeypatch.setattr(cli, "storage_path_protection", lambda path: {"decision": "allow_candidate"})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    partial = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    assert partial["partial"] is True
    assert partial["ok"] is False
    assert partial["deep_progress"]["status"] == "partial"
    assert partial["deep_progress"]["cursor"] == 2
    assert partial["last_deep_at"] == old_observed
    assert partial["retired"] == []
    assert "reclaim-old" in {item["candidate_id"] for item in partial["candidates"]}
    assert all(item.get("observation_status") == "current_deep" for item in partial["candidates"] if item["candidate_id"] != "reclaim-old")
    latest.update(partial)

    light = cli.storage_candidate_light_refresh(partial, "2026-09-05T19:01:30+00:00")
    assert light["partial"] is True
    assert light["ok"] is False
    assert light["deep_progress"]["cursor"] == 2
    assert light["coverage"]["mode"] == "light_carry_forward_deep_partial"
    latest.update(light)

    recovered = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    assert recovered["partial"] is False
    assert recovered["ok"] is True
    assert recovered["deep_progress"]["status"] == "complete"
    assert recovered["last_deep_at"] == "2026-09-05T19:01:00+00:00"
    assert "reclaim-old" not in {item["candidate_id"] for item in recovered["candidates"]}
    assert "reclaim-old" in {item["candidate_id"] for item in recovered["retired"]}
    assert len({item["candidate_id"] for item in recovered["candidates"]}) == 3


def test_bounded_deep_deadline_keeps_last_good_and_does_not_retire_failed_object(monkeypatch) -> None:
    generated_at = "2026-09-05T20:00:00+00:00"
    last_deep_at = "2026-09-05T18:00:00+00:00"
    old = {
        "candidate_id": "reclaim-keep",
        "path": "/srv/abyss-machine/tmp/keep",
        "owner": "test-owner",
        "kind": "generated_tmp",
        "source_adapter": "test",
        "verdict": "blocked_unknown",
        "physical_bytes": 8,
        "reclaimable_bytes": 8,
        "observed_at": last_deep_at,
        "fingerprint": {"digest": "old", "complete": True},
        "evidence": {key: {"checked": True, "active": False} for key in (
            "process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs",
        )},
        "executor": {"type": "test", "owner_specific": True},
    }
    latest = {"generated_at": last_deep_at, "last_deep_at": last_deep_at, "candidates": [old], "retired": [], "coverage": {"runtime_errors": [], "pressure_findings": []}}
    spec = {"candidate_id": "reclaim-new", "path": "/srv/abyss-machine/tmp/new", "owner": "test-owner", "kind": "generated_tmp", "source_id": "new", "source_adapter": "test"}

    def timed_out_observation(spec, **kwargs):
        return {
            **spec,
            "exists": True,
            "physical_bytes": None,
            "reclaimable_bytes": None,
            "fingerprint": {"digest": "partial", "complete": False, "timed_out": True, "reason": "deadline_exceeded"},
            "latest_mtime": None,
            "observed_at": kwargs["generated_at"],
            "executor": {},
            "evidence": {"physical_size": {"checked": True, "ok": False, "error": "deadline_exceeded"}},
        }

    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BATCH_LIMIT", 2)
    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BUDGET_SECONDS", 120.0)
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "load_json_document", lambda path: (latest, None))
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", lambda **kwargs: [spec])
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli.storage_candidate_adapters, "collect_observation", timed_out_observation)
    monkeypatch.setattr(cli, "storage_path_protection", lambda path: {"decision": "allow_candidate"})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    assert refreshed["ok"] is False
    assert refreshed["partial"] is True
    assert refreshed["deep_progress"]["status"] == "partial"
    assert refreshed["deep_progress"]["cursor"] == 0
    assert refreshed["last_deep_at"] == last_deep_at
    assert [item["candidate_id"] for item in refreshed["candidates"]] == ["reclaim-keep"]
    assert refreshed["retired"] == []
    assert refreshed["runtime_errors"][0]["error"] == "deadline_exceeded"


def test_bounded_deep_pre_batch_deadline_has_explicit_cursor_result(monkeypatch) -> None:
    ticks = iter((100.0, 102.0, 102.0))
    spec = {"candidate_id": "reclaim-pending", "path": "/srv/abyss-machine/tmp/pending", "owner": "test", "kind": "generated_tmp"}
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BATCH_LIMIT", 1)
    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BUDGET_SECONDS", 1.0)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-09-05T20:30:00+00:00")
    monkeypatch.setattr(cli, "load_json_document", lambda path: ({}, None))
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", lambda **kwargs: [spec])
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    assert refreshed["partial"] is True
    assert refreshed["ok"] is False
    assert refreshed["deep_progress"]["cursor"] == 0
    assert refreshed["deep_progress"]["remaining"] == 1
    assert refreshed["runtime_errors"][0]["error"] == "deadline_exceeded_before_batch"
    assert refreshed["retired"] == []


def test_bounded_deep_observation_failure_does_not_starve_healthy_suffix(monkeypatch) -> None:
    generated_at = "2026-09-05T20:45:00+00:00"
    bad_id = "reclaim-bad-git-index"
    healthy_id = "reclaim-healthy-suffix"
    bad_spec = {
        "candidate_id": bad_id,
        "path": "/srv/abyss-machine/tmp/bad-git-index",
        "owner": "git",
        "kind": "git_worktree",
        "source_adapter": "git_worktree",
    }
    healthy_spec = {
        "candidate_id": healthy_id,
        "path": "/srv/abyss-machine/tmp/healthy-suffix",
        "owner": "test-owner",
        "kind": "generated_tmp",
        "source_adapter": "test",
    }
    required_evidence = {
        key: {"checked": True, "active": False}
        for key in ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
    }
    last_good_bad = {
        **bad_spec,
        "exists": True,
        "physical_bytes": 4,
        "reclaimable_bytes": 4,
        "verdict": "blocked_unknown",
        "observed_at": "2026-09-05T18:00:00+00:00",
        "fingerprint": {"digest": "last-good-git-index", "complete": True},
        "evidence": {**required_evidence, "physical_size": {"checked": True, "ok": True}},
        "executor": {"type": "git_worktree_remove", "owner_specific": True},
    }
    previous = {
        "last_deep_at": "2026-09-05T18:00:00+00:00",
        "candidates": [last_good_bad],
        "coverage": {"runtime_errors": [], "pressure_findings": []},
        "retired": [],
    }
    observed_ids: list[str] = []

    def observation(spec, **kwargs):
        candidate_id = str(spec["candidate_id"])
        observed_ids.append(candidate_id)
        if candidate_id == bad_id:
            raise RuntimeError("corrupt git index")
        return {
            **spec,
            "exists": True,
            "physical_bytes": 7,
            "reclaimable_bytes": 7,
            "fingerprint": {"digest": healthy_id, "complete": True},
            "latest_mtime": kwargs["generated_at"],
            "observed_at": kwargs["generated_at"],
            "executor": {"type": "test", "owner_specific": True},
            "evidence": {**required_evidence, "physical_size": {"checked": True, "ok": True}},
        }

    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BATCH_LIMIT", 2)
    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BUDGET_SECONDS", 120.0)
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "load_json_document", lambda path: (previous, None))
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", lambda **kwargs: [bad_spec, healthy_spec])
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli.storage_candidate_adapters, "collect_observation", observation)
    monkeypatch.setattr(cli, "storage_path_protection", lambda path: {"decision": "allow_candidate"})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    refreshed = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)

    assert observed_ids == [bad_id, healthy_id]
    assert refreshed["ok"] is False
    assert refreshed["partial"] is True
    assert refreshed["coverage"]["observed"] == 2
    assert refreshed["deep_progress"]["processed_this_run"] == 2
    assert refreshed["deep_progress"]["cursor"] == 0
    preserved = next(item for item in refreshed["candidates"] if item["candidate_id"] == bad_id)
    assert preserved["observation_status"] == "carried_forward"
    assert preserved["fingerprint"]["digest"] == "last-good-git-index"
    assert any(
        item.get("candidate_id") == bad_id and item.get("error") == "corrupt git index"
        for item in refreshed["coverage"]["runtime_errors_full"]
    )
    assert any(item["candidate_id"] == healthy_id for item in refreshed["candidates"])
    assert refreshed["retired"] == []


def test_bounded_deep_attempted_timeout_advances_to_healthy_suffix(monkeypatch) -> None:
    generated_at = "2026-09-05T20:50:00+00:00"
    last_deep_at = "2026-09-05T18:00:00+00:00"
    bad_id = "reclaim-bad-timeout"
    healthy_id = "reclaim-healthy-after-timeout"
    bad_spec = {
        "candidate_id": bad_id,
        "path": "/srv/abyss-machine/tmp/bad-timeout",
        "owner": "test-owner",
        "kind": "generated_tmp",
        "source_adapter": "test",
    }
    healthy_spec = {
        "candidate_id": healthy_id,
        "path": "/srv/abyss-machine/tmp/healthy-after-timeout",
        "owner": "test-owner",
        "kind": "generated_tmp",
        "source_adapter": "test",
    }
    required_evidence = {
        key: {"checked": True, "active": False}
        for key in ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
    }
    last_good_bad = {
        **bad_spec,
        "exists": True,
        "physical_bytes": 4,
        "reclaimable_bytes": 4,
        "verdict": "blocked_unknown",
        "observed_at": last_deep_at,
        "fingerprint": {"digest": "last-good-timeout", "complete": True},
        "evidence": {**required_evidence, "physical_size": {"checked": True, "ok": True}},
        "executor": {"type": "test", "owner_specific": True},
    }
    previous = {
        "last_deep_at": last_deep_at,
        "candidates": [last_good_bad],
        "coverage": {"runtime_errors": [], "pressure_findings": []},
        "retired": [],
    }
    current_previous = {"document": previous}
    observed_ids: list[str] = []

    def observation(spec, **kwargs):
        candidate_id = str(spec["candidate_id"])
        observed_ids.append(candidate_id)
        if candidate_id == bad_id:
            return {
                **spec,
                "exists": True,
                "physical_bytes": None,
                "reclaimable_bytes": None,
                "fingerprint": {
                    "digest": "partial-timeout",
                    "complete": False,
                    "timed_out": True,
                    "reason": "deadline_exceeded",
                },
                "latest_mtime": None,
                "observed_at": kwargs["generated_at"],
                "executor": {},
                "evidence": {"physical_size": {"checked": True, "ok": False, "error": "deadline_exceeded"}},
            }
        return {
            **spec,
            "exists": True,
            "physical_bytes": 7,
            "reclaimable_bytes": 7,
            "fingerprint": {"digest": "healthy-after-timeout", "complete": True},
            "latest_mtime": kwargs["generated_at"],
            "observed_at": kwargs["generated_at"],
            "executor": {"type": "test", "owner_specific": True},
            "evidence": {**required_evidence, "physical_size": {"checked": True, "ok": True}},
        }

    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BATCH_LIMIT", 2)
    monkeypatch.setattr(cli, "STORAGE_CANDIDATE_DEEP_BUDGET_SECONDS", 120.0)
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "load_json_document", lambda path: (current_previous["document"], None))
    monkeypatch.setattr(cli, "storage_candidate_discover_specs", lambda **kwargs: [bad_spec, healthy_spec])
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda root: [])
    monkeypatch.setattr(cli, "storage_candidate_runtime_documents", lambda: [])
    monkeypatch.setattr(cli, "storage_candidate_lane_documents", lambda: [])
    monkeypatch.setattr(cli.storage_candidate_adapters, "process_references", lambda paths: {})
    monkeypatch.setattr(cli, "storage_candidate_config_refs_by_path", lambda specs: {})
    monkeypatch.setattr(cli.storage_candidate_adapters, "collect_observation", observation)
    monkeypatch.setattr(cli, "storage_path_protection", lambda path: {"decision": "allow_candidate"})
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})

    first = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    assert observed_ids == [bad_id]
    assert first["ok"] is False
    assert first["partial"] is True
    assert first["deep_progress"]["cursor"] == 1
    assert first["coverage"]["observed"] == 1
    assert first["last_deep_at"] == last_deep_at
    assert first["retired"] == []
    preserved = next(item for item in first["candidates"] if item["candidate_id"] == bad_id)
    assert preserved["observation_status"] == "carried_forward"
    assert preserved["fingerprint"]["digest"] == "last-good-timeout"
    assert any(
        item.get("candidate_id") == bad_id and item.get("error") == "deadline_exceeded"
        for item in first["coverage"]["runtime_errors_full"]
    )

    current_previous["document"] = first
    observed_ids.clear()
    second = cli._storage_candidates_refresh_unlocked(deep=True, write_latest=False)
    assert observed_ids == [healthy_id]
    assert second["ok"] is False
    assert second["partial"] is True
    assert second["coverage"]["observed"] == 2
    assert second["deep_progress"]["processed_this_run"] == 1
    assert second["last_deep_at"] == last_deep_at
    assert second["retired"] == []
    assert any(item["candidate_id"] == healthy_id for item in second["candidates"])
    assert any(
        item.get("candidate_id") == bad_id and item.get("error") == "deadline_exceeded"
        for item in second["coverage"]["runtime_errors_full"]
    )


def test_bounded_deep_error_authority_exceeds_display_window_until_reverified() -> None:
    generated_at = "2026-09-05T21:00:00+00:00"
    candidate_ids = [f"reclaim-{index:03d}" for index in range(205)]
    required_evidence = {
        key: {"checked": True, "active": False}
        for key in ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
    }

    def record(candidate_id: str, *, failed: bool) -> dict[str, object]:
        evidence = {
            **required_evidence,
            "physical_size": {"checked": True, "ok": True},
        }
        if failed:
            evidence["service_refs"] = {"checked": False, "active": False, "error": f"service failure {candidate_id}"}
        return {
            "candidate_id": candidate_id,
            "path": f"/srv/abyss-machine/tmp/{candidate_id}",
            "source_adapter": "test",
            "physical_bytes": 1,
            "reclaimable_bytes": 1,
            "observed_at": "2026-09-05T18:00:00+00:00",
            "fingerprint": {"digest": candidate_id, "complete": True},
            "evidence": evidence,
            "executor": {"type": "test", "owner_specific": True},
        }

    failed_records = [record(candidate_id, failed=True) for candidate_id in candidate_ids]
    previous = {
        "last_deep_at": "2026-09-05T18:00:00+00:00",
        "candidates": failed_records,
        # Emulate an older bounded document: only the first 200 failures are
        # visible in the persisted display field and no full authority field
        # is available yet. The builder must derive the missing tail from
        # carried per-object evidence.
        "coverage": {
            "runtime_errors": storage_candidate_contracts.coverage_summary(failed_records)["runtime_errors"],
            "pressure_findings": [],
        },
        "retired": [],
    }
    healthy_last = record(candidate_ids[-1], failed=False)
    common = {
        "previous": previous,
        "specs": [
            {"candidate_id": candidate_id, "path": f"/srv/abyss-machine/tmp/{candidate_id}"}
            for candidate_id in candidate_ids
        ],
        "cursor_before": 204,
        "cursor_after": 205,
        "generated_at": generated_at,
        "elapsed_seconds": 1.0,
        "budget_seconds": 120.0,
        "batch_limit": 1,
        "runtime_errors": [],
        "producer_status": {},
        "candidate_document": {
            "candidates": [healthy_last],
            "retired": [],
            "changes": [],
            "coverage": {"runtime_errors": [], "pressure_findings": []},
        },
        "complete": True,
        "deadline_exceeded": False,
    }
    partial = cli._storage_candidate_build_bounded_document([healthy_last], **common)

    assert partial["ok"] is False
    assert partial["partial"] is True
    assert len(partial["coverage"]["runtime_errors_full"]) == 204
    assert len(partial["runtime_errors"]) == 200
    assert partial["deep_progress"]["status"] == "partial"
    assert partial["retired"] == []

    light = cli._storage_candidate_preserve_partial_light_state({"coverage": {}}, partial)
    assert len(light["coverage"]["runtime_errors_full"]) == 204
    assert len(light["coverage"]["runtime_errors"]) == 200

    healthy_records = [record(candidate_id, failed=False) for candidate_id in candidate_ids]
    recovered = cli._storage_candidate_build_bounded_document(
        healthy_records,
        previous=partial,
        specs=common["specs"],
        cursor_before=0,
        cursor_after=len(candidate_ids),
        generated_at="2026-09-05T21:01:00+00:00",
        elapsed_seconds=1.0,
        budget_seconds=120.0,
        batch_limit=len(candidate_ids),
        runtime_errors=[],
        producer_status={},
        candidate_document={
            "candidates": healthy_records,
            "retired": [],
            "changes": [],
            "coverage": {"runtime_errors": [], "pressure_findings": []},
        },
        complete=True,
        deadline_exceeded=False,
    )
    assert recovered["ok"] is True
    assert recovered["partial"] is False
    assert recovered["coverage"]["runtime_errors_full"] == []
    assert recovered["retired"] == []


def test_bounded_deep_inventory_churn_resumes_after_stable_identity() -> None:
    specs = [
        {"candidate_id": f"reclaim-{letter}", "path": f"/srv/abyss-machine/tmp/{letter}", "owner": "test", "kind": "generated_tmp"}
        for letter in ("a", "b", "c", "d", "z")
    ]
    previous = {
        "candidates": [{"candidate_id": "reclaim-a"}, {"candidate_id": "reclaim-b"}],
        "deep_progress": {
            "status": "partial",
            "inventory_digest": "old-digest",
            "cursor": 2,
            "cursor_candidate_id": "reclaim-b",
        },
    }
    ordered_specs = cli._storage_candidate_ordered_specs(specs)
    digest = cli._storage_candidate_inventory_digest(ordered_specs)
    cursor, state = cli._storage_candidate_deep_progress(previous, digest, ordered_specs)
    assert cursor == 2
    assert state["inventory_changed"] is True

    prefix_specs = [
        {"candidate_id": "reclaim-aa", "path": "/srv/abyss-machine/tmp/aa", "owner": "test", "kind": "generated_tmp"},
        *specs,
    ]
    ordered_prefix_specs = cli._storage_candidate_ordered_specs(prefix_specs)
    prefix_digest = cli._storage_candidate_inventory_digest(ordered_prefix_specs)
    prefix_cursor, prefix_state = cli._storage_candidate_deep_progress(previous, prefix_digest, ordered_prefix_specs)
    assert prefix_cursor == 3
    assert prefix_state["deferred_prefix"] is True

    def record(candidate_id: str) -> dict[str, object]:
        return {
            "candidate_id": candidate_id,
            "path": f"/srv/abyss-machine/tmp/{candidate_id.removeprefix('reclaim-')}",
            "source_adapter": "test",
            "physical_bytes": 1,
            "reclaimable_bytes": 1,
            "fingerprint": {"digest": candidate_id, "complete": True},
            "evidence": {
                key: {"checked": True, "active": False}
                for key in ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
            },
        }

    # Finish the stable suffix while the new prefix is deferred.  The
    # resulting state keeps an anchor at the suffix end and starts a separate
    # prefix pass instead of pretending that the inventory is complete.
    suffix_result = cli._storage_candidate_build_bounded_document(
        [record(candidate_id) for candidate_id in ("reclaim-c", "reclaim-d", "reclaim-z")],
        previous=previous,
        specs=ordered_prefix_specs,
        cursor_before=prefix_cursor,
        cursor_after=len(ordered_prefix_specs),
        generated_at="2026-09-05T19:02:00+00:00",
        elapsed_seconds=1.0,
        budget_seconds=120.0,
        batch_limit=4096,
        runtime_errors=[],
        producer_status={},
        candidate_document={
            "candidates": [record(candidate_id) for candidate_id in ("reclaim-c", "reclaim-d", "reclaim-z")],
            "retired": [],
            "changes": [],
            "coverage": {"runtime_errors": [], "pressure_findings": []},
        },
        complete=True,
        deadline_exceeded=False,
        deferred_prefix=True,
    )
    assert suffix_result["partial"] is True
    assert suffix_result["deep_progress"]["deferred_prefix"] is True
    assert suffix_result["deep_progress"]["last_processed_candidate_id"] == "reclaim-z"
    assert suffix_result["coverage"]["observed"] == len(ordered_prefix_specs)

    # Repeated new identities before the old cursor still resume after the
    # serviced suffix.  They cannot reset the scan to the earliest prefix.
    repeated_prefix_specs = cli._storage_candidate_ordered_specs([
        {"candidate_id": "reclaim-ab", "path": "/srv/abyss-machine/tmp/ab", "owner": "test", "kind": "generated_tmp"},
        {"candidate_id": "reclaim-aa", "path": "/srv/abyss-machine/tmp/aa", "owner": "test", "kind": "generated_tmp"},
        *prefix_specs,
    ])
    repeated_digest = cli._storage_candidate_inventory_digest(repeated_prefix_specs)
    repeated_cursor, repeated_state = cli._storage_candidate_deep_progress(
        suffix_result,
        repeated_digest,
        repeated_prefix_specs,
    )
    assert repeated_cursor == len(repeated_prefix_specs)
    assert repeated_state["deferred_prefix"] is True

    prefix_pass_cursor, prefix_pass_state = cli._storage_candidate_deep_progress(
        suffix_result,
        cli._storage_candidate_inventory_digest(ordered_prefix_specs),
        ordered_prefix_specs,
    )
    assert prefix_pass_cursor == 0
    assert prefix_pass_state["prefix_pass"] is True
    assert prefix_pass_state["deferred_prefix"] is False


def test_bounded_deep_does_not_claim_complete_while_earlier_error_is_unresolved() -> None:
    previous = {
        "last_deep_at": "2026-09-05T17:00:00+00:00",
        "candidates": [
            {"candidate_id": "reclaim-a", "path": "/srv/abyss-machine/tmp/a", "observed_at": "2026-09-05T17:00:00+00:00"},
            {"candidate_id": "reclaim-gone", "path": "/srv/abyss-machine/tmp/gone", "observed_at": "2026-09-05T17:00:00+00:00"},
        ],
        "coverage": {"runtime_errors": [
            {"candidate_id": "reclaim-a", "surface": "process_refs", "error": "permission"},
            {"candidate_id": "reclaim-gone", "surface": "process_refs", "error": "stale permission"},
        ]},
        "deep_progress": {"status": "partial", "cursor": 1, "cursor_candidate_id": "reclaim-a"},
    }
    current = {
        "candidate_id": "reclaim-b",
        "path": "/srv/abyss-machine/tmp/b",
        "observed_at": "2026-09-05T19:00:00+00:00",
        "physical_bytes": 1,
        "reclaimable_bytes": 1,
        "fingerprint": {"digest": "b", "complete": True},
        "evidence": {key: {"checked": True, "active": False} for key in (
            "process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs",
        )},
        "executor": {"type": "test", "owner_specific": True},
    }
    specs = [
        {"candidate_id": "reclaim-a", "path": "/srv/abyss-machine/tmp/a"},
        {"candidate_id": "reclaim-b", "path": "/srv/abyss-machine/tmp/b"},
    ]
    result = cli._storage_candidate_build_bounded_document(
        [current],
        previous=previous,
        specs=specs,
        cursor_before=1,
        cursor_after=2,
        generated_at="2026-09-05T19:01:00+00:00",
        elapsed_seconds=1.0,
        budget_seconds=120.0,
        batch_limit=2,
        runtime_errors=[],
        producer_status={},
        candidate_document={"candidates": [current], "retired": [], "changes": [], "coverage": {"runtime_errors": [], "pressure_findings": []}},
        complete=True,
        deadline_exceeded=False,
    )
    assert result["ok"] is False
    assert result["partial"] is True
    assert result["deep_progress"]["status"] == "partial"
    assert result["deep_progress"]["cursor"] == 0
    assert result["last_deep_at"] == "2026-09-05T17:00:00+00:00"
    assert any(item.get("candidate_id") == "reclaim-a" for item in result["runtime_errors"])
    gone = next(item for item in result["candidates"] if item["candidate_id"] == "reclaim-gone")
    assert gone["discovery_absent"] is True
    assert gone["prior_runtime_errors"][0]["error"] == "stale permission"
    assert result["retired"] == []


def test_bounded_deep_complete_absence_clears_disappeared_candidate_error() -> None:
    previous = {
        "last_deep_at": "2026-09-05T17:00:00+00:00",
        "candidates": [{
            "candidate_id": "reclaim-gone",
            "path": "/srv/abyss-machine/tmp/gone",
            "observed_at": "2026-09-05T17:00:00+00:00",
            "evidence": {"service_refs": {"checked": False, "error": "permission"}},
        }],
        "coverage": {
            "runtime_errors": [{"candidate_id": "reclaim-gone", "surface": "process_refs", "error": "permission"}],
            "pressure_findings": [],
        },
    }
    current = {
        "candidate_id": "reclaim-current",
        "path": "/srv/abyss-machine/tmp/current",
        "observed_at": "2026-09-05T19:00:00+00:00",
        "physical_bytes": 1,
        "reclaimable_bytes": 1,
        "fingerprint": {"digest": "current", "complete": True},
        "evidence": {
            key: {"checked": True, "active": False}
            for key in ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
        },
    }
    result = cli._storage_candidate_build_bounded_document(
        [current],
        previous=previous,
        specs=[{"candidate_id": "reclaim-current", "path": current["path"]}],
        cursor_before=0,
        cursor_after=1,
        generated_at="2026-09-05T19:01:00+00:00",
        elapsed_seconds=1.0,
        budget_seconds=120.0,
        batch_limit=2,
        runtime_errors=[],
        producer_status={},
        candidate_document={
            "candidates": [current],
            "retired": [],
            "changes": [],
            "coverage": {"runtime_errors": [], "pressure_findings": []},
        },
        complete=True,
        deadline_exceeded=False,
    )
    assert result["ok"] is True
    assert result["partial"] is False
    assert result["runtime_errors"] == []
    assert "reclaim-gone" not in {item["candidate_id"] for item in result["candidates"]}
    assert "reclaim-gone" in {item["candidate_id"] for item in result["retired"]}
    retired = next(item for item in result["retired"] if item["candidate_id"] == "reclaim-gone")
    assert retired["prior_runtime_errors"][0]["error"] == "permission"
