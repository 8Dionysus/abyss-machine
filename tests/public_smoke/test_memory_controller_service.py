from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from abyss_machine import memory_controller_contracts as contracts
from abyss_machine import memory_controller_adapters as adapters
from abyss_machine import memory_controller_service as service
from abyss_machine import entrypoint


def sample(epoch: float, available_mib: float = 20_000.0) -> dict[str, object]:
    return {
        "schema": "abyss_machine_memory_controller_sample_v1",
        "ok": True,
        "epoch": epoch,
        "monotonic": epoch,
        "mem_total_mib": 32_000.0,
        "mem_available_mib": available_mib,
        "swap_total_mib": 20_000.0,
        "swap_used_mib": 7_000.0,
        "swap_free_mib": 13_000.0,
        "zram_resident_mib": 3_500.0,
        "psi_some_total_usec": 0,
        "psi_full_total_usec": 0,
        "pgmajfault": 0,
        "oom_kill": 0,
        "reservation_count": 0,
        "reservation_outstanding_mib": 0.0,
        "queued_demand_mib": 0.0,
    }


def enrolled_canary() -> dict[str, object]:
    def route(path: str, method: str, expect: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "kind": "local_http_json_v1",
            "url": f"http://127.0.0.1:45451{path}",
            "method": method,
            "expect": {"json_equals": expect or {}},
        }

    return {
        "id": "canary:model",
        "owner": "canary-owner",
        "role": "managed_model_canary",
        "importance": "normal",
        "posture": "background",
        "statefulness": "reconstructable",
        "protected": False,
        "registry_status": "exact",
        "memory": {"expected_mib": 256, "observed_mib": 200},
        "activity": {"state": "idle", "confidence": "high"},
        "sla": {"rehydrate_p95_ms": 100},
        "lifecycle": {
            "activity": route("/activity", "GET", {"active_requests": 0}),
            "dehydrate": route("/dehydrate", "POST", {"ok": True}),
            "rehydrate": route("/rehydrate", "POST", {"ok": True}),
            "health": route("/health", "GET", {"ok": True, "service": "canary-model"}),
            "rollback": route("/rollback", "POST", {"ok": True}),
        },
        "enrollment": {
            "id": "canary-enrollment",
            "status": "enrolled",
            "owner_approved": True,
            "allowed_actions": ["managed_dehydrate"],
        },
        "measurement": {
            "kind": "cgroup_v2_v1",
            "uid": os.getuid(),
            "path": f"/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice/canary.scope",
        },
        "residency": {"minimum_sec": 1, "cooldown_sec": 30},
        "metadata": {"registry_source": "static", "registry_trusted_for_lifecycle": True},
    }


def make_paths(tmp_path: Path) -> service.ControllerPaths:
    etc = tmp_path / "etc"
    runtime = tmp_path / "run"
    evidence = tmp_path / "evidence"
    etc.mkdir()
    (etc / "policy.json").write_text(json.dumps(contracts.default_policy()), encoding="utf-8")
    (etc / "registry.json").write_text(
        json.dumps({"schema": "abyss_machine_memory_controller_registry_v1", "workloads": [], "rules": []}),
        encoding="utf-8",
    )
    return service.ControllerPaths(
        policy=etc / "policy.json",
        registry=etc / "registry.json",
        runtime_root=runtime,
        evidence_root=evidence,
    )


class Clock:
    def __init__(self, value: float) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def test_engine_once_persists_bounded_reason_packet_and_recovers_window(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    clock = Clock(1_000.0)
    values = iter((sample(880.0), sample(940.0), sample(1_000.0)))
    engine = service.ControllerEngine(paths, sample_port=lambda **_kwargs: next(values), epoch_port=clock, monotonic_port=clock)

    for event_id in ("one", "two", "three"):
        result = engine.decide(service.ControllerEvent(source="test", kind="sample", event_id=event_id, epoch=clock(), monotonic=clock()))
        assert result["ok"] is True
        clock.value += 60.0

    latest = json.loads(paths.latest.read_text(encoding="utf-8"))
    assert latest["schema"] == "abyss_machine_memory_controller_reason_packet_v1"
    assert latest["decision"]["live_action_authorized"] is False
    assert latest["integrity"]["generic_process_mutation"] is False
    assert not list(paths.evidence_root.glob(".*.tmp"))

    recovered = service.ControllerEngine(paths, sample_port=lambda **_kwargs: sample(1_180.0), epoch_port=clock, monotonic_port=clock)
    assert len(recovered.samples) == 3
    assert recovered.sequence == 3


def test_forecast_compute_window_is_smaller_than_retained_evidence(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["history"]["sample_limit"] = 100
    policy["forecast"]["sample_window_limit"] = 3
    policy["forecast"]["sample_window_sec"] = 120
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    store = adapters.EvidenceStore(paths.database)
    try:
        for epoch in (60, 120, 180, 240, 300):
            store.append_sample(sample(epoch), limit=100, retention_hours=24)
        retained_count = store.summary()["samples"]["count"]
    finally:
        store.close()

    engine = service.ControllerEngine(paths, sample_port=lambda **_kwargs: sample(300))
    try:
        forecast_epochs = [item["epoch"] for item in engine.samples]
    finally:
        engine.close()

    assert retained_count == 5
    assert forecast_epochs == [180, 240, 300]


def test_duplicate_event_is_idempotent_across_engine_restart(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    clock = Clock(100.0)
    event = service.ControllerEvent(source="socket", kind="demand", event_id="stable-id", epoch=100.0, monotonic=99.5)
    first = service.ControllerEngine(paths, sample_port=lambda **_kwargs: sample(100.0), epoch_port=clock, monotonic_port=clock)
    accepted = first.decide(event)
    assert accepted["status"] == "decision_recorded"

    restarted = service.ControllerEngine(paths, sample_port=lambda **_kwargs: sample(100.0), epoch_port=clock, monotonic_port=clock)
    duplicate = restarted.decide(event)
    assert duplicate == {
        "ok": True,
        "status": "duplicate_event_ignored",
        "event_id": "stable-id",
        "sequence": 1,
    }


def test_reason_packet_measures_event_to_decision_latency(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    monotonic = Clock(52.25)
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: sample(1_000.0),
        epoch_port=lambda: 1_000.0,
        monotonic_port=monotonic,
    )
    result = engine.decide(service.ControllerEvent(source="psi", kind="some", event_id="psi-1", epoch=999.0, monotonic=50.5))
    assert result["timing"]["event_to_decision_ms"] == 1_750.0
    assert result["timing"]["target_ms"] == 2_000.0
    assert result["timing"]["within_target"] is True
    assert result["timing"]["scope"] == "controller_control_plane"
    assert result["timing"]["interactive_latency_claim"] == "not_measured_by_controller_event_latency"
    assert result["controller_overhead"]["process_cpu_ms"] >= 0.0
    assert result["controller_overhead"]["process_peak_rss_mib"] > 0.0
    assert result["controller_overhead"]["energy_status"] == "per_process_energy_not_attributable_without_owner_probe"


def test_resource_launch_outcome_is_persisted_with_queue_and_envelope_metrics(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: sample(100),
        epoch_port=lambda: 100,
        monotonic_port=lambda: 100,
    )
    event = service.ControllerEvent(
        "socket",
        "resource_launch_outcome",
        "resource-outcome-1",
        100,
        100,
        {
            "workload_id": "index:one",
            "owner": "indexer",
            "requested_mib": 512,
            "observed_peak_mib": 768,
            "queue_delay_sec": 0.8,
            "elapsed_sec": 2.0,
            "ok": True,
            "queue_granted": True,
        },
    )
    try:
        result = engine.decide(event)
        evidence = engine.store.summary()
    finally:
        engine.close()

    assert result["launch_outcome"]["classification"] == "envelope_underestimate"
    assert result["launch_outcome"]["calibration_recommendation"]["calibrated_mib"] == 588.8
    assert evidence["launch_outcomes"]["count"] == 1
    assert evidence["launch_outcomes"]["queue_delay_sec"]["p95"] == 0.8


def test_coalescer_has_debounce_cap_and_preserves_event_ids() -> None:
    coalescer = service.EventCoalescer(debounce_ms=200, max_coalesce_ms=1_000)
    coalescer.add(service.ControllerEvent("psi", "some", "a", 10.0, 10.0))
    coalescer.add(service.ControllerEvent("systemd", "unit_new", "b", 10.1, 10.1))

    assert coalescer.ready(10.19) is False
    assert coalescer.ready(10.31) is True
    event = coalescer.pop(10.31)
    assert event.kind == "coalesced"
    assert event.details["event_ids"] == ["a", "b"]
    assert event.monotonic == 10.0

    coalescer.add(service.ControllerEvent("test", "storm", "c", 20.0, 20.0))
    coalescer.add(service.ControllerEvent("test", "storm", "d", 20.9, 20.9))
    assert coalescer.ready(21.01) is True


def test_coalescer_preserves_single_and_bounded_outcome_payloads() -> None:
    coalescer = service.EventCoalescer(debounce_ms=0, max_coalesce_ms=100)
    outcome = service.ControllerEvent(
        "socket",
        "resource_launch_outcome",
        "outcome-1",
        10,
        10,
        {"workload_id": "one", "observed_peak_mib": 64},
    )
    coalescer.add(outcome)
    assert coalescer.pop(10) == outcome

    coalescer.add(outcome)
    coalescer.add(service.ControllerEvent("psi", "some", "psi-1", 10.1, 10.1, {"large": "discarded"}))
    combined = coalescer.pop(10.2)
    assert combined.kind == "coalesced"
    assert combined.details["events"][0]["details"]["workload_id"] == "one"
    assert combined.details["events"][1]["details"] == {}

    storm = service.EventCoalescer(debounce_ms=200, max_coalesce_ms=1_000, maximum_events=4)
    for index in range(100):
        storm.add(service.ControllerEvent("cgroup_memory_events", "filesystem_change", f"cgroup-{index}", 20 + index / 100, 20 + index / 100))
    storm.add(outcome)
    for index in range(10):
        storm.add(service.ControllerEvent("queue", "filesystem_change", f"queue-{index}", 21 + index / 100, 21 + index / 100))
    bounded = storm.pop(22)
    members = {item["event_id"]: item for item in bounded.details["events"]}
    cgroup = next(item for item in members.values() if item["source"] == "cgroup_memory_events")
    assert "outcome-1" in members
    assert bounded.details["event_count"] <= 4
    assert bounded.details["raw_event_count"] >= 100
    assert cgroup["details"]["raw_change_count"] == 100


def test_coalescer_normalizes_untrusted_event_counts() -> None:
    coalescer = service.EventCoalescer(debounce_ms=0, max_coalesce_ms=100)
    coalescer.add(service.ControllerEvent("socket", "custom", "socket-bad-count", 10, 10, {"change_count": "bad"}))
    coalescer.add(service.ControllerEvent("psi", "some", "psi-one", 10.1, 10.1))

    combined = coalescer.pop(10.2)

    assert combined.details["raw_event_count"] == 2
    assert combined.details["event_ids"] == ["socket-bad-count", "psi-one"]


def test_invalid_or_live_policy_fails_closed(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["safety"]["generic_kill"] = True
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")

    result = service.validate_controller_configuration(paths)
    assert result["ok"] is False
    assert "forbidden_safety_capability_enabled:generic_kill" in result["errors"]
    assert "live_mode_requires_enrolled_executor" in result["errors"]


def test_missing_registry_preserves_unknown_and_never_authorizes_lifecycle(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    paths.registry.unlink()
    policy = contracts.default_policy()
    policy["forecast"]["minimum_samples"] = 1
    policy["forecast"]["minimum_span_sec"] = 0
    policy["forecast"]["memory_bands_percent"] = {"watch": 80, "warm": 70, "hot": 60, "critical": 10}
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    engine = service.ControllerEngine(paths, sample_port=lambda **_kwargs: sample(100.0, 4_000.0), epoch_port=lambda: 100.0, monotonic_port=lambda: 100.0)

    result = engine.decide(service.ControllerEvent("test", "pressure", "p", 100.0, 100.0))
    assert result["registry"]["ok"] is False
    assert result["decision"]["selected"]["action"] == "observe"
    assert result["forecast"]["new_work_control_needed"] is True
    assert result["decision"]["live_action_authorized"] is False
    assert result["integrity"]["unknown_workloads_preserved"] is True


def test_status_reports_absent_and_current_checkpoint(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    assert service.controller_status(paths)["status"] == "not_started"
    engine = service.ControllerEngine(paths, sample_port=lambda **_kwargs: sample(100.0), epoch_port=lambda: 100.0, monotonic_port=lambda: 100.0)
    engine.decide(service.ControllerEvent("test", "start", "start", 100.0, 100.0))
    status = service.controller_status(paths)
    assert status["status"] == "running_or_last_checkpoint"
    assert status["sequence"] == 1


def test_linux_event_sources_wake_on_socket_and_inotify(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    paths.runtime_registry.mkdir(parents=True)
    paths.queue.mkdir(parents=True)
    sources = service.LinuxEventSources(
        paths,
        contracts.default_policy(),
        enable_psi=False,
        enable_systemd=False,
        cgroup_events=None,
        reservations_root=None,
    )
    try:
        adapters.send_event_socket(
            paths.socket,
            {
                "schema": "abyss_machine_memory_controller_event_v1",
                "kind": "demand_registered",
                "event_id": "socket-event",
                "details": {"demand_mib": 512},
            },
        )
        (paths.queue / "request.json").write_text(json.dumps({"demand_mib": 512}), encoding="utf-8")
        observed = []
        for _attempt in range(3):
            observed.extend(sources.poll(1_000))
            if {item.source for item in observed} >= {"socket", "queue"}:
                break
    finally:
        sources.close()

    assert any(item.event_id == "socket-event" for item in observed)
    assert any(item.source == "queue" and item.details["name"] == "request.json" for item in observed)
    assert not paths.socket.exists()


def test_controller_lock_allows_only_one_live_loop(tmp_path: Path) -> None:
    path = tmp_path / "controller.lock"
    first = service.ControllerLock(path)
    second = service.ControllerLock(path)
    try:
        assert first.acquire() is True
        assert second.acquire() is False
    finally:
        second.close()
        first.close()
    final = service.ControllerLock(path)
    try:
        assert final.acquire() is True
    finally:
        final.close()


def test_source_policy_registry_and_entrypoint_form_a_valid_shadow_surface(tmp_path: Path, capsys) -> None:
    paths = service.ControllerPaths(
        policy=ROOT / "config-templates" / "etc" / "abyss-machine" / "memory-controller-policy.json",
        registry=ROOT / "config-templates" / "etc" / "abyss-machine" / "memory-controller-registry.json",
        runtime_root=tmp_path / "run",
        evidence_root=tmp_path / "evidence",
    )
    validation = service.validate_controller_configuration(paths)
    assert validation["ok"] is True
    assert validation["policy_mode"] == "shadow"

    returncode = entrypoint.main([
        "memory",
        "controller",
        "status",
        "--policy",
        str(paths.policy),
        "--registry",
        str(paths.registry),
        "--runtime-root",
        str(paths.runtime_root),
        "--evidence-root",
        str(paths.evidence_root),
        "--json",
    ])
    output = json.loads(capsys.readouterr().out)
    assert returncode == 0
    assert output["status"] == "not_started"

    unit = (ROOT / "systemd" / "user" / "abyss-memory-controller.service").read_text(encoding="utf-8")
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in unit
    assert "IPAddressDeny=any" in unit
    assert "IPAddressAllow=localhost" in unit
    assert "RuntimeDirectory=abyss-machine/memory-controller" in unit
    assert "RuntimeDirectoryMode=0700" in unit
    assert "RuntimeDirectoryPreserve=restart" in unit
    assert "After=basic.target" in unit
    assert "After=default.target" not in unit


def test_systemd_lifecycle_filter_accepts_managed_or_registered_units_only() -> None:
    policy = contracts.default_policy()
    registry = {
        "workloads": [{
            "id": "model:test",
            "owner": "model-owner",
            "metadata": {"systemd_units": ["registered-model.service"]},
        }],
        "rules": [],
    }
    managed = service.systemd_unit_relevance("abyss-machine-ai-medium-token.service", policy, registry)
    registered = service.systemd_unit_relevance("registered-model.service", policy, registry)
    noisy = service.systemd_unit_relevance("libpod-deadbeef.scope", policy, registry)

    assert managed == {"relevant": True, "reason": "managed_prefix"}
    assert registered == {"relevant": True, "reason": "exact_registry_identity"}
    assert noisy == {"relevant": False, "reason": "unregistered_unit_preserved_without_immediate_decision"}


def test_runtime_contract_enrollment_is_validated_atomic_and_owner_stable(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    contract = {
        "id": "canary:model",
        "owner": "canary-owner",
        "role": "managed_model_canary",
        "importance": "normal",
        "posture": "background",
        "statefulness": "reconstructable",
        "protected": True,
        "memory": {"expected_mib": 256},
        "metadata": {"systemd_unit": "canary-model.service"},
    }

    registered = service.register_runtime_contract(paths, contract, epoch_port=lambda: 100.0)
    assert registered["ok"] is True
    path = Path(registered["path"])
    assert path.is_file()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert json.loads(path.read_text(encoding="utf-8"))["metadata"]["registered_epoch"] == 100.0

    takeover = service.register_runtime_contract(paths, {**contract, "owner": "other-owner"})
    assert takeover["ok"] is False
    assert takeover["status"] == "runtime_identity_owner_conflict"

    removed = service.unregister_runtime_contract(paths, "canary:model")
    assert removed["ok"] is True
    assert removed["status"] == "runtime_contract_removed"
    assert not path.exists()


def test_invalid_runtime_lifecycle_contract_is_not_written(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    result = service.register_runtime_contract(
        paths,
        {
            "id": "unsafe",
            "owner": "owner",
            "lifecycle": {"dehydrate": {"kind": "systemd", "target": "unsafe.service"}},
        },
    )

    assert result["ok"] is False
    assert set(result["issues"]) >= {"health_route_required", "rollback_route_required", "rehydrate_route_required"}
    assert not list(paths.runtime_registry.glob("*.json"))


def test_queue_snapshot_rejects_incomplete_contract_without_crashing(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "incomplete",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "launcher_pid": os.getpid(),
            "deadline_epoch": 300,
        },
    )

    snapshot = service.queue_snapshot(paths.queue, now_epoch=60, cleanup=True)

    assert snapshot["ok"] is False
    assert snapshot["items"] == []
    assert snapshot["errors"][0]["error"] == "queue_numeric_contract_invalid"


def test_queue_snapshot_removes_expired_request_from_demand(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    request_path = adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "expired",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "created_epoch": 10,
            "launcher_pid": os.getpid(),
            "deadline_epoch": 50,
        },
    )

    snapshot = service.queue_snapshot(paths.queue, now_epoch=60, cleanup=True)

    assert snapshot["ok"] is True
    assert snapshot["summary"] == {
        "count": 0,
        "demand_mib": 0,
        "error_count": 0,
        "expired_count": 1,
        "orphaned_count": 0,
        "removed_count": 1,
    }
    assert not request_path.exists()


def test_queue_snapshot_removes_orphaned_launcher_request(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    request_path = adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "orphaned",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "created_epoch": 10,
            "launcher_pid": 12345,
            "deadline_epoch": 100,
        },
    )

    snapshot = service.queue_snapshot(
        paths.queue,
        now_epoch=60,
        cleanup=True,
        pid_alive_port=lambda _pid: False,
    )

    assert snapshot["ok"] is True
    assert snapshot["summary"]["orphaned_count"] == 1
    assert snapshot["summary"]["removed_count"] == 1
    assert not request_path.exists()


def test_grant_snapshot_requires_controller_identity_and_bounded_ttl(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    adapters.resource_adapters.atomic_write_controller_queue_grant(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_grant_v1",
            "request_id": "valid",
            "owner": "indexer",
            "issued_epoch": 100,
            "expires_epoch": 105,
            "controller_sequence": 1,
            "nonce": "a" * 64,
        },
    )
    adapters.resource_adapters.atomic_write_controller_queue_grant(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_grant_v1",
            "request_id": "unbounded",
            "owner": "indexer",
            "issued_epoch": 100,
            "expires_epoch": 200,
            "controller_sequence": 1,
            "nonce": "b" * 64,
        },
    )

    snapshot = service.grant_snapshot(paths.grants, now_epoch=101, cleanup=True, maximum_ttl_sec=5)

    assert snapshot["ok"] is False
    assert [item["request_id"] for item in snapshot["items"]] == ["valid"]
    assert snapshot["errors"][0]["error"] == "grant_ttl_outside_policy"


def test_shadow_queue_plans_but_does_not_write_grant(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    paths.queue.mkdir(parents=True)
    adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "queued",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "created_epoch": 0,
            "launcher_pid": os.getpid(),
            "deadline_epoch": 100,
        },
    )
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: sample(60),
        reservations_port=lambda: {"ok": True, "summary": {"outstanding_mib": 0}},
        epoch_port=lambda: 60,
        monotonic_port=lambda: 60,
    )
    try:
        result = engine.decide(service.ControllerEvent("test", "queue", "shadow-queue", 60, 60))
    finally:
        engine.close()

    assert result["queue_plan"]["selected"] is None
    assert result["queue_execution"]["status"] == "shadow_or_not_authorized"
    assert not list(paths.grants.glob("*.json"))
    assert json.loads(paths.admission.read_text(encoding="utf-8"))["queue_live"] is False


def test_live_queue_writes_one_idempotent_grant_after_high_confidence(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["execution"] = {"enrolled": True}
    policy["actions"]["queue_control"]["live_enabled"] = True
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "queued",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "created_epoch": 0,
            "launcher_pid": os.getpid(),
            "deadline_epoch": 100,
        },
    )
    clock = Clock(0)
    samples = iter((sample(0), sample(30), sample(60)))
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: next(samples),
        reservations_port=lambda: {"ok": True, "summary": {"outstanding_mib": 0}},
        epoch_port=clock,
        monotonic_port=clock,
    )
    try:
        for index in range(3):
            result = engine.decide(service.ControllerEvent("test", "queue", f"live-queue-{index}", clock(), clock()))
            clock.value += 30
    finally:
        engine.close()

    grant = adapters.resource_adapters.controller_queue_grant(paths.runtime_root, "queued", now_epoch=60)
    assert result["decision"]["selected"]["action"] == "queue_control"
    assert result["queue_execution"]["status"] == "grant_written"
    assert grant["status"] == "granted"
    assert grant["controller_sequence"] == 3
    assert json.loads(paths.admission.read_text(encoding="utf-8"))["queue_live"] is True


def test_live_queue_fails_closed_on_invalid_grant_evidence(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["execution"] = {"enrolled": True}
    policy["actions"]["queue_control"]["live_enabled"] = True
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "queued",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "created_epoch": 0,
            "launcher_pid": os.getpid(),
            "deadline_epoch": 100,
        },
    )
    paths.grants.mkdir(parents=True)
    (paths.grants / "invalid.json").write_text("{}\n", encoding="utf-8")
    clock = Clock(0)
    samples = iter((sample(0), sample(30), sample(60)))
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: next(samples),
        reservations_port=lambda: {"ok": True, "summary": {"outstanding_mib": 0}},
        epoch_port=clock,
        monotonic_port=clock,
    )
    try:
        for index in range(3):
            result = engine.decide(service.ControllerEvent("test", "queue", f"invalid-grant-{index}", clock(), clock()))
            clock.value += 30
    finally:
        engine.close()

    admission = json.loads(paths.admission.read_text(encoding="utf-8"))
    assert result["decision"]["selected"]["execution"] == "shadow_only"
    assert result["queue_execution"]["status"] == "runtime_evidence_invalid"
    assert result["configuration"]["runtime_evidence_errors"] == ["grant_evidence_invalid"]
    assert adapters.resource_adapters.controller_queue_grant(paths.runtime_root, "queued", now_epoch=60)["status"] == "missing"
    assert admission["queue_live"] is False


def test_live_queue_fails_closed_on_incomplete_request_evidence(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["execution"] = {"enrolled": True}
    policy["actions"]["queue_control"]["live_enabled"] = True
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    adapters.resource_adapters.atomic_write_controller_queue_request(
        paths.runtime_root,
        {
            "schema": "abyss_machine_memory_controller_queue_request_v1",
            "id": "incomplete",
            "owner": "indexer",
            "posture": "background",
            "demand_mib": 1024,
            "priority": 10,
            "launcher_pid": os.getpid(),
            "deadline_epoch": 300,
        },
    )
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: sample(60),
        reservations_port=lambda: {"ok": True, "summary": {"outstanding_mib": 0}},
        epoch_port=lambda: 60,
        monotonic_port=lambda: 60,
    )
    try:
        result = engine.decide(service.ControllerEvent("test", "queue", "invalid-request", 60, 60))
    finally:
        engine.close()

    admission = json.loads(paths.admission.read_text(encoding="utf-8"))
    assert result["status"] == "decision_recorded"
    assert result["queue_plan"]["decisions"] == []
    assert result["queue_execution"]["status"] == "runtime_evidence_invalid"
    assert result["configuration"]["runtime_evidence_errors"] == ["queue_evidence_invalid"]
    assert admission["queue_live"] is False


def test_live_queue_fails_closed_on_malformed_reservation_evidence(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["execution"] = {"enrolled": True}
    policy["actions"]["queue_control"]["live_enabled"] = True
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: sample(60),
        reservations_port=lambda: {"ok": True, "summary": {"outstanding_mib": "not-a-number"}},
        epoch_port=lambda: 60,
        monotonic_port=lambda: 60,
    )
    try:
        result = engine.decide(service.ControllerEvent("test", "reservations", "invalid-reservations", 60, 60))
    finally:
        engine.close()

    admission = json.loads(paths.admission.read_text(encoding="utf-8"))
    assert result["status"] == "decision_recorded"
    assert result["configuration"]["runtime_evidence_errors"] == ["reservation_evidence_invalid"]
    assert result["decision"]["selected"]["execution"] == "shadow_only"
    assert admission["queue_live"] is False


def test_engine_executes_only_enrolled_lifecycle_after_fresh_pressure_preflight(tmp_path: Path, monkeypatch) -> None:
    paths = make_paths(tmp_path)
    policy = contracts.default_policy()
    policy["mode"] = "live"
    policy["execution"] = {"enrolled": True}
    policy["actions"]["queue_control"]["enabled"] = False
    policy["actions"]["managed_dehydrate"]["live_enabled"] = True
    paths.policy.write_text(json.dumps(policy), encoding="utf-8")
    registry = {
        "schema": "abyss_machine_memory_controller_registry_v1",
        "ok": True,
        "workloads": [enrolled_canary()],
        "rules": [],
        "runtime_count": 0,
        "errors": [],
    }
    monkeypatch.setattr(adapters, "load_registry", lambda *_args, **_kwargs: registry)
    calls: list[str] = []

    def route_port(item: dict) -> dict:
        calls.append(item["url"])
        if item["url"].endswith("/activity"):
            return {"ok": True, "document": {"active_requests": 0}}
        return {"ok": True, "document": {"ok": True, "service": "canary-model"}}

    pressure = sample(60, 4_000)
    pressure["psi_full_total_usec"] = 1_800_000
    samples = iter((sample(0), sample(30), pressure, sample(60, 4_000), sample(60, 4_200)))
    measurements = iter((
        {"ok": True, "status": "measurement_ready", "memory_mib": 300, "swap_mib": 20},
        {"ok": True, "status": "measurement_ready", "memory_mib": 100, "swap_mib": 10},
    ))
    clock = Clock(0)
    engine = service.ControllerEngine(
        paths,
        sample_port=lambda **_kwargs: next(samples),
        reservations_port=lambda: {"ok": True, "summary": {"outstanding_mib": 0}},
        lifecycle_route_port=route_port,
        lifecycle_measurement_port=lambda _measurement: next(measurements),
        epoch_port=clock,
        monotonic_port=clock,
    )
    try:
        for index in range(3):
            result = engine.decide(service.ControllerEvent("test", "pressure", f"lifecycle-{index}", clock(), clock()))
            clock.value += 30
        evidence = engine.store.summary()
    finally:
        engine.close()

    assert result["decision"]["selected"]["action"] == "managed_dehydrate"
    assert result["decision"]["live_action_authorized"] is True
    assert result["lifecycle_execution"]["status"] == "action_completed_verified"
    assert result["lifecycle_execution"]["observed_freed_mib"] == 200.0
    assert result["lifecycle_execution"]["benefit_verified"] is True
    assert any(item.endswith("/dehydrate") for item in calls)
    assert evidence["action_outcomes"]["count"] == 1
    assert not paths.pending_action.exists()
