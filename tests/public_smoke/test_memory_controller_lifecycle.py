from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from abyss_machine import memory_controller_adapters as adapters
from abyss_machine import memory_controller_contracts as contracts
from abyss_machine import memory_controller_lifecycle as lifecycle


def route(path: str, *, method: str, expect: dict | None = None) -> dict:
    return {
        "kind": "local_http_json_v1",
        "url": f"http://127.0.0.1:45451{path}",
        "method": method,
        "timeout_ms": 500,
        "maximum_response_bytes": 4096,
        "expect": {"json_equals": expect or {}},
    }


def workload() -> dict:
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
            "activity": route("/activity", method="GET", expect={"active_requests": 0}),
            "dehydrate": route("/dehydrate", method="POST", expect={"ok": True}),
            "rehydrate": route("/rehydrate", method="POST", expect={"ok": True}),
            "health": route("/health", method="GET", expect={"ok": True, "service": "canary-model"}),
            "rollback": route("/rollback", method="POST", expect={"ok": True}),
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


def selected() -> dict:
    item = workload()
    enrollment = contracts.lifecycle_action_enrolled(item, "managed_dehydrate", now_epoch=100)
    return {
        "action": "managed_dehydrate",
        "workload_id": item["id"],
        "owner": item["owner"],
        "importance": item["importance"],
        "protected": item["protected"],
        "expected_freed_mib": 200,
        "enrollment": enrollment,
        "lifecycle_plan": {
            "action_route_name": "dehydrate",
            "action_route": item["lifecycle"]["dehydrate"],
            "activity_route": item["lifecycle"]["activity"],
            "health_route": item["lifecycle"]["health"],
            "rollback_route": item["lifecycle"]["rollback"],
            "rehydrate_route": item["lifecycle"]["rehydrate"],
            "measurement": item["measurement"],
        },
    }


class Clock:
    def __init__(self, value: float) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def test_action_plan_rejects_protected_workload_even_with_enrollment_claim() -> None:
    candidate = selected()
    candidate["protected"] = True
    candidate["enrollment"] = {**candidate["enrollment"], "authorized": True}
    plan = lifecycle.build_action_plan(candidate, event_id="protected", sequence=1, now_epoch=100)

    checked = lifecycle.validate_action_plan(plan, now_epoch=100)

    assert checked["valid"] is False
    assert "plan_workload_not_mutable" in checked["issues"]


def test_lifecycle_action_lock_serializes_concurrent_relief(tmp_path: Path) -> None:
    first = lifecycle.ActionLock(tmp_path / "action.lock")
    second = lifecycle.ActionLock(tmp_path / "action.lock")
    try:
        assert first.acquire() is True
        assert second.acquire() is False
    finally:
        second.close()
        first.close()


def test_execute_plan_checks_idle_health_records_outcome_and_deduplicates(tmp_path: Path) -> None:
    clock = Clock(100)
    plan = lifecycle.build_action_plan(selected(), event_id="event-1", sequence=1, now_epoch=clock())
    calls: list[str] = []

    def route_port(item: dict) -> dict:
        calls.append(item["url"])
        documents = {
            "/activity": {"active_requests": 0},
            "/health": {"ok": True, "service": "canary-model"},
            "/dehydrate": {"ok": True},
        }
        path = "/" + item["url"].split("/", 3)[-1]
        return {"ok": True, "status": "response_ready", "document": documents[path], "elapsed_ms": 1}

    samples = iter(({"mem_available_mib": 1000}, {"mem_available_mib": 1200}))
    measurements = iter((
        {"ok": True, "status": "measurement_ready", "memory_mib": 300, "swap_mib": 20},
        {"ok": True, "status": "measurement_ready", "memory_mib": 100, "swap_mib": 10},
    ))
    store = adapters.EvidenceStore(tmp_path / "evidence.sqlite3")
    try:
        outcome = lifecycle.execute_action_plan(
            plan,
            pending_path=tmp_path / "pending.json",
            lock_path=tmp_path / "action.lock",
            store=store,
            route_port=route_port,
            measurement_port=lambda _measurement: next(measurements),
            sample_port=lambda: next(samples),
            history_limit=20,
            retention_hours=24,
            epoch_port=clock,
            monotonic_port=clock,
            sleep_port=lambda _seconds: None,
        )
        call_count = len(calls)
        duplicate = lifecycle.execute_action_plan(
            plan,
            pending_path=tmp_path / "pending.json",
            lock_path=tmp_path / "action.lock",
            store=store,
            route_port=route_port,
            measurement_port=lambda _measurement: {"ok": True, "memory_mib": 100},
            sample_port=lambda: {"mem_available_mib": 1200},
            history_limit=20,
            retention_hours=24,
            epoch_port=clock,
            monotonic_port=clock,
        )
        summary = store.summary()
    finally:
        store.close()

    assert outcome["ok"] is True
    assert outcome["observed_freed_mib"] == 200.0
    assert outcome["benefit_verified"] is True
    assert outcome["classification"] == "true_positive"
    assert not (tmp_path / "pending.json").exists()
    assert duplicate["status"] == "duplicate_action_suppressed"
    assert len(calls) == call_count
    assert summary["action_outcomes"]["count"] == 1


def test_busy_preflight_never_calls_mutation_route(tmp_path: Path) -> None:
    plan = lifecycle.build_action_plan(selected(), event_id="event-busy", sequence=1, now_epoch=100)
    calls: list[str] = []

    def route_port(item: dict) -> dict:
        calls.append(item["url"])
        if item["url"].endswith("/activity"):
            return {"ok": True, "document": {"active_requests": 1}}
        return {"ok": True, "document": {"ok": True, "service": "canary-model"}}

    store = adapters.EvidenceStore(tmp_path / "evidence.sqlite3")
    try:
        outcome = lifecycle.execute_action_plan(
            plan,
            pending_path=tmp_path / "pending.json",
            lock_path=tmp_path / "action.lock",
            store=store,
            route_port=route_port,
            measurement_port=lambda _measurement: {"ok": True, "memory_mib": 300},
            sample_port=lambda: {"mem_available_mib": 1000},
            history_limit=20,
            retention_hours=24,
            epoch_port=lambda: 100,
            monotonic_port=lambda: 100,
        )
    finally:
        store.close()

    assert outcome["status"] == "live_preflight_failed"
    assert not any(item.endswith("/dehydrate") for item in calls)
    assert not (tmp_path / "pending.json").exists()


def test_unavailable_preflight_endpoint_fails_closed_without_mutation(tmp_path: Path) -> None:
    plan = lifecycle.build_action_plan(selected(), event_id="event-unavailable", sequence=1, now_epoch=100)
    calls: list[str] = []

    def route_port(item: dict) -> dict:
        calls.append(item["url"])
        if item["url"].endswith("/activity"):
            return {"ok": False, "status": "endpoint_unavailable", "error": "connection refused"}
        return {"ok": True, "document": {"ok": True, "service": "canary-model"}}

    store = adapters.EvidenceStore(tmp_path / "evidence.sqlite3")
    try:
        outcome = lifecycle.execute_action_plan(
            plan,
            pending_path=tmp_path / "pending.json",
            lock_path=tmp_path / "action.lock",
            store=store,
            route_port=route_port,
            measurement_port=lambda _measurement: {"ok": True, "memory_mib": 300},
            sample_port=lambda: {"mem_available_mib": 1000},
            history_limit=20,
            retention_hours=24,
            epoch_port=lambda: 100,
            monotonic_port=lambda: 100,
        )
    finally:
        store.close()

    assert outcome["status"] == "live_preflight_failed"
    assert outcome["activity"]["status"] == "route_transport_failed"
    assert not any(item.endswith("/dehydrate") for item in calls)
    assert not (tmp_path / "pending.json").exists()


def test_failed_post_health_runs_typed_rollback_and_records_failure(tmp_path: Path) -> None:
    plan = lifecycle.build_action_plan(selected(), event_id="event-rollback", sequence=1, now_epoch=100)
    state = {"mutated": False, "rolled_back": False, "health_calls": 0}

    def route_port(item: dict) -> dict:
        url = item["url"]
        if url.endswith("/activity"):
            return {"ok": True, "document": {"active_requests": 0}}
        if url.endswith("/dehydrate"):
            state["mutated"] = True
            return {"ok": True, "document": {"ok": True}}
        if url.endswith("/rollback"):
            state["rolled_back"] = True
            return {"ok": True, "document": {"ok": True}}
        if url.endswith("/health"):
            state["health_calls"] += 1
            healthy = not state["mutated"] or state["rolled_back"]
            return {"ok": True, "document": {"ok": healthy, "service": "canary-model"}}
        raise AssertionError(url)

    store = adapters.EvidenceStore(tmp_path / "evidence.sqlite3")
    try:
        outcome = lifecycle.execute_action_plan(
            plan,
            pending_path=tmp_path / "pending.json",
            lock_path=tmp_path / "action.lock",
            store=store,
            route_port=route_port,
            measurement_port=lambda _measurement: {"ok": True, "memory_mib": 300},
            sample_port=lambda: {"mem_available_mib": 1000},
            history_limit=20,
            retention_hours=24,
            epoch_port=lambda: 100,
            monotonic_port=lambda: 100,
            sleep_port=lambda _seconds: None,
        )
    finally:
        store.close()

    assert outcome["ok"] is False
    assert outcome["status"] == "action_failed_rolled_back"
    assert outcome["rollback"]["status"] == "rollback_verified"
    assert state["rolled_back"] is True
    assert outcome["pending_removed"] is True


def test_failed_rollback_retains_pending_and_recovery_never_repeats_action(tmp_path: Path) -> None:
    plan = lifecycle.build_action_plan(selected(), event_id="event-unresolved", sequence=1, now_epoch=100)
    pending = tmp_path / "pending.json"
    calls: list[str] = []
    state = {"mutated": False}

    def route_port(item: dict) -> dict:
        url = item["url"]
        calls.append(url)
        if url.endswith("/activity"):
            return {"ok": True, "document": {"active_requests": 0}}
        if url.endswith("/dehydrate"):
            state["mutated"] = True
            return {"ok": True, "document": {"ok": True}}
        if url.endswith("/health"):
            return {
                "ok": True,
                "document": {"ok": not state["mutated"], "service": "canary-model"},
            }
        if url.endswith("/rollback"):
            return {"ok": True, "document": {"ok": False}}
        raise AssertionError(url)

    store = adapters.EvidenceStore(tmp_path / "evidence.sqlite3")
    try:
        failed = lifecycle.execute_action_plan(
            plan,
            pending_path=pending,
            lock_path=tmp_path / "action.lock",
            store=store,
            route_port=route_port,
            measurement_port=lambda _measurement: {"ok": True, "memory_mib": 300},
            sample_port=lambda: {"mem_available_mib": 1000},
            history_limit=20,
            retention_hours=24,
            epoch_port=lambda: 100,
            monotonic_port=lambda: 100,
            sleep_port=lambda _seconds: None,
        )
        action_call_count = sum(item.endswith("/dehydrate") for item in calls)
        recovered = lifecycle.recover_pending_action(
            pending_path=pending,
            store=store,
            registry={"workloads": [workload()], "rules": []},
            route_port=route_port,
            history_limit=20,
            retention_hours=24,
            epoch_port=lambda: 101,
            sleep_port=lambda _seconds: None,
        )
        persisted = store.action_outcome(plan["nonce"])
    finally:
        store.close()

    assert failed["status"] == "action_failed_rollback_failed"
    assert failed["pending_resolved"] is False
    assert recovered["status"] == "recovery_rollback_failed"
    assert recovered["pending_resolved"] is False
    assert sum(item.endswith("/dehydrate") for item in calls) == action_call_count == 1
    assert pending.is_file()
    assert adapters.load_json(pending)[0]["status"] == "owner_recovery_required"
    assert persisted["pending_resolved"] is False


def test_recovery_never_repeats_action_and_cleans_verified_pending_plan(tmp_path: Path) -> None:
    plan = lifecycle.build_action_plan(selected(), event_id="event-crash", sequence=1, now_epoch=100)
    pending = tmp_path / "pending.json"
    adapters.atomic_write_json(pending, {**plan, "status": "executing"})
    calls: list[str] = []

    def route_port(item: dict) -> dict:
        calls.append(item["url"])
        return {"ok": True, "document": {"ok": True, "service": "canary-model"}}

    registry = {"workloads": [workload()], "rules": []}
    store = adapters.EvidenceStore(tmp_path / "evidence.sqlite3")
    try:
        recovered = lifecycle.recover_pending_action(
            pending_path=pending,
            store=store,
            registry=registry,
            route_port=route_port,
            history_limit=20,
            retention_hours=24,
            epoch_port=lambda: 200,
            sleep_port=lambda _seconds: None,
        )
    finally:
        store.close()

    assert recovered["status"] == "recovered_health_verified"
    assert recovered["recovery"]["action_was_not_repeated"] is True
    assert not any(item.endswith("/dehydrate") for item in calls)
    assert not pending.exists()
