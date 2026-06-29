from __future__ import annotations

import datetime as dt
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from . import nervous_index
from . import nervous_recall
from . import nervous_rerank
from . import typing_nervous_adapters


SearchPort = Callable[..., Mapping[str, Any]]
StatusPort = Callable[[], Mapping[str, Any]]
MaintainAssessPort = Callable[[dict[str, Any], int, float], Mapping[str, Any]]
NeuralApplyPort = Callable[
    [list[dict[str, Any]], str, set[str], dict[str, Any], dict[str, Any], bool],
    tuple[list[dict[str, Any]], Mapping[str, Any] | None, list[str]],
]
NowPort = Callable[[], dt.datetime]
PathExistsPort = Callable[[Any], bool]


def write_latest_history(data: dict[str, Any], latest_path: Path, daily_root: Path) -> dict[str, Any]:
    errors = typing_nervous_adapters.write_latest_and_history(data, latest_path, daily_root, mode=0o664)
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
    return data


def hybrid_rerank_search(
    *,
    query: str,
    config: Mapping[str, Any],
    rerank_profile: dict[str, Any],
    neural_config: dict[str, Any],
    lexical_search: SearchPort,
    semantic_status: StatusPort,
    semantic_config: Mapping[str, Any],
    semantic_maintain_assess: MaintainAssessPort,
    semantic_search: SearchPort,
    neural_apply: NeuralApplyPort,
    latest_path: Path,
    daily_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    limit: int | None = None,
    candidate_limit: int | None = None,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    use_semantic: bool = True,
    use_neural: bool | None = None,
    force_policy: bool = False,
    write_latest: bool = True,
    now: NowPort | None = None,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    search_config = config.get("search", {}) if isinstance(config.get("search"), Mapping) else {}
    max_limit = max(1, int(search_config.get("max_limit") or 50))
    final_limit = max(1, min(int(limit or 12), max_limit))
    final_candidate_limit = max(final_limit, min(int(candidate_limit or max(final_limit * 4, 24)), max_limit))
    lexical = dict(
        lexical_search(
            query=query,
            limit=final_candidate_limit,
            dedupe=False,
            order="ranked",
            source=source,
            schema=schema,
            since=since,
            until=until,
            severity=severity,
            sensitivity=sensitivity,
        )
    )
    semantic_status_doc = dict(semantic_status())
    semantic_maintain_config = semantic_config.get("maintain") if isinstance(semantic_config.get("maintain"), Mapping) else {}
    semantic_maintenance = dict(
        semantic_maintain_assess(
            semantic_status_doc,
            int(semantic_maintain_config.get("min_delta_chunks") or 128),
            float(semantic_maintain_config.get("max_stale_minutes") or 90),
        )
    )
    if use_neural is False:
        neural_config = dict(neural_config)
        neural_config["enabled"] = False

    semantic: dict[str, Any] | None = None
    neural: Mapping[str, Any] | None = None
    warnings: list[str] = []
    notices: list[str] = []
    if use_semantic and semantic_status_doc.get("ready"):
        if _nested_get(semantic_status_doc, ["freshness", "stale"]):
            if semantic_maintenance.get("needed"):
                warnings.append("semantic sidecar exceeds maintenance thresholds; semantic scores are advisory")
            else:
                notices.append("semantic sidecar has bounded stale drift below maintenance thresholds")
        semantic = dict(
            semantic_search(
                query=query,
                limit=final_candidate_limit,
                dedupe=False,
                source=source,
                schema=schema,
                since=since,
                until=until,
                severity=severity,
                sensitivity=sensitivity,
                force_policy=force_policy,
            )
        )
        if not semantic.get("ok"):
            warnings.append(str(semantic.get("error") or "semantic search failed; lexical candidates are used"))
    elif use_semantic:
        warnings.append("semantic index is not ready; lexical candidates are used")

    query_tokens = _query_tokens(query)
    merged = _merge_lexical_semantic(lexical, semantic)
    ranked: list[dict[str, Any]] = []
    for item in merged.values():
        text_tokens = _query_tokens(_result_text(item))
        scored = nervous_rerank.score_result_item(
            item,
            query_tokens=query_tokens,
            text_tokens=text_tokens,
            recency_score=_result_recency_score(item, now=now),
            severity_score=_result_severity_score(item),
            profile=rerank_profile,
        )
        ranked.append(scored)
    ranked.sort(key=nervous_rerank.ranked_sort_key)
    if bool(neural_config.get("enabled")) and ranked:
        ranked, neural, neural_warnings = neural_apply(
            ranked,
            query,
            query_tokens,
            rerank_profile,
            neural_config,
            force_policy,
        )
        warnings.extend(neural_warnings)
    results = ranked[:final_limit]
    lexical_results = lexical.get("results") if isinstance(lexical.get("results"), list) else []
    semantic_results = semantic.get("results") if isinstance(semantic, dict) and isinstance(semantic.get("results"), list) else []
    exists = path_exists or (lambda value: Path(str(value or "")).exists())
    data = {
        "schema": f"{schema_prefix}_nervous_rerank_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(lexical.get("ok")) and bool(results),
        "query": query,
        "limit": final_limit,
        "candidate_limit": final_candidate_limit,
        "filters": {
            "source": source,
            "schema": schema,
            "since": since,
            "until": until,
            "severity": severity,
            "sensitivity": sensitivity,
        },
        "warnings": warnings,
        "notices": notices,
        "results": results,
        "summary": {
            "results": len(results),
            "candidates": len(merged),
            "lexical_results": len(lexical_results),
            "semantic_results": len(semantic_results),
            "semantic_used": bool(isinstance(semantic, dict) and semantic.get("ok")),
            "neural_enabled": bool(neural_config.get("enabled")),
            "neural_used": bool(isinstance(neural, Mapping) and neural.get("ok")),
            "neural_ready": bool(exists(neural_config.get("model_dir"))),
            "neural_candidates": int(_nested_get(neural, ["timing", "documents"]) or 0) if isinstance(neural, Mapping) else 0,
            "semantic_ready": bool(semantic_status_doc.get("ready")),
            "semantic_stale": bool(_nested_get(semantic_status_doc, ["freshness", "stale"])),
            "semantic_maintenance_needed": bool(semantic_maintenance.get("needed")),
            "index_run_id": _nested_get(lexical, ["summary", "index_run_id"]),
            "built_at": _nested_get(lexical, ["summary", "built_at"]),
            "freshness": _nested_get(lexical, ["summary", "freshness"]),
            "semantic_run_id": _nested_get(semantic, ["summary", "semantic_run_id"]) if isinstance(semantic, dict) else None,
            "source_prior_profile": rerank_profile.get("id"),
        },
        "sources": _source_statuses(lexical, semantic, semantic_status_doc, semantic_maintenance, neural, neural_config),
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "model_used": bool((isinstance(semantic, dict) and semantic.get("ok")) or (isinstance(neural, Mapping) and neural.get("ok"))),
            "resident_service": False,
            "repo_mutation": False,
            "rerank_profile": {
                "id": rerank_profile.get("id"),
                "weights": rerank_profile.get("weights"),
                "weight_total": rerank_profile.get("weight_total"),
            },
            "neural_rerank": {
                "enabled": bool(neural_config.get("enabled")),
                "backend": neural_config.get("backend"),
                "resident_service": False,
                "guarded_by_hybrid_source_prior": True,
            },
        },
        "paths": {
            "latest": str(latest_path),
            "daily_glob": str(daily_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
    }
    if not lexical.get("ok"):
        data["ok"] = False
        data["error"] = lexical.get("error") or "lexical search failed"
    return write_latest_history(data, latest_path, daily_root) if write_latest else data


def build_recall_pack(
    *,
    query: str,
    index_search: SearchPort,
    rerank_search: SearchPort,
    latest_path: Path,
    daily_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    limit: int | None = None,
    mode: str = "lexical",
    force_policy: bool = False,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    plan = nervous_recall.pack_execution_plan(
        query=query,
        limit=limit,
        mode=mode,
        force_policy=force_policy,
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        schema_prefix=schema_prefix,
    )
    search_plan = plan["search"]
    search_kwargs = search_plan["kwargs"]
    if search_plan["adapter"] == "nervous_rerank_search":
        search = dict(rerank_search(**search_kwargs))
    else:
        search = dict(index_search(**search_kwargs))
    results = search.get("results") if isinstance(search.get("results"), list) else []
    evidence = nervous_recall.evidence_from_results(results)
    data = nervous_recall.pack_document(
        query=str(plan["query"]),
        mode=str(plan["mode"]),
        filters=plan["filters"],
        search=search,
        evidence=evidence,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        latest_path=str(latest_path),
        daily_glob=str(daily_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
    )
    return write_latest_history(data, latest_path, daily_root) if write_latest else data


def _merge_lexical_semantic(lexical: Mapping[str, Any], semantic: Mapping[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    lexical_results = lexical.get("results") if isinstance(lexical.get("results"), list) else []
    for rank, item in enumerate(lexical_results, start=1):
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        copied["sources_used"] = ["lexical"]
        copied["scores"] = {
            "lexical_rank": round(1.0 / rank, 6),
            "lexical_raw": item.get("score"),
        }
        key = nervous_index.search_dedupe_key(copied)
        merged[key] = nervous_rerank.merge_item(merged.get(key, {}), copied, timestamp_parser=_parse_time)

    semantic_results = semantic.get("results") if isinstance(semantic, Mapping) and isinstance(semantic.get("results"), list) else []
    for rank, item in enumerate(semantic_results, start=1):
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        semantic_score = float(copied.get("semantic_score") or copied.get("score") or 0.0)
        copied["sources_used"] = ["semantic"]
        copied["scores"] = {
            "semantic_rank": round(1.0 / rank, 6),
            "semantic_raw": round(semantic_score, 6),
            "semantic_norm": round(max(0.0, min((semantic_score + 1.0) / 2.0, 1.0)), 6),
        }
        key = nervous_index.search_dedupe_key(copied)
        merged[key] = nervous_rerank.merge_item(merged.get(key, {}), copied, timestamp_parser=_parse_time)
    return merged


def _source_statuses(
    lexical: Mapping[str, Any],
    semantic: Mapping[str, Any] | None,
    semantic_status_doc: Mapping[str, Any],
    semantic_maintenance: Mapping[str, Any],
    neural: Mapping[str, Any] | None,
    neural_config: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "lexical": {
            "ok": lexical.get("ok"),
            "error": lexical.get("error"),
            "freshness": _nested_get(lexical, ["summary", "freshness"]),
        },
        "semantic": {
            "ok": semantic.get("ok") if isinstance(semantic, Mapping) else None,
            "error": semantic.get("error") if isinstance(semantic, Mapping) else None,
            "status": {
                "ready": semantic_status_doc.get("ready"),
                "warnings": semantic_status_doc.get("warnings"),
                "freshness": semantic_status_doc.get("freshness"),
                "maintenance": semantic_maintenance,
            },
        },
        "neural": {
            "ok": neural.get("ok") if isinstance(neural, Mapping) else None,
            "error": neural.get("error") if isinstance(neural, Mapping) else None,
            "returncode": neural.get("returncode") if isinstance(neural, Mapping) else None,
            "device": neural_config.get("device"),
            "model_dir": neural_config.get("model_dir"),
            "backend": neural_config.get("backend"),
            "weight": neural_config.get("weight"),
            "machine_context_weight": neural_config.get("machine_context_weight"),
            "timing": neural.get("timing") if isinstance(neural, Mapping) else None,
            "resource_profile": neural.get("resource_profile") if isinstance(neural, Mapping) else None,
        },
    }


def _query_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[\wА-Яа-яЁё]{3,}", str(text or ""), flags=re.UNICODE)
    }


def _result_text(item: Mapping[str, Any]) -> str:
    return " ".join(str(item.get(key) or "") for key in ("title", "snippet", "body_preview"))


def _result_recency_score(item: Mapping[str, Any], *, now: NowPort | None = None) -> float:
    parsed = _parse_time(item.get("chunk_generated_at") or item.get("generated_at") or item.get("document_generated_at"))
    if not parsed:
        return 0.0
    basis = now() if now else dt.datetime.now(dt.timezone.utc).astimezone()
    age_hours = max(0.0, (basis - parsed.astimezone(basis.tzinfo)).total_seconds() / 3600.0)
    if age_hours <= 6:
        return 1.0
    if age_hours <= 24:
        return 0.75
    if age_hours <= 24 * 7:
        return 0.45
    return 0.2


def _result_severity_score(item: Mapping[str, Any]) -> float:
    severity = str(item.get("severity") or "").lower()
    return {
        "critical": 1.0,
        "warning": 0.75,
        "watch": 0.55,
        "notice": 0.35,
        "info": 0.2,
    }.get(severity, 0.1)


def _parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    raw = str(value)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def _nested_get(value: Any, path: list[str]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
