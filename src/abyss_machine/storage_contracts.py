from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CACHE_ENV_ROUTE_KEYS = (
    "XDG_CACHE_HOME",
    "HF_HOME",
    "HUGGINGFACE_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "PIP_CACHE_DIR",
    "TORCH_HOME",
    "TORCHINDUCTOR_CACHE_DIR",
    "TRITON_CACHE_DIR",
    "NLTK_DATA",
    "SYCL_CACHE_DIR",
    "SYCL_CACHE_PERSISTENT",
    "TMPDIR",
    "ABYSS_OPENVINO_CACHE_DIR",
    "PLAYWRIGHT_BROWSERS_PATH",
    "PUPPETEER_CACHE_DIR",
)

PRESSURE_CANDIDATE_CATEGORIES = {
    "cleanup_candidate",
    "rebuildable_cache",
    "redownloadable_heavy",
    "package_cache",
    "stale_archive_candidate",
    "migrate_not_delete",
}

VALID_WRITE_KINDS = {"model-cache", "cache", "runtime", "benchmark", "container", "tmp", "artifact"}


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def is_relative_to_path(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def parse_policy_env_lines(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def policy_env_document(
    path: Path,
    *,
    exists: bool,
    lines: list[str],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": exists,
        "errors": errors,
        "values": parse_policy_env_lines(lines),
    }


def policy_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    path: Path,
    exists: bool,
    document: dict[str, Any] | None,
    load_error: str | None,
    env: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "storage_policy_read_v1"),
        "version": version,
        "generated_at": generated_at,
        "path": str(path),
        "exists": exists,
        "ok": document is not None,
        "load_error": load_error,
        "document": document if document is not None else {},
        "env": env,
    }


def hook_stage_definitions() -> list[dict[str, Any]]:
    return [
        {
            "stage": "pre_large_write",
            "purpose": "Gate or annotate large downloads, conversions, benchmark artifacts, and generated runtime writes.",
        },
        {
            "stage": "post_large_write",
            "purpose": "Record completed large writes and route evidence after the artifact exists.",
        },
        {
            "stage": "pre_runtime_create",
            "purpose": "Gate host-owned Python, container, browser, OpenVINO, or tool runtime creation.",
        },
        {
            "stage": "post_runtime_create",
            "purpose": "Record runtime creation results and update future bridge evidence.",
        },
        {
            "stage": "pre_cache_cleanup",
            "purpose": "Gate destructive cleanup of generated caches before deletion.",
        },
        {
            "stage": "post_cache_cleanup",
            "purpose": "Record generated-cache cleanup results.",
        },
        {
            "stage": "pre_podman_migration",
            "purpose": "Gate rootless Podman graphroot migration while containers must be stopped.",
        },
        {
            "stage": "post_podman_migration",
            "purpose": "Record Podman storage migration evidence.",
        },
        {
            "stage": "process_snapshot",
            "purpose": "Attach process snapshot events to storage or workload investigations.",
        },
    ]


def hook_stage_names() -> set[str]:
    return {str(item["stage"]) for item in hook_stage_definitions()}


def hook_directories(stage: str | None, *, etc_dir: Path, srv_dir: Path) -> list[Path]:
    if stage:
        return [etc_dir / f"{stage}.d", srv_dir / f"{stage}.d"]
    return [etc_dir, srv_dir]


def hooks_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    selected_stage: str | None,
    root_dirs: list[Path],
    directories: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    stages = hook_stage_definitions()
    names = hook_stage_names()
    selected_stages = [selected_stage] if selected_stage else [str(item["stage"]) for item in stages]
    invalid = [item for item in selected_stages if item not in names]
    executable_count = sum(
        int(directory.get("executable_count") or 0)
        for directory_list in directories.values()
        for directory in directory_list
    )
    return {
        "schema": _schema(schema_prefix, "storage_hooks_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": not invalid,
        "invalid_stages": invalid,
        "root_dirs": [str(path) for path in root_dirs],
        "stages": stages,
        "directories": directories,
        "summary": {
            "stages": len(stages),
            "selected_stages": len(selected_stages) - len(invalid),
            "executable_hooks": executable_count,
        },
        "contract": {
            "ordering": "lexical within /etc stage dir, then lexical within /srv stage dir",
            "stdin": "JSON payload",
            "stdout": "optional JSON or text evidence",
            "enforcement": "non-zero hook exit blocks only when run with --enforce",
        },
    }


def cache_env_routes(env: dict[str, str]) -> dict[str, str]:
    return {key: env[key] for key in CACHE_ENV_ROUTE_KEYS if key in env}


def inventory_drift(items: list[dict[str, Any]], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(previous, dict):
        return {"baseline": "created", "new": [], "grown": [], "shrunk": [], "missing": []}
    previous_items = {
        str(item.get("id") or item.get("path")): item
        for item in previous.get("items", [])
        if isinstance(item, dict)
    }
    current_ids = {str(item.get("id") or item.get("path")) for item in items}
    new_items = []
    grown = []
    shrunk = []
    for item in items:
        key = str(item.get("id") or item.get("path"))
        prev = previous_items.get(key)
        if not prev:
            if item.get("exists"):
                new_items.append({"id": key, "path": item.get("path"), "size_bytes": item.get("size_bytes")})
            continue
        current_size = item.get("size_bytes")
        previous_size = prev.get("size_bytes")
        if isinstance(current_size, int) and isinstance(previous_size, int):
            delta = current_size - previous_size
            threshold = max(512 * 1024 * 1024, int(previous_size * 0.2))
            if delta >= threshold:
                grown.append({"id": key, "path": item.get("path"), "delta_bytes": delta, "size_bytes": current_size})
            elif delta <= -threshold:
                shrunk.append({"id": key, "path": item.get("path"), "delta_bytes": delta, "size_bytes": current_size})
    missing = [
        {"id": key, "path": prev.get("path"), "previous_size_bytes": prev.get("size_bytes")}
        for key, prev in previous_items.items()
        if key not in current_ids
    ]
    return {"baseline": "compared", "new": new_items, "grown": grown, "shrunk": shrunk, "missing": missing}


def policy_thresholds(policy: dict[str, Any]) -> dict[str, float]:
    document = policy.get("document", {}) if isinstance(policy.get("document"), dict) else {}
    system_root = document.get("system_root", {}) if isinstance(document.get("system_root"), dict) else {}
    return {
        "system_warning_percent": float(system_root.get("warning_threshold_percent", 80)),
        "system_critical_percent": float(system_root.get("critical_threshold_percent", 90)),
        "srv_warning_percent": float(document.get("srv_warning_threshold_percent", 85)),
        "srv_critical_percent": float(document.get("srv_critical_threshold_percent", 92)),
        "watch_margin_percent": float(document.get("watch_margin_percent", 5)),
    }


def pressure_class(used_percent: Any, warning: float, critical: float, watch_margin: float) -> str:
    if not isinstance(used_percent, (int, float)):
        return "unknown"
    if used_percent >= critical:
        return "critical"
    if used_percent >= warning:
        return "warning"
    if used_percent >= max(0.0, warning - watch_margin):
        return "watch"
    return "green"


def threshold_bytes(usage: dict[str, Any], threshold_percent: float) -> dict[str, Any]:
    total = usage.get("total_bytes")
    used = usage.get("used_bytes")
    if not isinstance(total, int) or not isinstance(used, int):
        return {"bytes_to_threshold": None, "bytes_over_threshold": None}
    threshold_value = int(float(total) * (threshold_percent / 100.0))
    return {
        "threshold_bytes": threshold_value,
        "bytes_to_threshold": max(0, threshold_value - used),
        "bytes_over_threshold": max(0, used - threshold_value),
    }


def item_scope(item: dict[str, Any], *, abyss_machine_root: Path) -> str:
    tags = {str(tag) for tag in item.get("tags", []) if isinstance(tag, str)}
    path_text = str(item.get("path") or "")
    path = Path(path_text) if path_text else Path("/")
    if "work" in tags or path_text.startswith("/srv/work/") or path_text == "/srv/work":
        return "work"
    if "srv" in tags or path_text.startswith("/srv/") or is_relative_to_path(path, abyss_machine_root):
        return "srv"
    if "root" in tags:
        return "root"
    if path_text.startswith("/home/") or path_text.startswith("/var/") or path_text.startswith("/etc/") or path_text.startswith("/usr/"):
        return "root"
    return "unknown"


def item_size_bytes(item: dict[str, Any]) -> int:
    size = item.get("size_bytes")
    return int(size) if isinstance(size, int) and size > 0 else 0


def item_is_pressure_candidate(item: dict[str, Any]) -> bool:
    return bool(item.get("exists") and item.get("category") in PRESSURE_CANDIDATE_CATEGORIES)


def pressure_recommendations(
    candidates: list[dict[str, Any]],
    root_class: str,
    srv_class: str,
    *,
    abyss_machine_root: Path,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if root_class in {"watch", "warning", "critical"}:
        root_candidates = [item for item in candidates if item_scope(item, abyss_machine_root=abyss_machine_root) == "root"]
        for item in sorted(root_candidates, key=item_size_bytes, reverse=True)[:5]:
            recommendations.append({
                "priority": 1 if root_class in {"warning", "critical"} else 2,
                "action": "review_root_pressure_candidate",
                "id": item.get("id"),
                "path": item.get("path"),
                "category": item.get("category"),
                "size_bytes": item.get("size_bytes"),
                "reason": item.get("reason"),
            })
    if srv_class in {"watch", "warning", "critical"}:
        srv_candidates = [item for item in candidates if item_scope(item, abyss_machine_root=abyss_machine_root) == "srv"]
        for item in sorted(srv_candidates, key=item_size_bytes, reverse=True)[:5]:
            recommendations.append({
                "priority": 2,
                "action": "review_srv_pressure_valve",
                "id": item.get("id"),
                "path": item.get("path"),
                "category": item.get("category"),
                "size_bytes": item.get("size_bytes"),
                "reason": item.get("reason"),
            })
    if not recommendations:
        recommendations.append({
            "priority": 3,
            "action": "keep_monitoring",
            "reason": "No filesystem crossed a warning threshold; keep inventory/pressure facts current before large writes.",
        })
    recommendations.append({
        "priority": 9,
        "action": "generate_cleanup_plan_before_deletion",
        "command": "abyss-machine storage cleanup-plan --json",
        "reason": "Pressure facts do not authorize deletion; cleanup-plan adds process guard and hook context.",
    })
    return recommendations


def cleanup_action_for_item(
    item: dict[str, Any],
    *,
    guard_by_path: dict[str, dict[str, Any]],
    abyss_machine_root: Path,
) -> dict[str, Any]:
    category = str(item.get("category") or "unknown")
    path = str(item.get("path") or "")
    scope = item_scope(item, abyss_machine_root=abyss_machine_root)
    guard = guard_by_path.get(path, {"status": "not_checked", "active": None})
    action_type = "manual_review"
    operator_steps: list[str] = []
    consequence = "Requires explicit operator decision."
    if category == "package_cache":
        action_type = "package_manager_clean"
        consequence = "Package metadata/cache will be redownloaded when needed."
        if item.get("id") == "var_cache_libdnf5":
            operator_steps = ["pkexec dnf5 clean all"]
        else:
            operator_steps = ["review PackageKit cache through system package tools; do not rm blindly"]
    elif category == "cleanup_candidate":
        action_type = "age_based_generated_temp_cleanup"
        consequence = "Old generated temporary files disappear; active outputs must remain protected by process guard."
        operator_steps = [f"find {path} -mindepth 1 -mtime +7 -print"]
    elif category == "rebuildable_cache":
        action_type = "rebuildable_cache_pressure_valve"
        consequence = "First run after cleanup may be slower while compile/cache artifacts are rebuilt."
        if item.get("id") == "home_npm_cache":
            operator_steps = ["npm cache verify", "npm cache clean --force"]
        else:
            operator_steps = [f"review cache path after guard is clear: {path}"]
    elif category == "redownloadable_heavy":
        action_type = "redownloadable_heavy_pressure_valve"
        consequence = "Network/offline cost: assets may need to be downloaded again."
        operator_steps = [f"review large cache path after guard is clear: {path}"]
    elif category == "stale_archive_candidate":
        action_type = "operator_archive_review"
        consequence = "Could contain unique user/project state; review before move/delete."
        operator_steps = [f"review archive candidate manually: {path}"]
    elif category == "migrate_not_delete":
        action_type = "migrate_not_delete"
        consequence = "Reclaims root pressure only after a direct migration, never by deletion."
        operator_steps = ["abyss-machine storage podman-preflight --json"]
    blocked_reasons: list[str] = []
    if scope == "work":
        blocked_reasons.append("work_path_protected")
    if bool(guard.get("active")):
        blocked_reasons.append("active_process_reference")
    if category == "migrate_not_delete":
        blocked_reasons.append("migration_required_not_cleanup")
    readiness = "blocked" if blocked_reasons else "operator_review_ready"
    return {
        "id": item.get("id"),
        "path": path,
        "scope": scope,
        "category": category,
        "action_type": action_type,
        "readiness": readiness,
        "blocked_reasons": blocked_reasons,
        "estimated_bytes": item.get("size_bytes"),
        "measured": item.get("measured"),
        "confidence": item.get("confidence"),
        "reclaimability": item.get("reclaimability"),
        "disposition": item.get("disposition"),
        "safe_automatic_cleanup": False,
        "guard": guard,
        "operator_steps": operator_steps,
        "consequence": consequence,
        "reason": item.get("reason"),
        "requires": [
            "explicit_operator_action",
            "pre_cache_cleanup_hook_before_destructive_cleanup",
            "post_cache_cleanup_hook_after_destructive_cleanup",
        ],
    }


def default_protected_roots(*, abyss_machine_root: Path, abyss_stack_user_source_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": "/srv/AbyssOS",
            "owner": "abyss_os_project",
            "status": "protected_read_only",
            "reason": "Abyss OS project material. Host storage automation may read bridge evidence but must not write or clean here.",
        },
        {
            "path": "/srv/AbyssOS/abyss-stack",
            "owner": "abyss_stack",
            "status": "protected_read_only",
            "reason": "Stack repository/model material under reformation; host layer must not mutate it.",
        },
        {
            "path": "/srv/abyss-stack",
            "owner": "abyss_stack",
            "status": "protected_read_only",
            "reason": "Stack/service material; host layer must not mutate it.",
        },
        {
            "path": str(abyss_stack_user_source_root),
            "owner": "abyss_stack",
            "status": "protected_read_only",
            "reason": "User source repository; host layer must not mutate it.",
        },
        {
            "path": "/srv/GAMES",
            "owner": "operator_games",
            "status": "protected_operator_owned",
            "reason": "Operator-owned game library. Never a machine cleanup/write target.",
        },
        {
            "path": "/srv/games",
            "owner": "operator_games",
            "status": "protected_operator_owned",
            "reason": "Operator-owned game library. Never a machine cleanup/write target.",
        },
        {
            "path": "/srv/work",
            "owner": "operator_work",
            "status": "protected_work_owned",
            "reason": "Freelance/work projects. Machine-owned data must not be routed here.",
        },
        {
            "path": "/work",
            "owner": "operator_work",
            "status": "protected_work_owned",
            "reason": "Work mount/path. Machine-owned data must not be routed here.",
        },
    ]


def protected_roots(policy: dict[str, Any], defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    document = policy.get("document", {}) if isinstance(policy.get("document"), dict) else {}
    configured = document.get("protected_roots", []) if isinstance(document.get("protected_roots"), list) else []
    roots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*defaults, *configured]:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path = str(item["path"])
        if path in seen:
            continue
        seen.add(path)
        roots.append({
            "path": path,
            "owner": item.get("owner") or "unknown",
            "status": item.get("status") or "protected",
            "reason": item.get("reason") or "Protected by storage policy.",
        })
    return roots


def path_protection(path: Path, *, abyss_machine_root: Path, protected_roots: list[dict[str, Any]]) -> dict[str, Any]:
    path_text = str(path)
    if is_relative_to_path(path, abyss_machine_root):
        return {
            "class": "host_owned_allowed",
            "decision": "allow_candidate",
            "owner": "abyss_machine",
            "matched_root": str(abyss_machine_root),
            "reason": "Host-owned machine data root.",
        }
    for root in protected_roots:
        root_path = Path(str(root["path"]))
        if path_text == str(root_path) or is_relative_to_path(path, root_path):
            return {
                "class": str(root.get("status") or "protected"),
                "decision": "deny",
                "owner": root.get("owner"),
                "matched_root": str(root_path),
                "reason": root.get("reason"),
            }
    if path_text == "/srv" or is_relative_to_path(path, Path("/srv")):
        return {
            "class": "srv_unknown_protected",
            "decision": "deny",
            "owner": "unknown_srv_owner",
            "matched_root": "/srv",
            "reason": "Unknown /srv paths are protected unless explicitly allowlisted as /srv/abyss-machine.",
        }
    if path_text == "/":
        return {
            "class": "system_root",
            "decision": "reroute_for_large_generated_data",
            "owner": "system",
            "matched_root": "/",
            "reason": "System root is reserved for OS, packages, configs and compact state.",
        }
    if path_text.startswith("/home/") or path_text.startswith("/var/") or path_text.startswith("/tmp") or path_text.startswith("/usr/"):
        return {
            "class": "system_root",
            "decision": "reroute_for_large_generated_data",
            "owner": "system_or_user",
            "matched_root": "/",
            "reason": "Large generated machine-owned data should be routed to /srv/abyss-machine instead.",
        }
    return {
        "class": "unknown",
        "decision": "deny",
        "owner": "unknown",
        "matched_root": None,
        "reason": "Unknown target is not allowlisted for machine-owned writes.",
    }


def preflight_recommended_base(kind: str, *, routes: dict[str, Path]) -> Path:
    return routes.get(kind, routes["artifact"])


def preflight_recommended_target(kind: str, requested: Path, *, routes: dict[str, Path]) -> str:
    base = preflight_recommended_base(kind, routes=routes)
    name = requested.name if requested.name not in {"", ".", "/"} else kind
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or kind
    return str(base / clean)


def write_preflight_decision(
    *,
    kind: str,
    requested_bytes: int,
    protection: dict[str, Any],
    pressure_summary: dict[str, Any],
    target_usage: dict[str, Any],
    recommended_usage: dict[str, Any],
    large_write_threshold: int,
    min_free_after: int,
) -> dict[str, Any]:
    free_after = (
        int(target_usage.get("free_bytes") or 0) - requested_bytes
        if isinstance(target_usage.get("free_bytes"), int)
        else None
    )
    recommended_free_after = (
        int(recommended_usage.get("free_bytes") or 0) - requested_bytes
        if isinstance(recommended_usage.get("free_bytes"), int)
        else None
    )
    reasons: list[str] = []
    decision = "allow"
    if kind not in VALID_WRITE_KINDS:
        decision = "deny"
        reasons.append("invalid_kind")
    elif protection.get("decision") == "deny":
        decision = "deny"
        reasons.append("protected_or_unknown_target")
    elif protection.get("class") == "system_root" and requested_bytes >= large_write_threshold:
        decision = "reroute"
        reasons.append("large_generated_write_on_system_root")
    elif pressure_summary.get("root_pressure_class") in {"watch", "warning", "critical"} and protection.get("class") == "system_root":
        decision = "reroute"
        reasons.append("system_root_under_pressure")
    elif free_after is not None and free_after < min_free_after:
        decision = "cleanup_first"
        reasons.append("target_free_space_after_write_below_policy")
    elif protection.get("class") != "host_owned_allowed":
        decision = "reroute"
        reasons.append("target_not_host_owned_large_root")
    if decision in {"reroute", "cleanup_first"} and recommended_free_after is not None and recommended_free_after < min_free_after:
        decision = "cleanup_first"
        reasons.append("recommended_route_needs_cleanup_first")
    return {
        "decision": decision,
        "reasons": reasons or ["target_matches_policy"],
        "free_after_bytes": free_after,
        "recommended_free_after_bytes": recommended_free_after,
    }


def apply_find_action(cleanup: dict[str, Any], action_id: str) -> dict[str, Any] | None:
    for action in cleanup.get("actions", []) if isinstance(cleanup.get("actions"), list) else []:
        if isinstance(action, dict) and str(action.get("id")) == action_id:
            return action
    return None


def apply_dry_run_result(action: dict[str, Any], *, age_days: float, abyss_machine_tmp_root: Path) -> dict[str, Any]:
    action_type = str(action.get("action_type") or "")
    action_id = str(action.get("id") or "")
    path = str(action.get("path") or "")
    if action_type == "package_manager_clean" and action_id == "var_cache_libdnf5":
        return {"would_execute": [["dnf5", "clean", "all"]], "requires_root": True}
    if action_type == "rebuildable_cache_pressure_valve" and action_id == "home_npm_cache":
        return {"would_execute": [["npm", "cache", "verify"], ["npm", "cache", "clean", "--force"]], "requires_root": False}
    if action_type == "age_based_generated_temp_cleanup" and is_relative_to_path(Path(path), abyss_machine_tmp_root):
        return {"would_scan": path, "would_remove": "files older than age_days and empty old directories only", "age_days": age_days}
    return {"manual_review_only": True, "reason": "This action type or id is not allowlisted for automatic apply."}


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    storage_state_root: Path,
    latest_path: Path,
    index_path: Path,
    policy_path: Path,
    policy_env_path: Path,
    hooks_etc_dir: Path,
    hooks_srv_dir: Path,
    abyss_machine_root: Path,
    cache_root: Path,
    ai_cache_root: Path,
    runtime_root: Path,
    storage_root: Path,
    tmp_root: Path,
    process_paths: dict[str, Any],
    podman_preflight_latest_path: Path,
    podman_preflight_root: Path,
    inventory_latest_path: Path,
    inventory_root: Path,
    pressure_latest_path: Path,
    pressure_root: Path,
    cleanup_plan_latest_path: Path,
    cleanup_plan_root: Path,
    monitor_latest_path: Path,
    monitor_root: Path,
    write_preflight_latest_path: Path,
    write_preflight_root: Path,
    apply_latest_path: Path,
    apply_root: Path,
    protected_roots: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "storage_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(storage_state_root),
        "latest": str(latest_path),
        "index": str(index_path),
        "policy": str(policy_path),
        "policy_env": str(policy_env_path),
        "hooks": {
            "etc": str(hooks_etc_dir),
            "srv": str(hooks_srv_dir),
        },
        "large_roots": {
            "machine": str(abyss_machine_root),
            "cache": str(cache_root),
            "ai_cache": str(ai_cache_root),
            "runtime": str(runtime_root),
            "storage": str(storage_root),
            "tmp": str(tmp_root),
        },
        "processes": process_paths,
        "podman_preflight": {
            "latest": str(podman_preflight_latest_path),
            "daily_glob": str(podman_preflight_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine storage podman-preflight --json",
        },
        "inventory": {
            "latest": str(inventory_latest_path),
            "daily_glob": str(inventory_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine storage inventory --json",
            "full_command": "abyss-machine storage inventory --full --json",
        },
        "pressure": {
            "latest": str(pressure_latest_path),
            "daily_glob": str(pressure_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine storage pressure --json",
            "refresh_command": "abyss-machine storage pressure --refresh-inventory --json",
        },
        "cleanup_plan": {
            "latest": str(cleanup_plan_latest_path),
            "daily_glob": str(cleanup_plan_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine storage cleanup-plan --json",
            "refresh_command": "abyss-machine storage cleanup-plan --refresh-inventory --json",
        },
        "monitor": {
            "latest": str(monitor_latest_path),
            "daily_glob": str(monitor_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine storage monitor --json",
            "timer": "abyss-storage-monitor.timer",
            "service": "abyss-storage-monitor.service",
            "scope": "user",
        },
        "write_preflight": {
            "latest": str(write_preflight_latest_path),
            "daily_glob": str(write_preflight_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine storage write-preflight --kind KIND --bytes BYTES --target PATH --json",
        },
        "apply": {
            "latest": str(apply_latest_path),
            "daily_glob": str(apply_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "dry_run_command": "abyss-machine storage apply --action-id ID --dry-run --json",
            "confirm_command": "abyss-machine storage apply --action-id ID --confirm --json",
        },
        "protected_roots": protected_roots,
    }
