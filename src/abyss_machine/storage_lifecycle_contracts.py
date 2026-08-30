from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


STATES = {"open", "sealed", "released"}
DECISIONS = {"KEEP", "DELETE", "ARCHIVE", "UNKNOWN"}
MUTATING_DECISIONS = {"DELETE", "ARCHIVE"}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8", errors="replace")).hexdigest()


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def canonical_path(value: str) -> str:
    text = str(value or "")
    return os.path.normpath(text) if text.startswith("/") else text


def workspace_id(*, owner: str, path: str, nonce: str) -> str:
    return "workspace-" + digest({"owner": owner, "path": canonical_path(path), "nonce": nonce})[:24]


def open_workspace(
    *,
    owner: str,
    path: str,
    nonce: str,
    lease_token_sha256: str,
    opened_at: str,
    lease_expires_at: str,
    unit: str | None,
    launcher_created: bool,
    callback_path: str,
) -> dict[str, Any]:
    path = canonical_path(path)
    errors: list[str] = []
    if not owner.strip():
        errors.append("owner_required")
    if not path or not Path(path).is_absolute():
        errors.append("absolute_workspace_path_required")
    if not nonce:
        errors.append("nonce_required")
    if len(lease_token_sha256) != 64:
        errors.append("lease_capability_digest_required")
    if parse_time(opened_at) is None or parse_time(lease_expires_at) is None:
        errors.append("valid_lease_times_required")
    return {
        "schema": "abyss_machine_storage_workspace_lifecycle_v1",
        "workspace_id": workspace_id(owner=owner, path=path, nonce=nonce),
        "owner": owner,
        "path": path,
        "state": "open",
        "opened_at": opened_at,
        "updated_at": opened_at,
        "unit": unit,
        "launcher_created": bool(launcher_created),
        "lease": {
            "token_sha256": lease_token_sha256,
            "expires_at": lease_expires_at,
            "generation": 1,
        },
        "callback_path": callback_path,
        "seal": None,
        "disposition": None,
        "valid": not errors,
        "errors": errors,
        "policy": {
            "managed_only": True,
            "absence_or_age_is_not_release": True,
            "storage_does_not_infer_owner_semantics": True,
        },
    }


def renew_lease(
    record: Mapping[str, Any],
    *,
    token: str,
    expires_at: str,
    updated_at: str,
) -> dict[str, Any]:
    result = dict(record)
    lease = dict(record.get("lease") if isinstance(record.get("lease"), Mapping) else {})
    errors: list[str] = []
    if record.get("state") != "open":
        errors.append("workspace_not_open")
    if hashlib.sha256(token.encode()).hexdigest() != lease.get("token_sha256"):
        errors.append("lease_capability_mismatch")
    if parse_time(expires_at) is None:
        errors.append("valid_expiry_required")
    if errors:
        return {"ok": False, "errors": errors, "record": result}
    lease["expires_at"] = expires_at
    lease["generation"] = int(lease.get("generation") or 0) + 1
    result["lease"] = lease
    result["updated_at"] = updated_at
    return {"ok": True, "errors": [], "record": result}


def seal_workspace(
    record: Mapping[str, Any],
    *,
    token: str,
    fingerprint: Mapping[str, Any],
    physical_bytes: int,
    sealed_at: str,
    preserved_refs: Sequence[str] = (),
) -> dict[str, Any]:
    result = dict(record)
    lease = record.get("lease") if isinstance(record.get("lease"), Mapping) else {}
    errors: list[str] = []
    if record.get("state") != "open":
        errors.append("workspace_not_open")
    if hashlib.sha256(token.encode()).hexdigest() != lease.get("token_sha256"):
        errors.append("lease_capability_mismatch")
    if fingerprint.get("complete") is not True or not fingerprint.get("digest"):
        errors.append("complete_fingerprint_required")
    if not isinstance(physical_bytes, int) or physical_bytes < 0:
        errors.append("physical_bytes_required")
    if errors:
        return {"ok": False, "errors": errors, "record": result}
    result["state"] = "sealed"
    result["updated_at"] = sealed_at
    result["seal"] = {
        "sealed_at": sealed_at,
        "fingerprint": dict(fingerprint),
        "physical_bytes": physical_bytes,
        "preserved_refs": [str(item) for item in preserved_refs if str(item)],
    }
    result["lease"] = None
    return {"ok": True, "errors": [], "record": result}


def recover_abandoned_workspace(
    record: Mapping[str, Any],
    *,
    fingerprint: Mapping[str, Any],
    physical_bytes: int,
    recovered_at: str,
) -> dict[str, Any]:
    result = dict(record)
    errors: list[str] = []
    expiry = parse_time((record.get("lease") or {}).get("expires_at")) if isinstance(record.get("lease"), Mapping) else None
    recovered = parse_time(recovered_at)
    if record.get("state") != "open":
        errors.append("workspace_not_open")
    if expiry is None or recovered is None or expiry > recovered:
        errors.append("lease_not_expired")
    if fingerprint.get("complete") is not True or not fingerprint.get("digest"):
        errors.append("complete_fingerprint_required")
    if not isinstance(physical_bytes, int) or physical_bytes < 0:
        errors.append("physical_bytes_required")
    if errors:
        return {"ok": False, "errors": errors, "record": result}
    result["state"] = "sealed"
    result["updated_at"] = recovered_at
    result["lease"] = None
    result["seal"] = {
        "sealed_at": recovered_at,
        "fingerprint": dict(fingerprint),
        "physical_bytes": physical_bytes,
        "preserved_refs": [],
        "recovery": "expired_lease_and_inactive_unit",
    }
    result["disposition"] = {
        "decision": "UNKNOWN",
        "plan": {},
        "valid": True,
        "errors": [],
        "released": False,
        "recovery": "owner_callback_not_confirmed",
    }
    return {"ok": True, "errors": [], "record": result}


def disposition_document(value: Mapping[str, Any]) -> dict[str, Any]:
    decision = str(value.get("decision") or "UNKNOWN").upper()
    plan = dict(value.get("plan") if isinstance(value.get("plan"), Mapping) else {})
    errors: list[str] = []
    if decision not in DECISIONS:
        errors.append("unsupported_owner_decision")
    if decision == "DELETE" and plan.get("kind") != "delete_workspace":
        errors.append("delete_workspace_plan_required")
    if decision == "ARCHIVE":
        if plan.get("kind") != "archive_workspace":
            errors.append("archive_workspace_plan_required")
        target = canonical_path(str(plan.get("target") or ""))
        if not target or not Path(target).is_absolute():
            errors.append("absolute_archive_target_required")
        plan["target"] = target
    return {
        "decision": decision if decision in DECISIONS else "UNKNOWN",
        "plan": plan,
        "owner_evidence_refs": [str(item) for item in value.get("owner_evidence_refs", []) if str(item)]
        if isinstance(value.get("owner_evidence_refs"), Sequence) and not isinstance(value.get("owner_evidence_refs"), (str, bytes))
        else [],
        "valid": not errors,
        "errors": errors,
    }


def release_workspace(
    record: Mapping[str, Any],
    *,
    disposition: Mapping[str, Any],
    released_at: str,
    grace_seconds: int,
) -> dict[str, Any]:
    result = dict(record)
    normalized = disposition_document(disposition)
    errors = list(normalized["errors"])
    if record.get("state") != "sealed":
        errors.append("workspace_not_sealed")
    decision = normalized["decision"]
    if decision not in MUTATING_DECISIONS:
        errors.append("owner_did_not_release_for_mutation")
    if record.get("launcher_created") is not True:
        errors.append("workspace_not_created_by_managed_launcher")
    released_time = parse_time(released_at)
    if released_time is None:
        errors.append("valid_release_time_required")
    if errors:
        result["disposition"] = {**normalized, "released": False}
        result["updated_at"] = released_at
        return {"ok": False, "errors": errors, "record": result}
    not_before = released_time + dt.timedelta(seconds=max(0, int(grace_seconds)))
    result["state"] = "released"
    result["updated_at"] = released_at
    result["disposition"] = {
        **normalized,
        "released": True,
        "released_at": released_at,
        "not_before": not_before.isoformat(),
        "seal_fingerprint_digest": (record.get("seal") or {}).get("fingerprint", {}).get("digest")
        if isinstance(record.get("seal"), Mapping)
        else None,
    }
    return {"ok": True, "errors": [], "record": result}


def execution_eligibility(record: Mapping[str, Any], *, now_time: dt.datetime) -> dict[str, Any]:
    disposition = record.get("disposition") if isinstance(record.get("disposition"), Mapping) else {}
    seal = record.get("seal") if isinstance(record.get("seal"), Mapping) else {}
    not_before = parse_time(disposition.get("not_before"))
    reasons = [
        code
        for code, failed in (
            ("workspace_not_released", record.get("state") != "released"),
            ("launcher_creation_not_proven", record.get("launcher_created") is not True),
            ("disposition_invalid", disposition.get("valid") is not True),
            ("unsupported_mutating_decision", disposition.get("decision") not in MUTATING_DECISIONS),
            ("seal_missing", not isinstance(seal.get("fingerprint"), Mapping)),
            ("grace_period_active", not_before is None or not_before > now_time.astimezone(dt.timezone.utc)),
        )
        if failed
    ]
    return {"eligible": not reasons, "reasons": reasons}
