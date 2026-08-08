from __future__ import annotations

import json
import hashlib
import time
from typing import Any, Callable, Mapping
from urllib import error, parse, request


JsonRequestPort = Callable[[str, str, float, Mapping[str, Any] | None], dict[str, Any]]

_RELIEF_CLASS_ORDER = {
    "reloadable_idle": 0,
    "checkpointable_background": 1,
    "resumable_detached": 2,
    "explicitly_disposable_emergency": 3,
}


def _loopback_http_url(value: object) -> str | None:
    text = str(value or "").strip()
    try:
        parsed = parse.urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}:
        return None
    if parsed.username or parsed.password or parsed.fragment or not parsed.port:
        return None
    return text


def http_json(
    method: str,
    url: str,
    timeout_sec: float,
    document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = json.dumps(dict(document or {}), sort_keys=True, separators=(",", ":")).encode("utf-8") if method == "POST" else None
    req = request.Request(url, data=payload, method=method, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=max(0.1, timeout_sec)) as response:
            raw = response.read(256 * 1024 + 1)
    except (error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": "owner_transport_unavailable", "error_type": type(exc).__name__}
    if len(raw) > 256 * 1024:
        return {"ok": False, "error": "owner_response_too_large"}
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "error": "owner_response_invalid"}
    return document if isinstance(document, dict) else {"ok": False, "error": "owner_response_not_object"}


def owner_offer(
    adapter: Mapping[str, Any],
    *,
    json_request: JsonRequestPort = http_json,
) -> dict[str, Any]:
    adapter_id = str(adapter.get("id") or "").strip()
    owner = str(adapter.get("owner") or "").strip()
    workload_id = str(adapter.get("workload_id") or "").strip()
    importance_class = str(adapter.get("importance_class") or "").strip()
    health_url = _loopback_http_url(adapter.get("health_url"))
    action_url = _loopback_http_url(adapter.get("action_url"))
    try:
        expected_relief_mib = float(adapter.get("expected_relief_mib") or 0.0)
        minimum_idle_sec = max(0.0, float(adapter.get("minimum_idle_sec") or 0.0))
        timeout_sec = max(0.1, min(float(adapter.get("timeout_sec") or 2.0), 10.0))
    except (TypeError, ValueError):
        expected_relief_mib = 0.0
        minimum_idle_sec = 0.0
        timeout_sec = 2.0
    errors: list[str] = []
    if not adapter_id or not owner or not workload_id:
        errors.append("owner_identity_invalid")
    if importance_class not in _RELIEF_CLASS_ORDER:
        errors.append("importance_class_not_automatable")
    if not health_url or not action_url:
        errors.append("owner_endpoint_not_fixed_loopback_http")
    if expected_relief_mib <= 0:
        errors.append("expected_relief_invalid")
    if adapter.get("data_risk") is not False:
        errors.append("data_risk_not_proven_false")
    if str(adapter.get("recoverability") or "") not in {"reload", "resume", "checkpoint", "dispose"}:
        errors.append("recoverability_invalid")
    if errors:
        return {"ok": False, "offered": False, "adapter_id": adapter_id or None, "errors": errors}

    health = json_request("GET", health_url, timeout_sec, None)
    if health.get("ok") is not True:
        return {"ok": False, "offered": False, "adapter_id": adapter_id, "errors": ["owner_health_unavailable"]}
    loaded = health.get(str(adapter.get("loaded_field") or "loaded"))
    active_requests = health.get(str(adapter.get("active_requests_field") or "active_requests"))
    idle_for_sec = health.get(str(adapter.get("idle_for_field") or "idle_for_sec"))
    try:
        active_count = int(active_requests)
    except (TypeError, ValueError):
        active_count = -1
    try:
        idle_seconds = float(idle_for_sec)
    except (TypeError, ValueError):
        idle_seconds = -1.0
    if loaded is not True:
        return {"ok": True, "offered": False, "adapter_id": adapter_id, "reason": "not_loaded"}
    if active_count != 0:
        return {"ok": True, "offered": False, "adapter_id": adapter_id, "reason": "active_or_unknown_requests"}
    if idle_seconds < minimum_idle_sec:
        return {"ok": True, "offered": False, "adapter_id": adapter_id, "reason": "not_idle_or_idle_unknown"}
    return {
        "ok": True,
        "offered": True,
        "adapter_id": adapter_id,
        "owner": owner,
        "workload_id": workload_id,
        "importance_class": importance_class,
        "data_risk": False,
        "recoverability": adapter.get("recoverability"),
        "expected_relief_mib": round(expected_relief_mib, 3),
        "cold_return_cost": str(adapter.get("cold_return_cost") or "owner_measured"),
        "activity_proof": {"active_requests": active_count, "idle_for_sec": round(idle_seconds, 3)},
        "health": {"ok": True, "loaded": True},
        "resume": str(adapter.get("resume") or "owner_reload_on_demand"),
        "rollback": str(adapter.get("rollback") or "owner_health_and_reload_probe"),
        "action": "owner_http_unload",
        "action_url": action_url,
        "health_url": health_url,
        "timeout_sec": timeout_sec,
    }


def select_offer(offers: list[Mapping[str, Any]], *, needed_relief_mib: float) -> dict[str, Any] | None:
    eligible = [
        dict(item)
        for item in offers
        if item.get("offered") is True
        and item.get("data_risk") is False
        and str(item.get("importance_class")) in _RELIEF_CLASS_ORDER
    ]
    if not eligible:
        return None
    needed = max(0.0, float(needed_relief_mib))
    sufficient = [item for item in eligible if float(item.get("expected_relief_mib") or 0.0) >= needed]
    if not sufficient:
        return None
    return min(
        sufficient,
        key=lambda item: (
            _RELIEF_CLASS_ORDER[str(item["importance_class"])],
            float(item.get("expected_relief_mib") or 0.0),
            str(item.get("adapter_id") or ""),
        ),
    )


def coordinate_one(
    policy: Mapping[str, Any],
    *,
    needed_relief_mib: float,
    request_id: str,
    json_request: JsonRequestPort = http_json,
    sleep_port: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if needed_relief_mib <= 0:
        return {
            "ok": True,
            "action_executed": False,
            "reason": "no_relief_required",
            "offer_count": 0,
        }
    configured = policy.get("owner_relief_adapters") if isinstance(policy.get("owner_relief_adapters"), list) else []
    offers = [owner_offer(item, json_request=json_request) for item in configured if isinstance(item, dict)]
    selected = select_offer(offers, needed_relief_mib=needed_relief_mib)
    if selected is None:
        return {
            "ok": False,
            "action_executed": False,
            "reason": "no_sufficient_safe_owner_offer",
            "offer_count": sum(item.get("offered") is True for item in offers),
            "owner_errors": [item for item in offers if item.get("ok") is not True],
        }
    action_id = hashlib.sha256(f"{selected['adapter_id']}\0{request_id}".encode("utf-8")).hexdigest()[:32]
    result = json_request(
        "POST",
        str(selected["action_url"]),
        float(selected["timeout_sec"]),
        {
            "action": "relieve_memory",
            "action_id": action_id,
            "owner": selected["owner"],
            "workload_id": selected["workload_id"],
        },
    )
    owner_gate = result.get("owner_gate") if isinstance(result.get("owner_gate"), dict) else {}
    action_ok = bool(
        result.get("ok") is True
        and result.get("action_id") == action_id
        and owner_gate.get("active_requests_at_action") == 0
        and owner_gate.get("data_risk") is False
        and result.get("loaded") is False
    )
    if action_ok:
        sleep_port(max(0.0, min(float(policy.get("relief_settle_sec") or 0.25), 2.0)))
    return {
        "ok": action_ok,
        "action_executed": True,
        "adapter_id": selected["adapter_id"],
        "owner": selected["owner"],
        "workload_id": selected["workload_id"],
        "importance_class": selected["importance_class"],
        "expected_relief_mib": selected["expected_relief_mib"],
        "activity_proof": selected["activity_proof"],
        "recoverability": selected["recoverability"],
        "action": selected["action"],
        "action_id": action_id,
        "result": {
            "ok": result.get("ok") is True,
            "unloaded": result.get("unloaded"),
            "loaded": result.get("loaded"),
            "reason": result.get("reason"),
            "error": result.get("error"),
            "owner_gate_valid": bool(action_ok),
        },
        "resume": selected["resume"],
        "rollback": selected["rollback"],
    }
