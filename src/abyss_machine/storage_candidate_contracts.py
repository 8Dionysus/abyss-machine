from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


VERDICTS = {
    "keep_current",
    "blocked_active",
    "blocked_owner_reference",
    "blocked_unique_data",
    "blocked_unknown",
    "archive_pending",
    "archive_ready",
    "delete_ready_rebuildable",
    "delete_ready_superseded",
}

READY_VERDICTS = {
    "archive_ready",
    "delete_ready_rebuildable",
    "delete_ready_superseded",
}

DELETE_READY_VERDICTS = {
    "delete_ready_rebuildable",
    "delete_ready_superseded",
}

DEFAULT_POLICY: dict[str, Any] = {
    "history_limit": 32,
    "minimum_reclaimable_bytes": 1,
    "deep_max_age_seconds": 172800,
    "light_max_age_seconds": 7200,
    "default": {"minimum_observations": 3, "quiet_seconds": 72 * 3600},
    "by_kind": {
        "generated_tmp": {"minimum_observations": 3, "quiet_seconds": 24 * 3600},
        "failed_runtime": {"minimum_observations": 3, "quiet_seconds": 24 * 3600},
        "runtime": {"minimum_observations": 3, "quiet_seconds": 72 * 3600},
        "git_worktree": {"minimum_observations": 3, "quiet_seconds": 24 * 3600},
        "openvino_cache": {"minimum_observations": 3, "quiet_seconds": 72 * 3600},
        "huggingface_model": {"minimum_observations": 3, "quiet_seconds": 72 * 3600},
        "model_cache": {"minimum_observations": 3, "quiet_seconds": 7 * 24 * 3600},
        "podman_image": {"minimum_observations": 3, "quiet_seconds": 72 * 3600},
        "podman_volume": {"minimum_observations": 3, "quiet_seconds": 7 * 24 * 3600},
        "aoa_owner_debris": {"minimum_observations": 2, "quiet_seconds": 3600},
    },
}

EXECUTORS_BY_KIND = {
    "generated_tmp": "age_bounded_tmp_cleanup",
    "failed_runtime": "runtime_retire_preserve_receipts",
    "runtime": "runtime_retire",
    "git_worktree": "git_worktree_remove",
    "openvino_cache": "owner_cache_cleanup",
    "huggingface_model": "owner_cache_cleanup",
    "model_cache": "owner_cache_cleanup",
    "podman_image": "podman_image_remove",
    "podman_volume": "podman_volume_remove",
    "aoa_owner_debris": "aoa_maintenance_cleanup",
    "vault_archive": "vault_verified_offload",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, *, length: int = 32) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8", errors="replace")).hexdigest()[:length]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def canonical_candidate_path(path: str) -> str:
    """Return a stable lexical path without resolving symlinks or live targets."""
    text = str(path or "")
    return os.path.normpath(text) if text.startswith("/") else text


def _parse_time(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            parsed = dt.datetime.fromtimestamp(float(value), dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value.strip():
        try:
            parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def parse_time(value: Any) -> dt.datetime | None:
    """Public timestamp parser shared by read-only candidate adapters."""
    return _parse_time(value)


def _policy_for_kind(policy: Mapping[str, Any], kind: str) -> dict[str, int]:
    default = _mapping(policy.get("default"))
    by_kind = _mapping(policy.get("by_kind"))
    selected = _mapping(by_kind.get(kind))
    return {
        "minimum_observations": max(1, _safe_int(selected.get("minimum_observations"), _safe_int(default.get("minimum_observations"), 3))),
        "quiet_seconds": max(0, _safe_int(selected.get("quiet_seconds"), _safe_int(default.get("quiet_seconds"), 72 * 3600))),
    }


def merged_policy(configured: Mapping[str, Any] | None = None) -> dict[str, Any]:
    configured = _mapping(configured)
    result = json.loads(json.dumps(DEFAULT_POLICY))
    for key in (
        "history_limit",
        "minimum_reclaimable_bytes",
        "deep_max_age_seconds",
        "light_max_age_seconds",
    ):
        if key in configured:
            result[key] = configured[key]
    if isinstance(configured.get("default"), Mapping):
        result["default"].update(configured["default"])
    if isinstance(configured.get("by_kind"), Mapping):
        for kind, values in configured["by_kind"].items():
            if isinstance(values, Mapping):
                result["by_kind"].setdefault(str(kind), {}).update(values)
    return result


def stable_candidate_id(*, owner: str, kind: str, path: str, source_id: str = "") -> str:
    identity = {
        "owner": owner.strip() or "unknown",
        "kind": kind.strip() or "unknown",
        "path": canonical_candidate_path(path),
        "source_id": source_id.strip(),
    }
    return "reclaim-" + _digest(identity, length=24)


def snapshot_id(records: Sequence[Mapping[str, Any]]) -> str:
    identity = [
        {
            "candidate_id": item.get("candidate_id"),
            "fingerprint": _mapping(item.get("fingerprint")).get("digest"),
            "verdict": item.get("verdict"),
        }
        for item in sorted(records, key=lambda row: str(row.get("candidate_id") or ""))
    ]
    return "reclaim-snapshot-" + _digest(identity, length=24)


def freshness_status(
    *,
    generated_at: Any,
    last_deep_at: Any,
    now_time: dt.datetime | None = None,
    max_age_seconds: int = 172800,
) -> dict[str, Any]:
    """Classify deep evidence freshness without treating missing data as fresh."""
    now_time = now_time or dt.datetime.now(dt.timezone.utc)
    if now_time.tzinfo is None:
        now_time = now_time.replace(tzinfo=dt.timezone.utc)
    parsed = _parse_time(last_deep_at)
    if parsed is None:
        return {
            "status": "unknown",
            "last_deep_at": last_deep_at,
            "generated_at": generated_at,
            "age_seconds": None,
            "max_age_seconds": max(0, int(max_age_seconds)),
            "reason": "deep_snapshot_missing_or_timestamp_invalid",
        }
    age = max(0, int((now_time.astimezone(dt.timezone.utc) - parsed).total_seconds()))
    limit = max(0, int(max_age_seconds))
    return {
        "status": "fresh" if age <= limit else "stale",
        "last_deep_at": parsed.isoformat(),
        "generated_at": generated_at,
        "age_seconds": age,
        "max_age_seconds": limit,
        "reason": "within_deep_refresh_window" if age <= limit else "deep_snapshot_older_than_policy_window",
    }


def coverage_summary(
    records: Sequence[Mapping[str, Any]],
    *,
    error_limit: int | None = 200,
) -> dict[str, Any]:
    """Summarize evidence coverage while keeping runtime failures separate from pressure."""
    rows = [dict(item) for item in records if isinstance(item, Mapping)]
    adapters = sorted({str(item.get("source_adapter") or "unknown") for item in rows})
    required_evidence = ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
    runtime_errors: list[dict[str, Any]] = []
    pressure_findings: list[dict[str, Any]] = []
    physical_measured = 0
    fingerprint_complete = 0
    evidence_complete = 0
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        physical = row.get("physical_bytes")
        if isinstance(physical, int) and physical >= 0:
            physical_measured += 1
            if physical > 0:
                pressure_findings.append({
                    "candidate_id": candidate_id,
                    "path": row.get("path"),
                    "physical_bytes": physical,
                    "reclaimable_bytes": row.get("reclaimable_bytes"),
                    "source": "candidate_physical_measurement",
                })
        fingerprint = _mapping(row.get("fingerprint"))
        if fingerprint.get("complete") is True and fingerprint.get("digest"):
            fingerprint_complete += 1
        evidence = _mapping(row.get("evidence"))
        complete = True
        for key in required_evidence:
            value = _mapping(evidence.get(key))
            if key not in evidence or value.get("checked") is False:
                complete = False
            if value.get("error") or value.get("errors"):
                runtime_errors.append({
                    "candidate_id": candidate_id,
                    "path": row.get("path"),
                    "surface": key,
                    "error": value.get("error") or value.get("errors"),
                })
        physical_evidence = _mapping(evidence.get("physical_size"))
        if physical_evidence.get("error") or physical_evidence.get("ok") is False:
            runtime_errors.append({
                "candidate_id": candidate_id,
                "path": row.get("path"),
                "surface": "physical_size",
                "error": physical_evidence.get("error") or "physical measurement unavailable",
            })
        if complete:
            evidence_complete += 1
    bounded_errors = runtime_errors if error_limit is None else runtime_errors[: max(0, int(error_limit))]
    return {
        "discovered": len(rows),
        "observed": len(rows),
        "adapters": adapters,
        "adapter_count": len(adapters),
        "physical_measured": physical_measured,
        "physical_unknown": max(0, len(rows) - physical_measured),
        "fingerprint_complete": fingerprint_complete,
        "fingerprint_incomplete": max(0, len(rows) - fingerprint_complete),
        "evidence_complete": evidence_complete,
        "evidence_incomplete": max(0, len(rows) - evidence_complete),
        "runtime_errors": bounded_errors,
        "pressure_findings": pressure_findings[:200],
        "runtime_error_count": len(runtime_errors),
        "pressure_finding_count": len(pressure_findings),
    }


def _blocker(code: str, source: str, detail: Any = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "source": source}
    if detail not in (None, "", [], {}):
        item["detail"] = detail
    return item


def _active_reference_blockers(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    evidence = _mapping(observation.get("evidence"))
    for key, code in (
        ("process_refs", "active_process_reference"),
        ("mount_refs", "active_mount_reference"),
        ("service_refs", "active_service_reference"),
        ("container_refs", "active_container_reference"),
        ("runtime_refs", "active_runtime_registry_reference"),
    ):
        value = _mapping(evidence.get(key))
        if value.get("active") is True:
            blockers.append(_blocker(code, key, value.get("refs") or value.get("units") or value.get("containers") or value.get("matches")))
    config_refs = _mapping(evidence.get("config_refs"))
    if config_refs.get("active") is True or _safe_int(config_refs.get("strong_live_hit_count")) > 0:
        hits = _list_of_mappings(config_refs.get("hits"))
        live_hits = [item for item in hits if item.get("active_evidence") is True]
        detail: Any = live_hits
        if not detail:
            detail = {"strong_live_hit_count": _safe_int(config_refs.get("strong_live_hit_count")), "live_hits_truncated_from_detail": bool(hits)}
        blockers.append(_blocker("active_config_reference", "config_refs", detail))
    claims = _list_of_mappings(evidence.get("active_claims"))
    if claims:
        blockers.append(_blocker("active_session_or_change_claim", "claims", claims))
    owner_verdict = _mapping(evidence.get("owner_verdict"))
    if owner_verdict.get("active_writer") is True or str(owner_verdict.get("status") or "").startswith("deferred_active"):
        blockers.append(_blocker("owner_reports_active_writer", "owner_verdict", owner_verdict.get("status")))
    return blockers


def _retention_until_value(observation: Mapping[str, Any]) -> Any:
    value = observation.get("retention_until")
    if value is not None:
        return value
    manifest = _mapping(_mapping(observation.get("evidence")).get("manifest"))
    return manifest.get("retention_until") if "retention_until" in manifest else None


def _parse_retention_until(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def _retention_blockers(observation: Mapping[str, Any], *, now_time: dt.datetime) -> list[dict[str, Any]]:
    value = _retention_until_value(observation)
    if value is None:
        return []
    deadline = _parse_retention_until(value)
    if deadline is None:
        return [_blocker("retention_until_invalid", "retention_until", value)]
    if deadline > now_time.astimezone(dt.timezone.utc):
        return [_blocker("retention_until_active", "retention_until", deadline.isoformat())]
    return []


def _owner_blockers(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    owner = str(observation.get("owner") or "unknown")
    evidence = _mapping(observation.get("evidence"))
    protection = _mapping(evidence.get("protection"))
    owner_verdict = _mapping(evidence.get("owner_verdict"))
    owner_authoritative = owner_verdict.get("authoritative") is True
    blockers: list[dict[str, Any]] = []
    if owner in {"", "unknown", "unknown_srv_owner"}:
        blockers.append(_blocker("owner_unknown", "owner"))
    decision = str(protection.get("decision") or "unknown")
    if decision != "allow_candidate" and not owner_authoritative:
        blockers.append(_blocker("path_not_owner_allowlisted", "protection", protection))
    if owner_verdict and owner_verdict.get("safe_to_remove") is False:
        blockers.append(_blocker("owner_verdict_blocks_removal", "owner_verdict", owner_verdict.get("status") or owner_verdict.get("reason")))
    return blockers


def _evidence_completeness_blockers(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    fingerprint = _mapping(observation.get("fingerprint"))
    physical_bytes = observation.get("physical_bytes")
    reclaimable_bytes = observation.get("reclaimable_bytes")
    executor = _mapping(observation.get("executor"))
    evidence = _mapping(observation.get("evidence"))
    if not fingerprint.get("digest") or fingerprint.get("complete") is not True:
        blockers.append(_blocker("filesystem_fingerprint_incomplete", "fingerprint", fingerprint.get("errors") or fingerprint.get("reason")))
    if not isinstance(physical_bytes, int) or physical_bytes < 0:
        blockers.append(_blocker("physical_size_unknown", "physical_size"))
    if not isinstance(reclaimable_bytes, int) or reclaimable_bytes < 0:
        blockers.append(_blocker("unique_reclaimable_size_unknown", "reclaimable_size"))
    if executor.get("owner_specific") is not True or not executor.get("type"):
        blockers.append(_blocker("owner_specific_executor_unknown", "executor", executor))
    required_evidence = ("process_refs", "mount_refs", "service_refs", "container_refs", "config_refs", "runtime_refs")
    for key in required_evidence:
        if key not in evidence:
            blockers.append(_blocker(f"{key}_not_checked", key))
        elif _mapping(evidence.get(key)).get("checked") is False:
            blockers.append(_blocker(f"{key}_not_checked", key, _mapping(evidence.get(key)).get("errors")))
    if "active_claims" not in evidence:
        blockers.append(_blocker("session_claims_not_checked", "claims"))
    return blockers


def _unique_data_state(observation: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    unique = _mapping(_mapping(observation.get("evidence")).get("unique_data"))
    status = str(unique.get("status") or "unknown")
    reasons = unique.get("reasons") or unique.get("evidence_refs") or unique.get("detail")
    if status == "clear":
        return status, []
    if status == "present":
        return status, [_blocker("unique_data_present", "unique_data", reasons)]
    return status, [_blocker("unique_data_not_proven_clear", "unique_data", reasons)]


def _archive_state(observation: Mapping[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    evidence = _mapping(observation.get("evidence"))
    backup = _mapping(evidence.get("backup"))
    restore = _mapping(evidence.get("restore"))
    blockers: list[dict[str, Any]] = []
    if backup.get("fresh") is not True:
        blockers.append(_blocker("backup_lane_not_fresh", "backup", backup.get("status") or backup.get("finished_at")))
    if backup.get("digest_match") is not True:
        blockers.append(_blocker("archive_digest_not_verified", "backup", backup.get("digest")))
    if restore.get("verified") is not True or not restore.get("command"):
        blockers.append(_blocker("restore_route_not_verified", "restore", restore.get("status")))
    return not blockers, blockers


def _recovery_state(observation: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    evidence = _mapping(observation.get("evidence"))
    replacement = _mapping(evidence.get("replacement"))
    recovery = _mapping(evidence.get("recovery"))
    owner_verdict = _mapping(evidence.get("owner_verdict"))
    if replacement.get("verified") is True:
        return "delete_ready_superseded", []
    if owner_verdict.get("authoritative") is True and owner_verdict.get("safe_to_remove") is True and owner_verdict.get("preservation_verified") is True:
        return "delete_ready_superseded", []
    if recovery.get("verified") is True and recovery.get("command"):
        return "delete_ready_rebuildable", []
    return "blocked_unknown", [_blocker("recovery_or_replacement_not_verified", "recovery", recovery or replacement)]


def _base_provisional_classification(observation: Mapping[str, Any]) -> dict[str, Any]:
    if observation.get("exists") is not True:
        return {
            "verdict": "blocked_unknown",
            "blockers": [_blocker("candidate_path_missing", "filesystem")],
            "reasons": ["candidate no longer exists at observation time"],
        }

    active = _active_reference_blockers(observation)
    if active:
        return {
            "verdict": "keep_current",
            "blockers": active,
            "reasons": ["current runtime, session, service, container, mount, or configuration evidence references the object"],
        }

    owner_blockers = _owner_blockers(observation)
    if owner_blockers:
        verdict = "blocked_owner_reference"
        if any(item.get("code") == "owner_reports_active_writer" for item in owner_blockers):
            verdict = "blocked_active"
        return {
            "verdict": verdict,
            "blockers": owner_blockers,
            "reasons": ["the owning route has not authorized this exact object as a cleanup candidate"],
        }

    unique_status, unique_blockers = _unique_data_state(observation)
    if unique_status == "present":
        archive_ok, archive_blockers = _archive_state(observation)
        if archive_ok:
            return {
                "verdict": "archive_ready",
                "blockers": [],
                "reasons": ["unique inactive data has fresh digest-matched archive and verified restore evidence"],
            }
        archivable = _mapping(_mapping(observation.get("evidence")).get("unique_data")).get("archivable") is True
        return {
            "verdict": "archive_pending" if archivable else "blocked_unique_data",
            "blockers": unique_blockers + archive_blockers,
            "reasons": ["unique data must be preserved before local cleanup"],
        }
    if unique_status != "clear":
        return {
            "verdict": "blocked_unknown",
            "blockers": unique_blockers,
            "reasons": ["absence of unique data has not been proven"],
        }

    completeness = _evidence_completeness_blockers(observation)
    if completeness:
        return {
            "verdict": "blocked_unknown",
            "blockers": completeness,
            "reasons": ["one or more mandatory evidence gates were not checked completely"],
        }

    recovery_verdict, recovery_blockers = _recovery_state(observation)
    if recovery_blockers:
        return {
            "verdict": "blocked_unknown",
            "blockers": recovery_blockers,
            "reasons": ["deletion consequence is not yet recoverable or replaced"],
        }
    return {
        "verdict": recovery_verdict,
        "blockers": [],
        "reasons": ["all current dependency, uniqueness, recoverability, ownership, executor, and measurement gates are clear"],
    }


def provisional_classification(
    observation: Mapping[str, Any],
    *,
    now_time: dt.datetime | None = None,
) -> dict[str, Any]:
    now_time = now_time or dt.datetime.now(dt.timezone.utc)
    if now_time.tzinfo is None:
        now_time = now_time.replace(tzinfo=dt.timezone.utc)
    result = _base_provisional_classification(observation)
    retention_blockers = _retention_blockers(observation, now_time=now_time)
    if retention_blockers and result.get("verdict") in READY_VERDICTS:
        result = dict(result)
        result["verdict"] = "archive_pending" if result.get("verdict") == "archive_ready" else "blocked_unknown"
        result["blockers"] = _list_of_mappings(result.get("blockers")) + retention_blockers
        result["reasons"] = list(result.get("reasons") or []) + [
            "retention_until is malformed or has not expired"
        ]
    return result


def observation_history_entry(observation: Mapping[str, Any], provisional: Mapping[str, Any]) -> dict[str, Any]:
    fingerprint = _mapping(observation.get("fingerprint"))
    return {
        "observed_at": observation.get("observed_at"),
        "fingerprint_digest": fingerprint.get("digest"),
        "fingerprint_complete": fingerprint.get("complete") is True,
        "physical_bytes": observation.get("physical_bytes"),
        "reclaimable_bytes": observation.get("reclaimable_bytes"),
        "provisional_verdict": provisional.get("verdict"),
        "retention_until": _retention_until_value(observation),
    }


def _append_history(previous: Sequence[Mapping[str, Any]], current: Mapping[str, Any], limit: int) -> list[dict[str, Any]]:
    history = [dict(item) for item in previous if isinstance(item, Mapping)]
    if history and _stable_json(history[-1]) == _stable_json(current):
        return history[-limit:]
    history.append(dict(current))
    return history[-limit:]


def _stability(
    observation: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    provisional_verdict: str,
    policy: Mapping[str, Any],
    *,
    now_time: dt.datetime,
) -> dict[str, Any]:
    selected = _policy_for_kind(policy, str(observation.get("kind") or "unknown"))
    fingerprint_digest = _mapping(observation.get("fingerprint")).get("digest")
    consecutive: list[Mapping[str, Any]] = []
    for item in reversed(history):
        if item.get("fingerprint_digest") != fingerprint_digest or item.get("provisional_verdict") != provisional_verdict:
            break
        consecutive.append(item)
    latest_mtime = _parse_time(observation.get("latest_mtime"))
    quiet_seconds = None
    if latest_mtime is not None:
        quiet_seconds = max(0, int((now_time - latest_mtime).total_seconds()))
    observations_ok = len(consecutive) >= selected["minimum_observations"]
    quiet_ok = quiet_seconds is not None and quiet_seconds >= selected["quiet_seconds"]
    return {
        "stable": observations_ok and quiet_ok,
        "consecutive_observations": len(consecutive),
        "minimum_observations": selected["minimum_observations"],
        "quiet_seconds": quiet_seconds,
        "minimum_quiet_seconds": selected["quiet_seconds"],
        "observations_ok": observations_ok,
        "quiet_window_ok": quiet_ok,
    }


def candidate_record(
    observation: Mapping[str, Any],
    *,
    previous: Mapping[str, Any] | None = None,
    configured_policy: Mapping[str, Any] | None = None,
    now_time: dt.datetime | None = None,
) -> dict[str, Any]:
    now_time = now_time or dt.datetime.now(dt.timezone.utc)
    if now_time.tzinfo is None:
        now_time = now_time.replace(tzinfo=dt.timezone.utc)
    policy = merged_policy(configured_policy)
    previous = _mapping(previous)
    owner = str(observation.get("owner") or "unknown")
    kind = str(observation.get("kind") or "unknown")
    path = canonical_candidate_path(str(observation.get("path") or ""))
    source_id = str(observation.get("source_id") or "")
    candidate_id = str(observation.get("candidate_id") or stable_candidate_id(owner=owner, kind=kind, path=path, source_id=source_id))
    provisional = provisional_classification(observation, now_time=now_time)
    current_history = observation_history_entry(observation, provisional)
    history = _append_history(
        _list_of_mappings(previous.get("observation_history")),
        current_history,
        max(3, _safe_int(policy.get("history_limit"), 32)),
    )
    verdict = str(provisional.get("verdict") or "blocked_unknown")
    blockers = _list_of_mappings(provisional.get("blockers"))
    stability = _stability(observation, history, verdict, policy, now_time=now_time)
    if verdict in READY_VERDICTS and not stability["stable"]:
        provisional_ready = verdict
        verdict = "blocked_unknown" if verdict in DELETE_READY_VERDICTS else "archive_pending"
        blockers.append(
            _blocker(
                "candidate_not_stable_across_required_window",
                "observation_history",
                {
                    **stability,
                    "provisional_ready_verdict": provisional_ready,
                },
            )
        )
    reclaimable_bytes = observation.get("reclaimable_bytes")
    minimum_bytes = max(0, _safe_int(policy.get("minimum_reclaimable_bytes"), 1))
    if verdict in DELETE_READY_VERDICTS and _safe_int(reclaimable_bytes, -1) < minimum_bytes:
        verdict = "blocked_unknown"
        blockers.append(_blocker("no_measurable_reclaim_benefit", "reclaimable_size", reclaimable_bytes))
    previous_verdict = previous.get("verdict")
    lifecycle_state = "observed" if any(item.get("code") == "candidate_not_stable_across_required_window" for item in blockers) else "classified"
    record = {
        "candidate_id": candidate_id,
        "source_id": source_id,
        "path": path,
        "owner": owner,
        "kind": kind,
        "source_adapter": observation.get("source_adapter"),
        "exists": observation.get("exists") is True,
        "physical_bytes": observation.get("physical_bytes"),
        "size_basis": "physical_allocated_bytes",
        "reclaimable_bytes": reclaimable_bytes,
        "fingerprint": dict(_mapping(observation.get("fingerprint"))),
        "latest_mtime": observation.get("latest_mtime"),
        "observed_at": observation.get("observed_at"),
        "retention_until": _retention_until_value(observation),
        "evidence": dict(_mapping(observation.get("evidence"))),
        "executor": dict(_mapping(observation.get("executor"))),
        "verdict": verdict,
        "provisional_verdict": provisional.get("verdict"),
        "lifecycle_state": lifecycle_state,
        "blockers": blockers,
        "reasons": list(provisional.get("reasons") or []),
        "stability": stability,
        "observation_history": history,
        "transition": {
            "previous": previous_verdict,
            "current": verdict,
            "changed": bool(previous_verdict and previous_verdict != verdict),
        },
        "automatic_deletion": False,
        "requires_operator": True,
    }
    record["evidence_digest"] = _digest({
        "candidate_id": candidate_id,
        "fingerprint": record["fingerprint"],
        "verdict": verdict,
        "blockers": blockers,
        "executor": record["executor"],
    })
    return record


def _refresh_record_integrity(record: dict[str, Any]) -> None:
    previous_verdict = _mapping(record.get("transition")).get("previous")
    verdict = str(record.get("verdict") or "blocked_unknown")
    blockers = _list_of_mappings(record.get("blockers"))
    executor = dict(_mapping(record.get("executor")))
    record["transition"] = {
        "previous": previous_verdict,
        "current": verdict,
        "changed": bool(previous_verdict and previous_verdict != verdict),
    }
    record["evidence_digest"] = _digest({
        "candidate_id": record.get("candidate_id"),
        "fingerprint": dict(_mapping(record.get("fingerprint"))),
        "verdict": verdict,
        "blockers": blockers,
        "executor": executor,
    })


def _path_parts(path: str) -> tuple[str, ...]:
    try:
        return Path(path).parts
    except (OSError, ValueError):
        return ()


def apply_overlap_guards(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for parent in records:
        parent_parts = _path_parts(str(parent.get("path") or ""))
        if not parent_parts:
            continue
        children = [
            child
            for child in records
            if child is not parent
            and len(_path_parts(str(child.get("path") or ""))) > len(parent_parts)
            and _path_parts(str(child.get("path") or ""))[: len(parent_parts)] == parent_parts
        ]
        if not children:
            continue
        parent["overlap"] = {
            "role": "ancestor_summary_only",
            "child_candidate_ids": [str(item.get("candidate_id")) for item in children],
        }
        parent["reclaimable_bytes"] = 0
        if parent.get("verdict") in READY_VERDICTS:
            parent["verdict"] = "blocked_unknown"
            parent["lifecycle_state"] = "classified"
            parent.setdefault("blockers", []).append(
                _blocker("overlapping_child_candidates_require_exact_scope", "candidate_inventory", parent["overlap"])
            )
        _refresh_record_integrity(parent)
    return records


def candidates_document(
    observations: Sequence[Mapping[str, Any]],
    *,
    previous_document: Mapping[str, Any] | None,
    configured_policy: Mapping[str, Any] | None,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: Mapping[str, Any],
    deep: bool,
) -> dict[str, Any]:
    previous_document = _mapping(previous_document)
    previous_by_id = {
        str(item.get("candidate_id")): item
        for item in _list_of_mappings(previous_document.get("candidates"))
        if item.get("candidate_id")
    }
    now_time = _parse_time(generated_at) or dt.datetime.now(dt.timezone.utc)
    records = [
        candidate_record(
            observation,
            previous=previous_by_id.get(
                str(observation.get("candidate_id") or stable_candidate_id(
                    owner=str(observation.get("owner") or "unknown"),
                    kind=str(observation.get("kind") or "unknown"),
                    path=str(observation.get("path") or ""),
                    source_id=str(observation.get("source_id") or ""),
                ))
            ),
            configured_policy=configured_policy,
            now_time=now_time,
        )
        for observation in observations
        if isinstance(observation, Mapping) and observation.get("path")
    ]
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        current = deduped.get(str(record["candidate_id"]))
        if current is None or _safe_int(record.get("physical_bytes"), -1) > _safe_int(current.get("physical_bytes"), -1):
            deduped[str(record["candidate_id"])] = record
    records = apply_overlap_guards(list(deduped.values()))
    records.sort(key=lambda item: (_safe_int(item.get("reclaimable_bytes")), _safe_int(item.get("physical_bytes"))), reverse=True)
    coverage = coverage_summary(records)
    current_ids = {str(item.get("candidate_id")) for item in records}
    retired = [
        {
            "candidate_id": candidate_id,
            "path": item.get("path"),
            "owner": item.get("owner"),
            "kind": item.get("kind"),
            "last_verdict": item.get("verdict"),
            "last_seen": item.get("observed_at"),
            "retired_at": generated_at,
            "reason": "not_rediscovered_in_current_refresh",
        }
        for candidate_id, item in previous_by_id.items()
        if candidate_id not in current_ids
    ]
    by_verdict: dict[str, dict[str, int]] = {}
    for item in records:
        verdict = str(item.get("verdict") or "blocked_unknown")
        summary = by_verdict.setdefault(verdict, {"candidates": 0, "physical_bytes": 0, "reclaimable_bytes": 0})
        summary["candidates"] += 1
        summary["physical_bytes"] += max(0, _safe_int(item.get("physical_bytes")))
        summary["reclaimable_bytes"] += max(0, _safe_int(item.get("reclaimable_bytes")))
    data = {
        "schema": f"{schema_prefix}_storage_candidates_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "deep": bool(deep),
        "snapshot_id": snapshot_id(records),
        "policy": {
            **merged_policy(configured_policy),
            "automatic_deletion": False,
            "absence_of_pid_is_not_permission": True,
            "age_alone_is_not_permission": True,
            "missing_or_expired_claim_is_not_permission": True,
            "owner_verdicts_cannot_be_overridden": True,
        },
        "coverage": coverage,
        "runtime_errors": list(coverage.get("runtime_errors", [])),
        "pressure_findings": list(coverage.get("pressure_findings", [])),
        "freshness": {
            "status": "fresh" if deep else "unknown",
            "last_deep_at": generated_at if deep else None,
            "generated_at": generated_at,
            "age_seconds": 0 if deep else None,
            "max_age_seconds": _safe_int(merged_policy(configured_policy).get("deep_max_age_seconds"), 172800),
            "reason": "deep_refresh_completed" if deep else "light_refresh_requires_prior_deep_snapshot",
        },
        "summary": {
            "candidates": len(records),
            "ready": sum(1 for item in records if item.get("verdict") in READY_VERDICTS),
            "delete_ready": sum(1 for item in records if item.get("verdict") in DELETE_READY_VERDICTS),
            "archive_ready": sum(1 for item in records if item.get("verdict") == "archive_ready"),
            "changed": sum(1 for item in records if _mapping(item.get("transition")).get("changed") is True),
            "retired": len(retired),
            "physical_bytes": sum(max(0, _safe_int(item.get("physical_bytes"))) for item in records),
            "reclaimable_bytes": sum(max(0, _safe_int(item.get("reclaimable_bytes"))) for item in records if not item.get("overlap")),
            "physical_measured": coverage.get("physical_measured"),
            "fingerprint_complete": coverage.get("fingerprint_complete"),
            "runtime_error_count": coverage.get("runtime_error_count"),
            "pressure_finding_count": coverage.get("pressure_finding_count"),
            "by_verdict": by_verdict,
        },
        "changes": [
            {
                "candidate_id": item.get("candidate_id"),
                "path": item.get("path"),
                "previous": _mapping(item.get("transition")).get("previous"),
                "current": item.get("verdict"),
            }
            for item in records
            if _mapping(item.get("transition")).get("changed") is True
        ],
        "candidates": records,
        "retired": retired[:200],
        "paths": dict(paths),
    }
    return data


def candidate_history_event(document: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _list_of_mappings(document.get("candidates"))
    return {
        "schema": "abyss_machine_storage_candidate_history_event_v1",
        "version": document.get("version"),
        "generated_at": document.get("generated_at"),
        "deep": document.get("deep") is True,
        "last_deep_at": document.get("last_deep_at"),
        "freshness": document.get("freshness"),
        "coverage": document.get("coverage"),
        "runtime_errors": document.get("runtime_errors", []),
        "pressure_findings": document.get("pressure_findings", []),
        "snapshot_id": document.get("snapshot_id"),
        "summary": document.get("summary"),
        "changes": document.get("changes"),
        "observations": [
            {
                "candidate_id": item.get("candidate_id"),
                "path": item.get("path"),
                "owner": item.get("owner"),
                "kind": item.get("kind"),
                "verdict": item.get("verdict"),
                "physical_bytes": item.get("physical_bytes"),
                "size_basis": item.get("size_basis", "physical_allocated_bytes"),
                "reclaimable_bytes": item.get("reclaimable_bytes"),
                "fingerprint_digest": _mapping(item.get("fingerprint")).get("digest"),
                "fingerprint_complete": _mapping(item.get("fingerprint")).get("complete") is True,
                "blockers": [blocker.get("code") for blocker in _list_of_mappings(item.get("blockers"))],
            }
            for item in candidates
        ] if document.get("deep") is True else [],
        "full_evidence_path": _mapping(document.get("paths")).get("latest"),
    }


def filter_candidates(
    document: Mapping[str, Any],
    *,
    verdicts: Sequence[str] | None = None,
    owners: Sequence[str] | None = None,
    blockers: Sequence[str] | None = None,
    minimum_bytes: int = 0,
    changed_only: bool = False,
) -> list[dict[str, Any]]:
    verdict_set = {str(item) for item in verdicts or [] if str(item)}
    owner_set = {str(item) for item in owners or [] if str(item)}
    blocker_set = {str(item) for item in blockers or [] if str(item)}
    selected: list[dict[str, Any]] = []
    for item in _list_of_mappings(document.get("candidates")):
        codes = {str(blocker.get("code")) for blocker in _list_of_mappings(item.get("blockers"))}
        if verdict_set and str(item.get("verdict")) not in verdict_set:
            continue
        if owner_set and str(item.get("owner")) not in owner_set:
            continue
        if blocker_set and not blocker_set.intersection(codes):
            continue
        if max(_safe_int(item.get("reclaimable_bytes")), _safe_int(item.get("physical_bytes"))) < max(0, int(minimum_bytes)):
            continue
        if changed_only and _mapping(item.get("transition")).get("changed") is not True:
            continue
        selected.append(item)
    return selected


def explain_candidate(document: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    candidate = next(
        (item for item in _list_of_mappings(document.get("candidates")) if str(item.get("candidate_id")) == candidate_id),
        None,
    )
    if candidate is None:
        return {
            "schema": "abyss_machine_storage_candidate_explain_v1",
            "ok": False,
            "candidate_id": candidate_id,
            "error": "candidate_not_found",
            "snapshot_id": document.get("snapshot_id"),
        }
    return {
        "schema": "abyss_machine_storage_candidate_explain_v1",
        "ok": True,
        "snapshot_id": document.get("snapshot_id"),
        "candidate": candidate,
        "explanation": {
            "verdict": candidate.get("verdict"),
            "reasons": candidate.get("reasons"),
            "blockers": candidate.get("blockers"),
            "physical_bytes": candidate.get("physical_bytes"),
            "size_basis": candidate.get("size_basis", "physical_allocated_bytes"),
            "reclaimable_bytes": candidate.get("reclaimable_bytes"),
            "recovery": _mapping(candidate.get("evidence")).get("recovery"),
            "replacement": _mapping(candidate.get("evidence")).get("replacement"),
            "backup": _mapping(candidate.get("evidence")).get("backup"),
            "restore": _mapping(candidate.get("evidence")).get("restore"),
            "stability": candidate.get("stability"),
        },
    }


def apply_contract(candidate: Mapping[str, Any], snapshot: str) -> dict[str, Any]:
    kind = str(candidate.get("kind") or "unknown")
    executor = _mapping(candidate.get("executor"))
    expected_executor = EXECUTORS_BY_KIND.get(kind)
    admitted = bool(expected_executor and executor.get("type") == expected_executor and executor.get("owner_specific") is True)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "snapshot_id": snapshot,
        "fingerprint_digest": _mapping(candidate.get("fingerprint")).get("digest"),
        "evidence_digest": candidate.get("evidence_digest"),
        "verdict": candidate.get("verdict"),
        "executor": dict(executor),
        "expected_executor": expected_executor,
        "executor_admitted": admitted,
        "automatic": False,
        "requires_operator": True,
        "requires_revalidation_immediately_before_apply": True,
        "drift_behavior": "fail_closed",
        "source_contract_executes_mutation": False,
    }


def validate_candidate(
    document: Mapping[str, Any],
    current_observation: Mapping[str, Any],
    *,
    candidate_id: str,
    configured_policy: Mapping[str, Any] | None,
    generated_at: str,
) -> dict[str, Any]:
    saved = next(
        (item for item in _list_of_mappings(document.get("candidates")) if str(item.get("candidate_id")) == candidate_id),
        None,
    )
    if saved is None:
        return {
            "schema": "abyss_machine_storage_candidate_validate_v1",
            "generated_at": generated_at,
            "ok": False,
            "valid": False,
            "candidate_id": candidate_id,
            "error": "candidate_not_found",
        }
    current = candidate_record(
        current_observation,
        previous=saved,
        configured_policy=configured_policy,
        now_time=_parse_time(generated_at),
    )
    saved_fingerprint = _mapping(saved.get("fingerprint")).get("digest")
    current_fingerprint = _mapping(current.get("fingerprint")).get("digest")
    drift = saved_fingerprint != current_fingerprint
    verdict_changed = saved.get("verdict") != current.get("verdict")
    contract = apply_contract(saved, str(document.get("snapshot_id") or ""))
    ready = saved.get("verdict") in READY_VERDICTS
    valid = bool(ready and not drift and not verdict_changed and contract.get("executor_admitted"))
    reasons: list[str] = []
    if not ready:
        reasons.append("saved_candidate_not_ready")
    if drift:
        reasons.append("filesystem_fingerprint_drift")
    if verdict_changed:
        reasons.append("verdict_changed_on_revalidation")
    if not contract.get("executor_admitted"):
        reasons.append("candidate_executor_not_admitted")
    return {
        "schema": "abyss_machine_storage_candidate_validate_v1",
        "generated_at": generated_at,
        "ok": valid,
        "valid": valid,
        "decision": "operator_apply_eligible" if valid else "blocked_fail_closed",
        "candidate_id": candidate_id,
        "snapshot_id": document.get("snapshot_id"),
        "reasons": reasons or ["candidate evidence and fingerprint remain current"],
        "saved": {
            "verdict": saved.get("verdict"),
            "fingerprint_digest": saved_fingerprint,
            "evidence_digest": saved.get("evidence_digest"),
        },
        "current": {
            "verdict": current.get("verdict"),
            "fingerprint_digest": current_fingerprint,
            "evidence_digest": current.get("evidence_digest"),
            "blockers": current.get("blockers"),
        },
        "apply_contract": contract,
    }


def apply_preflight(
    candidate: Mapping[str, Any],
    validation: Mapping[str, Any],
    current_observation: Mapping[str, Any],
) -> dict[str, Any]:
    expected_fingerprint = _mapping(validation.get("saved")).get("fingerprint_digest")
    current_fingerprint = _mapping(current_observation.get("fingerprint")).get("digest")
    valid = validation.get("valid") is True
    same_candidate = str(validation.get("candidate_id")) == str(candidate.get("candidate_id"))
    no_drift = bool(expected_fingerprint and expected_fingerprint == current_fingerprint)
    allowed = bool(valid and same_candidate and no_drift)
    return {
        "ok": allowed,
        "decision": "operator_apply_eligible" if allowed else "blocked_fail_closed",
        "candidate_id": candidate.get("candidate_id"),
        "expected_fingerprint_digest": expected_fingerprint,
        "current_fingerprint_digest": current_fingerprint,
        "reasons": [] if allowed else [
            reason
            for reason, present in (
                ("validation_not_current_or_valid", not valid),
                ("candidate_identity_mismatch", not same_candidate),
                ("filesystem_fingerprint_drift", not no_drift),
            )
            if present
        ],
        "automatic": False,
        "executes_mutation": False,
    }


def approval_document(
    *,
    candidate: Mapping[str, Any],
    validation: Mapping[str, Any],
    approved_by: str,
    approved_at: str,
    expires_at: str,
    note: str | None = None,
) -> dict[str, Any]:
    expires = _parse_time(expires_at)
    approved = _parse_time(approved_at)
    same_candidate = str(candidate.get("candidate_id") or "") == str(validation.get("candidate_id") or "")
    errors = [
        code for code, failed in (
            ("approved_by_required", not approved_by),
            ("candidate_validation_not_valid", validation.get("valid") is not True),
            ("candidate_identity_mismatch", not same_candidate),
            ("valid_expiry_required", expires is None),
            ("expiry_must_follow_approval", bool(expires and approved and expires <= approved)),
        ) if failed
    ]
    return {
        "schema": "abyss_machine_storage_candidate_approval_v1",
        "candidate_id": candidate.get("candidate_id"),
        "snapshot_id": validation.get("snapshot_id"),
        "fingerprint_digest": _mapping(validation.get("saved")).get("fingerprint_digest"),
        "evidence_digest": _mapping(validation.get("saved")).get("evidence_digest"),
        "approved_by": approved_by,
        "approved_at": approved_at,
        "expires_at": expires_at,
        "note": note,
        "valid": not errors,
        "errors": errors,
        "single_candidate_only": True,
        "automatic": False,
        "does_not_execute_mutation": True,
    }


def operator_apply_preflight(
    *,
    candidate: Mapping[str, Any],
    validation: Mapping[str, Any],
    approval: Mapping[str, Any],
    now_time: dt.datetime | None = None,
) -> dict[str, Any]:
    now_time = now_time or dt.datetime.now(dt.timezone.utc)
    if now_time.tzinfo is None:
        now_time = now_time.replace(tzinfo=dt.timezone.utc)
    expiry = _parse_time(approval.get("expires_at"))
    contract = apply_contract(candidate, str(validation.get("snapshot_id") or ""))
    saved = _mapping(validation.get("saved"))
    reasons = [
        code for code, failed in (
            ("validation_not_valid", validation.get("valid") is not True),
            ("approval_not_valid", approval.get("valid") is not True),
            ("approval_expired", expiry is None or expiry <= now_time.astimezone(dt.timezone.utc)),
            ("candidate_identity_mismatch", str(candidate.get("candidate_id") or "") != str(approval.get("candidate_id") or "") or str(candidate.get("candidate_id") or "") != str(validation.get("candidate_id") or "")),
            ("snapshot_binding_mismatch", str(approval.get("snapshot_id") or "") != str(validation.get("snapshot_id") or "")),
            ("fingerprint_binding_mismatch", str(approval.get("fingerprint_digest") or "") != str(saved.get("fingerprint_digest") or "")),
            ("evidence_binding_mismatch", str(approval.get("evidence_digest") or "") != str(saved.get("evidence_digest") or "")),
            ("candidate_executor_not_admitted", contract.get("executor_admitted") is not True),
        ) if failed
    ]
    return {
        "schema": "abyss_machine_storage_candidate_operator_apply_preflight_v1",
        "candidate_id": candidate.get("candidate_id"),
        "ok": not reasons,
        "decision": "operator_apply_eligible" if not reasons else "blocked_fail_closed",
        "reasons": reasons,
        "apply_contract": contract,
        "automatic": False,
        "executes_mutation": False,
    }


def receipt_document(
    *,
    candidate_id: str,
    approval: Mapping[str, Any],
    action: str,
    result: str,
    applied_at: str,
    before_bytes: int | None,
    after_bytes: int | None,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    approval_expiry = _parse_time(approval.get("expires_at"))
    action_time = _parse_time(applied_at) or dt.datetime.now(dt.timezone.utc)
    errors = [
        code for code, failed in (
            ("approval_not_valid", approval.get("valid") is not True),
            ("candidate_identity_mismatch", str(approval.get("candidate_id") or "") != candidate_id),
            ("approval_expired", approval_expiry is None or approval_expiry <= action_time),
            ("action_required", not action),
            ("unsupported_result", result not in {"applied", "failed", "aborted"}),
            ("evidence_ref_required", not evidence_refs),
        ) if failed
    ]
    reclaimed = None
    if isinstance(before_bytes, int) and isinstance(after_bytes, int):
        reclaimed = max(0, before_bytes - after_bytes)
    return {
        "schema": "abyss_machine_storage_candidate_receipt_v1",
        "candidate_id": candidate_id,
        "approval": {
            "snapshot_id": approval.get("snapshot_id"),
            "fingerprint_digest": approval.get("fingerprint_digest"),
            "evidence_digest": approval.get("evidence_digest"),
            "approved_by": approval.get("approved_by"),
        },
        "action": action,
        "result": result,
        "applied_at": applied_at,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "reclaimed_bytes": reclaimed,
        "evidence_refs": [str(item) for item in evidence_refs if str(item)],
        "valid": not errors,
        "errors": errors,
        "lifecycle_state": "receipted" if not errors else "receipt_rejected",
        "records_external_action_only": True,
    }


def manifest_document(
    *,
    path: str,
    owner: str,
    kind: str,
    purpose: str,
    producer: str,
    source_id: str,
    recovery_command: str | None,
    replacement_ref: str | None,
    retention_until: str | None,
    executor_type: str | None,
    created_at: str,
    unique_data_clear: bool = False,
    preserved_refs: Sequence[str] | None = None,
    archivable: bool = False,
    recovery_verified: bool = False,
    replacement_verified: bool = False,
    archive: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    path = canonical_candidate_path(path)
    candidate_id = stable_candidate_id(owner=owner, kind=kind, path=path, source_id=source_id)
    errors: list[str] = []
    if not path or not Path(path).is_absolute():
        errors.append("absolute_path_required")
    if not owner or owner == "unknown":
        errors.append("owner_required")
    if not kind:
        errors.append("kind_required")
    if not purpose:
        errors.append("purpose_required")
    if retention_until is not None and _parse_retention_until(retention_until) is None:
        errors.append("retention_until_invalid")
    return {
        "schema": "abyss_machine_storage_candidate_manifest_v1",
        "candidate_id": candidate_id,
        "path": path,
        "owner": owner,
        "kind": kind,
        "purpose": purpose,
        "producer": producer,
        "source_id": source_id,
        "created_at": created_at,
        "retention_until": retention_until,
        "unique_data_clear": bool(unique_data_clear),
        "preserved_refs": [str(item) for item in preserved_refs or [] if str(item)],
        "archivable": bool(archivable),
        "recovery": {
            "command": recovery_command,
            "declared": bool(recovery_command),
            "verified": bool(recovery_verified and recovery_command),
        },
        "replacement": {
            "ref": replacement_ref,
            "declared": bool(replacement_ref),
            "verified": bool(replacement_verified and replacement_ref),
        },
        "archive": dict(archive or {}),
        "executor": {
            "type": executor_type or EXECUTORS_BY_KIND.get(kind),
            "owner_specific": bool(executor_type or EXECUTORS_BY_KIND.get(kind)),
        },
        "valid": not errors,
        "errors": errors,
        "automatic_deletion": False,
    }


def claim_document(
    *,
    claim_id: str,
    candidate_id: str | None,
    path: str | None,
    owner: str,
    session_id: str | None,
    change_id: str | None,
    purpose: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if not claim_id:
        errors.append("claim_id_required")
    if not candidate_id and not path:
        errors.append("candidate_id_or_path_required")
    if not owner:
        errors.append("owner_required")
    if _parse_time(expires_at) is None:
        errors.append("valid_expires_at_required")
    return {
        "schema": "abyss_machine_storage_candidate_claim_v1",
        "claim_id": claim_id,
        "candidate_id": candidate_id,
        "path": path,
        "owner": owner,
        "session_id": session_id,
        "change_id": change_id,
        "purpose": purpose,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "valid": not errors,
        "errors": errors,
        "absence_or_expiry_is_not_delete_permission": True,
    }


def active_claims(
    claims: Sequence[Mapping[str, Any]],
    *,
    candidate_id: str,
    path: str,
    now_time: dt.datetime | None = None,
) -> list[dict[str, Any]]:
    now_time = now_time or dt.datetime.now(dt.timezone.utc)
    active: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, Mapping) or claim.get("valid") is not True:
            continue
        expires = _parse_time(claim.get("expires_at"))
        if expires is None or expires <= now_time.astimezone(dt.timezone.utc):
            continue
        matches_id = str(claim.get("candidate_id") or "") == candidate_id
        claim_path = str(claim.get("path") or "")
        matches_path = bool(claim_path and (claim_path == path or path.startswith(claim_path.rstrip("/") + "/") or claim_path.startswith(path.rstrip("/") + "/")))
        if matches_id or matches_path:
            active.append(dict(claim))
    return active


def paths_document(
    *,
    root: Path,
    latest_path: Path,
    manifests_root: Path,
    claims_root: Path,
    validation_root: Path,
) -> dict[str, Any]:
    return {
        "root": str(root),
        "latest": str(latest_path),
        "daily_glob": str(root / "history" / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "manifests": str(manifests_root),
        "claims": str(claims_root),
        "validation": str(validation_root),
        "commands": {
            "refresh": "abyss-machine storage candidates refresh --json",
            "refresh_deep": "abyss-machine storage candidates refresh --deep --json",
            "list": "abyss-machine storage candidates list --json",
            "explain": "abyss-machine storage candidates explain CANDIDATE_ID --json",
            "validate": "abyss-machine storage candidates validate CANDIDATE_ID --json",
            "preflight": "abyss-machine storage candidates preflight CANDIDATE_ID --json",
        },
    }
