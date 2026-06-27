from __future__ import annotations

import datetime as dt
from typing import Any, Mapping


def normalize_scope(scope: str | None) -> str:
    return scope if scope in {"now", "today", "session"} else "now"


def normalize_limit(limit: int | str | None) -> int:
    try:
        value = int(limit) if limit is not None else 8
    except (TypeError, ValueError):
        value = 8
    return max(1, value)


def cache_key(scope: str | None, limit: int | str | None, refresh: bool) -> str:
    return f"{normalize_scope(scope)}:{normalize_limit(limit)}:{bool(refresh)}"


def semantic_maintenance_thresholds(config: Mapping[str, Any]) -> dict[str, float | int]:
    maintain = config.get("maintain") if isinstance(config.get("maintain"), Mapping) else {}
    return {
        "min_delta_chunks": int(maintain.get("min_delta_chunks") or 128),
        "max_stale_minutes": float(maintain.get("max_stale_minutes") or 90),
    }


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _summary(data: Mapping[str, Any]) -> dict[str, Any]:
    return data.get("summary") if isinstance(data.get("summary"), dict) else {}


def _summary_or_none(data: Mapping[str, Any]) -> dict[str, Any] | None:
    return data.get("summary") if isinstance(data.get("summary"), dict) else None


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def record_time_value(record: Mapping[str, Any]) -> dt.datetime | None:
    return parse_time(record.get("observed_at") or record.get("start_at") or record.get("generated_at"))


def recent_episodes_document(
    items: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    *,
    limit: int | str | None = 8,
    scope: str = "now",
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    final_limit = normalize_limit(limit)
    final_scope = scope if scope in {"now", "today"} else "now"
    now_local = now or dt.datetime.now(dt.timezone.utc).astimezone()
    records: list[dict[str, Any]] = []
    for item in items:
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        if not record:
            continue
        timestamp = record_time_value(record)
        if final_scope == "today" and timestamp and timestamp.astimezone().date() != now_local.date():
            continue
        records.append(record)
    records.sort(key=lambda item: (item.get("end_at") or item.get("start_at") or "", item.get("episode_id") or ""), reverse=True)
    compact = [
        {
            "episode_id": item.get("episode_id"),
            "category": item.get("category"),
            "severity": item.get("severity"),
            "title": item.get("title"),
            "start_at": item.get("start_at"),
            "end_at": item.get("end_at"),
            "event_count": item.get("event_count"),
        }
        for item in records[:final_limit]
    ]
    return {
        "items": compact,
        "summary": {
            "returned": len(compact),
            "available": len(records),
            "parse_errors": len(parse_errors),
        },
    }


def _commands(commands: Mapping[str, str]) -> dict[str, str]:
    return {
        "quality": commands.get("quality", "abyss-machine nervous quality-audit --json"),
        "quality_refresh": commands.get("quality_refresh", "abyss-machine nervous quality-audit --refresh --json"),
        "quality_refresh_index_operator": commands.get("quality_refresh_index_operator", "abyss-machine nervous quality-audit --refresh --refresh-index --json"),
        "quality_recheck": commands.get("quality_recheck", "abyss-machine nervous quality-audit --json"),
        "search": commands.get("search", "abyss-machine nervous search --query TEXT --json"),
        "rerank": commands.get("rerank", "abyss-machine nervous rerank --query TEXT --json"),
        "hybrid_recall": commands.get("hybrid_recall", "abyss-machine nervous recall --mode hybrid --query TEXT --json"),
        "semantic_status": commands.get("semantic_status", "abyss-machine nervous semantic-status --json"),
        "semantic_maintain_review": commands.get("semantic_maintain_review", "abyss-machine nervous semantic-maintain --dry-run --json"),
        "semantic_maintain_retry": commands.get("semantic_maintain_retry", "abyss-machine nervous semantic-maintain --json"),
    }


def brief_document(
    *,
    scope: str,
    quality: Mapping[str, Any],
    privacy: Mapping[str, Any],
    capture: Mapping[str, Any],
    index_status: Mapping[str, Any],
    semantic_status: Mapping[str, Any],
    semantic_maintenance: Mapping[str, Any],
    derived_refresh: Mapping[str, Any],
    synthesis: Mapping[str, Any],
    observability: Mapping[str, Any],
    memory: Mapping[str, Any],
    storage: Mapping[str, Any],
    processes: Mapping[str, Any],
    resource: Mapping[str, Any],
    recent_episodes: Mapping[str, Any],
    commands: Mapping[str, str],
    latest_path: str,
    daily_glob: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    scope = normalize_scope(scope)
    command_map = _commands(commands)
    quality_summary = _summary(quality)
    quality_clean = int(quality_summary.get("fails") or 0) == 0 and int(quality_summary.get("warnings") or 0) == 0
    index_fresh = _nested_get(index_status, ["freshness", "stale"]) is False
    privacy_open = not bool(privacy.get("global_pause")) and not bool(privacy.get("private_mode"))
    semantic_ready = bool(semantic_status.get("ready"))
    semantic_stale = bool(_nested_get(semantic_status, ["freshness", "stale"]))
    semantic_maintenance_needed = bool(semantic_maintenance.get("needed"))

    gaps: list[dict[str, Any]] = []
    if not quality_clean:
        gaps.append({"layer": "quality", "reason": "quality audit has non-ok checks", "summary": quality_summary})
    if not index_fresh:
        gaps.append({"layer": "index", "reason": "FTS index is stale or freshness is unknown", "freshness": index_status.get("freshness")})
    if not privacy_open:
        gaps.append({"layer": "privacy", "reason": "global pause or private mode is active", "privacy": {"global_pause": privacy.get("global_pause"), "private_mode": privacy.get("private_mode")}})
    if not semantic_ready:
        gaps.append({"layer": "semantic", "reason": "semantic index is not ready", "warnings": semantic_status.get("warnings")})
    elif semantic_maintenance_needed:
        gaps.append({
            "layer": "semantic",
            "reason": "semantic sidecar exceeds maintenance thresholds",
            "freshness": semantic_status.get("freshness"),
            "maintenance": dict(semantic_maintenance),
        })
    if not derived_refresh.get("ok"):
        gaps.append({"layer": "automation", "reason": "passive chronicle derived-refresh contract is incomplete", "status": dict(derived_refresh)})

    readiness_status = "ready" if quality_clean and index_fresh and privacy_open else "degraded"
    next_actions: list[dict[str, str]] = []
    if not index_fresh or semantic_maintenance_needed or not semantic_ready:
        next_actions.append({
            "action": "semantic_maintain",
            "command": command_map["semantic_maintain_review"],
            "retry_command": command_map["semantic_maintain_retry"],
            "reason": "review stale SQLite/FTS and embedding sidecar drift through a dry-run resource gate before any maintainer retry",
        })
    if not quality_clean and index_fresh:
        next_actions.append({
            "action": "quality_refresh",
            "command": command_map["quality_refresh"],
            "reason": "refresh deterministic derived layers only; index refresh remains routed through semantic maintenance review",
        })
    elif not quality_clean:
        next_actions.append({
            "action": "quality_recheck",
            "command": command_map["quality_recheck"],
            "reason": "recheck quality after resource-gated semantic maintenance refreshes the source index",
        })
    if not derived_refresh.get("ok"):
        next_actions.append({
            "action": "automation_repair",
            "command": "systemctl --user daemon-reload && systemctl --user start abyss-nervous-passive-chronicle.service",
            "reason": "verify passive chronicle triggers derived refresh",
        })

    return {
        "schema": f"{schema_prefix}_nervous_brief_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": readiness_status == "ready",
        "scope": scope,
        "readiness": {
            "status": readiness_status,
            "quality_clean": quality_clean,
            "index_fresh": index_fresh,
            "privacy_open": privacy_open,
            "semantic_ready": semantic_ready,
            "semantic_stale": semantic_stale,
            "semantic_maintenance_needed": semantic_maintenance_needed,
            "derived_refresh_ok": bool(derived_refresh.get("ok")),
        },
        "current": {
            "quality": quality_summary,
            "privacy": {"global_pause": privacy.get("global_pause"), "private_mode": privacy.get("private_mode")},
            "index": {
                "ready": index_status.get("ready"),
                "warnings": index_status.get("warnings"),
                "freshness": index_status.get("freshness"),
                "counts": index_status.get("counts"),
            },
            "semantic": {
                "ready": semantic_status.get("ready"),
                "warnings": semantic_status.get("warnings"),
                "freshness": semantic_status.get("freshness"),
                "maintenance": dict(semantic_maintenance),
                "counts": semantic_status.get("counts"),
            },
            "observability": {
                "timer": observability.get("timer"),
                "latest": observability.get("latest"),
            },
            "memory": _summary_or_none(memory),
            "storage": _summary_or_none(storage),
            "processes": _summary_or_none(processes),
            "resource": _summary_or_none(resource),
            "capture": {
                "ok": capture.get("ok"),
                "latest": capture.get("latest"),
                "browser_content_latest": capture.get("browser_content_latest"),
                "storage": capture.get("storage"),
            },
            "synthesis": {
                "ok": synthesis.get("ok"),
                "candidate_id": synthesis.get("candidate_id"),
                "scope": synthesis.get("scope"),
                "summary": synthesis.get("summary"),
            },
        },
        "recent_episodes": dict(recent_episodes),
        "gaps": gaps,
        "next_actions": next_actions,
        "commands": command_map,
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "model_used": False,
            "repo_mutation": False,
            "maintenance_review_before_retry": True,
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }
