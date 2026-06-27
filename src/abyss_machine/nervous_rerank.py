from __future__ import annotations

import copy
import datetime as dt
from typing import Any, Callable, Mapping


DEFAULT_PROFILE: dict[str, Any] = {
    "id": "host_machine_evidence_v1",
    "weights": {
        "lexical": 0.36,
        "semantic": 0.28,
        "query_overlap": 0.15,
        "recency": 0.07,
        "severity": 0.05,
        "source_prior": 0.09,
    },
    "sources": [
        {
            "source_id": "nervous_events",
            "default": 1.0,
            "matched": 1.0,
            "tokens": [
                "event",
                "events",
                "episode",
                "episodes",
                "thermal",
                "temperature",
                "memory",
                "ram",
                "swap",
                "zram",
                "system",
                "resource",
                "machine",
                "service",
                "timer",
                "index",
                "indexing",
                "embedding",
                "rerank",
                "gemma",
                "llama",
                "tts",
                "dictation",
                "cpu",
                "gpu",
                "podman",
            ],
            "reason": "derived host event evidence is canonical for machine state questions",
        },
        {
            "source_id": "nervous_episodes",
            "default": 1.0,
            "matched": 1.0,
            "tokens": [
                "event",
                "events",
                "episode",
                "episodes",
                "thermal",
                "temperature",
                "memory",
                "ram",
                "swap",
                "zram",
                "system",
                "resource",
                "machine",
                "service",
                "timer",
                "index",
                "indexing",
                "embedding",
                "rerank",
                "gemma",
                "llama",
                "tts",
                "dictation",
                "cpu",
                "gpu",
                "podman",
            ],
            "reason": "derived host episode evidence is canonical for machine state questions",
        },
        {
            "source_id": "abyss_machine_facts",
            "default": 1.0,
            "matched": 1.0,
            "tokens": [
                "thermal",
                "temperature",
                "memory",
                "ram",
                "swap",
                "zram",
                "storage",
                "resource",
                "system",
                "machine",
                "timer",
                "service",
                "index",
                "indexing",
                "embedding",
                "rerank",
                "gemma",
                "llama",
                "tts",
                "dictation",
                "cpu",
                "gpu",
                "podman",
            ],
            "reason": "abyss-machine facts are first-party host evidence",
        },
        {
            "source_id": "browser_active_tab",
            "default": 0.2,
            "matched": 0.95,
            "tokens": ["browser", "firefox", "url", "tab", "web", "page", "history"],
            "reason": "browser evidence is useful when the query is explicitly browser-shaped",
        },
        {
            "source_id": "clipboard",
            "default": 0.15,
            "matched": 0.95,
            "tokens": ["clipboard", "copy", "paste", "buffer"],
            "reason": "clipboard evidence is useful only for clipboard-shaped queries",
        },
        {
            "source_id": "terminal_stdout_stderr",
            "default": 0.35,
            "matched": 0.85,
            "tokens": ["terminal", "shell", "command", "stdout", "stderr", "console"],
            "reason": "terminal evidence is useful for command-output queries",
        },
        {
            "source_id": "screenshots",
            "default": 0.2,
            "matched": 0.85,
            "tokens": ["screen", "screenshot", "visual", "window"],
            "reason": "screenshot evidence is useful for visual desktop queries",
        },
        {
            "source_id": "audio_transcript_autolog",
            "default": 0.25,
            "matched": 0.85,
            "tokens": ["dictation", "transcript", "speech", "audio", "voice"],
            "reason": "dictation evidence is useful for speech/transcript queries",
        },
        {
            "source_id": "typed_text_autolog",
            "default": 0.25,
            "matched": 0.9,
            "tokens": ["typing", "typed", "text", "input", "write", "editor", "shell", "command"],
            "reason": "typed-text evidence is useful for explicit writing/input context queries",
        },
    ],
    "fallback": {"default": 0.6, "reason": "neutral source prior for known but unprofiled sources"},
    "machine_query": {
        "tokens": [
            "thermal",
            "temperature",
            "memory",
            "ram",
            "swap",
            "zram",
            "resource",
            "system",
            "machine",
            "timer",
            "service",
            "index",
            "indexing",
            "embedding",
            "rerank",
            "gemma",
            "llama",
            "tts",
            "dictation",
            "cpu",
            "gpu",
            "podman",
        ],
        "preferred_sources": [
            "abyss_machine_facts",
            "nervous_events",
            "nervous_episodes",
            "systemd_metadata",
            "podman_metadata",
        ],
        "context_sources": [
            "browser_active_tab",
            "clipboard",
            "screenshots",
            "audio_transcript_autolog",
            "typed_text_autolog",
        ],
        "unmatched_context_max_score": 0.34,
        "reason": "machine-state queries should not be led by unmatched desktop context when first-party host evidence is available",
    },
}


def default_profile() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_PROFILE)


def profile_from_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = config if isinstance(config, Mapping) else {}
    search_config = config.get("search", {}) if isinstance(config.get("search"), dict) else {}
    override = search_config.get("rerank") if isinstance(search_config.get("rerank"), dict) else {}
    profile = default_profile()
    if isinstance(override, dict):
        if override.get("source_prior_profile"):
            profile["id"] = str(override.get("source_prior_profile"))
        weights = override.get("weights") if isinstance(override.get("weights"), dict) else {}
        for key, value in weights.items():
            try:
                profile["weights"][str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        source_priors = override.get("source_priors") if isinstance(override.get("source_priors"), dict) else {}
        if source_priors:
            by_source = {
                str(item.get("source_id")): dict(item)
                for item in profile.get("sources", [])
                if isinstance(item, dict) and item.get("source_id")
            }
            for source_id, spec in source_priors.items():
                if not isinstance(spec, dict):
                    continue
                current = by_source.setdefault(str(source_id), {"source_id": str(source_id)})
                if "default" in spec:
                    current["default"] = spec.get("default")
                if "matched" in spec:
                    current["matched"] = spec.get("matched")
                if isinstance(spec.get("tokens"), list):
                    current["tokens"] = [str(token) for token in spec.get("tokens", [])]
                if spec.get("reason"):
                    current["reason"] = str(spec.get("reason"))
            profile["sources"] = list(by_source.values())
        machine_query = override.get("machine_query") if isinstance(override.get("machine_query"), dict) else {}
        if machine_query:
            current_machine_query = profile.get("machine_query") if isinstance(profile.get("machine_query"), dict) else {}
            for key in ("tokens", "preferred_sources", "context_sources"):
                if isinstance(machine_query.get(key), list):
                    current_machine_query[key] = [str(value) for value in machine_query.get(key, []) if str(value).strip()]
            if "unmatched_context_max_score" in machine_query:
                try:
                    current_machine_query["unmatched_context_max_score"] = float(machine_query.get("unmatched_context_max_score"))
                except (TypeError, ValueError):
                    pass
            if machine_query.get("reason"):
                current_machine_query["reason"] = str(machine_query.get("reason"))
            profile["machine_query"] = current_machine_query
    total_weight = sum(float(value or 0.0) for value in profile.get("weights", {}).values())
    profile["weight_total"] = round(total_weight, 6)
    return profile


def neural_config_from_config(
    config: Mapping[str, Any] | None,
    *,
    default_model_dir: str,
    default_cache_dir: str,
    default_scorer: str,
) -> dict[str, Any]:
    config = config if isinstance(config, Mapping) else {}
    search_config = config.get("search", {}) if isinstance(config.get("search"), dict) else {}
    rerank_config = search_config.get("rerank") if isinstance(search_config.get("rerank"), dict) else {}
    override = rerank_config.get("neural") if isinstance(rerank_config.get("neural"), dict) else {}
    cfg = {
        "enabled": bool(override.get("enabled", False)),
        "backend": str(override.get("backend") or "openvino_qwen3_reranker"),
        "model_dir": str(override.get("model_dir") or default_model_dir),
        "device": str(override.get("device") or "GPU"),
        "cache_dir": str(override.get("cache_dir") or default_cache_dir),
        "scorer": str(override.get("scorer") or default_scorer),
        "max_length": int(override.get("max_length") or 2048),
        "batch_size": int(override.get("batch_size") or 4),
        "candidate_limit": int(override.get("candidate_limit") or 24),
        "weight": float(override.get("weight") if override.get("weight") is not None else 0.35),
        "machine_context_weight": float(override.get("machine_context_weight") if override.get("machine_context_weight") is not None else 0.0),
        "timeout_sec": float(override.get("timeout_sec") or 240),
        "resource_class": str(override.get("resource_class") or "medium"),
        "instruction": str(
            override.get("instruction")
            or "Given a local machine memory search query, retrieve relevant evidence chunks that answer the query"
        ),
        "policy": {
            "resident_service": False,
            "repo_mutation": False,
            "guarded_by_hybrid_source_prior": True,
            "unmatched_machine_context_receives_neural_boost": False,
        },
    }
    cfg["weight"] = _clamp01(cfg["weight"])
    cfg["machine_context_weight"] = _clamp01(cfg["machine_context_weight"])
    return cfg


def neural_text(item: Mapping[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    snippet = str(item.get("snippet") or item.get("body_preview") or "").strip()
    source_id = str(item.get("source_id") or "").strip()
    schema = str(item.get("document_schema") or "").strip()
    parts = []
    if source_id or schema:
        parts.append(f"Source: {source_id} {schema}".strip())
    if title:
        parts.append(f"Title: {title}")
    if snippet:
        parts.append(snippet)
    return "\n".join(parts).strip()


def apply_neural_scores(
    ranked: list[dict[str, Any]],
    neural_scores: list[dict[str, Any]],
    query_tokens: set[str],
    rerank_profile: Mapping[str, Any],
    neural_config: Mapping[str, Any],
    *,
    candidate_limit: int | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(candidate_limit or len(ranked) or 1), len(ranked)))
    candidates = ranked[:limit]
    score_by_id = {
        str(item.get("id")): item
        for item in neural_scores
        if isinstance(item, dict) and item.get("id") is not None
    }
    machine_config = rerank_profile.get("machine_query") if isinstance(rerank_profile.get("machine_query"), dict) else {}
    context_sources = {str(value) for value in machine_config.get("context_sources", []) if str(value).strip()}
    preferred_sources = {str(value) for value in machine_config.get("preferred_sources", []) if str(value).strip()}
    machine_tokens = {str(token).lower() for token in machine_config.get("tokens", []) if str(token).strip()}
    machine_query_active = bool(query_tokens & machine_tokens)
    default_weight = float(neural_config.get("weight") or 0.0)
    context_weight = float(neural_config.get("machine_context_weight") or 0.0)
    for item in candidates:
        item_id = str(item.get("chunk_id") or item.get("doc_id") or "")
        scored = score_by_id.get(item_id)
        if not scored:
            continue
        rerank = item.get("rerank") if isinstance(item.get("rerank"), dict) else {}
        hybrid_score = float(rerank.get("score") or item.get("score") or 0.0)
        neural_score = float(scored.get("score") or 0.0)
        source_id = str(item.get("source_id") or "")
        source_matched = rerank.get("source_matched_tokens") if isinstance(rerank.get("source_matched_tokens"), list) else []
        unmatched_machine_context = bool(machine_query_active and source_id in context_sources and not source_matched)
        weight = context_weight if unmatched_machine_context else default_weight
        final_score = ((1.0 - weight) * hybrid_score) + (weight * neural_score)
        guard = {
            "machine_query_active": machine_query_active,
            "unmatched_machine_context": unmatched_machine_context,
            "weight": round(weight, 6),
            "reason": (
                "unmatched desktop context receives no neural boost for machine-shaped queries"
                if unmatched_machine_context and weight == 0.0
                else "hybrid/source-prior guarded neural blend"
            ),
        }
        rerank["score_before_neural"] = round(hybrid_score, 6)
        rerank["neural_score"] = round(neural_score, 6)
        rerank["neural_raw_logit_diff"] = scored.get("raw_logit_diff")
        rerank["neural_blend_weight"] = round(weight, 6)
        rerank["neural_guard"] = guard
        rerank["score"] = round(final_score, 6)
        item["rerank"] = rerank
        item["score"] = round(final_score, 6)
    if machine_query_active and preferred_sources:
        _apply_preferred_host_guard(candidates, preferred_sources, context_sources)
    ranked.sort(key=ranked_sort_key)
    return ranked


def machine_query_cap_detail(
    query_tokens: set[str],
    source_id: str,
    source_detail: Mapping[str, Any],
    final_score: float,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    machine_config = profile.get("machine_query") if isinstance(profile.get("machine_query"), dict) else {}
    machine_tokens = {str(token).lower() for token in machine_config.get("tokens", []) if str(token).strip()}
    matched_machine_tokens = sorted(query_tokens & machine_tokens)
    detail: dict[str, Any] = {
        "active": bool(matched_machine_tokens),
        "applied": False,
        "matched_tokens": matched_machine_tokens,
    }
    if not matched_machine_tokens:
        return detail
    context_sources = {str(value) for value in machine_config.get("context_sources", []) if str(value).strip()}
    source_matched_tokens = source_detail.get("matched_tokens") if isinstance(source_detail.get("matched_tokens"), list) else []
    if source_id not in context_sources or source_matched_tokens:
        return detail
    try:
        cap = float(machine_config.get("unmatched_context_max_score", 0.34))
    except (TypeError, ValueError):
        cap = 0.34
    cap = _clamp01(cap)
    capped_score = min(float(final_score), cap)
    detail.update(
        {
            "applied": capped_score < float(final_score),
            "score_before": round(float(final_score), 6),
            "score_after": round(capped_score, 6),
            "max_score": round(cap, 6),
            "reason": machine_config.get("reason"),
        }
    )
    return detail


def result_source_score_detail(item: Mapping[str, Any], query_tokens: set[str], profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    profile = profile if isinstance(profile, Mapping) else default_profile()
    source_id = str(item.get("source_id") or "")
    for spec in profile.get("sources", []):
        if not isinstance(spec, dict) or str(spec.get("source_id") or "") != source_id:
            continue
        source_tokens = {str(token).lower() for token in spec.get("tokens", []) if str(token).strip()}
        matched_tokens = sorted(query_tokens & source_tokens)
        try:
            default_score = float(spec.get("default", 0.6))
            matched_score = float(spec.get("matched", default_score))
        except (TypeError, ValueError):
            default_score = 0.6
            matched_score = default_score
        score = matched_score if matched_tokens else default_score
        return {
            "source_id": source_id,
            "score": round(_clamp01(score), 6),
            "profile": profile.get("id"),
            "matched_tokens": matched_tokens,
            "reason": spec.get("reason"),
        }
    fallback = profile.get("fallback") if isinstance(profile.get("fallback"), dict) else {}
    try:
        fallback_score = float(fallback.get("default", 0.6))
    except (TypeError, ValueError):
        fallback_score = 0.6
    return {
        "source_id": source_id,
        "score": round(_clamp01(fallback_score), 6),
        "profile": profile.get("id"),
        "matched_tokens": [],
        "reason": fallback.get("reason") or "neutral source prior",
    }


def result_source_score(item: Mapping[str, Any], query_tokens: set[str], profile: Mapping[str, Any] | None = None) -> float:
    return float(result_source_score_detail(item, query_tokens, profile).get("score") or 0.0)


def merge_item(
    existing: dict[str, Any],
    incoming: Mapping[str, Any],
    *,
    timestamp_parser: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    incoming = dict(incoming)

    def item_timestamp(value: Mapping[str, Any]) -> float:
        raw = value.get("chunk_generated_at") or value.get("document_generated_at") or value.get("generated_at")
        parsed = timestamp_parser(raw) if timestamp_parser else _parse_datetime(raw)
        return parsed.timestamp() if parsed else 0.0

    if existing and item_timestamp(incoming) > item_timestamp(existing):
        preserved_sources = sorted(set(existing.get("sources_used") or []) | set(incoming.get("sources_used") or []))
        preserved_scores = dict(existing.get("scores") if isinstance(existing.get("scores"), dict) else {})
        for key, value in incoming.items():
            if key in {"sources_used", "scores"}:
                continue
            existing[key] = value
        existing["sources_used"] = preserved_sources
        existing["scores"] = preserved_scores
    for key, value in incoming.items():
        if key in {"sources_used", "scores"}:
            continue
        if existing.get(key) in (None, "", []):
            existing[key] = value
    existing_sources = set(existing.get("sources_used") or [])
    existing_sources.update(incoming.get("sources_used") or [])
    existing["sources_used"] = sorted(existing_sources)
    scores = existing.setdefault("scores", {})
    incoming_scores = incoming.get("scores") if isinstance(incoming.get("scores"), dict) else {}
    for key, value in incoming_scores.items():
        if value is None:
            continue
        current = scores.get(key)
        if current is None or float(value) > float(current):
            scores[key] = value
    return existing


def score_result_item(
    item: dict[str, Any],
    *,
    query_tokens: set[str],
    text_tokens: set[str],
    recency_score: float,
    severity_score: float,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
    rerank_weights = profile.get("weights") if isinstance(profile.get("weights"), dict) else {}
    overlap = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
    source_detail = result_source_score_detail(item, query_tokens, profile)
    source_score = float(source_detail.get("score") or 0.0)
    lexical_score = float(scores.get("lexical_rank") or 0.0)
    semantic_score = float(scores.get("semantic_norm") or 0.0)
    final_score = (
        float(rerank_weights.get("lexical", 0.36)) * lexical_score
        + float(rerank_weights.get("semantic", 0.28)) * semantic_score
        + float(rerank_weights.get("query_overlap", 0.15)) * overlap
        + float(rerank_weights.get("recency", 0.07)) * recency_score
        + float(rerank_weights.get("severity", 0.05)) * severity_score
        + float(rerank_weights.get("source_prior", 0.09)) * source_score
    )
    machine_cap = machine_query_cap_detail(
        query_tokens,
        str(item.get("source_id") or ""),
        source_detail,
        final_score,
        profile,
    )
    if machine_cap.get("applied"):
        final_score = float(machine_cap.get("score_after") or final_score)
    item["rerank"] = {
        "score": round(final_score, 6),
        "lexical_rank_score": round(lexical_score, 6),
        "semantic_score": round(semantic_score, 6),
        "query_overlap": round(overlap, 6),
        "recency_score": round(recency_score, 6),
        "severity_score": round(severity_score, 6),
        "source_score": round(source_score, 6),
        "source_profile": source_detail.get("profile"),
        "source_reason": source_detail.get("reason"),
        "source_matched_tokens": source_detail.get("matched_tokens"),
    }
    if machine_cap.get("active"):
        item["rerank"]["machine_query_cap"] = machine_cap
    item["score"] = round(final_score, 6)
    return item


def ranked_sort_key(item: Mapping[str, Any]) -> tuple[float, str, str]:
    return (
        -float(_nested_get(item, ["rerank", "score"]) or 0.0),
        str(item.get("document_generated_at") or ""),
        str(item.get("chunk_id") or ""),
    )


def eval_check(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["details"] = details
    return item


def eval_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    fails = sum(1 for item in checks if item.get("level") == "fail")
    warnings = sum(1 for item in checks if item.get("level") == "warn")
    return {
        "status": "ok" if fails == 0 and warnings == 0 else ("fail" if fails else "warn"),
        "fails": fails,
        "warnings": warnings,
        "checks": len(checks),
    }


def eval_document(
    *,
    profile: Mapping[str, Any],
    search: Mapping[str, Any],
    latest_path: str,
    daily_glob: str,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    weights = profile.get("weights") if isinstance(profile.get("weights"), dict) else {}
    try:
        weight_total = float(profile.get("weight_total") or 0.0)
    except (TypeError, ValueError):
        weight_total = 0.0
    machine_detail = result_source_score_detail(
        {"source_id": "abyss_machine_facts"},
        {"thermal", "resource", "machine"},
        profile,
    )
    browser_detail = result_source_score_detail(
        {"source_id": "browser_active_tab"},
        {"thermal", "resource", "machine"},
        profile,
    )
    terminal_detail = result_source_score_detail(
        {"source_id": "terminal_stdout_stderr"},
        {"terminal", "command", "stderr"},
        profile,
    )
    search_summary = search.get("summary") if isinstance(search.get("summary"), dict) else {}
    results = search.get("results") if isinstance(search.get("results"), list) else []
    first_result = results[0] if results and isinstance(results[0], dict) else {}
    first_rerank = first_result.get("rerank") if isinstance(first_result.get("rerank"), dict) else {}
    machine_query_config = profile.get("machine_query") if isinstance(profile.get("machine_query"), dict) else {}
    preferred_machine_sources = {str(value) for value in machine_query_config.get("preferred_sources", []) if str(value).strip()}
    context_sources = {str(value) for value in machine_query_config.get("context_sources", []) if str(value).strip()}
    first_source_id = str(first_result.get("source_id") or "") if isinstance(first_result, dict) else ""
    machine_cap_results = []
    unmatched_context_results = []
    for result in results:
        if not isinstance(result, dict):
            continue
        rerank = result.get("rerank") if isinstance(result.get("rerank"), dict) else {}
        cap = rerank.get("machine_query_cap") if isinstance(rerank.get("machine_query_cap"), dict) else {}
        if result.get("source_id") in context_sources and cap.get("active") and not rerank.get("source_matched_tokens"):
            unmatched_context_results.append(
                {
                    "source_id": result.get("source_id"),
                    "score": rerank.get("score"),
                }
            )
            machine_cap_results.append(
                {
                    "source_id": result.get("source_id"),
                    "score": rerank.get("score"),
                    "cap": cap,
                }
            )
    stale_warnings = [str(item) for item in (search.get("warnings") or []) if "semantic index is stale relative" in str(item)]
    checks = [
        eval_check(
            "ok" if 0.99 <= weight_total <= 1.01 else "fail",
            "weights_total",
            f"rerank weights total {weight_total}",
            {"profile": profile.get("id"), "weights": weights},
        ),
        eval_check(
            "ok" if float(machine_detail.get("score") or 0.0) >= 0.95 else "fail",
            "machine_source_prior",
            "first-party machine facts keep the strongest source prior",
            machine_detail,
        ),
        eval_check(
            "ok" if float(browser_detail.get("score") or 1.0) <= 0.3 else "fail",
            "context_source_prior_unmatched",
            "browser source prior stays low for non-browser machine queries",
            browser_detail,
        ),
        eval_check(
            "ok" if float(terminal_detail.get("score") or 0.0) >= 0.8 else "fail",
            "context_source_prior_matched",
            "terminal source prior rises for command-shaped queries",
            terminal_detail,
        ),
        eval_check(
            "ok" if search.get("ok") else "fail",
            "live_rerank_query",
            "live hybrid rerank query returns results",
            {"summary": search_summary, "warnings": search.get("warnings"), "notices": search.get("notices")},
        ),
        eval_check(
            "ok" if first_rerank.get("source_profile") and "source_score" in first_rerank else "fail",
            "explainable_source_prior",
            "rerank results expose source-prior profile and score",
            {"first_rerank": first_rerank},
        ),
        eval_check(
            "ok" if first_source_id in preferred_machine_sources else "fail",
            "machine_query_prefers_host_evidence",
            "machine-shaped rerank query is led by first-party host evidence",
            {"first_source_id": first_source_id, "preferred_sources": sorted(preferred_machine_sources), "first_rerank": first_rerank},
        ),
        eval_check(
            "ok" if not unmatched_context_results or machine_cap_results else "fail",
            "machine_query_caps_unmatched_context",
            "unmatched desktop context is absent or capped for machine-shaped queries",
            {"context_sources": sorted(context_sources), "unmatched_context_results": unmatched_context_results[:5], "capped_results": machine_cap_results[:5]},
        ),
        eval_check(
            "ok" if not stale_warnings else "fail",
            "threshold_aware_stale_warning",
            "rerank does not emit the old raw stale warning",
            {"old_warnings": stale_warnings, "notices": search.get("notices")},
        ),
    ]
    if search_summary.get("semantic_stale") and not search_summary.get("semantic_maintenance_needed"):
        notices = [str(item) for item in (search.get("notices") or [])]
        checks.append(
            eval_check(
                "ok" if any("below maintenance thresholds" in item or "bounded stale drift" in item for item in notices) else "fail",
                "bounded_stale_notice",
                "below-threshold semantic drift is a notice, not a warning",
                {"notices": notices, "maintenance": _nested_get(search, ["sources", "semantic", "status", "maintenance"])},
            )
        )
    summary = eval_summary(checks)
    return {
        "schema": f"{schema_prefix}_nervous_rerank_eval_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0,
        "status": summary["status"],
        "summary": summary,
        "checks": checks,
        "profile": {
            "id": profile.get("id"),
            "weights": weights,
            "weight_total": profile.get("weight_total"),
        },
        "live_search": {
            "query": search.get("query"),
            "summary": search_summary,
            "warnings": search.get("warnings"),
            "notices": search.get("notices"),
            "top_sources": [item.get("source_id") for item in results[:5] if isinstance(item, dict)],
        },
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "model_used": bool(search_summary.get("semantic_used")),
            "repo_mutation": False,
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }


def _apply_preferred_host_guard(
    candidates: list[dict[str, Any]],
    preferred_sources: set[str],
    context_sources: set[str],
) -> None:
    preferred_scores = [
        float(_nested_get(item, ["rerank", "score"]) or item.get("score") or 0.0)
        for item in candidates
        if str(item.get("source_id") or "") in preferred_sources
    ]
    best_preferred_score = max(preferred_scores) if preferred_scores else 0.0
    if best_preferred_score <= 0.0:
        return
    preferred_guard_score = max(0.0, best_preferred_score - 0.001)
    for item in candidates:
        source_id = str(item.get("source_id") or "")
        rerank = item.get("rerank") if isinstance(item.get("rerank"), dict) else {}
        guard = rerank.get("neural_guard") if isinstance(rerank.get("neural_guard"), dict) else {}
        source_matched = rerank.get("source_matched_tokens") if isinstance(rerank.get("source_matched_tokens"), list) else []
        unmatched_machine_context = bool(source_id in context_sources and not source_matched)
        current_score = float(rerank.get("score") or item.get("score") or 0.0)
        if not unmatched_machine_context or current_score <= preferred_guard_score:
            continue
        demoted_score = round(preferred_guard_score, 6)
        guard.update(
            {
                "preferred_host_guard": True,
                "preferred_host_score": round(best_preferred_score, 6),
                "score_before_preferred_host_guard": round(current_score, 6),
                "reason": "unmatched desktop context is kept below first-party machine evidence",
            }
        )
        rerank["neural_guard"] = guard
        rerank["score"] = demoted_score
        item["rerank"] = rerank
        item["score"] = demoted_score


def _nested_get(value: Any, path: list[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, min(numeric, 1.0))


def _parse_datetime(value: Any) -> dt.datetime | None:
    if not value:
        return None
    raw = str(value)
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed
