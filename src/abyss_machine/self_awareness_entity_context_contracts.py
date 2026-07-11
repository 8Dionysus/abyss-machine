from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
import re
from typing import Any, Callable

from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessEntityContextPaths:
    completion_audit_latest: Path
    events_latest: Path


@dataclass(frozen=True)
class SelfAwarenessEntityContextConfig:
    schema_prefix: str


@dataclass(frozen=True)
class SelfAwarenessEntityContextRuntimePort:
    load_latest_json: DocumentPort


nested_get = self_awareness_contracts.nested_get


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def entity_event_document_map_issues(
    mapping: Any,
    *,
    expected_stack_organs: int | None = None,
    expected_machine_bridges: int | None = None,
    config: SelfAwarenessEntityContextConfig,
) -> list[str]:
    SCHEMA_PREFIX = config.schema_prefix
    issues: list[str] = []
    if not isinstance(mapping, dict):
        return ["map_missing"]
    summary = mapping.get("summary") if isinstance(mapping.get("summary"), dict) else {}
    automation = (
        mapping.get("automation") if isinstance(mapping.get("automation"), dict) else {}
    )
    validation_contract = (
        automation.get("validation_contract")
        if isinstance(automation.get("validation_contract"), dict)
        else {}
    )
    policy = mapping.get("policy") if isinstance(mapping.get("policy"), dict) else {}
    entities = (
        mapping.get("entities") if isinstance(mapping.get("entities"), list) else []
    )
    events = mapping.get("events") if isinstance(mapping.get("events"), list) else []
    documents = (
        mapping.get("documents") if isinstance(mapping.get("documents"), list) else []
    )
    stack_organ_entities = (
        mapping.get("stack_organ_entities")
        if isinstance(mapping.get("stack_organ_entities"), list)
        else []
    )
    machine_bridge_entities = (
        mapping.get("machine_bridge_entities")
        if isinstance(mapping.get("machine_bridge_entities"), list)
        else []
    )
    document_ids = {
        str(document.get("document_id"))
        for document in documents
        if isinstance(document, dict) and document.get("document_id")
    }
    if (
        mapping.get("schema")
        != f"{SCHEMA_PREFIX}_self_awareness_entity_event_document_map_v1"
    ):
        issues.append("schema")
    if mapping.get("ok") is not True or summary.get("automation_ready") is not True:
        issues.append("automation_not_ready")
    if (
        policy.get("host_layer_mutates_stack") is not False
        or policy.get("executes_commands") is not False
    ):
        issues.append("policy")
    if (
        automation.get("runs_probe") is not False
        or automation.get("runs_cycle") is not False
        or automation.get("runs_indexing") is not False
    ):
        issues.append("automation_runs_heavy_work")
    if (
        automation.get("runs_stack_http_probes") is not False
        or automation.get("executes_verifiers") is not False
    ):
        issues.append("automation_executes_verifiers_or_stack_probes")
    for key in (
        "every_action_has_entity",
        "every_action_has_event",
        "every_route_action_has_entity",
        "every_entity_has_document_refs",
        "every_entity_has_route",
        "every_stack_organ_has_entity",
        "every_machine_bridge_has_entity",
        "document_refs_resolve",
    ):
        if validation_contract.get(key) is not True:
            issues.append(f"validation_contract:{key}")
    if validation_contract.get("host_layer_mutates_stack") is not False:
        issues.append("validation_contract:host_layer_mutates_stack")
    if safe_int(summary.get("entities"), -1) != len(entities):
        issues.append("entity_count")
    if safe_int(summary.get("events"), -1) != len(events):
        issues.append("event_count")
    if safe_int(summary.get("documents"), -1) != len(documents):
        issues.append("document_count")
    if safe_int(summary.get("stack_organs"), -1) != len(stack_organ_entities):
        issues.append("stack_organ_count")
    if safe_int(summary.get("machine_bridges"), -1) != len(machine_bridge_entities):
        issues.append("machine_bridge_count")
    if safe_int(summary.get("body_surfaces"), -1) != len(stack_organ_entities) + len(
        machine_bridge_entities
    ):
        issues.append("body_surface_count")
    if (
        expected_stack_organs is not None
        and safe_int(summary.get("stack_organs"), -1) != expected_stack_organs
    ):
        issues.append("expected_stack_organ_count")
    if (
        expected_machine_bridges is not None
        and safe_int(summary.get("machine_bridges"), -1) != expected_machine_bridges
    ):
        issues.append("expected_machine_bridge_count")
    for key in (
        "unmapped_actions",
        "unmapped_route_actions",
        "unmapped_stack_organs",
        "unmapped_machine_bridges",
        "unmapped_document_refs",
    ):
        if summary.get(key):
            issues.append(key)
    for document in documents:
        if not isinstance(document, dict):
            issues.append("malformed_document")
            continue
        document_id = str(document.get("document_id") or "unknown")
        if (
            document.get("schema")
            != f"{SCHEMA_PREFIX}_self_awareness_entity_event_document_document_v1"
        ):
            issues.append(f"{document_id}:document_schema")
        if (
            not document.get("document_path")
            or not document.get("path")
            or (not document.get("role"))
        ):
            issues.append(f"{document_id}:document_identity")
        if (
            nested_get(document, ["policy", "host_layer_mutates_stack"]) is not False
            or nested_get(document, ["policy", "executes_commands"]) is not False
        ):
            issues.append(f"{document_id}:document_policy")
    event_ids = {
        str(event.get("event_id"))
        for event in events
        if isinstance(event, dict) and event.get("event_id")
    }
    for entity in entities:
        if not isinstance(entity, dict):
            issues.append("malformed_entity")
            continue
        entity_id = str(entity.get("entity_id") or "unknown")
        entity_document_ids = [
            str(document_id)
            for document_id in (
                entity.get("document_ids")
                if isinstance(entity.get("document_ids"), list)
                else []
            )
        ]
        if (
            entity.get("schema")
            != f"{SCHEMA_PREFIX}_self_awareness_entity_event_document_entity_v1"
        ):
            issues.append(f"{entity_id}:entity_schema")
        if (
            not entity.get("entity_path")
            or not entity.get("entity_kind")
            or (not entity.get("event_id"))
            or (not entity.get("route_path"))
        ):
            issues.append(f"{entity_id}:entity_identity")
        if str(entity.get("event_id")) not in event_ids:
            issues.append(f"{entity_id}:event_ref")
        if not entity_document_ids:
            issues.append(f"{entity_id}:document_refs")
        if not set(entity_document_ids).issubset(document_ids):
            issues.append(f"{entity_id}:document_ref_resolution")
        if (
            nested_get(entity, ["policy", "host_layer_mutates_stack"]) is not False
            or nested_get(entity, ["policy", "executes_commands"]) is not False
        ):
            issues.append(f"{entity_id}:entity_policy")
        if entity.get("entity_kind") == "stack_organ" and (
            entity.get("route_path") != "body/stack-organs"
            or not nested_get(entity, ["subject", "service"])
            or (not nested_get(entity, ["subject", "working_stack_link_id"]))
            or (not entity.get("evidence_refs"))
        ):
            issues.append(f"{entity_id}:stack_organ_depth")
        if entity.get("entity_kind") == "machine_bridge" and (
            entity.get("route_path") != "body/machine-bridges"
            or not nested_get(entity, ["subject", "bridge_id"])
            or (not nested_get(entity, ["artifact", "path"]))
            or (not nested_get(entity, ["artifact", "sha256"]))
            or (not entity.get("evidence_refs"))
        ):
            issues.append(f"{entity_id}:machine_bridge_depth")
    entity_ids = {
        str(entity.get("entity_id"))
        for entity in entities
        if isinstance(entity, dict) and entity.get("entity_id")
    }
    for event in events:
        if not isinstance(event, dict):
            issues.append("malformed_event")
            continue
        event_id = str(event.get("event_id") or "unknown")
        event_document_ids = [
            str(document_id)
            for document_id in (
                event.get("document_ids")
                if isinstance(event.get("document_ids"), list)
                else []
            )
        ]
        if (
            event.get("schema")
            != f"{SCHEMA_PREFIX}_self_awareness_entity_event_document_event_v1"
        ):
            issues.append(f"{event_id}:event_schema")
        if (
            not event.get("event_path")
            or not event.get("event_kind")
            or str(event.get("entity_id") or "") not in entity_ids
        ):
            issues.append(f"{event_id}:event_identity")
        if not event_document_ids or not set(event_document_ids).issubset(document_ids):
            issues.append(f"{event_id}:event_document_refs")
        if (
            nested_get(event, ["policy", "host_layer_mutates_stack"]) is not False
            or nested_get(event, ["policy", "executes_commands"]) is not False
        ):
            issues.append(f"{event_id}:event_policy")
    return sorted(set(issues))


def entity_event_document_map_complete(
    mapping: Any,
    *,
    expected_stack_organs: int | None = None,
    expected_machine_bridges: int | None = None,
    config: SelfAwarenessEntityContextConfig,
) -> bool:
    self_awareness_entity_event_document_map_issues = partial(
        entity_event_document_map_issues, config=config
    )
    return not self_awareness_entity_event_document_map_issues(
        mapping,
        expected_stack_organs=expected_stack_organs,
        expected_machine_bridges=expected_machine_bridges,
    )


def response_entity_event_document_context(
    *,
    completion_audit_doc: dict[str, Any] | None = None,
    episode: dict[str, Any] | None = None,
    source_event: dict[str, Any] | None = None,
    body_trace: dict[str, Any] | None = None,
    paths: SelfAwarenessEntityContextPaths,
    config: SelfAwarenessEntityContextConfig,
    runtime_port: SelfAwarenessEntityContextRuntimePort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH = paths.completion_audit_latest
    SELF_AWARENESS_EVENTS_LATEST_PATH = paths.events_latest
    load_latest_json = runtime_port.load_latest_json
    self_awareness_entity_event_document_map_issues = partial(
        entity_event_document_map_issues, config=config
    )
    completion_audit_doc = (
        completion_audit_doc
        if isinstance(completion_audit_doc, dict)
        else load_latest_json(
            SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH,
            f"{SCHEMA_PREFIX}_self_awareness_completion_audit_v1",
        )
    )
    episode = episode if isinstance(episode, dict) else {}
    source_event = source_event if isinstance(source_event, dict) else {}
    body_trace = body_trace if isinstance(body_trace, dict) else {}
    mapping = (
        completion_audit_doc.get("entity_event_document_map")
        if isinstance(completion_audit_doc.get("entity_event_document_map"), dict)
        else {}
    )
    route_packets = (
        completion_audit_doc.get("completion_route_packets")
        if isinstance(completion_audit_doc.get("completion_route_packets"), dict)
        else {}
    )
    map_issues = self_awareness_entity_event_document_map_issues(mapping)
    entities = (
        mapping.get("entities") if isinstance(mapping.get("entities"), list) else []
    )
    events = mapping.get("events") if isinstance(mapping.get("events"), list) else []
    documents = (
        mapping.get("documents") if isinstance(mapping.get("documents"), list) else []
    )
    route_bindings = (
        mapping.get("routes") if isinstance(mapping.get("routes"), list) else []
    )

    def stable_segment(value: Any) -> str:
        raw = str(value or "unknown").strip()
        compact = re.sub("[^A-Za-z0-9._-]+", "-", raw)
        return compact.strip("-") or "unknown"

    episode_event_ids = {
        str(item)
        for item in (
            episode.get("event_ids")
            if isinstance(episode.get("event_ids"), list)
            else []
        )
        if item
    }
    if source_event.get("event_id"):
        episode_event_ids.add(str(source_event.get("event_id")))
    affected_services = {
        str(item)
        for item in (
            nested_get(body_trace, ["spatial", "affected_services"])
            if isinstance(
                nested_get(body_trace, ["spatial", "affected_services"]), list
            )
            else []
        )
        if item
    }
    affected_services.update(
        (
            str(node).split(":", 1)[1]
            for node in (
                nested_get(body_trace, ["spatial", "affected_spatial_nodes"])
                if isinstance(
                    nested_get(body_trace, ["spatial", "affected_spatial_nodes"]), list
                )
                else []
            )
            if str(node).startswith("service:")
        )
    )
    for candidate_service in (
        nested_get(source_event, ["resource", "service"]),
        nested_get(episode, ["working_stack_gap", "service"]),
        episode.get("service"),
    ):
        if candidate_service:
            affected_services.add(str(candidate_service))
    selected_entity_ids: set[str] = set()
    requirement_id = str(episode.get("requirement_id") or "")
    if requirement_id:
        selected_entity_ids.add(f"stack.requirement.{stable_segment(requirement_id)}")
    for service in affected_services:
        selected_entity_ids.add(f"stack.service.{stable_segment(service)}")
        selected_entity_ids.add(f"stack.organ.{stable_segment(service)}")
    top_route_id = (
        nested_get(route_packets, ["summary", "top_route_id"])
        or nested_get(route_packets, ["top_packet", "route_id"])
        or nested_get(mapping, ["top_entity", "route_id"])
    )
    selected_route_ids = {str(top_route_id)} if top_route_id else set()
    selected_route_ids.update({"body.stack_organs", "body.machine_bridges"})
    selected_entities = [
        entity
        for entity in entities
        if isinstance(entity, dict)
        and (
            str(entity.get("entity_id") or "") in selected_entity_ids
            or str(entity.get("event_id") or "") in episode_event_ids
            or str(entity.get("route_id") or "") in selected_route_ids
            or (
                str(nested_get(entity, ["subject", "service"]) or "")
                in affected_services
            )
        )
    ]
    if not selected_entities and entities:
        selected_entities = [entity for entity in entities if isinstance(entity, dict)][
            :1
        ]
    selected_event_ids = {
        str(entity.get("event_id"))
        for entity in selected_entities
        if entity.get("event_id")
    }
    selected_events = [
        event
        for event in events
        if isinstance(event, dict)
        and (
            str(event.get("event_id") or "") in selected_event_ids
            or str(event.get("event_id") or "") in episode_event_ids
            or str(event.get("route_id") or "") in selected_route_ids
        )
    ]
    selected_document_ids = sorted(
        {
            str(document_id)
            for row in [*selected_entities, *selected_events]
            for document_id in (
                row.get("document_ids")
                if isinstance(row.get("document_ids"), list)
                else []
            )
            if document_id
        }
    )
    selected_documents = [
        document
        for document in documents
        if isinstance(document, dict)
        and str(document.get("document_id") or "") in set(selected_document_ids)
    ]
    selected_route_bindings = [
        row
        for row in route_bindings
        if isinstance(row, dict)
        and (
            str(row.get("route_id") or "") in selected_route_ids
            or bool(
                set(
                    (
                        str(item)
                        for item in (
                            row.get("entity_ids")
                            if isinstance(row.get("entity_ids"), list)
                            else []
                        )
                    )
                )
                & {
                    str(entity.get("entity_id"))
                    for entity in selected_entities
                    if entity.get("entity_id")
                }
            )
        )
    ]
    if not selected_route_bindings:
        selected_route_bindings = [
            row
            for row in route_bindings
            if isinstance(row, dict)
            and str(row.get("route_id") or "")
            in {"body.stack_organs", "body.machine_bridges"}
        ][:2]
    policy = {
        "read_only": True,
        "latest_only_readmodel": True,
        "host_layer_mutates_stack": False,
        "writes_project_roots": False,
        "executes_commands": False,
        "actions_executed": False,
        "automatic_remediation": False,
    }
    complete = bool(
        not map_issues
        and selected_entities
        and selected_events
        and selected_documents
        and selected_route_bindings
        and (nested_get(mapping, ["summary", "automation_ready"]) is True)
        and (nested_get(mapping, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(mapping, ["policy", "executes_commands"]) is False)
    )
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_response_entity_event_document_context_v1",
        "complete": complete,
        "issues": map_issues,
        "episode_id": episode.get("episode_id"),
        "episode_kind": episode.get("episode_kind")
        or nested_get(body_trace, ["episode_kind"]),
        "top_route_id": top_route_id,
        "summary": {
            "map_entities": nested_get(mapping, ["summary", "entities"]),
            "map_events": nested_get(mapping, ["summary", "events"]),
            "map_documents": nested_get(mapping, ["summary", "documents"]),
            "map_body_surfaces": nested_get(mapping, ["summary", "body_surfaces"]),
            "selected_entities": len(selected_entities),
            "selected_events": len(selected_events),
            "selected_documents": len(selected_documents),
            "selected_route_bindings": len(selected_route_bindings),
            "automation_ready": nested_get(mapping, ["summary", "automation_ready"]),
        },
        "entity_ids": [
            str(entity.get("entity_id"))
            for entity in selected_entities
            if entity.get("entity_id")
        ],
        "event_ids": [
            str(event.get("event_id"))
            for event in selected_events
            if event.get("event_id")
        ],
        "document_ids": selected_document_ids,
        "route_ids": [
            str(row.get("route_id"))
            for row in selected_route_bindings
            if row.get("route_id")
        ],
        "top_entity": mapping.get("top_entity")
        if isinstance(mapping.get("top_entity"), dict)
        else {},
        "top_event": mapping.get("top_event")
        if isinstance(mapping.get("top_event"), dict)
        else {},
        "selected_entities": selected_entities[:12],
        "selected_events": selected_events[:12],
        "selected_documents": selected_documents[:16],
        "selected_route_bindings": selected_route_bindings[:12],
        "automation": {
            "mode": "latest_only_readmodel",
            "runs_probe": False,
            "runs_cycle": False,
            "runs_indexing": False,
            "runs_stack_http_probes": False,
            "executes_verifiers": False,
            "validation_source": "entity_event_document_map",
        },
        "policy": policy,
        "evidence_refs": [
            {
                "path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH),
                "section": "entity_event_document_map",
            },
            {
                "path": str(SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH),
                "section": "completion_route_packets",
            },
            {
                "path": str(SELF_AWARENESS_EVENTS_LATEST_PATH),
                "event_ids": sorted(episode_event_ids),
            },
        ],
    }
    return data


def response_entity_event_document_context_complete(
    context: Any, *, config: SelfAwarenessEntityContextConfig
) -> bool:
    SCHEMA_PREFIX = config.schema_prefix
    if not isinstance(context, dict):
        return False
    return (
        context.get("schema")
        == f"{SCHEMA_PREFIX}_self_awareness_response_entity_event_document_context_v1"
        and context.get("complete") is True
        and (not context.get("issues"))
        and (safe_int(nested_get(context, ["summary", "selected_entities"]), 0) > 0)
        and (safe_int(nested_get(context, ["summary", "selected_events"]), 0) > 0)
        and (safe_int(nested_get(context, ["summary", "selected_documents"]), 0) > 0)
        and (
            safe_int(nested_get(context, ["summary", "selected_route_bindings"]), 0) > 0
        )
        and (nested_get(context, ["summary", "automation_ready"]) is True)
        and bool(context.get("entity_ids"))
        and bool(context.get("event_ids"))
        and bool(context.get("document_ids"))
        and bool(context.get("route_ids"))
        and (nested_get(context, ["automation", "runs_probe"]) is False)
        and (nested_get(context, ["automation", "runs_cycle"]) is False)
        and (nested_get(context, ["automation", "runs_indexing"]) is False)
        and (nested_get(context, ["automation", "runs_stack_http_probes"]) is False)
        and (nested_get(context, ["automation", "executes_verifiers"]) is False)
        and (nested_get(context, ["policy", "host_layer_mutates_stack"]) is False)
        and (nested_get(context, ["policy", "writes_project_roots"]) is False)
        and (nested_get(context, ["policy", "executes_commands"]) is False)
        and bool(context.get("evidence_refs"))
    )


def completion_route_packet_issues(
    packet_index: Any,
    *,
    expected_routes: int | None = None,
    expected_actions: int | None = None,
    config: SelfAwarenessEntityContextConfig,
) -> list[str]:
    SCHEMA_PREFIX = config.schema_prefix
    issues: list[str] = []
    if not isinstance(packet_index, dict):
        return ["packet_index_missing"]
    summary = (
        packet_index.get("summary")
        if isinstance(packet_index.get("summary"), dict)
        else {}
    )
    automation = (
        packet_index.get("automation")
        if isinstance(packet_index.get("automation"), dict)
        else {}
    )
    validation_contract = (
        automation.get("validation_contract")
        if isinstance(automation.get("validation_contract"), dict)
        else {}
    )
    policy = (
        packet_index.get("policy")
        if isinstance(packet_index.get("policy"), dict)
        else {}
    )
    packets = (
        packet_index.get("packets")
        if isinstance(packet_index.get("packets"), list)
        else []
    )
    if (
        packet_index.get("schema")
        != f"{SCHEMA_PREFIX}_self_awareness_completion_route_packet_index_v1"
    ):
        issues.append("schema")
    if (
        packet_index.get("ok") is not True
        or summary.get("automation_ready") is not True
    ):
        issues.append("automation_not_ready")
    if (
        policy.get("host_layer_mutates_stack") is not False
        or policy.get("executes_commands") is not False
    ):
        issues.append("policy")
    if (
        automation.get("runs_probe") is not False
        or automation.get("runs_cycle") is not False
        or automation.get("runs_indexing") is not False
    ):
        issues.append("automation_runs_heavy_work")
    if (
        automation.get("runs_stack_http_probes") is not False
        or automation.get("executes_verifiers") is not False
    ):
        issues.append("automation_executes_verifiers_or_stack_probes")
    for key in (
        "every_completion_route_has_packet",
        "every_completion_action_has_route_packet",
        "every_packet_has_entities_events_documents",
    ):
        if validation_contract.get(key) is not True:
            issues.append(f"validation_contract:{key}")
    if validation_contract.get("host_layer_mutates_stack") is not False:
        issues.append("validation_contract:host_layer_mutates_stack")
    if safe_int(summary.get("packets"), -1) != len(packets):
        issues.append("packet_count")
    if safe_int(summary.get("packets_complete"), -1) != sum(
        (
            1
            for packet in packets
            if isinstance(packet, dict) and packet.get("complete") is True
        )
    ):
        issues.append("packet_complete_count")
    if (
        expected_routes is not None
        and safe_int(summary.get("routes"), -1) != expected_routes
    ):
        issues.append("expected_route_count")
    if (
        expected_actions is not None
        and safe_int(summary.get("actions"), -1) != expected_actions
    ):
        issues.append("expected_action_count")
    if summary.get("unmapped_actions"):
        issues.append("unmapped_actions")
    if summary.get("unmapped_routes"):
        issues.append("unmapped_routes")
    packet_by_route = (
        packet_index.get("packet_by_route")
        if isinstance(packet_index.get("packet_by_route"), dict)
        else {}
    )
    packet_route_ids = {
        str(packet.get("route_id"))
        for packet in packets
        if isinstance(packet, dict) and packet.get("route_id")
    }
    if set((str(route_id) for route_id in packet_by_route)) != packet_route_ids:
        issues.append("packet_by_route")
    for packet in packets:
        if not isinstance(packet, dict):
            issues.append("malformed_packet")
            continue
        packet_id = str(packet.get("packet_id") or packet.get("route_id") or "unknown")
        action_ids = (
            packet.get("action_ids")
            if isinstance(packet.get("action_ids"), list)
            else []
        )
        actions = (
            packet.get("actions") if isinstance(packet.get("actions"), list) else []
        )
        entity_ids = (
            packet.get("entity_ids")
            if isinstance(packet.get("entity_ids"), list)
            else []
        )
        event_ids = (
            packet.get("event_ids") if isinstance(packet.get("event_ids"), list) else []
        )
        document_ids = (
            packet.get("document_ids")
            if isinstance(packet.get("document_ids"), list)
            else []
        )
        document_refs = (
            packet.get("document_refs")
            if isinstance(packet.get("document_refs"), list)
            else []
        )
        verifier_commands = (
            packet.get("verifier_commands")
            if isinstance(packet.get("verifier_commands"), list)
            else []
        )
        if (
            packet.get("schema")
            != f"{SCHEMA_PREFIX}_self_awareness_completion_route_packet_v1"
        ):
            issues.append(f"{packet_id}:schema")
        if packet.get("complete") is not True:
            issues.append(f"{packet_id}:incomplete")
        if (
            not packet.get("route_id")
            or not packet.get("route_path")
            or (not action_ids)
        ):
            issues.append(f"{packet_id}:identity")
        if len(actions) != len(action_ids):
            issues.append(f"{packet_id}:action_count")
        if len(entity_ids) != len(action_ids) or len(event_ids) != len(action_ids):
            issues.append(f"{packet_id}:entity_event_count")
        if not document_ids or not document_refs:
            issues.append(f"{packet_id}:documents")
        if not verifier_commands:
            issues.append(f"{packet_id}:verifier_commands")
        if not packet.get("evidence_refs"):
            issues.append(f"{packet_id}:evidence_refs")
        if (
            nested_get(packet, ["automation", "runs_probe"]) is not False
            or nested_get(packet, ["automation", "runs_cycle"]) is not False
            or nested_get(packet, ["automation", "runs_indexing"]) is not False
        ):
            issues.append(f"{packet_id}:automation_runs_heavy_work")
        if (
            nested_get(packet, ["automation", "runs_stack_http_probes"]) is not False
            or nested_get(packet, ["automation", "executes_verifiers"]) is not False
        ):
            issues.append(f"{packet_id}:automation_executes_verifiers_or_stack_probes")
        if (
            nested_get(packet, ["policy", "host_layer_mutates_stack"]) is not False
            or nested_get(packet, ["policy", "executes_commands"]) is not False
        ):
            issues.append(f"{packet_id}:policy")
        for action in actions:
            if not isinstance(action, dict):
                issues.append(f"{packet_id}:malformed_action")
                continue
            action_id = str(action.get("id") or "unknown")
            if (
                nested_get(action, ["policy", "host_layer_mutates_stack"]) is not False
                or nested_get(action, ["policy", "executes_commands"]) is not False
            ):
                issues.append(f"{packet_id}:{action_id}:action_policy")
    return sorted(set(issues))


def completion_route_packet_index_complete(
    packet_index: Any,
    *,
    expected_routes: int | None = None,
    expected_actions: int | None = None,
    config: SelfAwarenessEntityContextConfig,
) -> bool:
    self_awareness_completion_route_packet_issues = partial(
        completion_route_packet_issues, config=config
    )
    return not self_awareness_completion_route_packet_issues(
        packet_index, expected_routes=expected_routes, expected_actions=expected_actions
    )
