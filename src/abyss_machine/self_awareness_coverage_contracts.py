from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import runtime_evidence_contracts
from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessCoveragePaths:
    activation_smoke_latest: Path
    alerts_latest: Path
    capabilities_latest: Path
    context_latest: Path
    coverage_audit_latest: Path
    coverage_audit_root: Path
    cycle_latest: Path
    episodes_latest: Path
    events_latest: Path
    export_latest: Path
    failure_matrix_latest: Path
    investigate_latest: Path
    replay_latest: Path
    requirements_latest: Path
    requirement_probes_latest: Path
    spatial_graph_latest: Path
    stack_closure_dossier_latest: Path
    timeline_latest: Path
    validate_latest: Path
    working_stack_latest: Path


@dataclass(frozen=True)
class SelfAwarenessCoverageConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessCoverageRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort
    latest_artifact_ref: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCoverageRefreshPort:
    capabilities: DocumentPort
    requirements: DocumentPort
    requirement_probes: DocumentPort
    working_stack_inventory: DocumentPort
    collect: DocumentPort
    timeline: DocumentPort
    spatial_graph: DocumentPort
    context: DocumentPort
    episodes: DocumentPort
    alerts: DocumentPort
    investigate: DocumentPort
    replay: DocumentPort
    cycle: DocumentPort
    activation_smoke: DocumentPort
    stack_closure_dossier: DocumentPort
    refresh_working_stack_dependent_readmodels: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessCoverageContractPort:
    e2e_lineage_artifact_specs: DocumentPort
    requirement_probes_cover_requirements: DocumentPort
    resident_cognitive_cycle_chain_overlay: DocumentPort
    working_stack_link_integrity_matrix: DocumentPort
    working_stack_activation_dossier: DocumentPort
    activation_synthetic_proof: DocumentPort
    activation_smoke_needs_refresh: DocumentPort
    activation_smoke_compact: DocumentPort
    activation_synthetic_proof_complete: DocumentPort
    dependent_link_readmodels_fresh: DocumentPort
    link_integrity_matches_working_stack: DocumentPort
    working_stack_gap_coverage_planes: DocumentPort
    stack_requirement_closure_acceptance_complete: DocumentPort


def objective_coverage_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "prometheus_promql",
            "objective_area": "inventory",
            "title": "Prometheus/PromQL target and query coverage",
            "owner": "abyss-stack",
            "capabilities": ["prometheus.targets"],
            "artifacts": ["capabilities", "collect", "events"],
            "chain_keys": ["capability_inventory", "signal_fabric"],
        },
        {
            "id": "working_stack_runtime_body",
            "objective_area": "inventory",
            "title": "Actual working stack runtime, declared services, model roots, endpoint probes, and time-space-context links",
            "owner": "abyss-machine",
            "artifacts": [
                "working_stack",
                "collect",
                "events",
                "timeline",
                "spatial_graph",
                "context",
            ],
            "chain_keys": ["working_stack"],
        },
        {
            "id": "loki_logql",
            "objective_area": "signal_fabric",
            "title": "Loki/LogQL bounded logs without high-cardinality labels",
            "owner": "abyss-stack",
            "capabilities": ["loki.logql"],
            "artifacts": ["capabilities", "collect", "events", "query"],
            "chain_keys": ["signal_fabric", "query"],
        },
        {
            "id": "grafana_health",
            "objective_area": "inventory",
            "title": "Grafana health and safe stack UI evidence",
            "owner": "abyss-stack",
            "capabilities": ["grafana.health"],
            "artifacts": ["capabilities", "requirements"],
            "chain_keys": ["capability_inventory"],
        },
        {
            "id": "grafana_datasource_inventory",
            "objective_area": "inventory",
            "title": "Grafana datasource inventory handoff",
            "owner": "abyss-stack",
            "capabilities": ["grafana.health"],
            "requirements": ["stack.grafana.datasource-read"],
            "artifacts": [
                "requirements",
                "requirement_probes",
                "stack_closure_dossier",
            ],
            "chain_keys": ["requirement_probes", "stack_closure_dossier"],
        },
        {
            "id": "alertmanager",
            "objective_area": "signal_fabric",
            "title": "Alertmanager lifecycle and alert evidence",
            "owner": "abyss-stack",
            "capabilities": ["alertmanager.lifecycle"],
            "artifacts": ["capabilities", "collect", "alerts"],
            "chain_keys": ["alert"],
        },
        {
            "id": "alloy_otel",
            "objective_area": "signal_fabric",
            "title": "Alloy/OTel pipeline evidence",
            "owner": "abyss-stack",
            "capabilities": ["alloy.otel.pipeline"],
            "artifacts": ["capabilities", "collect", "events"],
            "chain_keys": ["signal_fabric"],
        },
        {
            "id": "trace_backend",
            "objective_area": "signal_fabric",
            "title": "Trace backend span/log/metric joins",
            "owner": "abyss-stack",
            "capabilities": ["tempo.trace.backend"],
            "requirements": ["stack.trace-backend"],
            "artifacts": [
                "requirements",
                "requirement_probes",
                "stack_closure_dossier",
                "trace_context",
                "replay",
            ],
            "chain_keys": ["stack_handoff_readiness_replay", "trace_context_fallback"],
        },
        {
            "id": "route_rag_api",
            "objective_area": "memory_space",
            "title": "route-api/rag-api bounded memory-space evidence",
            "owner": "abyss-stack",
            "capabilities": ["stack.memory-space.live-routes", "rag.memory.trace-gate"],
            "artifacts": ["capabilities", "query", "context", "collect"],
            "chain_keys": ["query", "rag_memory"],
        },
        {
            "id": "postgres_neo4j_graph",
            "objective_area": "memory_space",
            "title": "Postgres/Neo4j semantic graph inventory handoff",
            "owner": "abyss-stack",
            "capabilities": ["stack.memory-space.live-routes"],
            "requirements": ["stack.database-graph.read-route"],
            "artifacts": [
                "requirements",
                "requirement_probes",
                "stack_closure_dossier",
                "spatial_graph",
            ],
            "chain_keys": ["spatial_graph"],
        },
        {
            "id": "langchain_langgraph_stack",
            "objective_area": "langgraph_loop",
            "title": "langchain-api/LangGraph stack observability handoff",
            "owner": "abyss-stack",
            "capabilities": [
                "stack.langchain-api.health-openapi",
                "langgraph.investigator.runtime",
            ],
            "requirements": ["stack.langchain-api.graph-observability"],
            "artifacts": [
                "requirements",
                "requirement_probes",
                "investigate",
                "replay",
            ],
            "chain_keys": ["langgraph_investigation", "replay"],
        },
        {
            "id": "stack_models_stt_embeddings_tts_npu",
            "objective_area": "inventory",
            "title": "Stack model roots, STT, embeddings, TTS, NPU and model-root evidence",
            "owner": "abyss-machine",
            "capabilities": ["ai.multimodal.capability-map"],
            "artifacts": ["capabilities"],
            "chain_keys": ["capability_inventory"],
        },
        {
            "id": "warm_e2b_resident_worker",
            "objective_area": "warm_e2b_agent",
            "title": "warm-E2B/gemma4 monitored cognitive worker",
            "owner": "abyss-machine",
            "capabilities": ["warm-e2b.resident-cognitive-worker"],
            "artifacts": [
                "capabilities",
                "context",
                "investigate",
                "replay",
                "export",
                "collect",
            ],
            "chain_keys": [
                "warm_e2b_worker",
                "resident_cognitive_replay",
                "resident_cognitive_export",
            ],
        },
        {
            "id": "e4b_qwen_escalation",
            "objective_area": "warm_e2b_agent",
            "title": "On-demand E4B/Qwen routes through resource and mode gates",
            "owner": "abyss-machine",
            "capabilities": ["llm.escalation.routes", "host.governance-gates"],
            "artifacts": ["capabilities", "context"],
            "chain_keys": ["capability_inventory"],
        },
        {
            "id": "machine_bridges",
            "objective_area": "machine_bridges",
            "title": "Heartbeat, memory, mode, nervous, resource, process/thermal, typing, reactions and responses bridges",
            "owner": "abyss-machine",
            "capabilities": [
                "host.governance-gates",
                "nervous.freshness-gate",
                "governed.response-loop",
            ],
            "artifacts": ["cycle", "probe", "reactions", "responses"],
            "chain_keys": ["machine_bridges"],
        },
        {
            "id": "signal_fabric_schema",
            "objective_area": "signal_fabric",
            "title": "Unified event schema with time, space, actor, route, model, trace and redaction",
            "owner": "abyss-machine",
            "artifacts": ["collect", "events", "validate"],
            "chain_keys": ["signal_fabric"],
        },
        {
            "id": "memory_space_freshness",
            "objective_area": "memory_space",
            "title": "Bounded retrieval and freshness gates before reasoning",
            "owner": "abyss-machine",
            "capabilities": ["rag.memory.trace-gate", "nervous.freshness-gate"],
            "artifacts": ["context", "query", "collect"],
            "chain_keys": ["rag_memory", "nervous_freshness"],
        },
        {
            "id": "checkpointed_investigation_replay",
            "objective_area": "langgraph_loop",
            "title": "Checkpointed investigate graph, resume, replay, conclusion diff and failure recovery",
            "owner": "abyss-machine",
            "artifacts": ["investigate", "replay", "cycle"],
            "chain_keys": ["langgraph_investigation", "replay"],
        },
        {
            "id": "response_layer",
            "objective_area": "response_layer",
            "title": "Episodes become reaction candidates, response routes, runbook candidates, risk and rollback notes",
            "owner": "abyss-machine",
            "capabilities": ["governed.response-loop"],
            "artifacts": ["alerts", "reactions", "responses", "brief"],
            "chain_keys": [
                "reaction_candidate",
                "governed_response",
                "body_trace",
                "entity_event_document",
            ],
        },
        {
            "id": "ux_api_commands",
            "objective_area": "ux_api",
            "title": "Self-awareness command/API surface",
            "owner": "abyss-machine",
            "artifacts": [
                "capabilities",
                "collect",
                "context",
                "timeline",
                "spatial_graph",
                "episodes",
                "investigate",
                "brief",
                "probe",
                "replay",
                "validate",
                "export",
            ],
            "chain_keys": ["export"],
        },
        {
            "id": "failure_tests",
            "objective_area": "tests",
            "title": "Failure matrix for stale/missing/down/cardinality/redaction/resource denial cases",
            "owner": "abyss-machine",
            "artifacts": ["failure_matrix", "validate"],
            "chain_keys": ["failure_matrix"],
        },
        {
            "id": "e2e_probe_export_replay",
            "objective_area": "tests",
            "title": "Synthetic E2E proof from event through export and replay",
            "owner": "abyss-machine",
            "artifacts": ["probe", "cycle", "export", "replay"],
            "chain_keys": [
                "synthetic_request",
                "signal_fabric",
                "timeline",
                "spatial_graph",
                "causal_episode",
                "alert",
                "langgraph_investigation",
                "replay",
                "reaction_candidate",
                "governed_response",
                "body_trace",
                "entity_event_document",
                "export",
            ],
        },
        {
            "id": "owner_boundary",
            "objective_area": "boundary",
            "title": "abyss-stack remains owner of stack runtime/config while abyss-machine is read-only consumer",
            "owner": "abyss-machine",
            "artifacts": ["requirements", "requirement_probes", "export", "cycle"],
            "chain_keys": ["requirement_probes"],
        },
    ]


def objective_coverage_planes(spec: dict[str, Any]) -> list[str]:
    area_planes = {
        "inventory": ["observability_inventory"],
        "signal_fabric": ["signal_fabric", "observability_inventory"],
        "memory_space": ["memory_space", "rag_retrieval", "freshness_gates"],
        "langgraph_loop": [
            "langgraph_loop",
            "investigation_replay",
            "langgraph_replay",
        ],
        "warm_e2b_agent": ["resident_worker", "response_governance"],
        "machine_bridges": [
            "machine_bridges",
            "freshness_gates",
            "response_governance",
        ],
        "response_layer": ["response_governance"],
        "ux_api": ["export_handoff"],
        "tests": ["investigation_replay", "export_handoff"],
        "boundary": ["redaction_governance", "owner_boundary"],
    }
    id_planes = {
        "prometheus_promql": ["metrics_query", "observability_inventory"],
        "working_stack_runtime_body": [
            "working_stack_body",
            "runtime_organs",
            "model_root_inventory",
            "causal_timeline",
            "spatial_graph",
        ],
        "loki_logql": ["logs_query", "redaction_governance"],
        "grafana_health": ["operator_dashboard_truth"],
        "grafana_datasource_inventory": [
            "operator_dashboard_truth",
            "export_handoff",
            "redaction_governance",
        ],
        "alertmanager": ["alert_lifecycle", "response_governance"],
        "alloy_otel": ["otel_pipeline", "signal_fabric"],
        "trace_backend": ["causal_timeline", "spatial_graph"],
        "route_rag_api": ["rag_retrieval", "memory_space"],
        "postgres_neo4j_graph": ["spatial_graph", "memory_space"],
        "langchain_langgraph_stack": ["resident_worker", "response_governance"],
        "stack_models_stt_embeddings_tts_npu": [
            "ai_multimodal",
            "model_root_inventory",
            "npu_runtime",
        ],
        "warm_e2b_resident_worker": [
            "resident_worker",
            "cognitive_worker",
            "response_governance",
        ],
        "e4b_qwen_escalation": ["llm_escalation", "resource_gates", "mode_gates"],
        "machine_bridges": [
            "heartbeat_bridge",
            "nervous_bridge",
            "resource_gates",
            "mode_gates",
        ],
        "signal_fabric_schema": [
            "event_schema",
            "redaction_governance",
            "spatial_graph",
        ],
        "memory_space_freshness": ["freshness_gates", "rag_retrieval", "memory_space"],
        "checkpointed_investigation_replay": [
            "langgraph_loop",
            "langgraph_replay",
            "investigation_replay",
        ],
        "response_layer": ["reaction_candidates", "response_governance"],
        "ux_api_commands": ["operator_api", "export_handoff"],
        "failure_tests": ["failure_matrix", "redaction_governance"],
        "e2e_probe_export_replay": [
            "e2e_lineage",
            "export_handoff",
            "langgraph_replay",
        ],
        "owner_boundary": ["owner_boundary", "redaction_governance"],
    }
    planes = [
        *area_planes.get(str(spec.get("objective_area") or ""), []),
        *id_planes.get(str(spec.get("id") or ""), []),
    ]
    return sorted({str(plane) for plane in planes if plane})


_objective_coverage_planes = objective_coverage_planes


def objective_coverage_audit(
    write_latest: bool = True,
    refresh: bool = False,
    *,
    working_stack_doc: dict[str, Any] | None = None,
    stack_closure_dossier_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessCoveragePaths,
    config: SelfAwarenessCoverageConfig,
    runtime_port: SelfAwarenessCoverageRuntimePort,
    refresh_port: SelfAwarenessCoverageRefreshPort,
    contract_port: SelfAwarenessCoverageContractPort,
) -> dict[str, Any]:
    generated_at = runtime_port.now_iso()
    working_stack_doc_supplied = isinstance(working_stack_doc, dict)
    if refresh:
        refresh_port.cycle(write_latest=True)
    artifact_specs = contract_port.e2e_lineage_artifact_specs(
        include_cycle=True, include_probe=True
    )
    artifact_specs["validate"] = (
        paths.validate_latest,
        f"{config.schema_prefix}_self_awareness_validate_v1",
    )
    artifact_refs = {
        name: runtime_port.latest_artifact_ref(name, path, schema)
        for name, (path, schema) in artifact_specs.items()
    }
    capabilities = runtime_port.load_latest_json(
        paths.capabilities_latest,
        f"{config.schema_prefix}_self_awareness_capabilities_v1",
    )
    if (
        capabilities.get("schema")
        != f"{config.schema_prefix}_self_awareness_capabilities_v1"
    ):
        capabilities = refresh_port.capabilities(write_latest=True)
    requirements = runtime_port.load_latest_json(
        paths.requirements_latest,
        f"{config.schema_prefix}_self_awareness_requirements_v1",
    )
    if (
        requirements.get("schema")
        != f"{config.schema_prefix}_self_awareness_requirements_v1"
    ):
        requirements = refresh_port.requirements(write_latest=True)
    requirement_probes = runtime_port.load_latest_json(
        paths.requirement_probes_latest,
        f"{config.schema_prefix}_self_awareness_requirement_probes_v1",
    )
    if (
        requirement_probes.get("schema")
        != f"{config.schema_prefix}_self_awareness_requirement_probes_v1"
        or not contract_port.requirement_probes_cover_requirements(
            requirements, requirement_probes
        )
    ):
        requirement_probes = refresh_port.requirement_probes(
            write_latest=True, requirements_doc=requirements
        )
    cycle = runtime_port.load_latest_json(
        paths.cycle_latest, f"{config.schema_prefix}_self_awareness_cycle_v1"
    )
    export_doc = runtime_port.load_latest_json(
        paths.export_latest, f"{config.schema_prefix}_self_awareness_export_v1"
    )
    failure_matrix = runtime_port.load_latest_json(
        paths.failure_matrix_latest,
        f"{config.schema_prefix}_self_awareness_failure_matrix_v1",
    )
    validation_doc = runtime_port.load_latest_json(
        paths.validate_latest, f"{config.schema_prefix}_self_awareness_validate_v1"
    )
    working_stack = (
        working_stack_doc
        if isinstance(working_stack_doc, dict)
        else runtime_port.load_latest_json(
            paths.working_stack_latest,
            f"{config.schema_prefix}_self_awareness_working_stack_inventory_v1",
        )
    )
    if (
        working_stack.get("schema")
        != f"{config.schema_prefix}_self_awareness_working_stack_inventory_v1"
    ):
        working_stack = refresh_port.working_stack_inventory(write_latest=True)
    events_doc = runtime_port.load_latest_json(
        paths.events_latest, f"{config.schema_prefix}_self_awareness_events_v1"
    )
    if events_doc.get("schema") != f"{config.schema_prefix}_self_awareness_events_v1":
        if working_stack_doc_supplied:
            refresh_port.collect(write_latest=True, working_stack_doc=working_stack)
        else:
            refresh_port.collect(write_latest=True)
        events_doc = runtime_port.load_latest_json(
            paths.events_latest, f"{config.schema_prefix}_self_awareness_events_v1"
        )
    timeline_doc = runtime_port.load_latest_json(
        paths.timeline_latest, f"{config.schema_prefix}_self_awareness_timeline_v1"
    )
    if (
        timeline_doc.get("schema")
        != f"{config.schema_prefix}_self_awareness_timeline_v1"
    ):
        timeline_doc = refresh_port.timeline(write_latest=True)
    spatial_doc = runtime_port.load_latest_json(
        paths.spatial_graph_latest,
        f"{config.schema_prefix}_self_awareness_spatial_graph_v1",
    )
    if (
        spatial_doc.get("schema")
        != f"{config.schema_prefix}_self_awareness_spatial_graph_v1"
    ):
        if working_stack_doc_supplied:
            spatial_doc = refresh_port.spatial_graph(
                write_latest=True,
                working_stack_doc=working_stack,
                timeline_doc=timeline_doc,
            )
        else:
            spatial_doc = refresh_port.spatial_graph(write_latest=True)
    context_doc = runtime_port.load_latest_json(
        paths.context_latest, f"{config.schema_prefix}_self_awareness_context_v1"
    )
    if context_doc.get("schema") != f"{config.schema_prefix}_self_awareness_context_v1":
        context_doc = refresh_port.context(write_latest=True)
    episodes_doc = runtime_port.load_latest_json(
        paths.episodes_latest, f"{config.schema_prefix}_self_awareness_episodes_v1"
    )
    if (
        episodes_doc.get("schema")
        != f"{config.schema_prefix}_self_awareness_episodes_v1"
    ):
        if working_stack_doc_supplied:
            episodes_doc = refresh_port.episodes(
                write_latest=True, working_stack_doc=working_stack
            )
        else:
            episodes_doc = refresh_port.episodes(write_latest=True)
    alerts_doc = runtime_port.load_latest_json(
        paths.alerts_latest, f"{config.schema_prefix}_self_awareness_alerts_v1"
    )
    if alerts_doc.get("schema") != f"{config.schema_prefix}_self_awareness_alerts_v1":
        alerts_doc = refresh_port.alerts(write_latest=True)
    investigation_doc = runtime_port.load_latest_json(
        paths.investigate_latest,
        f"{config.schema_prefix}_self_awareness_investigation_v1",
    )
    if (
        investigation_doc.get("schema")
        != f"{config.schema_prefix}_self_awareness_investigation_v1"
    ):
        investigation_doc = refresh_port.investigate("latest", write_latest=True)
    replay_doc = runtime_port.load_latest_json(
        paths.replay_latest, f"{config.schema_prefix}_self_awareness_replay_v1"
    )
    if replay_doc.get("schema") != f"{config.schema_prefix}_self_awareness_replay_v1":
        replay_doc = refresh_port.replay(
            thread_id=str(investigation_doc.get("thread_id") or ""), write_latest=True
        )
    stack_closure_dossier = (
        stack_closure_dossier_doc
        if isinstance(stack_closure_dossier_doc, dict)
        else runtime_port.load_latest_json(
            paths.stack_closure_dossier_latest,
            f"{config.schema_prefix}_self_awareness_stack_closure_dossier_v1",
        )
    )
    expected_working_gaps = runtime_evidence_contracts.safe_int(
        self_awareness_contracts.nested_get(working_stack, ["summary", "usage_gaps"]), 0
    )
    if stack_closure_dossier.get(
        "schema"
    ) != f"{config.schema_prefix}_self_awareness_stack_closure_dossier_v1" or (
        expected_working_gaps > 0
        and runtime_evidence_contracts.safe_int(
            self_awareness_contracts.nested_get(
                stack_closure_dossier, ["summary", "working_stack_activation_entries"]
            ),
            -1,
        )
        != expected_working_gaps
    ):
        stack_closure_dossier = refresh_port.stack_closure_dossier(
            write_latest=True,
            requirements_doc=requirements,
            requirement_probes_doc=requirement_probes,
            working_stack_doc=working_stack,
        )
    working_stack_activation_dossier = (
        stack_closure_dossier.get("working_stack_activation_dossier")
        if isinstance(
            stack_closure_dossier.get("working_stack_activation_dossier"), dict
        )
        else {}
    )
    working_stack_activation_entries = (
        working_stack_activation_dossier.get("entries")
        if isinstance(working_stack_activation_dossier.get("entries"), list)
        else []
    )
    working_stack_activation_summary = (
        working_stack_activation_dossier.get("summary")
        if isinstance(working_stack_activation_dossier.get("summary"), dict)
        else {}
    )
    stack_closure_entries = (
        stack_closure_dossier.get("entries")
        if isinstance(stack_closure_dossier.get("entries"), list)
        else []
    )
    stack_closure_entry_by_requirement = {
        str(item.get("requirement_id")): item
        for item in stack_closure_entries
        if isinstance(item, dict) and item.get("requirement_id")
    }
    cycle_chain = (
        cycle.get("cycle_chain") if isinstance(cycle.get("cycle_chain"), dict) else {}
    )
    cycle_chain, replay_doc, export_doc = (
        contract_port.resident_cognitive_cycle_chain_overlay(
            cycle_chain,
            replay_doc=runtime_port.load_latest_json(
                paths.replay_latest, f"{config.schema_prefix}_self_awareness_replay_v1"
            ),
            export_doc=export_doc,
            write_latest=True,
        )
    )
    for refreshed_name in ("replay", "export"):
        if refreshed_name in artifact_specs:
            artifact_refs[refreshed_name] = runtime_port.latest_artifact_ref(
                refreshed_name, *artifact_specs[refreshed_name]
            )
    capability_rows = (
        capabilities.get("capabilities")
        if isinstance(capabilities.get("capabilities"), list)
        else []
    )
    capability_by_id = {
        str(item.get("id")): item
        for item in capability_rows
        if isinstance(item, dict) and item.get("id")
    }
    requirement_rows = (
        requirements.get("requirements")
        if isinstance(requirements.get("requirements"), list)
        else []
    )
    requirement_by_id = {
        str(item.get("id")): item
        for item in requirement_rows
        if isinstance(item, dict) and item.get("id")
    }
    probe_rows = (
        requirement_probes.get("probes")
        if isinstance(requirement_probes.get("probes"), list)
        else []
    )
    probe_by_id = {
        str(item.get("id") or item.get("requirement_id")): item
        for item in probe_rows
        if isinstance(item, dict) and (item.get("id") or item.get("requirement_id"))
    }
    rows: list[dict[str, Any]] = []
    for spec in objective_coverage_specs():
        objective_coverage_planes = _objective_coverage_planes(spec)
        capability_ids = [
            str(item)
            for item in (
                spec.get("capabilities")
                if isinstance(spec.get("capabilities"), list)
                else []
            )
        ]
        requirement_ids = [
            str(item)
            for item in (
                spec.get("requirements")
                if isinstance(spec.get("requirements"), list)
                else []
            )
        ]
        artifact_names = [
            str(item)
            for item in (
                spec.get("artifacts") if isinstance(spec.get("artifacts"), list) else []
            )
        ]
        chain_keys = [
            str(item)
            for item in (
                spec.get("chain_keys")
                if isinstance(spec.get("chain_keys"), list)
                else []
            )
        ]
        capability_status = [
            {
                "id": capability_id,
                "present": capability_id in capability_by_id,
                "ok": capability_by_id.get(capability_id, {}).get("ok"),
                "owner": capability_by_id.get(capability_id, {}).get("owner"),
                "evidence_refs": capability_by_id.get(capability_id, {}).get(
                    "evidence_refs"
                ),
            }
            for capability_id in capability_ids
        ]
        all_capabilities_present_and_ok = bool(capability_ids) and all(
            (
                item.get("present") is True and item.get("ok") is True
                for item in capability_status
            )
        )
        missing_capabilities = [
            item["id"] for item in capability_status if item["present"] is not True
        ]
        degraded_capabilities = [
            item["id"]
            for item in capability_status
            if item["present"] is True and item["ok"] is False
        ]
        blockers: list[dict[str, Any]] = []
        for requirement_id in requirement_ids:
            requirement = requirement_by_id.get(requirement_id, {})
            probe = probe_by_id.get(requirement_id, {})
            dossier_entry = stack_closure_entry_by_requirement.get(requirement_id, {})
            closure_readiness = (
                requirement.get("closure_readiness")
                if isinstance(requirement.get("closure_readiness"), dict)
                else {}
            )
            probe_readiness = (
                probe.get("closure_readiness")
                if isinstance(probe.get("closure_readiness"), dict)
                else {}
            )
            closure_acceptance = (
                dossier_entry.get("closure_acceptance")
                if isinstance(dossier_entry, dict)
                and isinstance(dossier_entry.get("closure_acceptance"), dict)
                else {}
            )
            coverage_impact = (
                requirement.get("coverage_impact")
                if isinstance(requirement.get("coverage_impact"), dict)
                else closure_readiness.get("coverage_impact")
                if isinstance(closure_readiness.get("coverage_impact"), dict)
                else probe_readiness.get("coverage_impact")
                if isinstance(probe_readiness.get("coverage_impact"), dict)
                else {}
            )
            requirement_present = requirement_id in requirement_by_id
            probe_status = probe.get("status")
            requirement_absence_covered = (
                not requirement_present
                and all_capabilities_present_and_ok
                and (probe_status not in {"open", "blocked", "failed"})
            )
            blockers.append(
                {
                    "id": requirement_id,
                    "present": requirement_present,
                    "owner": requirement.get("owner"),
                    "status": requirement.get("status"),
                    "title": requirement.get("title"),
                    "current_handoff_state": "absent_covered_by_current_capability"
                    if requirement_absence_covered
                    else "present"
                    if requirement_present
                    else "absent_unproven",
                    "absence_covered_by_current_capability": requirement_absence_covered,
                    "requirement_missing_blocks_coverage": not requirement_present
                    and (not requirement_absence_covered),
                    "coverage_capability_ids": capability_ids
                    if requirement_absence_covered
                    else [],
                    "coverage_capability_evidence_refs": [
                        ref
                        for capability_id in capability_ids
                        for ref in (
                            capability_by_id.get(capability_id, {}).get("evidence_refs")
                            if isinstance(
                                capability_by_id.get(capability_id, {}).get(
                                    "evidence_refs"
                                ),
                                list,
                            )
                            else []
                        )
                    ]
                    if requirement_absence_covered
                    else [],
                    "closure_readiness": closure_readiness or None,
                    "closure_acceptance": closure_acceptance or None,
                    "closure_acceptance_id": closure_acceptance.get("acceptance_id")
                    if closure_acceptance
                    else None,
                    "compat_requirement_id": self_awareness_contracts.nested_get(
                        closure_acceptance,
                        ["stack_compat_requirement", "requirement_id"],
                    )
                    if closure_acceptance
                    else None,
                    "coverage_impact": coverage_impact or None,
                    "blocking_check_keys": requirement.get("blocking_check_keys"),
                    "runbook_candidate_id": requirement.get("runbook_candidate_id"),
                    "probe_status": probe_status,
                }
            )
        open_blocker_ids = [
            item["id"]
            for item in blockers
            if item.get("present") is True
            and item.get("owner") == "abyss-stack"
            and (item.get("probe_status") != "closed")
        ]
        open_blockers = [
            item for item in blockers if item.get("id") in set(open_blocker_ids)
        ]
        blocker_check_keys = sorted(
            {
                str(key)
                for item in open_blockers
                for key in (
                    item.get("blocking_check_keys")
                    if isinstance(item.get("blocking_check_keys"), list)
                    else []
                )
                if key
            }
        )
        coverage_impacts = [
            {
                "requirement_id": item.get("id"),
                "organ": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "organ"]
                ),
                "coverage_planes": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "coverage_planes"]
                )
                if isinstance(
                    self_awareness_contracts.nested_get(
                        item, ["coverage_impact", "coverage_planes"]
                    ),
                    list,
                )
                else [],
                "affected_stack_surfaces": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "affected_stack_surfaces"]
                )
                if isinstance(
                    self_awareness_contracts.nested_get(
                        item, ["coverage_impact", "affected_stack_surfaces"]
                    ),
                    list,
                )
                else [],
                "affected_machine_surfaces": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "affected_machine_surfaces"]
                )
                if isinstance(
                    self_awareness_contracts.nested_get(
                        item, ["coverage_impact", "affected_machine_surfaces"]
                    ),
                    list,
                )
                else [],
                "blocks_stack_usage_requirements": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "blocks_stack_usage_requirements"]
                )
                if isinstance(
                    self_awareness_contracts.nested_get(
                        item, ["coverage_impact", "blocks_stack_usage_requirements"]
                    ),
                    list,
                )
                else [],
                "closure_value": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "closure_value"]
                ),
                "proof_commands": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "proof_commands"]
                )
                if isinstance(
                    self_awareness_contracts.nested_get(
                        item, ["coverage_impact", "proof_commands"]
                    ),
                    list,
                )
                else [],
                "policy": self_awareness_contracts.nested_get(
                    item, ["coverage_impact", "policy"]
                )
                if isinstance(
                    self_awareness_contracts.nested_get(
                        item, ["coverage_impact", "policy"]
                    ),
                    dict,
                )
                else {},
            }
            for item in open_blockers
            if isinstance(item.get("coverage_impact"), dict)
        ]
        blocked_coverage_planes = sorted(
            {
                str(plane)
                for impact in coverage_impacts
                for plane in (
                    impact.get("coverage_planes")
                    if isinstance(impact.get("coverage_planes"), list)
                    else []
                )
                if plane
            }
        )
        missing_requirements = [
            item["id"]
            for item in blockers
            if item.get("present") is not True
            and item.get("absence_covered_by_current_capability") is not True
        ]
        row_artifacts = [
            artifact_refs[name] for name in artifact_names if name in artifact_refs
        ]
        missing_artifacts = [
            str(artifact.get("name"))
            for artifact in row_artifacts
            if artifact.get("exists") is not True
            or artifact.get("schema_ok") is not True
            or (not artifact.get("sha256"))
        ]
        chain_missing = [key for key in chain_keys if cycle_chain.get(key) is not True]
        status = "covered"
        if open_blocker_ids:
            status = "blocked_stack_owned"
        elif (
            missing_requirements
            or missing_capabilities
            or missing_artifacts
            or chain_missing
        ):
            status = "incomplete"
        elif degraded_capabilities:
            status = "degraded"
        covered_coverage_planes = (
            objective_coverage_planes if status == "covered" else []
        )
        row_coverage_planes = (
            blocked_coverage_planes
            if status == "blocked_stack_owned"
            else objective_coverage_planes
        )
        evidence_refs = [
            {
                "path": artifact.get("path"),
                "schema": artifact.get("schema"),
                "sha256": artifact.get("sha256"),
                "coverage_row": spec.get("id"),
            }
            for artifact in row_artifacts
            if artifact.get("path")
        ]
        rows.append(
            {
                "schema": f"{config.schema_prefix}_self_awareness_objective_coverage_row_v1",
                "id": spec.get("id"),
                "objective_area": spec.get("objective_area"),
                "title": spec.get("title"),
                "owner": spec.get("owner"),
                "status": status,
                "capabilities": capability_status,
                "missing_capabilities": missing_capabilities,
                "degraded_capabilities": degraded_capabilities,
                "requirements": blockers,
                "open_stack_requirement_ids": open_blocker_ids,
                "blocked_by_requirement_ids": open_blocker_ids,
                "blocking_check_keys": blocker_check_keys,
                "coverage_impacts": coverage_impacts,
                "objective_coverage_planes": objective_coverage_planes,
                "covered_coverage_planes": covered_coverage_planes,
                "coverage_planes": row_coverage_planes,
                "blocked_coverage_planes": blocked_coverage_planes,
                "coverage_plane_status": {
                    "objective": objective_coverage_planes,
                    "covered": covered_coverage_planes,
                    "blocked": blocked_coverage_planes,
                    "unproven": []
                    if status in {"covered", "blocked_stack_owned"}
                    else objective_coverage_planes,
                },
                "missing_requirements": missing_requirements,
                "artifacts": row_artifacts,
                "missing_artifacts": missing_artifacts,
                "chain_keys": chain_keys,
                "missing_chain_keys": chain_missing,
                "evidence_refs": evidence_refs,
                "policy": {
                    "read_only": True,
                    "host_layer_mutates_stack": False,
                    "actions_executed": False,
                    "automatic_remediation": False,
                    "raw_evidence_is_not_truth": True,
                },
            }
        )
    working_stack_gap_rows: list[dict[str, Any]] = []
    if not working_stack_activation_entries and expected_working_gaps:
        working_stack_activation_dossier = (
            contract_port.working_stack_activation_dossier(
                working_stack, generated_at=generated_at, write_latest=True
            )
        )
        working_stack_activation_entries = (
            working_stack_activation_dossier.get("entries")
            if isinstance(working_stack_activation_dossier.get("entries"), list)
            else []
        )
        working_stack_activation_summary = (
            working_stack_activation_dossier.get("summary")
            if isinstance(working_stack_activation_dossier.get("summary"), dict)
            else {}
        )
    dependency_probe_link_integrity = contract_port.working_stack_link_integrity_matrix(
        working_stack_doc=working_stack,
        events_doc=events_doc,
        timeline_doc=timeline_doc,
        spatial_doc=spatial_doc,
        context_doc=context_doc,
        episodes_doc=episodes_doc,
        coverage_gap_rows=[],
        generated_at=generated_at,
    )
    if not contract_port.dependent_link_readmodels_fresh(
        dependency_probe_link_integrity
    ) or not contract_port.link_integrity_matches_working_stack(
        working_stack, dependency_probe_link_integrity
    ):
        if working_stack_doc_supplied:
            refresh_port.refresh_working_stack_dependent_readmodels(
                working_stack_doc=working_stack
            )
        else:
            refresh_port.refresh_working_stack_dependent_readmodels()
        events_doc = runtime_port.load_latest_json(
            paths.events_latest, f"{config.schema_prefix}_self_awareness_events_v1"
        )
        timeline_doc = runtime_port.load_latest_json(
            paths.timeline_latest, f"{config.schema_prefix}_self_awareness_timeline_v1"
        )
        spatial_doc = runtime_port.load_latest_json(
            paths.spatial_graph_latest,
            f"{config.schema_prefix}_self_awareness_spatial_graph_v1",
        )
        context_doc = runtime_port.load_latest_json(
            paths.context_latest, f"{config.schema_prefix}_self_awareness_context_v1"
        )
        episodes_doc = runtime_port.load_latest_json(
            paths.episodes_latest, f"{config.schema_prefix}_self_awareness_episodes_v1"
        )
    for entry in working_stack_activation_entries:
        if not isinstance(entry, dict) or not entry.get("service"):
            continue
        service = str(entry.get("service"))
        status = str(entry.get("machine_usage_status") or "unknown")
        runtime = entry.get("runtime") if isinstance(entry.get("runtime"), dict) else {}
        coverage_planes = (
            entry.get("coverage_planes")
            if isinstance(entry.get("coverage_planes"), list)
            else contract_port.working_stack_gap_coverage_planes(status)
        )
        row = {
            "schema": f"{config.schema_prefix}_self_awareness_working_stack_gap_coverage_row_v1",
            "id": "working_stack_gap:" + service,
            "service": service,
            "owner": "abyss-stack",
            "status": "working_stack_usage_gap",
            "machine_usage_status": status,
            "usage_gap": entry.get("usage_gap"),
            "activation_kind": entry.get("activation_kind"),
            "working_stack_link_id": entry.get("working_stack_link_id"),
            "runtime_running": runtime.get("running"),
            "container": runtime.get("container"),
            "health": runtime.get("health"),
            "deep_usage_proven": entry.get("deep_usage_proven"),
            "coverage_planes": coverage_planes,
            "blocked_coverage_planes": coverage_planes,
            "closure_blocker_keys": entry.get("closure_blocker_keys")
            if isinstance(entry.get("closure_blocker_keys"), list)
            else [],
            "missing_checks": entry.get("missing_checks")
            if isinstance(entry.get("missing_checks"), list)
            else [],
            "fulfilled_checks": entry.get("fulfilled_checks")
            if isinstance(entry.get("fulfilled_checks"), list)
            else [],
            "activation_readiness": entry.get("activation_readiness")
            if isinstance(entry.get("activation_readiness"), dict)
            else {},
            "closure_acceptance": entry.get("closure_acceptance")
            if isinstance(entry.get("closure_acceptance"), dict)
            else {},
            "synthetic_scenario": entry.get("synthetic_scenario")
            if isinstance(entry.get("synthetic_scenario"), dict)
            else {},
            "runbook_candidate": entry.get("runbook_candidate")
            if isinstance(entry.get("runbook_candidate"), dict)
            else {},
            "safe_next_action": entry.get("safe_next_action")
            if isinstance(entry.get("safe_next_action"), dict)
            else {},
            "verifier_commands": entry.get("verifier_commands")
            if isinstance(entry.get("verifier_commands"), list)
            else [],
            "evidence_refs": entry.get("evidence_refs")
            if isinstance(entry.get("evidence_refs"), list)
            else [],
            "policy": {
                "read_only": True,
                "handoff_only": True,
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "actions_executed": False,
                "automatic_remediation": False,
                "raw_evidence_is_not_truth": True,
                "working_stack_gap_is_open_potential_not_host_failure": True,
            },
        }
        row["synthetic_proof"] = contract_port.activation_synthetic_proof(
            entry,
            generated_at=generated_at,
            working_stack_doc=working_stack,
            spatial_doc=spatial_doc,
            episodes_doc=episodes_doc,
            alerts_doc=alerts_doc,
            export_doc=export_doc,
            cycle_doc=cycle,
            investigation_doc=investigation_doc,
            replay_doc=replay_doc,
            coverage_row=row,
        )
        working_stack_gap_rows.append(row)
    activation_smoke_doc = runtime_port.load_latest_json(
        paths.activation_smoke_latest,
        f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_v1",
    )
    if (
        working_stack_activation_entries
        and contract_port.activation_smoke_needs_refresh(
            activation_smoke_doc, working_stack_activation_entries
        )
    ):
        if working_stack_doc_supplied:
            activation_smoke_doc = refresh_port.activation_smoke(
                write_latest=True,
                stack_closure_dossier_doc=stack_closure_dossier,
                working_stack_doc=working_stack,
            )
        else:
            activation_smoke_doc = refresh_port.activation_smoke(
                write_latest=True, stack_closure_dossier_doc=stack_closure_dossier
            )
    activation_smoke_by_service = (
        activation_smoke_doc.get("by_service")
        if isinstance(activation_smoke_doc.get("by_service"), dict)
        else {}
    )
    for row in working_stack_gap_rows:
        if not isinstance(row, dict) or not row.get("service"):
            continue
        smoke_row = activation_smoke_by_service.get(str(row.get("service")))
        row["activation_smoke"] = contract_port.activation_smoke_compact(smoke_row)
        row.setdefault("evidence_refs", [])
        if isinstance(row["evidence_refs"], list):
            row["evidence_refs"].append(
                {
                    "path": str(paths.activation_smoke_latest),
                    "service": row.get("service"),
                    "section": "activation_smoke",
                }
            )
    working_stack_link_integrity = contract_port.working_stack_link_integrity_matrix(
        working_stack_doc=working_stack,
        events_doc=events_doc,
        timeline_doc=timeline_doc,
        spatial_doc=spatial_doc,
        context_doc=context_doc,
        episodes_doc=episodes_doc,
        coverage_gap_rows=working_stack_gap_rows,
        generated_at=generated_at,
    )
    working_stack_link_integrity_incomplete_rows = [
        str(row.get("service"))
        for row in (
            working_stack_link_integrity.get("rows")
            if isinstance(working_stack_link_integrity.get("rows"), list)
            else []
        )
        if not row.get("complete")
    ]
    incomplete_rows = [
        str(row.get("id")) for row in rows if row.get("status") == "incomplete"
    ]
    degraded_rows = [
        str(row.get("id")) for row in rows if row.get("status") == "degraded"
    ]
    blocked_rows = [
        str(row.get("id")) for row in rows if row.get("status") == "blocked_stack_owned"
    ]
    mutation_claims = [
        str(row.get("id"))
        for row in rows
        if self_awareness_contracts.nested_get(
            row, ["policy", "host_layer_mutates_stack"]
        )
        is not False
    ]
    open_stack_requirement_ids = sorted(
        {
            requirement_id
            for row in rows
            for requirement_id in (
                row.get("open_stack_requirement_ids")
                if isinstance(row.get("open_stack_requirement_ids"), list)
                else []
            )
        }
    )
    blocked_coverage_planes = sorted(
        {
            str(plane)
            for row in rows
            for plane in (
                row.get("blocked_coverage_planes")
                if isinstance(row.get("blocked_coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    objective_coverage_planes = sorted(
        {
            str(plane)
            for row in rows
            for plane in (
                row.get("objective_coverage_planes")
                if isinstance(row.get("objective_coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    covered_coverage_planes = sorted(
        {
            str(plane)
            for row in rows
            for plane in (
                row.get("covered_coverage_planes")
                if isinstance(row.get("covered_coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    working_stack_gap_coverage_planes = sorted(
        {
            str(plane)
            for row in working_stack_gap_rows
            for plane in (
                row.get("blocked_coverage_planes")
                if isinstance(row.get("blocked_coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    working_stack_activation_synthetic_proofs = [
        row.get("synthetic_proof")
        for row in working_stack_gap_rows
        if isinstance(row.get("synthetic_proof"), dict)
    ]
    working_stack_activation_synthetic_proofs_complete = [
        proof
        for proof in working_stack_activation_synthetic_proofs
        if contract_port.activation_synthetic_proof_complete(proof)
    ]
    working_stack_activation_synthetic_proof_incomplete_rows = [
        str(row.get("id"))
        for row in working_stack_gap_rows
        if not contract_port.activation_synthetic_proof_complete(
            row.get("synthetic_proof")
        )
    ]
    working_stack_activation_smoke_incomplete_rows = [
        str(row.get("id"))
        for row in working_stack_gap_rows
        if not self_awareness_contracts.nested_get(
            row, ["activation_smoke", "complete"]
        )
    ]
    data = {
        "schema": f"{config.schema_prefix}_self_awareness_objective_coverage_audit_v1",
        "version": config.version,
        "generated_at": generated_at,
        "ok": not incomplete_rows
        and (not mutation_claims)
        and (not working_stack_activation_synthetic_proof_incomplete_rows)
        and (not working_stack_activation_smoke_incomplete_rows)
        and (not working_stack_link_integrity_incomplete_rows),
        "status": "covered_with_stack_blockers"
        if blocked_rows
        and (not incomplete_rows)
        and (not working_stack_activation_synthetic_proof_incomplete_rows)
        and (not working_stack_activation_smoke_incomplete_rows)
        and (not working_stack_link_integrity_incomplete_rows)
        else "covered"
        if not incomplete_rows
        and (not working_stack_activation_synthetic_proof_incomplete_rows)
        and (not working_stack_activation_smoke_incomplete_rows)
        and (not working_stack_link_integrity_incomplete_rows)
        else "incomplete",
        "summary": {
            "rows": len(rows),
            "covered": sum((1 for row in rows if row.get("status") == "covered")),
            "blocked_stack_owned": len(blocked_rows),
            "degraded": len(degraded_rows),
            "incomplete": len(incomplete_rows),
            "open_stack_requirements": len(open_stack_requirement_ids),
            "stack_requirement_closure_acceptance_packets": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    stack_closure_dossier, ["summary", "closure_acceptance_packets"]
                ),
                0,
            ),
            "stack_requirement_closure_acceptance_packets_complete": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    stack_closure_dossier,
                    ["summary", "closure_acceptance_packets_complete"],
                ),
                0,
            ),
            "stack_requirement_compat_requirements": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    stack_closure_dossier,
                    ["summary", "stack_requirement_compat_requirements"],
                ),
                0,
            ),
            "objective_coverage_planes": objective_coverage_planes,
            "covered_coverage_planes": covered_coverage_planes,
            "blocked_coverage_planes": blocked_coverage_planes,
            "working_stack_gap_coverage_planes": working_stack_gap_coverage_planes,
            "cycle_status": cycle.get("status"),
            "cycle_chain_passed": self_awareness_contracts.nested_get(
                cycle, ["summary", "chain_passed"]
            ),
            "cycle_chain_total": self_awareness_contracts.nested_get(
                cycle, ["summary", "chain_total"]
            ),
            "e2e_lineage_ok": self_awareness_contracts.nested_get(
                cycle, ["summary", "e2e_lineage_ok"]
            ),
            "export_missing": self_awareness_contracts.nested_get(
                export_doc, ["summary", "missing"]
            ),
            "failure_matrix_missing_required": self_awareness_contracts.nested_get(
                failure_matrix, ["summary", "missing_required"]
            ),
            "working_stack_organs": self_awareness_contracts.nested_get(
                working_stack, ["summary", "organs"]
            ),
            "working_stack_usage_gaps": self_awareness_contracts.nested_get(
                working_stack, ["summary", "usage_gaps"]
            ),
            "working_stack_link_integrity_rows": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    working_stack_link_integrity, ["summary", "rows"]
                ),
                0,
            ),
            "working_stack_link_integrity_rows_complete": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    working_stack_link_integrity, ["summary", "complete_rows"]
                ),
                0,
            ),
            "working_stack_link_integrity_missing_rows": self_awareness_contracts.nested_get(
                working_stack_link_integrity, ["summary", "missing_rows"]
            )
            if isinstance(
                self_awareness_contracts.nested_get(
                    working_stack_link_integrity, ["summary", "missing_rows"]
                ),
                list,
            )
            else [],
            "working_stack_link_integrity_usage_gap_rows": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    working_stack_link_integrity, ["summary", "usage_gap_rows"]
                ),
                0,
            ),
            "working_stack_link_integrity_usage_gap_rows_with_coverage": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    working_stack_link_integrity,
                    ["summary", "usage_gap_rows_with_coverage"],
                ),
                0,
            ),
            "working_stack_link_integrity_usage_gap_rows_with_activation_smoke": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    working_stack_link_integrity,
                    ["summary", "usage_gap_rows_with_activation_smoke"],
                ),
                0,
            ),
            "working_stack_gap_rows": len(working_stack_gap_rows),
            "working_stack_gap_services": [
                str(row.get("service")) for row in working_stack_gap_rows
            ],
            "working_stack_activation_entries": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("entries"),
                len(working_stack_activation_entries),
            ),
            "working_stack_activation_missing_checks": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("missing_checks"), 0
            ),
            "working_stack_activation_fulfilled_checks": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("fulfilled_checks"), 0
            ),
            "working_stack_activation_verifier_commands": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("verifier_commands"), 0
            ),
            "working_stack_activation_entries_complete": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("activation_entries_complete"), 0
            ),
            "working_stack_activation_synthetic_scenarios": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("synthetic_scenarios"),
                len(
                    [
                        row
                        for row in working_stack_gap_rows
                        if isinstance(row.get("synthetic_scenario"), dict)
                        and row["synthetic_scenario"]
                    ]
                ),
            ),
            "working_stack_activation_synthetic_scenarios_complete": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("synthetic_scenarios_complete"),
                sum(
                    (
                        1
                        for row in working_stack_gap_rows
                        if self_awareness_contracts.nested_get(
                            row, ["synthetic_scenario", "complete"]
                        )
                        is True
                    )
                ),
            ),
            "working_stack_activation_closure_acceptance_packets": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("closure_acceptance_packets"),
                len(
                    [
                        row
                        for row in working_stack_gap_rows
                        if isinstance(row.get("closure_acceptance"), dict)
                        and row["closure_acceptance"]
                    ]
                ),
            ),
            "working_stack_activation_closure_acceptance_packets_complete": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get(
                    "closure_acceptance_packets_complete"
                ),
                sum(
                    (
                        1
                        for row in working_stack_gap_rows
                        if self_awareness_contracts.nested_get(
                            row, ["closure_acceptance", "complete"]
                        )
                        is True
                    )
                ),
            ),
            "working_stack_activation_compat_requirements": runtime_evidence_contracts.safe_int(
                working_stack_activation_summary.get("activation_compat_requirements"),
                len(
                    {
                        str(
                            self_awareness_contracts.nested_get(
                                row,
                                [
                                    "closure_acceptance",
                                    "stack_compat_requirement",
                                    "requirement_id",
                                ],
                            )
                        )
                        for row in working_stack_gap_rows
                        if self_awareness_contracts.nested_get(
                            row,
                            [
                                "closure_acceptance",
                                "stack_compat_requirement",
                                "requirement_id",
                            ],
                        )
                    }
                ),
            ),
            "working_stack_activation_synthetic_proofs": len(
                working_stack_activation_synthetic_proofs
            ),
            "working_stack_activation_synthetic_proofs_complete": len(
                working_stack_activation_synthetic_proofs_complete
            ),
            "working_stack_activation_synthetic_proof_incomplete_rows": working_stack_activation_synthetic_proof_incomplete_rows,
            "working_stack_activation_synthetic_proof_services": [
                str(proof.get("service"))
                for proof in working_stack_activation_synthetic_proofs
                if isinstance(proof, dict) and proof.get("service")
            ],
            "working_stack_activation_smoke_rows": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    activation_smoke_doc, ["summary", "rows"]
                ),
                0,
            ),
            "working_stack_activation_smoke_rows_ok": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    activation_smoke_doc, ["summary", "rows_ok"]
                ),
                0,
            ),
            "working_stack_activation_smoke_incomplete_rows": working_stack_activation_smoke_incomplete_rows,
            "working_stack_activation_smoke_failed_services": self_awareness_contracts.nested_get(
                activation_smoke_doc, ["summary", "failed_services"]
            )
            if isinstance(
                self_awareness_contracts.nested_get(
                    activation_smoke_doc, ["summary", "failed_services"]
                ),
                list,
            )
            else [],
            "validation_summary": validation_doc.get("summary"),
        },
        "rows": rows,
        "working_stack_gap_rows": working_stack_gap_rows,
        "working_stack_link_integrity": working_stack_link_integrity,
        "working_stack_activation_dossier": {
            "schema": working_stack_activation_dossier.get("schema"),
            "status": working_stack_activation_dossier.get("status"),
            "summary": working_stack_activation_summary,
            "open_service_ids": working_stack_activation_dossier.get("open_service_ids")
            if isinstance(
                working_stack_activation_dossier.get("open_service_ids"), list
            )
            else [],
            "policy": working_stack_activation_dossier.get("policy")
            if isinstance(working_stack_activation_dossier.get("policy"), dict)
            else {},
        },
        "blocked_rows": blocked_rows,
        "degraded_rows": degraded_rows,
        "incomplete_rows": incomplete_rows,
        "open_stack_requirement_ids": open_stack_requirement_ids,
        "artifact_refs": artifact_refs,
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
            "writes_project_roots": False,
            "actions_executed": False,
            "automatic_remediation": False,
            "open_stack_requirements_are_blockers_not_host_failures": True,
            "working_stack_usage_gaps_are_open_potential_not_host_failures": True,
            "raw_evidence_is_not_truth": True,
        },
        "source_commands": {
            "coverage_audit": "abyss-machine self-awareness coverage-audit --json",
            "activation_smoke": "abyss-machine self-awareness activation-smoke --json",
            "refresh": "abyss-machine self-awareness coverage-audit --refresh --json",
            "cycle": "abyss-machine self-awareness cycle --json",
            "requirements": "abyss-machine self-awareness requirements --json",
            "validate": "abyss-machine self-awareness validate --json",
            "export": "abyss-machine self-awareness export --json",
        },
    }
    if write_latest:
        errors = runtime_port.write_latest_and_history(
            data, paths.coverage_audit_latest, paths.coverage_audit_root
        )
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def coverage_audit_blocker_linkage_issues(
    coverage_audit: dict[str, Any],
    *,
    config: SelfAwarenessCoverageConfig,
    contract_port: SelfAwarenessCoverageContractPort,
) -> list[str]:
    if (
        coverage_audit.get("schema")
        != f"{config.schema_prefix}_self_awareness_objective_coverage_audit_v1"
    ):
        return ["schema"]
    rows = (
        coverage_audit.get("rows")
        if isinstance(coverage_audit.get("rows"), list)
        else []
    )
    blocked_rows = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("status") == "blocked_stack_owned"
    ]
    covered_rows = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("status") == "covered"
    ]
    issues: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "unknown")
        objective_planes = (
            row.get("objective_coverage_planes")
            if isinstance(row.get("objective_coverage_planes"), list)
            else []
        )
        if not objective_planes:
            issues.append(f"{row_id}:objective_coverage_planes")
        plane_status = (
            row.get("coverage_plane_status")
            if isinstance(row.get("coverage_plane_status"), dict)
            else {}
        )
        if [str(item) for item in plane_status.get("objective", []) if item] != [
            str(item) for item in objective_planes
        ]:
            issues.append(f"{row_id}:coverage_plane_status_objective")
    for row in covered_rows:
        row_id = str(row.get("id") or "unknown")
        objective_planes = (
            row.get("objective_coverage_planes")
            if isinstance(row.get("objective_coverage_planes"), list)
            else []
        )
        covered_planes = (
            row.get("covered_coverage_planes")
            if isinstance(row.get("covered_coverage_planes"), list)
            else []
        )
        coverage_planes = (
            row.get("coverage_planes")
            if isinstance(row.get("coverage_planes"), list)
            else []
        )
        if not covered_planes:
            issues.append(f"{row_id}:covered_coverage_planes")
        if [str(item) for item in covered_planes] != [
            str(item) for item in objective_planes
        ]:
            issues.append(f"{row_id}:covered_objective_mismatch")
        if [str(item) for item in coverage_planes] != [
            str(item) for item in objective_planes
        ]:
            issues.append(f"{row_id}:coverage_planes_objective_alias")
    for row in blocked_rows:
        row_id = str(row.get("id") or "unknown")
        blocked_by = (
            row.get("blocked_by_requirement_ids")
            if isinstance(row.get("blocked_by_requirement_ids"), list)
            else []
        )
        open_stack = (
            row.get("open_stack_requirement_ids")
            if isinstance(row.get("open_stack_requirement_ids"), list)
            else []
        )
        requirements = (
            row.get("requirements")
            if isinstance(row.get("requirements"), list)
            else []
        )
        coverage_impacts = (
            row.get("coverage_impacts")
            if isinstance(row.get("coverage_impacts"), list)
            else []
        )
        blocked_planes = (
            row.get("blocked_coverage_planes")
            if isinstance(row.get("blocked_coverage_planes"), list)
            else []
        )
        coverage_planes = (
            row.get("coverage_planes")
            if isinstance(row.get("coverage_planes"), list)
            else []
        )
        if not blocked_by:
            issues.append(f"{row_id}:blocked_by_requirement_ids")
        if [str(item) for item in blocked_by] != [str(item) for item in open_stack]:
            issues.append(f"{row_id}:blocked_by_open_stack_mismatch")
        if not row.get("blocking_check_keys"):
            issues.append(f"{row_id}:blocking_check_keys")
        if not coverage_impacts:
            issues.append(f"{row_id}:coverage_impacts")
        if not blocked_planes:
            issues.append(f"{row_id}:blocked_coverage_planes")
        if [str(item) for item in coverage_planes] != [
            str(item) for item in blocked_planes
        ]:
            issues.append(f"{row_id}:coverage_planes_alias")
        for blocker in requirements:
            if not isinstance(blocker, dict) or blocker.get("id") not in set(
                open_stack
            ):
                continue
            requirement_id = str(blocker.get("id") or "unknown")
            closure_acceptance = (
                blocker.get("closure_acceptance")
                if isinstance(blocker.get("closure_acceptance"), dict)
                else {}
            )
            if not contract_port.stack_requirement_closure_acceptance_complete(
                closure_acceptance
            ):
                issues.append(f"{row_id}:{requirement_id}:closure_acceptance")
            if (
                closure_acceptance
                and closure_acceptance.get("requirement_id") != requirement_id
            ):
                issues.append(
                    f"{row_id}:{requirement_id}:closure_acceptance_identity"
                )
            if (
                closure_acceptance
                and self_awareness_contracts.nested_get(
                    closure_acceptance, ["stack_compat_requirement", "owner"]
                )
                != "abyss-stack"
            ):
                issues.append(f"{row_id}:{requirement_id}:closure_acceptance_owner")
            if (
                closure_acceptance
                and self_awareness_contracts.nested_get(
                    closure_acceptance, ["policy", "host_layer_mutates_stack"]
                )
                is not False
            ):
                issues.append(f"{row_id}:{requirement_id}:closure_acceptance_policy")
        for impact in coverage_impacts:
            if not isinstance(impact, dict):
                issues.append(f"{row_id}:malformed_coverage_impact")
                continue
            if not impact.get("requirement_id"):
                issues.append(f"{row_id}:impact_requirement_id")
            if (
                not isinstance(impact.get("coverage_planes"), list)
                or not impact.get("coverage_planes")
            ):
                issues.append(f"{row_id}:impact_coverage_planes")
            if (
                self_awareness_contracts.nested_get(
                    impact, ["policy", "host_layer_mutates_stack"]
                )
                is not False
            ):
                issues.append(f"{row_id}:impact_policy")
    summary_planes = self_awareness_contracts.nested_get(
        coverage_audit, ["summary", "blocked_coverage_planes"]
    )
    if blocked_rows and not isinstance(summary_planes, list):
        issues.append("summary:blocked_coverage_planes")
    if blocked_rows and isinstance(summary_planes, list):
        row_planes = sorted(
            {
                str(plane)
                for row in blocked_rows
                for plane in (
                    row.get("blocked_coverage_planes")
                    if isinstance(row.get("blocked_coverage_planes"), list)
                    else []
                )
                if plane
            }
        )
        if sorted(str(plane) for plane in summary_planes) != row_planes:
            issues.append("summary:blocked_coverage_planes_mismatch")
    summary_objective_planes = self_awareness_contracts.nested_get(
        coverage_audit, ["summary", "objective_coverage_planes"]
    )
    row_objective_planes = sorted(
        {
            str(plane)
            for row in rows
            for plane in (
                row.get("objective_coverage_planes")
                if isinstance(row.get("objective_coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    if sorted(
        str(plane)
        for plane in (
            summary_objective_planes
            if isinstance(summary_objective_planes, list)
            else []
        )
    ) != row_objective_planes:
        issues.append("summary:objective_coverage_planes_mismatch")
    summary_covered_planes = self_awareness_contracts.nested_get(
        coverage_audit, ["summary", "covered_coverage_planes"]
    )
    row_covered_planes = sorted(
        {
            str(plane)
            for row in covered_rows
            for plane in (
                row.get("covered_coverage_planes")
                if isinstance(row.get("covered_coverage_planes"), list)
                else []
            )
            if plane
        }
    )
    if sorted(
        str(plane)
        for plane in (
            summary_covered_planes
            if isinstance(summary_covered_planes, list)
            else []
        )
    ) != row_covered_planes:
        issues.append("summary:covered_coverage_planes_mismatch")
    open_requirement_ids = sorted(
        {
            str(requirement_id)
            for row in blocked_rows
            for requirement_id in (
                row.get("open_stack_requirement_ids")
                if isinstance(row.get("open_stack_requirement_ids"), list)
                else []
            )
            if requirement_id
        }
    )
    if blocked_rows and runtime_evidence_contracts.safe_int(
        self_awareness_contracts.nested_get(
            coverage_audit,
            ["summary", "stack_requirement_closure_acceptance_packets_complete"],
        ),
        -1,
    ) < len(open_requirement_ids):
        issues.append("summary:stack_requirement_closure_acceptance_packets_complete")
    return issues
