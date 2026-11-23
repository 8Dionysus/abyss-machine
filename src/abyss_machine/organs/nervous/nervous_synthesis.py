from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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


def record_time_value(record: dict[str, Any]) -> dt.datetime | None:
    return parse_time(record.get("observed_at") or record.get("start_at") or record.get("generated_at"))


def record_ids(records: list[dict[str, Any]], key: str) -> set[str]:
    return {str(record.get(key)) for record in records if record.get(key)}


def severity_max(values: list[str]) -> str:
    ranks = {"info": 0, "notice": 1, "watch": 2, "warning": 3, "critical": 4}
    best = "info"
    for value in values:
        current = str(value or "info")
        if ranks.get(current, 0) > ranks.get(best, 0):
            best = current
    return best


def period_jsonl_path(root: Path, period: dict[str, Any]) -> Path:
    date_text = str(period.get("date") or dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y-%m-%d"))
    return root / date_text[:4] / date_text[5:7] / f"{date_text}.jsonl"


def select_period_episodes(
    episodes: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    *,
    scope: str,
    date_value: str | None = None,
    hour: int | None = None,
    now: dt.datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    scope = scope if scope in {"hourly", "daily"} else "daily"
    if date_value is None:
        times = [record_time_value(item) for item in episodes]
        times = [item for item in times if item is not None]
        basis = now or dt.datetime.now(dt.timezone.utc).astimezone()
        date_value = max(times).astimezone().strftime("%Y-%m-%d") if times else basis.strftime("%Y-%m-%d")
    selected = []
    for episode in episodes:
        start = record_time_value(episode)
        if start is None or start.astimezone().strftime("%Y-%m-%d") != date_value:
            continue
        if scope == "hourly" and hour is not None and start.astimezone().hour != hour:
            continue
        selected.append(episode)
    selected.sort(key=lambda item: (item.get("start_at") or "", item.get("episode_id") or ""))
    period = {
        "scope": scope,
        "date": date_value,
        "hour": hour if scope == "hourly" else None,
    }
    return selected, parse_errors, period


def select_events_for_episode_ids(
    episode_records: list[dict[str, Any]],
    event_records: list[dict[str, Any]],
    episode_ids: list[str],
) -> list[dict[str, Any]]:
    wanted_episode_ids = set(episode_ids)
    wanted_event_ids: set[str] = set()
    for record in episode_records:
        if str(record.get("episode_id") or "") not in wanted_episode_ids:
            continue
        if isinstance(record.get("event_ids"), list):
            wanted_event_ids.update(str(event_id) for event_id in record["event_ids"])
    events = [
        record for record in event_records
        if str(record.get("event_id") or "") in wanted_event_ids
    ]
    events.sort(key=lambda item: (item.get("observed_at") or "", item.get("event_id") or ""))
    return events


def records_from_items(items: list[dict[str, Any]], *, schema: str | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        record = item.get("record") if isinstance(item.get("record"), dict) else None
        if record is None:
            continue
        if schema is not None and record.get("schema") != schema:
            continue
        records.append(record)
    return records


def candidate_refused_result(
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_synthesis_candidate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; synthesis candidate was not built",
    }


def eval_refused_result(
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_eval_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; eval run did not touch recall, synthesis, or eval files",
    }


def eval_run_execution_plan(
    *,
    schema_prefix: str = "abyss_machine",
    recall_query: str = "thermal storage power nervous",
    recall_limit: int = 16,
    synthesis_scope: str = "daily",
) -> dict[str, Any]:
    scope = synthesis_scope if synthesis_scope in {"hourly", "daily"} else "daily"
    return {
        "schema": f"{schema_prefix}_nervous_eval_run_execution_plan_v1",
        "step_order": [
            "events_validation",
            "episodes_validation",
            "index_validation",
            "recall",
            "synthesis",
            "synthesis_validation",
        ],
        "events_validation": {"adapter": "nervous_events_validate", "write_latest": False},
        "episodes_validation": {"adapter": "nervous_episodes_validate", "write_latest": False},
        "index_validation": {"adapter": "nervous_index_validate", "write_latest": False},
        "recall": {
            "adapter": "nervous_recall_pack",
            "query": str(recall_query),
            "limit": int(recall_limit),
            "write_latest": True,
        },
        "synthesis": {
            "adapter": "nervous_synthesis_build",
            "scope": scope,
            "write_latest": True,
        },
        "synthesis_validation": {"adapter": "nervous_synthesis_validate", "write_latest": False},
        "policy": {
            "model_used": False,
            "local_only": True,
            "live_execution_at_cli_edge": True,
            "automatic_repo_write": False,
        },
    }


def paths_document(
    *,
    latest_path: str,
    hourly_glob: str,
    daily_jsonl_glob: str,
    daily_markdown_glob: str,
) -> dict[str, str]:
    return {
        "latest": latest_path,
        "hourly_glob": hourly_glob,
        "daily_jsonl_glob": daily_jsonl_glob,
        "daily_markdown_glob": daily_markdown_glob,
    }


def build_candidate(
    *,
    scope: str,
    period: dict[str, Any],
    episodes: list[dict[str, Any]],
    events: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    paths: dict[str, str],
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    scope = scope if scope in {"hourly", "daily"} else "daily"
    episode_ids = [str(item.get("episode_id")) for item in episodes if item.get("episode_id")]
    severities = [str(item.get("severity") or "info") for item in episodes + events]
    highest = severity_max(severities) if severities else "info"
    by_category = {
        category: sum(1 for item in episodes if item.get("category") == category)
        for category in sorted({str(item.get("category")) for item in episodes})
    }
    by_severity = {
        severity: sum(1 for item in episodes if item.get("severity") == severity)
        for severity in sorted({str(item.get("severity")) for item in episodes})
    }
    event_types = {
        event_type: sum(1 for item in events if item.get("event_type") == event_type)
        for event_type in sorted({str(item.get("event_type")) for item in events})
    }
    identity = json.dumps({"scope": scope, "period": period, "episode_ids": episode_ids}, ensure_ascii=False, sort_keys=True)
    candidate_id = "syn-" + hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:24]
    start_values = [item.get("start_at") for item in episodes if item.get("start_at")]
    end_values = [item.get("end_at") for item in episodes if item.get("end_at")]
    claims = [
        {
            "claim": f"{len(episodes)} episode records and {len(events)} event records are present for this {scope} period.",
            "confidence": "high" if episodes else "low",
            "supporting_episode_ids": episode_ids[:50],
            "supporting_event_ids": [str(item.get("event_id")) for item in events if item.get("event_id")][:50],
        },
        {
            "claim": f"The highest derived severity in this candidate is {highest}.",
            "confidence": "high" if severities else "low",
            "supporting_episode_ids": episode_ids[:50],
        },
    ]
    return {
        "schema": f"{schema_prefix}_nervous_synthesis_candidate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not parse_errors,
        "candidate_id": candidate_id,
        "scope": scope,
        "period": period,
        "window": {
            "start_at": min(start_values) if start_values else None,
            "end_at": max(end_values) if end_values else None,
        },
        "summary": {
            "episodes": len(episodes),
            "events": len(events),
            "highest_severity": highest,
            "by_category": by_category,
            "by_severity": by_severity,
            "event_types": event_types,
            "parse_errors": len(parse_errors),
        },
        "evidence": {
            "episodes": [
                {
                    "episode_id": item.get("episode_id"),
                    "title": item.get("title"),
                    "category": item.get("category"),
                    "severity": item.get("severity"),
                    "start_at": item.get("start_at"),
                    "end_at": item.get("end_at"),
                    "event_count": item.get("event_count"),
                    "event_ids": item.get("event_ids") if isinstance(item.get("event_ids"), list) else [],
                }
                for item in episodes
            ],
            "events_sample": [
                {
                    "event_id": item.get("event_id"),
                    "observed_at": item.get("observed_at"),
                    "event_type": item.get("event_type"),
                    "category": item.get("category"),
                    "severity": item.get("severity"),
                    "title": item.get("title"),
                }
                for item in events[:80]
            ],
        },
        "claims": claims,
        "review_candidates": [
            {
                "kind": "critical_severity_review",
                "reason": "derived critical severity present; operator may inspect supporting events",
                "episode_ids": [str(item.get("episode_id")) for item in episodes if item.get("severity") == "critical"],
            }
        ] if highest == "critical" else [],
        "policy": {
            "candidate_only": True,
            "model_used": False,
            "raw_private_content": False,
            "automatic_action": False,
            "automatic_repo_write": False,
        },
        "paths": paths,
        "parse_errors": parse_errors[:20],
    }


def build_candidate_from_items(
    *,
    episode_items: list[dict[str, Any]],
    episode_parse_errors: list[dict[str, Any]],
    event_items: list[dict[str, Any]],
    scope: str = "daily",
    date_value: str | None = None,
    hour: int | None = None,
    paths: dict[str, str],
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    episode_records = records_from_items(episode_items)
    event_records = records_from_items(event_items)
    selected_episodes, parse_errors, period = select_period_episodes(
        episode_records,
        episode_parse_errors,
        scope=scope,
        date_value=date_value,
        hour=hour,
    )
    episode_ids = [str(item.get("episode_id")) for item in selected_episodes if item.get("episode_id")]
    selected_events = select_events_for_episode_ids(episode_records, event_records, episode_ids)
    return build_candidate(
        scope=scope,
        period=period,
        episodes=selected_episodes,
        events=selected_events,
        parse_errors=parse_errors,
        paths=paths,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def write_paths(scope: str, period: dict[str, Any], *, hourly_root: Path, daily_root: Path) -> dict[str, Path]:
    root = hourly_root if scope == "hourly" else daily_root
    paths = {"period_jsonl": period_jsonl_path(root, period)}
    if scope == "daily":
        date_text = str(period.get("date") or dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y-%m-%d"))
        paths["daily_markdown"] = daily_root / date_text[:4] / date_text[5:7] / f"{date_text}.md"
    return paths


def with_write_results(
    candidate: dict[str, Any],
    *,
    write_paths: dict[str, Path | str],
    write_errors: list[Any],
) -> dict[str, Any]:
    data = dict(candidate)
    paths = dict(data.get("paths") if isinstance(data.get("paths"), dict) else {})
    for key, path in write_paths.items():
        paths[key] = str(path)
    data["paths"] = paths
    errors = [error for error in write_errors if error]
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
    return data


def markdown(candidate: dict[str, Any]) -> str:
    summary = candidate.get("summary") if isinstance(candidate.get("summary"), dict) else {}
    lines = [
        f"# Abyss Nervous {candidate.get('scope')} Synthesis {_nested_get(candidate, ['period', 'date'])}",
        "",
        f"- Candidate ID: `{candidate.get('candidate_id')}`",
        f"- Generated: `{candidate.get('generated_at')}`",
        f"- Episodes: `{summary.get('episodes')}`",
        f"- Events: `{summary.get('events')}`",
        f"- Highest severity: `{summary.get('highest_severity')}`",
        "",
        "## Categories",
        "",
    ]
    for category, count in (summary.get("by_category") or {}).items():
        lines.append(f"- `{category}`: {count}")
    lines.extend(["", "## Evidence Episodes", ""])
    for episode in candidate.get("evidence", {}).get("episodes", [])[:20]:
        lines.append(f"- `{episode.get('episode_id')}` {episode.get('title')} severity=`{episode.get('severity')}` events={episode.get('event_count')}")
    lines.extend(["", "## Claims", ""])
    for claim in candidate.get("claims", []):
        lines.append(f"- {claim.get('claim')} Confidence: `{claim.get('confidence')}`")
    lines.extend(["", "## Policy", "", "Candidate only. No model call. No automatic write to AoA or abyss-stack repositories.", ""])
    return "\n".join(lines)


def validate_records(
    *,
    latest: Any,
    latest_error: Any,
    episodes_latest: Any,
    candidate_items: list[dict[str, Any]],
    candidate_parse_errors: list[dict[str, Any]],
    episode_items: list[dict[str, Any]],
    event_items: list[dict[str, Any]],
    latest_path: str,
    validate_latest_path: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
        item: dict[str, Any] = {"level": level, "key": key, "message": message}
        if details is not None:
            item["details"] = details
        checks.append(item)

    add("ok" if isinstance(latest, dict) else "fail", "latest", "synthesis latest exists", {"path": latest_path, "error": latest_error})
    latest_candidate_id = str(latest.get("candidate_id") or "") if isinstance(latest, dict) else ""
    latest_generated_at = parse_time(latest.get("generated_at")) if isinstance(latest, dict) else None
    episodes_generated_at = parse_time(episodes_latest.get("generated_at")) if isinstance(episodes_latest, dict) else None
    latest_is_stale = bool(latest_generated_at and episodes_generated_at and latest_generated_at < episodes_generated_at)
    episode_ids = record_ids([item.get("record", {}) for item in episode_items], "episode_id")
    event_ids = record_ids([item.get("record", {}) for item in event_items], "event_id")
    missing_refs: list[dict[str, Any]] = []
    bad_records: list[dict[str, Any]] = []
    for item in candidate_items:
        record = item.get("record") if isinstance(item.get("record"), dict) else {}
        if record.get("schema") != f"{schema_prefix}_nervous_synthesis_candidate_v1":
            bad_records.append({"path": item.get("path"), "line": item.get("line"), "reason": "schema"})
        for key in ("candidate_id", "scope", "period", "summary", "evidence", "claims", "policy"):
            if key not in record:
                bad_records.append({"path": item.get("path"), "line": item.get("line"), "reason": f"missing:{key}"})
        policy = record.get("policy") if isinstance(record.get("policy"), dict) else {}
        if policy.get("raw_private_content") is not False or policy.get("automatic_repo_write") is not False:
            bad_records.append({"path": item.get("path"), "line": item.get("line"), "reason": "policy"})
        evidence = _nested_get(record, ["evidence", "episodes"]) or []
        enforce_current_refs = str(record.get("candidate_id") or "") == latest_candidate_id
        for episode in evidence:
            if enforce_current_refs and isinstance(episode, dict) and episode.get("episode_id") and str(episode.get("episode_id")) not in episode_ids:
                missing_refs.append({"candidate_id": record.get("candidate_id"), "episode_id": episode.get("episode_id")})
            if isinstance(episode, dict) and isinstance(episode.get("event_ids"), list):
                for event_id in episode["event_ids"]:
                    if enforce_current_refs and str(event_id) not in event_ids:
                        missing_refs.append({"candidate_id": record.get("candidate_id"), "event_id": event_id})
    add("ok" if not candidate_parse_errors else "fail", "jsonl_parse", "synthesis JSONL parses", {"parse_errors": candidate_parse_errors[:20], "parse_error_count": len(candidate_parse_errors)})
    add("ok" if not bad_records else "fail", "candidate_shape", "synthesis candidates have required shape and policy", {"bad_records": bad_records[:20], "bad_count": len(bad_records)})
    if missing_refs and latest_is_stale:
        add("warn", "evidence_refs_stale", "latest synthesis references previous episode/event ids after a newer derived rebuild; refresh synthesis to update candidate evidence", {
            "missing_refs": missing_refs[:20],
            "missing_count": len(missing_refs),
            "latest_generated_at": latest_generated_at.isoformat() if latest_generated_at else None,
            "episodes_generated_at": episodes_generated_at.isoformat() if episodes_generated_at else None,
            "repair_command": "abyss-machine nervous synthesis-build --scope daily --json",
        })
    else:
        add("ok" if not missing_refs else "fail", "evidence_refs", "synthesis evidence references existing episodes/events", {"missing_refs": missing_refs[:20], "missing_count": len(missing_refs)})
    add("ok" if candidate_items else "warn", "candidate_count", "synthesis candidates exist", {"candidates": len(candidate_items)})
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_synthesis_validate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "checks": checks,
        "summary": {
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
            "candidates": len(candidate_items),
            "parse_errors": len(candidate_parse_errors),
        },
        "paths": {
            "latest": latest_path,
            "validate_latest": validate_latest_path,
        },
    }


def eval_check(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["details"] = details
    return item


def eval_run_document(
    *,
    events_validation: dict[str, Any],
    episodes_validation: dict[str, Any],
    index_validation: dict[str, Any],
    recall: dict[str, Any],
    synthesis: dict[str, Any],
    synthesis_validation: dict[str, Any],
    latest_path: str,
    daily_glob: str,
    recall_latest_path: str,
    synthesis_latest_path: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    checks = [
        eval_check(
            "ok" if events_validation.get("ok") else "fail",
            "events_validate",
            "event layer validates",
            events_validation.get("summary") if isinstance(events_validation.get("summary"), dict) else None,
        ),
        eval_check(
            "ok" if episodes_validation.get("ok") else "fail",
            "episodes_validate",
            "episode layer validates",
            episodes_validation.get("summary") if isinstance(episodes_validation.get("summary"), dict) else None,
        ),
        eval_check(
            "ok" if index_validation.get("ok") else "fail",
            "index_validate",
            "index validates",
            index_validation.get("summary") if isinstance(index_validation.get("summary"), dict) else None,
        ),
        eval_check(
            "ok" if recall.get("ok") and _nested_get(recall, ["summary", "evidence_items"]) else "fail",
            "recall_pack",
            "recall pack has evidence",
            recall.get("summary") if isinstance(recall.get("summary"), dict) else None,
        ),
        eval_check(
            "ok" if synthesis.get("ok") and _nested_get(synthesis, ["summary", "episodes"]) is not None else "fail",
            "synthesis_build",
            "synthesis candidate builds",
            synthesis.get("summary") if isinstance(synthesis.get("summary"), dict) else None,
        ),
        eval_check(
            "ok" if synthesis_validation.get("ok") else "fail",
            "synthesis_validate",
            "synthesis candidate validates",
            synthesis_validation.get("summary") if isinstance(synthesis_validation.get("summary"), dict) else None,
        ),
    ]
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_eval_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "checks": checks,
        "artifacts": {
            "recall_pack": {
                "ok": recall.get("ok"),
                "pack_id": recall.get("pack_id"),
                "evidence_items": _nested_get(recall, ["summary", "evidence_items"]),
                "latest": recall_latest_path,
            },
            "synthesis": {
                "ok": synthesis.get("ok"),
                "candidate_id": synthesis.get("candidate_id"),
                "scope": synthesis.get("scope"),
                "latest": synthesis_latest_path,
            },
        },
        "summary": {
            "status": "ok" if fails == 0 and warnings == 0 else ("fail" if fails else "warn"),
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
        },
        "policy": {
            "model_used": False,
            "local_only": True,
            "repo_mutation": False,
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }


def eval_validate_document(
    *,
    latest: Any,
    latest_error: Any,
    latest_path: str,
    validate_latest_path: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        eval_check("ok" if isinstance(latest, dict) else "fail", "latest", "eval latest exists", {"path": latest_path, "error": latest_error})
    ]
    if isinstance(latest, dict):
        checks.append(eval_check(
            "ok" if latest.get("schema") == f"{schema_prefix}_nervous_eval_v1" else "fail",
            "schema",
            "eval schema is expected",
            {"schema": latest.get("schema")},
        ))
        checks.append(eval_check(
            "ok" if latest.get("ok") is True else "fail",
            "eval_ok",
            "latest eval run is ok",
            latest.get("summary") if isinstance(latest.get("summary"), dict) else None,
        ))
        checks.append(eval_check(
            "ok" if _nested_get(latest, ["policy", "repo_mutation"]) is False else "fail",
            "repo_mutation",
            "eval does not mutate repos",
            latest.get("policy") if isinstance(latest.get("policy"), dict) else None,
        ))
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{schema_prefix}_nervous_eval_validate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "checks": checks,
        "summary": {"fails": fails, "warnings": warnings, "checks": len(checks)},
        "paths": {"latest": latest_path, "validate_latest": validate_latest_path},
    }
