from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
import hashlib
import json
from math import isfinite
from typing import Any


C18_SCHEMA_REF = "schemas/active-organ-host-capability-snapshot-reference.schema.json"
C19_SCHEMA_REF = "schemas/active-organ-host-resource-storage-plan-reference.schema.json"

C18_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "contract_id",
        "contract_name",
        "reference_id",
        "reference_version",
        "idempotency_key",
        "owner",
        "host_identity_digest",
        "snapshot_generation",
        "captured_at",
        "produced_at",
        "expires_at",
        "freshness_state",
        "capture_command_ref",
        "capability_refs",
        "source_refs",
        "policy_pin",
        "allowed_consumers",
        "validation_status",
        "privacy_class",
        "public_safe",
        "raw_host_data_included",
        "content_digest",
        "evidence_only",
        "semantic_authority",
        "effect_authority",
    }
)
C19_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "contract_id",
        "contract_name",
        "reference_id",
        "reference_version",
        "idempotency_key",
        "owner",
        "request",
        "capability_snapshot_ref",
        "resource_plan_ref",
        "storage_write_preflight_ref",
        "resource_plan_decision",
        "host_disposition",
        "softening_constraints",
        "blocked_reasons",
        "denied_reasons",
        "warnings",
        "source_refs",
        "resource_policy_pin",
        "storage_policy_pin",
        "rollback_ref",
        "produced_at",
        "expires_at",
        "plan_freshness",
        "validation_status",
        "content_digest",
        "launch_executed",
        "machine_owned_roots_only",
        "project_root_mutation",
        "stack_root_mutation",
        "memory_semantic_authority",
        "effect_authority",
        "owner_workload_effect",
    }
)
C18_EXPECTED_LITERALS = {
    "schema_version": "1.0.0",
    "contract_id": "C18",
    "contract_name": "HostCapabilitySnapshotReference",
    "owner": "abyss-machine",
    "public_safe": True,
    "raw_host_data_included": False,
    "evidence_only": True,
    "semantic_authority": "none",
    "effect_authority": "none",
}
C19_EXPECTED_LITERALS = {
    "schema_version": "1.0.0",
    "contract_id": "C19",
    "contract_name": "HostResourceStoragePlanReference",
    "owner": "abyss-machine",
    "launch_executed": False,
    "machine_owned_roots_only": True,
    "project_root_mutation": "forbidden",
    "stack_root_mutation": "forbidden",
    "memory_semantic_authority": "none",
    "effect_authority": "host_admission_only",
    "owner_workload_effect": "start_defer_soften_or_deny_only",
}


class ActiveOrganHostContractError(ValueError):
    """Raised when an active-organ host reference would widen host authority."""


def _aware_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _portable_ref(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    lowered = value.lower()
    return not (
        value.startswith(("/", "~"))
        or "/home/" in lowered
        or "/srv/" in lowered
        or ".aoa/sessions" in lowered
        or "transcript" in lowered
    )


def _iter_mappings(value: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _iter_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_mappings(child)


def _ref_key(value: object) -> tuple[object, ...] | None:
    if not isinstance(value, Mapping):
        return None
    fields = ("owner_repo", "artifact_ref", "artifact_version", "artifact_digest")
    if not all(field in value for field in fields):
        return None
    return tuple(value[field] for field in fields)


def _unique_ref_issues(values: object, *, label: str) -> list[str]:
    if not isinstance(values, list):
        return []
    keys = [key for value in values if (key := _ref_key(value)) is not None]
    return [f"{label} must contain unique refs"] if len(keys) != len(set(keys)) else []


def _top_level_issues(
    payload: Mapping[str, Any],
    *,
    required: frozenset[str],
    expected_literals: Mapping[str, object],
) -> list[str]:
    issues: list[str] = []
    actual = set(payload)
    missing = sorted(required - actual)
    unknown = sorted(actual - required)
    if missing:
        issues.append(f"missing required top-level fields: {', '.join(missing)}")
    if unknown:
        issues.append(f"unknown top-level fields: {', '.join(unknown)}")
    for field, expected in expected_literals.items():
        if field in payload and payload[field] != expected:
            issues.append(f"{field} must remain {expected!r}")
    return issues


def _common_portability_issues(payload: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    for mapping in _iter_mappings(payload):
        artifact_ref = mapping.get("artifact_ref")
        if artifact_ref is not None and not _portable_ref(artifact_ref):
            issues.append(f"non-portable artifact_ref: {artifact_ref!r}")
        decision_ref = mapping.get("decision_ref")
        if decision_ref is not None and not _portable_ref(decision_ref):
            issues.append(f"non-portable decision_ref: {decision_ref!r}")
    return issues


def _validate_time_order(
    payload: Mapping[str, Any],
    fields: Sequence[str],
) -> list[str]:
    issues: list[str] = []
    parsed: list[tuple[str, datetime]] = []
    for field in fields:
        timestamp = _aware_datetime(payload.get(field))
        if timestamp is None:
            issues.append(f"{field} must be a timezone-aware date-time")
        else:
            parsed.append((field, timestamp))
    for (left_name, left), (right_name, right) in zip(parsed, parsed[1:]):
        if right < left or (right == left and right_name == "expires_at"):
            issues.append(f"{right_name} must follow {left_name}")
    return issues


def validate_host_capability_snapshot_reference(
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate C18 semantics without reading the referenced live host facts."""

    issues = _top_level_issues(
        payload,
        required=C18_REQUIRED_FIELDS,
        expected_literals=C18_EXPECTED_LITERALS,
    )
    issues.extend(_common_portability_issues(payload))
    issues.extend(
        _validate_time_order(payload, ("captured_at", "produced_at", "expires_at"))
    )

    capture_ref = payload.get("capture_command_ref")
    if (
        isinstance(capture_ref, Mapping)
        and capture_ref.get("owner_repo") != "abyss-machine"
    ):
        issues.append("capture_command_ref must be owned by abyss-machine")

    capabilities = payload.get("capability_refs")
    capability_items = capabilities if isinstance(capabilities, list) else []
    classes: list[object] = []
    capability_keys: set[tuple[object, ...]] = set()
    all_current = True
    captured_at = _aware_datetime(payload.get("captured_at"))
    for index, capability in enumerate(capability_items):
        if not isinstance(capability, Mapping):
            continue
        classes.append(capability.get("capability_class"))
        artifact = capability.get("artifact")
        key = _ref_key(artifact)
        if key is not None:
            capability_keys.add(key)
        if (
            not isinstance(artifact, Mapping)
            or artifact.get("owner_repo") != "abyss-machine"
        ):
            issues.append(
                f"capability_refs[{index}] artifact must be owned by abyss-machine"
            )
        observed_at = _aware_datetime(capability.get("observed_at"))
        if observed_at is None:
            issues.append(
                f"capability_refs[{index}].observed_at must be timezone-aware"
            )
        elif captured_at is not None and observed_at > captured_at:
            issues.append(
                f"capability_refs[{index}].observed_at cannot follow captured_at"
            )
        if capability.get("freshness_state") != "current":
            all_current = False
    if len(classes) != len(set(classes)):
        issues.append("capability classes must be unique within one snapshot")

    if payload.get("freshness_state") == "current" and not all_current:
        issues.append("current C18 requires every capability ref to be current")
    if (
        payload.get("freshness_state") == "current"
        and payload.get("validation_status") != "valid"
    ):
        issues.append("current C18 requires valid validation_status")

    source_refs = payload.get("source_refs")
    issues.extend(_unique_ref_issues(source_refs, label="source_refs"))
    source_keys = (
        {key for value in source_refs if (key := _ref_key(value)) is not None}
        if isinstance(source_refs, list)
        else set()
    )
    capture_key = _ref_key(capture_ref)
    required_keys = capability_keys | (
        {capture_key} if capture_key is not None else set()
    )
    if not required_keys.issubset(source_keys):
        issues.append("source_refs must retain capture and capability artifact refs")

    return issues


def validate_host_resource_storage_plan_reference(
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate C19 as admission reference only, never as launch execution."""

    issues = _top_level_issues(
        payload,
        required=C19_REQUIRED_FIELDS,
        expected_literals=C19_EXPECTED_LITERALS,
    )
    issues.extend(_common_portability_issues(payload))
    issues.extend(_validate_time_order(payload, ("produced_at", "expires_at")))

    request = payload.get("request")
    request_data = request if isinstance(request, Mapping) else {}
    write_required = request_data.get("storage_write_required") is True
    target_ref = request_data.get("target_ref")
    preflight_ref = payload.get("storage_write_preflight_ref")
    requested_bytes = request_data.get("requested_bytes")
    target_class = request_data.get("target_class")

    if write_required:
        if (
            target_class == "none"
            or target_ref is None
            or preflight_ref is None
            or not isinstance(requested_bytes, int)
            or isinstance(requested_bytes, bool)
            or requested_bytes <= 0
        ):
            issues.append(
                "storage write requires host target, positive bytes, and preflight ref"
            )
    elif (
        target_class != "none"
        or target_ref is not None
        or preflight_ref is not None
        or requested_bytes is not None
    ):
        issues.append("no-write request must not carry storage target or preflight")

    if (
        isinstance(target_ref, Mapping)
        and target_ref.get("owner_repo") != "abyss-machine"
    ):
        issues.append("storage target ref must be owned by abyss-machine")

    memory_demand = request_data.get("memory_demand_mib")
    if memory_demand is not None and (
        not isinstance(memory_demand, (int, float))
        or isinstance(memory_demand, bool)
        or not isfinite(float(memory_demand))
        or float(memory_demand) < 0
    ):
        issues.append("memory_demand_mib must be finite and non-negative")

    disposition = payload.get("host_disposition")
    plan_decision = payload.get("resource_plan_decision")
    blocked = payload.get("blocked_reasons")
    blocked_items = blocked if isinstance(blocked, list) else []
    denied = payload.get("denied_reasons")
    denied_items = denied if isinstance(denied, list) else []
    constraints = payload.get("softening_constraints")
    constraint_items = constraints if isinstance(constraints, list) else []
    current_valid = (
        payload.get("plan_freshness") == "current"
        and payload.get("validation_status") == "valid"
    )

    if disposition == "start" and (
        plan_decision != "allow"
        or not current_valid
        or blocked_items
        or denied_items
        or constraint_items
    ):
        issues.append(
            "start requires current valid allow with no block, denial, or softening"
        )
    if disposition == "soften" and (
        plan_decision != "allow"
        or not current_valid
        or not constraint_items
        or blocked_items
        or denied_items
    ):
        issues.append(
            "soften requires current valid allow, explicit constraints, and no denial"
        )
    if disposition == "defer" and (
        plan_decision != "force_required" and not blocked_items
    ):
        issues.append("defer requires force_required or explicit blocked reasons")
    if disposition == "defer" and denied_items:
        issues.append("denied reasons require deny rather than defer")
    if disposition == "deny" and plan_decision != "deny" and not denied_items:
        issues.append("deny requires resource-plan denial or explicit denied reasons")
    if plan_decision == "deny" and disposition != "deny":
        issues.append("resource-plan deny must remain host disposition deny")
    if plan_decision == "force_required" and disposition != "defer":
        issues.append("force_required must remain deferred pending a new plan")

    for label in ("blocked_reasons", "denied_reasons", "warnings"):
        values = payload.get(label)
        if isinstance(values, list) and len(values) != len(set(values)):
            issues.append(f"{label} must be unique")

    core_refs = [
        payload.get("capability_snapshot_ref"),
        payload.get("resource_plan_ref"),
        payload.get("storage_write_preflight_ref"),
        payload.get("rollback_ref"),
    ]
    for label, ref in zip(
        (
            "capability_snapshot_ref",
            "resource_plan_ref",
            "storage_write_preflight_ref",
            "rollback_ref",
        ),
        core_refs,
    ):
        if ref is not None and (
            not isinstance(ref, Mapping) or ref.get("owner_repo") != "abyss-machine"
        ):
            issues.append(f"{label} must be owned by abyss-machine")

    source_refs = payload.get("source_refs")
    issues.extend(_unique_ref_issues(source_refs, label="source_refs"))
    source_keys = (
        {key for value in source_refs if (key := _ref_key(value)) is not None}
        if isinstance(source_refs, list)
        else set()
    )
    required_keys = {key for ref in core_refs if (key := _ref_key(ref)) is not None}
    if not required_keys.issubset(source_keys):
        issues.append("source_refs must retain every host plan input and rollback ref")

    return issues


def build_host_capability_snapshot_reference(
    **fields: Any,
) -> dict[str, Any]:
    payload = {
        **fields,
        "schema_version": "1.0.0",
        "contract_id": "C18",
        "contract_name": "HostCapabilitySnapshotReference",
        "owner": "abyss-machine",
        "public_safe": True,
        "raw_host_data_included": False,
        "evidence_only": True,
        "semantic_authority": "none",
        "effect_authority": "none",
    }
    issues = validate_host_capability_snapshot_reference(payload)
    if issues:
        raise ActiveOrganHostContractError("; ".join(issues))
    return payload


def build_host_resource_storage_plan_reference(
    **fields: Any,
) -> dict[str, Any]:
    payload = {
        **fields,
        "schema_version": "1.0.0",
        "contract_id": "C19",
        "contract_name": "HostResourceStoragePlanReference",
        "owner": "abyss-machine",
        "launch_executed": False,
        "machine_owned_roots_only": True,
        "project_root_mutation": "forbidden",
        "stack_root_mutation": "forbidden",
        "memory_semantic_authority": "none",
        "effect_authority": "host_admission_only",
        "owner_workload_effect": "start_defer_soften_or_deny_only",
    }
    issues = validate_host_resource_storage_plan_reference(payload)
    if issues:
        raise ActiveOrganHostContractError("; ".join(issues))
    return payload


def admit_shadow_workload(
    capability_snapshot: Mapping[str, Any],
    resource_plan: Mapping[str, Any],
    *,
    workload_id: str,
    consumer_id: str,
    admitted_at: datetime,
) -> dict[str, Any]:
    """Apply exact C18/C19 host admission without launching or authoring meaning."""

    if admitted_at.tzinfo is None:
        raise ActiveOrganHostContractError("admitted_at must be timezone-aware")
    capability_issues = validate_host_capability_snapshot_reference(
        capability_snapshot
    )
    resource_issues = validate_host_resource_storage_plan_reference(resource_plan)
    if capability_issues or resource_issues:
        raise ActiveOrganHostContractError(
            "; ".join((*capability_issues, *resource_issues))
        )
    request = resource_plan["request"]
    if request["workload_id"] != workload_id:
        raise ActiveOrganHostContractError(
            "workload_id must match the exact C19 request"
        )

    c18_expiry = _aware_datetime(capability_snapshot["expires_at"])
    c19_expiry = _aware_datetime(resource_plan["expires_at"])
    if c18_expiry is None or c19_expiry is None:
        raise ActiveOrganHostContractError("C18/C19 expiry must be timezone-aware")
    expires_at = min(c18_expiry, c19_expiry)
    stale = (
        admitted_at >= expires_at
        or capability_snapshot["freshness_state"] != "current"
        or resource_plan["plan_freshness"] != "current"
    )
    allowed_consumers = capability_snapshot.get("allowed_consumers", [])
    consumer_denied = consumer_id not in allowed_consumers
    disposition = resource_plan["host_disposition"]
    constraints = list(resource_plan["softening_constraints"])
    reason_codes: list[str] = []
    if stale:
        disposition = "deny"
        constraints = []
        reason_codes.append("stale-host-evidence")
    if consumer_denied:
        disposition = "deny"
        constraints = []
        reason_codes.append("consumer-not-admitted-by-c18")
    if not reason_codes:
        if disposition == "deny":
            reason_codes.extend(resource_plan["denied_reasons"])
        elif disposition == "defer":
            reason_codes.extend(resource_plan["blocked_reasons"])
        elif disposition == "soften":
            reason_codes.append("host-softening-required")
        else:
            reason_codes.append("host-start-admitted")

    payload: dict[str, Any] = {
        "schema_version": "abyss_machine_shadow_workload_admission_v0",
        "owner": "abyss-machine",
        "workload_id": workload_id,
        "consumer_id": consumer_id,
        "capability_snapshot_ref": capability_snapshot["reference_id"],
        "capability_snapshot_digest": capability_snapshot["content_digest"],
        "resource_plan_ref": resource_plan["reference_id"],
        "resource_plan_digest": resource_plan["content_digest"],
        "host_disposition": disposition,
        "softening_constraints": constraints,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "admitted_at": admitted_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "launch_executed": False,
        "project_root_mutation": "forbidden",
        "stack_root_mutation": "forbidden",
        "memory_semantic_authority": "none",
        "effect_authority": "host_admission_only",
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload["admission_digest"] = (
        f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    )
    return payload


def admit_canary_workload(
    capability_snapshot: Mapping[str, Any],
    resource_plan: Mapping[str, Any],
    *,
    workload_id: str,
    runtime_consumer_id: str,
    memory_consumer_id: str,
    admitted_at: datetime,
) -> dict[str, Any]:
    """Admit canary resource use without granting delivery or memory meaning."""

    if memory_consumer_id != "codex_owner_orientation_canary_v0":
        raise ActiveOrganHostContractError(
            "host canary admission is limited to the exact memory consumer"
        )
    payload = admit_shadow_workload(
        capability_snapshot,
        resource_plan,
        workload_id=workload_id,
        consumer_id=runtime_consumer_id,
        admitted_at=admitted_at,
    )
    payload["schema_version"] = "abyss_machine_canary_workload_admission_v0"
    payload["memory_consumer_id"] = memory_consumer_id
    payload["delivery_semantic_authority"] = "none"
    payload["canary_effect_authority"] = "none"
    payload["admission_digest"] = "sha256:" + ("0" * 64)
    encoded = json.dumps(
        {
            key: value
            for key, value in payload.items()
            if key != "admission_digest"
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload["admission_digest"] = (
        f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    )
    return payload
