from __future__ import annotations

import collections
import json
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessRequirementPaths:
    requirements_latest: Path
    requirements_root: Path
    requirement_probes_latest: Path
    failure_matrix_latest: Path
    cycle_latest: Path


@dataclass(frozen=True)
class SelfAwarenessRequirementConfig:
    schema_prefix: str
    version: str
    grafana_url: str
    tempo_url: str
    route_api_url: str
    rag_api_url: str
    langchain_api_url: str
    neo4j_url: str
    postgres_host: str
    postgres_port: int


@dataclass(frozen=True)
class SelfAwarenessRequirementRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort
    secret_search: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessRequirementRefreshPort:
    capabilities: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessRequirementContractPort:
    brief_stack_handoff_action_map: DocumentPort


stable_hash_json = self_awareness_contracts.stable_hash_json
nested_get = self_awareness_contracts.nested_get


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def external_closure_row(raw: dict[str, Any], requirement_id: str) -> dict[str, Any]:
    external = (
        raw.get("stack_closure_external_evidence")
        if isinstance(raw.get("stack_closure_external_evidence"), dict)
        else {}
    )
    entries = (
        external.get("entries") if isinstance(external.get("entries"), dict) else {}
    )
    row = (
        entries.get(requirement_id)
        if isinstance(entries.get(requirement_id), dict)
        else {}
    )
    return row if row.get("accepted") is True else row


def requirement_item(
    requirement_id: str,
    title: str,
    *,
    owner: str = "abyss-stack",
    severity: str = "gap",
    reason: str,
    detection: dict[str, Any],
    expected_shape: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "title": title,
        "owner": owner,
        "severity": severity,
        "reason": reason,
        "detection": detection,
        "expected_shape": expected_shape,
        "machine_action": "record_requirement_only",
        "host_layer_mutates_stack": False,
        "status": "open",
        "evidence_refs": detection.get("evidence_refs")
        if isinstance(detection.get("evidence_refs"), list)
        else [],
    }


def requirement_acceptance_contract(
    requirement: dict[str, Any], *, config: SelfAwarenessRequirementConfig
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    STACK_OBSERVABILITY_GRAFANA_URL = config.grafana_url
    SELF_AWARENESS_TEMPO_URL = config.tempo_url
    SELF_AWARENESS_ROUTE_API_URL = config.route_api_url
    SELF_AWARENESS_RAG_API_URL = config.rag_api_url
    SELF_AWARENESS_LANGCHAIN_API_URL = config.langchain_api_url
    SELF_AWARENESS_NEO4J_URL = config.neo4j_url
    SELF_AWARENESS_POSTGRES_HOST = config.postgres_host
    SELF_AWARENESS_POSTGRES_PORT = config.postgres_port
    requirement_id = str(requirement.get("id") or "")
    expected_shape = (
        requirement.get("expected_shape")
        if isinstance(requirement.get("expected_shape"), dict)
        else {}
    )
    common_verifiers = [
        {
            "command": "abyss-machine self-awareness capabilities --json",
            "must": [
                f"open requirements exclude {requirement_id}",
                "the corresponding capability is available or explicitly optional",
                "evidence_refs cite the stack-owned route that closed the gap",
            ],
        },
        {
            "command": "abyss-machine self-awareness requirements --json",
            "must": [
                f"stack_handoff excludes {requirement_id}",
                "closed evidence does not contain raw credentials, tokens, prompts, row payloads, or private message bodies",
            ],
        },
        {
            "command": "abyss-machine self-awareness cycle --json",
            "must": [
                "open_stack_requirements decreases only after the stack-owned route is readable",
                "automatic_responses remains 0",
                "routes_with_mutating_command_if_run remains 0",
            ],
        },
        {
            "command": "abyss-machine self-awareness validate --json",
            "must": [
                "capability_map_and_requirements passes",
                "no_secret_leakage passes",
                "no_protected_root_writes passes",
            ],
        },
        {
            "command": "abyss-machine stack-bridge validate --json",
            "must": [
                "static bridge routes still expose self-awareness artifacts",
                "protected_write_claims remains empty",
            ],
        },
    ]
    common_must_not = [
        "abyss-machine must not write abyss-stack repos, dashboards, datasources, service configs, model roots, or runtime containers",
        "abyss-machine must not persist stack credentials or private payloads in latest/history artifacts",
        "abyss-machine must not treat an HTTP 2xx response as closure unless required fields and redaction rules also pass",
        "abyss-machine must not introduce high-cardinality Loki labels such as trace_id, request_id, session_id, span_id, or task_id",
    ]
    probe_plan: dict[str, Any] = {
        "kind": "generic_bounded_readonly_stack_inventory",
        "candidate_routes": ["stack-owned bounded read-only inventory endpoint"],
        "required_fields": ["status", "generated_at_or_freshness", "evidence_refs"],
        "success_predicates": [
            "route is read-only and stack-owned",
            "payload is bounded",
            "payload has evidence refs and freshness",
            "payload does not expose secrets or private raw data",
        ],
        "redaction_rules": ["no secrets", "no raw private payloads"],
    }
    if requirement_id == "stack.grafana.datasource-read":
        probe_plan = {
            "kind": "grafana_datasource_inventory",
            "candidate_routes": [
                f"{STACK_OBSERVABILITY_GRAFANA_URL.rstrip('/')}/api/health",
                f"{STACK_OBSERVABILITY_GRAFANA_URL.rstrip('/')}/api/search",
                f"{STACK_OBSERVABILITY_GRAFANA_URL.rstrip('/')}/api/frontend/settings",
                "http://127.0.0.1:3000/api/datasources with stack-owned read-only auth",
                "stack-owned bounded datasource inventory export consumed by abyss-machine",
            ],
            "required_fields": [
                "grafana.version",
                "grafana.database",
                "api_access.denied_routes",
                "inferred_candidates",
                "datasource_uid_or_id",
                "name",
                "type",
                "access_or_route",
                "is_default",
                "freshness_or_version",
                "readable_status",
            ],
            "success_predicates": [
                "Grafana health remains readable as liveness evidence",
                "source candidates inferred from Prometheus/Loki/Alertmanager are marked candidate-only and cannot close the requirement",
                "inventory route returns 2xx or a stack-owned exported artifact with at least one datasource",
                "datasource identity, type, and freshness can be cited by self-awareness correlation outputs",
                "secureJsonData, passwords, tokens, basic auth material, and raw URLs with credentials are absent or redacted",
            ],
            "redaction_rules": [
                "redact url userinfo",
                "omit secureJsonData",
                "omit passwords",
                "omit tokens",
            ],
            "boundedness": {"max_datasources": 256, "raw_credentials_allowed": False},
        }
    elif requirement_id == "stack.trace-backend":
        probe_plan = {
            "kind": "trace_backend_inventory",
            "candidate_routes": [
                f"{SELF_AWARENESS_TEMPO_URL.rstrip()}/ready or equivalent ready endpoint",
                f"{SELF_AWARENESS_TEMPO_URL.rstrip()}/api/search or equivalent bounded trace search route",
                'Prometheus up{job="alloy"} pipeline evidence',
                "bounded Loki LogQL traceparent query",
                "stack-owned bounded trace search/export route",
            ],
            "required_fields": [
                "backend",
                "ready_status",
                "trace_id_query_supported",
                "traceparent_supported",
                "alloy_pipeline_status",
                "loki_traceparent_query_status",
                "span_log_metric_join_supported",
                "freshness_or_retention",
            ],
            "success_predicates": [
                "ready endpoint reports healthy",
                "Alloy/Prometheus/Loki pipeline evidence remains readable as the metric/log side of the join",
                "W3C traceparent can be queried in logs with a bounded result or an explicit empty safe result",
                "W3C traceparent can connect at least one span/log/metric evidence chain after the trace backend is present",
                "trace evidence can be cited without changing stack runtime config",
            ],
            "redaction_rules": [
                "omit span attributes known to contain secrets",
                "hash log lines",
                "bound trace search result count",
            ],
            "boundedness": {
                "max_spans_per_probe": 200,
                "max_log_samples": 3,
                "raw_payloads_allowed": False,
            },
        }
    elif requirement_id == "stack.database-graph.read-route":
        probe_plan = {
            "kind": "database_graph_semantic_inventory",
            "candidate_routes": [
                f"{SELF_AWARENESS_ROUTE_API_URL.rstrip('/')}/health",
                f"{SELF_AWARENESS_ROUTE_API_URL.rstrip('/')}/openapi.json",
                f"{SELF_AWARENESS_RAG_API_URL.rstrip('/')}/health",
                f"{SELF_AWARENESS_RAG_API_URL.rstrip('/')}/openapi.json",
                f"{SELF_AWARENESS_RAG_API_URL.rstrip('/')}/collections",
                f"{SELF_AWARENESS_RAG_API_URL.rstrip('/')}/sources",
                f"{SELF_AWARENESS_RAG_API_URL.rstrip('/')}/agentic-rag/graph",
                f"{SELF_AWARENESS_NEO4J_URL.rstrip('/')}/",
                f"tcp://{SELF_AWARENESS_POSTGRES_HOST}:{SELF_AWARENESS_POSTGRES_PORT}",
                "stack-owned read-only Postgres schema/freshness inventory endpoint or export",
                "stack-owned read-only Neo4j label/relationship/freshness inventory endpoint or export",
            ],
            "required_fields": [
                "route_api.openapi_paths",
                "rag_api.collection_names",
                "rag_api.source_count",
                "rag_api.agentic_graph_shape",
                "postgres.tcp_ready",
                "postgres.schemas",
                "postgres.tables_or_relations",
                "postgres.freshness",
                "neo4j.version",
                "neo4j.labels",
                "neo4j.relationship_types",
                "neo4j.freshness",
                "inventory_generated_at",
            ],
            "success_predicates": [
                "route-api health and bounded OpenAPI remain readable as route/federation context",
                "rag-api health, bounded OpenAPI, collections, sources, and agentic graph shape remain readable",
                "Postgres service readiness and Neo4j root metadata are visible without storing credentials",
                "Postgres inventory exposes schema shape and freshness without row payloads by default",
                "Neo4j inventory exposes labels, relationship types, and freshness without private property values by default",
                "inventory is bounded and safe for self-awareness spatial graph overlays",
            ],
            "redaction_rules": [
                "omit row payloads",
                "omit private property values",
                "redact connection strings",
            ],
            "boundedness": {
                "max_objects_per_store": 1000,
                "raw_rows_allowed": False,
                "raw_graph_properties_allowed": False,
            },
        }
    elif requirement_id == "stack.langchain-api.graph-observability":
        probe_plan = {
            "kind": "langchain_langgraph_observability_inventory",
            "candidate_routes": [
                f"{SELF_AWARENESS_LANGCHAIN_API_URL.rstrip('/')}/health",
                f"{SELF_AWARENESS_LANGCHAIN_API_URL.rstrip('/')}/openapi.json",
                f"{SELF_AWARENESS_LANGCHAIN_API_URL.rstrip('/')}/run",
                f"{SELF_AWARENESS_LANGCHAIN_API_URL.rstrip('/')}/run/federated",
                f"{SELF_AWARENESS_LANGCHAIN_API_URL.rstrip('/')}/embeddings",
                f"{SELF_AWARENESS_TEMPO_URL.rstrip()}/ready",
                "stack-owned /threads inventory",
                "stack-owned /checkpoints inventory",
                "stack-owned /traces inventory",
            ],
            "required_fields": [
                "health.service",
                "health.embeddings_provider",
                "health.federated_run_enabled",
                "health.ovms_auth_enabled",
                "openapi_paths",
                "run_routes",
                "federated_run_routes",
                "embeddings_routes",
                "thread_count_or_ids",
                "checkpoint_count_or_ids",
                "latest_checkpoint_at",
                "thread_inventory_status",
                "checkpoint_inventory_status",
                "trace_inventory_status",
                "trace_backend_coupling",
                "freshness",
            ],
            "success_predicates": [
                "health endpoint reports langchain-api is serving",
                "OpenAPI inventory exposes bounded runtime route shape for run, federated run, and embeddings routes",
                "trace backend readiness or explicit equivalent trace inventory is visible for span/log/metric joins",
                "thread/checkpoint/trace inventories are read-only and bounded",
                "self-awareness investigation/replay can cite checkpoint inventory without storing prompt or message bodies",
            ],
            "redaction_rules": [
                "omit prompts",
                "omit messages",
                "omit tool payload bodies",
                "redact secrets in trace metadata",
            ],
            "boundedness": {
                "max_threads": 200,
                "max_checkpoints": 500,
                "max_traces": 200,
                "raw_prompt_payloads_allowed": False,
                "raw_message_payloads_allowed": False,
                "raw_tool_payloads_allowed": False,
            },
        }
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_requirement_acceptance_contract_v1",
        "requirement_id": requirement_id,
        "owner": requirement.get("owner") or "abyss-stack",
        "machine_role": "read_only_consumer",
        "status": requirement.get("status") or "open",
        "expected_shape": expected_shape,
        "probe_plan": probe_plan,
        "machine_verifiers": common_verifiers,
        "closure_semantics": {
            "no_partial_credit": True,
            "requires_current_evidence_refs": True,
            "requires_redaction_pass": True,
            "requires_stack_owned_route": True,
            "host_layer_mutates_stack": False,
        },
        "must_not": common_must_not,
    }


def stack_requirement_compat_contract(
    requirement: dict[str, Any],
    *,
    acceptance_contract: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
    current_state: dict[str, Any] | None = None,
    coverage_impact: dict[str, Any] | None = None,
    dependency_requirement_ids: list[str] | None = None,
    unblocks_requirement_ids: list[str] | None = None,
    config: SelfAwarenessRequirementConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    self_awareness_requirement_acceptance_contract = partial(
        requirement_acceptance_contract, config=config
    )
    self_awareness_stack_requirement_coverage_impact = partial(
        stack_requirement_coverage_impact, config=config
    )
    requirement_id = str(
        requirement.get("id") or requirement.get("requirement_id") or ""
    )
    owner = str(requirement.get("owner") or "abyss-stack")
    expected_shape = (
        requirement.get("expected_shape")
        if isinstance(requirement.get("expected_shape"), dict)
        else {}
    )
    acceptance_contract = (
        acceptance_contract
        if isinstance(acceptance_contract, dict)
        else self_awareness_requirement_acceptance_contract(requirement)
    )
    readiness = readiness if isinstance(readiness, dict) else {}
    current_state = current_state if isinstance(current_state, dict) else {}
    coverage_impact = (
        coverage_impact
        if isinstance(coverage_impact, dict)
        else self_awareness_stack_requirement_coverage_impact(requirement_id)
    )
    probe_plan = (
        acceptance_contract.get("probe_plan")
        if isinstance(acceptance_contract.get("probe_plan"), dict)
        else {}
    )
    machine_verifiers = (
        acceptance_contract.get("machine_verifiers")
        if isinstance(acceptance_contract.get("machine_verifiers"), list)
        else []
    )
    required_fields = (
        probe_plan.get("required_fields")
        if isinstance(probe_plan.get("required_fields"), list)
        else []
    )
    success_predicates = (
        probe_plan.get("success_predicates")
        if isinstance(probe_plan.get("success_predicates"), list)
        else []
    )
    redaction_rules = (
        probe_plan.get("redaction_rules")
        if isinstance(probe_plan.get("redaction_rules"), list)
        else []
    )
    boundedness = (
        probe_plan.get("boundedness")
        if isinstance(probe_plan.get("boundedness"), dict)
        else {}
    )
    candidate_routes = (
        probe_plan.get("candidate_routes")
        if isinstance(probe_plan.get("candidate_routes"), list)
        else []
    )
    blocking_check_keys = (
        readiness.get("blocking_check_keys")
        if isinstance(readiness.get("blocking_check_keys"), list)
        else []
    )
    if not blocking_check_keys:
        missing_checks = (
            readiness.get("missing_checks")
            if isinstance(readiness.get("missing_checks"), list)
            else []
        )
        blocking_check_keys = [
            str(item.get("key"))
            for item in missing_checks
            if isinstance(item, dict) and item.get("key")
        ]
    dependency_requirement_ids = [
        str(item)
        for item in (
            dependency_requirement_ids
            if isinstance(dependency_requirement_ids, list)
            else readiness.get("dependency_requirement_ids")
            if isinstance(readiness.get("dependency_requirement_ids"), list)
            else []
        )
    ]
    unblocks_requirement_ids = [
        str(item)
        for item in (
            unblocks_requirement_ids
            if isinstance(unblocks_requirement_ids, list)
            else []
        )
    ]
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_compat_contract_v1",
        "requirement_id": requirement_id,
        "owner_route": owner,
        "status": requirement.get("status") or readiness.get("status") or "open",
        "surface_kind": probe_plan.get("kind") or "bounded_stack_inventory",
        "expected_shape": expected_shape,
        "route_or_export_options": [str(item) for item in candidate_routes],
        "minimum_response_contract": {
            "required_fields": [str(item) for item in required_fields],
            "success_predicates": [str(item) for item in success_predicates],
            "current_blocking_check_keys": [str(item) for item in blocking_check_keys],
            "current_state_digest": stable_hash_json(current_state, length=24)
            if current_state
            else None,
        },
        "redaction_contract": {
            "rules": [str(item) for item in redaction_rules],
            "boundedness": boundedness,
            "forbidden_payloads": [
                "credentials",
                "tokens",
                "passwords",
                "raw prompts",
                "raw messages",
                "row payloads",
                "private graph property values",
                "raw trace payloads",
            ],
            "raw_secrets_allowed": False,
            "raw_private_payloads_allowed": False,
        },
        "machine_consumer_contract": {
            "consumer": "abyss-machine:self-awareness",
            "read_command": "abyss-machine self-awareness stack-closure-dossier --json",
            "probe_command": "abyss-machine self-awareness requirement-probes --json",
            "post_close_verifiers": machine_verifiers,
            "closure_requires_current_evidence": True,
            "closure_requires_redaction_pass": True,
            "no_partial_credit": True,
        },
        "dependency_contract": {
            "depends_on_requirement_ids": dependency_requirement_ids,
            "unblocks_requirement_ids": unblocks_requirement_ids,
            "dependency_order_is_handoff_guidance": True,
        },
        "coverage_contract": {
            "organ": coverage_impact.get("organ"),
            "coverage_planes": coverage_impact.get("coverage_planes")
            if isinstance(coverage_impact.get("coverage_planes"), list)
            else [],
            "closure_value": coverage_impact.get("closure_value"),
            "proof_commands": coverage_impact.get("proof_commands")
            if isinstance(coverage_impact.get("proof_commands"), list)
            else [],
        },
        "operator_boundary": {
            "stack_owner_may_mutate_stack_after_operator_approval": True,
            "abyss_machine_executes_stack_change": False,
            "host_layer_mutates_stack": False,
            "automatic_remediation": False,
        },
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "raw_secrets_included": False,
        },
    }


def stack_compat_contract_complete(
    contract: Any, *, config: SelfAwarenessRequirementConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    return (
        isinstance(contract, dict)
        and contract.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_stack_compat_contract_v1"
        and bool(contract.get("requirement_id"))
        and (contract.get("owner_route") == "abyss-stack")
        and bool(contract.get("route_or_export_options"))
        and isinstance(
            nested_get(contract, ["minimum_response_contract", "required_fields"]), list
        )
        and bool(nested_get(contract, ["minimum_response_contract", "required_fields"]))
        and isinstance(
            nested_get(contract, ["minimum_response_contract", "success_predicates"]),
            list,
        )
        and bool(
            nested_get(contract, ["minimum_response_contract", "success_predicates"])
        )
        and isinstance(nested_get(contract, ["redaction_contract", "rules"]), list)
        and bool(nested_get(contract, ["redaction_contract", "rules"]))
        and (
            nested_get(contract, ["redaction_contract", "raw_secrets_allowed"]) is False
        )
        and (
            nested_get(contract, ["redaction_contract", "raw_private_payloads_allowed"])
            is False
        )
        and isinstance(
            nested_get(contract, ["machine_consumer_contract", "post_close_verifiers"]),
            list,
        )
        and bool(
            nested_get(contract, ["machine_consumer_contract", "post_close_verifiers"])
        )
        and (
            nested_get(
                contract,
                ["machine_consumer_contract", "closure_requires_current_evidence"],
            )
            is True
        )
        and (
            nested_get(
                contract,
                ["machine_consumer_contract", "closure_requires_redaction_pass"],
            )
            is True
        )
        and nested_get(contract, ["coverage_contract", "organ"])
        and isinstance(
            nested_get(contract, ["coverage_contract", "coverage_planes"]), list
        )
        and bool(nested_get(contract, ["coverage_contract", "coverage_planes"]))
        and (
            nested_get(
                contract, ["operator_boundary", "abyss_machine_executes_stack_change"]
            )
            is False
        )
        and (
            nested_get(contract, ["operator_boundary", "host_layer_mutates_stack"])
            is False
        )
        and (nested_get(contract, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(contract, ["policy", "executes_commands"]) is False)
        and (nested_get(contract, ["policy", "raw_secrets_included"]) is False)
    )


def stack_requirement_negative_controls(requirement_id: str) -> list[dict[str, Any]]:
    controls = [
        {
            "key": "http_2xx_without_required_fields_does_not_close",
            "must_fail_closure_when": "a route answers but omits required fields, freshness, evidence refs, or redaction status",
        },
        {
            "key": "host_inference_without_stack_owned_route_does_not_close",
            "must_fail_closure_when": "abyss-machine can infer a candidate route but no stack-owned bounded route/export exists",
        },
        {
            "key": "secret_or_private_payload_rejects_closure",
            "must_fail_closure_when": "credentials, tokens, raw prompts, row payloads, graph property values, or raw trace payloads appear",
        },
    ]
    per_requirement: dict[str, list[dict[str, Any]]] = {
        "stack.grafana.datasource-read": [
            {
                "key": "inferred_datasource_candidates_do_not_close",
                "must_fail_closure_when": "Prometheus/Loki/Alertmanager/Tempo candidates are inferred but Grafana datasource inventory is absent",
            },
            {
                "key": "grafana_secret_fields_do_not_close",
                "must_fail_closure_when": "secureJsonData, passwords, tokens, or URL userinfo are present in stored evidence",
            },
        ],
        "stack.trace-backend": [
            {
                "key": "ready_only_without_trace_search_does_not_close",
                "must_fail_closure_when": "backend readiness exists but bounded trace search/export or traceparent join evidence is absent",
            },
            {
                "key": "raw_span_or_log_payload_rejects_closure",
                "must_fail_closure_when": "raw span attributes or raw log exports are stored instead of bounded/redacted evidence",
            },
        ],
        "stack.database-graph.read-route": [
            {
                "key": "tcp_and_root_metadata_do_not_close",
                "must_fail_closure_when": "Postgres TCP and Neo4j root metadata are visible but bounded schema/label/freshness inventory is absent",
            },
            {
                "key": "raw_rows_or_graph_properties_reject_closure",
                "must_fail_closure_when": "row payloads or private graph property values are included in stored evidence",
            },
        ],
        "stack.langchain-api.graph-observability": [
            {
                "key": "health_openapi_run_routes_do_not_close",
                "must_fail_closure_when": "health/OpenAPI/run routes exist but thread, checkpoint, trace inventory, or trace coupling is missing",
            },
            {
                "key": "prompt_message_tool_payloads_reject_closure",
                "must_fail_closure_when": "prompts, messages, tool payload bodies, or raw trace payloads are included",
            },
        ],
    }
    return controls + per_requirement.get(requirement_id, [])


def stack_requirement_closure_acceptance(
    entry: dict[str, Any], generated_at: str, *, config: SelfAwarenessRequirementConfig
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    self_awareness_stack_requirement_closure_acceptance_complete = partial(
        stack_requirement_closure_acceptance_complete, config=config
    )
    self_awareness_stack_requirement_negative_controls = (
        stack_requirement_negative_controls
    )
    requirement_id = str(entry.get("requirement_id") or entry.get("id") or "")
    readiness = (
        entry.get("closure_readiness")
        if isinstance(entry.get("closure_readiness"), dict)
        else {}
    )
    compat = (
        entry.get("compat_contract")
        if isinstance(entry.get("compat_contract"), dict)
        else {}
    )
    acceptance_contract = (
        entry.get("acceptance_contract")
        if isinstance(entry.get("acceptance_contract"), dict)
        else {}
    )
    coverage = (
        entry.get("coverage_impact")
        if isinstance(entry.get("coverage_impact"), dict)
        else {}
    )
    current_state = (
        entry.get("current_state")
        if isinstance(entry.get("current_state"), dict)
        else {}
    )
    fulfilled_checks = (
        entry.get("fulfilled_checks")
        if isinstance(entry.get("fulfilled_checks"), list)
        else readiness.get("fulfilled_checks")
        if isinstance(readiness.get("fulfilled_checks"), list)
        else []
    )
    blocking_keys = (
        entry.get("blocking_check_keys")
        if isinstance(entry.get("blocking_check_keys"), list)
        else readiness.get("blocking_check_keys")
        if isinstance(readiness.get("blocking_check_keys"), list)
        else []
    )
    verifier_commands = (
        entry.get("verifier_commands")
        if isinstance(entry.get("verifier_commands"), list)
        else readiness.get("verifier_commands")
        if isinstance(readiness.get("verifier_commands"), list)
        else []
    )
    post_close_verifiers = nested_get(
        compat, ["machine_consumer_contract", "post_close_verifiers"]
    )
    if not isinstance(post_close_verifiers, list):
        post_close_verifiers = (
            acceptance_contract.get("machine_verifiers")
            if isinstance(acceptance_contract.get("machine_verifiers"), list)
            else []
        )
    success_predicates = nested_get(
        compat, ["minimum_response_contract", "success_predicates"]
    )
    if not isinstance(success_predicates, list):
        success_predicates = (
            entry.get("success_predicates")
            if isinstance(entry.get("success_predicates"), list)
            else []
        )
    route_or_export_options = (
        compat.get("route_or_export_options")
        if isinstance(compat.get("route_or_export_options"), list)
        else []
    )
    expected_post_close_facts = [
        f"{requirement_id} is absent from stack_handoff.open_requirement_ids after current stack-owned evidence is readable",
        f"{requirement_id} has closed_by_current_probe=true in requirement-probes or is no longer emitted as open",
        "self-awareness validate has 0 fails and no new warnings for this closure surface",
    ]
    packet = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_acceptance_v1",
        "acceptance_id": "saclose-"
        + stable_hash_json(
            {
                "requirement_id": requirement_id,
                "current_state": current_state,
                "blocking_keys": blocking_keys,
            },
            length=20,
        ),
        "requirement_id": requirement_id,
        "owner": entry.get("owner") or "abyss-stack",
        "status": "closed_by_current_probe"
        if entry.get("closed_by_current_probe") is True
        else "awaiting_stack_owner_change",
        "requirement_status": entry.get("status"),
        "surface_kind": compat.get("surface_kind") or entry.get("probe_kind"),
        "generated_at": generated_at,
        "pre_close_identity": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_pre_close_identity_v1",
            "requirement_id": requirement_id,
            "status": entry.get("status"),
            "closed_by_current_probe": entry.get("closed_by_current_probe") is True,
            "current_state_digest": entry.get("current_state_digest")
            or stable_hash_json(current_state, length=24),
            "current_state_keys": sorted((str(key) for key in current_state.keys()))[
                :80
            ],
            "missing_check_keys": [str(item) for item in blocking_keys],
            "fulfilled_check_keys": [
                str(item.get("key"))
                for item in fulfilled_checks
                if isinstance(item, dict) and item.get("key")
            ],
            "depends_on_requirement_ids": entry.get("depends_on_requirement_ids")
            if isinstance(entry.get("depends_on_requirement_ids"), list)
            else entry.get("dependency_requirement_ids")
            if isinstance(entry.get("dependency_requirement_ids"), list)
            else [],
            "unblocks_requirement_ids": entry.get("unblocks_requirement_ids")
            if isinstance(entry.get("unblocks_requirement_ids"), list)
            else [],
            "coverage_planes": coverage.get("coverage_planes")
            if isinstance(coverage.get("coverage_planes"), list)
            else [],
        },
        "stack_compat_requirement": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_compat_requirement_v1",
            "requirement_id": requirement_id,
            "owner": "abyss-stack",
            "consumer": "abyss-machine:self-awareness",
            "surface_kind": compat.get("surface_kind")
            or entry.get("probe_kind")
            or "bounded_stack_inventory",
            "source_compat_contract_schema": compat.get("schema"),
            "source_compat_contract_digest": stable_hash_json(compat, length=24)
            if compat
            else None,
            "route_or_export_options": [str(item) for item in route_or_export_options],
            "minimum_response_contract": compat.get("minimum_response_contract")
            if isinstance(compat.get("minimum_response_contract"), dict)
            else {},
            "machine_consumer_contract": {
                "read_command": "abyss-machine self-awareness stack-closure-dossier --json",
                "probe_command": "abyss-machine self-awareness requirement-probes --json",
                "post_close_verifiers": post_close_verifiers,
                "expected_post_close_facts": expected_post_close_facts,
            },
            "dependency_contract": compat.get("dependency_contract")
            if isinstance(compat.get("dependency_contract"), dict)
            else {},
            "coverage_contract": compat.get("coverage_contract")
            if isinstance(compat.get("coverage_contract"), dict)
            else {},
            "redaction_contract": compat.get("redaction_contract")
            if isinstance(compat.get("redaction_contract"), dict)
            else {},
            "operator_boundary": {
                "operator_approval_required": True,
                "stack_owner_may_mutate_stack_after_operator_approval": True,
                "abyss_machine_executes_stack_change": False,
                "host_layer_mutates_stack": False,
                "automatic_remediation": False,
            },
        },
        "closure_diff_contract": {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_diff_contract_v1",
            "before_missing_check_keys": [str(item) for item in blocking_keys],
            "after_required_state": [
                "blocking_check_keys is empty for this requirement or the requirement is not emitted as open",
                "closed_by_current_probe is true only when required fields, success predicates, redaction, boundedness, and evidence refs pass",
                "coverage planes previously blocked by this requirement have current evidence refs before they move to covered",
            ],
            "no_partial_credit_conditions": [
                "HTTP 2xx alone is not closure",
                "candidate-only inference is not closure",
                "health-only liveness is not closure unless the acceptance contract says so and verifier evidence is present",
                "secret/private/raw payload leakage rejects closure",
            ],
            "current_state_digest_before": entry.get("current_state_digest")
            or stable_hash_json(current_state, length=24),
        },
        "post_close_success_predicates": [str(item) for item in success_predicates],
        "post_close_verifier_chain": [
            {
                "command": command,
                "must": [
                    "current bounded evidence proves this requirement closed without stack mutation"
                ],
            }
            for command in verifier_commands
        ]
        + [item for item in post_close_verifiers if isinstance(item, dict)],
        "negative_controls": self_awareness_stack_requirement_negative_controls(
            requirement_id
        ),
        "safe_next_action": entry.get("safe_next_action")
        if isinstance(entry.get("safe_next_action"), dict)
        else {},
        "evidence_refs": entry.get("evidence_refs")
        if isinstance(entry.get("evidence_refs"), list)
        else [],
        "policy": {
            "handoff_only": entry.get("closed_by_current_probe") is not True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_payloads_included": False,
        },
    }
    packet["complete"] = self_awareness_stack_requirement_closure_acceptance_complete(
        packet
    )
    return packet


def stack_requirement_closure_acceptance_complete(
    packet: Any, *, config: SelfAwarenessRequirementConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    pre_close = (
        packet.get("pre_close_identity")
        if isinstance(packet, dict)
        and isinstance(packet.get("pre_close_identity"), dict)
        else {}
    )
    compat = (
        packet.get("stack_compat_requirement")
        if isinstance(packet, dict)
        and isinstance(packet.get("stack_compat_requirement"), dict)
        else {}
    )
    diff = (
        packet.get("closure_diff_contract")
        if isinstance(packet, dict)
        and isinstance(packet.get("closure_diff_contract"), dict)
        else {}
    )
    return (
        isinstance(packet, dict)
        and packet.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_acceptance_v1"
        and bool(packet.get("requirement_id"))
        and (packet.get("owner") == "abyss-stack")
        and (
            pre_close.get("schema")
            == f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_pre_close_identity_v1"
        )
        and (pre_close.get("requirement_id") == packet.get("requirement_id"))
        and isinstance(pre_close.get("missing_check_keys"), list)
        and (
            compat.get("schema")
            == f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_compat_requirement_v1"
        )
        and (compat.get("requirement_id") == packet.get("requirement_id"))
        and (compat.get("owner") == "abyss-stack")
        and bool(compat.get("route_or_export_options"))
        and isinstance(
            nested_get(compat, ["machine_consumer_contract", "post_close_verifiers"]),
            list,
        )
        and bool(
            nested_get(compat, ["machine_consumer_contract", "post_close_verifiers"])
        )
        and isinstance(
            nested_get(
                compat, ["machine_consumer_contract", "expected_post_close_facts"]
            ),
            list,
        )
        and bool(
            nested_get(
                compat, ["machine_consumer_contract", "expected_post_close_facts"]
            )
        )
        and (
            nested_get(
                compat, ["operator_boundary", "abyss_machine_executes_stack_change"]
            )
            is False
        )
        and (
            nested_get(compat, ["operator_boundary", "host_layer_mutates_stack"])
            is False
        )
        and (
            nested_get(compat, ["operator_boundary", "automatic_remediation"]) is False
        )
        and (nested_get(compat, ["redaction_contract", "raw_secrets_allowed"]) is False)
        and (
            nested_get(compat, ["redaction_contract", "raw_private_payloads_allowed"])
            is False
        )
        and (
            diff.get("schema")
            == f"{SCHEMA_PREFIX}_self_awareness_stack_requirement_closure_diff_contract_v1"
        )
        and isinstance(packet.get("post_close_success_predicates"), list)
        and bool(packet.get("post_close_success_predicates"))
        and isinstance(packet.get("post_close_verifier_chain"), list)
        and bool(packet.get("post_close_verifier_chain"))
        and isinstance(packet.get("negative_controls"), list)
        and bool(packet.get("negative_controls"))
        and isinstance(packet.get("evidence_refs"), list)
        and bool(packet.get("evidence_refs"))
        and (nested_get(packet, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(packet, ["policy", "executes_commands"]) is False)
        and (nested_get(packet, ["policy", "action_execution"]) is False)
        and (nested_get(packet, ["policy", "automatic_remediation"]) is False)
        and (nested_get(packet, ["policy", "raw_secrets_included"]) is False)
    )


def requirement_handoff(
    requirement: dict[str, Any], *, config: SelfAwarenessRequirementConfig
) -> dict[str, Any]:
    self_awareness_requirement_acceptance_contract = partial(
        requirement_acceptance_contract, config=config
    )
    self_awareness_stack_requirement_compat_contract = partial(
        stack_requirement_compat_contract, config=config
    )
    requirement_id = str(requirement.get("id") or "")
    expected_shape = (
        requirement.get("expected_shape")
        if isinstance(requirement.get("expected_shape"), dict)
        else {}
    )
    acceptance_contract = self_awareness_requirement_acceptance_contract(requirement)
    compat_contract = self_awareness_stack_requirement_compat_contract(
        requirement, acceptance_contract=acceptance_contract
    )
    base = {
        "id": requirement_id,
        "requirement_id": requirement_id,
        "owner": requirement.get("owner"),
        "status": requirement.get("status"),
        "machine_read_command": "abyss-machine self-awareness requirements --json",
        "evidence_commands": [
            "abyss-machine self-awareness capabilities --json",
            "abyss-machine self-awareness failure-matrix --json",
            "abyss-machine self-awareness cycle --json",
            "abyss-machine self-awareness validate --json",
        ],
        "expected_shape": expected_shape,
        "acceptance_contract": acceptance_contract,
        "compat_contract": compat_contract,
        "machine_closure_probe": acceptance_contract.get("probe_plan"),
        "host_layer_mutates_stack": False,
        "acceptance_after_stack_change": [
            "abyss-machine self-awareness capabilities --json reports no open requirement for this id",
            "abyss-machine self-awareness requirements --json keeps evidence refs and owner route current",
            "abyss-machine self-awareness cycle --json preserves closed requirement state and non-mutating response policy",
            "abyss-machine self-awareness validate --json passes without new warnings",
            "abyss-machine stack-bridge validate --json passes without static bridge drift",
        ],
    }
    per_requirement: dict[str, Any] = {
        "stack.grafana.datasource-read": {
            "stack_acceptance": [
                "Grafana datasource inventory is available through a stack-owned read-only token or bounded inventory endpoint",
                "No Grafana credential is stored in abyss-machine latest/history artifacts",
                "Datasource identity and freshness can be cited by machine correlation outputs",
            ]
        },
        "stack.trace-backend": {
            "stack_acceptance": [
                "Tempo or compatible trace backend exposes a read-only health endpoint",
                "W3C traceparent joins can be searched or exported for span/log/metric correlation",
                "Trace backend evidence is available without abyss-machine modifying stack runtime config",
            ]
        },
        "stack.database-graph.read-route": {
            "stack_acceptance": [
                "route-api health and bounded OpenAPI remain readable as route/federation context",
                "rag-api health, bounded OpenAPI, collections, sources, and agentic graph shape remain readable without raw source documents",
                "Postgres service readiness and Neo4j root metadata are visible without storing database credentials",
                "Postgres schema/freshness inventory is exposed through a bounded read-only stack route",
                "Neo4j label/relationship/freshness inventory is exposed through a bounded read-only stack route",
                "Database and graph inventories are safe for machine correlation and do not expose private row payloads by default",
            ]
        },
        "stack.langchain-api.graph-observability": {
            "stack_acceptance": [
                "langchain-api health, OpenAPI, run, federated run, and embeddings route shape remain readable through stack-owned routes",
                "LangChain/LangGraph API exposes read-only thread, checkpoint, and trace inventory with freshness",
                "Trace backend or equivalent trace route is available for span/log/metric joins",
                "Checkpoint inventory can be cited by self-awareness investigation/replay outputs",
                "The API route is stack-owned and bounded; abyss-machine remains a read-only consumer and stores no prompts, messages, tool payloads, or raw trace payloads",
            ]
        },
    }
    base.update(
        per_requirement.get(
            requirement_id,
            {
                "stack_acceptance": [
                    "Stack-owned route exposes the expected shape through a bounded read-only interface"
                ]
            },
        )
    )
    return base


def requirements_with_probe_readiness(
    requirements_doc: dict[str, Any],
    requirement_probes_doc: dict[str, Any],
    *,
    paths: SelfAwarenessRequirementPaths,
    config: SelfAwarenessRequirementConfig,
    runtime_port: SelfAwarenessRequirementRuntimePort,
    contract_port: SelfAwarenessRequirementContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    self_awareness_brief_stack_handoff_action_map = (
        contract_port.brief_stack_handoff_action_map
    )
    self_awareness_requirement_acceptance_contract = partial(
        requirement_acceptance_contract, config=config
    )
    self_awareness_requirement_handoff = partial(requirement_handoff, config=config)
    self_awareness_requirement_probes_cover_requirements = (
        requirement_probes_cover_requirements
    )
    self_awareness_stack_requirement_compat_contract = partial(
        stack_requirement_compat_contract, config=config
    )
    self_awareness_stack_requirement_coverage_impact = partial(
        stack_requirement_coverage_impact, config=config
    )
    if not isinstance(requirements_doc, dict) or not isinstance(
        requirement_probes_doc, dict
    ):
        return requirements_doc
    if (
        requirement_probes_doc.get("schema")
        != f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1"
    ):
        return requirements_doc
    if not self_awareness_requirement_probes_cover_requirements(
        requirements_doc, requirement_probes_doc
    ):
        return requirements_doc
    probes = (
        requirement_probes_doc.get("probes")
        if isinstance(requirement_probes_doc.get("probes"), list)
        else []
    )
    probe_by_id = {
        str(probe.get("requirement_id") or probe.get("id")): probe
        for probe in probes
        if isinstance(probe, dict) and (probe.get("requirement_id") or probe.get("id"))
    }
    action_map = self_awareness_brief_stack_handoff_action_map(requirement_probes_doc)
    action_by_id = {
        str(action.get("requirement_id")): action
        for action in (
            action_map.get("actions")
            if isinstance(action_map.get("actions"), list)
            else []
        )
        if isinstance(action, dict) and action.get("requirement_id")
    }
    handoff_by_id = {
        str(handoff.get("requirement_id") or handoff.get("id")): handoff
        for handoff in (
            requirements_doc.get("stack_handoff")
            if isinstance(requirements_doc.get("stack_handoff"), list)
            else []
        )
        if isinstance(handoff, dict)
        and (handoff.get("requirement_id") or handoff.get("id"))
    }

    def compact_check(check: Any) -> dict[str, Any] | None:
        if not isinstance(check, dict):
            return None
        return {
            "key": check.get("key"),
            "level": check.get("level"),
            "ok": check.get("ok"),
            "message": check.get("message"),
        }

    def compact_readiness(
        requirement_id: str, probe: dict[str, Any], action: dict[str, Any]
    ) -> dict[str, Any]:
        readiness = (
            probe.get("closure_readiness")
            if isinstance(probe.get("closure_readiness"), dict)
            else {}
        )
        missing_checks = [
            item
            for item in (
                compact_check(check)
                for check in (
                    readiness.get("missing_checks")
                    if isinstance(readiness.get("missing_checks"), list)
                    else []
                )
            )
            if item is not None
        ]
        fulfilled_checks = [
            item
            for item in (
                compact_check(check)
                for check in (
                    readiness.get("fulfilled_checks")
                    if isinstance(readiness.get("fulfilled_checks"), list)
                    else []
                )
            )
            if item is not None
        ]
        return {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_readiness_summary_v1",
            "requirement_id": requirement_id,
            "status": readiness.get("status") or probe.get("status"),
            "closed_by_current_probe": probe.get("closed_by_current_probe") is True,
            "readiness_score": readiness.get("readiness_score"),
            "fulfilled_check_count": safe_int(
                readiness.get("fulfilled_check_count"), len(fulfilled_checks)
            ),
            "missing_check_count": safe_int(
                readiness.get("open_blocker_count"), len(missing_checks)
            ),
            "blocking_check_keys": readiness.get("blocking_check_keys")
            if isinstance(readiness.get("blocking_check_keys"), list)
            else [],
            "missing_checks": missing_checks,
            "fulfilled_checks": fulfilled_checks,
            "dependency_requirement_ids": readiness.get("dependency_requirement_ids")
            if isinstance(readiness.get("dependency_requirement_ids"), list)
            else [],
            "runbook_candidate_id": readiness.get("runbook_candidate_id")
            or nested_get(probe, ["runbook_candidate", "id"])
            or action.get("runbook_candidate_id"),
            "verifier_commands": readiness.get("verifier_commands")
            if isinstance(readiness.get("verifier_commands"), list)
            else action.get("verifier_commands")
            if isinstance(action.get("verifier_commands"), list)
            else [],
            "safe_next_action": readiness.get("safe_next_action")
            if isinstance(readiness.get("safe_next_action"), dict)
            else action.get("safe_next_action")
            if isinstance(action.get("safe_next_action"), dict)
            else {},
            "coverage_impact": action.get("coverage_impact")
            if isinstance(action.get("coverage_impact"), dict)
            else self_awareness_stack_requirement_coverage_impact(requirement_id),
            "evidence_refs": probe.get("evidence_refs")
            if isinstance(probe.get("evidence_refs"), list)
            else [],
            "policy": {
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "raw_secrets_included": False,
            },
        }

    def first_list(*values: Any) -> list[Any]:
        for value in values:
            if isinstance(value, list) and value:
                return value
        return []

    def first_dict(*values: Any) -> dict[str, Any]:
        for value in values:
            if isinstance(value, dict) and value:
                return value
        return {}

    def current_state_digest(probe: dict[str, Any]) -> dict[str, Any]:
        current_state = (
            probe.get("current_state")
            if isinstance(probe.get("current_state"), dict)
            else {}
        )
        evidence_refs = (
            probe.get("evidence_refs")
            if isinstance(probe.get("evidence_refs"), list)
            else []
        )
        return {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_current_state_digest_v1",
            "has_current_state": bool(current_state),
            "keys": sorted((str(key) for key in current_state.keys()))[:80],
            "evidence_refs": len(evidence_refs),
            "policy": {
                "raw_payloads_included": False,
                "raw_secrets_included": False,
                "host_layer_mutates_stack": False,
            },
        }

    def probe_effective_status(probe: dict[str, Any]) -> str:
        status = str(probe.get("status") or "")
        if probe.get("closed_by_current_probe") is True or status in {
            "closed",
            "closed_by_current_probe",
        }:
            return "closed"
        return status or "open"

    def probe_current_state_snapshot(probe: dict[str, Any]) -> dict[str, Any]:
        current_state = (
            probe.get("current_state")
            if isinstance(probe.get("current_state"), dict)
            else {}
        )
        if not current_state:
            return {}
        preview = json.dumps(current_state, sort_keys=True, default=str)[:50000]
        if runtime_port.secret_search(preview):
            return {
                "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_current_state_redacted_v1",
                "redacted_due_to_secret_pattern": True,
                "keys": sorted((str(key) for key in current_state.keys()))[:80],
                "policy": {
                    "raw_payloads_included": False,
                    "raw_secrets_included": False,
                    "host_layer_mutates_stack": False,
                },
            }
        return current_state

    def add_direct_handoff_contract_fields(
        item: dict[str, Any],
        *,
        requirement_id: str,
        probe: dict[str, Any],
        action: dict[str, Any],
        source_handoff: dict[str, Any],
        readiness_summary: dict[str, Any],
    ) -> None:
        runbook = first_dict(
            probe.get("runbook_candidate"), action.get("runbook_candidate")
        )
        fresh_requirement = dict(source_handoff)
        fresh_requirement.update(item)
        fresh_requirement["id"] = requirement_id
        fresh_requirement["requirement_id"] = requirement_id
        fresh_requirement["owner"] = fresh_requirement.get("owner") or "abyss-stack"
        effective_status = probe_effective_status(probe)
        fresh_requirement["status"] = effective_status
        fresh_contract = self_awareness_requirement_acceptance_contract(
            fresh_requirement
        )
        fresh_handoff = self_awareness_requirement_handoff(fresh_requirement)
        item["status"] = effective_status
        item["probe_status"] = str(probe.get("status") or effective_status)
        item["current_state"] = probe_current_state_snapshot(probe)
        item["evidence_refs"] = (
            probe.get("evidence_refs")
            if isinstance(probe.get("evidence_refs"), list)
            else item.get("evidence_refs", [])
        )
        item["acceptance_contract"] = fresh_contract
        item["machine_closure_probe"] = (
            fresh_contract.get("probe_plan")
            if isinstance(fresh_contract.get("probe_plan"), dict)
            else {}
        )
        item["acceptance_verifiers"] = (
            fresh_contract.get("machine_verifiers")
            if isinstance(fresh_contract.get("machine_verifiers"), list)
            else []
        )
        item["acceptance_after_stack_change"] = (
            fresh_handoff.get("acceptance_after_stack_change")
            if isinstance(fresh_handoff.get("acceptance_after_stack_change"), list)
            else []
        )
        item["stack_acceptance"] = first_list(
            fresh_handoff.get("stack_acceptance"),
            source_handoff.get("stack_acceptance"),
            nested_get(runbook, ["problem", "stack_acceptance"]),
        )
        item["coverage_impact"] = (
            readiness_summary.get("coverage_impact")
            if isinstance(readiness_summary.get("coverage_impact"), dict)
            else self_awareness_stack_requirement_coverage_impact(requirement_id)
        )
        item["safe_next_action"] = (
            readiness_summary.get("safe_next_action")
            if isinstance(readiness_summary.get("safe_next_action"), dict)
            else {}
        )
        item["current_state_digest"] = current_state_digest(probe)
        item["closed_by_current_probe"] = probe.get("closed_by_current_probe") is True
        item["handoff_contract_complete"] = (
            bool(item.get("acceptance_contract"))
            and bool(item.get("machine_closure_probe"))
            and bool(item.get("acceptance_verifiers"))
            and bool(item.get("coverage_impact"))
            and (nested_get(item, ["policy", "host_layer_mutates_stack"]) is not True)
        )

    enriched = dict(requirements_doc)
    requirements = []
    for requirement in (
        requirements_doc.get("requirements", [])
        if isinstance(requirements_doc.get("requirements"), list)
        else []
    ):
        if not isinstance(requirement, dict):
            requirements.append(requirement)
            continue
        requirement_id = str(
            requirement.get("id") or requirement.get("requirement_id") or ""
        )
        probe = probe_by_id.get(requirement_id, {})
        action = action_by_id.get(requirement_id, {})
        source_handoff = handoff_by_id.get(requirement_id, {})
        item = dict(requirement)
        if isinstance(probe, dict) and probe:
            readiness_summary = compact_readiness(
                requirement_id, probe, action if isinstance(action, dict) else {}
            )
            fresh_acceptance_contract = self_awareness_requirement_acceptance_contract(
                item
            )
            compat_contract = self_awareness_stack_requirement_compat_contract(
                item,
                acceptance_contract=fresh_acceptance_contract,
                readiness=probe.get("closure_readiness")
                if isinstance(probe.get("closure_readiness"), dict)
                else readiness_summary,
                current_state=probe.get("current_state")
                if isinstance(probe.get("current_state"), dict)
                else {},
                coverage_impact=readiness_summary.get("coverage_impact")
                if isinstance(readiness_summary.get("coverage_impact"), dict)
                else None,
                dependency_requirement_ids=readiness_summary.get(
                    "dependency_requirement_ids"
                )
                if isinstance(readiness_summary.get("dependency_requirement_ids"), list)
                else [],
            )
            item["closure_readiness"] = readiness_summary
            item["missing_checks"] = readiness_summary["missing_checks"]
            item["blocking_check_keys"] = readiness_summary["blocking_check_keys"]
            item["runbook_candidate_id"] = readiness_summary["runbook_candidate_id"]
            item["verifier_commands"] = readiness_summary["verifier_commands"]
            item["compat_contract"] = compat_contract
            add_direct_handoff_contract_fields(
                item,
                requirement_id=requirement_id,
                probe=probe,
                action=action if isinstance(action, dict) else {},
                source_handoff=source_handoff
                if isinstance(source_handoff, dict)
                else {},
                readiness_summary=readiness_summary,
            )
        requirements.append(item)
    enriched["requirements"] = requirements
    stack_handoff = []
    for handoff in (
        requirements_doc.get("stack_handoff", [])
        if isinstance(requirements_doc.get("stack_handoff"), list)
        else []
    ):
        if not isinstance(handoff, dict):
            stack_handoff.append(handoff)
            continue
        requirement_id = str(handoff.get("id") or handoff.get("requirement_id") or "")
        probe = probe_by_id.get(requirement_id, {})
        action = action_by_id.get(requirement_id, {})
        item = dict(handoff)
        if isinstance(probe, dict) and probe:
            readiness_summary = compact_readiness(
                requirement_id, probe, action if isinstance(action, dict) else {}
            )
            item["closure_readiness"] = readiness_summary
            item["missing_checks"] = readiness_summary["missing_checks"]
            item["blocking_check_keys"] = readiness_summary["blocking_check_keys"]
            item["runbook_candidate_id"] = readiness_summary["runbook_candidate_id"]
            item["verifier_commands"] = readiness_summary["verifier_commands"]
            item["safe_next_action"] = readiness_summary["safe_next_action"]
            item["coverage_impact"] = readiness_summary["coverage_impact"]
            fresh_acceptance_contract = self_awareness_requirement_acceptance_contract(
                item
            )
            item["compat_contract"] = self_awareness_stack_requirement_compat_contract(
                item,
                acceptance_contract=fresh_acceptance_contract,
                readiness=probe.get("closure_readiness")
                if isinstance(probe.get("closure_readiness"), dict)
                else readiness_summary,
                current_state=probe.get("current_state")
                if isinstance(probe.get("current_state"), dict)
                else {},
                coverage_impact=readiness_summary.get("coverage_impact")
                if isinstance(readiness_summary.get("coverage_impact"), dict)
                else None,
                dependency_requirement_ids=readiness_summary.get(
                    "dependency_requirement_ids"
                )
                if isinstance(readiness_summary.get("dependency_requirement_ids"), list)
                else [],
            )
            add_direct_handoff_contract_fields(
                item,
                requirement_id=requirement_id,
                probe=probe,
                action=action if isinstance(action, dict) else {},
                source_handoff=handoff,
                readiness_summary=readiness_summary,
            )
        stack_handoff.append(item)
    enriched["stack_handoff"] = stack_handoff
    summary = dict(
        enriched.get("summary") if isinstance(enriched.get("summary"), dict) else {}
    )
    closure_packets = [
        item.get("closure_readiness")
        for item in stack_handoff
        if isinstance(item, dict) and isinstance(item.get("closure_readiness"), dict)
    ]
    open_stack_ids = [
        str(item.get("requirement_id") or item.get("id"))
        for item in stack_handoff
        if isinstance(item, dict)
        and (item.get("requirement_id") or item.get("id"))
        and (item.get("owner") == "abyss-stack")
        and (item.get("closed_by_current_probe") is not True)
    ]
    closed_stack_ids = [
        str(item.get("requirement_id") or item.get("id"))
        for item in stack_handoff
        if isinstance(item, dict)
        and (item.get("requirement_id") or item.get("id"))
        and (item.get("owner") == "abyss-stack")
        and (item.get("closed_by_current_probe") is True)
    ]
    summary.update(
        {
            "open_stack_requirements": len(open_stack_ids),
            "closed_stack_requirements": len(closed_stack_ids),
            "stack_handoff_acceptance_verifiers": sum(
                (
                    1
                    for item in stack_handoff
                    if isinstance(item, dict) and item.get("acceptance_verifiers")
                )
            ),
            "stack_handoff_acceptance_verifier_steps": sum(
                (
                    len(
                        item.get("acceptance_verifiers")
                        if isinstance(item.get("acceptance_verifiers"), list)
                        else []
                    )
                    for item in stack_handoff
                    if isinstance(item, dict)
                )
            ),
            "stack_handoff_closure_readiness_packets": len(closure_packets),
            "stack_handoff_closure_readiness_missing_checks": sum(
                (
                    safe_int(packet.get("missing_check_count"), 0)
                    for packet in closure_packets
                )
            ),
            "stack_handoff_closure_readiness_fulfilled_checks": sum(
                (
                    safe_int(packet.get("fulfilled_check_count"), 0)
                    for packet in closure_packets
                )
            ),
            "stack_handoff_runbook_candidates": sum(
                (
                    1
                    for item in stack_handoff
                    if isinstance(item, dict) and item.get("runbook_candidate_id")
                )
            ),
            "stack_handoff_safe_next_actions": sum(
                (
                    1
                    for item in stack_handoff
                    if isinstance(item, dict)
                    and isinstance(item.get("safe_next_action"), dict)
                    and item.get("safe_next_action")
                )
            ),
            "stack_handoff_coverage_impact_entries": sum(
                (
                    1
                    for item in stack_handoff
                    if isinstance(item, dict)
                    and isinstance(item.get("coverage_impact"), dict)
                    and item.get("coverage_impact")
                )
            ),
            "stack_handoff_verifier_commands": len(
                sorted(
                    {
                        str(command)
                        for item in stack_handoff
                        if isinstance(item, dict)
                        for command in (
                            item.get("verifier_commands")
                            if isinstance(item.get("verifier_commands"), list)
                            else []
                        )
                        if command
                    }
                )
            ),
            "top_stack_handoff_requirement": nested_get(
                action_map, ["summary", "top_requirement_id"]
            ),
        }
    )
    enriched["summary"] = summary
    enriched["status"] = "open_requirements" if open_stack_ids else "satisfied"
    enriched["open_stack_ids"] = open_stack_ids
    enriched["open_stack_requirement_ids"] = open_stack_ids
    enriched["closed_stack_ids"] = closed_stack_ids
    enriched["closed_stack_requirement_ids"] = closed_stack_ids
    enriched["stack_handoff_closure_order"] = [
        {
            "rank": action.get("priority_rank"),
            "requirement_id": action.get("requirement_id"),
            "priority_class": action.get("priority_class"),
            "blocking_check_keys": action.get("closure_blocker_keys"),
            "runbook_candidate_id": action.get("runbook_candidate_id"),
            "verifier_commands": action.get("verifier_commands")
            if isinstance(action.get("verifier_commands"), list)
            else [],
            "acceptance_verifiers": action.get("acceptance_verifiers")
            if isinstance(action.get("acceptance_verifiers"), list)
            else [],
            "dependency_requirement_ids": action.get("dependency_requirement_ids")
            if isinstance(action.get("dependency_requirement_ids"), list)
            else [],
            "coverage_impact": action.get("coverage_impact")
            if isinstance(action.get("coverage_impact"), dict)
            else {},
            "safe_next_action": action.get("safe_next_action"),
        }
        for action in (
            action_map.get("actions")
            if isinstance(action_map.get("actions"), list)
            else []
        )
        if isinstance(action, dict)
    ]
    enriched["stack_handoff_action_summary"] = (
        action_map.get("summary") if isinstance(action_map.get("summary"), dict) else {}
    )
    enriched["evidence_refs"] = list(
        enriched.get("evidence_refs")
        if isinstance(enriched.get("evidence_refs"), list)
        else []
    ) + [
        {
            "path": str(SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH),
            "schema": requirement_probes_doc.get("schema"),
        }
    ]
    return enriched


def requirements_document(
    requirements: list[dict[str, Any]],
    generated_at: str,
    *,
    paths: SelfAwarenessRequirementPaths,
    config: SelfAwarenessRequirementConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_FAILURE_MATRIX_LATEST_PATH = paths.failure_matrix_latest
    SELF_AWARENESS_CYCLE_LATEST_PATH = paths.cycle_latest
    self_awareness_requirement_handoff = partial(requirement_handoff, config=config)
    self_awareness_stack_compat_contract_complete = partial(
        stack_compat_contract_complete, config=config
    )
    by_owner = dict(
        collections.Counter(
            (str(item.get("owner") or "unknown") for item in requirements)
        )
    )
    stack_handoff = [
        self_awareness_requirement_handoff(item)
        for item in requirements
        if item.get("owner") == "abyss-stack"
    ]
    handoff_identity_ok = all(
        (
            item.get("id") and item.get("requirement_id") == item.get("id")
            for item in stack_handoff
        )
    )
    handoff_acceptance_ok = all(
        (
            isinstance(item.get("acceptance_contract"), dict)
            and item["acceptance_contract"].get("schema")
            == f"{SCHEMA_PREFIX}_stack_requirement_acceptance_contract_v1"
            and isinstance(item.get("machine_closure_probe"), dict)
            and bool(item["machine_closure_probe"].get("required_fields"))
            and bool(item["machine_closure_probe"].get("success_predicates"))
            and (
                item["acceptance_contract"]
                .get("closure_semantics", {})
                .get("host_layer_mutates_stack")
                is False
            )
            and self_awareness_stack_compat_contract_complete(
                item.get("compat_contract")
            )
            for item in stack_handoff
        )
    )
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_requirements_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "ok": all(
            (item.get("owner") and item.get("expected_shape") for item in requirements)
        )
        and handoff_identity_ok
        and handoff_acceptance_ok,
        "status": "open_requirements" if requirements else "satisfied",
        "summary": {
            "requirements": len(requirements),
            "by_owner": by_owner,
            "stack_owned": sum(
                (1 for item in requirements if item.get("owner") == "abyss-stack")
            ),
            "machine_owned": sum(
                (1 for item in requirements if item.get("owner") == "abyss-machine")
            ),
            "stack_handoff_acceptance_contracts": sum(
                (
                    1
                    for item in stack_handoff
                    if isinstance(item.get("acceptance_contract"), dict)
                )
            ),
            "stack_handoff_compat_contracts": sum(
                (
                    1
                    for item in stack_handoff
                    if self_awareness_stack_compat_contract_complete(
                        item.get("compat_contract")
                    )
                )
            ),
        },
        "requirements": requirements,
        "stack_handoff": stack_handoff,
        "failure_matrix_latest": str(SELF_AWARENESS_FAILURE_MATRIX_LATEST_PATH),
        "cycle_latest": str(SELF_AWARENESS_CYCLE_LATEST_PATH),
        "policy": {
            "requirements_are_not_stack_mutations": True,
            "owner_route_required_before_runtime_change": True,
            "stack_handoff_is_machine_checkable": True,
        },
    }


def requirements(
    write_latest: bool = True,
    *,
    paths: SelfAwarenessRequirementPaths,
    config: SelfAwarenessRequirementConfig,
    runtime_port: SelfAwarenessRequirementRuntimePort,
    refresh_port: SelfAwarenessRequirementRefreshPort,
    contract_port: SelfAwarenessRequirementContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_REQUIREMENTS_LATEST_PATH = paths.requirements_latest
    SELF_AWARENESS_REQUIREMENTS_ROOT = paths.requirements_root
    SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH = paths.requirement_probes_latest
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    self_awareness_capabilities = refresh_port.capabilities
    self_awareness_requirements_document = partial(
        requirements_document, paths=paths, config=config
    )
    self_awareness_requirements_with_probe_readiness = partial(
        requirements_with_probe_readiness,
        paths=paths,
        config=config,
        runtime_port=runtime_port,
        contract_port=contract_port,
    )
    if write_latest:
        self_awareness_capabilities(write_latest=True)
    data = load_latest_json(
        SELF_AWARENESS_REQUIREMENTS_LATEST_PATH,
        f"{SCHEMA_PREFIX}_self_awareness_requirements_v1",
    )
    if not data.get("schema"):
        data = self_awareness_requirements_document([], now_iso())
    data = dict(data)
    requirement_probes = load_latest_json(
        SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH,
        f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1",
    )
    data = self_awareness_requirements_with_probe_readiness(data, requirement_probes)
    data["read_at"] = now_iso()
    data["command"] = "abyss-machine self-awareness requirements --json"
    data["ok"] = bool(data.get("ok")) and all(
        (
            isinstance(item, dict)
            and item.get("owner")
            and item.get("expected_shape")
            and (item.get("host_layer_mutates_stack") is False)
            for item in data.get("requirements", [])
            if isinstance(item, dict)
        )
    )
    if write_latest:
        errors = write_latest_and_history(
            data,
            SELF_AWARENESS_REQUIREMENTS_LATEST_PATH,
            SELF_AWARENESS_REQUIREMENTS_ROOT,
        )
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def stack_requirement_runbook_candidate(
    requirement_id: str,
    handoff: dict[str, Any],
    probe_plan: dict[str, Any],
    current_state: dict[str, Any],
    evidence_refs: list[dict[str, Any]],
    *,
    config: SelfAwarenessRequirementConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    title = str(handoff.get("title") or requirement_id)
    contract = (
        handoff.get("acceptance_contract")
        if isinstance(handoff.get("acceptance_contract"), dict)
        else {}
    )
    stack_acceptance = (
        handoff.get("stack_acceptance")
        if isinstance(handoff.get("stack_acceptance"), list)
        else []
    )
    acceptance_after = (
        handoff.get("acceptance_after_stack_change")
        if isinstance(handoff.get("acceptance_after_stack_change"), list)
        else []
    )
    machine_verifiers = (
        contract.get("machine_verifiers")
        if isinstance(contract.get("machine_verifiers"), list)
        else []
    )
    affected_surfaces = [
        "abyss-stack runtime/config",
        "abyss-stack read-only API/export surface",
    ]
    risks = [
        "stack-owned route may expose more evidence than intended if not bounded and redacted"
    ]
    rollback_steps = [
        "revert the stack-owned endpoint, export, datasource auth policy, or service route that introduced the capability",
        "rerun abyss-machine self-awareness capabilities --json",
        "rerun abyss-machine self-awareness requirement-probes --json",
        "rerun abyss-machine self-awareness validate --json",
    ]
    if requirement_id == "stack.grafana.datasource-read":
        affected_surfaces = [
            "Grafana datasource inventory route",
            "Grafana read-only auth policy",
            "stack bridge datasource export",
        ]
        risks = [
            "read-only auth token could be over-scoped",
            "datasource URLs could leak credentials if userinfo or secure fields are not stripped",
            "unbounded datasource export could include plugin-specific secret fields",
        ]
        rollback_steps.insert(
            0, "remove the stack-owned datasource inventory export or read-only token"
        )
    elif requirement_id == "stack.trace-backend":
        affected_surfaces = [
            "Tempo or trace backend service",
            "OTel/Alloy trace pipeline",
            "trace retention storage",
        ]
        risks = [
            "trace backend can increase storage and resource pressure",
            "span attributes can contain private payload fragments if instrumentation is not filtered",
            "partial trace propagation can create false confidence in causality",
        ]
        rollback_steps.insert(
            0, "disable the stack-owned trace backend route or trace pipeline change"
        )
    elif requirement_id == "stack.database-graph.read-route":
        affected_surfaces = [
            "Postgres schema/freshness inventory route",
            "Neo4j label/relationship inventory route",
            "RAG/graph semantic inventory export",
        ]
        risks = [
            "database inventory could accidentally include row payloads",
            "graph inventory could expose private property values",
            "large schema/graph exports can become expensive if not bounded",
        ]
        rollback_steps.insert(
            0,
            "remove the stack-owned database/graph inventory export or read-only route",
        )
    elif requirement_id == "stack.langchain-api.graph-observability":
        affected_surfaces = [
            "langchain-api runtime route shape",
            "LangGraph thread/checkpoint inventory",
            "trace/checkpoint metadata export",
            "Tempo or equivalent trace backend coupling",
        ]
        risks = [
            "checkpoint inventory could expose prompts, messages, or tool payload bodies",
            "trace inventory could expose raw span attributes or private payload fragments",
            "thread/checkpoint listing can become high-cardinality without limits",
            "health-only success can hide missing checkpoint, thread, trace, or backend inventory",
        ]
        rollback_steps.insert(
            0, "remove the stack-owned LangChain/LangGraph inventory route"
        )
    acceptance_steps = [
        {"command": command.get("command"), "must": command.get("must")}
        for command in machine_verifiers
        if isinstance(command, dict)
    ] + [
        {
            "command": "abyss-machine self-awareness capabilities --json",
            "must": [
                "requirement is no longer open after stack-owned route is readable"
            ],
        },
        {
            "command": "abyss-machine self-awareness requirement-probes --json",
            "must": [
                "closed_by_current_probe is true for this requirement or stack_handoff excludes it"
            ],
        },
        {
            "command": "abyss-machine self-awareness validate --json",
            "must": ["0 fails and 0 new warnings"],
        },
        {
            "command": "abyss-machine stack-bridge validate --json",
            "must": ["0 fails and 0 new warnings"],
        },
    ]
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_requirement_runbook_candidate_v1",
        "id": "stack-runbook-"
        + re.sub("[^a-z0-9]+", "-", requirement_id.lower()).strip("-"),
        "requirement_id": requirement_id,
        "title": title,
        "owner_route": "abyss-stack",
        "status": "candidate",
        "machine_action": "handoff_only",
        "source_command": "abyss-machine self-awareness requirement-probes --json",
        "host_layer_mutates_stack": False,
        "machine_executes_stack_change": False,
        "stack_owner_may_mutate_stack": True,
        "operator_approval_required": True,
        "problem": {
            "current_state": current_state,
            "stack_acceptance": stack_acceptance,
        },
        "proposed_stack_work": {
            "kind": probe_plan.get("kind"),
            "candidate_routes": probe_plan.get("candidate_routes")
            if isinstance(probe_plan.get("candidate_routes"), list)
            else [],
            "required_fields": probe_plan.get("required_fields")
            if isinstance(probe_plan.get("required_fields"), list)
            else [],
            "success_predicates": probe_plan.get("success_predicates")
            if isinstance(probe_plan.get("success_predicates"), list)
            else [],
            "redaction_rules": probe_plan.get("redaction_rules")
            if isinstance(probe_plan.get("redaction_rules"), list)
            else [],
            "boundedness": probe_plan.get("boundedness")
            if isinstance(probe_plan.get("boundedness"), dict)
            else {},
        },
        "acceptance_steps": acceptance_steps,
        "acceptance_verifiers": acceptance_steps,
        "acceptance_after_stack_change": acceptance_after,
        "risk": {
            "level": "medium",
            "risks": risks,
            "required_mitigations": [
                "bounded result size",
                "redaction rules enforced before abyss-machine stores evidence",
                "read-only route or exported inventory only",
                "no raw credentials, prompts, row payloads, or private graph properties",
            ],
        },
        "blast_radius": {
            "owner": "abyss-stack",
            "affected_surfaces": affected_surfaces,
            "not_affected": [
                "/usr/local/libexec/abyss-machine",
                "/var/lib/abyss-machine/self-awareness",
                "/srv/abyss-machine/tests",
            ],
        },
        "rollback": {
            "owner": "abyss-stack",
            "steps": rollback_steps,
            "machine_recovery": "discard/regenerate machine-owned latest artifacts; no stack rollback is executed by abyss-machine",
        },
        "evidence_refs": evidence_refs,
        "policy": {
            "automatic_execution": False,
            "requires_owner_gate": True,
            "abyss_machine_writes_stack": False,
            "raw_secret_storage": False,
        },
    }


def stack_requirement_runbook_complete(
    candidate: dict[str, Any],
    requirement_id: str,
    *,
    config: SelfAwarenessRequirementConfig,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    if not isinstance(candidate, dict):
        return False
    return (
        candidate.get("schema")
        == f"{SCHEMA_PREFIX}_stack_requirement_runbook_candidate_v1"
        and candidate.get("requirement_id") == requirement_id
        and (candidate.get("owner_route") == "abyss-stack")
        and (candidate.get("machine_action") == "handoff_only")
        and (candidate.get("host_layer_mutates_stack") is False)
        and (candidate.get("machine_executes_stack_change") is False)
        and (candidate.get("stack_owner_may_mutate_stack") is True)
        and (candidate.get("operator_approval_required") is True)
        and bool(candidate.get("risk"))
        and bool(candidate.get("blast_radius"))
        and bool(candidate.get("rollback"))
        and bool(candidate.get("acceptance_steps"))
        and bool(candidate.get("acceptance_verifiers"))
        and bool(candidate.get("evidence_refs"))
    )


def stack_handoff_closure_readiness(
    *,
    requirement_id: str,
    status: str,
    probe_kind: Any,
    checks: list[dict[str, Any]],
    acceptance_verifiers: list[Any],
    closure_semantics: dict[str, Any],
    machine_closure_probe: dict[str, Any],
    current_state: dict[str, Any],
    runbook_candidate: dict[str, Any],
    evidence_refs: list[dict[str, Any]],
    config: SelfAwarenessRequirementConfig,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    check_rows = [check for check in checks if isinstance(check, dict)]
    fulfilled = [
        {
            "key": check.get("key"),
            "message": check.get("message"),
            "evidence_hint": check.get("data"),
        }
        for check in check_rows
        if check.get("ok") is True and str(check.get("level") or "ok").lower() == "ok"
    ]
    missing = [
        {
            "key": check.get("key"),
            "level": check.get("level"),
            "message": check.get("message"),
            "evidence_hint": check.get("data"),
        }
        for check in check_rows
        if check.get("ok") is not True
        or str(check.get("level") or "").lower() in {"open", "warn", "fail"}
    ]
    readiness_total = max(1, len(fulfilled) + len(missing))
    readiness_score = round(len(fulfilled) / readiness_total, 2)
    verifier_commands = [
        str(item.get("command"))
        for item in acceptance_verifiers
        if isinstance(item, dict) and item.get("command")
    ]
    dependency_requirement_ids: list[str] = []
    dependency_reasons: list[str] = []
    missing_keys = {str(item.get("key")) for item in missing if item.get("key")}
    if (
        requirement_id == "stack.langchain-api.graph-observability"
        and "langchain_trace_backend_coupled" in missing_keys
    ):
        dependency_requirement_ids.append("stack.trace-backend")
        dependency_reasons.append(
            "LangGraph trace/checkpoint replay needs the trace backend coupling first."
        )
    if requirement_id == "stack.trace-backend":
        dependency_reasons.append(
            "Trace backend unlocks span/log/metric joins and also unblocks LangGraph trace coupling."
        )
    required_fields = (
        machine_closure_probe.get("required_fields")
        if isinstance(machine_closure_probe.get("required_fields"), list)
        else []
    )
    success_predicates = (
        machine_closure_probe.get("success_predicates")
        if isinstance(machine_closure_probe.get("success_predicates"), list)
        else []
    )
    redaction_rules = (
        machine_closure_probe.get("redaction_rules")
        if isinstance(machine_closure_probe.get("redaction_rules"), list)
        else []
    )
    boundedness = (
        machine_closure_probe.get("boundedness")
        if isinstance(machine_closure_probe.get("boundedness"), dict)
        else {}
    )
    closure_evidence_needed = [
        {
            "kind": "missing_check",
            "key": item.get("key"),
            "message": item.get("message"),
            "expected_evidence": item.get("evidence_hint"),
        }
        for item in missing
        if item.get("key")
        not in {
            "acceptance_contract_probeable",
            "host_layer_non_mutating",
            "no_secret_leakage",
            "runbook_candidate_complete",
        }
    ]
    safe_next_command = (
        "abyss-machine self-awareness export --json"
        if status != "closed"
        else "abyss-machine self-awareness validate --json"
    )
    return {
        "schema": f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1",
        "requirement_id": requirement_id,
        "status": status,
        "probe_kind": probe_kind,
        "readiness_score": readiness_score,
        "fulfilled_checks": fulfilled,
        "missing_checks": missing,
        "blocking_check_keys": [
            str(item.get("key")) for item in missing if item.get("key")
        ],
        "open_blocker_count": len(missing),
        "fulfilled_check_count": len(fulfilled),
        "dependency_requirement_ids": dependency_requirement_ids,
        "dependency_reasons": dependency_reasons,
        "closure_evidence_needed": closure_evidence_needed,
        "required_fields": required_fields,
        "success_predicates": success_predicates,
        "redaction_rules": redaction_rules,
        "boundedness": boundedness,
        "verifier_commands": verifier_commands,
        "runbook_candidate_id": runbook_candidate.get("id"),
        "safe_next_action": {
            "kind": "stack_owner_closure_readiness_review"
            if status != "closed"
            else "machine_verifier_confirmation",
            "owner_route": "abyss-stack"
            if status != "closed"
            else "abyss-machine:self-awareness",
            "command": safe_next_command,
            "requirement_probe_command": "abyss-machine self-awareness requirement-probes --json",
            "automatic": False,
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "action_execution": False,
        },
        "current_state_digest": {
            "keys": sorted((str(key) for key in current_state.keys()))[:80],
            "has_current_state": bool(current_state),
            "evidence_refs": len(evidence_refs),
        },
        "evidence_refs": evidence_refs[:24],
        "policy": {
            "handoff_only": status != "closed",
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "closure_requires_probe_success": True,
            "no_partial_credit": closure_semantics.get("no_partial_credit") is True,
            "raw_secrets_included": False,
        },
    }


def requirement_probe_evaluate(
    handoff: dict[str, Any],
    capabilities: dict[str, Any],
    requirement: dict[str, Any] | None = None,
    *,
    config: SelfAwarenessRequirementConfig,
    runtime_port: SelfAwarenessRequirementRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    self_awareness_external_closure_row = external_closure_row
    self_awareness_requirement_acceptance_contract = partial(
        requirement_acceptance_contract, config=config
    )
    self_awareness_stack_handoff_closure_readiness = partial(
        stack_handoff_closure_readiness, config=config
    )
    self_awareness_stack_requirement_runbook_candidate = partial(
        stack_requirement_runbook_candidate, config=config
    )
    self_awareness_stack_requirement_runbook_complete = partial(
        stack_requirement_runbook_complete, config=config
    )
    requirement = requirement if isinstance(requirement, dict) else {}
    requirement_id = str(
        handoff.get("requirement_id")
        or handoff.get("id")
        or requirement.get("id")
        or ""
    )
    contract_source = dict(handoff)
    contract_source.update(requirement)
    contract_source["id"] = requirement_id
    contract_source["requirement_id"] = requirement_id
    contract_source["owner"] = contract_source.get("owner") or "abyss-stack"
    contract_source["status"] = contract_source.get("status") or "open"
    contract = self_awareness_requirement_acceptance_contract(contract_source)
    probe_plan = (
        contract.get("probe_plan")
        if isinstance(contract.get("probe_plan"), dict)
        else {}
    )
    raw = capabilities.get("raw") if isinstance(capabilities.get("raw"), dict) else {}
    capability_items = (
        capabilities.get("capabilities")
        if isinstance(capabilities.get("capabilities"), list)
        else []
    )
    cap_by_id = {
        str(item.get("id")): item
        for item in capability_items
        if isinstance(item, dict) and item.get("id")
    }
    checks: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, Any]] = []

    def add_check(
        key: str,
        ok: bool,
        message: str,
        data: dict[str, Any] | None = None,
        *,
        open_check: bool = False,
    ) -> None:
        checks.append(
            {
                "key": key,
                "ok": bool(ok),
                "level": "ok" if ok else "open" if open_check else "fail",
                "message": message,
                "data": data or {},
            }
        )

    def add_ref(ref: dict[str, Any] | None) -> None:
        if isinstance(ref, dict) and ref:
            evidence_refs.append(ref)

    for ref in (
        requirement.get("evidence_refs", [])
        if isinstance(requirement.get("evidence_refs"), list)
        else []
    ):
        add_ref(ref)
    for ref in (
        handoff.get("evidence_refs", [])
        if isinstance(handoff.get("evidence_refs"), list)
        else []
    ):
        add_ref(ref)
    contract_ok = (
        contract.get("schema")
        == f"{SCHEMA_PREFIX}_stack_requirement_acceptance_contract_v1"
        and contract.get("requirement_id") == requirement_id
        and isinstance(probe_plan.get("required_fields"), list)
        and bool(probe_plan.get("required_fields"))
        and isinstance(probe_plan.get("success_predicates"), list)
        and bool(probe_plan.get("success_predicates"))
        and (
            nested_get(contract, ["closure_semantics", "host_layer_mutates_stack"])
            is False
        )
    )
    add_check(
        "acceptance_contract_probeable",
        contract_ok,
        "acceptance contract has schema, identity, required fields, success predicates, and non-mutating closure semantics",
        {
            "contract_schema": contract.get("schema"),
            "requirement_id": requirement_id,
            "required_fields": probe_plan.get("required_fields")
            if isinstance(probe_plan.get("required_fields"), list)
            else [],
            "success_predicates": len(
                probe_plan.get("success_predicates")
                if isinstance(probe_plan.get("success_predicates"), list)
                else []
            ),
        },
    )
    mutating_route = (
        handoff.get("host_layer_mutates_stack") is not False
        or nested_get(contract, ["closure_semantics", "host_layer_mutates_stack"])
        is not False
    )
    add_check(
        "host_layer_non_mutating",
        not mutating_route,
        "machine probe remains read-only and does not mutate abyss-stack",
        {"host_layer_mutates_stack": bool(mutating_route)},
    )
    current_state: dict[str, Any] = {
        "requirement_status": requirement.get("status") or handoff.get("status")
    }
    external_row = self_awareness_external_closure_row(raw, requirement_id)
    external_accepted = external_row.get("accepted") is True
    external_checks = (
        external_row.get("checks")
        if external_accepted and isinstance(external_row.get("checks"), dict)
        else {}
    )
    external_state = (
        external_row.get("current_state")
        if external_accepted and isinstance(external_row.get("current_state"), dict)
        else {}
    )
    if external_row:
        current_state.update(
            {
                "external_closure_evidence_present": True,
                "external_closure_evidence_accepted": external_accepted,
                "external_closure_evidence_rejection_reasons": external_row.get(
                    "rejection_reasons"
                )
                if isinstance(external_row.get("rejection_reasons"), list)
                else [],
                "external_closure_evidence_config_path": nested_get(
                    external_row, ["source", "config_path"]
                ),
            }
        )
        for ref in (
            external_row.get("evidence_refs", [])
            if isinstance(external_row.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
    closure_predicate = False
    if requirement_id == "stack.grafana.datasource-read":
        grafana_probe = (
            raw.get("grafana_datasource_inventory")
            if isinstance(raw.get("grafana_datasource_inventory"), dict)
            else {}
        )
        grafana_raw = (
            raw.get("grafana_datasources")
            if isinstance(raw.get("grafana_datasources"), dict)
            else {}
        )
        grafana_cap = cap_by_id.get("grafana.health", {})
        detail = (
            grafana_cap.get("detail")
            if isinstance(grafana_cap.get("detail"), dict)
            else {}
        )
        if not grafana_probe and isinstance(detail.get("datasource_probe"), dict):
            grafana_probe = detail.get("datasource_probe")
        health = (
            grafana_probe.get("health")
            if isinstance(grafana_probe.get("health"), dict)
            else {}
        )
        api_access = (
            grafana_probe.get("api_access")
            if isinstance(grafana_probe.get("api_access"), dict)
            else {}
        )
        inventory = (
            grafana_probe.get("datasource_inventory")
            if isinstance(grafana_probe.get("datasource_inventory"), dict)
            else {}
        )
        handoff = (
            grafana_probe.get("handoff")
            if isinstance(grafana_probe.get("handoff"), dict)
            else {}
        )
        candidates = (
            grafana_probe.get("inferred_datasource_candidates")
            if isinstance(grafana_probe.get("inferred_datasource_candidates"), list)
            else []
        )
        if not grafana_raw and isinstance(api_access.get("routes"), dict):
            grafana_raw = (
                api_access["routes"].get("datasources")
                if isinstance(api_access["routes"].get("datasources"), dict)
                else {}
            )
        current_state.update(
            {
                "health_ok": health.get("ok"),
                "health_status_code": health.get("status_code"),
                "grafana_version": health.get("version"),
                "grafana_database": health.get("database"),
                "route": grafana_raw.get("url"),
                "ok": grafana_raw.get("ok"),
                "status_code": grafana_raw.get("status_code"),
                "error": grafana_raw.get("error"),
                "denied_routes": api_access.get("denied_routes")
                if isinstance(api_access.get("denied_routes"), list)
                else [],
                "readable_routes": api_access.get("readable_routes")
                if isinstance(api_access.get("readable_routes"), list)
                else [],
                "datasource_api_auth_denied": api_access.get(
                    "datasource_api_auth_denied"
                ),
                "all_inventory_routes_denied": api_access.get(
                    "all_inventory_routes_denied"
                ),
                "datasource_inventory_present": inventory.get("present"),
                "datasource_inventory_count": inventory.get("count"),
                "inferred_datasource_candidate_count": len(candidates),
                "inferred_datasource_candidate_types": sorted(
                    (
                        str(item.get("type"))
                        for item in candidates
                        if isinstance(item, dict) and item.get("type")
                    )
                ),
                "inferred_candidates_are_not_inventory": handoff.get(
                    "inferred_candidates_are_not_inventory"
                ),
                "stack_owned_inventory_required": handoff.get(
                    "stack_owned_inventory_required"
                ),
            }
        )
        if external_accepted:
            external_inventory_readable = bool(
                external_checks.get("grafana_datasource_inventory_readable")
                or external_checks.get("datasource_inventory_readable")
                or external_state.get("datasource_inventory_present")
            )
            current_state.update(
                {
                    "external_datasource_inventory_readable": external_inventory_readable,
                    "datasource_inventory_present": bool(
                        current_state.get("datasource_inventory_present")
                        or external_inventory_readable
                    ),
                    "datasource_inventory_count": safe_int(
                        external_state.get("datasource_inventory_count"),
                        safe_int(current_state.get("datasource_inventory_count"), 0),
                    ),
                    "stack_owned_inventory_required": False
                    if external_inventory_readable
                    else current_state.get("stack_owned_inventory_required"),
                }
            )
        for ref in (
            grafana_probe.get("evidence_refs", [])
            if isinstance(grafana_probe.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        if not grafana_probe:
            add_ref(
                {
                    "url": grafana_raw.get("url"),
                    "status_code": grafana_raw.get("status_code"),
                    "probe": "grafana_datasource_inventory",
                }
            )
        closure_predicate = bool(
            current_state.get("datasource_inventory_present")
            and safe_int(current_state.get("datasource_inventory_count"), 0) > 0
        )
        add_check(
            "grafana_health_readable",
            bool(current_state.get("health_ok")),
            "Grafana health endpoint is readable as liveness evidence",
            {
                "status_code": current_state.get("health_status_code"),
                "version": current_state.get("grafana_version"),
                "database": current_state.get("grafana_database"),
            },
        )
        add_check(
            "grafana_datasource_candidates_inferred",
            bool(candidates),
            "Prometheus/Loki/Alertmanager/Tempo datasource candidates are inferred from live stack evidence but do not close inventory",
            {
                "candidate_count": current_state.get(
                    "inferred_datasource_candidate_count"
                ),
                "candidate_types": current_state.get(
                    "inferred_datasource_candidate_types"
                ),
                "inferred_candidates_are_not_inventory": current_state.get(
                    "inferred_candidates_are_not_inventory"
                ),
            },
        )
        add_check(
            "grafana_datasource_api_auth_denied",
            bool(current_state.get("datasource_api_auth_denied")),
            "Grafana datasource inventory route is auth-denied from the host layer",
            {
                "status_code": grafana_raw.get("status_code"),
                "url": grafana_raw.get("url"),
                "denied_routes": current_state.get("denied_routes"),
            },
            open_check=bool(current_state.get("datasource_api_auth_denied")),
        )
        add_check(
            "grafana_datasource_inventory_readable",
            closure_predicate,
            "Grafana datasource inventory is readable through a stack-owned bounded route",
            {
                "status_code": grafana_raw.get("status_code"),
                "url": grafana_raw.get("url"),
                "inventory_count": current_state.get("datasource_inventory_count"),
            },
            open_check=True,
        )
    elif requirement_id == "stack.trace-backend":
        trace_raw = (
            raw.get("trace_backend")
            if isinstance(raw.get("trace_backend"), dict)
            else {}
        )
        tempo_raw = (
            raw.get("tempo_ready") if isinstance(raw.get("tempo_ready"), dict) else {}
        )
        trace_backend_raw = (
            raw.get("trace_backend")
            if isinstance(raw.get("trace_backend"), dict)
            else {}
        )
        backend = (
            trace_raw.get("backend")
            if isinstance(trace_raw.get("backend"), dict)
            else {}
        )
        pipeline = (
            trace_raw.get("pipeline_evidence")
            if isinstance(trace_raw.get("pipeline_evidence"), dict)
            else {}
        )
        trace_context = (
            trace_raw.get("trace_context")
            if isinstance(trace_raw.get("trace_context"), dict)
            else {}
        )
        join = (
            trace_raw.get("join_readiness")
            if isinstance(trace_raw.get("join_readiness"), dict)
            else {}
        )
        ready = backend.get("ready") if isinstance(backend.get("ready"), dict) else {}
        search = (
            backend.get("search") if isinstance(backend.get("search"), dict) else {}
        )
        if not ready:
            ready = tempo_raw
        current_state.update(
            {
                "route": ready.get("url"),
                "ok": ready.get("ok"),
                "status_code": ready.get("status_code"),
                "error": ready.get("error"),
                "search_route": search.get("url"),
                "search_ok": search.get("ok"),
                "search_status_code": search.get("status_code"),
                "search_error": search.get("error"),
                "alloy_seen": pipeline.get("alloy_seen"),
                "alloy_prometheus_value": pipeline.get("alloy_prometheus_value"),
                "loki_ready": pipeline.get("loki_ready"),
                "loki_labels_readable": pipeline.get("loki_labels_readable"),
                "logql_entries_seen": pipeline.get("logql_entries_seen"),
                "metrics_log_pipeline_readable": pipeline.get(
                    "metrics_log_pipeline_readable"
                ),
                "traceparent_log_query_ok": trace_context.get(
                    "traceparent_log_query_ok"
                ),
                "traceparent_log_entries_seen": trace_context.get(
                    "traceparent_log_entries_seen"
                ),
                "trace_context_query_safe_empty": trace_context.get(
                    "trace_context_query_safe_empty"
                ),
                "trace_backend_ready": join.get("trace_backend_ready")
                if "trace_backend_ready" in join
                else ready.get("ok"),
                "trace_search_readable": join.get("trace_search_readable")
                if "trace_search_readable" in join
                else search.get("ok"),
                "span_log_metric_join_supported": join.get(
                    "span_log_metric_join_supported"
                ),
                "join_missing": join.get("missing")
                if isinstance(join.get("missing"), list)
                else [],
            }
        )
        if external_accepted:
            current_state.update(
                {
                    "external_trace_backend_evidence_accepted": True,
                    "trace_backend_ready": bool(
                        current_state.get("trace_backend_ready")
                        or external_checks.get("trace_backend_ready")
                        or external_state.get("trace_backend_ready")
                    ),
                    "trace_search_readable": bool(
                        current_state.get("trace_search_readable")
                        or external_checks.get("trace_span_search_readable")
                        or external_checks.get("trace_search_readable")
                        or external_state.get("trace_search_readable")
                    ),
                    "span_log_metric_join_supported": bool(
                        current_state.get("span_log_metric_join_supported")
                        or external_checks.get("span_log_metric_join_supported")
                        or external_state.get("span_log_metric_join_supported")
                    ),
                }
            )
            current_state["join_missing"] = [
                label
                for label in (
                    "trace_backend_ready",
                    "trace_search_readable",
                    "span_log_metric_join_supported",
                )
                if not current_state.get(label)
            ]
        for ref in (
            trace_raw.get("evidence_refs", [])
            if isinstance(trace_raw.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        if not trace_raw:
            add_ref(
                {
                    "url": tempo_raw.get("url"),
                    "status_code": tempo_raw.get("status_code"),
                    "probe": "trace_backend_ready",
                }
            )
        closure_predicate = bool(
            current_state.get("trace_backend_ready")
            and current_state.get("trace_search_readable")
            and current_state.get("span_log_metric_join_supported")
        )
        add_check(
            "trace_pipeline_evidence_readable",
            bool(current_state.get("metrics_log_pipeline_readable")),
            "Prometheus/Alloy/Loki metric-log pipeline evidence is readable",
            {
                "alloy_seen": current_state.get("alloy_seen"),
                "loki_ready": current_state.get("loki_ready"),
                "loki_labels_readable": current_state.get("loki_labels_readable"),
                "logql_entries_seen": current_state.get("logql_entries_seen"),
            },
            open_check=not bool(current_state.get("metrics_log_pipeline_readable")),
        )
        add_check(
            "traceparent_log_context_queryable",
            bool(current_state.get("traceparent_log_query_ok")),
            "W3C traceparent can be queried in logs through a bounded LogQL route",
            {
                "traceparent_log_entries_seen": current_state.get(
                    "traceparent_log_entries_seen"
                ),
                "trace_context_query_safe_empty": current_state.get(
                    "trace_context_query_safe_empty"
                ),
            },
            open_check=not bool(current_state.get("traceparent_log_query_ok")),
        )
        add_check(
            "trace_backend_ready",
            bool(current_state.get("trace_backend_ready")),
            "Trace backend ready endpoint is readable",
            {
                "status_code": ready.get("status_code"),
                "url": ready.get("url"),
                "error": ready.get("error"),
            },
            open_check=True,
        )
        add_check(
            "trace_span_search_readable",
            bool(current_state.get("trace_search_readable")),
            "Trace backend search/export route is readable for bounded span lookup",
            {
                "status_code": search.get("status_code"),
                "url": search.get("url"),
                "error": search.get("error"),
            },
            open_check=True,
        )
        add_check(
            "span_log_metric_join_supported",
            closure_predicate,
            "Trace backend can support span/log/metric joins for self-awareness replay",
            {
                "trace_backend_ready": current_state.get("trace_backend_ready"),
                "trace_search_readable": current_state.get("trace_search_readable"),
                "traceparent_log_query_ok": current_state.get(
                    "traceparent_log_query_ok"
                ),
                "join_missing": current_state.get("join_missing"),
            },
            open_check=True,
        )
    elif requirement_id == "stack.database-graph.read-route":
        active_services = cap_by_id.get("stack.active.services", {})
        detail = (
            active_services.get("detail")
            if isinstance(active_services.get("detail"), dict)
            else {}
        )
        memory_routes = (
            raw.get("memory_space_routes")
            if isinstance(raw.get("memory_space_routes"), dict)
            else {}
        )
        memory_cap = cap_by_id.get("stack.memory-space.live-routes", {})
        memory_detail = (
            memory_cap.get("detail")
            if isinstance(memory_cap.get("detail"), dict)
            else {}
        )
        if not memory_routes:
            memory_routes = memory_detail
        route_api = (
            memory_routes.get("route_api")
            if isinstance(memory_routes.get("route_api"), dict)
            else {}
        )
        rag_api = (
            memory_routes.get("rag_api")
            if isinstance(memory_routes.get("rag_api"), dict)
            else {}
        )
        postgres = (
            memory_routes.get("postgres")
            if isinstance(memory_routes.get("postgres"), dict)
            else {}
        )
        neo4j = (
            memory_routes.get("neo4j")
            if isinstance(memory_routes.get("neo4j"), dict)
            else {}
        )
        semantic_inventory = (
            memory_routes.get("semantic_inventory")
            if isinstance(memory_routes.get("semantic_inventory"), dict)
            else {}
        )
        route_openapi = (
            route_api.get("openapi")
            if isinstance(route_api.get("openapi"), dict)
            else {}
        )
        route_health = (
            route_api.get("health") if isinstance(route_api.get("health"), dict) else {}
        )
        rag_openapi = (
            rag_api.get("openapi") if isinstance(rag_api.get("openapi"), dict) else {}
        )
        rag_health = (
            rag_api.get("health") if isinstance(rag_api.get("health"), dict) else {}
        )
        rag_collections = (
            rag_api.get("collections")
            if isinstance(rag_api.get("collections"), dict)
            else {}
        )
        rag_sources = (
            rag_api.get("sources") if isinstance(rag_api.get("sources"), dict) else {}
        )
        rag_graph = (
            rag_api.get("agentic_graph")
            if isinstance(rag_api.get("agentic_graph"), dict)
            else {}
        )
        neo4j_root = neo4j.get("root") if isinstance(neo4j.get("root"), dict) else {}
        route_readable = bool(route_health.get("ok") and route_openapi.get("ok"))
        rag_readable = bool(
            rag_health.get("ok")
            and rag_openapi.get("ok")
            and rag_collections.get("ok")
            and rag_sources.get("ok")
        )
        db_endpoint_readable = bool(postgres.get("tcp_ready") and neo4j_root.get("ok"))
        closure_predicate = bool(semantic_inventory.get("inventory_complete"))
        current_state.update(
            {
                "postgres_seen": detail.get("postgres_seen"),
                "neo4j_seen": detail.get("neo4j_seen"),
                "route_api_health_ok": route_health.get("ok"),
                "route_api_openapi_ok": route_openapi.get("ok"),
                "route_api_openapi_path_count": route_openapi.get("path_count"),
                "route_api_openapi_paths": route_openapi.get("paths", [])[:40]
                if isinstance(route_openapi.get("paths"), list)
                else [],
                "rag_api_health_ok": rag_health.get("ok"),
                "rag_api_openapi_ok": rag_openapi.get("ok"),
                "rag_api_openapi_path_count": rag_openapi.get("path_count"),
                "rag_api_openapi_paths": rag_openapi.get("paths", [])[:40]
                if isinstance(rag_openapi.get("paths"), list)
                else [],
                "rag_collection_names": rag_collections.get("collection_names", []),
                "rag_source_count": rag_sources.get("source_count"),
                "rag_agentic_graph_node_count": rag_graph.get("node_count"),
                "rag_agentic_graph_edge_count": rag_graph.get("edge_count"),
                "postgres_tcp_ready": postgres.get("tcp_ready"),
                "postgres_schema_inventory_present": postgres.get(
                    "schema_inventory_present"
                ),
                "neo4j_root_readable": neo4j_root.get("ok"),
                "neo4j_version": neo4j_root.get("neo4j_version"),
                "neo4j_query_endpoint_present": neo4j_root.get(
                    "query_endpoint_present"
                ),
                "neo4j_graph_inventory_present": neo4j.get("graph_inventory_present"),
                "stack_owned_postgres_schema_inventory_present": semantic_inventory.get(
                    "stack_owned_postgres_schema_inventory_present"
                ),
                "stack_owned_neo4j_graph_inventory_present": semantic_inventory.get(
                    "stack_owned_neo4j_graph_inventory_present"
                ),
                "stack_owned_inventory_route_present": closure_predicate,
                "container_names": detail.get("container_names", []),
            }
        )
        if external_accepted:
            external_inventory_complete = bool(
                external_checks.get("database_graph_inventory_route_present")
                or external_checks.get("inventory_complete")
                or external_state.get("inventory_complete")
            )
            current_state.update(
                {
                    "external_database_graph_inventory_accepted": True,
                    "postgres_schema_inventory_present": bool(
                        current_state.get("postgres_schema_inventory_present")
                        or external_state.get("postgres_schema_inventory_present")
                    ),
                    "neo4j_graph_inventory_present": bool(
                        current_state.get("neo4j_graph_inventory_present")
                        or external_state.get("neo4j_graph_inventory_present")
                    ),
                    "stack_owned_postgres_schema_inventory_present": bool(
                        current_state.get(
                            "stack_owned_postgres_schema_inventory_present"
                        )
                        or external_state.get("postgres_schema_inventory_present")
                        or external_state.get(
                            "stack_owned_postgres_schema_inventory_present"
                        )
                    ),
                    "stack_owned_neo4j_graph_inventory_present": bool(
                        current_state.get("stack_owned_neo4j_graph_inventory_present")
                        or external_state.get("neo4j_graph_inventory_present")
                        or external_state.get(
                            "stack_owned_neo4j_graph_inventory_present"
                        )
                    ),
                    "stack_owned_inventory_route_present": bool(
                        current_state.get("stack_owned_inventory_route_present")
                        or external_inventory_complete
                    ),
                }
            )
            closure_predicate = bool(closure_predicate or external_inventory_complete)
        for ref in (
            active_services.get("evidence_refs", [])
            if isinstance(active_services.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        for ref in (
            memory_routes.get("evidence_refs", [])
            if isinstance(memory_routes.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        for ref in (
            memory_cap.get("evidence_refs", [])
            if isinstance(memory_cap.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        add_check(
            "route_api_health_openapi_readable",
            route_readable,
            "route-api health and bounded OpenAPI are readable as stack route/federation context",
            {
                "health_ok": route_health.get("ok"),
                "openapi_ok": route_openapi.get("ok"),
                "path_count": route_openapi.get("path_count"),
            },
            open_check=not route_readable,
        )
        add_check(
            "rag_api_inventory_routes_readable",
            rag_readable,
            "rag-api health, bounded OpenAPI, collections, and sources are readable without raw source documents",
            {
                "health_ok": rag_health.get("ok"),
                "openapi_ok": rag_openapi.get("ok"),
                "collection_count": rag_collections.get("collection_count"),
                "source_count": rag_sources.get("source_count"),
                "graph_route_ok": rag_graph.get("ok"),
            },
            open_check=not rag_readable,
        )
        add_check(
            "database_endpoint_metadata_readable",
            db_endpoint_readable,
            "Postgres service readiness and Neo4j root metadata are readable without database credentials",
            {
                "postgres_tcp_ready": postgres.get("tcp_ready"),
                "neo4j_root_readable": neo4j_root.get("ok"),
                "neo4j_version": neo4j_root.get("neo4j_version"),
            },
            open_check=not db_endpoint_readable,
        )
        add_check(
            "database_graph_inventory_route_present",
            closure_predicate,
            "Stack-owned bounded Postgres schema/freshness and Neo4j label/relationship/freshness inventory is readable",
            {
                "postgres_schema_inventory_present": current_state.get(
                    "stack_owned_postgres_schema_inventory_present"
                ),
                "neo4j_graph_inventory_present": current_state.get(
                    "stack_owned_neo4j_graph_inventory_present"
                ),
                "inventory_complete": current_state.get(
                    "stack_owned_inventory_route_present"
                ),
            },
            open_check=True,
        )
    elif requirement_id == "stack.langchain-api.graph-observability":
        langchain_raw = (
            raw.get("langchain_api")
            if isinstance(raw.get("langchain_api"), dict)
            else {}
        )
        langchain_cap = cap_by_id.get("stack.langchain-api.health-openapi", {})
        detail = (
            langchain_cap.get("detail")
            if isinstance(langchain_cap.get("detail"), dict)
            else {}
        )
        observability = (
            langchain_raw.get("observability")
            if isinstance(langchain_raw.get("observability"), dict)
            else {}
        )
        if not observability and isinstance(detail.get("observability"), dict):
            observability = detail.get("observability")
        openapi = (
            langchain_raw.get("openapi")
            if isinstance(langchain_raw.get("openapi"), dict)
            else {}
        )
        if not openapi and isinstance(detail.get("openapi"), dict):
            openapi = detail.get("openapi")
        health = (
            langchain_raw.get("health")
            if isinstance(langchain_raw.get("health"), dict)
            else {}
        )
        if not health and isinstance(detail.get("health"), dict):
            health = detail.get("health")
        runtime_surface = (
            langchain_raw.get("runtime_surface")
            if isinstance(langchain_raw.get("runtime_surface"), dict)
            else {}
        )
        if not runtime_surface and isinstance(detail.get("runtime_surface"), dict):
            runtime_surface = detail.get("runtime_surface")
        route_classes = (
            langchain_raw.get("route_classes")
            if isinstance(langchain_raw.get("route_classes"), dict)
            else {}
        )
        if not route_classes and isinstance(detail.get("route_classes"), dict):
            route_classes = detail.get("route_classes")
        replay_inventory = (
            langchain_raw.get("replay_inventory")
            if isinstance(langchain_raw.get("replay_inventory"), dict)
            else {}
        )
        if not replay_inventory and isinstance(detail.get("replay_inventory"), dict):
            replay_inventory = detail.get("replay_inventory")
        trace_coupling = (
            langchain_raw.get("trace_backend_coupling")
            if isinstance(langchain_raw.get("trace_backend_coupling"), dict)
            else {}
        )
        if not trace_coupling and isinstance(
            detail.get("trace_backend_coupling"), dict
        ):
            trace_coupling = detail.get("trace_backend_coupling")
        tempo_raw = (
            raw.get("tempo_ready") if isinstance(raw.get("tempo_ready"), dict) else {}
        )
        trace_backend_raw = (
            raw.get("trace_backend")
            if isinstance(raw.get("trace_backend"), dict)
            else {}
        )
        path_rows = (
            openapi.get("paths") if isinstance(openapi.get("paths"), list) else []
        )
        run_paths = (
            route_classes.get("run_paths")
            if isinstance(route_classes.get("run_paths"), list)
            else []
        )
        federated_run_paths = (
            route_classes.get("federated_run_paths")
            if isinstance(route_classes.get("federated_run_paths"), list)
            else []
        )
        embeddings_paths = (
            route_classes.get("embeddings_paths")
            if isinstance(route_classes.get("embeddings_paths"), list)
            else []
        )
        thread_paths = (
            route_classes.get("thread_paths")
            if isinstance(route_classes.get("thread_paths"), list)
            else []
        )
        checkpoint_paths = (
            route_classes.get("checkpoint_paths")
            if isinstance(route_classes.get("checkpoint_paths"), list)
            else []
        )
        trace_paths = (
            route_classes.get("trace_paths")
            if isinstance(route_classes.get("trace_paths"), list)
            else []
        )
        thread_present = bool(
            replay_inventory.get("thread_inventory_present")
            or observability.get("thread_inventory_present")
            or thread_paths
        )
        checkpoint_present = bool(
            replay_inventory.get("checkpoint_inventory_present")
            or observability.get("checkpoint_inventory_present")
            or checkpoint_paths
        )
        trace_present = bool(
            replay_inventory.get("trace_inventory_present")
            or observability.get("trace_inventory_present")
            or trace_paths
        )
        graph_complete = bool(observability.get("graph_observability_complete"))
        runtime_routes_readable = bool(
            runtime_surface.get("run_route_present")
            and runtime_surface.get("embeddings_route_present")
        )
        trace_backend_ready = bool(
            nested_get(trace_backend_raw, ["join_readiness", "trace_backend_ready"])
            if isinstance(trace_backend_raw, dict)
            else tempo_raw.get("ok")
        )
        current_state.update(
            {
                "langchain_api_base_url": langchain_raw.get("base_url")
                or detail.get("base_url"),
                "health_service": health.get("service")
                or runtime_surface.get("service"),
                "embeddings_provider": health.get("embeddings_provider")
                or runtime_surface.get("embeddings_provider"),
                "ovms_auth_enabled": health.get("ovms_auth_enabled")
                if health.get("ovms_auth_enabled") is not None
                else runtime_surface.get("ovms_auth_enabled"),
                "federated_run_enabled": health.get("federated_run_enabled")
                if health.get("federated_run_enabled") is not None
                else runtime_surface.get("federated_run_enabled"),
                "api_health_ok": health.get("ok")
                or observability.get("health_readable"),
                "openapi_ok": openapi.get("ok")
                or observability.get("openapi_readable"),
                "openapi_path_count": openapi.get("path_count"),
                "openapi_paths": path_rows[:32],
                "run_route_present": bool(
                    runtime_surface.get("run_route_present") or run_paths
                ),
                "federated_run_route_present": bool(
                    runtime_surface.get("federated_run_route_present")
                    or federated_run_paths
                ),
                "embeddings_route_present": bool(
                    runtime_surface.get("embeddings_route_present") or embeddings_paths
                ),
                "runtime_request_schema_names": runtime_surface.get(
                    "runtime_request_schema_names"
                )
                or openapi.get("runtime_request_schema_names")
                or [],
                "runtime_surface_usable": bool(
                    runtime_surface.get("usable_runtime_surface")
                    or runtime_routes_readable
                ),
                "thread_inventory_present": thread_present,
                "checkpoint_inventory_present": checkpoint_present,
                "trace_inventory_present": trace_present,
                "missing_replay_inventory": replay_inventory.get("missing_inventory")
                or observability.get("missing_replay_inventory")
                or [],
                "trace_backend_ready": trace_backend_ready,
                "trace_backend_url": nested_get(
                    trace_backend_raw, ["backend", "ready", "url"]
                )
                or tempo_raw.get("url")
                or trace_coupling.get("candidate_ready_url"),
                "trace_backend_status_code": nested_get(
                    trace_backend_raw, ["backend", "ready", "status_code"]
                )
                or tempo_raw.get("status_code"),
                "trace_backend_error": nested_get(
                    trace_backend_raw, ["backend", "ready", "error"]
                )
                or tempo_raw.get("error"),
                "trace_backend_coupling_required": trace_coupling.get(
                    "required_for_trace_join"
                )
                is not False,
                "stack_owned_checkpoint_inventory_present": checkpoint_present,
                "stack_owned_trace_inventory_present": trace_present,
            }
        )
        if external_accepted:
            external_trace_coupled = bool(
                external_checks.get("langchain_trace_backend_coupled")
                or external_state.get("langchain_trace_backend_coupled")
                or external_state.get("trace_backend_ready")
            )
            external_inventory_readable = bool(
                external_checks.get("langchain_langgraph_inventory_readable")
                or external_state.get("langchain_langgraph_inventory_readable")
                or (
                    external_state.get("thread_inventory_present")
                    and external_state.get("checkpoint_inventory_present")
                    and external_state.get("trace_inventory_present")
                )
            )
            thread_present = bool(
                thread_present or external_state.get("thread_inventory_present")
            )
            checkpoint_present = bool(
                checkpoint_present or external_state.get("checkpoint_inventory_present")
            )
            trace_present = bool(
                trace_present or external_state.get("trace_inventory_present")
            )
            trace_backend_ready = bool(trace_backend_ready or external_trace_coupled)
            graph_complete = bool(graph_complete or external_inventory_readable)
            current_state.update(
                {
                    "external_langgraph_inventory_accepted": True,
                    "thread_inventory_present": thread_present,
                    "checkpoint_inventory_present": checkpoint_present,
                    "trace_inventory_present": trace_present,
                    "trace_backend_ready": trace_backend_ready,
                    "stack_owned_checkpoint_inventory_present": checkpoint_present,
                    "stack_owned_trace_inventory_present": trace_present,
                    "missing_replay_inventory": [
                        label
                        for label, present in (
                            ("threads", thread_present),
                            ("checkpoints", checkpoint_present),
                            ("traces", trace_present),
                        )
                        if not present
                    ],
                }
            )
        for ref in (
            langchain_raw.get("evidence_refs", [])
            if isinstance(langchain_raw.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        for ref in (
            langchain_cap.get("evidence_refs", [])
            if isinstance(langchain_cap.get("evidence_refs"), list)
            else []
        ):
            add_ref(ref)
        if current_state.get("trace_backend_url"):
            add_ref(
                {
                    "url": current_state.get("trace_backend_url"),
                    "status_code": current_state.get("trace_backend_status_code"),
                    "error": current_state.get("trace_backend_error"),
                    "probe": "trace_backend_for_langgraph",
                }
            )
        closure_predicate = bool(graph_complete and trace_backend_ready)
        add_check(
            "langchain_api_health_readable",
            bool(health.get("ok") or observability.get("health_readable")),
            "langchain-api health endpoint is readable from the machine",
            {"url": health.get("url"), "status_code": health.get("status_code")},
        )
        add_check(
            "langchain_api_openapi_readable",
            bool(openapi.get("ok") or observability.get("openapi_readable")),
            "langchain-api bounded OpenAPI inventory is readable from the machine",
            {
                "url": openapi.get("url"),
                "status_code": openapi.get("status_code"),
                "path_count": openapi.get("path_count"),
            },
        )
        add_check(
            "langchain_runtime_routes_readable",
            runtime_routes_readable,
            "langchain-api runtime route shape is readable for run and embeddings surfaces",
            {
                "run_route_present": current_state.get("run_route_present"),
                "federated_run_route_present": current_state.get(
                    "federated_run_route_present"
                ),
                "embeddings_route_present": current_state.get(
                    "embeddings_route_present"
                ),
                "runtime_request_schema_names": current_state.get(
                    "runtime_request_schema_names"
                ),
            },
        )
        add_check(
            "langchain_trace_backend_coupled",
            trace_backend_ready,
            "Trace backend readiness is visible for LangGraph span/log/metric joins",
            {
                "trace_backend_url": current_state.get("trace_backend_url"),
                "trace_backend_ready": trace_backend_ready,
                "trace_backend_error": current_state.get("trace_backend_error"),
            },
            open_check=not trace_backend_ready,
        )
        add_check(
            "langchain_langgraph_inventory_readable",
            closure_predicate,
            "Stack-owned LangChain/LangGraph thread/checkpoint/trace inventory is readable",
            {
                "api_health_ok": current_state.get("api_health_ok"),
                "openapi_ok": current_state.get("openapi_ok"),
                "thread_inventory_present": thread_present,
                "checkpoint_inventory_present": checkpoint_present,
                "trace_inventory_present": trace_present,
                "trace_backend_ready": trace_backend_ready,
                "missing_replay_inventory": current_state.get(
                    "missing_replay_inventory"
                ),
            },
            open_check=True,
        )
    else:
        add_check(
            "generic_stack_requirement_probe",
            False,
            "No specialized machine probe exists yet for this requirement id",
            {"requirement_id": requirement_id, "probe_kind": probe_plan.get("kind")},
            open_check=True,
        )
    deduped_refs: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for ref in evidence_refs:
        digest = stable_hash_json(ref, length=20)
        if digest in seen_refs:
            continue
        seen_refs.add(digest)
        deduped_refs.append(ref)
    preview = json.dumps(
        {
            "requirement_id": requirement_id,
            "probe_kind": probe_plan.get("kind"),
            "current_state": current_state,
            "evidence_refs": deduped_refs,
        },
        sort_keys=True,
        default=str,
    )[:50000]
    secret_leak = bool(runtime_port.secret_search(preview))
    add_check(
        "no_secret_leakage",
        not secret_leak,
        "Probe evidence preview does not contain obvious secrets or private payloads",
    )
    runbook_candidate = self_awareness_stack_requirement_runbook_candidate(
        requirement_id, handoff, probe_plan, current_state, deduped_refs
    )
    add_check(
        "runbook_candidate_complete",
        self_awareness_stack_requirement_runbook_complete(
            runbook_candidate, requirement_id
        ),
        "Stack-owned open requirement has an owner-gated runbook candidate with risk, blast radius, rollback, acceptance steps, and evidence refs",
        {"runbook_candidate_id": runbook_candidate.get("id")},
    )
    status = (
        "closed"
        if closure_predicate
        and contract_ok
        and (not secret_leak)
        and (not mutating_route)
        else "open"
    )
    acceptance_verifiers = (
        contract.get("machine_verifiers")
        if isinstance(contract.get("machine_verifiers"), list)
        else []
    )
    closure_semantics = (
        contract.get("closure_semantics")
        if isinstance(contract.get("closure_semantics"), dict)
        else {}
    )
    closure_readiness = self_awareness_stack_handoff_closure_readiness(
        requirement_id=requirement_id,
        status=status,
        probe_kind=probe_plan.get("kind"),
        checks=checks,
        acceptance_verifiers=acceptance_verifiers,
        closure_semantics=closure_semantics,
        machine_closure_probe=probe_plan,
        current_state=current_state,
        runbook_candidate=runbook_candidate,
        evidence_refs=deduped_refs,
    )
    probe_policy = {
        "handoff_only": True,
        "read_only": True,
        "host_layer_mutates_stack": False,
        "writes_project_roots": False,
        "executes_commands": False,
        "action_execution": False,
        "automatic_remediation": False,
        "open_stack_requirements_are_blockers_not_host_failures": True,
        "closure_requires_probe_success": True,
        "raw_secrets_included": False,
        "raw_private_payloads_included": False,
    }
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_probe_v1",
        "id": requirement_id,
        "requirement_id": requirement_id,
        "owner": handoff.get("owner") or requirement.get("owner") or "abyss-stack",
        "status": status,
        "stack_handoff": True,
        "closed_by_current_probe": status == "closed",
        "host_layer_mutates_stack": False,
        "probe_kind": probe_plan.get("kind"),
        "machine_read_command": "abyss-machine self-awareness requirement-probes --json",
        "source_handoff_command": handoff.get("machine_read_command")
        or "abyss-machine self-awareness requirements --json",
        "acceptance_contract": contract,
        "machine_closure_probe": probe_plan,
        "acceptance_verifiers": acceptance_verifiers,
        "closure_semantics": closure_semantics,
        "required_fields": probe_plan.get("required_fields")
        if isinstance(probe_plan.get("required_fields"), list)
        else [],
        "success_predicates": probe_plan.get("success_predicates")
        if isinstance(probe_plan.get("success_predicates"), list)
        else [],
        "redaction_rules": probe_plan.get("redaction_rules")
        if isinstance(probe_plan.get("redaction_rules"), list)
        else [],
        "machine_verifiers": contract.get("machine_verifiers")
        if isinstance(contract.get("machine_verifiers"), list)
        else [],
        "must_not": contract.get("must_not")
        if isinstance(contract.get("must_not"), list)
        else [],
        "current_state": current_state,
        "checks": checks,
        "closure_readiness": closure_readiness,
        "evidence_refs": deduped_refs,
        "runbook_candidate": runbook_candidate,
        "policy": probe_policy,
    }


def stack_requirement_coverage_impact(
    requirement_id: str, *, config: SelfAwarenessRequirementConfig
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    mapping: dict[str, dict[str, Any]] = {
        "stack.trace-backend": {
            "organ": "trace_join_backbone",
            "coverage_planes": [
                "signal_fabric",
                "causal_timeline",
                "spatial_graph",
                "langgraph_replay",
            ],
            "affected_stack_surfaces": [
                "Tempo or compatible trace backend",
                "Alloy/OTel trace pipeline",
                "Loki traceparent log query",
                "Prometheus metric side of joins",
            ],
            "affected_machine_surfaces": [
                "self-awareness correlation",
                "timeline",
                "spatial-graph",
                "investigate",
                "replay",
                "cycle",
            ],
            "blocks_stack_usage_requirements": [
                "span/log/metric correlation",
                "trace-backed replay",
                "LangGraph trace coupling",
            ],
            "closure_value": "turns metric/log evidence into structural span/log/metric joins for replayable self-awareness",
            "proof_commands": [
                "abyss-machine self-awareness requirement-probes --json",
                "abyss-machine self-awareness stack-closure-dossier --json",
                "abyss-machine self-awareness cycle --json",
                "abyss-machine self-awareness validate --json",
            ],
        },
        "stack.langchain-api.graph-observability": {
            "organ": "checkpointed_reasoning_runtime",
            "coverage_planes": [
                "langgraph_loop",
                "resident_worker",
                "investigation_replay",
                "response_governance",
            ],
            "affected_stack_surfaces": [
                "langchain-api",
                "LangGraph thread inventory",
                "checkpoint inventory",
                "trace inventory",
            ],
            "affected_machine_surfaces": [
                "self-awareness investigate",
                "replay",
                "brief",
                "reactions",
                "responses",
            ],
            "blocks_stack_usage_requirements": [
                "checkpointed investigation",
                "resume/replay conclusion diff",
                "thread/checkpoint/trace spatial joins",
            ],
            "closure_value": "makes the reasoning loop inspectable as stack runtime state instead of only machine-side replay state",
            "proof_commands": [
                "abyss-machine self-awareness requirement-probes --json",
                "abyss-machine self-awareness investigate --query latest --json",
                "abyss-machine self-awareness replay --json",
                "abyss-machine self-awareness validate --json",
            ],
        },
        "stack.database-graph.read-route": {
            "organ": "semantic_space_inventory",
            "coverage_planes": [
                "memory_space",
                "spatial_graph",
                "rag_retrieval",
                "freshness_gates",
            ],
            "affected_stack_surfaces": [
                "Postgres",
                "Neo4j",
                "rag-api",
                "route-api semantic inventory",
            ],
            "affected_machine_surfaces": [
                "self-awareness context",
                "spatial-graph",
                "query",
                "rag trace",
                "graph validate",
            ],
            "blocks_stack_usage_requirements": [
                "bounded Postgres schema/freshness inventory",
                "Neo4j labels/relationships/freshness inventory",
                "memory-space proof before reasoning",
            ],
            "closure_value": "lets machine bind retrieved evidence to database and graph space without treating raw rows or private graph properties as truth",
            "proof_commands": [
                "abyss-machine self-awareness requirement-probes --json",
                "abyss-machine self-awareness context --json",
                "abyss-machine rag validate --json",
                "abyss-machine graph validate --json",
                "abyss-machine self-awareness validate --json",
            ],
        },
        "stack.grafana.datasource-read": {
            "organ": "dashboard_source_authority",
            "coverage_planes": [
                "observability_inventory",
                "operator_dashboard_truth",
                "export_handoff",
                "redaction_governance",
            ],
            "affected_stack_surfaces": [
                "Grafana datasources",
                "Prometheus datasource",
                "Loki datasource",
                "Alertmanager datasource",
                "Tempo datasource",
            ],
            "affected_machine_surfaces": [
                "self-awareness capabilities",
                "requirements",
                "export",
                "stack-bridge",
            ],
            "blocks_stack_usage_requirements": [
                "authoritative datasource identity",
                "read-only datasource type/default/freshness inventory",
                "redacted dashboard-source export",
            ],
            "closure_value": "separates inferred datasource candidates from authoritative dashboard-source truth without storing Grafana secrets",
            "proof_commands": [
                "abyss-machine self-awareness capabilities --json",
                "abyss-machine self-awareness requirement-probes --json",
                "abyss-machine self-awareness export --json",
                "abyss-machine stack-bridge validate --json",
            ],
        },
    }
    impact = dict(
        mapping.get(
            requirement_id,
            {
                "organ": "stack_owned_capability",
                "coverage_planes": ["stack_handoff"],
                "affected_stack_surfaces": [],
                "affected_machine_surfaces": [
                    "self-awareness requirements",
                    "requirement-probes",
                    "stack-closure-dossier",
                ],
                "blocks_stack_usage_requirements": ["open stack-owned requirement"],
                "closure_value": "keeps the stack-owned capability visible until owner-routed evidence closes it",
                "proof_commands": [
                    "abyss-machine self-awareness requirement-probes --json",
                    "abyss-machine self-awareness validate --json",
                ],
            },
        )
    )
    impact.update(
        {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_coverage_impact_v1",
            "requirement_id": requirement_id,
            "policy": {
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "raw_secrets_included": False,
            },
        }
    )
    return impact


def stack_coverage_impact_complete(
    impact: Any, *, config: SelfAwarenessRequirementConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    return (
        isinstance(impact, dict)
        and impact.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_stack_coverage_impact_v1"
        and bool(impact.get("organ"))
        and bool(impact.get("closure_value"))
        and isinstance(impact.get("coverage_planes"), list)
        and bool(impact.get("coverage_planes"))
        and isinstance(impact.get("proof_commands"), list)
        and bool(impact.get("proof_commands"))
        and (nested_get(impact, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(impact, ["policy", "executes_commands"]) is False)
        and (nested_get(impact, ["policy", "raw_secrets_included"]) is False)
    )


def stack_requirement_ids_for_doc(requirements_doc: dict[str, Any]) -> set[str]:
    handoff_rows = (
        requirements_doc.get("stack_handoff")
        if isinstance(requirements_doc.get("stack_handoff"), list)
        else []
    )
    ids = {
        str(item.get("id") or item.get("requirement_id"))
        for item in handoff_rows
        if isinstance(item, dict) and (item.get("id") or item.get("requirement_id"))
    }
    if ids:
        return ids
    requirement_rows = (
        requirements_doc.get("requirements")
        if isinstance(requirements_doc.get("requirements"), list)
        else []
    )
    return {
        str(item.get("id"))
        for item in requirement_rows
        if isinstance(item, dict)
        and item.get("owner") == "abyss-stack"
        and item.get("id")
    }


def requirement_probe_ids_for_doc(requirement_probes_doc: dict[str, Any]) -> set[str]:
    probe_rows = (
        requirement_probes_doc.get("probes")
        if isinstance(requirement_probes_doc.get("probes"), list)
        else []
    )
    return {
        str(item.get("requirement_id") or item.get("id"))
        for item in probe_rows
        if isinstance(item, dict) and (item.get("requirement_id") or item.get("id"))
    }


def requirement_probes_cover_requirements(
    requirements_doc: dict[str, Any], requirement_probes_doc: dict[str, Any]
) -> bool:
    self_awareness_requirement_probe_ids_for_doc = requirement_probe_ids_for_doc
    self_awareness_stack_requirement_ids_for_doc = stack_requirement_ids_for_doc
    requirement_ids = self_awareness_stack_requirement_ids_for_doc(requirements_doc)
    probe_ids = self_awareness_requirement_probe_ids_for_doc(requirement_probes_doc)
    if not requirement_ids:
        return not probe_ids
    return requirement_ids == probe_ids


def requirement_probes_export_ready(
    requirements_doc: dict[str, Any],
    requirement_probes_doc: dict[str, Any],
    *,
    config: SelfAwarenessRequirementConfig,
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    self_awareness_requirement_probes_cover_requirements = (
        requirement_probes_cover_requirements
    )
    self_awareness_stack_requirement_ids_for_doc = stack_requirement_ids_for_doc
    self_awareness_stack_requirement_runbook_complete = partial(
        stack_requirement_runbook_complete, config=config
    )
    if (
        requirement_probes_doc.get("schema")
        != f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1"
    ):
        return False
    if not self_awareness_requirement_probes_cover_requirements(
        requirements_doc, requirement_probes_doc
    ):
        return False
    requirement_ids = self_awareness_stack_requirement_ids_for_doc(requirements_doc)
    probe_rows = (
        requirement_probes_doc.get("probes")
        if isinstance(requirement_probes_doc.get("probes"), list)
        else []
    )
    probe_by_id = {
        str(probe.get("requirement_id") or probe.get("id")): probe
        for probe in probe_rows
        if isinstance(probe, dict) and (probe.get("requirement_id") or probe.get("id"))
    }
    for requirement_id in requirement_ids:
        probe = probe_by_id.get(requirement_id)
        if not isinstance(probe, dict):
            return False
        contract = (
            probe.get("acceptance_contract")
            if isinstance(probe.get("acceptance_contract"), dict)
            else {}
        )
        closure_readiness = (
            probe.get("closure_readiness")
            if isinstance(probe.get("closure_readiness"), dict)
            else {}
        )
        acceptance_verifiers = (
            probe.get("acceptance_verifiers")
            if isinstance(probe.get("acceptance_verifiers"), list)
            else []
        )
        runbook_candidate = (
            probe.get("runbook_candidate")
            if isinstance(probe.get("runbook_candidate"), dict)
            else {}
        )
        policy = probe.get("policy") if isinstance(probe.get("policy"), dict) else {}
        if (
            contract.get("schema")
            != f"{SCHEMA_PREFIX}_stack_requirement_acceptance_contract_v1"
        ):
            return False
        if (
            policy.get("read_only") is not True
            or policy.get("host_layer_mutates_stack") is not False
            or policy.get("executes_commands") is not False
            or (policy.get("raw_secrets_included") is not False)
        ):
            return False
        if not acceptance_verifiers:
            return False
        if (
            closure_readiness.get("schema")
            != f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1"
        ):
            return False
        if not closure_readiness.get("verifier_commands"):
            return False
        if not self_awareness_stack_requirement_runbook_complete(
            runbook_candidate, requirement_id
        ):
            return False
    return True
