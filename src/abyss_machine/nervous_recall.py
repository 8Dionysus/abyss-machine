from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def normalize_mode(mode: str | None) -> str:
    return mode if mode in {"lexical", "hybrid"} else "lexical"


def pack_execution_plan(
    *,
    query: str,
    limit: int | None = None,
    mode: str = "lexical",
    force_policy: bool = False,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    filters = {
        "source": source,
        "schema": schema,
        "since": since,
        "until": until,
        "severity": severity,
        "sensitivity": sensitivity,
    }
    base_kwargs: dict[str, Any] = {
        "query": str(query),
        "limit": int(limit) if limit is not None else None,
        **filters,
    }
    if normalized_mode == "hybrid":
        adapter = "nervous_rerank_search"
        search_kwargs = {
            **base_kwargs,
            "use_semantic": True,
            "force_policy": bool(force_policy),
            "write_latest": True,
        }
    else:
        adapter = "nervous_index_search"
        search_kwargs = {
            **base_kwargs,
            "dedupe": True,
            "order": "latest",
        }
    return {
        "schema": f"{schema_prefix}_nervous_recall_pack_execution_plan_v1",
        "query": str(query),
        "mode": normalized_mode,
        "filters": filters,
        "search": {
            "adapter": adapter,
            "kwargs": search_kwargs,
        },
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "model_used": normalized_mode == "hybrid",
            "repo_mutation": False,
            "live_execution_at_cli_edge": True,
        },
    }


def refused_result(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_retrieval_pack_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; recall did not read or write a retrieval pack",
    }


def evidence_from_results(results: list[Any]) -> list[dict[str, Any]]:
    evidence = []
    for item in results:
        if not isinstance(item, dict):
            continue
        evidence.append({
            "chunk_id": item.get("chunk_id"),
            "doc_id": item.get("doc_id"),
            "source_id": item.get("source_id"),
            "document_schema": item.get("document_schema"),
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "score": item.get("score"),
            "rerank": item.get("rerank") if isinstance(item.get("rerank"), dict) else None,
            "sources_used": item.get("sources_used") if isinstance(item.get("sources_used"), list) else None,
            "document_generated_at": item.get("document_generated_at"),
            "chunk_generated_at": item.get("chunk_generated_at"),
            "capture_trigger": item.get("capture_trigger"),
            "source_path": item.get("source_path"),
            "source_line": item.get("source_line"),
            "severity": item.get("severity"),
            "sensitivity": item.get("sensitivity"),
            "provenance": item.get("provenance") if isinstance(item.get("provenance"), dict) else {},
        })
    return evidence


def evidence_summary(evidence: list[dict[str, Any]], search: Mapping[str, Any]) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    schema_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in evidence:
        source_counts[str(item.get("source_id") or "unknown")] = source_counts.get(str(item.get("source_id") or "unknown"), 0) + 1
        schema_counts[str(item.get("document_schema") or "unknown")] = schema_counts.get(str(item.get("document_schema") or "unknown"), 0) + 1
        severity_counts[str(item.get("severity") or "unknown")] = severity_counts.get(str(item.get("severity") or "unknown"), 0) + 1
        provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
        if provenance.get("category"):
            category_counts[str(provenance.get("category"))] = category_counts.get(str(provenance.get("category")), 0) + 1
    return {
        "evidence_items": len(evidence),
        "source_counts": dict(sorted(source_counts.items())),
        "schema_counts": dict(sorted(schema_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "search_error": search.get("error"),
        "search_warnings": search.get("warnings") if isinstance(search.get("warnings"), list) else [],
    }


def pack_id(query: str, filters: Mapping[str, Any], evidence: list[dict[str, Any]], index_run_id: Any) -> str:
    identity = json.dumps({
        "query": query,
        "filters": dict(filters),
        "result_ids": [str(item.get("chunk_id") or item.get("doc_id") or "") for item in evidence],
        "index_run_id": index_run_id,
    }, ensure_ascii=False, sort_keys=True)
    return "rpk-" + hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:24]


def pack_document(
    *,
    query: str,
    mode: str,
    filters: dict[str, Any],
    search: Mapping[str, Any],
    evidence: list[dict[str, Any]],
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_path: str,
    daily_glob: str,
) -> dict[str, Any]:
    index_run_id = _nested_get(search, ["summary", "index_run_id"])
    data = {
        "schema": f"{schema_prefix}_nervous_retrieval_pack_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(search.get("ok")),
        "pack_id": pack_id(query, filters, evidence, index_run_id),
        "query": query,
        "mode": normalize_mode(mode),
        "filters": filters,
        "source": {
            "search_schema": search.get("schema"),
            "search_ok": search.get("ok"),
            "search_mode": normalize_mode(mode),
            "index_run_id": index_run_id,
            "semantic_run_id": _nested_get(search, ["summary", "semantic_run_id"]),
            "index_built_at": _nested_get(search, ["summary", "built_at"]),
            "freshness": _nested_get(search, ["summary", "freshness"]),
            "warnings": search.get("warnings") if isinstance(search.get("warnings"), list) else [],
        },
        "summary": evidence_summary(evidence, search),
        "evidence": evidence,
        "claims": [
            {
                "claim": "This pack contains search evidence only; it does not assert unstated causes or decisions.",
                "confidence": "high",
                "supporting_chunk_ids": [str(item.get("chunk_id")) for item in evidence if item.get("chunk_id")][:20],
            }
        ],
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "model_used": bool(_nested_get(search, ["summary", "semantic_used"])),
            "repo_mutation": False,
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }
    if not search.get("ok"):
        data["ok"] = False
        data["error"] = search.get("error") or "search failed"
    return data


def _nested_get(value: Any, path: list[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
