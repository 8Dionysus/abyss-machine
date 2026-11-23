"""Retrieval and evidence atlas (rag, maps) organ CLI, moved out of the abyss_machine core CLI.

`abyss_machine.cli` keeps the `rag`, `maps` command names and
delegates here lazily. Shared core helpers are reached as `_core.<name>`,
so callers and tests that patch `abyss_machine.cli` keep the same effect.
"""

from __future__ import annotations

import argparse
import array
import concurrent.futures
from contextlib import contextmanager
import datetime as dt
import fcntl
import fnmatch
import grp
import hashlib
import importlib.util
import json
import os
import platform
import re
import resource
import secrets
import signal
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from abyss_machine import cli as _core

_ORGAN_PACKAGE = "abyss_machine.organs.knowledge"
sys.dont_write_bytecode = True

ai_cli = _core._lazy_import_module("abyss_machine.organs.ai.cli", allow_eager=False)


MAPS_START_PATH = _core.MAPS_ROOT / "START.md"


MAPS_USER_SYSTEMD_DIR = _core.path_from_env("ABYSS_MACHINE_USER_SYSTEMD_DIR", _core.PATH_POLICY.systemd_user_dir or _core.PATH_POLICY.home / ".config/systemd/user")


MAPS_SERVICE = "abyss-machine-context-refresh.service"


MAPS_SERVICE_PATH = MAPS_USER_SYSTEMD_DIR / MAPS_SERVICE


MAPS_TIMER_PATH = MAPS_USER_SYSTEMD_DIR / _core.MAPS_TIMER


def maps_axis_definitions() -> list[dict[str, str]]:
    return _core.context_contracts.maps_axis_definitions()


def default_maps_policy() -> dict[str, Any]:
    return _core.context_contracts.default_maps_policy(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        maps_doc_path=_core.MAPS_DOC_PATH,
    )


def maps_policy_document() -> dict[str, Any]:
    loaded, error = _core.load_json_document(_core.MAPS_POLICY_PATH)
    return _core.context_contracts.maps_policy_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        maps_doc_path=_core.MAPS_DOC_PATH,
        loaded=loaded,
        load_error=error,
    )


def maps_paths() -> dict[str, Any]:
    return _core.context_contracts.maps_paths_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        maps_root=_core.MAPS_ROOT,
        maps_doc_path=_core.MAPS_DOC_PATH,
        maps_policy_path=_core.MAPS_POLICY_PATH,
        maps_agents_path=_core.MAPS_AGENTS_PATH,
        maps_start_path=MAPS_START_PATH,
        maps_latest_path=_core.MAPS_LATEST_PATH,
        maps_index_path=_core.MAPS_INDEX_PATH,
        maps_validate_latest_path=_core.MAPS_VALIDATE_LATEST_PATH,
        history_today=_core.ai_daily_jsonl_path(_core.MAPS_ROOT),
        service_path=MAPS_SERVICE_PATH,
        timer_path=MAPS_TIMER_PATH,
        timer_unit=_core.MAPS_TIMER,
    )


def maps_source_ref(path: Path, truth_level: str, note: str | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "path": str(path),
        "truth_level": truth_level,
        "exists": path.exists(),
    }
    if note:
        ref["note"] = note
    if path.exists() and path.is_file():
        try:
            stat = path.stat()
            ref["size_bytes"] = stat.st_size
            ref["mtime"] = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds")
            if stat.st_size <= _core.safe_int(_core.nested_get(maps_policy_document(), ["limits", "hash_file_max_bytes"]), 1048576):
                raw = path.read_bytes()
                ref["sha256"] = hashlib.sha256(raw).hexdigest()
                if path.suffix == ".json":
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                        if isinstance(payload, dict):
                            ref["schema"] = payload.get("schema")
                            ref["generated_at"] = payload.get("generated_at")
                            ref["ok"] = payload.get("ok")
                            if isinstance(payload.get("summary"), dict):
                                ref["summary"] = payload.get("summary")
                            elif isinstance(payload.get("readiness"), dict):
                                ref["summary"] = payload.get("readiness")
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        pass
        except OSError as exc:
            ref["error"] = str(exc)
    return ref


def maps_entry(
    axis: str,
    label: str,
    route: str,
    summary: str,
    evidence_refs: list[dict[str, Any]],
    *,
    owner_route: str = "abyss-machine",
    tags: list[str] | None = None,
    next_commands: list[str] | None = None,
    freshness: str | None = None,
    actionability: str = "route_signal_only",
) -> dict[str, Any]:
    return _core.context_contracts.maps_entry(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        axis=axis,
        label=label,
        route=route,
        summary=summary,
        evidence_refs=evidence_refs,
        owner_route=owner_route,
        tags=tags,
        next_commands=next_commands,
        freshness=freshness,
        actionability=actionability,
    )


def maps_surface_latest_specs() -> list[tuple[str, Path, str, str]]:
    return [
        ("topology", _core.TOPOLOGY_LATEST_PATH, "generated_contract_topology", "by-time"),
        ("graph", _core.GRAPH_LATEST_PATH, "generated_contract_graph", "by-time"),
        ("docs_audit", _core.DOCS_LATEST_PATH, "generated_docs_audit", "by-time"),
        ("changes_index", _core.CHANGE_INDEX_PATH, "generated_change_index", "by-time"),
        ("nervous_brief", _core.NERVOUS_BRIEF_LATEST_PATH, "generated_nervous_brief", "by-time"),
        ("nervous_events", _core.NERVOUS_EVENTS_LATEST_PATH, "generated_nervous_events", "by-event-type"),
        ("nervous_episodes", _core.NERVOUS_EPISODES_LATEST_PATH, "generated_nervous_episodes", "by-episode"),
        ("nervous_index", _core.NERVOUS_SEARCH_INDEX_LATEST_PATH, "generated_nervous_index", "by-freshness"),
        ("nervous_semantic", _core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH, "generated_semantic_index", "by-freshness"),
        ("nervous_retrieval", _core.NERVOUS_RETRIEVAL_LATEST_PATH, "generated_retrieval_pack", "by-rag-run"),
        ("nervous_rerank", _core.NERVOUS_RERANK_LATEST_PATH, "generated_rerank_pack", "by-rag-run"),
        ("machine_rag_trace", _core.RAG_TRACE_LATEST_PATH, "generated_rag_trace", "by-rag-run"),
        ("machine_rag_eval", _core.RAG_EVAL_LATEST_PATH, "generated_rag_eval", "by-eval-packet"),
        ("nervous_synthesis", _core.NERVOUS_SYNTHESIS_LATEST_PATH, "generated_synthesis_candidate", "by-causal-chain"),
        ("nervous_eval", _core.NERVOUS_EVALS_LATEST_PATH, "generated_nervous_eval", "by-eval-packet"),
        ("reactions", _core.REACTIONS_LATEST_PATH, "generated_reaction_candidates", "by-actionability"),
        ("responses", _core.RESPONSES_LATEST_PATH, "generated_response_routes", "by-actionability"),
        ("heartbeats", _core.HEARTBEATS_LATEST_PATH, "generated_heartbeat", "by-correlation"),
        ("resource_orchestrator", _core.RESOURCE_ORCHESTRATOR_LATEST_PATH, "generated_resource_orchestrator", "by-resource-state"),
        ("memory_plan", _core.MEMORY_PLAN_LATEST_PATH, "generated_memory_plan", "by-resource-state"),
        ("storage_pressure", _core.STORAGE_PRESSURE_LATEST_PATH, "generated_storage_pressure", "by-resource-state"),
        ("cooling_latest", _core.COOLING_LATEST_PATH, "generated_cooling_status", "by-resource-state"),
        ("mode_latest", _core.MODE_LATEST_PATH, "generated_work_mode", "by-resource-state"),
        ("typing_process", _core.TYPING_PROCESS_LATEST_PATH, "generated_typing_causal_process", "by-correlation"),
        ("memo_port_index", _core.STATE_DIR / "memo" / "index.min.json", "generated_memo_port_index", "by-memory-candidate"),
    ]


def maps_entries_by_axis() -> dict[str, list[dict[str, Any]]]:
    entries: dict[str, list[dict[str, Any]]] = {axis["axis"]: [] for axis in maps_axis_definitions()}

    latest_records: list[dict[str, Any]] = []
    for label, path, truth_level, default_axis in maps_surface_latest_specs():
        ref = maps_source_ref(path, truth_level)
        if not ref.get("exists"):
            continue
        generated_at = ref.get("generated_at") or ref.get("mtime")
        latest_records.append({"label": label, "path": path, "ref": ref, "axis": default_axis, "generated_at": generated_at})
        entries["by-time"].append(maps_entry(
            "by-time",
            label,
            f"Open {path}",
            f"{label} latest read model generated at {generated_at or 'unknown time'}.",
            [ref],
            tags=["latest", label],
            freshness="known" if generated_at else "unknown",
        ))

    for name, spec in _core.subsystem_specs().items():
        latest_path = Path(spec.get("latest"))
        refs = [maps_source_ref(latest_path, "subsystem_validator_latest")]
        for doc_path in spec.get("docs", []) or []:
            refs.append(maps_source_ref(Path(doc_path), "subsystem_route_card_or_contract"))
        entries["by-subsystem"].append(maps_entry(
            "by-subsystem",
            name,
            f"Run abyss-machine {name} validate --json" if name not in {"maps"} else "Run abyss-machine maps validate --json",
            f"{name} owns a host-machine subsystem route and validation surface.",
            refs,
            tags=["subsystem", name],
            next_commands=[f"abyss-machine {name} validate --json" if name not in {"maps"} else "abyss-machine maps validate --json"],
        ))

    events_latest, _ = _core.load_json_document(_core.NERVOUS_EVENTS_LATEST_PATH)
    events_summary = events_latest.get("summary") if isinstance(events_latest, dict) and isinstance(events_latest.get("summary"), dict) else {}
    for category, count in sorted((events_summary.get("by_category") or {}).items()):
        entries["by-event-type"].append(maps_entry(
            "by-event-type",
            f"event category {category}",
            f"Search events for category {category}",
            f"Nervous event layer has {count} events in category {category}.",
            [maps_source_ref(_core.NERVOUS_EVENTS_LATEST_PATH, "generated_nervous_events")],
            tags=["event_category", str(category)],
            next_commands=[f"abyss-machine nervous search --query {shlex.quote(str(category))} --source nervous_events --json"],
        ))
    for severity, count in sorted((events_summary.get("by_severity") or {}).items()):
        entries["by-event-type"].append(maps_entry(
            "by-event-type",
            f"event severity {severity}",
            f"Search events with severity {severity}",
            f"Nervous event layer has {count} events with severity {severity}.",
            [maps_source_ref(_core.NERVOUS_EVENTS_LATEST_PATH, "generated_nervous_events")],
            tags=["event_severity", str(severity)],
            next_commands=[f"abyss-machine nervous search --query {shlex.quote(str(severity))} --source nervous_events --json"],
        ))

    episodes_latest, _ = _core.load_json_document(_core.NERVOUS_EPISODES_LATEST_PATH)
    episodes_summary = episodes_latest.get("summary") if isinstance(episodes_latest, dict) and isinstance(episodes_latest.get("summary"), dict) else {}
    for category, count in sorted((episodes_summary.get("by_category") or {}).items()):
        entries["by-episode"].append(maps_entry(
            "by-episode",
            f"episode category {category}",
            f"Search episodes for category {category}",
            f"Nervous episode layer has {count} grouped episodes in category {category}.",
            [maps_source_ref(_core.NERVOUS_EPISODES_LATEST_PATH, "generated_nervous_episodes")],
            tags=["episode_category", str(category)],
            next_commands=[f"abyss-machine nervous search --query {shlex.quote(str(category))} --source nervous_episodes --json"],
        ))

    chain_specs = [
        ("passive chronicle to brief", "facts -> events -> episodes -> index -> brief", [_core.NERVOUS_FACTS_LATEST_PATH, _core.NERVOUS_EVENTS_LATEST_PATH, _core.NERVOUS_EPISODES_LATEST_PATH, _core.NERVOUS_SEARCH_INDEX_LATEST_PATH, _core.NERVOUS_BRIEF_LATEST_PATH], ["abyss-machine nervous quality-audit --json"]),
        ("evidence to action route", "nervous/doctor/resource evidence -> reactions -> responses -> owner approval", [_core.REACTIONS_LATEST_PATH, _core.RESPONSES_LATEST_PATH], ["abyss-machine reactions --json", "abyss-machine responses --json"]),
        ("change to validation", "change ledger -> source edits -> validators -> decision review closeout", [_core.CHANGE_INDEX_PATH, _core.CHANGE_PREFLIGHT_LATEST_PATH], ["abyss-machine changes status --json"]),
        ("retrieval to proof-context", "RAG/retrieval trace -> host eval evidence -> agent proof-context packet", [Path("/srv/abyss-machine/PLANS.md"), _core.NERVOUS_EVALS_LATEST_PATH], ["abyss-machine maps query --axis by-eval-packet --json"]),
        ("runtime evidence to memory-context", "host evidence -> memo candidate port -> agent memory-context packet", [_core.STATE_DIR / "memo" / "index.min.json"], ["abyss-machine maps query --axis by-memory-candidate --json"]),
        ("derived graph to knowledge-context", "host graph/map signal -> provenance refs -> agent knowledge-context packet", [_core.GRAPH_LATEST_PATH, _core.MAPS_DOC_PATH], ["abyss-machine graph validate --json", "abyss-machine maps validate --json"]),
    ]
    for label, summary, paths, commands in chain_specs:
        entries["by-causal-chain"].append(maps_entry(
            "by-causal-chain",
            label,
            summary,
            f"Route chain: {summary}.",
            [maps_source_ref(path, "chain_evidence_or_contract") for path in paths],
            tags=["causal_chain"],
            next_commands=commands,
        ))

    owner_specs = [
        ("host contracts", "/etc/abyss-machine", "Stable policy, contracts, command catalog, and maps source law.", [_core.MAPS_DOC_PATH, _core.MAPS_POLICY_PATH]),
        ("host compact state", "/var/lib/abyss-machine", "Generated compact facts, validators, maps, graph, nervous read models.", [_core.STATE_DIR / "AGENTS.md", _core.MAPS_LATEST_PATH]),
        ("host large storage", "/srv/abyss-machine", "Large caches, runtimes, private nervous captures, graph backing stores.", [_core.ABYSS_MACHINE_ROOT / "AGENTS.md"]),
        ("aoa-evals", "/srv/AbyssOS/aoa-evals", "Bounded proof/eval authority; machine context is only external boundary evidence for an agent to verify.", [Path("/srv/AbyssOS/aoa-evals/AGENTS.md")]),
        ("aoa-memo", "/srv/AbyssOS/aoa-memo", "Reviewed memory-object authority; host memo port remains a candidate source outside reviewed memory.", [Path("/srv/AbyssOS/aoa-memo/AGENTS.md")]),
        ("aoa-kag", "/srv/AbyssOS/aoa-kag", "Derived provenance-aware KAG substrate authority.", [Path("/srv/AbyssOS/aoa-kag/AGENTS.md")]),
        ("abyss-stack", "/srv/AbyssOS/abyss-stack", "Runtime/service authority; host layer remains read-only toward project truth.", [Path("/srv/AbyssOS/abyss-stack/AGENTS.md")]),
    ]
    for label, route, summary, paths in owner_specs:
        entries["by-owner-route"].append(maps_entry(
            "by-owner-route",
            label,
            route,
            summary,
            [maps_source_ref(path, "owner_route_card_or_contract") for path in paths],
            owner_route=label,
            tags=["owner_route"],
        ))

    brief, _ = _core.load_json_document(_core.NERVOUS_BRIEF_LATEST_PATH)
    readiness = brief.get("readiness") if isinstance(brief, dict) and isinstance(brief.get("readiness"), dict) else {}
    for key, value in sorted(readiness.items()):
        freshness = "stale" if key.endswith("_stale") and value else "maintenance_needed" if key.endswith("_needed") and value else "ready" if value else "not_ready"
        entries["by-freshness"].append(maps_entry(
            "by-freshness",
            key,
            "Open nervous brief readiness",
            f"Nervous readiness {key}={value}.",
            [maps_source_ref(_core.NERVOUS_BRIEF_LATEST_PATH, "generated_nervous_brief")],
            tags=["freshness", key],
            freshness=freshness,
            next_commands=["abyss-machine nervous brief --scope now --json"],
        ))

    for label, path in [
        ("resource orchestrator", _core.RESOURCE_ORCHESTRATOR_LATEST_PATH),
        ("resource plan", _core.RESOURCE_PLAN_LATEST_PATH),
        ("memory plan", _core.MEMORY_PLAN_LATEST_PATH),
        ("storage pressure", _core.STORAGE_PRESSURE_LATEST_PATH),
        ("cooling", _core.COOLING_LATEST_PATH),
        ("mode", _core.MODE_LATEST_PATH),
    ]:
        entries["by-resource-state"].append(maps_entry(
            "by-resource-state",
            label,
            f"Open {path}",
            f"{label} is a current resource/readiness input for safe future work.",
            [maps_source_ref(path, "resource_state")],
            tags=["resource_state"],
            next_commands=["abyss-machine resource orchestrator --json"],
        ))

    for label, path, summary in [
        ("privacy status", _core.NERVOUS_PRIVACY_LATEST_PATH, "Nervous privacy gates and pause/private-mode state."),
        ("browser content capture", _core.NERVOUS_BROWSER_CONTENT_LATEST_PATH, "Browser capture is local-private, redacted, and login-sensitive pages are skipped."),
        ("typing validate", _core.TYPING_VALIDATE_LATEST_PATH, "Typed-text intake must preserve non-keylogger and password-field boundaries."),
        ("storage policy", _core.STORAGE_POLICY_PATH, "Protected roots and large-artifact routing policy."),
    ]:
        entries["by-risk-privacy"].append(maps_entry(
            "by-risk-privacy",
            label,
            f"Open {path}",
            summary,
            [maps_source_ref(path, "privacy_or_boundary_contract")],
            tags=["risk_privacy"],
        ))

    reactions, _ = _core.load_json_document(_core.REACTIONS_LATEST_PATH)
    responses, _ = _core.load_json_document(_core.RESPONSES_LATEST_PATH)
    changes, _ = _core.load_json_document(_core.CHANGE_INDEX_PATH)
    for label, path, payload in [("reactions", _core.REACTIONS_LATEST_PATH, reactions), ("responses", _core.RESPONSES_LATEST_PATH, responses), ("changes", _core.CHANGE_INDEX_PATH, changes)]:
        summary = payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {}
        entries["by-actionability"].append(maps_entry(
            "by-actionability",
            label,
            f"Open {path}",
            f"{label} actionability summary: {summary}.",
            [maps_source_ref(path, "actionability_read_model")],
            tags=["actionability"],
            actionability="owner_gated" if label in {"reactions", "responses"} else "change_ledger",
            next_commands=["abyss-machine responses --json"] if label == "responses" else ["abyss-machine changes status --json"],
        ))

    for label, path in [
        ("active change correlation", _core.CHANGE_INDEX_PATH),
        ("heartbeat correlation", _core.HEARTBEATS_LATEST_PATH),
        ("typing causal process", _core.TYPING_PROCESS_LATEST_PATH),
        ("nervous synthesis", _core.NERVOUS_SYNTHESIS_LATEST_PATH),
    ]:
        entries["by-correlation"].append(maps_entry(
            "by-correlation",
            label,
            f"Open {path}",
            f"{label} can connect events across host time and route surfaces.",
            [maps_source_ref(path, "correlation_read_model")],
            tags=["correlation"],
        ))

    for label, path, command in [
        ("nervous recall/retrieval", _core.NERVOUS_RETRIEVAL_LATEST_PATH, "abyss-machine nervous recall --mode hybrid --query TEXT --json"),
        ("nervous rerank", _core.NERVOUS_RERANK_LATEST_PATH, "abyss-machine nervous rerank --query TEXT --json"),
        ("semantic index", _core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH, "abyss-machine nervous semantic-status --json"),
        ("machine RAG trace", _core.RAG_TRACE_LATEST_PATH, "abyss-machine rag trace --query TEXT --json"),
        ("RAG/KAG plan", Path("/srv/abyss-machine/PLANS.md"), "abyss-machine maps query --axis by-rag-run --json"),
    ]:
        entries["by-rag-run"].append(maps_entry(
            "by-rag-run",
            label,
            f"Open {path}",
            f"{label} is part of retrieval/GraphRAG/Agentic RAG evidence routing.",
            [maps_source_ref(path, "rag_or_retrieval_evidence")],
            tags=["rag", "retrieval"],
            next_commands=[command],
        ))

    for label, path in [
        ("host memo port", _core.STATE_DIR / "memo" / "index.min.json"),
        ("memo candidates", _core.STATE_DIR / "memo" / "candidates"),
    ]:
        entries["by-memory-candidate"].append(maps_entry(
            "by-memory-candidate",
            label,
            f"Open {path}",
            "Host evidence may inform memory work only through candidate/review routes.",
            [maps_source_ref(path, "memory_candidate_route")],
            owner_route="abyss-machine memo port",
            tags=["memory_candidate"],
        ))

    for label, path in [
        ("nervous eval latest", _core.NERVOUS_EVALS_LATEST_PATH),
        ("machine RAG eval latest", _core.RAG_EVAL_LATEST_PATH),
        ("AI eval latest", ai_cli.AI_EVAL_LATEST_PATH),
        ("LLM resident eval latest", _core.AI_LLM_RESIDENT_EVALS_LATEST_PATH),
    ]:
        entries["by-eval-packet"].append(maps_entry(
            "by-eval-packet",
            label,
            f"Open {path}",
            "Evaluation material is host-side evidence; proof authority remains outside abyss-machine.",
            [maps_source_ref(path, "eval_packet_or_route")],
            owner_route="abyss-machine",
            tags=["eval_packet"],
        ))

    for label, path in [
        ("host graph", _core.GRAPH_LATEST_PATH),
        ("machine atlas", _core.MAPS_LATEST_PATH),
    ]:
        entries["by-kag-export"].append(maps_entry(
            "by-kag-export",
            label,
            f"Open {path}",
            "KAG export material is host-side projection evidence; canonical derived KAG truth belongs outside abyss-machine.",
            [maps_source_ref(path, "kag_candidate_route")],
            owner_route="abyss-machine",
            tags=["kag_export"],
        ))

    return entries


def maps_axis_index_markdown(axis: dict[str, str], entries: list[dict[str, Any]]) -> str:
    return _core.context_contracts.maps_axis_index_markdown(axis, entries)


def maps_start_markdown(data: dict[str, Any]) -> str:
    return _core.context_contracts.maps_start_markdown(data)


def write_machine_maps_files(data: dict[str, Any], entries_by_axis: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    try:
        _core.MAPS_ROOT.mkdir(parents=True, exist_ok=True)
        if _core.MAPS_ROOT.is_symlink():
            raise OSError("maps root must not be a symlink")
        flags = os.O_RDONLY | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        lock_fd = os.open(_core.MAPS_ROOT / ".write.lock", flags, 0o664)
        with os.fdopen(lock_fd, "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            axis_lookup = {axis["axis"]: axis for axis in maps_axis_definitions()}
            write_entries = _core.nested_get(maps_policy_document(), ["limits", "write_entry_files"]) is not False
            published: dict[Path, tuple[str, set[str]]] = {}
            for axis_id, entries in entries_by_axis.items():
                axis_root = _core.MAPS_ROOT / axis_id
                entries_root = axis_root / "entries"
                if axis_id not in axis_lookup or axis_root.is_symlink() or entries_root.is_symlink():
                    errors.append({"path": str(axis_root), "error": "unknown or symlinked maps axis"})
                    continue
                try:
                    entries_root.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    errors.append({"path": str(entries_root), "error": str(exc)})
                    continue
                axis_errors: list[dict[str, Any]] = []
                expected: set[str] = set()
                if write_entries:
                    for entry in entries:
                        filename = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(entry.get("id") or _core.stable_hash_json(entry, 16))).strip("-") + ".json"
                        expected.add(filename)
                        error = _core.safe_atomic_write_json(entries_root / filename, entry, 0o664)
                        if error:
                            axis_errors.append(error)
                if axis_errors:
                    errors.extend(axis_errors)
                    continue
                axis_doc = {
                    "schema": f"{_core.SCHEMA_PREFIX}_maps_axis_index_v1",
                    "version": _core.VERSION,
                    "generated_at": data.get("generated_at"),
                    "axis": axis_id,
                    "question": axis_lookup[axis_id].get("question"),
                    "truth_status": data.get("truth_status"),
                    "entry_count": len(entries),
                    "entries": entries,
                }
                for error in [
                    _core.safe_atomic_write_json(axis_root / "index.json", axis_doc, 0o664),
                    _core.safe_atomic_write_text(axis_root / "INDEX.md", maps_axis_index_markdown(axis_lookup[axis_id], entries), 0o664),
                ]:
                    if error:
                        axis_errors.append(error)
                errors.extend(axis_errors)
                if write_entries and not axis_errors:
                    published[entries_root] = (axis_id, expected)
            if errors:
                return errors
            for error in [
                _core.safe_atomic_write_json(_core.MAPS_LATEST_PATH, data, 0o664),
                _core.safe_atomic_write_json(_core.MAPS_INDEX_PATH, maps_index_document(data), 0o664),
                _core.safe_atomic_write_text(MAPS_START_PATH, maps_start_markdown(data), 0o664),
                _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.MAPS_ROOT), data, 0o664),
            ]:
                if error:
                    errors.append(error)
            if errors:
                return errors
            # Prune only displaced generated cards after successful publication.
            # The same lock serializes publication and pruning across writers.
            for entries_root, (axis_id, expected) in published.items():
                pattern = re.compile(re.escape(axis_id) + r":[0-9a-f]{16}\.json")
                with os.scandir(entries_root) as cards:
                    for card in cards:
                        if card.name in expected or not pattern.fullmatch(card.name) or not card.is_file(follow_symlinks=False):
                            continue
                        if card.stat(follow_symlinks=False).st_nlink != 1:
                            continue
                        path = Path(card.path)
                        try:
                            old = json.loads(path.read_text(encoding="utf-8"))
                        except (ValueError, UnicodeError):
                            continue
                        if not isinstance(old, dict) or old.get("schema") != f"{_core.SCHEMA_PREFIX}_maps_entry_v1" or old.get("axis") != axis_id or old.get("id") != path.stem or old.get("truth_status") != "generated_route_signal_not_source_truth":
                            continue
                        path.unlink()
    except OSError as exc:
        errors.append({"path": str(_core.MAPS_ROOT), "error": str(exc)})
    return errors


def machine_maps(write_latest: bool = True) -> dict[str, Any]:
    policy = maps_policy_document()
    entries_by_axis = maps_entries_by_axis()
    data = _core.context_contracts.maps_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        maps_root=_core.MAPS_ROOT,
        maps_start_path=MAPS_START_PATH,
        maps_index_path=_core.MAPS_INDEX_PATH,
        maps_policy_path=_core.MAPS_POLICY_PATH,
        maps_doc_path=_core.MAPS_DOC_PATH,
        entries_by_axis=entries_by_axis,
        surface_specs_count=len(maps_surface_latest_specs()),
        source_inputs=[
            maps_source_ref(Path(path), "policy_source_input")
            for path in policy.get("source_inputs", [])
            if isinstance(path, str)
        ],
    )
    if write_latest:
        errors = write_machine_maps_files(data, entries_by_axis)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def maps_index_document(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return _core.context_contracts.maps_index_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        maps_root=_core.MAPS_ROOT,
        start_path=MAPS_START_PATH,
        latest_path=_core.MAPS_LATEST_PATH,
        validate_latest_path=_core.MAPS_VALIDATE_LATEST_PATH,
        maps_doc_path=_core.MAPS_DOC_PATH,
        maps_policy_path=_core.MAPS_POLICY_PATH,
        data=data,
    )


def maps_query(axis: str | None = None, query: str | None = None, write_latest: bool = False) -> dict[str, Any]:
    data = machine_maps(write_latest=write_latest)
    entries_by_axis = data.get("entries_by_axis") if isinstance(data.get("entries_by_axis"), dict) else {}
    return _core.context_contracts.maps_query_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        axis=axis,
        query=query,
        entries_by_axis=entries_by_axis,
    )


def maps_packet_reader_profiles() -> dict[str, dict[str, Any]]:
    return _core.context_contracts.maps_packet_reader_profiles()


def maps_packet_consumer_profiles() -> dict[str, str]:
    return _core.context_contracts.maps_packet_consumer_profiles()


def maps_packet_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return _core.context_contracts.maps_packet_entry(entry)


def maps_packet(
    axis: str | None = None,
    query: str | None = None,
    reader_profile: str = "agent",
    limit: int = 20,
    consumer: str | None = None,
) -> dict[str, Any]:
    query_result = maps_query(axis=axis, query=query, write_latest=False)
    return _core.context_contracts.maps_packet_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        axis=axis,
        query=query,
        reader_profile=reader_profile,
        limit=limit,
        consumer=consumer,
        query_result=query_result,
        maps_doc_path=_core.MAPS_DOC_PATH,
        maps_policy_path=_core.MAPS_POLICY_PATH,
        maps_latest_path=_core.MAPS_LATEST_PATH,
    )


def maps_validate_document_from_checks(
    checks: list[dict[str, Any]],
    *,
    strict: bool,
    maps_summary: dict[str, Any] | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return _core.context_contracts.maps_validate_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=generated_at or _core.now_iso(),
        checks=checks,
        strict=strict,
        maps_summary=maps_summary,
    )


def maps_validate(strict: bool = False, write_latest: bool = True) -> dict[str, Any]:
    maps_data = machine_maps(write_latest=write_latest)
    checks: list[dict[str, Any]] = []
    _core.validation_add_path_exists(checks, "doc:maps_contract", _core.MAPS_DOC_PATH, "file", required=True)
    _core.validation_json_file(checks, "json:maps_policy", _core.MAPS_POLICY_PATH, f"{_core.SCHEMA_PREFIX}_maps_policy_v1", required=True)
    _core.validation_add_path_exists(checks, "doc:maps_agents", _core.MAPS_AGENTS_PATH, "file", required=True)
    _core.validation_add_path_exists(checks, "unit:context_refresh_service", MAPS_SERVICE_PATH, "file", required=True)
    _core.validation_add_path_exists(checks, "unit:context_refresh_timer", MAPS_TIMER_PATH, "file", required=True)
    timer_state = _core.user_systemd_unit(_core.MAPS_TIMER)
    _core.topology_validation_add(
        checks,
        "ok" if timer_state.get("is_enabled") else "warn",
        "unit:context_refresh_timer_enabled",
        "context refresh timer is enabled" if timer_state.get("is_enabled") else "context refresh timer is not enabled",
        timer_state,
    )
    _core.validation_add_path_exists(checks, "doc:maps_start", MAPS_START_PATH, "file", required=True)
    _core.validation_json_file(checks, "json:maps_latest", _core.MAPS_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_maps_v1", required=True)
    _core.validation_json_file(checks, "json:maps_index", _core.MAPS_INDEX_PATH, f"{_core.SCHEMA_PREFIX}_maps_index_v1", required=True)
    axes = maps_data.get("axes") if isinstance(maps_data.get("axes"), list) else []
    missing_axes = [axis["axis"] for axis in maps_axis_definitions() if not (_core.MAPS_ROOT / axis["axis"] / "index.json").exists()]
    _core.topology_validation_add(
        checks,
        "fail" if missing_axes else "ok",
        "axis_indexes",
        "all required atlas axis indexes exist" if not missing_axes else "required atlas axis indexes missing",
        {"missing": missing_axes},
    )
    empty_axes = [axis.get("axis") for axis in axes if _core.safe_int(axis.get("entry_count"), 0) == 0]
    _core.topology_validation_add(
        checks,
        "warn" if empty_axes else "ok",
        "axis_entries",
        "all atlas axes have entries" if not empty_axes else "some atlas axes have no generated entries",
        {"empty_axes": empty_axes},
    )
    bad_entries: list[dict[str, Any]] = []
    entries_by_axis = maps_data.get("entries_by_axis") if isinstance(maps_data.get("entries_by_axis"), dict) else {}
    for axis_id, entries in entries_by_axis.items():
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                bad_entries.append({"axis": axis_id, "reason": "entry_not_object"})
                continue
            if entry.get("truth_status") != "generated_route_signal_not_source_truth":
                bad_entries.append({"axis": axis_id, "id": entry.get("id"), "reason": "bad_truth_status"})
            if not isinstance(entry.get("evidence_refs"), list) or not entry.get("evidence_refs"):
                bad_entries.append({"axis": axis_id, "id": entry.get("id"), "reason": "missing_evidence_refs"})
            policy = entry.get("policy") if isinstance(entry.get("policy"), dict) else {}
            if policy.get("automatic_action") is not False or policy.get("automatic_response") is not False or policy.get("raw_private_content") is not False:
                bad_entries.append({"axis": axis_id, "id": entry.get("id"), "reason": "bad_policy"})
    _core.topology_validation_add(
        checks,
        "fail" if bad_entries else "ok",
        "entry_contract",
        "all map entries carry truth status, evidence refs, and non-action policy",
        {"bad_entries": bad_entries[:20], "bad_count": len(bad_entries)},
    )
    sample_packet = maps_packet(axis="by-eval-packet", reader_profile="proof-context", limit=4, consumer="aoa-evals")
    packet_ok = (
        sample_packet.get("schema") == f"{_core.SCHEMA_PREFIX}_maps_packet_v1"
        and sample_packet.get("truth_status") == "generated_route_signal_not_source_truth"
        and _core.nested_get(sample_packet, ["summary", "automatic_action"]) is False
        and _core.nested_get(sample_packet, ["summary", "proof_verdict"]) is False
        and sample_packet.get("reader_profile") == "proof-context"
        and sample_packet.get("consumer") == "aoa-evals"
        and bool(sample_packet.get("entries"))
    )
    _core.topology_validation_add(
        checks,
        "ok" if packet_ok else "fail",
        "packet_contract",
        "sample map context packet preserves route-signal and non-action contract" if packet_ok else "sample map context packet contract failed",
        {
            "schema": sample_packet.get("schema"),
            "entries": _core.nested_get(sample_packet, ["summary", "entries"]),
            "reader_profile": sample_packet.get("reader_profile"),
            "consumer": sample_packet.get("consumer"),
            "truth_status": sample_packet.get("truth_status"),
        },
    )
    data = maps_validate_document_from_checks(
        checks,
        strict=strict,
        maps_summary=maps_data.get("summary") if isinstance(maps_data.get("summary"), dict) else None,
    )
    if write_latest:
        errors = _core.write_latest_and_history(data, _core.MAPS_VALIDATE_LATEST_PATH, _core.MAPS_VALIDATE_ROOT)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def default_rag_policy() -> dict[str, Any]:
    return _core.context_contracts.default_rag_policy(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        rag_doc_path=_core.RAG_DOC_PATH,
        rag_policy_path=_core.RAG_POLICY_PATH,
        maps_doc_path=_core.MAPS_DOC_PATH,
    )


def rag_policy_document() -> dict[str, Any]:
    loaded, error = _core.load_json_document(_core.RAG_POLICY_PATH)
    return _core.context_contracts.rag_policy_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        rag_doc_path=_core.RAG_DOC_PATH,
        rag_policy_path=_core.RAG_POLICY_PATH,
        maps_doc_path=_core.MAPS_DOC_PATH,
        loaded=loaded,
        load_error=error,
    )


def rag_paths() -> dict[str, Any]:
    return _core.context_contracts.rag_paths_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        rag_root=_core.RAG_ROOT,
        rag_doc_path=_core.RAG_DOC_PATH,
        rag_policy_path=_core.RAG_POLICY_PATH,
        rag_agents_path=_core.RAG_AGENTS_PATH,
        rag_latest_path=_core.RAG_LATEST_PATH,
        rag_index_path=_core.RAG_INDEX_PATH,
        trace_root=_core.RAG_TRACE_ROOT,
        trace_latest_path=_core.RAG_TRACE_LATEST_PATH,
        eval_root=_core.RAG_EVAL_ROOT,
        eval_latest_path=_core.RAG_EVAL_LATEST_PATH,
        refresh_root=_core.RAG_REFRESH_ROOT,
        refresh_latest_path=_core.RAG_REFRESH_LATEST_PATH,
        validate_root=_core.RAG_VALIDATE_ROOT,
        validate_latest_path=_core.RAG_VALIDATE_LATEST_PATH,
        maps_service_path=MAPS_SERVICE_PATH,
        maps_timer_path=MAPS_TIMER_PATH,
        maps_timer=_core.MAPS_TIMER,
        maps_latest_path=_core.MAPS_LATEST_PATH,
        maps_doc_path=_core.MAPS_DOC_PATH,
        maps_policy_path=_core.MAPS_POLICY_PATH,
    )


def rag_is_private_raw_path(path: Path) -> bool:
    path_text = str(path)
    private_roots = [
        str(_core.NERVOUS_PRIVATE_CAPTURE_ROOT),
        str(_core.NERVOUS_SCREENSHOT_ROOT),
        str(_core.NERVOUS_BROWSER_CONTENT_ROOT),
    ]
    return any(path_text == root or path_text.startswith(root + os.sep) for root in private_roots)


def rag_evidence_snapshot(ref: dict[str, Any], *, max_json_bytes: int, max_text_bytes: int, max_text_chars: int, max_dir_entries: int) -> dict[str, Any]:
    path = Path(str(ref.get("path") or ""))
    snapshot: dict[str, Any] = {
        "schema": f"{_core.SCHEMA_PREFIX}_rag_evidence_snapshot_v1",
        "path": str(path),
        "truth_level": ref.get("truth_level"),
        "source_ref": {
            key: ref.get(key)
            for key in ("path", "truth_level", "exists", "schema", "generated_at", "ok", "summary")
            if key in ref
        },
        "exists": path.exists(),
        "read_at": _core.now_iso(),
        "raw_private_content": False,
        "content_mode": "metadata_only",
    }
    if not path.exists():
        snapshot["status"] = "missing"
        return snapshot
    try:
        stat = path.stat()
        snapshot["size_bytes"] = stat.st_size
        snapshot["mtime"] = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds")
        snapshot["is_file"] = path.is_file()
        snapshot["is_dir"] = path.is_dir()
    except OSError as exc:
        snapshot["status"] = "stat_error"
        snapshot["error"] = str(exc)
        return snapshot

    if path.is_dir():
        try:
            children = sorted(item.name for item in path.iterdir())[:max(1, max_dir_entries)]
        except OSError as exc:
            snapshot["status"] = "list_error"
            snapshot["error"] = str(exc)
            return snapshot
        snapshot["status"] = "directory_summary"
        snapshot["content_mode"] = "directory_listing"
        snapshot["children"] = children
        snapshot["truncated"] = len(children) >= max(1, max_dir_entries)
        return snapshot

    if not path.is_file():
        snapshot["status"] = "not_regular_file"
        return snapshot

    try:
        if stat.st_size <= max(max_json_bytes, max_text_bytes):
            raw = path.read_bytes()
            snapshot["sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            raw = b""
            snapshot["sha256"] = None
            snapshot["hash_skipped_reason"] = "too_large_for_rag_trace"
    except OSError as exc:
        snapshot["status"] = "read_error"
        snapshot["error"] = str(exc)
        return snapshot

    if rag_is_private_raw_path(path):
        snapshot["status"] = "private_raw_path_omitted"
        snapshot["content_mode"] = "metadata_only_private"
        return snapshot

    suffix = path.suffix.lower()
    if suffix == ".json" and stat.st_size <= max_json_bytes:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            snapshot["status"] = "json_parse_error"
            snapshot["error"] = str(exc)
            return snapshot
        snapshot["status"] = "json_summary"
        snapshot["content_mode"] = "bounded_json_summary"
        if isinstance(payload, dict):
            snapshot["payload_schema"] = payload.get("schema")
            snapshot["payload_ok"] = payload.get("ok")
            snapshot["payload_generated_at"] = payload.get("generated_at")
            snapshot["payload_status"] = payload.get("status")
            snapshot["payload_summary"] = _compact_for_rag(payload.get("summary"), max_depth=4, max_items=16)
            snapshot["payload_readiness"] = _compact_for_rag(payload.get("readiness"), max_depth=4, max_items=16)
            snapshot["payload_keys"] = sorted(str(key) for key in payload.keys())[:40]
        else:
            snapshot["payload_type"] = type(payload).__name__
            snapshot["payload_compact"] = _compact_for_rag(payload, max_depth=3, max_items=16)
        return snapshot

    if suffix in {".md", ".txt", ".log"} and stat.st_size <= max_text_bytes:
        try:
            text = raw.decode("utf-8", errors="replace")
        except UnicodeDecodeError as exc:
            snapshot["status"] = "text_decode_error"
            snapshot["error"] = str(exc)
            return snapshot
        snapshot["status"] = "text_excerpt"
        snapshot["content_mode"] = "bounded_redacted_text_excerpt"
        snapshot["excerpt"] = _core.nervous_text_payload(text, max_chars=max_text_chars)
        return snapshot

    snapshot["status"] = "metadata_only"
    snapshot["content_mode"] = "metadata_only_unsupported_or_large"
    return snapshot


def _compact_for_rag(value: Any, max_depth: int = 4, max_items: int = 16) -> Any:
    if max_depth <= 0:
        return "<omitted>"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                result["_truncated_items"] = len(value) - max_items
                break
            result[str(key)] = _compact_for_rag(item, max_depth=max_depth - 1, max_items=max_items)
        return result
    if isinstance(value, list):
        result = [_compact_for_rag(item, max_depth=max_depth - 1, max_items=max_items) for item in value[:max_items]]
        if len(value) > max_items:
            result.append({"_truncated_items": len(value) - max_items})
        return result
    if isinstance(value, str):
        return _core.nervous_text_payload(value, max_chars=800)["text"] if len(value) > 800 else value
    return value


def rag_answer_from_trace_seed(query: str, packet: dict[str, Any], evidence_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    return _core.context_contracts.rag_answer_from_trace_seed(
        schema_prefix=_core.SCHEMA_PREFIX,
        query=query,
        packet=packet,
        evidence_snapshots=evidence_snapshots,
    )


def rag_eval_document(trace: dict[str, Any]) -> dict[str, Any]:
    return _core.context_contracts.rag_eval_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        trace=trace,
    )


def rag_eval_missing_trace_document(error: Any, *, generated_at: str | None = None) -> dict[str, Any]:
    return _core.context_contracts.rag_eval_missing_trace_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=generated_at or _core.now_iso(),
        trace_latest_path=_core.RAG_TRACE_LATEST_PATH,
        error=error,
    )


def rag_validate_document_from_checks(
    checks: list[dict[str, Any]],
    *,
    strict: bool,
    paths: dict[str, Any],
    latest_trace: dict[str, Any] | None,
    latest_eval: dict[str, Any] | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return _core.context_contracts.rag_validate_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=generated_at or _core.now_iso(),
        checks=checks,
        strict=strict,
        paths=paths,
        latest_trace=latest_trace,
        latest_eval=latest_eval,
    )


def write_rag_index(trace: dict[str, Any] | None = None, eval_doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    latest_trace, trace_error = _core.load_json_document(_core.RAG_TRACE_LATEST_PATH)
    latest_eval, eval_error = _core.load_json_document(_core.RAG_EVAL_LATEST_PATH)
    if trace is None and isinstance(latest_trace, dict):
        trace = latest_trace
    if eval_doc is None and isinstance(latest_eval, dict):
        eval_doc = latest_eval
    data = _core.context_contracts.rag_index_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        rag_root=_core.RAG_ROOT,
        rag_latest_path=_core.RAG_LATEST_PATH,
        trace_latest_path=_core.RAG_TRACE_LATEST_PATH,
        eval_latest_path=_core.RAG_EVAL_LATEST_PATH,
        refresh_latest_path=_core.RAG_REFRESH_LATEST_PATH,
        validate_latest_path=_core.RAG_VALIDATE_LATEST_PATH,
        rag_doc_path=_core.RAG_DOC_PATH,
        rag_policy_path=_core.RAG_POLICY_PATH,
        trace=trace,
        trace_error=trace_error,
        eval_doc=eval_doc,
        eval_error=eval_error,
        commands=rag_paths()["commands"],
    )
    return [error for error in [_core.safe_atomic_write_json(_core.RAG_INDEX_PATH, data, 0o664)] if error]


def rag_status(write_latest: bool = True) -> dict[str, Any]:
    latest_trace, trace_error = _core.load_json_document(_core.RAG_TRACE_LATEST_PATH)
    latest_eval, eval_error = _core.load_json_document(_core.RAG_EVAL_LATEST_PATH)
    data = _core.context_contracts.rag_status_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        paths=rag_paths(),
        latest_trace_exists=_core.RAG_TRACE_LATEST_PATH.exists(),
        trace_error=trace_error,
        latest_trace=latest_trace,
        latest_eval_exists=_core.RAG_EVAL_LATEST_PATH.exists(),
        eval_error=eval_error,
        latest_eval=latest_eval,
        policy=rag_policy_document(),
    )
    if write_latest:
        errors = [error for error in [
            _core.safe_atomic_write_json(_core.RAG_LATEST_PATH, data, 0o664),
            *write_rag_index(latest_trace if isinstance(latest_trace, dict) else None, latest_eval if isinstance(latest_eval, dict) else None),
        ] if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def rag_trace(
    query: str,
    *,
    axis: str | None = None,
    reader_profile: str | None = None,
    limit: int | None = None,
    evidence_limit: int | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    policy = rag_policy_document()
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    axis_id = axis or str(policy.get("default_axis") or "by-rag-run")
    profile = reader_profile or str(policy.get("default_reader_profile") or "retrieval-context")
    bounded_limit = max(1, min(_core.safe_int(limit, _core.safe_int(limits.get("packet_entries"), 8)), 50))
    bounded_evidence_limit = max(1, min(_core.safe_int(evidence_limit, _core.safe_int(limits.get("evidence_refs"), 12)), 40))
    query_text = (query or "").strip() or "machine RAG trace"
    packet = maps_packet(axis=axis_id, query=query_text, reader_profile=profile, limit=bounded_limit)
    query_fallback = False
    if not packet.get("entries") and query_text:
        packet = maps_packet(axis=axis_id, query=None, reader_profile=profile, limit=bounded_limit)
        query_fallback = True
    refs = packet.get("evidence_refs") if isinstance(packet.get("evidence_refs"), list) else []
    evidence_snapshots = [
        rag_evidence_snapshot(
            ref,
            max_json_bytes=_core.safe_int(limits.get("json_file_max_bytes"), 262144),
            max_text_bytes=_core.safe_int(limits.get("text_file_max_bytes"), 65536),
            max_text_chars=_core.safe_int(limits.get("text_excerpt_chars"), 4000),
            max_dir_entries=_core.safe_int(limits.get("directory_entries"), 24),
        )
        for ref in refs[:bounded_evidence_limit]
        if isinstance(ref, dict)
    ]
    answer = rag_answer_from_trace_seed(query_text, packet, evidence_snapshots)
    trace = _core.context_contracts.rag_trace_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        query_text=query_text,
        axis_id=axis_id,
        profile=profile,
        packet=packet,
        evidence_snapshots=evidence_snapshots,
        answer=answer,
        policy=policy,
        rag_doc_path=_core.RAG_DOC_PATH,
        rag_policy_path=_core.RAG_POLICY_PATH,
        maps_doc_path=_core.MAPS_DOC_PATH,
        query_fallback=query_fallback,
    )
    eval_doc = rag_eval_document(trace)
    trace["eval"] = {
        "schema": eval_doc.get("schema"),
        "ok": eval_doc.get("ok"),
        "summary": eval_doc.get("summary"),
        "score": eval_doc.get("score"),
    }
    if write_latest:
        errors = [error for error in [
            _core.safe_atomic_write_json(_core.RAG_TRACE_LATEST_PATH, trace, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.RAG_TRACE_ROOT), trace, 0o664),
            _core.safe_atomic_write_json(_core.RAG_EVAL_LATEST_PATH, eval_doc, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.RAG_EVAL_ROOT), eval_doc, 0o664),
            *write_rag_index(trace, eval_doc),
        ] if error]
        status = rag_status(write_latest=True)
        if not status.get("ok"):
            errors.extend(status.get("write_errors") or [])
        if errors:
            trace["ok"] = False
            trace["write_errors"] = errors
    return trace


def rag_eval(write_latest: bool = True) -> dict[str, Any]:
    trace, error = _core.load_json_document(_core.RAG_TRACE_LATEST_PATH)
    if not isinstance(trace, dict):
        data = rag_eval_missing_trace_document(error)
    else:
        data = rag_eval_document(trace)
    if write_latest:
        errors = [error for error in [
            _core.safe_atomic_write_json(_core.RAG_EVAL_LATEST_PATH, data, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.RAG_EVAL_ROOT), data, 0o664),
            *write_rag_index(trace if isinstance(trace, dict) else None, data),
        ] if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def rag_refresh(
    query: str = "scheduled machine context refresh",
    *,
    axis: str | None = None,
    reader_profile: str | None = None,
    limit: int | None = None,
    evidence_limit: int | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    maps_doc = machine_maps(write_latest=True)
    maps_check = maps_validate(strict=False, write_latest=True)
    trace = rag_trace(
        query=query,
        axis=axis or "by-rag-run",
        reader_profile=reader_profile or "retrieval-context",
        limit=limit,
        evidence_limit=evidence_limit,
        write_latest=True,
    )
    rag_check = rag_validate(strict=False, write_latest=True)
    data = _core.context_contracts.rag_refresh_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        query=query,
        axis=axis or "by-rag-run",
        reader_profile=reader_profile or "retrieval-context",
        maps_doc=maps_doc,
        maps_check=maps_check,
        trace=trace,
        rag_check=rag_check,
        maps_latest_path=_core.MAPS_LATEST_PATH,
        maps_validate_latest_path=_core.MAPS_VALIDATE_LATEST_PATH,
        rag_trace_latest_path=_core.RAG_TRACE_LATEST_PATH,
        rag_eval_latest_path=_core.RAG_EVAL_LATEST_PATH,
        rag_validate_latest_path=_core.RAG_VALIDATE_LATEST_PATH,
        paths=rag_paths(),
    )
    if write_latest:
        errors = [error for error in [
            _core.safe_atomic_write_json(_core.RAG_REFRESH_LATEST_PATH, data, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.RAG_REFRESH_ROOT), data, 0o664),
            *write_rag_index(trace if isinstance(trace, dict) else None, None),
        ] if error]
        status = rag_status(write_latest=True)
        if not status.get("ok"):
            errors.extend(status.get("write_errors") or [])
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def rag_validate(strict: bool = False, write_latest: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    _core.validation_add_path_exists(checks, "doc:rag_contract", _core.RAG_DOC_PATH, "file", required=True)
    _core.validation_json_file(checks, "json:rag_policy_source", _core.RAG_POLICY_PATH, f"{_core.SCHEMA_PREFIX}_maps_policy_v1", required=True)
    _core.validation_add_path_exists(checks, "doc:rag_agents", _core.RAG_AGENTS_PATH, "file", required=True)
    _core.validation_add_path_exists(checks, "unit:context_refresh_service", MAPS_SERVICE_PATH, "file", required=True)
    _core.validation_add_path_exists(checks, "unit:context_refresh_timer", MAPS_TIMER_PATH, "file", required=True)
    timer_state = _core.user_systemd_unit(_core.MAPS_TIMER)
    _core.topology_validation_add(
        checks,
        "ok" if timer_state.get("is_enabled") else "warn",
        "unit:context_refresh_timer_enabled",
        "context refresh timer is enabled" if timer_state.get("is_enabled") else "context refresh timer is not enabled",
        timer_state,
    )
    if not _core.RAG_TRACE_LATEST_PATH.exists():
        sample = rag_trace("machine rag validation", axis="by-rag-run", reader_profile="retrieval-context", limit=4, evidence_limit=6, write_latest=True)
    else:
        sample, _ = _core.load_json_document(_core.RAG_TRACE_LATEST_PATH)
        if not isinstance(sample, dict):
            sample = rag_trace("machine rag validation", axis="by-rag-run", reader_profile="retrieval-context", limit=4, evidence_limit=6, write_latest=True)
    _core.validation_add_path_exists(checks, "json:rag_trace_latest", _core.RAG_TRACE_LATEST_PATH, "file", required=True)
    _core.validation_json_file(checks, "json:rag_refresh_latest", _core.RAG_REFRESH_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_rag_refresh_v1", required=False)
    eval_doc = rag_eval_document(sample if isinstance(sample, dict) else {})
    _core.topology_validation_add(
        checks,
        "ok" if isinstance(sample, dict) and sample.get("schema") == f"{_core.SCHEMA_PREFIX}_rag_trace_v1" else "fail",
        "trace_contract",
        "latest/sample RAG trace schema is current",
        {"schema": sample.get("schema") if isinstance(sample, dict) else None},
    )
    _core.topology_validation_add(
        checks,
        "ok" if isinstance(sample, dict) and _core.nested_get(sample, ["summary", "packet_entries"]) else "fail",
        "trace_packet_entries",
        "RAG trace has packet entries",
        {"packet_entries": _core.nested_get(sample, ["summary", "packet_entries"]) if isinstance(sample, dict) else None},
    )
    _core.topology_validation_add(
        checks,
        "ok" if isinstance(sample, dict) and _core.nested_get(sample, ["summary", "evidence_opened"]) else "fail",
        "trace_evidence_opened",
        "RAG trace opens bounded evidence summaries",
        {"evidence_opened": _core.nested_get(sample, ["summary", "evidence_opened"]) if isinstance(sample, dict) else None},
    )
    _core.topology_validation_add(
        checks,
        "ok" if eval_doc.get("ok") else "fail",
        "trace_eval",
        "RAG eval passes trace quality gates",
        {"summary": eval_doc.get("summary")},
    )
    policy = rag_policy_document().get("policy")
    _core.topology_validation_add(
        checks,
        "ok" if isinstance(policy, dict) and policy.get("automatic_action") is False and policy.get("memory_writeback") is False and policy.get("proof_verdict") is False else "fail",
        "non_mutating_policy",
        "RAG policy disables action, response, memory writeback, proof, and KAG publication",
        policy,
    )
    data = rag_validate_document_from_checks(
        checks,
        strict=strict,
        paths=rag_paths(),
        latest_trace=sample if isinstance(sample, dict) else None,
        latest_eval=eval_doc if isinstance(eval_doc, dict) else None,
    )
    if write_latest:
        errors = [error for error in [
            _core.safe_atomic_write_json(_core.RAG_EVAL_LATEST_PATH, eval_doc, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.RAG_EVAL_ROOT), eval_doc, 0o664),
            _core.safe_atomic_write_json(_core.RAG_VALIDATE_LATEST_PATH, data, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.RAG_VALIDATE_ROOT), data, 0o664),
            *write_rag_index(sample if isinstance(sample, dict) else None, eval_doc),
        ] if error]
        status = rag_status(write_latest=True)
        if not status.get("ok"):
            errors.extend(status.get("write_errors") or [])
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def add_rag_parser(add_top_level_parser: Any, selected_parser_choices: Any) -> None:
    rag_parser = add_top_level_parser("rag", help="run read-only machine RAG trace loops over maps and bounded evidence")
    rag_parser.add_argument("rag_command", nargs="?", choices=["status", "paths", "policy", "trace", "refresh", "latest", "eval", "validate"], default="status")
    rag_parser.add_argument("--query", default="machine RAG trace", help="for trace/refresh: focused query or intent")
    rag_parser.add_argument("--axis", default=None, help="for trace/refresh: maps axis, default by-rag-run")
    rag_parser.add_argument("--reader-profile", default=None, help="for trace/refresh: reader profile, default retrieval-context")
    rag_parser.add_argument("--limit", type=int, default=None, help="for trace/refresh: maximum packet entries")
    rag_parser.add_argument("--evidence-limit", type=int, default=None, help="for trace/refresh: maximum evidence refs to open")
    rag_parser.add_argument("--strict", action="store_true", help="for validate: treat warnings as non-zero")
    rag_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def dispatch_rag(args: Any, parser: Any, argv: list[str]) -> int:
    if args.command == "rag":
        command = getattr(args, "rag_command", "status")
        if command == "paths":
            data = rag_paths()
            _core.print_json(data) if args.json else print(f"rag root: {_core.RAG_ROOT}")
            return 0
        if command == "policy":
            data = rag_policy_document()
            _core.print_json(data)
            return 0
        if command == "trace":
            data = rag_trace(
                query=getattr(args, "query", "machine RAG trace"),
                axis=getattr(args, "axis", None),
                reader_profile=getattr(args, "reader_profile", None),
                limit=getattr(args, "limit", None),
                evidence_limit=getattr(args, "evidence_limit", None),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(
                    f"rag trace: ok={data.get('ok')} trace_id={data.get('trace_id')} "
                    f"entries={summary.get('packet_entries')} evidence_opened={summary.get('evidence_opened')}"
                )
            return 0 if data.get("ok") else 1
        if command == "refresh":
            data = rag_refresh(
                query=getattr(args, "query", "scheduled machine context refresh"),
                axis=getattr(args, "axis", None),
                reader_profile=getattr(args, "reader_profile", None),
                limit=getattr(args, "limit", None),
                evidence_limit=getattr(args, "evidence_limit", None),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(
                    f"rag refresh: ok={data.get('ok')} maps={summary.get('maps_entries')} "
                    f"trace_id={summary.get('trace_id')} evidence_opened={summary.get('trace_evidence_opened')}"
                )
            return 0 if data.get("ok") else 1
        if command == "latest":
            data, error = _core.load_json_document(_core.RAG_TRACE_LATEST_PATH)
            if not isinstance(data, dict):
                data = {"schema": f"{_core.SCHEMA_PREFIX}_rag_trace_latest_v1", "ok": False, "path": str(_core.RAG_TRACE_LATEST_PATH), "error": error}
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"rag latest: ok={data.get('ok')} trace_id={data.get('trace_id')} entries={summary.get('packet_entries')}")
            return 0 if data.get("ok") else 1
        if command == "eval":
            data = rag_eval(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(f"rag eval: {summary.get('status')} ({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)")
            return 0 if data.get("ok") else 1
        if command == "validate":
            data = rag_validate(strict=bool(args.strict), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(f"rag validate: {summary.get('status')} ({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)")
            if data.get("summary", {}).get("fails"):
                return 1
            if args.strict and data.get("summary", {}).get("warnings"):
                return 2
            return 0
        data = rag_status(write_latest=True)
        if args.json:
            _core.print_json(data)
        else:
            latest = data.get("latest_trace", {}) if isinstance(data.get("latest_trace"), dict) else {}
            latest_eval = data.get("latest_eval", {}) if isinstance(data.get("latest_eval"), dict) else {}
            print(f"rag: ok={data.get('ok')} trace={latest.get('trace_id')} eval_ok={latest_eval.get('ok')}")
        return 0 if data.get("ok") else 1
    parser.error("unknown command")
    return 64


def add_maps_parser(add_top_level_parser: Any, selected_parser_choices: Any) -> None:
    maps_parser = add_top_level_parser("maps", help="inspect generated host-machine atlas maps")
    maps_parser.add_argument("maps_command", nargs="?", choices=["status", "paths", "policy", "build", "query", "packet", "validate"], default="status")
    maps_parser.add_argument("--axis", default=None, help="axis id for maps query, for example by-freshness")
    maps_parser.add_argument("--query", default=None, help="substring query across generated map entries")
    maps_parser.add_argument("--reader-profile", default="agent", help="for packet: reader profile, for example agent, proof-context, memory-context, graph-context")
    maps_parser.add_argument("--consumer", default=None, help="for packet: context consumer label, for example aoa-evals or aoa-memo")
    maps_parser.add_argument("--limit", type=int, default=20, help="for packet: maximum entries to include")
    maps_parser.add_argument("--strict", action="store_true", help="for validate: treat warnings as non-zero")
    maps_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def dispatch_maps(args: Any, parser: Any, argv: list[str]) -> int:
    if args.command == "maps":
        if args.maps_command == "paths":
            data = maps_paths()
            _core.print_json(data) if args.json else print(f"maps root: {_core.MAPS_ROOT}")
            return 0
        if args.maps_command == "policy":
            data = maps_policy_document()
            _core.print_json(data)
            return 0
        if args.maps_command == "query":
            data = maps_query(axis=getattr(args, "axis", None), query=getattr(args, "query", None), write_latest=False)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(f"maps query: results={summary.get('results')} axes={summary.get('axes_searched')}")
            return 0 if data.get("ok") else 1
        if args.maps_command == "packet":
            data = maps_packet(
                axis=getattr(args, "axis", None),
                query=getattr(args, "query", None),
                reader_profile=getattr(args, "reader_profile", "agent"),
                limit=_core.safe_int(getattr(args, "limit", 20), 20),
                consumer=getattr(args, "consumer", None),
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(
                    f"maps packet: reader_profile={data.get('reader_profile')} entries={summary.get('entries')} "
                    f"evidence_refs={summary.get('evidence_refs')}"
                )
            return 0 if data.get("ok") else 1
        if args.maps_command == "validate":
            data = maps_validate(strict=bool(args.strict), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(
                    f"maps validate: {summary.get('status')} "
                    f"({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)"
                )
            if data.get("summary", {}).get("fails"):
                return 1
            if args.strict and data.get("summary", {}).get("warnings"):
                return 2
            return 0
        data = machine_maps(write_latest=True)
        if args.json:
            _core.print_json(data)
        else:
            summary = data.get("summary", {})
            print(f"maps: axes={summary.get('axes')} entries={summary.get('entries')} start={MAPS_START_PATH}")
        return 0 if data.get("ok") else 1
    parser.error("unknown command")
    return 64
