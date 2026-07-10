from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import runtime_evidence_contracts
from . import self_awareness_contracts


@dataclass(frozen=True)
class SelfAwarenessResidentWorkerConfig:
    schema_prefix: str


def resident_worker_detail(
    status_doc: dict[str, Any],
    monitor_doc: dict[str, Any],
    digest_doc: dict[str, Any],
    micro_doc: dict[str, Any],
    evals_doc: dict[str, Any],
    candidates_doc: dict[str, Any],
    *,
    config: SelfAwarenessResidentWorkerConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    safe_float = runtime_evidence_contracts.safe_float
    safe_int = runtime_evidence_contracts.safe_int
    def as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def first_dict(values: Any) -> dict[str, Any]:
        if not isinstance(values, list):
            return {}
        return next((item for item in values if isinstance(item, dict)), {})

    health = as_dict(status_doc.get("health"))
    monitor_status = as_dict(monitor_doc.get("status"))
    serving = as_dict(health.get("serving")) or as_dict(status_doc.get("serving")) or as_dict(monitor_status.get("serving"))
    health_check = as_dict(health.get("health"))
    health_http = as_dict(health_check.get("_http"))
    models_health = as_dict(health.get("models"))
    models_http = as_dict(models_health.get("_http"))
    primary_model = first_dict(models_health.get("data")) or first_dict(models_health.get("models"))
    model_meta = as_dict(primary_model.get("meta"))
    service = as_dict(monitor_status.get("service")) or as_dict(status_doc.get("service"))
    metrics = as_dict(monitor_status.get("metrics")) or as_dict(status_doc.get("metrics"))
    micro_summary = as_dict(micro_doc.get("summary"))
    eval_summary = as_dict(evals_doc.get("summary"))
    candidates_summary = as_dict(candidates_doc.get("summary"))

    monitor_ok = monitor_doc.get("ok")
    if monitor_ok is None:
        monitor_ok = monitor_status.get("ok")
    if monitor_ok is None:
        monitor_ok = bool(status_doc.get("ok") and monitor_status.get("status") == "running")

    health_ok = health.get("ok")
    if health_ok is None:
        health_ok = bool(health_http.get("ok") or health_check.get("status") == "ok")

    candidate_action_execution = candidates_summary.get("action_execution")
    worker_ok = bool(
        status_doc.get("ok")
        and status_doc.get("status") == "running"
        and monitor_ok is not False
        and digest_doc.get("ok")
        and micro_doc.get("ok")
        and evals_doc.get("ok")
        and candidates_doc.get("ok")
        and candidate_action_execution is False
    )

    return {
        "status": status_doc.get("status") or monitor_status.get("status"),
        "ok": worker_ok,
        "profile": status_doc.get("profile") or monitor_status.get("profile") or "gemma4.spark",
        "model": status_doc.get("model") if isinstance(status_doc.get("model"), dict) else None,
        "serving": {
            "owner": serving.get("owner"),
            "base_url": serving.get("base_url"),
            "external_endpoint": serving.get("external_endpoint"),
            "local_fallback_allowed": serving.get("local_fallback_allowed"),
            "stack_owned_serving": serving.get("owner") == "abyss-stack",
        },
        "health": {
            "ok": bool(health_ok),
            "health_status_code": health_http.get("status"),
            "health_latency_ms": safe_float(health_http.get("latency_ms")),
            "models_status_code": models_http.get("status"),
            "models_latency_ms": safe_float(models_http.get("latency_ms")),
            "model_id": primary_model.get("id") or primary_model.get("name") or primary_model.get("model"),
            "n_ctx": safe_int(model_meta.get("n_ctx"), 0) or None,
            "n_ctx_train": safe_int(model_meta.get("n_ctx_train"), 0) or None,
            "n_embd": safe_int(model_meta.get("n_embd"), 0) or None,
            "n_params": safe_int(model_meta.get("n_params"), 0) or None,
            "served_model_size_bytes": safe_int(model_meta.get("size"), 0) or None,
        },
        "monitor": {
            "ok": bool(monitor_ok),
            "status": monitor_status.get("status"),
            "service_unit": service.get("service"),
            "service_active": service.get("active"),
            "service_enabled": service.get("enabled"),
            "legacy_start_timer_active": nested_get(service, ["timer", "active"]),
            "monitor_timer_active": nested_get(service, ["monitor_timer", "active"]),
            "digest_timer_active": nested_get(service, ["digest_timer", "active"]),
            "jobs_timer_active": nested_get(service, ["jobs_timer", "active"]),
            "micro_timer_active": nested_get(service, ["micro_timer", "active"]),
            "stack_owned_mode_legacy_service_expected_inactive": serving.get("owner") == "abyss-stack" and service.get("active") == "inactive",
        },
        "resource_thermal": {
            "package_temp_c": safe_float(metrics.get("package_temp_c")),
            "loadavg": metrics.get("loadavg"),
            "power_profile": nested_get(metrics, ["power", "profile"]),
            "on_ac": nested_get(metrics, ["power", "on_ac"]),
        },
        "candidate_context": {
            "digest_ok": digest_doc.get("ok"),
            "digest_status": digest_doc.get("status"),
            "micro_ok": micro_doc.get("ok"),
            "micro_status": micro_summary.get("status"),
            "micro_selected_job": micro_summary.get("selected_job"),
            "micro_next_job": micro_summary.get("next_job"),
            "micro_elapsed_ms": safe_float(micro_summary.get("elapsed_ms")),
            "micro_model_used": micro_summary.get("model_used"),
            "micro_fallback_used": micro_summary.get("fallback_used"),
            "candidate_readmodel": micro_summary.get("candidate_readmodel") if isinstance(micro_summary.get("candidate_readmodel"), dict) else None,
            "candidates": safe_int(candidates_summary.get("candidates"), 0) or None,
            "review_required": safe_int(candidates_summary.get("review_required"), 0),
            "selected": safe_int(candidates_summary.get("selected"), 0),
            "selected_for_heartbeat": safe_int(candidates_summary.get("selected_for_heartbeat"), 0),
            "selected_for_e4b_review": safe_int(candidates_summary.get("selected_for_e4b_review"), 0),
            "action_execution": candidate_action_execution,
        },
        "evals": {
            "overall_score": safe_float(eval_summary.get("overall_score")),
            "checks": safe_int(eval_summary.get("checks"), 0),
            "fails": safe_int(eval_summary.get("fails"), 0),
            "warnings": safe_int(eval_summary.get("warnings"), 0),
            "candidates": safe_int(eval_summary.get("candidates"), 0),
            "selected_for_e4b_review": safe_int(eval_summary.get("selected_for_e4b_review"), 0),
            "degraded_or_fallback_jobs": safe_int(eval_summary.get("degraded_or_fallback_jobs"), 0),
            "elapsed_ms": safe_float(eval_summary.get("elapsed_ms")),
        },
        "policy": {
            "model_execution_in_self_awareness_graph": False,
            "candidate_synthesis_only": True,
            "action_execution": candidate_action_execution is True,
            "resource_mode_gated": True,
            "host_layer_mutates_stack": False,
            "serving_owner": serving.get("owner"),
            "abyss_machine_writes_stack": False,
            "candidate_output_is_owner_truth": False,
        },
        "cognitive_contract": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_resident_cognitive_contract_v1",
            "worker": "warm-e2b/gemma4.spark",
            "bounded_context_packet_required": True,
            "read_only_tool_inventory_required": True,
            "hypothesis_testing_required": True,
            "contradiction_notes_required": True,
            "evidence_cited_summary_required": True,
            "resource_mode_gated_escalation_required": True,
            "direct_model_generation_in_self_awareness": False,
            "candidate_synthesis_only": True,
            "candidate_output_is_owner_truth": False,
            "host_layer_mutates_stack": False,
            "allowed_tool_kinds": [
                "promql_read",
                "logql_read",
                "self_awareness_query",
                "self_awareness_context",
                "self_awareness_spatial_graph",
                "rag_validate",
                "nervous_brief",
                "requirements_handoff",
                "resource_mode_gate",
            ],
        },
        "role": "monitored resident reasoning worker; candidate synthesis is not owner truth",
    }


def resident_worker_detail_complete(
    detail: dict[str, Any],
    *,
    config: SelfAwarenessResidentWorkerConfig,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    nested_get = self_awareness_contracts.nested_get
    if not isinstance(detail, dict):
        return False
    monitor_timer = str(nested_get(detail, ["monitor", "monitor_timer_active"]) or "")
    digest_timer = str(nested_get(detail, ["monitor", "digest_timer_active"]) or "")
    micro_timer = str(nested_get(detail, ["monitor", "micro_timer_active"]) or "")
    return (
        detail.get("ok") is True
        and detail.get("status") == "running"
        and nested_get(detail, ["serving", "owner"]) in {"abyss-stack", "abyss-machine"}
        and nested_get(detail, ["serving", "stack_owned_serving"]) is True
        and nested_get(detail, ["health", "ok"]) is True
        and nested_get(detail, ["health", "health_latency_ms"]) is not None
        and nested_get(detail, ["health", "model_id"]) is not None
        and nested_get(detail, ["monitor", "ok"]) is True
        and monitor_timer == "active"
        and digest_timer == "active"
        and micro_timer == "active"
        and nested_get(detail, ["resource_thermal", "package_temp_c"]) is not None
        and nested_get(detail, ["candidate_context", "digest_ok"]) is True
        and nested_get(detail, ["candidate_context", "micro_ok"]) is True
        and nested_get(detail, ["candidate_context", "candidates"]) is not None
        and nested_get(detail, ["candidate_context", "action_execution"]) is False
        and nested_get(detail, ["evals", "overall_score"]) is not None
        and nested_get(detail, ["policy", "model_execution_in_self_awareness_graph"]) is False
        and nested_get(detail, ["policy", "candidate_synthesis_only"]) is True
        and nested_get(detail, ["policy", "host_layer_mutates_stack"]) is False
        and nested_get(detail, ["policy", "abyss_machine_writes_stack"]) is False
        and nested_get(detail, ["policy", "candidate_output_is_owner_truth"]) is False
        and nested_get(detail, ["cognitive_contract", "schema"]) == f"{SCHEMA_PREFIX}_self_awareness_resident_cognitive_contract_v1"
        and nested_get(detail, ["cognitive_contract", "bounded_context_packet_required"]) is True
        and nested_get(detail, ["cognitive_contract", "read_only_tool_inventory_required"]) is True
        and nested_get(detail, ["cognitive_contract", "hypothesis_testing_required"]) is True
        and nested_get(detail, ["cognitive_contract", "contradiction_notes_required"]) is True
        and nested_get(detail, ["cognitive_contract", "resource_mode_gated_escalation_required"]) is True
        and nested_get(detail, ["cognitive_contract", "direct_model_generation_in_self_awareness"]) is False
        and nested_get(detail, ["cognitive_contract", "host_layer_mutates_stack"]) is False
    )
