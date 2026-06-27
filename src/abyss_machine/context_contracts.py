from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def stable_hash_json(payload: Any, length: int = 24) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[: max(8, min(int(length), 64))]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def nested_get(data: dict[str, Any], path: list[str]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def graph_node(node_id: str, kind: str, label: str, **extra: Any) -> dict[str, Any]:
    data = {"id": node_id, "kind": kind, "label": label}
    data.update(extra)
    return data


def graph_edge(source: str, target: str, relation: str, **extra: Any) -> dict[str, Any]:
    data = {"source": source, "target": target, "relation": relation}
    data.update(extra)
    return data


def graph_index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    graph_root: Path,
    latest_path: Path,
    validate_latest_path: Path,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "graph_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(graph_root),
        "latest": str(latest_path),
        "validate_latest": str(validate_latest_path),
        "commands": {
            "graph": ["abyss-machine", "graph", "--json"],
            "query": ["abyss-machine", "graph", "query", "--node", "ai", "--json"],
            "validate": ["abyss-machine", "graph", "validate", "--json"],
        },
        "latest_summary": graph.get("summary") if isinstance(graph, dict) else None,
    }


def graph_query_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    query: str,
    graph: dict[str, Any],
) -> dict[str, Any]:
    needle = query.lower()
    nodes = [
        item for item in graph.get("nodes", [])
        if needle in str(item.get("id", "")).lower() or needle in str(item.get("label", "")).lower()
    ]
    node_ids = {item.get("id") for item in nodes}
    edges = [
        edge for edge in graph.get("edges", [])
        if edge.get("source") in node_ids or edge.get("target") in node_ids
        or needle in str(edge.get("source", "")).lower() or needle in str(edge.get("target", "")).lower()
    ]
    return {
        "schema": _schema(schema_prefix, "graph_query_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "query": query,
        "summary": {"nodes": len(nodes), "edges": len(edges)},
        "nodes": nodes,
        "edges": edges,
    }


def graph_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    graph_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = graph_summary if isinstance(graph_summary, dict) else None
    return validation_document(
        schema=_schema(schema_prefix, "graph_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="machine graph",
        extra={"graph_summary": summary},
    )


def maps_axis_definitions() -> list[dict[str, str]]:
    return [
        {"axis": "by-time", "question": "When did a machine observation or read model change?"},
        {"axis": "by-subsystem", "question": "Which host subsystem owns this evidence or validator?"},
        {"axis": "by-event-type", "question": "Which nervous event category or severity should I inspect?"},
        {"axis": "by-episode", "question": "Which grouped machine episode explains repeated events?"},
        {"axis": "by-causal-chain", "question": "Which event chain links facts, synthesis, route, action candidate, and validation?"},
        {"axis": "by-owner-route", "question": "Which owner surface owns the cited truth boundary?"},
        {"axis": "by-freshness", "question": "Which evidence is fresh, stale, or maintenance-needed?"},
        {"axis": "by-resource-state", "question": "What does current resource posture allow or defer?"},
        {"axis": "by-risk-privacy", "question": "What privacy, protected-root, or non-action boundary applies?"},
        {"axis": "by-actionability", "question": "What can be acted on only through an owner-gated route?"},
        {"axis": "by-correlation", "question": "Which records are tied by an active change, route, or repeated signal?"},
        {"axis": "by-rag-run", "question": "Which RAG, retrieval, rerank, or agentic evidence is available?"},
        {"axis": "by-memory-candidate", "question": "Which host evidence could become reviewed memory later?"},
        {"axis": "by-eval-packet", "question": "Which host/runtime evidence can inform a bounded proof-context review?"},
        {"axis": "by-kag-export", "question": "Which derived host evidence can inform a graph or knowledge-context projection?"},
    ]


def default_maps_policy(*, schema_prefix: str, version: str, maps_doc_path: Path) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "maps_policy_v1"),
        "version": version,
        "purpose": "Generated host-machine atlas for fast orientation across time, subsystems, routes, freshness, and boundary-context packets.",
        "truth_status": "generated_route_signal_not_source_truth",
        "source_contract": str(maps_doc_path),
        "axes": maps_axis_definitions(),
        "limits": {
            "entries_per_axis_soft": 80,
            "hash_file_max_bytes": 1048576,
            "write_entry_files": True,
        },
        "source_inputs": [
            "/etc/abyss-machine/MAPS.md",
            "/etc/abyss-machine/maps-policy.json",
            "/var/lib/abyss-machine/graph/latest.json",
            "/var/lib/abyss-machine/nervous/brief/latest.json",
            "/var/lib/abyss-machine/nervous/events/latest.json",
            "/var/lib/abyss-machine/nervous/episodes/latest.json",
            "/var/lib/abyss-machine/reactions/latest.json",
            "/var/lib/abyss-machine/responses/latest.json",
            "/var/lib/abyss-machine/changes/index.json",
        ],
        "policy": {
            "generated": True,
            "do_not_hand_edit_generated_entries": True,
            "automatic_action": False,
            "automatic_response": False,
            "raw_private_content": False,
            "project_roots_readonly": True,
            "reader_profiles_are_not_destinations": True,
        },
    }


def maps_policy_document(
    *,
    schema_prefix: str,
    version: str,
    maps_doc_path: Path,
    loaded: dict[str, Any] | None,
    load_error: str | None,
) -> dict[str, Any]:
    defaults = default_maps_policy(schema_prefix=schema_prefix, version=version, maps_doc_path=maps_doc_path)
    if isinstance(loaded, dict):
        data = deep_merge(defaults, loaded)
        data.setdefault("schema", _schema(schema_prefix, "maps_policy_v1"))
        data.setdefault("version", version)
        if load_error:
            data["_load_error"] = load_error
        return data
    defaults["_load_error"] = load_error
    return defaults


def maps_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    maps_root: Path,
    maps_doc_path: Path,
    maps_policy_path: Path,
    maps_agents_path: Path,
    maps_start_path: Path,
    maps_latest_path: Path,
    maps_index_path: Path,
    maps_validate_latest_path: Path,
    history_today: Path,
    service_path: Path,
    timer_path: Path,
    timer_unit: str,
) -> dict[str, Any]:
    axes = maps_axis_definitions()
    return {
        "schema": _schema(schema_prefix, "maps_paths_v1"),
        "version": version,
        "ok": True,
        "generated_at": generated_at,
        "root": str(maps_root),
        "contract": str(maps_doc_path),
        "policy": str(maps_policy_path),
        "agent_entrypoint": str(maps_agents_path),
        "start": str(maps_start_path),
        "latest": str(maps_latest_path),
        "index": str(maps_index_path),
        "validate_latest": str(maps_validate_latest_path),
        "history_today": str(history_today),
        "automation": {
            "service": str(service_path),
            "timer": str(timer_path),
            "unit": timer_unit,
            "cadence": "OnBootSec=9min, OnUnitActiveSec=15min, AccuracySec=2min",
            "command": "abyss-machine maps build --json",
            "resident_daemon": False,
            "automatic_action": False,
            "automatic_response": False,
        },
        "axes": [
            {
                **axis,
                "root": str(maps_root / axis["axis"]),
                "index": str(maps_root / axis["axis"] / "index.json"),
                "readable_index": str(maps_root / axis["axis"] / "INDEX.md"),
                "entries": str(maps_root / axis["axis"] / "entries"),
            }
            for axis in axes
        ],
        "commands": maps_commands(),
    }


def maps_commands() -> dict[str, str]:
    return {
        "status": "abyss-machine maps --json",
        "paths": "abyss-machine maps paths --json",
        "policy": "abyss-machine maps policy --json",
        "build": "abyss-machine maps build --json",
        "query": "abyss-machine maps query --axis by-freshness --query semantic --json",
        "packet": "abyss-machine maps packet --axis by-eval-packet --reader-profile proof-context --json",
        "validate": "abyss-machine maps validate --json",
    }


def maps_entry(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    axis: str,
    label: str,
    route: str,
    summary: str,
    evidence_refs: list[dict[str, Any]],
    owner_route: str = "abyss-machine",
    tags: list[str] | None = None,
    next_commands: list[str] | None = None,
    freshness: str | None = None,
    actionability: str = "route_signal_only",
) -> dict[str, Any]:
    payload = {
        "axis": axis,
        "label": label,
        "route": route,
        "summary": summary,
        "owner_route": owner_route,
        "tags": tags or [],
        "freshness": freshness,
        "actionability": actionability,
        "evidence_refs": evidence_refs,
    }
    return {
        "schema": _schema(schema_prefix, "maps_entry_v1"),
        "version": version,
        "id": f"{axis}:{stable_hash_json(payload, 16)}",
        "generated_at": generated_at,
        "truth_status": "generated_route_signal_not_source_truth",
        **payload,
        "next_commands": next_commands or [],
        "policy": {
            "automatic_action": False,
            "automatic_response": False,
            "raw_private_content": False,
            "does_not_mutate_project_repos": True,
        },
    }


def maps_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    maps_root: Path,
    maps_start_path: Path,
    maps_index_path: Path,
    maps_policy_path: Path,
    maps_doc_path: Path,
    entries_by_axis: dict[str, list[dict[str, Any]]],
    surface_specs_count: int,
    source_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    axes = [
        {
            **axis,
            "entry_count": len(entries_by_axis.get(axis["axis"], [])),
            "index": str(maps_root / axis["axis"] / "index.json"),
            "readable_index": str(maps_root / axis["axis"] / "INDEX.md"),
        }
        for axis in maps_axis_definitions()
    ]
    entries_total = sum(item["entry_count"] for item in axes)
    return {
        "schema": _schema(schema_prefix, "maps_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "root": str(maps_root),
        "start": str(maps_start_path),
        "index": str(maps_index_path),
        "policy_path": str(maps_policy_path),
        "contract": str(maps_doc_path),
        "truth_status": "generated_route_signal_not_source_truth",
        "summary": {
            "axes": len(axes),
            "entries": entries_total,
            "source_inputs": surface_specs_count,
            "automatic_action": False,
            "automatic_response": False,
        },
        "axes": axes,
        "entries_by_axis": entries_by_axis,
        "source_inputs": source_inputs,
        "commands": maps_commands(),
        "policy": {
            "generated": True,
            "do_not_hand_edit": True,
            "source_contract": str(maps_doc_path),
            "generated_facts_do_not_replace_source_contracts": True,
            "automatic_action": False,
            "automatic_response": False,
            "raw_private_content": False,
            "project_roots_readonly": True,
            "reader_profiles_are_not_destinations": True,
        },
    }


def maps_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    maps_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = maps_summary if isinstance(maps_summary, dict) else None
    return validation_document(
        schema=_schema(schema_prefix, "maps_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="machine atlas maps",
        extra={
            "maps_summary": summary,
            "truth_status": "generated_route_signal_not_source_truth",
            "non_claims": [
                "Machine maps are route signals and do not replace source contracts, validators, or reviewed AoA memory/proof/KAG owners.",
                "Machine maps do not authorize automatic action from captured facts, synthesis candidates, reactions, responses, or retrieval packs.",
            ],
        },
    )


def maps_axis_index_markdown(axis: dict[str, str], entries: list[dict[str, Any]]) -> str:
    lines = [
        f"# {axis['axis']}",
        "",
        axis["question"],
        "",
        "Generated entries are route signals, not source truth.",
        "",
        "| Label | Route | Evidence |",
        "| --- | --- | --- |",
    ]
    for entry in entries[:80]:
        evidence = ", ".join(str(ref.get("path")) for ref in entry.get("evidence_refs", [])[:2] if isinstance(ref, dict))
        lines.append(f"| {entry.get('label')} | {entry.get('route')} | {evidence} |")
    lines.append("")
    return "\n".join(lines)


def maps_start_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Abyss Machine Atlas Start",
        "",
        "Use this atlas to orient through host-machine evidence before opening heavy histories or raw captures.",
        "",
        "## First Route",
        "",
        "1. Choose the axis that matches the question.",
        "2. Open that axis `INDEX.md` or `index.json`.",
        "3. Follow evidence refs into source contracts, latest read models, validators, or append-only histories.",
        "4. Treat entries as route signals, not source truth or permission to act.",
        "",
        "## Axis Questions",
        "",
        "| Question | Route | Entries |",
        "| --- | --- | --- |",
    ]
    axis_lookup = {axis["axis"]: axis for axis in maps_axis_definitions()}
    for axis in data.get("axes", []):
        axis_id = str(axis.get("axis"))
        definition = axis_lookup.get(axis_id, {"question": axis_id})
        lines.append(f"| {definition.get('question')} | `{axis_id}/` | {axis.get('entry_count')} |")
    lines.extend([
        "",
        "## Boundaries",
        "",
        "- Generated maps do not replace `/etc/abyss-machine` source contracts.",
        "- Nervous captures, synthesis, reactions, responses, and retrieval packs do not authorize automatic action.",
        "- Reader-profile packets are boundary context for agents; they do not deliver evidence into AoA organs.",
        "",
    ])
    return "\n".join(lines)


def maps_index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    maps_root: Path,
    start_path: Path,
    latest_path: Path,
    validate_latest_path: Path,
    maps_doc_path: Path,
    maps_policy_path: Path,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "maps_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(maps_root),
        "start": str(start_path),
        "latest": str(latest_path),
        "validate_latest": str(validate_latest_path),
        "contract": str(maps_doc_path),
        "policy": str(maps_policy_path),
        "commands": maps_commands(),
        "axis_count": len(maps_axis_definitions()),
        "axes": data.get("axes") if isinstance(data, dict) else None,
        "latest_summary": data.get("summary") if isinstance(data, dict) else None,
        "truth_status": "generated_route_signal_not_source_truth",
    }


def maps_query_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    axis: str | None,
    query: str | None,
    entries_by_axis: dict[str, Any],
) -> dict[str, Any]:
    selected_axes = [axis] if axis else sorted(entries_by_axis)
    needle = (query or "").lower()
    results: list[dict[str, Any]] = []
    for axis_id in selected_axes:
        entries = entries_by_axis.get(axis_id, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            haystack = json.dumps(entry, ensure_ascii=False, sort_keys=True).lower()
            if needle and needle not in haystack:
                continue
            results.append(entry)
    return {
        "schema": _schema(schema_prefix, "maps_query_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "axis": axis,
        "query": query,
        "summary": {"results": len(results), "axes_searched": len(selected_axes)},
        "results": results[:100],
        "truth_status": "generated_route_signal_not_source_truth",
    }


def maps_packet_reader_profiles() -> dict[str, dict[str, Any]]:
    return {
        "agent": {
            "reader_role": "current agent session",
            "purpose": "compact orientation before opening heavier host evidence",
            "preferred_axes": ["by-freshness", "by-causal-chain", "by-owner-route", "by-actionability"],
            "acceptance": "verify source refs before making claims or proposing action",
        },
        "retrieval-context": {
            "reader_role": "agent using retrieval context",
            "purpose": "retrieval context and source-ref seed material without writeback",
            "preferred_axes": ["by-rag-run", "by-freshness", "by-correlation", "by-owner-route"],
            "acceptance": "use as retrieval evidence only; do not write facts back from packet content",
        },
        "graph-context": {
            "reader_role": "agent using graph context",
            "purpose": "GraphRAG route context over host evidence, owners, and causal links",
            "preferred_axes": ["by-causal-chain", "by-correlation", "by-rag-run", "by-kag-export"],
            "acceptance": "use as graph seed evidence only; source refs remain stronger than derived edges",
        },
        "knowledge-context": {
            "reader_role": "agent using derived knowledge context",
            "purpose": "provenance refs for possible graph or knowledge projection work",
            "preferred_axes": ["by-kag-export", "by-causal-chain", "by-owner-route", "by-correlation"],
            "acceptance": "boundary context only; canonical KAG truth belongs outside abyss-machine",
        },
        "proof-context": {
            "reader_role": "agent using bounded proof context",
            "purpose": "host/runtime evidence lens for deciding whether external proof work needs source verification",
            "preferred_axes": ["by-eval-packet", "by-rag-run", "by-resource-state", "by-freshness"],
            "acceptance": "boundary context only; packet does not create verdicts or deliver evidence into a proof organ",
        },
        "memory-context": {
            "reader_role": "agent using memory context",
            "purpose": "host evidence lens for deciding whether a reviewed memory route may be relevant",
            "preferred_axes": ["by-memory-candidate", "by-owner-route", "by-causal-chain", "by-freshness"],
            "acceptance": "boundary context only; packet does not write memory or enter reviewed memory",
        },
        "runtime-context": {
            "reader_role": "agent using runtime context",
            "purpose": "runtime/service boundary context without host-to-stack mutation",
            "preferred_axes": ["by-owner-route", "by-resource-state", "by-correlation", "by-kag-export"],
            "acceptance": "boundary context only; stack promotion decisions remain outside abyss-machine",
        },
    }


def maps_packet_consumer_profiles() -> dict[str, str]:
    return {
        "aoa-evals": "proof-context",
        "aoa-memo": "memory-context",
        "abyss-stack": "runtime-context",
    }


def maps_packet_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "abyss_machine_maps_packet_entry_v1",
        "id": entry.get("id"),
        "axis": entry.get("axis"),
        "label": entry.get("label"),
        "route": entry.get("route"),
        "summary": entry.get("summary"),
        "owner_route": entry.get("owner_route"),
        "tags": entry.get("tags") if isinstance(entry.get("tags"), list) else [],
        "freshness": entry.get("freshness"),
        "actionability": entry.get("actionability"),
        "truth_status": entry.get("truth_status"),
        "evidence_refs": entry.get("evidence_refs") if isinstance(entry.get("evidence_refs"), list) else [],
        "next_commands": entry.get("next_commands") if isinstance(entry.get("next_commands"), list) else [],
        "policy": entry.get("policy") if isinstance(entry.get("policy"), dict) else {},
    }


def maps_packet_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    axis: str | None,
    query: str | None,
    reader_profile: str,
    limit: int,
    consumer: str | None,
    query_result: dict[str, Any],
    maps_doc_path: Path,
    maps_policy_path: Path,
    maps_latest_path: Path,
) -> dict[str, Any]:
    consumer_id = str(consumer or "").strip() or None
    consumer_profiles = maps_packet_consumer_profiles()
    profile_id = reader_profile or "agent"
    if consumer_id and profile_id == "agent":
        profile_id = consumer_profiles.get(consumer_id, profile_id)
    reader_profiles = maps_packet_reader_profiles()
    profile_route = reader_profiles.get(profile_id, {
        "reader_role": profile_id,
        "purpose": "generic boundary-context reader profile",
        "preferred_axes": [axis] if axis else ["by-owner-route", "by-freshness"],
        "acceptance": "boundary context only; verify source refs with owning layer",
    })
    bounded_limit = max(1, min(safe_int(limit, 20), 50))
    raw_results = query_result.get("results") if isinstance(query_result.get("results"), list) else []
    selected_entries = [maps_packet_entry(entry) for entry in raw_results[:bounded_limit] if isinstance(entry, dict)]
    evidence_refs: list[dict[str, Any]] = []
    seen_refs: set[tuple[str, str]] = set()
    for entry in selected_entries:
        for ref in entry.get("evidence_refs", []):
            if not isinstance(ref, dict):
                continue
            key = (str(ref.get("path") or ""), str(ref.get("truth_level") or ""))
            if key in seen_refs:
                continue
            seen_refs.add(key)
            evidence_refs.append(ref)
    packet_core = {
        "reader_profile": profile_id,
        "consumer": consumer_id,
        "axis": axis,
        "query": query,
        "entry_ids": [entry.get("id") for entry in selected_entries],
        "evidence_paths": [ref.get("path") for ref in evidence_refs if isinstance(ref.get("path"), str)],
    }
    return {
        "schema": _schema(schema_prefix, "maps_packet_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(query_result.get("ok")),
        "packet_id": f"maps-packet:{stable_hash_json(packet_core, 16)}",
        "truth_status": "generated_route_signal_not_source_truth",
        "consumer": consumer_id,
        "reader_profile": profile_id,
        "profile_route": profile_route,
        "axis": axis,
        "query": query,
        "limit": bounded_limit,
        "summary": {
            "entries": len(selected_entries),
            "available_results": len(raw_results),
            "truncated": len(raw_results) > bounded_limit,
            "axes_searched": nested_get(query_result, ["summary", "axes_searched"]),
            "evidence_refs": len(evidence_refs),
            "automatic_action": False,
            "automatic_response": False,
            "memory_writeback": False,
            "proof_verdict": False,
            "kag_truth_publication": False,
        },
        "entries": selected_entries,
        "evidence_refs": evidence_refs,
        "source": {
            "query_command": "abyss-machine maps query --json",
            "validate_command": "abyss-machine maps validate --json",
            "source_contract": str(maps_doc_path),
            "source_policy": str(maps_policy_path),
            "generated_atlas": str(maps_latest_path),
        },
        "consumer_route": {
            "consumer": consumer_id,
            "selected_reader_profile": profile_id,
            "automatic_delivery": False,
            "automatic_acceptance": False,
            "consumer_profiles": consumer_profiles,
        },
        "authority_boundary": {
            "packet_owner": "abyss-machine",
            "packet_role": "bounded boundary-context packet over generated machine atlas route signals",
            "stronger_sources": [
                str(maps_doc_path),
                str(maps_policy_path),
                "/etc/abyss-machine source contracts",
                "/var/lib/abyss-machine generated latest files referenced by evidence_refs",
                "owning external repo for verdicts, reviewed memory, KAG truth, or stack promotion",
                "operator authorization for mutation or private context",
            ],
            "non_claims": [
                "does not execute actions",
                "does not execute responses",
                "does not deliver evidence into AoA organs",
                "does not run retrieval or eval jobs",
                "does not write reviewed memory",
                "does not publish KAG truth",
                "does not authorize mutation",
            ],
        },
        "policy": {
            "generated": True,
            "route_signal_only": True,
            "boundary_context_only": True,
            "reader_profiles_are_not_destinations": True,
            "consumers_are_context_labels_not_destinations": True,
            "raw_private_content": False,
            "automatic_action": False,
            "automatic_response": False,
            "project_roots_readonly": True,
        },
    }


def default_rag_policy(
    *,
    schema_prefix: str,
    version: str,
    rag_doc_path: Path,
    rag_policy_path: Path,
    maps_doc_path: Path,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "rag_policy_v1"),
        "version": version,
        "purpose": "Read-only machine RAG trace loop over atlas context packets and bounded evidence summaries.",
        "source_contract": str(rag_doc_path),
        "source_policy": str(rag_policy_path),
        "maps_contract": str(maps_doc_path),
        "default_axis": "by-rag-run",
        "default_reader_profile": "retrieval-context",
        "limits": {
            "packet_entries": 8,
            "evidence_refs": 12,
            "json_file_max_bytes": 262144,
            "text_file_max_bytes": 65536,
            "text_excerpt_chars": 4000,
            "directory_entries": 24,
        },
        "policy": {
            "generated": True,
            "read_only": True,
            "route_signal_only": True,
            "opens_bounded_evidence_summaries": True,
            "raw_private_content": False,
            "automatic_action": False,
            "automatic_response": False,
            "memory_writeback": False,
            "proof_verdict": False,
            "kag_truth_publication": False,
            "reader_profiles_are_not_destinations": True,
            "aoa_organs_are_external_authorities": True,
        },
    }


def rag_policy_document(
    *,
    schema_prefix: str,
    version: str,
    rag_doc_path: Path,
    rag_policy_path: Path,
    maps_doc_path: Path,
    loaded: dict[str, Any] | None,
    load_error: str | None,
) -> dict[str, Any]:
    defaults = default_rag_policy(
        schema_prefix=schema_prefix,
        version=version,
        rag_doc_path=rag_doc_path,
        rag_policy_path=rag_policy_path,
        maps_doc_path=maps_doc_path,
    )
    if isinstance(loaded, dict):
        rag_section = loaded.get("rag_trace") if isinstance(loaded.get("rag_trace"), dict) else {}
        data = deep_merge(defaults, rag_section)
        data.setdefault("schema", _schema(schema_prefix, "rag_policy_v1"))
        data.setdefault("version", version)
        data["source_policy_schema"] = loaded.get("schema")
        data["source_policy_path"] = str(rag_policy_path)
        if load_error:
            data["_load_error"] = load_error
        return data
    defaults["_load_error"] = load_error
    return defaults


def rag_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    rag_root: Path,
    rag_doc_path: Path,
    rag_policy_path: Path,
    rag_agents_path: Path,
    rag_latest_path: Path,
    rag_index_path: Path,
    trace_root: Path,
    trace_latest_path: Path,
    eval_root: Path,
    eval_latest_path: Path,
    refresh_root: Path,
    refresh_latest_path: Path,
    validate_root: Path,
    validate_latest_path: Path,
    maps_service_path: Path,
    maps_timer_path: Path,
    maps_timer: str,
    maps_latest_path: Path,
    maps_doc_path: Path,
    maps_policy_path: Path,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "rag_paths_v1"),
        "version": version,
        "ok": True,
        "generated_at": generated_at,
        "root": str(rag_root),
        "contract": str(rag_doc_path),
        "policy": str(rag_policy_path),
        "agent_entrypoint": str(rag_agents_path),
        "latest": str(rag_latest_path),
        "index": str(rag_index_path),
        "trace": {
            "root": str(trace_root),
            "latest": str(trace_latest_path),
            "daily_glob": str(trace_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "eval": {
            "root": str(eval_root),
            "latest": str(eval_latest_path),
            "daily_glob": str(eval_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "refresh": {
            "root": str(refresh_root),
            "latest": str(refresh_latest_path),
            "daily_glob": str(refresh_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "service": str(maps_service_path),
            "timer": str(maps_timer_path),
            "unit": maps_timer,
        },
        "validate": {
            "root": str(validate_root),
            "latest": str(validate_latest_path),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "commands": {
            "status": "abyss-machine rag --json",
            "paths": "abyss-machine rag paths --json",
            "policy": "abyss-machine rag policy --json",
            "trace": "abyss-machine rag trace --query TEXT --json",
            "refresh": "abyss-machine rag refresh --query TEXT --json",
            "latest": "abyss-machine rag latest --json",
            "eval": "abyss-machine rag eval --json",
            "validate": "abyss-machine rag validate --json",
            "maps_packet": "abyss-machine maps packet --axis by-rag-run --reader-profile retrieval-context --json",
        },
        "source": {
            "maps_packet": str(maps_latest_path),
            "maps_contract": str(maps_doc_path),
            "maps_policy": str(maps_policy_path),
        },
    }


def rag_answer_from_trace_seed(
    *,
    schema_prefix: str,
    query: str,
    packet: dict[str, Any],
    evidence_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    entries = packet.get("entries") if isinstance(packet.get("entries"), list) else []
    opened = [item for item in evidence_snapshots if item.get("exists")]
    readable = [item for item in opened if str(item.get("status")) in {"json_summary", "text_excerpt", "directory_summary"}]
    claim_refs: list[dict[str, Any]] = []
    for entry in entries[:12]:
        refs = entry.get("evidence_refs") if isinstance(entry, dict) and isinstance(entry.get("evidence_refs"), list) else []
        claim_refs.append({
            "entry_id": entry.get("id") if isinstance(entry, dict) else None,
            "label": entry.get("label") if isinstance(entry, dict) else None,
            "route": entry.get("route") if isinstance(entry, dict) else None,
            "evidence_paths": [ref.get("path") for ref in refs if isinstance(ref, dict) and isinstance(ref.get("path"), str)],
        })
    return {
        "schema": _schema(schema_prefix, "rag_answer_v1"),
        "answer_type": "deterministic_evidence_route_trace",
        "query": query,
        "summary": (
            f"Selected {len(entries)} machine-atlas route entries and opened "
            f"{len(opened)} bounded evidence summaries; {len(readable)} were readable as compact JSON, text, or directory summaries."
        ),
        "claims": [
            "The answer is a route/evidence trace, not source truth.",
            "Every listed entry remains a generated machine-atlas route signal.",
            "Evidence summaries are bounded and redacted; raw private captures are not exposed.",
            "The trace does not execute actions, responses, memory writeback, proof verdicts, or KAG publication.",
        ],
        "claim_refs": claim_refs,
        "non_claims": [
            "not a proof verdict",
            "not reviewed memory",
            "not KAG truth",
            "not operator authorization",
            "not delivery into AoA organs",
        ],
    }


def validation_add(checks: list[dict[str, Any]], level: str, key: str, message: str, data: Any = None) -> None:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if data is not None:
        item["data"] = data
    checks.append(item)


def validation_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    fails = sum(1 for item in checks if item.get("level") == "fail")
    warnings = sum(1 for item in checks if item.get("level") == "warn")
    return {
        "status": "fail" if fails else "warn" if warnings else "ok",
        "fails": fails,
        "warnings": warnings,
        "checks": len(checks),
    }


def validation_document(
    *,
    schema: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    scope: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = validation_summary(checks)
    data: dict[str, Any] = {
        "schema": schema,
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0 and (not strict or summary["warnings"] == 0),
        "strict": strict,
        "scope": scope,
        "summary": summary,
        "checks": checks,
        "policy": {
            "read_only": True,
            "future_safe": True,
            "severity_rule": "fail only for broken contracts or protected-boundary violations; warn for stale, missing optional, or future-expandable evidence",
        },
    }
    if extra:
        data.update(extra)
    return data


def rag_eval_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    trace: dict[str, Any],
) -> dict[str, Any]:
    packet = trace.get("packet") if isinstance(trace.get("packet"), dict) else {}
    summary = trace.get("summary") if isinstance(trace.get("summary"), dict) else {}
    answer = trace.get("answer") if isinstance(trace.get("answer"), dict) else {}
    checks: list[dict[str, Any]] = []
    validation_add(
        checks,
        "ok" if trace.get("schema") == _schema(schema_prefix, "rag_trace_v1") else "fail",
        "trace_schema",
        "trace schema is current",
        {"schema": trace.get("schema")},
    )
    validation_add(
        checks,
        "ok" if packet.get("schema") == _schema(schema_prefix, "maps_packet_v1") and packet.get("truth_status") == "generated_route_signal_not_source_truth" else "fail",
        "maps_packet_contract",
        "trace uses host-owned maps context packet",
        {"schema": packet.get("schema"), "truth_status": packet.get("truth_status")},
    )
    validation_add(
        checks,
        "ok" if safe_int(summary.get("packet_entries"), 0) > 0 else "fail",
        "packet_entries",
        "trace selected at least one atlas entry",
        {"packet_entries": summary.get("packet_entries")},
    )
    validation_add(
        checks,
        "ok" if safe_int(summary.get("evidence_opened"), 0) > 0 else "fail",
        "evidence_opened",
        "trace opened at least one bounded evidence summary",
        {"evidence_opened": summary.get("evidence_opened"), "evidence_missing": summary.get("evidence_missing")},
    )
    packet_summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    forbidden_flags = {
        "automatic_action": packet_summary.get("automatic_action"),
        "automatic_response": packet_summary.get("automatic_response"),
        "memory_writeback": packet_summary.get("memory_writeback"),
        "proof_verdict": packet_summary.get("proof_verdict"),
        "kag_truth_publication": packet_summary.get("kag_truth_publication"),
    }
    validation_add(
        checks,
        "ok" if all(value is False for value in forbidden_flags.values()) else "fail",
        "non_action_packet",
        "packet disables action, response, proof, memory, and KAG side effects",
        forbidden_flags,
    )
    non_claims = answer.get("non_claims") if isinstance(answer.get("non_claims"), list) else []
    validation_add(
        checks,
        "ok" if {"not a proof verdict", "not reviewed memory", "not KAG truth", "not delivery into AoA organs"}.issubset(set(str(item) for item in non_claims)) else "fail",
        "authority_boundary",
        "answer preserves proof, memory, KAG, and organ boundaries",
        {"non_claims": non_claims},
    )
    return validation_document(
        schema=_schema(schema_prefix, "rag_eval_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=False,
        scope="machine RAG trace eval",
        extra={
            "trace_id": trace.get("trace_id"),
            "trace_sha256": stable_hash_json(trace, 64),
            "score": {
                "checks": len(checks),
                "fails": sum(1 for check in checks if check.get("level") == "fail"),
                "warnings": sum(1 for check in checks if check.get("level") == "warn"),
            },
            "policy": {
                "evaluates_trace_quality_only": True,
                "proof_verdict": False,
                "memory_writeback": False,
                "kag_truth_publication": False,
                "automatic_action": False,
            },
        },
    )


def rag_eval_missing_trace_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    trace_latest_path: Path,
    error: Any,
) -> dict[str, Any]:
    return validation_document(
        schema=_schema(schema_prefix, "rag_eval_v1"),
        version=version,
        generated_at=generated_at,
        checks=[
            {
                "level": "fail",
                "key": "trace_latest",
                "message": "latest RAG trace is missing or invalid",
                "data": {"path": str(trace_latest_path), "error": error},
            }
        ],
        strict=False,
        scope="machine RAG trace eval",
        extra={"policy": {"proof_verdict": False, "memory_writeback": False, "automatic_action": False}},
    )


def rag_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
    latest_trace: dict[str, Any] | None,
    latest_eval: dict[str, Any] | None,
) -> dict[str, Any]:
    trace_data = latest_trace if isinstance(latest_trace, dict) else {}
    eval_data = latest_eval if isinstance(latest_eval, dict) else {}
    return validation_document(
        schema=_schema(schema_prefix, "rag_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="machine RAG trace loop",
        extra={
            "paths": dict(paths) if isinstance(paths, dict) else {},
            "latest_trace": {
                "trace_id": trace_data.get("trace_id"),
                "summary": trace_data.get("summary") if isinstance(trace_data.get("summary"), dict) else None,
            },
            "latest_eval": {
                "ok": eval_data.get("ok"),
                "summary": eval_data.get("summary") if isinstance(eval_data.get("summary"), dict) else None,
            },
            "non_claims": [
                "RAG traces are generated evidence routes, not source truth.",
                "RAG evals check trace quality only; they do not create proof verdicts.",
                "RAG traces do not write reviewed memory, publish KAG truth, execute actions, or deliver evidence into AoA organs.",
            ],
        },
    )


def rag_trace_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    query_text: str,
    axis_id: str,
    profile: str,
    packet: dict[str, Any],
    evidence_snapshots: list[dict[str, Any]],
    answer: dict[str, Any],
    policy: dict[str, Any],
    rag_doc_path: Path,
    rag_policy_path: Path,
    maps_doc_path: Path,
    query_fallback: bool,
) -> dict[str, Any]:
    trace_core = {
        "query": query_text,
        "axis": axis_id,
        "reader_profile": profile,
        "packet_id": packet.get("packet_id"),
        "evidence_paths": [item.get("path") for item in evidence_snapshots],
        "fallback": query_fallback,
    }
    return {
        "schema": _schema(schema_prefix, "rag_trace_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(packet.get("ok")) and bool(packet.get("entries")) and bool(evidence_snapshots),
        "trace_id": f"rag-trace:{stable_hash_json(trace_core, 16)}",
        "query": query_text,
        "axis": axis_id,
        "reader_profile": profile,
        "query_fallback_to_axis": query_fallback,
        "truth_status": "generated_trace_not_source_truth",
        "summary": {
            "packet_entries": len(packet.get("entries") if isinstance(packet.get("entries"), list) else []),
            "packet_available_results": nested_get(packet, ["summary", "available_results"]),
            "evidence_refs": len(packet.get("evidence_refs") if isinstance(packet.get("evidence_refs"), list) else []),
            "evidence_opened": sum(1 for item in evidence_snapshots if item.get("exists")),
            "evidence_missing": sum(1 for item in evidence_snapshots if not item.get("exists")),
            "automatic_action": False,
            "automatic_response": False,
            "memory_writeback": False,
            "proof_verdict": False,
            "kag_truth_publication": False,
        },
        "packet": packet,
        "evidence_snapshots": evidence_snapshots,
        "answer": answer,
        "source": {
            "maps_packet_command": "abyss-machine maps packet --axis by-rag-run --reader-profile retrieval-context --json",
            "validate_command": "abyss-machine rag validate --json",
            "source_contract": str(rag_doc_path),
            "source_policy": str(rag_policy_path),
            "maps_contract": str(maps_doc_path),
        },
        "authority_boundary": {
            "owner": "abyss-machine",
            "role": "read-only machine RAG trace over host atlas route signals and bounded evidence summaries",
            "stronger_sources": [
                str(rag_doc_path),
                str(rag_policy_path),
                str(maps_doc_path),
                "/etc/abyss-machine source contracts",
                "/var/lib/abyss-machine generated latest files referenced by evidence snapshots",
                "owning external repo for proof, reviewed memory, KAG truth, or stack promotion",
            ],
            "non_claims": answer["non_claims"],
        },
        "policy": policy.get("policy"),
    }


def rag_index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    rag_root: Path,
    rag_latest_path: Path,
    trace_latest_path: Path,
    eval_latest_path: Path,
    refresh_latest_path: Path,
    validate_latest_path: Path,
    rag_doc_path: Path,
    rag_policy_path: Path,
    trace: dict[str, Any] | None,
    trace_error: str | None,
    eval_doc: dict[str, Any] | None,
    eval_error: str | None,
    commands: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "rag_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "root": str(rag_root),
        "latest": str(rag_latest_path),
        "trace_latest": str(trace_latest_path),
        "eval_latest": str(eval_latest_path),
        "refresh_latest": str(refresh_latest_path),
        "validate_latest": str(validate_latest_path),
        "latest_trace": {
            "trace_id": trace.get("trace_id") if isinstance(trace, dict) else None,
            "generated_at": trace.get("generated_at") if isinstance(trace, dict) else None,
            "summary": trace.get("summary") if isinstance(trace, dict) else None,
            "load_error": trace_error,
        },
        "latest_eval": {
            "ok": eval_doc.get("ok") if isinstance(eval_doc, dict) else None,
            "summary": eval_doc.get("summary") if isinstance(eval_doc, dict) else None,
            "load_error": eval_error,
        },
        "commands": commands,
        "policy": {
            "generated": True,
            "do_not_hand_edit": True,
            "source_contract": str(rag_doc_path),
            "source_policy": str(rag_policy_path),
        },
    }


def rag_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    latest_trace_exists: bool,
    trace_error: str | None,
    latest_trace: dict[str, Any] | None,
    latest_eval_exists: bool,
    eval_error: str | None,
    latest_eval: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "rag_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": not trace_error and not eval_error if latest_trace_exists or latest_eval_exists else True,
        "paths": paths,
        "latest_trace": {
            "exists": latest_trace_exists,
            "load_error": trace_error,
            "trace_id": latest_trace.get("trace_id") if isinstance(latest_trace, dict) else None,
            "summary": latest_trace.get("summary") if isinstance(latest_trace, dict) else None,
        },
        "latest_eval": {
            "exists": latest_eval_exists,
            "load_error": eval_error,
            "ok": latest_eval.get("ok") if isinstance(latest_eval, dict) else None,
            "summary": latest_eval.get("summary") if isinstance(latest_eval, dict) else None,
        },
        "policy": policy.get("policy"),
    }


def rag_refresh_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    query: str,
    axis: str,
    reader_profile: str,
    maps_doc: dict[str, Any],
    maps_check: dict[str, Any],
    trace: dict[str, Any],
    rag_check: dict[str, Any],
    maps_latest_path: Path,
    maps_validate_latest_path: Path,
    rag_trace_latest_path: Path,
    rag_eval_latest_path: Path,
    rag_validate_latest_path: Path,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "rag_refresh_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(maps_doc.get("ok")) and bool(maps_check.get("ok")) and bool(trace.get("ok")) and bool(rag_check.get("ok")),
        "query": query,
        "axis": axis,
        "reader_profile": reader_profile,
        "summary": {
            "maps_axes": nested_get(maps_doc, ["summary", "axes"]),
            "maps_entries": nested_get(maps_doc, ["summary", "entries"]),
            "maps_validate_status": nested_get(maps_check, ["summary", "status"]),
            "trace_id": trace.get("trace_id"),
            "trace_packet_entries": nested_get(trace, ["summary", "packet_entries"]),
            "trace_evidence_opened": nested_get(trace, ["summary", "evidence_opened"]),
            "rag_validate_status": nested_get(rag_check, ["summary", "status"]),
            "automatic_action": False,
            "automatic_response": False,
            "memory_writeback": False,
            "proof_verdict": False,
            "kag_truth_publication": False,
        },
        "generated": {
            "maps_latest": str(maps_latest_path),
            "maps_validate_latest": str(maps_validate_latest_path),
            "rag_trace_latest": str(rag_trace_latest_path),
            "rag_eval_latest": str(rag_eval_latest_path),
            "rag_validate_latest": str(rag_validate_latest_path),
        },
        "checks": {
            "maps": {
                "ok": maps_doc.get("ok"),
                "summary": maps_doc.get("summary"),
            },
            "maps_validate": {
                "ok": maps_check.get("ok"),
                "summary": maps_check.get("summary"),
            },
            "rag_trace": {
                "ok": trace.get("ok"),
                "trace_id": trace.get("trace_id"),
                "summary": trace.get("summary"),
            },
            "rag_validate": {
                "ok": rag_check.get("ok"),
                "summary": rag_check.get("summary"),
            },
        },
        "policy": {
            "generated": True,
            "read_only": True,
            "refreshes_generated_context_only": True,
            "automatic_action": False,
            "automatic_response": False,
            "memory_writeback": False,
            "proof_verdict": False,
            "kag_truth_publication": False,
            "aoa_organs_are_external_authorities": True,
        },
        "paths": paths,
    }
