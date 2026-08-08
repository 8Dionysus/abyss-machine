from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_relief_adapters


def adapter(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "id": "abyss-stack-reranker",
        "owner": "abyss-stack",
        "workload_id": "rerank-api:qwen3-0.6b",
        "importance_class": "reloadable_idle",
        "data_risk": False,
        "recoverability": "reload",
        "expected_relief_mib": 768,
        "minimum_idle_sec": 60,
        "health_url": "http://127.0.0.1:5405/health",
        "action_url": "http://127.0.0.1:5405/admin/unload",
        "resume": "lazy_load_on_rerank",
        "rollback": "health_then_rerank_probe",
    }
    document.update(overrides)
    return document


def test_owner_offer_requires_idle_loaded_and_no_active_requests() -> None:
    healthy = lambda *_args: {"ok": True, "loaded": True, "active_requests": 0, "idle_for_sec": 120}
    active = lambda *_args: {"ok": True, "loaded": True, "active_requests": 1, "idle_for_sec": 120}
    unknown = lambda *_args: {"ok": True, "loaded": True, "active_requests": 0}

    offered = resource_relief_adapters.owner_offer(adapter(), json_request=healthy)
    refused_active = resource_relief_adapters.owner_offer(adapter(), json_request=active)
    refused_unknown = resource_relief_adapters.owner_offer(adapter(), json_request=unknown)

    assert offered["offered"] is True
    assert offered["activity_proof"] == {"active_requests": 0, "idle_for_sec": 120.0}
    assert refused_active["reason"] == "active_or_unknown_requests"
    assert refused_unknown["reason"] == "not_idle_or_idle_unknown"


def test_owner_offer_rejects_external_or_data_risk_adapter_before_network() -> None:
    calls: list[object] = []
    external = resource_relief_adapters.owner_offer(
        adapter(health_url="https://example.com/health"),
        json_request=lambda *args: calls.append(args) or {},
    )
    risky = resource_relief_adapters.owner_offer(
        adapter(data_risk=True),
        json_request=lambda *args: calls.append(args) or {},
    )

    assert external["offered"] is False
    assert "owner_endpoint_not_fixed_loopback_http" in external["errors"]
    assert "data_risk_not_proven_false" in risky["errors"]
    assert calls == []


def test_coordinate_one_executes_only_selected_offer_and_requires_unloaded_result() -> None:
    calls: list[tuple[str, str]] = []

    def transport(method: str, url: str, _timeout: float, payload: object) -> dict[str, object]:
        calls.append((method, url))
        if method == "GET":
            return {"ok": True, "loaded": True, "active_requests": 0, "idle_for_sec": 120}
        assert isinstance(payload, dict)
        return {
            "ok": True,
            "action_id": payload["action_id"],
            "owner_gate": {"active_requests_at_action": 0, "data_risk": False},
            "unloaded": True,
            "loaded": False,
            "reason": "owner_relief",
        }

    result = resource_relief_adapters.coordinate_one(
        {"owner_relief_adapters": [adapter()], "relief_settle_sec": 0},
        needed_relief_mib=512,
        request_id="tool-789",
        json_request=transport,
        sleep_port=lambda _seconds: None,
    )

    assert result["ok"] is True
    assert result["action_executed"] is True
    assert result["importance_class"] == "reloadable_idle"
    assert calls == [
        ("GET", "http://127.0.0.1:5405/health"),
        ("POST", "http://127.0.0.1:5405/admin/unload"),
    ]
    assert "action_url" not in result


def test_coordinate_one_preserves_when_no_safe_offer() -> None:
    result = resource_relief_adapters.coordinate_one(
        {"owner_relief_adapters": [adapter()]},
        needed_relief_mib=512,
        request_id="tool-789",
        json_request=lambda *_args: {"ok": True, "loaded": True, "active_requests": 2, "idle_for_sec": 999},
    )

    assert result["ok"] is False
    assert result["action_executed"] is False
    assert result["reason"] == "no_sufficient_safe_owner_offer"


def test_coordinate_one_preserves_when_safe_offer_is_insufficient() -> None:
    calls: list[str] = []

    def transport(method: str, _url: str, _timeout: float, _payload: object) -> dict[str, object]:
        calls.append(method)
        return {"ok": True, "loaded": True, "active_requests": 0, "idle_for_sec": 120}

    result = resource_relief_adapters.coordinate_one(
        {"owner_relief_adapters": [adapter(expected_relief_mib=256)]},
        needed_relief_mib=512,
        request_id="tool-789",
        json_request=transport,
    )

    assert result["action_executed"] is False
    assert result["reason"] == "no_sufficient_safe_owner_offer"
    assert calls == ["GET"]


def test_coordinate_one_does_not_probe_owners_without_measured_need() -> None:
    calls: list[object] = []
    result = resource_relief_adapters.coordinate_one(
        {"owner_relief_adapters": [adapter()]},
        needed_relief_mib=0,
        request_id="tool-789",
        json_request=lambda *args: calls.append(args) or {},
    )

    assert result == {
        "ok": True,
        "action_executed": False,
        "reason": "no_relief_required",
        "offer_count": 0,
    }
    assert calls == []


def test_coordinate_one_rejects_legacy_non_atomic_unload_response() -> None:
    def transport(method: str, _url: str, _timeout: float, _payload: object) -> dict[str, object]:
        if method == "GET":
            return {"ok": True, "loaded": True, "active_requests": 0, "idle_for_sec": 120}
        return {"ok": True, "unloaded": True, "loaded": False, "reason": "admin_request"}

    result = resource_relief_adapters.coordinate_one(
        {"owner_relief_adapters": [adapter()], "relief_settle_sec": 0},
        needed_relief_mib=512,
        request_id="tool-789",
        json_request=transport,
        sleep_port=lambda _seconds: None,
    )

    assert result["ok"] is False
    assert result["action_executed"] is True
    assert result["result"]["owner_gate_valid"] is False
