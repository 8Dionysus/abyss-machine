from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessCycleProofPaths:
    heartbeats_latest: Path
    memory_latest: Path
    mode_latest: Path
    resource_latest: Path
    process_latest: Path
    process_container_latest: Path
    process_thermal_plan_latest: Path
    cooling_latest: Path
    typing_events_latest: Path
    typing_validate_latest: Path
    nervous_brief_latest: Path
    reactions_latest: Path
    responses_latest: Path


@dataclass(frozen=True)
class SelfAwarenessCycleProofConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessCycleProofContractPort:
    latest_artifact_ref: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCycleProofRuntimePort:
    path_stat: DocumentPort


nested_get = self_awareness_contracts.nested_get


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def cycle_from_zero_chain_sources() -> dict[str, list[str]]:
    return {
        "synthetic_request": ["probe", "collect", "events"],
        "capability_inventory": ["capabilities", "probe"],
        "requirement_probes": ["requirement_probes"],
        "stack_closure_dossier": ["stack_closure_dossier"],
        "failure_matrix": ["failure_matrix"],
        "working_stack": [
            "working_stack",
            "collect",
            "events",
            "timeline",
            "spatial_graph",
            "context",
        ],
        "working_stack_link_integrity": [
            "working_stack",
            "collect",
            "events",
            "timeline",
            "spatial_graph",
            "context",
            "episodes",
            "export",
        ],
        "autolink": [
            "autolink",
            "working_stack",
            "coverage_audit",
            "stack_closure_dossier",
            "episodes",
            "export",
        ],
        "trace_context_fallback": [
            "trace_context",
            "requirement_probes",
            "stack_closure_dossier",
        ],
        "signal_fabric": ["collect", "events", "probe"],
        "query": ["query"],
        "correlation": ["correlation"],
        "timeline": ["timeline"],
        "spatial_graph": ["spatial_graph"],
        "causal_episode": ["episodes"],
        "alert": ["alerts", "collect"],
        "warm_e2b_worker": ["collect", "context", "investigate"],
        "resident_cognitive_replay": ["investigate", "replay"],
        "resident_cognitive_export": ["replay", "export"],
        "rag_memory": ["collect", "context", "query"],
        "nervous_freshness": ["collect", "context"],
        "langgraph_investigation": ["investigate"],
        "replay": ["replay"],
        "working_stack_activation_smoke": [
            "activation_smoke",
            "investigate",
            "replay",
            "stack_closure_dossier",
        ],
        "stack_handoff_readiness_replay": ["replay", "stack_closure_dossier"],
        "semantic_brief": ["brief"],
        "reaction_candidate": ["alerts", "reactions"],
        "governed_response": ["responses"],
        "body_trace": [
            "context",
            "investigate",
            "replay",
            "reactions",
            "responses",
            "export",
        ],
        "entity_event_document": ["responses", "export"],
        "machine_bridges": [
            "heartbeats",
            "memory",
            "mode",
            "resource",
            "processes",
            "process_containers",
            "process_thermal_plan",
            "cooling",
            "typing_events",
            "typing_validate",
            "nervous_brief",
            "reactions",
            "responses",
        ],
        "export": ["export"],
    }


def cycle_bridge_surfaces(
    *, paths: SelfAwarenessCycleProofPaths, config: SelfAwarenessCycleProofConfig
) -> list[dict[str, Any]]:
    SCHEMA_PREFIX = config.schema_prefix
    HEARTBEATS_LATEST_PATH = paths.heartbeats_latest
    MEMORY_LATEST_PATH = paths.memory_latest
    MODE_LATEST_PATH = paths.mode_latest
    RESOURCE_LATEST_PATH = paths.resource_latest
    PROCESS_LATEST_PATH = paths.process_latest
    PROCESS_CONTAINER_LATEST_PATH = paths.process_container_latest
    PROCESS_THERMAL_PLAN_LATEST_PATH = paths.process_thermal_plan_latest
    COOLING_LATEST_PATH = paths.cooling_latest
    TYPING_EVENTS_LATEST_PATH = paths.typing_events_latest
    TYPING_VALIDATE_LATEST_PATH = paths.typing_validate_latest
    NERVOUS_BRIEF_LATEST_PATH = paths.nervous_brief_latest
    REACTIONS_LATEST_PATH = paths.reactions_latest
    RESPONSES_LATEST_PATH = paths.responses_latest
    return [
        {
            "id": "heartbeats",
            "organ": "heartbeat_bridge",
            "path": HEARTBEATS_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_heartbeat_pulse_v1",
            "command": "abyss-machine heartbeats pulse --json",
            "validator": "abyss-machine heartbeats validate --json",
            "coverage": ["heartbeat", "candidate_lifecycle", "e2b_breath"],
        },
        {
            "id": "memory",
            "organ": "memory_pressure_reserve",
            "path": MEMORY_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_memory_status_v1",
            "command": "abyss-machine memory status --json",
            "validator": "abyss-machine memory validate --json",
            "coverage": ["memory", "pressure", "swap_reserve"],
        },
        {
            "id": "mode",
            "organ": "mode_gate",
            "path": MODE_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_mode_status_v1",
            "command": "abyss-machine mode status --json",
            "validator": "abyss-machine mode validate --json",
            "coverage": ["mode", "power_profile", "operator_gate"],
        },
        {
            "id": "resource",
            "organ": "resource_orchestrator",
            "path": RESOURCE_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_resource_status_v1",
            "command": "abyss-machine resource status --json",
            "validator": "abyss-machine resource validate --json",
            "coverage": ["resource", "launch_policy", "mode_memory_thermal_gate"],
        },
        {
            "id": "processes",
            "organ": "process_snapshot",
            "path": PROCESS_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_process_snapshot_v1",
            "command": "abyss-machine processes latest --json",
            "validator": "abyss-machine processes validate --json",
            "coverage": ["process", "pid", "host_attribution"],
        },
        {
            "id": "process_containers",
            "organ": "container_bridge",
            "path": PROCESS_CONTAINER_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_process_container_health_v1",
            "command": "abyss-machine processes containers --json",
            "validator": "abyss-machine processes validate --json",
            "coverage": ["containers", "stack_services", "restart_health"],
        },
        {
            "id": "process_thermal_plan",
            "organ": "thermal_new_work_gate",
            "path": PROCESS_THERMAL_PLAN_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_process_thermal_plan_v1",
            "command": "abyss-machine processes thermal-plan --seconds 3 --interval 0.5 --json",
            "validator": "abyss-machine processes validate --json",
            "coverage": ["thermal", "routing", "unattended_cap"],
        },
        {
            "id": "cooling",
            "organ": "cooling_status",
            "path": COOLING_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_cooling_status_v1",
            "command": "abyss-machine cooling status --json",
            "validator": "abyss-machine cooling validate --json",
            "coverage": ["cooling", "fan_policy", "temperature"],
        },
        {
            "id": "typing_events",
            "organ": "typing_signal",
            "path": TYPING_EVENTS_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_typing_event_v1",
            "command": "abyss-machine typing latest --json",
            "validator": "abyss-machine typing validate --json",
            "coverage": ["typing", "submitted_text", "redaction"],
        },
        {
            "id": "typing_validate",
            "organ": "typing_privacy_gate",
            "path": TYPING_VALIDATE_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_typing_validate_v1",
            "command": "abyss-machine typing validate --json",
            "validator": "abyss-machine typing validate --json",
            "coverage": ["typing", "privacy", "capture_gate"],
        },
        {
            "id": "nervous_brief",
            "organ": "nervous_freshness",
            "path": NERVOUS_BRIEF_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_nervous_brief_v1",
            "command": "abyss-machine nervous brief --scope now --json",
            "validator": "abyss-machine nervous validate --json",
            "coverage": ["nervous", "freshness", "semantic_context"],
        },
        {
            "id": "reactions",
            "organ": "reaction_candidates",
            "path": REACTIONS_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_reactions_status_v1",
            "command": "abyss-machine reactions --json",
            "validator": "abyss-machine reactions validate --json",
            "coverage": ["reactions", "owner_gated_candidates"],
        },
        {
            "id": "responses",
            "organ": "response_routes",
            "path": RESPONSES_LATEST_PATH,
            "schema": f"{SCHEMA_PREFIX}_responses_status_v1",
            "command": "abyss-machine responses --json",
            "validator": "abyss-machine responses validate --json",
            "coverage": ["responses", "approval_gate", "runbook_route"],
        },
    ]


def cycle_bridge_proof(
    *,
    generated_at: str,
    cycle_id: str,
    probe_run_id: str,
    paths: SelfAwarenessCycleProofPaths,
    config: SelfAwarenessCycleProofConfig,
    contract_port: SelfAwarenessCycleProofContractPort,
    runtime_port: SelfAwarenessCycleProofRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    self_awareness_cycle_bridge_surfaces = partial(
        cycle_bridge_surfaces, paths=paths, config=config
    )
    self_awareness_latest_artifact_ref = contract_port.latest_artifact_ref
    rows: list[dict[str, Any]] = []
    for surface in self_awareness_cycle_bridge_surfaces():
        path = surface["path"]
        artifact = self_awareness_latest_artifact_ref(
            str(surface["id"]), path, str(surface["schema"])
        )
        exists = bool(artifact.get("exists"))
        stat_result = runtime_port.path_stat(path) if exists else None
        row_ok = (
            exists
            and artifact.get("schema_ok") is True
            and bool(artifact.get("sha256"))
            and str(artifact.get("path") or "").startswith("/var/lib/abyss-machine/")
        )
        rows.append(
            {
                "schema": f"{SCHEMA_PREFIX}_self_awareness_cycle_bridge_proof_row_v1",
                "id": surface["id"],
                "organ": surface["organ"],
                "command": surface["command"],
                "validator": surface["validator"],
                "coverage": surface["coverage"],
                "ok": row_ok,
                "artifact": {
                    **artifact,
                    "machine_owned_path": str(artifact.get("path") or "").startswith(
                        "/var/lib/abyss-machine/"
                    ),
                    "mtime_ns": stat_result.st_mtime_ns if stat_result else None,
                    "mtime_iso": dt.datetime.fromtimestamp(
                        stat_result.st_mtime, tz=dt.timezone.utc
                    ).isoformat()
                    if stat_result
                    else None,
                },
                "evidence_refs": [
                    {
                        "path": artifact.get("path"),
                        "schema": artifact.get("schema"),
                        "sha256": artifact.get("sha256"),
                        "bridge_id": surface["id"],
                    }
                ]
                if artifact.get("path")
                else [],
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "actions_executed": False,
                    "mutates_existing_processes": False,
                    "automatic_remediation": False,
                    "raw_secrets_included": False,
                },
            }
        )
    missing = [
        str(row.get("id"))
        for row in rows
        if nested_get(row, ["artifact", "exists"]) is not True
    ]
    schema_mismatch = [
        str(row.get("id"))
        for row in rows
        if nested_get(row, ["artifact", "schema_ok"]) is not True
    ]
    failed = [str(row.get("id")) for row in rows if row.get("ok") is not True]
    degraded = [
        str(row.get("id"))
        for row in rows
        if nested_get(row, ["artifact", "ok"]) is False
    ]
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_cycle_bridge_proof_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "cycle_id": cycle_id,
        "probe_run_id": probe_run_id,
        "ok": not missing and (not schema_mismatch) and (not failed),
        "summary": {
            "bridges": len(rows),
            "missing": missing,
            "schema_mismatch": schema_mismatch,
            "failed": failed,
            "degraded": degraded,
            "machine_bridge_obligations": [str(row.get("id")) for row in rows],
        },
        "rows": rows,
        "evidence_refs": [
            ref
            for row in rows
            for ref in (
                row.get("evidence_refs")
                if isinstance(row.get("evidence_refs"), list)
                else []
            )
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
            "mutates_existing_processes": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "bridge_latest_artifacts_are_machine_owned_readmodels": True,
        },
    }


def cycle_bridge_proof_complete(
    proof: Any,
    *,
    paths: SelfAwarenessCycleProofPaths,
    config: SelfAwarenessCycleProofConfig,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    self_awareness_cycle_bridge_surfaces = partial(
        cycle_bridge_surfaces, paths=paths, config=config
    )
    if not isinstance(proof, dict):
        return False
    rows = proof.get("rows") if isinstance(proof.get("rows"), list) else []
    expected_ids = {
        str(surface["id"]) for surface in self_awareness_cycle_bridge_surfaces()
    }
    row_ids = {
        str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id")
    }
    return (
        proof.get("schema") == f"{SCHEMA_PREFIX}_self_awareness_cycle_bridge_proof_v1"
        and proof.get("ok") is True
        and bool(proof.get("cycle_id"))
        and bool(proof.get("probe_run_id"))
        and (row_ids == expected_ids)
        and (
            safe_int(nested_get(proof, ["summary", "bridges"]), -1) == len(expected_ids)
        )
        and (nested_get(proof, ["summary", "missing"]) == [])
        and (nested_get(proof, ["summary", "schema_mismatch"]) == [])
        and (nested_get(proof, ["summary", "failed"]) == [])
        and (nested_get(proof, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(proof, ["policy", "executes_commands"]) is False)
        and (nested_get(proof, ["policy", "actions_executed"]) is False)
        and (nested_get(proof, ["policy", "automatic_remediation"]) is False)
        and all(
            (
                isinstance(row, dict)
                and row.get("schema")
                == f"{SCHEMA_PREFIX}_self_awareness_cycle_bridge_proof_row_v1"
                and (row.get("ok") is True)
                and bool(row.get("command"))
                and bool(row.get("validator"))
                and bool(row.get("coverage"))
                and (nested_get(row, ["artifact", "exists"]) is True)
                and (nested_get(row, ["artifact", "schema_ok"]) is True)
                and (nested_get(row, ["artifact", "machine_owned_path"]) is True)
                and bool(nested_get(row, ["artifact", "sha256"]))
                and bool(row.get("evidence_refs"))
                and (nested_get(row, ["policy", "host_layer_mutates_stack"]) is False)
                and (nested_get(row, ["policy", "executes_commands"]) is False)
                and (nested_get(row, ["policy", "actions_executed"]) is False)
                and (nested_get(row, ["policy", "automatic_remediation"]) is False)
                for row in rows
            )
        )
    )


def cycle_from_zero_proof(
    *,
    generated_at: str,
    cycle_id: str,
    probe_run_id: str,
    cycle_chain: dict[str, Any],
    steps: list[dict[str, Any]],
    failed_steps: list[str],
    missing_chain: list[str],
    config: SelfAwarenessCycleProofConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    self_awareness_cycle_from_zero_chain_sources = cycle_from_zero_chain_sources
    chain_sources = self_awareness_cycle_from_zero_chain_sources()
    step_by_id = {
        str(step.get("id")): step
        for step in steps
        if isinstance(step, dict) and step.get("id")
    }
    proof_steps: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        artifact = (
            step.get("artifact") if isinstance(step.get("artifact"), dict) else {}
        )
        path = str(artifact.get("path") or "")
        proof_steps.append(
            {
                "schema": f"{SCHEMA_PREFIX}_self_awareness_from_zero_proof_step_v1",
                "order": index,
                "id": step.get("id"),
                "command": step.get("command"),
                "ok": step.get("ok") is True,
                "artifact": {
                    "path": path,
                    "schema": artifact.get("schema"),
                    "generated_at": artifact.get("generated_at"),
                    "status": artifact.get("status"),
                    "ok": artifact.get("ok"),
                    "exists": artifact.get("exists"),
                    "size_bytes": artifact.get("size_bytes"),
                    "sha256": artifact.get("sha256"),
                    "machine_owned_path": path.startswith("/var/lib/abyss-machine/"),
                },
                "freshness": {
                    "generated_at": artifact.get("generated_at"),
                    "mtime_ns": artifact.get("mtime_ns"),
                    "mtime_iso": artifact.get("mtime_iso"),
                },
                "evidence_refs": [
                    {
                        "path": path,
                        "schema": artifact.get("schema"),
                        "sha256": artifact.get("sha256"),
                        "step": step.get("id"),
                    }
                ]
                if path
                else [],
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "actions_executed": False,
                    "artifact_is_machine_owned_readmodel": path.startswith(
                        "/var/lib/abyss-machine/"
                    ),
                },
            }
        )
    chain_obligations: list[dict[str, Any]] = []
    for key, value in cycle_chain.items():
        evidence_step_ids = [
            step_id
            for step_id in chain_sources.get(str(key), [])
            if step_id in step_by_id
        ]
        chain_obligations.append(
            {
                "schema": f"{SCHEMA_PREFIX}_self_awareness_from_zero_chain_obligation_v1",
                "key": str(key),
                "satisfied": bool(value),
                "evidence_step_ids": evidence_step_ids,
                "evidence_paths": [
                    nested_get(step_by_id[step_id], ["artifact", "path"])
                    for step_id in evidence_step_ids
                    if nested_get(step_by_id[step_id], ["artifact", "path"])
                ],
                "policy": {
                    "host_layer_mutates_stack": False,
                    "evidence_is_readmodel_not_truth_claim": True,
                },
            }
        )
    proof_bad_steps = [
        str(step.get("id") or "unknown")
        for step in proof_steps
        if step.get("ok") is not True
        or nested_get(step, ["artifact", "exists"]) is not True
        or (not nested_get(step, ["artifact", "schema"]))
        or (not nested_get(step, ["artifact", "sha256"]))
        or (nested_get(step, ["artifact", "machine_owned_path"]) is not True)
        or (not step.get("evidence_refs"))
        or (nested_get(step, ["policy", "host_layer_mutates_stack"]) is not False)
    ]
    missing_obligations = [
        str(row.get("key"))
        for row in chain_obligations
        if row.get("satisfied") is not True or not row.get("evidence_step_ids")
    ]
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_from_zero_cycle_proof_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "cycle_id": cycle_id,
        "probe_run_id": probe_run_id,
        "source_command": "abyss-machine self-awareness cycle --json",
        "ok": not failed_steps
        and (not missing_chain)
        and (not proof_bad_steps)
        and (not missing_obligations),
        "summary": {
            "proof_steps": len(proof_steps),
            "chain_obligations": len(chain_obligations),
            "failed_steps": failed_steps,
            "missing_chain": missing_chain,
            "proof_bad_steps": proof_bad_steps,
            "missing_obligations": missing_obligations,
            "chain_passed": sum((1 for value in cycle_chain.values() if value)),
            "chain_total": len(cycle_chain),
        },
        "proof_steps": proof_steps,
        "chain_obligations": chain_obligations,
        "chain_sources": chain_sources,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "actions_executed": False,
            "claims_require_evidence_refs": True,
            "latest_artifacts_are_machine_owned_readmodels": True,
            "raw_evidence_is_not_truth": True,
        },
    }
    return data


def cycle_from_zero_proof_complete(
    proof: Any, *, config: SelfAwarenessCycleProofConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    if not isinstance(proof, dict):
        return False
    steps = (
        proof.get("proof_steps") if isinstance(proof.get("proof_steps"), list) else []
    )
    obligations = (
        proof.get("chain_obligations")
        if isinstance(proof.get("chain_obligations"), list)
        else []
    )
    return (
        proof.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_from_zero_cycle_proof_v1"
        and proof.get("ok") is True
        and bool(proof.get("cycle_id"))
        and bool(proof.get("probe_run_id"))
        and bool(steps)
        and bool(obligations)
        and (safe_int(nested_get(proof, ["summary", "proof_steps"]), -1) == len(steps))
        and (
            safe_int(nested_get(proof, ["summary", "chain_obligations"]), -1)
            == len(obligations)
        )
        and (nested_get(proof, ["summary", "failed_steps"]) == [])
        and (nested_get(proof, ["summary", "missing_chain"]) == [])
        and (nested_get(proof, ["summary", "proof_bad_steps"]) == [])
        and (nested_get(proof, ["summary", "missing_obligations"]) == [])
        and (nested_get(proof, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(proof, ["policy", "executes_commands"]) is False)
        and (nested_get(proof, ["policy", "actions_executed"]) is False)
        and (nested_get(proof, ["policy", "claims_require_evidence_refs"]) is True)
        and all(
            (
                isinstance(step, dict)
                and step.get("schema")
                == f"{SCHEMA_PREFIX}_self_awareness_from_zero_proof_step_v1"
                and (step.get("ok") is True)
                and bool(step.get("command"))
                and (nested_get(step, ["artifact", "exists"]) is True)
                and bool(nested_get(step, ["artifact", "schema"]))
                and bool(nested_get(step, ["artifact", "sha256"]))
                and (nested_get(step, ["artifact", "machine_owned_path"]) is True)
                and bool(step.get("evidence_refs"))
                and (nested_get(step, ["policy", "host_layer_mutates_stack"]) is False)
                and (nested_get(step, ["policy", "executes_commands"]) is False)
                for step in steps
            )
        )
        and all(
            (
                isinstance(row, dict)
                and row.get("schema")
                == f"{SCHEMA_PREFIX}_self_awareness_from_zero_chain_obligation_v1"
                and (row.get("satisfied") is True)
                and bool(row.get("evidence_step_ids"))
                and bool(row.get("evidence_paths"))
                and (nested_get(row, ["policy", "host_layer_mutates_stack"]) is False)
                for row in obligations
            )
        )
    )
