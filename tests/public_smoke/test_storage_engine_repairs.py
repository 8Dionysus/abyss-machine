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
    assert "storage candidates refresh --deep --json" in service
    assert "--success-on-block" not in service
