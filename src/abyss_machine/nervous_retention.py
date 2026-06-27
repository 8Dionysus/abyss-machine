from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, Mapping


def _int_policy(policy: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(policy.get(key) or default)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stable_hash_json(payload: Any, length: int = 24) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[: max(8, min(int(length), 64))]


def route_specs(privacy: Mapping[str, Any], roots: Mapping[str, Any]) -> list[dict[str, Any]]:
    retention = privacy.get("retention") if isinstance(privacy.get("retention"), dict) else {}
    facts_days = _int_policy(retention, "facts_days", 90)
    summaries_days = _int_policy(retention, "summaries_days", 365)
    raw_events_days = _int_policy(retention, "raw_events_days", 14)
    private_capture_artifacts_days = _int_policy(retention, "private_capture_artifacts_days", raw_events_days)
    retrieval_packs_days = _int_policy(retention, "retrieval_packs_days", 30)
    evals_days = _int_policy(retention, "evals_days", summaries_days)
    return [
        {"layer": "facts", "root": str(roots["facts"]), "days": facts_days, "apply_allowed": False, "reason": "facts require explicit forget"},
        {"layer": "events", "root": str(roots["events"]), "days": raw_events_days, "apply_allowed": False, "reason": "derived event horizon is coupled to fact rebuild"},
        {"layer": "episodes", "root": str(roots["episodes"]), "days": summaries_days, "apply_allowed": False, "reason": "derived episode horizon is coupled to event rebuild"},
        {"layer": "retrieval", "root": str(roots["retrieval"]), "days": retrieval_packs_days, "apply_allowed": True, "reason": "operator recall packs are reproducible from the index"},
        {"layer": "synthesis", "root": str(roots["synthesis"]), "days": summaries_days, "apply_allowed": False, "reason": "reviewable synthesis candidates are retained as durable memory candidates"},
        {"layer": "evals", "root": str(roots["evals"]), "days": evals_days, "apply_allowed": True, "reason": "old eval history is diagnostic and latest summaries are preserved"},
        {"layer": "checks", "root": str(roots["checks"]), "days": summaries_days, "apply_allowed": True, "reason": "old check history is diagnostic and latest summaries are preserved"},
        {"layer": "private_capture_artifacts", "root": str(roots["private_capture_artifacts"]), "days": private_capture_artifacts_days, "apply_allowed": True, "extensions": [".png"], "reason": "raw local-private artifacts are bounded; compact redacted facts remain under /var/lib"},
        {"layer": "browser_content", "root": str(roots["browser_content"]), "days": private_capture_artifacts_days, "apply_allowed": True, "extensions": [".jsonl", ".json"], "reason": "browser page text captures are local-private calibration evidence with bounded retention"},
    ]


def root_missing_record(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "layer": spec["layer"],
        "root": str(spec["root"]),
        "exists": False,
        "days": spec["days"],
        "apply_allowed": bool(spec["apply_allowed"]),
        "candidate": False,
        "reason": "root_missing",
    }


def file_candidate_record(
    spec: Mapping[str, Any],
    *,
    path: str,
    relative: str,
    suffix: str,
    size_bytes: int | None,
    mtime: dt.datetime | None,
    now_time: dt.datetime,
) -> dict[str, Any]:
    protected = relative == "latest.json" or "/latest.json" in relative
    allowed_extensions = set(spec.get("extensions") or [".jsonl", ".json", ".md"])
    if suffix not in allowed_extensions:
        protected = True
    age_days = round((now_time - mtime).total_seconds() / 86400.0, 3) if mtime else None
    expired = age_days is not None and age_days > float(spec["days"])
    candidate = bool(expired and spec["apply_allowed"] and not protected)
    return {
        "layer": spec["layer"],
        "path": path,
        "relative": relative,
        "exists": True,
        "size_bytes": size_bytes,
        "mtime": mtime.isoformat(timespec="seconds") if mtime else None,
        "age_days": age_days,
        "retention_days": spec["days"],
        "apply_allowed": bool(spec["apply_allowed"]),
        "protected": protected,
        "candidate": candidate,
        "reason": spec["reason"] if not candidate else "expired_and_apply_allowed",
    }


def retention_policy() -> dict[str, Any]:
    return {
        "facts_delete_behavior": "explicit forget only",
        "default_apply": "dry-run",
        "no_project_repo_mutation": True,
        "no_symlink_tails_required": True,
    }


def plan_refused_result(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_retention_plan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; retention plan did not write latest/history files",
    }


def apply_refused_result(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_retention_apply_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; retention apply did not touch files",
    }


def plan_document(
    *,
    routes: list[dict[str, Any]],
    files: list[dict[str, Any]],
    route_errors: list[dict[str, Any]],
    paths: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    candidates = [item for item in files if item.get("candidate")]
    by_layer: dict[str, dict[str, Any]] = {}
    for item in files:
        layer = str(item.get("layer") or "unknown")
        stats = by_layer.setdefault(layer, {"files": 0, "bytes": 0, "candidates": 0, "candidate_bytes": 0})
        if item.get("exists"):
            stats["files"] += 1
            stats["bytes"] += int(item.get("size_bytes") or 0)
        if item.get("candidate"):
            stats["candidates"] += 1
            stats["candidate_bytes"] += int(item.get("size_bytes") or 0)
    return {
        "schema": f"{schema_prefix}_nervous_retention_plan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not route_errors,
        "policy": retention_policy(),
        "routes": routes,
        "summary": {
            "files": sum(1 for item in files if item.get("exists")),
            "bytes": sum(int(item.get("size_bytes") or 0) for item in files if item.get("exists")),
            "candidates": len(candidates),
            "candidate_bytes": sum(int(item.get("size_bytes") or 0) for item in candidates),
            "by_layer": by_layer,
            "route_errors": len(route_errors),
        },
        "candidates": candidates[:200],
        "route_errors": route_errors,
        "paths": paths,
    }


def apply_document(
    *,
    plan: Mapping[str, Any],
    dry_run: bool,
    confirm: bool,
    removed: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    paths: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    candidates = [item for item in plan.get("candidates", []) if isinstance(item, dict) and item.get("candidate")]
    should_apply = bool(confirm) and not dry_run
    return {
        "schema": f"{schema_prefix}_nervous_retention_apply_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not errors and bool(plan.get("ok")),
        "dry_run": dry_run,
        "confirm": confirm,
        "applied": should_apply,
        "plan_summary": plan.get("summary"),
        "removed": removed,
        "errors": errors,
        "summary": {
            "candidate_files": len(candidates),
            "removed_files": len(removed),
            "errors": len(errors),
            "candidate_bytes": _nested_get(plan, ["summary", "candidate_bytes"]),
            "removed_bytes": sum(int(item.get("size_bytes") or 0) for item in removed),
        },
        "policy": plan.get("policy"),
        "paths": paths,
    }


def validate_document(
    *,
    plan: Mapping[str, Any],
    latest_exists: bool,
    latest_path: str,
    latest_error: str | None,
    validate_latest_path: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
        item: dict[str, Any] = {"level": level, "key": key, "message": message}
        if details is not None:
            item["details"] = details
        checks.append(item)

    add("ok" if plan.get("ok") else "fail", "plan", "retention plan builds without route errors", plan.get("summary"))
    add("ok" if _nested_get(plan, ["policy", "facts_delete_behavior"]) == "explicit forget only" else "fail", "facts_policy", "facts are not deleted by retention apply", plan.get("policy"))
    add("ok" if latest_exists else "warn", "latest", "retention latest exists", {"path": latest_path, "error": latest_error})
    protected_violations = [
        item for item in plan.get("candidates", [])
        if isinstance(item, dict) and item.get("protected")
    ]
    add("ok" if not protected_violations else "fail", "protected", "latest/protected files are not retention candidates", {"violations": protected_violations[:20]})
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_retention_validate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "checks": checks,
        "summary": {"fails": fails, "warnings": warnings, "checks": len(checks)},
        "paths": {"latest": latest_path, "validate_latest": validate_latest_path},
    }


def layer_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    by_layer = summary.get("by_layer") if isinstance(summary.get("by_layer"), dict) else {}
    layers: dict[str, Any] = {}
    for layer, stats in sorted(by_layer.items()):
        if not isinstance(stats, dict):
            continue
        layers[str(layer)] = {
            "files": _safe_int(stats.get("files"), 0),
            "bytes": _safe_int(stats.get("bytes"), 0),
            "candidates": _safe_int(stats.get("candidates"), 0),
            "candidate_bytes": _safe_int(stats.get("candidate_bytes"), 0),
        }
    return layers


def privacy_route(
    retention_plan: Mapping[str, Any],
    *,
    schema_prefix: str,
    retention_latest_path: str,
    retention_validate_latest_path: str,
    privacy_config_path: str,
    privacy_state_path: str,
    route_errors_shape: Any | None = None,
) -> dict[str, Any]:
    retention_plan = retention_plan if isinstance(retention_plan, Mapping) else {}
    summary = retention_plan.get("summary") if isinstance(retention_plan.get("summary"), dict) else {}
    source_policy = retention_plan.get("policy") if isinstance(retention_plan.get("policy"), dict) else {}
    by_layer = layer_summary(summary)
    candidate_layers = [
        {
            "layer": layer,
            "candidates": stats.get("candidates"),
            "candidate_bytes": stats.get("candidate_bytes"),
            "files": stats.get("files"),
        }
        for layer, stats in sorted(
            by_layer.items(),
            key=lambda item: (_safe_int(item[1].get("candidate_bytes"), 0), _safe_int(item[1].get("candidates"), 0)),
            reverse=True,
        )
        if _safe_int(stats.get("candidates"), 0) > 0
    ]
    route_errors = retention_plan.get("route_errors") if isinstance(retention_plan.get("route_errors"), list) else []
    safe_next = {
        "kind": "nervous_retention_privacy_review",
        "owner_route": "abyss-machine:nervous-privacy",
        "review_command": "abyss-machine nervous retention-plan --json",
        "dry_run_command": "abyss-machine nervous retention-apply --dry-run --json",
        "validate_command": "abyss-machine nervous retention-validate --json",
        "human_approved_apply_command": "abyss-machine nervous retention-apply --confirm --json",
        "post_verifiers": [
            "abyss-machine nervous retention-validate --json",
            "abyss-machine nervous quality-audit --json",
            "abyss-machine reactions validate --json",
            "abyss-machine responses validate --json",
        ],
        "condition": "review layer counts, route errors, and dry-run output before any deletion; confirmed apply requires explicit operator approval and must not delete facts or project roots",
        "requires_operator": True,
        "requires_human_approval": True,
        "requires_explicit_confirm_for_deletion": True,
        "automatic": False,
        "executes_commands": False,
        "host_layer_mutates_stack": False,
        "action_execution": False,
        "does_not_delete_facts": True,
        "does_not_delete_project_roots": True,
        "does_not_follow_symlink_tails": True,
    }
    route = {
        "schema": f"{schema_prefix}_nervous_retention_privacy_route_v1",
        "route_id": "nervret-" + _stable_hash_json({
            "generated_at": retention_plan.get("generated_at"),
            "candidates": summary.get("candidates"),
            "candidate_bytes": summary.get("candidate_bytes"),
            "route_errors": _safe_int(summary.get("route_errors"), 0),
            "candidate_layers": candidate_layers,
        }, length=24),
        "generated_at": retention_plan.get("generated_at"),
        "plan_ok": retention_plan.get("ok") is True,
        "summary": {
            "files": _safe_int(summary.get("files"), 0),
            "bytes": _safe_int(summary.get("bytes"), 0),
            "candidates": _safe_int(summary.get("candidates"), 0),
            "candidate_bytes": _safe_int(summary.get("candidate_bytes"), 0),
            "route_errors": _safe_int(summary.get("route_errors"), 0),
        },
        "candidate_layers": candidate_layers,
        "by_layer": by_layer,
        "route_errors": route_errors_shape if route_errors_shape is not None else _bounded_json_shape(route_errors, max_depth=2, max_items=8),
        "retention_policy": {
            "facts_delete_behavior": source_policy.get("facts_delete_behavior"),
            "default_apply": source_policy.get("default_apply"),
            "no_project_repo_mutation": source_policy.get("no_project_repo_mutation"),
            "no_symlink_tails_required": source_policy.get("no_symlink_tails_required"),
        },
        "safe_next_action": safe_next,
        "evidence_refs": [
            {"path": retention_latest_path, "generated_at": retention_plan.get("generated_at"), "schema": retention_plan.get("schema")},
            {"path": retention_validate_latest_path, "schema": f"{schema_prefix}_nervous_retention_validate_v1"},
            {"path": privacy_config_path, "section": "retention"},
            {"path": privacy_state_path, "section": "privacy_state"},
        ],
        "policy": {
            "read_model": True,
            "owner_gated": True,
            "dry_run_first": True,
            "automatic_execution": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "deletes_project_roots": False,
            "requires_explicit_confirm_for_deletion": True,
            "facts_delete_behavior_explicit_forget_only": source_policy.get("facts_delete_behavior") == "explicit forget only",
            "default_apply_dry_run": source_policy.get("default_apply") == "dry-run",
            "no_project_repo_mutation": source_policy.get("no_project_repo_mutation") is True,
            "no_symlink_tails_required": source_policy.get("no_symlink_tails_required") is True,
            "does_not_delete_facts": True,
            "does_not_delete_latest_or_protected": True,
            "raw_private_content": False,
        },
    }
    route["complete"] = privacy_route_complete(route, schema_prefix=schema_prefix)
    return route


def privacy_route_complete(route: Any, *, schema_prefix: str = "abyss_machine") -> bool:
    if not isinstance(route, dict):
        return False
    safe_next = route.get("safe_next_action") if isinstance(route.get("safe_next_action"), dict) else {}
    policy = route.get("policy") if isinstance(route.get("policy"), dict) else {}
    summary = route.get("summary") if isinstance(route.get("summary"), dict) else {}
    return (
        route.get("schema") == f"{schema_prefix}_nervous_retention_privacy_route_v1"
        and bool(route.get("route_id"))
        and (_safe_int(summary.get("candidates"), 0) > 0 or _safe_int(summary.get("route_errors"), 0) > 0)
        and isinstance(route.get("candidate_layers"), list)
        and isinstance(route.get("by_layer"), dict)
        and bool(route.get("evidence_refs"))
        and safe_next.get("requires_operator") is True
        and safe_next.get("requires_human_approval") is True
        and safe_next.get("requires_explicit_confirm_for_deletion") is True
        and safe_next.get("automatic") is False
        and safe_next.get("executes_commands") is False
        and safe_next.get("host_layer_mutates_stack") is False
        and safe_next.get("does_not_delete_facts") is True
        and safe_next.get("does_not_delete_project_roots") is True
        and safe_next.get("does_not_follow_symlink_tails") is True
        and bool(safe_next.get("dry_run_command"))
        and bool(safe_next.get("validate_command"))
        and policy.get("owner_gated") is True
        and policy.get("dry_run_first") is True
        and policy.get("automatic_execution") is False
        and policy.get("executes_commands") is False
        and policy.get("host_layer_mutates_stack") is False
        and policy.get("writes_project_roots") is False
        and policy.get("deletes_project_roots") is False
        and policy.get("requires_explicit_confirm_for_deletion") is True
        and policy.get("facts_delete_behavior_explicit_forget_only") is True
        and policy.get("default_apply_dry_run") is True
        and policy.get("no_project_repo_mutation") is True
        and policy.get("no_symlink_tails_required") is True
        and policy.get("does_not_delete_facts") is True
        and policy.get("does_not_delete_latest_or_protected") is True
        and policy.get("raw_private_content") is False
    )


def _bounded_json_shape(value: Any, depth: int = 0, max_depth: int = 2, max_items: int = 12) -> Any:
    if depth >= max_depth:
        if isinstance(value, dict):
            return {"type": "object", "keys": sorted(str(key) for key in value)[:max_items]}
        if isinstance(value, list):
            return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        shaped: dict[str, Any] = {}
        for key in sorted(value)[:max_items]:
            item = value.get(key)
            if isinstance(item, (dict, list)):
                shaped[str(key)] = _bounded_json_shape(item, depth + 1, max_depth, max_items)
            elif isinstance(item, str):
                shaped[str(key)] = item[:120]
            elif isinstance(item, (int, float, bool)) or item is None:
                shaped[str(key)] = item
        return shaped
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "sample": [_bounded_json_shape(item, depth + 1, max_depth, max_items) for item in value[: min(len(value), 3)]],
        }
    if isinstance(value, str):
        return value[:120]
    return value


def _nested_get(value: Mapping[str, Any], path: list[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
