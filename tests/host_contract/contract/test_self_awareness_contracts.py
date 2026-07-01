from __future__ import annotations

import inspect
import json
from pathlib import Path
import wave

import pytest

from conftest import parse_json_stdout


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def _body_trace_fixture(episode_id: str = "episode-fixture") -> dict:
    return {
        "schema": "abyss_machine_self_awareness_body_trace_v1",
        "trace_id": "sabody-fixture",
        "episode_id": episode_id,
        "episode_kind": "event_correlation",
        "temporal": {
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-01T00:01:00+00:00",
            "bucket": "2026-01-01T00:00:00Z",
        },
        "spatial": {
            "affected_spatial_nodes": ["service:route-api"],
            "affected_services": ["route-api"],
            "node_count": 1,
            "service_count": 1,
            "owner_surfaces": ["abyss-machine"],
        },
        "contextual": {
            "context_keys": ["service:route-api", "source:synthetic"],
            "context_key_count": 2,
            "involved_context_count": 1,
            "event_ids": ["event-1"],
        },
        "host_body": {
            "schema": "abyss_machine_self_awareness_host_body_context_packet_v1",
            "complete": True,
            "scheduler_unit_contexts": 1,
            "scheduler_categories": ["warm_e2b"],
            "host_service_unit_contexts": 1,
            "host_service_categories": ["typing"],
            "manual_collect_contexts": 1,
        },
        "lineage": {
            "episode_latest": "/var/lib/abyss-machine/self-awareness/episodes/latest.json",
            "context_latest": "/var/lib/abyss-machine/self-awareness/context/latest.json",
            "timeline_latest": "/var/lib/abyss-machine/self-awareness/timeline/latest.json",
            "spatial_graph_latest": "/var/lib/abyss-machine/self-awareness/spatial-graph/latest.json",
        },
        "complete": True,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
            "stores_raw_body": False,
            "stores_raw_context_values": False,
            "raw_private_content": False,
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/context/latest.json"}],
    }


def _context_doc_fixture() -> dict:
    return {
        "schema": "abyss_machine_self_awareness_context_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "memory_space": {"summary": {"blocked_gates": 0, "retrieval_packets": 1}},
        "context_packet": {
            "schema": "abyss_machine_self_awareness_bounded_context_packet_v1",
            "complete": True,
            "sections": {
                "host_body": {
                    "schema": "abyss_machine_self_awareness_host_body_context_packet_v1",
                    "complete": True,
                    "scheduler": {"unit_contexts": 1, "categories": ["warm_e2b"]},
                    "host_services": {"unit_contexts": 1, "categories": ["typing"]},
                    "manual_collect": {"contexts": 1},
                    "policy": {"host_layer_mutates_stack": False},
                    "bounds": {"stores_raw_body": False, "stores_raw_context_values": False},
                }
            },
        },
    }


def _completion_audit_doc_fixture() -> dict:
    entity_document_refs = [
        {
            "schema": "abyss_machine_self_awareness_entity_event_document_document_v1",
            "document_id": "self-awareness.requirements.latest",
            "document_path": "self-awareness/requirements/latest",
            "role": "stack_requirement_handoff",
            "path": "/var/lib/abyss-machine/self-awareness/requirements/latest.json",
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "stack-owned requirement source and acceptance shape",
            "policy": {"read_only_stack_consumer": True, "host_layer_mutates_stack": False, "writes_project_roots": False, "executes_commands": False},
        },
        {
            "schema": "abyss_machine_self_awareness_entity_event_document_document_v1",
            "document_id": "self-awareness.requirement-probes.latest",
            "document_path": "self-awareness/requirement-probes/latest",
            "role": "stack_requirement_probe",
            "path": "/var/lib/abyss-machine/self-awareness/requirement-probes/latest.json",
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "bounded read-only probe over stack-owned acceptance contract",
            "policy": {"read_only_stack_consumer": True, "host_layer_mutates_stack": False, "writes_project_roots": False, "executes_commands": False},
        },
        {
            "schema": "abyss_machine_self_awareness_entity_event_document_document_v1",
            "document_id": "self-awareness.stack-closure-dossier.latest",
            "document_path": "self-awareness/stack-closure-dossier/latest",
            "role": "stack_owner_closure_packet",
            "path": "/var/lib/abyss-machine/self-awareness/stack-closure-dossier/latest.json",
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "ordered handoff packet and closure acceptance contract",
            "policy": {"read_only_stack_consumer": True, "host_layer_mutates_stack": False, "writes_project_roots": False, "executes_commands": False},
        },
        {
            "schema": "abyss_machine_self_awareness_entity_event_document_document_v1",
            "document_id": "self-awareness.working-stack.latest",
            "document_path": "self-awareness/working-stack/latest",
            "role": "working_stack_body_inventory",
            "path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json",
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "actual running/deployed stack body and usage gaps",
            "policy": {"read_only_stack_consumer": True, "host_layer_mutates_stack": False, "writes_project_roots": False, "executes_commands": False},
        },
        {
            "schema": "abyss_machine_self_awareness_entity_event_document_document_v1",
            "document_id": "self-awareness.autolink.latest",
            "document_path": "self-awareness/autolink/latest",
            "role": "automatic_time_space_context_links",
            "path": "/var/lib/abyss-machine/self-awareness/autolink/latest.json",
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "automatic temporal, spatial, contextual, and state-delta links",
            "policy": {"read_only_stack_consumer": True, "host_layer_mutates_stack": False, "writes_project_roots": False, "executes_commands": False},
        },
        {
            "schema": "abyss_machine_self_awareness_entity_event_document_document_v1",
            "document_id": "self-awareness.completion-audit.latest",
            "document_path": "self-awareness/completion-audit/latest",
            "role": "completion_gate",
            "path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json",
            "owner_route": "abyss-machine",
            "source_kind": "latest_readmodel",
            "truth_level": "stack-usage-closure gate and entity-event-document map container",
            "policy": {"read_only_stack_consumer": True, "host_layer_mutates_stack": False, "writes_project_roots": False, "executes_commands": False},
        },
    ]
    requirement_entity = {
        "schema": "abyss_machine_self_awareness_entity_event_document_entity_v1",
        "entity_id": "stack.requirement.stack.trace-backend",
        "entity_path": "stack/requirement/stack.trace-backend",
        "entity_kind": "stack_requirement",
        "status": "open",
        "owner_route": "abyss-stack",
        "action_id": "stack-requirement:stack.trace-backend",
        "event_id": "completion.open.trace",
        "route_id": "observability.trace_join_backbone",
        "route_path": "observability/trace/join-backbone",
        "subject": {"requirement_id": "stack.trace-backend"},
        "document_ids": ["self-awareness.requirements.latest", "self-awareness.requirement-probes.latest", "self-awareness.stack-closure-dossier.latest", "self-awareness.completion-audit.latest"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json"}],
        "policy": {"handoff_only": True, "requires_human_approval": True, "read_only": True, "executes_commands": False, "host_layer_mutates_stack": False, "writes_project_roots": False, "automatic_remediation": False, "actions_executed": False},
    }
    organ_entity = {
        "schema": "abyss_machine_self_awareness_entity_event_document_entity_v1",
        "entity_id": "stack.organ.route-api",
        "entity_path": "stack/organ/route-api",
        "entity_kind": "stack_organ",
        "status": "active",
        "owner_route": "abyss-stack",
        "event_id": "body.stack_organ.route-api",
        "route_id": "body.stack_organs",
        "route_path": "body/stack-organs",
        "subject": {"service": "route-api", "working_stack_link_id": "saworklink-fixture"},
        "document_ids": ["self-awareness.working-stack.latest", "self-awareness.autolink.latest", "self-awareness.completion-audit.latest"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": "route-api"}],
        "policy": {"handoff_only": False, "requires_human_approval": False, "read_only": True, "executes_commands": False, "host_layer_mutates_stack": False, "writes_project_roots": False, "automatic_remediation": False, "actions_executed": False, "raw_evidence_is_not_truth": True},
    }
    requirement_event = {
        "schema": "abyss_machine_self_awareness_entity_event_document_event_v1",
        "event_id": "completion.open.trace",
        "event_path": "completion/open/stack-requirement/stack.trace-backend",
        "event_kind": "stack_requirement_open",
        "source": "completion-audit",
        "action_id": "stack-requirement:stack.trace-backend",
        "entity_id": "stack.requirement.stack.trace-backend",
        "route_id": "observability.trace_join_backbone",
        "route_path": "observability/trace/join-backbone",
        "document_ids": requirement_entity["document_ids"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json"}],
        "observed_at": "2026-01-01T00:00:00+00:00",
        "truth_level": "latest_readmodel_open_state",
        "policy": {"handoff_only": True, "read_only": True, "executes_commands": False, "host_layer_mutates_stack": False, "writes_project_roots": False, "automatic_remediation": False, "actions_executed": False},
    }
    organ_event = {
        "schema": "abyss_machine_self_awareness_entity_event_document_event_v1",
        "event_id": "body.stack_organ.route-api",
        "event_path": "body/stack-organ/route-api/active",
        "event_kind": "stack_organ_linked",
        "source": "working-stack",
        "entity_id": "stack.organ.route-api",
        "route_id": "body.stack_organs",
        "route_path": "body/stack-organs",
        "document_ids": organ_entity["document_ids"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": "route-api"}],
        "observed_at": "2026-01-01T00:00:00+00:00",
        "truth_level": "latest_readmodel_body_state",
        "policy": {"handoff_only": False, "read_only": True, "executes_commands": False, "host_layer_mutates_stack": False, "writes_project_roots": False, "automatic_remediation": False, "actions_executed": False},
    }
    entity_event_document_map = {
        "schema": "abyss_machine_self_awareness_entity_event_document_map_v1",
        "ok": True,
        "summary": {
            "actions": 1,
            "entities": 2,
            "events": 2,
            "documents": len(entity_document_refs),
            "routes": 2,
            "completion_action_entities": 1,
            "stack_organs": 1,
            "machine_bridges": 0,
            "body_surfaces": 1,
            "working_stack_organs": 1,
            "working_stack_organs_with_entities": 1,
            "machine_bridge_rows": 0,
            "machine_bridge_rows_with_entities": 0,
            "actions_with_entities": 1,
            "actions_with_events": 1,
            "route_actions_mapped": 1,
            "unmapped_actions": [],
            "unmapped_route_actions": [],
            "unmapped_stack_organs": [],
            "unmapped_machine_bridges": [],
            "unmapped_document_refs": [],
            "top_entity_id": "stack.requirement.stack.trace-backend",
            "top_entity_path": "stack/requirement/stack.trace-backend",
            "top_event_id": "completion.open.trace",
            "top_event_path": "completion/open/stack-requirement/stack.trace-backend",
            "automation_ready": True,
            "owner_boundary_readonly": True,
        },
        "top_entity": requirement_entity,
        "top_event": requirement_event,
        "documents": entity_document_refs,
        "entities": [requirement_entity, organ_entity],
        "events": [requirement_event, organ_event],
        "stack_organ_entities": [organ_entity],
        "machine_bridge_entities": [],
        "routes": [
            {
                "schema": "abyss_machine_self_awareness_entity_event_document_route_binding_v1",
                "route_id": "observability.trace_join_backbone",
                "route_path": "observability/trace/join-backbone",
                "action_ids": ["stack-requirement:stack.trace-backend"],
                "entity_ids": ["stack.requirement.stack.trace-backend"],
                "event_ids": ["completion.open.trace"],
                "document_ids": requirement_entity["document_ids"],
            },
            {
                "schema": "abyss_machine_self_awareness_entity_event_document_route_binding_v1",
                "route_id": "body.stack_organs",
                "route_path": "body/stack-organs",
                "action_ids": [],
                "entity_ids": ["stack.organ.route-api"],
                "event_ids": ["body.stack_organ.route-api"],
                "document_ids": organ_entity["document_ids"],
            },
        ],
        "automation": {
            "mode": "latest_only_readmodel",
            "generated_from_latest_only": True,
            "runs_probe": False,
            "runs_cycle": False,
            "runs_indexing": False,
            "runs_stack_http_probes": False,
            "executes_verifiers": False,
            "validation_contract": {
                "every_action_has_entity": True,
                "every_action_has_event": True,
                "every_route_action_has_entity": True,
                "every_entity_has_document_refs": True,
                "every_entity_has_route": True,
                "every_stack_organ_has_entity": True,
                "every_machine_bridge_has_entity": True,
                "document_refs_resolve": True,
                "host_layer_mutates_stack": False,
            },
        },
        "policy": {"handoff_only": True, "read_only_stack_consumer": True, "requires_human_approval": True, "executes_commands": False, "host_layer_mutates_stack": False, "writes_project_roots": False, "automatic_remediation": False, "actions_executed": False},
    }
    packet = {
        "schema": "abyss_machine_self_awareness_completion_route_packet_v1",
        "packet_id": "sacompletionroute-fixture",
        "route_id": "observability.trace_join_backbone",
        "route_path": "observability/trace/join-backbone",
        "status": "blocked_by_stack_owner",
        "action_ids": ["stack-requirement:stack.trace-backend"],
        "actions": [
            {
                "id": "stack-requirement:stack.trace-backend",
                "category": "stack_requirement",
                "owner_route": "abyss-stack",
                "priority_rank": 1,
                "priority_class": "critical_trace_join",
                "requirement_id": "stack.trace-backend",
                "closure_blocker_keys": ["trace_backend_ready"],
                "missing_checks": [{"key": "trace_backend_ready"}],
                "safe_next_action": {"requires_human_approval": True, "executes_commands": False, "host_layer_mutates_stack": False},
                "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
            }
        ],
        "drilldown_ids": ["sacompletiondrill-fixture"],
        "entity_ids": ["stack.requirement.stack.trace-backend"],
        "event_ids": ["completion.open.trace"],
        "document_ids": [
            "self-awareness.requirements.latest",
            "self-awareness.requirement-probes.latest",
            "self-awareness.stack-closure-dossier.latest",
        ],
        "document_refs": [
            {"document_id": "self-awareness.requirements.latest", "path": "/var/lib/abyss-machine/self-awareness/requirements/latest.json", "role": "stack_requirement_handoff"},
            {"document_id": "self-awareness.requirement-probes.latest", "path": "/var/lib/abyss-machine/self-awareness/requirement-probes/latest.json", "role": "stack_requirement_probe"},
            {"document_id": "self-awareness.stack-closure-dossier.latest", "path": "/var/lib/abyss-machine/self-awareness/stack-closure-dossier/latest.json", "role": "stack_owner_closure_packet"},
        ],
        "coverage_planes": ["signal_fabric", "spatial_graph", "causal_timeline", "langgraph_replay"],
        "closure_blocker_keys": ["trace_backend_ready"],
        "unblocks_requirement_ids": ["stack.langchain-api.graph-observability"],
        "safe_next_actions": [{"requires_human_approval": True, "executes_commands": False, "host_layer_mutates_stack": False}],
        "verifier_commands": ["abyss-machine self-awareness validate --json"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json", "section": "completion_route_packets.observability.trace_join_backbone"}],
        "automation": {"runs_probe": False, "runs_cycle": False, "runs_indexing": False, "runs_stack_http_probes": False, "executes_verifiers": False},
        "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
        "complete": True,
    }
    return {
        "schema": "abyss_machine_self_awareness_completion_audit_v1",
        "completion_route_map": {"summary": {"routes": 1}},
        "action_backlog": {"summary": {"actions": 1}},
        "completion_route_packets": {
            "schema": "abyss_machine_self_awareness_completion_route_packet_index_v1",
            "ok": True,
            "summary": {
                "routes": 1,
                "packets": 1,
                "packets_complete": 1,
                "actions": 1,
                "covered_actions": 1,
                "unmapped_actions": [],
                "unmapped_routes": [],
                "top_packet_id": "sacompletionroute-fixture",
                "top_route_id": "observability.trace_join_backbone",
                "top_route_path": "observability/trace/join-backbone",
                "automation_ready": True,
            },
            "top_packet": packet,
            "packets": [packet],
            "packet_by_route": {"observability.trace_join_backbone": packet},
            "automation": {
                "runs_probe": False,
                "runs_cycle": False,
                "runs_indexing": False,
                "runs_stack_http_probes": False,
                "executes_verifiers": False,
                "validation_contract": {
                    "every_completion_route_has_packet": True,
                    "every_completion_action_has_route_packet": True,
                    "every_packet_has_entities_events_documents": True,
                    "host_layer_mutates_stack": False,
                },
            },
            "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
        },
        "entity_event_document_map": entity_event_document_map,
    }


def _completion_route_context_fixture(abyss_machine_module) -> dict:
    return abyss_machine_module.self_awareness_resident_completion_route_context(_completion_audit_doc_fixture())


def _resident_cognitive_replay_fixture() -> dict:
    body_trace = _body_trace_fixture()
    completion_route_context = {
        "schema": "abyss_machine_self_awareness_resident_completion_route_context_v1",
        "complete": True,
        "issues": [],
        "summary": {"routes": 1, "packets": 1, "covered_actions": 1, "automation_ready": True},
        "top_packet": {
            "packet_id": "sacompletionroute-fixture",
            "route_id": "observability.trace_join_backbone",
            "route_path": "observability/trace/join-backbone",
            "action_ids": ["stack-requirement:stack.trace-backend"],
            "entity_ids": ["stack.requirement.stack.trace-backend"],
            "event_ids": ["completion.open.trace"],
            "document_ids": ["self-awareness.requirements.latest"],
            "verifier_commands": ["abyss-machine self-awareness validate --json"],
            "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json"}],
            "complete": True,
            "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
        },
        "ordered_packets": [
            {
                "packet_id": "sacompletionroute-fixture",
                "route_id": "observability.trace_join_backbone",
                "route_path": "observability/trace/join-backbone",
                "action_ids": ["stack-requirement:stack.trace-backend"],
                "entity_ids": ["stack.requirement.stack.trace-backend"],
                "event_ids": ["completion.open.trace"],
                "document_ids": ["self-awareness.requirements.latest"],
                "verifier_commands": ["abyss-machine self-awareness validate --json"],
                "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json"}],
                "complete": True,
                "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
            }
        ],
        "automation": {"runs_probe": False, "runs_cycle": False, "runs_indexing": False, "runs_stack_http_probes": False, "executes_verifiers": False},
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "action_execution": False},
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/completion-audit/latest.json"}],
    }
    return {
        "schema": "abyss_machine_self_awareness_resident_cognitive_replay_v1",
        "worker": "warm-e2b/gemma4.spark",
        "complete": True,
        "thread_id": "thread-fixture",
        "selected_episode_id": "episode-fixture",
        "body_trace": body_trace,
        "packet_digest": "a" * 24,
        "checkpoint_packet_digest": "a" * 24,
        "state_preservation": {
            "investigation_top_level": True,
            "resident_context_packet": True,
            "reason_over_evidence": True,
            "write_semantic_conclusion": True,
            "body_trace": True,
            "completion_route_context": True,
        },
        "read_only_tool_kinds": [
            "logql_read",
            "nervous_brief",
            "promql_read",
            "rag_validate",
            "requirements_handoff",
            "resource_mode_gate",
            "self_awareness_context",
            "self_awareness_spatial_graph",
            "completion_route_packets",
        ],
        "summary": {
            "read_only_tools": 9,
            "hypothesis_tests": 3,
            "reason_hypotheses": 4,
            "contradiction_notes": 1,
            "reason_contradiction_notes": 1,
            "body_trace_complete": True,
            "completion_route_context_complete": True,
            "completion_route_packets": 1,
            "completion_route_packet_actions": 1,
            "top_completion_route_id": "observability.trace_join_backbone",
            "top_completion_route_path": "observability/trace/join-backbone",
            "evidence_refs": 1,
            "escalation_status": "blocked_by_preflight",
        },
        "completion_route_context": completion_route_context,
        "evidence_cited_summary": {"evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/investigate/latest.json"}]},
        "escalation_gate": {"host_layer_mutates_stack": False, "action_execution": False},
        "policy": {
            "read_only": True,
            "model_execution_in_this_graph": False,
            "direct_model_prompt_executed": False,
            "read_only_tools_only": True,
            "action_execution": False,
            "auto_remediation": False,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "human_approval_before_mutation": True,
            "candidate_output_is_owner_truth": False,
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/investigate/latest.json"}],
    }


def test_process_game_signal_matcher_bounds_long_cmdline_and_keeps_tail_signal(abyss_machine_module) -> None:
    long_prefix = "x" * (abyss_machine_module.PROCESS_REGEX_MATCH_HEAD_CHARS + 8192)
    cmdline = f"{long_prefix} {Path.home() / '.steam/steamapps/common/Example/Example.exe'}"

    assert abyss_machine_module.process_has_strong_game_signal(cmdline) is True
    assert abyss_machine_module.process_game_role(cmdline, "Example.exe") == "active_game"
    assert len(abyss_machine_module.PROCESS_REGEX_CACHE) <= (
        len(abyss_machine_module.GAME_STRONG_ACTIVE_PATTERNS)
        + len(abyss_machine_module.GAME_WINE_RUNTIME_PATTERNS)
    )


def test_nervous_bounded_index_validation_uses_status_without_full_scan(abyss_machine_module) -> None:
    payload = abyss_machine_module.nervous_index_bounded_validate_from_status(
        {
            "ok": True,
            "ready": True,
            "warnings": ["index stale: fixture"],
            "paths": {"db": "/srv/abyss-machine/nervous/indexes/sqlite/nervous.db"},
            "counts": {"documents": 3, "chunks": 9, "fts_chunks": 9},
            "freshness": {"stale": True, "lag_sec": 120},
        }
    )

    assert payload["schema"] == "abyss_machine_nervous_index_validate_bounded_v1"
    assert payload["ok"] is True
    assert payload["summary"]["bounded"] is True
    assert payload["summary"]["full_scan"] is False
    assert payload["summary"]["warnings"] == 2
    assert payload["summary"]["documents"] == 3
    assert payload["policy"]["full_index_scan"] is False
    assert {check["key"] for check in payload["checks"]} == {
        "index_ready",
        "index_status",
        "freshness",
        "index_status_warnings",
    }


def test_user_systemd_unit_caches_repeated_unit_lookups(monkeypatch, abyss_machine_module) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(cmd: list[str], **_: object) -> dict:
        calls.append(tuple(cmd))
        return {"stdout": "active" if "is-active" in cmd else "enabled"}

    monkeypatch.setattr(abyss_machine_module, "run", fake_run)
    abyss_machine_module.USER_SYSTEMD_UNIT_CACHE.clear()

    first = abyss_machine_module.user_systemd_unit("abyss-fixture.service")
    first["active"] = "mutated-copy"
    second = abyss_machine_module.user_systemd_unit("abyss-fixture.service")

    assert second["active"] == "active"
    assert second["enabled"] == "enabled"
    assert calls == [
        ("systemctl", "--user", "is-active", "abyss-fixture.service"),
        ("systemctl", "--user", "is-enabled", "abyss-fixture.service"),
    ]


def test_self_awareness_scheduler_timer_events_link_temporal_body(monkeypatch, abyss_machine_module) -> None:
    def fake_run(cmd: list[str], **_: object) -> dict:
        if "list-timers" in cmd:
            if "--user" not in cmd:
                return {"ok": True, "stdout": "NEXT LEFT LAST PASSED UNIT ACTIVATES\n", "stderr": "", "returncode": 0}
            return {
                "ok": True,
                "stdout": (
                    "NEXT LEFT LAST PASSED UNIT ACTIVATES\n"
                    "Sat 2026-01-01 00:15:00 UTC 15min - - abyss-machine-heartbeat.timer abyss-machine-heartbeat.service\n"
                    "Sat 2026-01-01 00:16:00 UTC 16min - - abyss-extra-temporal.timer abyss-extra-temporal.service\n"
                ),
                "stderr": "",
                "returncode": 0,
            }
        if "is-active" in cmd:
            return {"ok": True, "stdout": "active", "stderr": "", "returncode": 0}
        if "is-enabled" in cmd:
            return {"ok": True, "stdout": "enabled", "stderr": "", "returncode": 0}
        if "show" in cmd:
            unit = cmd[cmd.index("show") + 1]
            return {
                "ok": True,
                "stdout": "\n".join(
                    [
                        "LoadState=loaded",
                        "ActiveState=active",
                        "SubState=waiting",
                        "UnitFileState=enabled",
                        f"FragmentPath={Path.home() / '.config/systemd/user' / unit}",
                        f"Triggers={unit.removesuffix('.timer')}.service",
                        "LastTriggerUSec=Thu 2026-01-01 00:00:00 UTC",
                        "NextElapseUSecMonotonic=15min",
                        "Result=success",
                        "NeedDaemonReload=no",
                    ]
                ),
                "stderr": "",
                "returncode": 0,
            }
        return {"ok": False, "stdout": "", "stderr": "unexpected command", "returncode": 1}

    monkeypatch.setattr(abyss_machine_module, "run", fake_run)
    abyss_machine_module.USER_SYSTEMD_UNIT_CACHE.clear()
    abyss_machine_module.SYSTEMD_UNIT_CACHE.clear()

    events = abyss_machine_module.self_awareness_scheduler_timer_events("2026-01-01T00:00:00+00:00")
    by_unit = {event["resource"]["service"]: event for event in events}

    assert "abyss-machine-heartbeat.timer" in by_unit
    assert "abyss-extra-temporal.timer" in by_unit
    heartbeat = by_unit["abyss-machine-heartbeat.timer"]
    discovered = by_unit["abyss-extra-temporal.timer"]
    assert heartbeat["signal"] == "service"
    assert heartbeat["source"] == "scheduler"
    assert heartbeat["context"]["scheduler_unit"] == "abyss-machine-heartbeat.timer"
    assert heartbeat["fabric"]["spatial"]["layer"] == "host-scheduler"
    assert heartbeat["fabric"]["policy"]["host_layer_mutates_stack"] is False
    assert "scheduler_unit:abyss-machine-heartbeat.timer" in heartbeat["fabric"]["context_links"]["correlation_keys"]
    assert discovered["resource"]["timer_discovered"] is True
    assert abyss_machine_module.self_awareness_event_issues(heartbeat) == []

    index = abyss_machine_module.self_awareness_correlation_index([heartbeat, discovered])
    assert index["indexes"]["by_context"]["scheduler_scope:user"] == [heartbeat["event_id"], discovered["event_id"]]
    assert index["indexes"]["by_context"]["scheduler_unit:abyss-extra-temporal.timer"] == [discovered["event_id"]]


def test_power_profile_caches_repeated_gets(monkeypatch, abyss_machine_module) -> None:
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(abyss_machine_module, "command_exists", lambda command: command == "powerprofilesctl")

    def fake_run(cmd: list[str], **_: object) -> dict:
        calls.append(tuple(cmd))
        return {"ok": True, "stdout": "balanced"}

    monkeypatch.setattr(abyss_machine_module, "run", fake_run)
    monkeypatch.setattr(abyss_machine_module, "POWER_PROFILE_CACHE_READY", False)
    monkeypatch.setattr(abyss_machine_module, "POWER_PROFILE_CACHE_VALUE", None)

    assert abyss_machine_module.power_profile() == "balanced"
    assert abyss_machine_module.power_profile() == "balanced"
    assert calls == [("powerprofilesctl", "get")]


def test_stack_bridge_observability_caches_snapshot_inside_process(monkeypatch, abyss_machine_module) -> None:
    calls = {"prometheus": 0, "grafana": 0, "podman": 0, "labels": 0, "logql": 0}

    monkeypatch.setattr(abyss_machine_module, "process_container_health", lambda write_latest=False: {"containers": []})
    monkeypatch.setattr(abyss_machine_module, "stack_observability_expected_containers", lambda _health: {"ok": True})
    monkeypatch.setattr(abyss_machine_module, "stack_observability_exec_candidates", lambda _health: ["loki"])
    monkeypatch.setattr(abyss_machine_module, "write_latest_and_history", lambda *_args, **_kwargs: [])

    def fake_prometheus(_query: str) -> dict:
        calls["prometheus"] += 1
        return {
            "ok": True,
            "results": [
                {"metric": {"job": "prometheus"}, "value": "1"},
                {"metric": {"job": "grafana"}, "value": "1"},
                {"metric": {"job": "loki"}, "value": "1"},
                {"metric": {"job": "alloy"}, "value": "1"},
            ],
        }

    def fake_grafana() -> dict:
        calls["grafana"] += 1
        return {"ok": True}

    def fake_podman_http(*_args: object, **_kwargs: object) -> dict:
        calls["podman"] += 1
        return {"ok": True, "container": "loki", "status_code": 200, "text_preview": "ready"}

    def fake_labels(*_args: object, **_kwargs: object) -> dict:
        calls["labels"] += 1
        return {"ok": True, "labels": ["container"], "label_count": 1}

    def fake_logql(*_args: object, **_kwargs: object) -> dict:
        calls["logql"] += 1
        return {"ok": True, "entry_count": 1}

    monkeypatch.setattr(abyss_machine_module, "stack_observability_prometheus_query", fake_prometheus)
    monkeypatch.setattr(abyss_machine_module, "stack_observability_grafana_health", fake_grafana)
    monkeypatch.setattr(abyss_machine_module, "stack_observability_podman_http", fake_podman_http)
    monkeypatch.setattr(abyss_machine_module, "stack_observability_loki_labels", fake_labels)
    monkeypatch.setattr(abyss_machine_module, "stack_observability_logql_query", fake_logql)
    monkeypatch.setattr(abyss_machine_module, "STACK_BRIDGE_OBSERVABILITY_CACHE", None)

    first = abyss_machine_module.stack_bridge_observability(write_latest=True)
    second = abyss_machine_module.stack_bridge_observability(write_latest=True)

    assert first["ok"] is True
    assert second["ok"] is True
    assert calls == {"prometheus": 1, "grafana": 1, "podman": 1, "labels": 1, "logql": 3}


def test_nervous_brief_returns_process_cache_copy(monkeypatch, abyss_machine_module) -> None:
    cached = {
        "schema": "abyss_machine_nervous_brief_v1",
        "ok": True,
        "nested": {"value": "original"},
    }
    monkeypatch.setattr(abyss_machine_module, "NERVOUS_BRIEF_CACHE", {"now:6:False": cached})

    first = abyss_machine_module.nervous_brief(scope="now", limit=6, refresh=False, write_latest=True)
    first["nested"]["value"] = "changed"
    second = abyss_machine_module.nervous_brief(scope="now", limit=6, refresh=False, write_latest=True)

    assert second["schema"] == "abyss_machine_nervous_brief_v1"
    assert second["nested"]["value"] == "original"


def test_self_awareness_event_schema_redacts_secrets_and_links_trace(abyss_machine_module) -> None:
    traceparent = "00-" + ("a" * 32) + "-" + ("b" * 16) + "-01"
    event = abyss_machine_module.self_awareness_make_event(
        "log",
        "loki",
        event_time="2026-01-01T00:00:00+00:00",
        observed_at="2026-01-01T00:00:01+00:00",
        source_query='{container="route-api"} |= "Authorization"',
        resource={
            "service": "route-api",
            "container": "route-api",
            "owner_surface": "abyss-stack",
            "labels": {"container": "route-api"},
            "write": False,
        },
        context=abyss_machine_module.self_awareness_context_from_text(f"traceparent={traceparent}"),
        space={"host": "fixture", "owner_surface": "abyss-stack"},
        body="Authorization: Bearer sk-example-redacted traceparent=" + traceparent,
        evidence_refs=[{"fixture": "event"}],
    )

    assert event["schema"] == "abyss_machine_observation_event_v1"
    assert event["redaction"]["raw_body_stored"] is False
    assert "<redacted>" in event["body_preview"]
    assert "sk-example-redacted" not in event["body_preview"].lower()
    assert event["context"]["traceparent"] == traceparent
    assert event["context"]["trace_id"] == "a" * 32
    assert event["fabric"]["schema"] == "abyss_machine_self_awareness_signal_fabric_v1"
    assert event["fabric"]["actor"]["owner_surface"] == "abyss-stack"
    assert event["fabric"]["actor"]["service"] == "route-api"
    assert event["fabric"]["entity"]["container"] == "route-api"
    assert event["fabric"]["temporal"]["time_bucket"] == "2026-01-01T00:00:00Z"
    assert event["fabric"]["spatial"]["owner_surface"] == "abyss-stack"
    assert event["fabric"]["context_links"]["traceparent"] == traceparent
    assert f"trace_id:{'a' * 32}" in event["fabric"]["context_links"]["correlation_keys"]
    assert event["fabric"]["evidence_route"]["has_refs"] is True
    assert event["fabric"]["evidence_route"]["source_query"] == '{container="route-api"} |= "Authorization"'
    assert event["fabric"]["evidence_route"]["source_query_redacted"] is True
    assert event["fabric"]["policy"]["host_layer_mutates_stack"] is False
    assert event["fabric"]["policy"]["raw_body_stored"] is False
    assert abyss_machine_module.self_awareness_event_issues(event) == []


def test_self_awareness_rejects_missing_evidence_unbounded_labels_and_protected_writes(abyss_machine_module) -> None:
    missing_evidence = abyss_machine_module.self_awareness_make_event(
        "metric",
        "prometheus",
        resource={"service": "route-api", "owner_surface": "abyss-stack", "write": False},
        body={"value": 1},
        evidence_refs=[],
    )
    assert "missing_evidence_refs" in abyss_machine_module.self_awareness_event_issues(missing_evidence)

    bad_label = abyss_machine_module.self_awareness_make_event(
        "log",
        "loki",
        resource={
            "service": "route-api",
            "owner_surface": "abyss-stack",
            "labels": {"trace_id": "abc"},
            "write": False,
        },
        body="bad label",
        evidence_refs=[{"fixture": "bad_label"}],
    )
    assert any(issue.startswith("unbounded_label:trace_id") for issue in abyss_machine_module.self_awareness_event_issues(bad_label))
    assert "fabric_forbidden_label_keys" in abyss_machine_module.self_awareness_event_issues(bad_label)

    protected_write = abyss_machine_module.self_awareness_make_event(
        "process",
        "processes",
        resource={"service": "stack", "path": str(Path.home() / "src/abyss-stack/runtime.toml"), "write": True},
        body="would mutate stack",
        evidence_refs=[{"fixture": "protected_write"}],
    )
    assert "protected_write_claim" in abyss_machine_module.self_awareness_event_issues(protected_write)


def test_self_awareness_correlation_indexes_time_space_and_context(abyss_machine_module) -> None:
    traceparent = "00-" + ("c" * 32) + "-" + ("d" * 16) + "-01"
    context = abyss_machine_module.self_awareness_context_from_text(f"traceparent={traceparent}")
    context["thread_id"] = "thread-correlation"
    context["checkpoint_id"] = "checkpoint-correlation"
    first = abyss_machine_module.self_awareness_make_event(
        "log",
        "loki",
        event_time="2026-01-01T00:02:09+00:00",
        resource={"service": "route-api", "container": "route-api", "owner_surface": "abyss-stack", "write": False},
        context=context,
        evidence_refs=[{"fixture": "first"}],
    )
    second = abyss_machine_module.self_awareness_make_event(
        "metric",
        "prometheus",
        event_time="2026-01-01T00:04:59+00:00",
        resource={"service": "route-api", "container": "route-api", "owner_surface": "abyss-stack", "write": False},
        context=context,
        evidence_refs=[{"fixture": "second"}],
    )
    index = abyss_machine_module.self_awareness_correlation_index([first, second])

    trace_key = "trace_id:" + ("c" * 32)
    assert index["schema"] == "abyss_machine_self_awareness_correlation_index_v1"
    assert index["indexes"]["by_time_bucket"]["2026-01-01T00:00:00Z"] == [first["event_id"], second["event_id"]]
    assert index["indexes"]["by_service"]["route-api"] == [first["event_id"], second["event_id"]]
    assert index["indexes"]["by_context"][trace_key] == [first["event_id"], second["event_id"]]
    assert index["indexes"]["by_context"]["thread_id:thread-correlation"] == [first["event_id"], second["event_id"]]
    assert index["indexes"]["by_context"]["checkpoint_id:checkpoint-correlation"] == [first["event_id"], second["event_id"]]
    assert index["indexes"]["by_owner_surface"]["abyss-stack"] == [first["event_id"], second["event_id"]]


def test_self_awareness_context_indexes_scheduler_and_manual_context_links(abyss_machine_module, monkeypatch) -> None:
    assert abyss_machine_module.self_awareness_host_service_category("abyss-machine-indexing-medium-fixture.service") == "session_memory"
    scheduler_event = abyss_machine_module.self_awareness_make_event(
        "service",
        "scheduler",
        event_time="2026-01-01T00:02:09+00:00",
        resource={"service": "abyss-gemma4-spark-monitor.timer", "owner_surface": "abyss-machine", "write": False},
        context={
            "scheduler_unit": "abyss-gemma4-spark-monitor.timer",
            "scheduler_scope": "user",
            "scheduler_category": "warm_e2b",
        },
        space={"service": "abyss-gemma4-spark-monitor.timer", "owner_surface": "abyss-machine"},
        evidence_refs=[{"fixture": "scheduler"}],
    )
    manual_collect_event = abyss_machine_module.self_awareness_make_event(
        "metric",
        "observability",
        event_time="2026-01-01T00:03:09+00:00",
        resource={"service": "abyss-observability-collect", "owner_surface": "abyss-machine", "write": False},
        context={"manual_collect_status": "operator_authorization_required"},
        space={"service": "abyss-observability-collect", "owner_surface": "abyss-machine"},
        evidence_refs=[{"fixture": "manual_collect"}],
    )
    host_service_event = abyss_machine_module.self_awareness_make_event(
        "service",
        "host-service",
        event_time="2026-01-01T00:04:09+00:00",
        resource={"service": "abyss-dictation-server.service", "owner_surface": "abyss-machine", "write": False},
        context={
            "host_service_unit": "abyss-dictation-server.service",
            "host_service_scope": "user",
            "host_service_category": "dictation",
        },
        space={"service": "abyss-dictation-server.service", "owner_surface": "abyss-machine"},
        evidence_refs=[{"fixture": "host_service"}],
    )

    def fake_load_latest_json(path, schema):
        if schema == "abyss_machine_stack_observability_v1":
            return {"schema": schema, "ok": True, "loki": {"labels": {"labels": []}}}
        if schema == "abyss_machine_self_awareness_capabilities_v1":
            return {
                "schema": schema,
                "ok": True,
                "capabilities": [
                    {"id": "warm-e2b.resident-cognitive-worker"},
                    {"id": "host.governance-gates"},
                    {"id": "llm.escalation.routes"},
                ],
            }
        if schema == "abyss_machine_self_awareness_requirement_probes_v1":
            return {"schema": schema, "ok": True, "summary": {"open": 0}, "probes": []}
        return {"schema": schema, "ok": True}

    monkeypatch.setattr(abyss_machine_module, "self_awareness_load_events", lambda refresh=True: [scheduler_event, manual_collect_event, host_service_event])
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_memory_space_overlay",
        lambda events: {
            "schema": "abyss_machine_self_awareness_memory_space_overlay_v1",
            "summary": {"freshness_gates": 0},
            "freshness_gates": [],
            "policy": {"host_layer_mutates_stack": False},
        },
    )
    monkeypatch.setattr(abyss_machine_module, "self_awareness_brief_stack_handoff_action_map", lambda requirement_probes: {"summary": {"open_stack_requirements": 0}})
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_bounded_context_packet",
        lambda contexts, memory_space, stack_handoff_action_map, capabilities, generated_at, trace_context_doc=None: {
            "schema": "abyss_machine_self_awareness_bounded_context_packet_v1",
            "complete": True,
            "summary": {
                "sections": 6,
                "stack_handoff_actions": 0,
                "open_stack_requirements": 0,
                "resident_worker_complete": True,
                "governance_gates_complete": True,
            },
            "policy": {"host_layer_mutates_stack": False, "action_execution": False},
        },
    )

    payload = abyss_machine_module.self_awareness_context(write_latest=False)
    by_key = {row["key"]: row for row in payload["contexts"]}

    assert payload["schema"] == "abyss_machine_self_awareness_context_v1"
    assert payload["ok"] is True
    assert "scheduler_unit:abyss-gemma4-spark-monitor.timer" in by_key
    assert "scheduler_scope:user" in by_key
    assert "scheduler_category:warm_e2b" in by_key
    assert "manual_collect_status:operator_authorization_required" in by_key
    assert "host_service_unit:abyss-dictation-server.service" in by_key
    assert "host_service_category:dictation" in by_key
    unit_context = by_key["scheduler_unit:abyss-gemma4-spark-monitor.timer"]
    assert unit_context["sources"]["scheduler"] == 1
    assert unit_context["services"]["abyss-gemma4-spark-monitor.timer"] == 1
    assert "scheduler_unit:abyss-gemma4-spark-monitor.timer" in unit_context["correlation_keys"]
    assert unit_context["context"]["context_index_kind"] == "scheduler_unit"
    manual_context = by_key["manual_collect_status:operator_authorization_required"]
    assert manual_context["sources"]["observability"] == 1
    host_context = by_key["host_service_unit:abyss-dictation-server.service"]
    assert host_context["sources"]["host-service"] == 1
    assert host_context["services"]["abyss-dictation-server.service"] == 1
    assert "host_service_unit:abyss-dictation-server.service" in host_context["correlation_keys"]
    assert payload["summary"]["scheduler_unit_contexts"] == 1
    assert payload["summary"]["scheduler_category_contexts"] == 1
    assert payload["summary"]["host_service_unit_contexts"] == 1
    assert payload["summary"]["host_service_category_contexts"] == 1
    assert payload["summary"]["manual_collect_contexts"] == 1
    assert payload["policy"]["host_layer_mutates_stack"] is False


def test_self_awareness_checkpoint_observation_events_link_investigation_replay(abyss_machine_module) -> None:
    investigation = {
        "schema": "abyss_machine_self_awareness_investigation_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "ok": True,
        "thread_id": "thread-1",
        "query": "saprobe-fixture",
        "graph": {"nodes": ["plan_queries"], "resume": {"latest_checkpoint_id": "cp-1"}},
        "checkpoints": [{"checkpoint_id": "cp-1", "thread_id": "thread-1", "node": "plan_queries"}],
        "summary": {"checkpoints": 1},
    }
    replay = {
        "schema": "abyss_machine_self_awareness_replay_v1",
        "generated_at": "2026-01-01T00:00:01+00:00",
        "ok": True,
        "thread_id": "thread-1",
        "resume": {"latest_checkpoint_id": "cp-1"},
        "summary": {"node_order": ["plan_queries"]},
    }

    events = abyss_machine_module.self_awareness_checkpoint_observation_events(investigation, replay, "2026-01-01T00:00:02+00:00")
    summary = abyss_machine_module.self_awareness_signal_fabric_summary(events)

    assert len(events) == 2
    assert summary["with_thread_or_checkpoint"] == 2
    assert {event["resource"]["service"] for event in events} == {"self-awareness-investigate", "self-awareness-replay"}
    for event in events:
        assert event["source"] == "graph"
        assert event["context"]["thread_id"] == "thread-1"
        assert event["context"]["checkpoint_id"] == "cp-1"
        assert event["context"]["synthetic_run_id"] == "saprobe-fixture"
        assert event["fabric"]["context_links"]["thread_id"] == "thread-1"
        assert event["fabric"]["context_links"]["checkpoint_id"] == "cp-1"
        assert "thread_id:thread-1" in event["fabric"]["context_links"]["correlation_keys"]
        assert "checkpoint_id:cp-1" in event["fabric"]["context_links"]["correlation_keys"]
        assert event["fabric"]["policy"]["host_layer_mutates_stack"] is False
        assert abyss_machine_module.self_awareness_event_issues(event) == []


def test_self_awareness_signal_fabric_summary_covers_all_events(abyss_machine_module) -> None:
    event = abyss_machine_module.self_awareness_make_event(
        "model",
        "llm",
        event_time="2026-01-01T00:00:00+00:00",
        resource={"service": "warm-e2b", "model": "gemma4.spark", "owner_surface": "abyss-machine", "write": False},
        context={"thread_id": "thread-1", "checkpoint_id": "cp-1"},
        space={"host": "fixture", "owner_surface": "abyss-machine"},
        evidence_refs=[{"path": "/var/lib/abyss-machine/ai/llm/resident/gemma4.spark/status/latest.json"}],
    )
    summary = abyss_machine_module.self_awareness_signal_fabric_summary([event])

    assert summary["events"] == 1
    assert summary["with_fabric"] == 1
    assert summary["with_actor"] == 1
    assert summary["with_entity"] == 1
    assert summary["with_temporal"] == 1
    assert summary["with_spatial"] == 1
    assert summary["with_context_links"] == 1
    assert summary["with_evidence_route"] == 1
    assert summary["with_policy"] == 1
    assert summary["with_thread_or_checkpoint"] == 1
    assert summary["forbidden_label_events"] == 0


def test_self_awareness_working_stack_inventory_projects_runtime_body_without_stack_mutation(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
) -> None:
    source_stack = tmp_path / "source-stack"
    srv_stack = tmp_path / "srv-stack"
    (source_stack / "compose" / "modules").mkdir(parents=True)
    (srv_stack / "Configs" / "compose" / "modules").mkdir(parents=True)
    (srv_stack / "Services" / "rag-api").mkdir(parents=True)
    (srv_stack / "Services" / "rerank-api").mkdir(parents=True)
    (srv_stack / "Services" / "docs-api").mkdir(parents=True)
    (srv_stack / "Services" / "aoa-browser").mkdir(parents=True)
    (srv_stack / "Models" / "ovms" / "OpenVINO" / "Qwen3-Embedding-0.6B-int8-ov").mkdir(parents=True)
    (source_stack / "compose" / "modules" / "10-storage.yml").write_text(
        "services:\n  qdrant:\n    image: qdrant\n  redis:\n    image: redis\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "compose" / "modules" / "46-rag-api.yml").write_text(
        "services:\n  rag-api:\n    image: rag\n  rerank-api:\n    image: rerank\n  qwen-tts:\n    image: tts\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "compose" / "modules" / "51-browser-tools.yml").write_text(
        "services:\n  docs-api:\n    image: docs\n  aoa-browser:\n    image: browser\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        abyss_machine_module,
        "stack_paths",
        lambda: {
            "source_abyss_stack": str(source_stack),
            "source_abyss_stack_exists": True,
            "srv_abyss_stack": str(srv_stack),
            "srv_abyss_stack_exists": True,
            "canonical_abyss_stack": str(tmp_path / "canonical"),
            "canonical_abyss_stack_exists": False,
            "srv_abyss_os": str(tmp_path),
            "srv_abyss_os_exists": True,
            "host_layer_mutates_stack": False,
            },
    )
    monkeypatch.setattr(abyss_machine_module, "AI_MODEL_ROOTS", [srv_stack / "Models", source_stack / "Models"])
    container_health = {
        "schema": "abyss_machine_process_container_health_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "containers": [
            {"name": "abyss_qdrant_1", "names": ["abyss_qdrant_1"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "qdrant", "stack_managed": True}},
            {"name": "redis", "names": ["redis"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "redis", "stack_managed": True}},
            {"name": "rag-api", "names": ["rag-api"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "rag-api", "stack_managed": True}},
            {"name": "rerank-api", "names": ["rerank-api"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "rerank-api", "stack_managed": True}},
            {"name": "docs-api", "names": ["docs-api"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "docs-api", "stack_managed": True}},
            {"name": "aoa-browser", "names": ["aoa-browser"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "aoa-browser", "stack_managed": True}},
        ],
    }
    endpoint_probes = [
        {"service": "rag-api", "probe": "health", "ok": True, "url": "http://127.0.0.1:5406/health"},
        {"service": "qdrant", "probe": "collections", "ok": True, "url": "http://127.0.0.1:6333/collections"},
        {"service": "rerank-api", "probe": "health", "ok": True, "url": "http://127.0.0.1:5405/health"},
    ]
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_endpoint_probes", lambda enabled=True: endpoint_probes)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_working_stack_container_tool_probes",
        lambda runtime_by_service, enabled=True: [
            {"service": "docs-api", "probe": "health", "kind": "container_http_json", "ok": True, "container": "docs-api"},
            {"service": "docs-api", "probe": "search:n8n-workflow", "kind": "container_http_json", "ok": True, "container": "docs-api", "json_shape": {"results": {"length": 3}}},
            {"service": "aoa-browser", "probe": "health", "kind": "container_http_json", "ok": True, "container": "aoa-browser"},
            {"service": "aoa-browser", "probe": "private-host-guard", "kind": "container_http_json", "ok": True, "status_code": 403, "container": "aoa-browser"},
            {"service": "aoa-browser", "probe": "playwright-chromium-launch", "kind": "container_runtime_smoke", "ok": False, "container": "aoa-browser", "error": "missing chromium payload"},
        ],
    )
    def fail_heavy_ai_capability_refresh(*args, **kwargs):
        raise AssertionError("working-stack inventory must consume latest AI capability evidence")

    monkeypatch.setattr(abyss_machine_module, "ai_capabilities", fail_heavy_ai_capability_refresh)
    monkeypatch.setattr(
        abyss_machine_module,
        "ai_capabilities_latest",
        lambda: {
            "schema": "abyss_machine_ai_capabilities_v1",
            "capabilities": {
                "embeddings": {
                    "status": "ready",
                    "primary_bridge": "abyss-machine ai eval --suite embeddings --json",
                    "source_models": [
                        {
                            "path": str(srv_stack / "Models" / "ovms" / "OpenVINO" / "Qwen3-Embedding-0.6B-int8-ov"),
                            "read_only_source": True,
                        }
                    ],
                }
            },
            "latest_consumption": {
                "source": "latest_artifact",
                "refresh_inputs": False,
                "heavy_runtime_probe_allowed": False,
            },
        },
    )

    inventory = abyss_machine_module.self_awareness_working_stack_inventory(
        write_latest=False,
        stack_doc={"schema": "abyss_machine_stack_observability_v1", "ok": True},
        container_health=container_health,
    )
    organs = {row["service"]: row for row in inventory["organs"]}

    assert inventory["schema"] == "abyss_machine_self_awareness_working_stack_inventory_v1"
    assert inventory["ok"] is True
    assert {"qdrant", "redis", "rag-api", "rerank-api", "qwen-tts", "ovms", "embeddings"}.issubset(organs)
    assert organs["qdrant"]["machine_usage_status"] == "active_dependency_signal"
    assert organs["rag-api"]["machine_usage_status"] == "active_machine_signal"
    assert organs["docs-api"]["machine_usage_status"] == "active_machine_tool_signal"
    assert organs["docs-api"]["deep_usage_proven"] is True
    assert organs["aoa-browser"]["machine_usage_status"] == "tool_runtime_degraded"
    assert organs["aoa-browser"]["deep_usage_proven"] is False
    assert "functional runtime smoke failed" in organs["aoa-browser"]["usage_gap"]
    assert organs["embeddings"]["machine_usage_status"] == "active_model_root_bridge"
    assert organs["embeddings"]["deep_usage_proven"] is True
    assert organs["embeddings"]["model_bridge"]["active"] is True
    assert organs["embeddings"]["model_bridge"]["policy"]["host_layer_mutates_stack"] is False
    assert organs["qwen-tts"]["machine_usage_status"] == "declared_not_running"
    assert inventory["summary"]["time_space_context_links"] == inventory["summary"]["organs"]
    assert inventory["policy"]["host_layer_mutates_stack"] is False
    assert all(ref.get("read_only") is True for row in organs.values() for ref in row.get("stack_source_refs", []))

    events = abyss_machine_module.self_awareness_working_stack_events(inventory, "2026-01-01T00:00:00+00:00")
    event_by_service = {event["resource"]["service"]: event for event in events}

    assert {"qdrant", "rag-api", "rerank-api"}.issubset(event_by_service)
    assert event_by_service["docs-api"]["severity"] == "notice"
    assert event_by_service["aoa-browser"]["severity"] == "warning"
    assert all(event["source"] == "working-stack" for event in events)
    assert all(event["fabric"]["context_links"]["correlation_keys"] for event in events)
    assert all((event["context"] or {}).get("working_stack_link_id") for event in events)
    assert not any(
        str(ref.get("path", "")).startswith((str(source_stack), str(srv_stack)))
        for event in events
        for ref in event.get("evidence_refs", [])
    )
    assert all(abyss_machine_module.self_awareness_event_issues(event) == [] for event in events)


def test_self_awareness_working_stack_uses_service_selection_policy_for_nonresident_surfaces(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
) -> None:
    source_stack = tmp_path / "source-stack"
    srv_stack = tmp_path / "srv-stack"
    (source_stack / "compose" / "modules").mkdir(parents=True)
    (source_stack / "docs" / "runtime").mkdir(parents=True)
    (srv_stack / "Configs" / "compose" / "modules").mkdir(parents=True)
    (srv_stack / "Configs" / "docs" / "runtime").mkdir(parents=True)
    (srv_stack / "Configs" / "compose" / "modules" / "20-orchestration.yml").write_text(
        "services:\n  n8n:\n    image: n8n\n  n8n-task-runners:\n    image: runners\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "compose" / "modules" / "40-llm-gateway.yml").write_text(
        "services:\n  litellm:\n    image: litellm\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "compose" / "modules" / "44-llamacpp-agent-sidecar.yml").write_text(
        "services:\n  langchain-api-llamacpp:\n    image: langchain\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "compose" / "modules" / "52-tos-graph.yml").write_text(
        "services:\n  tos-graph:\n    image: tos\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "compose" / "modules" / "53-babelvox-tts.yml").write_text(
        "services:\n  babelvox-tts:\n    image: babelvox\n",
        encoding="utf-8",
    )
    (source_stack / "compose" / "modules" / "60-monitoring.yml").write_text(
        "services:\n  tempo:\n    image: tempo\n",
        encoding="utf-8",
    )
    (srv_stack / "Configs" / "docs" / "runtime" / "service-selection-policy.v1.json").write_text(
        json.dumps({
            "schema": "abyss_stack_service_selection_policy_v1",
            "services": [
                {"name": "n8n", "posture": "explicit_opt_in", "tier": "workflow_automation", "decision": "enable only for workflow runs"},
                {"name": "n8n-task-runners", "posture": "explicit_opt_in", "tier": "workflow_automation", "decision": "external runners only with workflows"},
                {"name": "litellm", "posture": "fallback_control", "tier": "fallback", "decision": "not current default"},
                {"name": "tos-graph", "posture": "explicit_opt_in", "tier": "curation", "decision": "not current always-on shape"},
                {"name": "babelvox-tts", "posture": "lab_only", "tier": "experimental_speech", "decision": "bounded service testing only"},
                {"name": "langchain-api-llamacpp", "posture": "lab_only", "tier": "benchmark_sidecar", "decision": "not default runtime"},
            ],
        }),
        encoding="utf-8",
    )
    (source_stack / "docs" / "runtime" / "service-selection-policy.v1.json").write_text(
        json.dumps({
            "schema": "abyss_stack_service_selection_policy_v1",
            "services": [
                {"name": "tempo", "posture": "selected_now", "tier": "explicit_observability", "decision": "keep trace backend bounded"},
            ],
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        abyss_machine_module,
        "stack_paths",
        lambda: {
            "source_abyss_stack": str(source_stack),
            "source_abyss_stack_exists": True,
            "srv_abyss_stack": str(srv_stack),
            "srv_abyss_stack_exists": True,
            "canonical_abyss_stack": str(tmp_path / "canonical"),
            "canonical_abyss_stack_exists": False,
            "srv_abyss_os": str(tmp_path),
            "srv_abyss_os_exists": True,
            "host_layer_mutates_stack": False,
        },
    )
    monkeypatch.setattr(abyss_machine_module, "AI_MODEL_ROOTS", [srv_stack / "Models", source_stack / "Models"])
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_working_stack_endpoint_probes",
        lambda enabled=True: [{"service": "tempo", "probe": "ready", "ok": True, "url": "http://127.0.0.1:3200/ready"}],
    )
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_container_tool_probes", lambda runtime_by_service, enabled=True: [])
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_tts_smoke_probes", lambda enabled=True: [])
    monkeypatch.setattr(
        abyss_machine_module,
        "ai_capabilities_latest",
        lambda: {"schema": "abyss_machine_ai_capabilities_v1", "capabilities": {}},
    )
    container_health = {
        "schema": "abyss_machine_process_container_health_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "containers": [
            {"name": "tempo", "names": ["tempo"], "running": True, "state": "running", "compose": {"project": "abyss", "service": "tempo", "stack_managed": True}},
        ],
    }

    inventory = abyss_machine_module.self_awareness_working_stack_inventory(
        write_latest=False,
        stack_doc={"schema": "abyss_machine_stack_observability_v1", "ok": True},
        container_health=container_health,
    )
    organs = {row["service"]: row for row in inventory["organs"]}

    assert organs["langchain-api-llamacpp"]["machine_usage_status"] == "policy_deferred_lab"
    assert organs["babelvox-tts"]["machine_usage_status"] == "policy_deferred_lab"
    assert organs["litellm"]["machine_usage_status"] == "policy_deferred_fallback"
    assert organs["n8n"]["machine_usage_status"] == "policy_deferred_opt_in"
    assert organs["n8n-task-runners"]["machine_usage_status"] == "policy_deferred_opt_in"
    assert organs["tos-graph"]["machine_usage_status"] == "policy_deferred_opt_in"
    for service in ("langchain-api-llamacpp", "babelvox-tts", "litellm", "n8n", "n8n-task-runners", "tos-graph"):
        assert organs[service]["usage_gap"] is None
        assert organs[service]["deep_usage_proven"] is False
        assert organs[service]["service_selection"]["source_ref"]["read_only"] is True
    assert organs["tempo"]["machine_usage_status"] == "active_machine_signal"
    assert organs["tempo"]["deep_usage_proven"] is True
    assert organs["tempo"]["service_selection"]["policy_origin"] == "source_checkout"
    assert inventory["summary"]["policy_deferred_services"] == 6
    assert not any(
        gap["service"] in {"langchain-api-llamacpp", "babelvox-tts", "litellm", "n8n", "n8n-task-runners", "tos-graph"}
        for gap in inventory["machine_usage_gaps"]
    )


def test_self_awareness_working_stack_reads_tts_synthesis_artifact_as_on_demand_tool_signal(
    abyss_machine_module,
    monkeypatch,
    tmp_path,
) -> None:
    source_stack = tmp_path / "source-stack"
    srv_stack = tmp_path / "srv-stack"
    (source_stack / "compose" / "modules").mkdir(parents=True)
    (srv_stack / "Configs" / "compose" / "modules").mkdir(parents=True)
    (srv_stack / "Logs" / "tts" / "aoa_archivist").mkdir(parents=True)
    (srv_stack / "Configs" / "compose" / "modules" / "50-speech.yml").write_text(
        "services:\n  qwen-tts:\n    image: qwen\n  tts-router:\n    image: router\n",
        encoding="utf-8",
    )
    wav_path = srv_stack / "Logs" / "tts" / "aoa_archivist" / "self_awareness_smoke.wav"
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 240)
    wav_path.with_suffix(".json").write_text(
        "\n".join([
            "agent_id: aoa_archivist",
            "voice_id: aoa_archivist",
            "model_id: /models/hf/local/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            "language: Russian",
            "speaker: Aiden",
            "saved_path: /out/aoa_archivist/self_awareness_smoke.wav",
            "text: Smoke after repair.",
            "ts: '2026-06-10 21:45:10'",
            "",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        abyss_machine_module,
        "stack_paths",
        lambda: {
            "source_abyss_stack": str(source_stack),
            "source_abyss_stack_exists": True,
            "srv_abyss_stack": str(srv_stack),
            "srv_abyss_stack_exists": True,
            "canonical_abyss_stack": str(tmp_path / "canonical"),
            "canonical_abyss_stack_exists": False,
            "srv_abyss_os": str(tmp_path),
            "srv_abyss_os_exists": True,
            "host_layer_mutates_stack": False,
        },
    )
    monkeypatch.setattr(abyss_machine_module, "AI_MODEL_ROOTS", [srv_stack / "Models", source_stack / "Models"])
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_endpoint_probes", lambda enabled=True: [])
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_container_tool_probes", lambda runtime_by_service, enabled=True: [])
    monkeypatch.setattr(
        abyss_machine_module,
        "ai_capabilities_latest",
        lambda: {"schema": "abyss_machine_ai_capabilities_v1", "capabilities": {}},
    )
    container_health = {
        "schema": "abyss_machine_process_container_health_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "containers": [
            {"name": "qwen-tts", "names": ["qwen-tts"], "running": False, "state": "exited", "compose": {"project": "abyss", "service": "qwen-tts", "stack_managed": True}},
            {"name": "tts-router", "names": ["tts-router"], "running": False, "state": "exited", "compose": {"project": "abyss", "service": "tts-router", "stack_managed": True}},
        ],
    }

    inventory = abyss_machine_module.self_awareness_working_stack_inventory(
        write_latest=False,
        stack_doc={"schema": "abyss_machine_stack_observability_v1", "ok": True},
        container_health=container_health,
    )
    organs = {row["service"]: row for row in inventory["organs"]}

    for service in ("qwen-tts", "tts-router"):
        organ = organs[service]
        assert organ["machine_usage_status"] == "recent_on_demand_tool_signal"
        assert organ["deep_usage_proven"] is True
        assert organ["usage_gap"] is None
        probe = next(item for item in organ["endpoint_probes"] if item["probe"] == "tts-synthesis-artifact")
        assert probe["ok"] is True
        assert probe["evidence"]["wav_bytes"] > 44
        assert probe["evidence"]["wav_format"]["framerate"] == 24000
        assert probe["policy"]["host_layer_mutates_stack"] is False
        assert probe["policy"]["raw_text_stored"] is False
        assert probe["policy"]["raw_audio_stored"] is False
        assert any(ref["path"] == str(wav_path) for ref in probe["evidence_refs"])
        assert any(ref["path"] == str(wav_path.with_suffix(".json")) for ref in probe["evidence_refs"])
        assert not any(str(ref.get("path", "")).startswith(str(srv_stack)) for ref in organ["evidence_refs"])
    assert not any(gap["service"] in {"qwen-tts", "tts-router"} for gap in inventory["machine_usage_gaps"])


def test_self_awareness_memory_space_overlay_preserves_freshness_and_boundaries(abyss_machine_module) -> None:
    event = abyss_machine_module.self_awareness_make_event(
        "rag",
        "rag",
        event_time="2026-01-01T00:00:00+00:00",
        resource={"service": "rag-api", "owner_surface": "abyss-stack", "write": False},
        evidence_refs=[{"path": "/var/lib/abyss-machine/rag/traces/latest.json"}],
    )
    rag_trace = {
        "schema": "abyss_machine_rag_trace_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "packet": {
            "entries": [
                {
                    "id": "packet-rag",
                    "axis": "by-rag-run",
                    "label": "machine RAG trace",
                    "route": "Open /var/lib/abyss-machine/rag/traces/latest.json",
                    "owner_route": "abyss-machine",
                    "tags": ["rag", "retrieval"],
                    "truth_status": "generated_route_signal_not_source_truth",
                    "evidence_refs": [{"path": "/var/lib/abyss-machine/rag/traces/latest.json"}],
                }
            ]
        },
    }
    maps = {
        "schema": "abyss_machine_maps_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "entries_by_axis": {
            "by-rag-run": [rag_trace["packet"]["entries"][0]],
            "by-freshness": [{"id": "fresh-rag", "axis": "by-freshness", "label": "rag freshness", "evidence_refs": [{"path": "/var/lib/abyss-machine/rag/validate/latest.json"}]}],
            "by-memory-candidate": [{"id": "memo", "axis": "by-memory-candidate", "label": "host memo port"}],
            "by-subsystem": [{"id": "subsystem-rag", "axis": "by-subsystem", "label": "rag graph memory postgres neo4j embeddings"}],
            "by-correlation": [{"id": "correlation-rag", "axis": "by-correlation", "label": "rag graph freshness"}],
        },
    }
    overlay = abyss_machine_module.self_awareness_memory_space_overlay(
        [event],
        maps=maps,
        rag_trace=rag_trace,
        rag_validate_doc={"schema": "abyss_machine_rag_validate_v1", "ok": True, "generated_at": "2026-01-01T00:00:00+00:00"},
        graph={"schema": "abyss_machine_graph_v1", "ok": True, "generated_at": "2026-01-01T00:00:00+00:00"},
        memory_latest={"schema": "abyss_machine_memory_status_v1", "ok": True, "generated_at": "2026-01-01T00:00:00+00:00"},
        nervous={
            "schema": "abyss_machine_nervous_brief_v1",
            "ok": False,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "readiness": {"status": "degraded", "semantic_stale": True, "semantic_maintenance_needed": True},
            "gaps": [{"layer": "semantic", "reason": "semantic sidecar exceeds maintenance thresholds"}],
            "next_actions": [{"action": "semantic_maintain", "command": abyss_machine_module.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND}],
        },
        nervous_semantic_maintain={
            "schema": "abyss_machine_nervous_semantic_maintain_v1",
            "ok": True,
            "generated_at": "2026-01-01T00:00:01+00:00",
            "decision": "blocked_index_refresh",
            "reason": "resource gate blocked source index refresh before semantic maintenance",
            "resource": {"class": "medium", "kind": "indexing", "unattended": True},
            "assessment": {"needed": True, "reasons": ["stale_age_minutes=120.0"]},
            "index_refresh": {
                "assessment": {"needed": True, "reasons": ["source_index_stale"]},
                "launch": {"blocked_reasons": ["indexing_unattended_swap_used_pressure"], "denied_reasons": []},
            },
        },
        requirements={"schema": "abyss_machine_self_awareness_requirements_v1", "requirements": [{"id": "stack.database-graph.read-route"}]},
        containers={"schema": "abyss_machine_process_container_health_v1", "ok": True, "containers": [{"name": "postgres"}, {"name": "neo4j"}, {"name": "rag-api"}]},
    )

    assert overlay["schema"] == "abyss_machine_self_awareness_memory_space_overlay_v1"
    assert overlay["summary"]["retrieval_packets"] == 1
    assert overlay["summary"]["freshness_gates"] == 6
    assert {gate["gate_id"] for gate in overlay["freshness_gates"]} == abyss_machine_module.SELF_AWARENESS_MEMORY_SPACE_REQUIRED_GATES
    assert overlay["policy"]["bounded_retrieval"] is True
    assert overlay["policy"]["raw_evidence_is_not_truth"] is True
    assert overlay["policy"]["host_layer_mutates_stack"] is False
    assert overlay["policy"]["memory_writeback"] is False
    gate_by_id = {gate["gate_id"]: gate for gate in overlay["freshness_gates"]}
    nervous_gate = gate_by_id["nervous_freshness"]
    assert nervous_gate["status"] == "stale"
    assert nervous_gate["maintenance_route"] == abyss_machine_module.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND
    assert nervous_gate["details"]["semantic_maintain"]["decision"] == "blocked_index_refresh"
    assert nervous_gate["details"]["semantic_maintain"]["index_refresh_blocked_reasons"] == ["indexing_unattended_swap_used_pressure"]
    assert nervous_gate["details"]["resource_denial_is_safe_gate"] is True
    assert nervous_gate["details"]["policy"]["does_not_bypass_resource_gate"] is True
    assert any(ref.get("truth_level") == "nervous_semantic_maintain" for ref in nervous_gate["evidence_refs"])
    backend_by_id = {item["id"]: item for item in overlay["stack_semantic_backends"]}
    assert backend_by_id["postgres"]["semantic_inventory"] == "requirement_open"
    assert backend_by_id["neo4j"]["semantic_inventory"] == "requirement_open"
    assert backend_by_id["rag-api"]["semantic_inventory"] == "bounded_machine_rag_trace"
    assert abyss_machine_module.self_awareness_match_score(
        backend_by_id["postgres"],
        "rag graph memory postgres neo4j embeddings freshness",
    ) > 0


def test_self_awareness_capability_item_carries_matrix_depth(abyss_machine_module) -> None:
    item = abyss_machine_module.self_awareness_capability_item(
        "prometheus.targets",
        "Prometheus target and rule discovery",
        "abyss-stack",
        True,
        required=True,
        evidence_refs=[
            {"path": "/var/lib/abyss-machine/stack-bridge/observability/latest.json", "schema": "abyss_machine_stack_observability_v1"},
            {"url": "http://127.0.0.1:9090/api/v1/targets", "status_code": 200},
        ],
        endpoints=[{"url": "http://127.0.0.1:9090/api/v1/rules", "status_code": 200, "ok": True}],
        detail={"targets_ok": True},
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert item["owner"] == "abyss-stack"
    assert item["matrix"]["schema"] == "abyss_machine_self_awareness_capability_matrix_row_v1"
    assert item["matrix"]["capability_id"] == "prometheus.targets"
    assert item["owner_boundary"]["owner"] == "abyss-stack"
    assert item["owner_boundary"]["stack_owned"] is True
    assert item["owner_boundary"]["host_layer_mutates_stack"] is False
    assert item["access"]["read_only"] is True
    assert item["access"]["host_layer_mutates_stack"] is False
    assert item["access"]["stores_raw_private_payload"] is False
    assert len(item["endpoints"]) == 2
    assert all(endpoint["read_only"] is True and endpoint["body_stored"] is False for endpoint in item["endpoints"])
    assert item["schemas"][0]["schema"] == "abyss_machine_stack_observability_v1"
    assert item["latest_artifacts"][0]["path"] == "/var/lib/abyss-machine/stack-bridge/observability/latest.json"
    assert item["freshness"]["freshness_must_precede_reasoning"] is True
    assert item["freshness"]["raw_evidence_is_not_truth"] is True
    assert item["history"]["latest_artifacts"][0]["daily_glob"].endswith("YYYY/MM/YYYY-MM-DD.jsonl")
    assert item["matrix"]["evidence_route"]["has_endpoint_or_artifact"] is True


def test_self_awareness_requirements_handoff_preserves_identity_and_owner_boundary(abyss_machine_module) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="missing stack trace backend should be a stack-owned requirement",
        detection={"evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/capabilities/latest.json"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    handoff = abyss_machine_module.self_awareness_requirement_handoff(requirement)
    document = abyss_machine_module.self_awareness_requirements_document([requirement], "2026-01-01T00:00:00+00:00")

    assert requirement["owner"] == "abyss-stack"
    assert requirement["host_layer_mutates_stack"] is False
    assert handoff["id"] == "stack.trace-backend"
    assert handoff["requirement_id"] == "stack.trace-backend"
    assert handoff["host_layer_mutates_stack"] is False
    assert "Tempo or compatible trace backend exposes a read-only health endpoint" in handoff["stack_acceptance"]
    assert handoff["acceptance_contract"]["schema"] == "abyss_machine_stack_requirement_acceptance_contract_v1"
    assert handoff["acceptance_contract"]["requirement_id"] == "stack.trace-backend"
    assert handoff["acceptance_contract"]["closure_semantics"]["host_layer_mutates_stack"] is False
    assert handoff["machine_closure_probe"]["kind"] == "trace_backend_inventory"
    assert "traceparent_supported" in handoff["machine_closure_probe"]["required_fields"]
    assert handoff["acceptance_contract"]["machine_verifiers"]
    assert any("must not write abyss-stack" in item for item in handoff["acceptance_contract"]["must_not"])
    assert handoff["compat_contract"]["schema"] == "abyss_machine_self_awareness_stack_compat_contract_v1"
    assert handoff["compat_contract"]["surface_kind"] == "trace_backend_inventory"
    assert "traceparent_supported" in handoff["compat_contract"]["minimum_response_contract"]["required_fields"]
    assert handoff["compat_contract"]["machine_consumer_contract"]["post_close_verifiers"]
    assert handoff["compat_contract"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
    assert handoff["compat_contract"]["redaction_contract"]["raw_secrets_allowed"] is False
    assert handoff["compat_contract"]["coverage_contract"]["organ"] == "trace_join_backbone"
    assert document["ok"] is True
    assert document["summary"]["stack_owned"] == 1
    assert document["summary"]["machine_owned"] == 0
    assert document["summary"]["stack_handoff_acceptance_contracts"] == 1
    assert document["summary"]["stack_handoff_compat_contracts"] == 1
    assert document["policy"]["stack_handoff_is_machine_checkable"] is True
    assert document["stack_handoff"][0]["id"] == document["stack_handoff"][0]["requirement_id"]


@pytest.mark.parametrize(
    ("requirement_id", "expected_kind", "expected_field"),
    [
        ("stack.grafana.datasource-read", "grafana_datasource_inventory", "datasource_uid_or_id"),
        ("stack.trace-backend", "trace_backend_inventory", "traceparent_supported"),
        ("stack.database-graph.read-route", "database_graph_semantic_inventory", "postgres.schemas"),
        ("stack.langchain-api.graph-observability", "langchain_langgraph_observability_inventory", "checkpoint_count_or_ids"),
    ],
)
def test_self_awareness_stack_requirement_acceptance_contracts_are_probeable(
    abyss_machine_module,
    requirement_id,
    expected_kind,
    expected_field,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        requirement_id,
        "Stack requirement",
        reason="fixture gap",
        detection={"evidence_refs": [{"fixture": requirement_id}]},
        expected_shape={"mutated_by": "abyss-stack"},
    )
    handoff = abyss_machine_module.self_awareness_requirement_handoff(requirement)
    contract = handoff["acceptance_contract"]
    compat = handoff["compat_contract"]
    probe = handoff["machine_closure_probe"]

    assert contract["schema"] == "abyss_machine_stack_requirement_acceptance_contract_v1"
    assert contract["owner"] == "abyss-stack"
    assert contract["machine_role"] == "read_only_consumer"
    assert contract["closure_semantics"]["no_partial_credit"] is True
    assert contract["closure_semantics"]["requires_stack_owned_route"] is True
    assert contract["closure_semantics"]["host_layer_mutates_stack"] is False
    assert probe["kind"] == expected_kind
    assert expected_field in probe["required_fields"]
    assert probe["success_predicates"]
    assert probe["redaction_rules"]
    assert contract["machine_verifiers"]
    assert all(item.get("command", "").startswith("abyss-machine ") for item in contract["machine_verifiers"])
    assert compat["schema"] == "abyss_machine_self_awareness_stack_compat_contract_v1"
    assert compat["surface_kind"] == expected_kind
    assert expected_field in compat["minimum_response_contract"]["required_fields"]
    assert compat["minimum_response_contract"]["success_predicates"]
    assert compat["machine_consumer_contract"]["post_close_verifiers"]
    assert compat["operator_boundary"]["abyss_machine_executes_stack_change"] is False
    assert compat["policy"]["host_layer_mutates_stack"] is False
    assert compat["redaction_contract"]["raw_private_payloads_allowed"] is False


def test_self_awareness_stack_memory_space_probe_summarizes_live_routes_without_payloads(
    abyss_machine_module,
    monkeypatch,
) -> None:
    def fake_http(url: str, timeout: float = 1.5, max_bytes: int = 262144, method: str = "GET") -> dict:
        del timeout, max_bytes, method
        payloads = {
            "http://127.0.0.1:5402/health": {
                "ok": True,
                "layers": ["aoa-memo"],
                "mirror_ready": True,
                "thin_routing_only": True,
                "advisory_only": True,
                "closure_summary": {"closure_ready": True},
            },
            "http://127.0.0.1:5402/openapi.json": {
                "paths": {
                    "/health": {"get": {}},
                    "/memo/catalog": {"get": {}},
                }
            },
            "http://127.0.0.1:5406/health": {
                "ok": True,
                "service": "rag-api",
                "collection": "abyss_stack_rag_chunks_v1",
                "vector_size": 1024,
                "checks": {"qdrant": {"status": "ok"}},
                "langchain": {"ok": True},
                "route_api": {"ok": True},
                "rerank_api": {"ok": True},
            },
            "http://127.0.0.1:5406/openapi.json": {
                "paths": {
                    "/health": {"get": {}},
                    "/collections": {"get": {}},
                    "/sources": {"get": {}},
                    "/agentic-rag/graph": {"get": {}},
                }
            },
            "http://127.0.0.1:5406/collections": {"ok": True, "data": {"collections": [{"name": "abyss_stack_rag_chunks_v1"}]}},
            "http://127.0.0.1:5406/sources": {"ok": True, "data": [{"id": "federation-public-surfaces"}, {"name": "abyss-stack-runtime-docs"}]},
                "http://127.0.0.1:5406/agentic-rag/graph": {
                    "ok": True,
                    "data": {
                        "nodes": [{"id": "node-1", "private_body": "must-not-be-stored"}],
                        "edges": [{"id": "edge-1"}],
                        "source_refs": [{"source": "fixture"}],
                    },
                },
                "http://127.0.0.1:5406/semantic-inventory": {
                    "schema": "abyss_stack_semantic_inventory_v1",
                    "semantic_inventory": {
                        "inventory_complete": False,
                        "stack_owned_postgres_schema_inventory_present": False,
                        "stack_owned_neo4j_graph_inventory_present": False,
                    },
                    "postgres": {"schema_inventory_present": False},
                    "neo4j": {"graph_inventory_present": False},
                    "redaction": {
                        "raw_database_rows_stored": False,
                        "raw_graph_properties_stored": False,
                        "raw_source_documents_stored": False,
                        "raw_credentials_stored": False,
                    },
                },
                "http://127.0.0.1:7474/": {
                    "neo4j_version": "5.26.26",
                    "neo4j_edition": "community",
                "query": "http://127.0.0.1:7474/db/{databaseName}/query/v2",
                "bolt_routing": "neo4j://127.0.0.1:7687",
            },
        }
        return {"ok": True, "url": url, "status_code": 200, "json": payloads[url]}

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(abyss_machine_module, "memory_orchestrate_http_json", fake_http)
    monkeypatch.setattr(abyss_machine_module.socket, "create_connection", lambda *args, **kwargs: FakeSocket())

    probe = abyss_machine_module.self_awareness_stack_memory_space_probe()

    assert probe["schema"] == "abyss_machine_stack_memory_space_probe_v1"
    assert probe["ok"] is True
    assert probe["route_api"]["openapi"]["path_count"] == 2
    assert probe["rag_api"]["collections"]["collection_names"] == ["abyss_stack_rag_chunks_v1"]
    assert probe["rag_api"]["sources"]["source_count"] == 2
    assert probe["rag_api"]["agentic_graph"]["node_count"] == 1
    assert probe["rag_api"]["agentic_graph"]["edge_count"] == 1
    assert probe["postgres"]["tcp_ready"] is True
    assert probe["neo4j"]["root"]["neo4j_version"] == "5.26.26"
    assert probe["semantic_inventory"]["route_api_readable"] is True
    assert probe["semantic_inventory"]["rag_api_readable"] is True
    assert probe["semantic_inventory"]["inventory_complete"] is False
    assert probe["redaction"]["raw_database_rows_stored"] is False
    assert probe["redaction"]["raw_graph_properties_stored"] is False
    assert probe["redaction"]["raw_source_documents_stored"] is False
    assert "must-not-be-stored" not in abyss_machine_module.json.dumps(probe)


def test_self_awareness_database_graph_requirement_uses_route_rag_db_metadata_without_false_closure(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.database-graph.read-route",
        "Database graph read route",
        reason="fixture route/rag/db endpoints are live but semantic inventory is absent",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5406/collections"}]},
        expected_shape={"mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    memory_space_routes = {
        "schema": "abyss_machine_stack_memory_space_probe_v1",
        "ok": True,
        "route_api": {
            "health": {"url": "http://127.0.0.1:5402/health", "ok": True, "status_code": 200},
            "openapi": {"url": "http://127.0.0.1:5402/openapi.json", "ok": True, "status_code": 200, "path_count": 2, "paths": [{"path": "/health", "methods": ["GET"]}]},
        },
        "rag_api": {
            "health": {"url": "http://127.0.0.1:5406/health", "ok": True, "status_code": 200},
            "openapi": {"url": "http://127.0.0.1:5406/openapi.json", "ok": True, "status_code": 200, "path_count": 4, "paths": [{"path": "/collections", "methods": ["GET"]}]},
            "collections": {"url": "http://127.0.0.1:5406/collections", "ok": True, "status_code": 200, "collection_names": ["abyss_stack_rag_chunks_v1"], "collection_count": 1},
            "sources": {"url": "http://127.0.0.1:5406/sources", "ok": True, "status_code": 200, "source_names": ["federation-public-surfaces"], "source_count": 1},
            "agentic_graph": {"url": "http://127.0.0.1:5406/agentic-rag/graph", "ok": True, "status_code": 200, "node_count": 6, "edge_count": 7},
        },
        "postgres": {"host": "127.0.0.1", "port": 5432, "tcp_ready": True, "schema_inventory_present": False},
        "neo4j": {"root": {"url": "http://127.0.0.1:7474/", "ok": True, "status_code": 200, "neo4j_version": "5.26.26", "query_endpoint_present": True}, "graph_inventory_present": False},
        "semantic_inventory": {
            "stack_owned_postgres_schema_inventory_present": False,
            "stack_owned_neo4j_graph_inventory_present": False,
            "inventory_complete": False,
        },
        "evidence_refs": [{"url": "http://127.0.0.1:5406/collections", "status_code": 200}],
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {"memory_space_routes": memory_space_routes},
        "capabilities": [
            {
                "id": "stack.active.services",
                "evidence_refs": [{"path": "/var/lib/abyss-machine/processes/containers/latest.json"}],
                "detail": {
                    "postgres_seen": True,
                    "neo4j_seen": True,
                    "container_names": ["route-api", "rag-api", "abyss_postgres_1", "abyss_neo4j_1"],
                },
            }
        ],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    current = probe["current_state"]
    assert probe["id"] == "stack.database-graph.read-route"
    assert probe["status"] == "open"
    assert probe["closed_by_current_probe"] is False
    assert current["route_api_health_ok"] is True
    assert current["route_api_openapi_ok"] is True
    assert current["rag_api_health_ok"] is True
    assert current["rag_api_openapi_ok"] is True
    assert current["rag_collection_names"] == ["abyss_stack_rag_chunks_v1"]
    assert current["postgres_tcp_ready"] is True
    assert current["neo4j_root_readable"] is True
    assert current["neo4j_version"] == "5.26.26"
    assert current["stack_owned_postgres_schema_inventory_present"] is False
    assert current["stack_owned_neo4j_graph_inventory_present"] is False
    required_fields = probe["acceptance_contract"]["probe_plan"]["required_fields"]
    assert "route_api.openapi_paths" in required_fields
    assert "rag_api.collection_names" in required_fields
    assert "postgres.schemas" in required_fields
    assert "neo4j.labels" in required_fields
    checks = {check["key"]: check for check in probe["checks"]}
    assert checks["route_api_health_openapi_readable"]["ok"] is True
    assert checks["rag_api_inventory_routes_readable"]["ok"] is True
    assert checks["database_endpoint_metadata_readable"]["ok"] is True
    assert checks["database_graph_inventory_route_present"]["level"] == "open"
    assert checks["host_layer_non_mutating"]["ok"] is True
    assert checks["no_secret_leakage"]["ok"] is True


def test_self_awareness_langchain_probe_classifies_runtime_routes_without_payloads(
    abyss_machine_module,
    monkeypatch,
) -> None:
    def fake_http(url: str, timeout: float = 1.5, max_bytes: int = 262144, method: str = "GET") -> dict:
        del timeout, max_bytes, method
        payloads = {
            "http://127.0.0.1:5403/health": {
                "ok": True,
                "service": "langchain-api",
                "embeddings_provider": "ovms",
                "ovms_auth_enabled": True,
                "federated_run_enabled": True,
            },
            "http://127.0.0.1:5403/openapi.json": {
                "paths": {
                    "/health": {"get": {}},
                    "/run": {"post": {"description": "must-not-store-prompt-body"}},
                    "/run/federated": {"post": {}},
                    "/embeddings": {"post": {}},
                },
                "components": {
                    "schemas": {
                        "RunReq": {},
                        "FederatedRunReq": {},
                        "EmbeddingsReq": {},
                    }
                },
            },
        }
        return {"ok": True, "url": url, "status_code": 200, "json": payloads[url]}

    monkeypatch.setattr(abyss_machine_module, "memory_orchestrate_http_json", fake_http)

    probe = abyss_machine_module.self_awareness_langchain_api_probe()

    assert probe["schema"] == "abyss_machine_stack_langchain_api_probe_v1"
    assert probe["ok"] is True
    assert probe["runtime_surface"]["run_route_present"] is True
    assert probe["runtime_surface"]["federated_run_route_present"] is True
    assert probe["runtime_surface"]["embeddings_route_present"] is True
    assert probe["runtime_surface"]["usable_runtime_surface"] is True
    assert probe["runtime_surface"]["runtime_request_schema_names"] == ["EmbeddingsReq", "FederatedRunReq", "RunReq"]
    assert probe["replay_inventory"]["thread_inventory_present"] is False
    assert probe["replay_inventory"]["checkpoint_inventory_present"] is False
    assert probe["replay_inventory"]["trace_inventory_present"] is False
    assert probe["replay_inventory"]["missing_inventory"] == ["threads", "checkpoints", "traces"]
    assert probe["observability"]["graph_observability_complete"] is False
    assert probe["trace_backend_coupling"]["stack_owned_trace_backend_requirement"] == "stack.trace-backend"
    assert probe["redaction"]["raw_prompt_payloads_stored"] is False
    assert probe["redaction"]["raw_message_payloads_stored"] is False
    assert probe["redaction"]["raw_tool_payloads_stored"] is False
    assert probe["redaction"]["raw_trace_payloads_stored"] is False
    assert "must-not-store-prompt-body" not in abyss_machine_module.json.dumps(probe)


def test_self_awareness_langchain_requirement_tracks_runtime_shape_without_false_closure(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.langchain-api.graph-observability",
        "LangChain graph observability",
        reason="fixture runtime routes are live but replay inventory and trace backend are absent",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5403/openapi.json"}]},
        expected_shape={"mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    langchain_api = {
        "schema": "abyss_machine_stack_langchain_api_probe_v1",
        "base_url": "http://127.0.0.1:5403",
        "ok": True,
        "health": {
            "url": "http://127.0.0.1:5403/health",
            "ok": True,
            "status_code": 200,
            "service": "langchain-api",
            "embeddings_provider": "ovms",
            "ovms_auth_enabled": True,
            "federated_run_enabled": True,
        },
        "openapi": {
            "url": "http://127.0.0.1:5403/openapi.json",
            "ok": True,
            "status_code": 200,
            "path_count": 4,
            "paths": [
                {"path": "/health", "methods": ["GET"]},
                {"path": "/run", "methods": ["POST"]},
                {"path": "/run/federated", "methods": ["POST"]},
                {"path": "/embeddings", "methods": ["POST"]},
            ],
            "runtime_request_schema_names": ["EmbeddingsReq", "FederatedRunReq", "RunReq"],
        },
        "runtime_surface": {
            "service": "langchain-api",
            "embeddings_provider": "ovms",
            "ovms_auth_enabled": True,
            "federated_run_enabled": True,
            "run_route_present": True,
            "federated_run_route_present": True,
            "embeddings_route_present": True,
            "runtime_request_schema_names": ["EmbeddingsReq", "FederatedRunReq", "RunReq"],
            "usable_runtime_surface": True,
        },
        "route_classes": {
            "run_paths": [{"path": "/run", "methods": ["POST"]}],
            "federated_run_paths": [{"path": "/run/federated", "methods": ["POST"]}],
            "embeddings_paths": [{"path": "/embeddings", "methods": ["POST"]}],
            "thread_paths": [],
            "checkpoint_paths": [],
            "trace_paths": [],
        },
        "replay_inventory": {
            "thread_inventory_present": False,
            "checkpoint_inventory_present": False,
            "trace_inventory_present": False,
            "inventory_complete": False,
            "missing_inventory": ["threads", "checkpoints", "traces"],
        },
        "trace_backend_coupling": {
            "required_for_trace_join": True,
            "candidate_ready_url": "http://127.0.0.1:3200/ready",
            "stack_owned_trace_backend_requirement": "stack.trace-backend",
        },
        "observability": {
            "health_readable": True,
            "openapi_readable": True,
            "runtime_surface_usable": True,
            "thread_inventory_present": False,
            "checkpoint_inventory_present": False,
            "trace_inventory_present": False,
            "missing_replay_inventory": ["threads", "checkpoints", "traces"],
            "graph_observability_complete": False,
        },
        "evidence_refs": [{"url": "http://127.0.0.1:5403/openapi.json", "status_code": 200}],
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {
            "langchain_api": langchain_api,
            "tempo_ready": {
                "ok": False,
                "url": "http://127.0.0.1:3200/ready",
                "error": "connection refused",
            },
        },
        "capabilities": [],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    current = probe["current_state"]
    assert probe["id"] == "stack.langchain-api.graph-observability"
    assert probe["status"] == "open"
    assert probe["closed_by_current_probe"] is False
    assert current["api_health_ok"] is True
    assert current["openapi_ok"] is True
    assert current["health_service"] == "langchain-api"
    assert current["embeddings_provider"] == "ovms"
    assert current["ovms_auth_enabled"] is True
    assert current["federated_run_enabled"] is True
    assert current["run_route_present"] is True
    assert current["federated_run_route_present"] is True
    assert current["embeddings_route_present"] is True
    assert current["runtime_surface_usable"] is True
    assert current["thread_inventory_present"] is False
    assert current["checkpoint_inventory_present"] is False
    assert current["trace_inventory_present"] is False
    assert current["missing_replay_inventory"] == ["threads", "checkpoints", "traces"]
    assert current["trace_backend_ready"] is False
    required_fields = probe["acceptance_contract"]["probe_plan"]["required_fields"]
    assert "run_routes" in required_fields
    assert "federated_run_routes" in required_fields
    assert "embeddings_routes" in required_fields
    assert "trace_backend_coupling" in required_fields
    checks = {check["key"]: check for check in probe["checks"]}
    assert checks["langchain_api_health_readable"]["ok"] is True
    assert checks["langchain_api_openapi_readable"]["ok"] is True
    assert checks["langchain_runtime_routes_readable"]["ok"] is True
    assert checks["langchain_trace_backend_coupled"]["level"] == "open"
    assert checks["langchain_langgraph_inventory_readable"]["level"] == "open"
    assert checks["host_layer_non_mutating"]["ok"] is True
    assert checks["no_secret_leakage"]["ok"] is True


def test_self_awareness_grafana_datasource_probe_sanitizes_inventory_and_candidates(
    abyss_machine_module,
    monkeypatch,
) -> None:
    def fake_http(url: str, timeout: float = 1.5, max_bytes: int = 262144, method: str = "GET") -> dict:
        del timeout, max_bytes, method
        return {
            "ok": False,
            "url": url,
            "status_code": 401,
            "error": "HTTP Error 401: Unauthorized",
        }

    monkeypatch.setattr(abyss_machine_module, "memory_orchestrate_http_json", fake_http)
    grafana_health = {
        "ok": True,
        "url": "http://127.0.0.1:3000/api/health",
        "status_code": 200,
        "json": {"database": "ok", "version": "13.0.1", "commit": "a100054f"},
    }
    grafana_datasources = {
        "ok": True,
        "url": "http://127.0.0.1:3000/api/datasources",
        "status_code": 200,
        "json": [
            {
                "id": 1,
                "uid": "prom",
                "name": "Prometheus",
                "type": "prometheus",
                "access": "proxy",
                "url": "http://user:secret@prometheus:9090",
                "isDefault": True,
                "basicAuth": True,
                "jsonData": {"httpMethod": "POST"},
                "secureJsonData": {"basicAuthPassword": "must-not-store"},
            }
        ],
    }
    stack = {
        "schema": "abyss_machine_stack_observability_v1",
        "summary": {"promql_jobs_up": ["prometheus", "loki"]},
        "loki": {"ready": {"ok": True}},
    }
    alertmanager = {"ok": True}
    trace_backend = {"join_readiness": {"trace_backend_ready": False}}

    probe = abyss_machine_module.self_awareness_grafana_datasource_probe(
        grafana_health,
        grafana_datasources,
        stack,
        alertmanager,
        trace_backend,
    )

    assert probe["schema"] == "abyss_machine_stack_grafana_datasource_probe_v1"
    assert probe["health"]["version"] == "13.0.1"
    assert probe["datasource_inventory"]["present"] is True
    entry = probe["datasource_inventory"]["entries"][0]
    assert entry["url"] == "http://prometheus:9090"
    assert entry["json_data_keys"] == ["httpMethod"]
    assert {item["type"] for item in probe["inferred_datasource_candidates"]} >= {"prometheus", "loki", "alertmanager", "tempo"}
    assert probe["handoff"]["inferred_candidates_are_not_inventory"] is True
    assert probe["redaction"]["secure_json_data_stored"] is False
    assert probe["redaction"]["tokens_stored"] is False
    payload = abyss_machine_module.json.dumps(probe)
    assert "must-not-store" not in payload
    assert "secret@" not in payload


def test_self_awareness_grafana_requirement_uses_health_and_candidates_without_false_closure(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.grafana.datasource-read",
        "Grafana datasource read",
        reason="fixture health and candidates are live but datasource inventory is auth-denied",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3000/api/datasources"}]},
        expected_shape={"mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    grafana_probe = {
        "schema": "abyss_machine_stack_grafana_datasource_probe_v1",
        "health": {
            "url": "http://127.0.0.1:3000/api/health",
            "ok": True,
            "status_code": 200,
            "database": "ok",
            "version": "13.0.1",
        },
        "api_access": {
            "routes": {
                "datasources": {"url": "http://127.0.0.1:3000/api/datasources", "ok": False, "status_code": 401, "error": "Unauthorized"},
                "search": {"url": "http://127.0.0.1:3000/api/search", "ok": False, "status_code": 401, "error": "Unauthorized"},
            },
            "denied_routes": ["datasources", "search"],
            "readable_routes": [],
            "datasource_api_auth_denied": True,
            "all_inventory_routes_denied": True,
        },
        "datasource_inventory": {"present": False, "count": 0, "entries": []},
        "inferred_datasource_candidates": [
            {"type": "prometheus", "source_readable": True, "closure_kind": "candidate_not_grafana_inventory"},
            {"type": "loki", "source_readable": True, "closure_kind": "candidate_not_grafana_inventory"},
        ],
        "handoff": {
            "stack_owned_inventory_required": True,
            "inferred_candidates_are_not_inventory": True,
        },
        "evidence_refs": [{"url": "http://127.0.0.1:3000/api/datasources", "status_code": 401}],
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {
            "grafana_datasource_inventory": grafana_probe,
            "grafana_datasources": {"ok": False, "url": "http://127.0.0.1:3000/api/datasources", "status_code": 401, "error": "Unauthorized"},
        },
        "capabilities": [],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    current = probe["current_state"]
    assert probe["id"] == "stack.grafana.datasource-read"
    assert probe["status"] == "open"
    assert probe["closed_by_current_probe"] is False
    assert current["health_ok"] is True
    assert current["grafana_version"] == "13.0.1"
    assert current["datasource_api_auth_denied"] is True
    assert current["datasource_inventory_present"] is False
    assert current["inferred_datasource_candidate_types"] == ["loki", "prometheus"]
    required_fields = probe["acceptance_contract"]["probe_plan"]["required_fields"]
    assert "grafana.version" in required_fields
    assert "inferred_candidates" in required_fields
    assert "datasource_uid_or_id" in required_fields
    checks = {check["key"]: check for check in probe["checks"]}
    assert checks["grafana_health_readable"]["ok"] is True
    assert checks["grafana_datasource_candidates_inferred"]["ok"] is True
    assert checks["grafana_datasource_api_auth_denied"]["ok"] is True
    assert checks["grafana_datasource_inventory_readable"]["level"] == "open"
    assert checks["host_layer_non_mutating"]["ok"] is True
    assert checks["no_secret_leakage"]["ok"] is True


def test_self_awareness_trace_backend_probe_summarizes_pipeline_without_payloads(
    abyss_machine_module,
    monkeypatch,
) -> None:
    def fake_http(url: str, timeout: float = 1.5, max_bytes: int = 262144, method: str = "GET") -> dict:
        del timeout, max_bytes, method
        assert url == "http://127.0.0.1:3200/api/search?limit=1"
        return {
            "ok": False,
            "url": url,
            "status_code": None,
            "error": "connection refused",
        }

    monkeypatch.setattr(abyss_machine_module, "memory_orchestrate_http_json", fake_http)
    stack = {
        "schema": "abyss_machine_stack_observability_v1",
        "summary": {
            "promql_jobs_up": ["prometheus", "grafana", "loki", "alloy"],
            "logql_entries_seen": 4,
        },
        "alloy": {"prometheus_value": "1"},
        "loki": {
            "ready": {"ok": True},
            "labels": {"ok": True, "label_count": 3, "labels": ["container", "job", "source"]},
            "trace_context": {
                "ok": True,
                "query": "{container=\"route-api\"} |= \"traceparent\"",
                "entry_count": 0,
                "samples": [{"ts": "1", "line_hash": "abc", "line_preview": "must-not-store-raw-log", "labels": {"container": "route-api"}}],
            },
        },
    }
    tempo_ready = {
        "ok": False,
        "url": "http://127.0.0.1:3200/ready",
        "status_code": None,
        "error": "connection refused",
    }

    probe = abyss_machine_module.self_awareness_trace_backend_probe(tempo_ready, stack)

    assert probe["schema"] == "abyss_machine_stack_trace_backend_probe_v1"
    assert probe["pipeline_evidence"]["alloy_seen"] is True
    assert probe["pipeline_evidence"]["metrics_log_pipeline_readable"] is True
    assert probe["trace_context"]["traceparent_log_query_ok"] is True
    assert probe["trace_context"]["trace_context_query_safe_empty"] is True
    assert probe["join_readiness"]["trace_backend_ready"] is False
    assert probe["join_readiness"]["trace_search_readable"] is False
    assert probe["join_readiness"]["span_log_metric_join_supported"] is False
    assert probe["redaction"]["raw_span_payloads_stored"] is False
    assert probe["redaction"]["raw_log_exports_stored"] is False
    assert probe["policy"]["host_layer_mutates_stack"] is False
    assert "must-not-store-raw-log" not in abyss_machine_module.json.dumps(probe)


def test_self_awareness_trace_backend_probe_accepts_plain_http_ready(
    abyss_machine_module,
    monkeypatch,
) -> None:
    def fake_http(url: str, timeout: float = 1.5, max_bytes: int = 262144, method: str = "GET") -> dict:
        del timeout, max_bytes, method
        assert url == "http://127.0.0.1:3200/api/search?limit=1"
        return {"ok": True, "url": url, "status_code": 200, "data": {"traces": []}}

    monkeypatch.setattr(abyss_machine_module, "memory_orchestrate_http_json", fake_http)
    stack = {
        "schema": "abyss_machine_stack_observability_v1",
        "summary": {"promql_jobs_up": ["prometheus", "loki", "alloy"], "logql_entries_seen": 1},
        "alloy": {"prometheus_value": "1"},
        "loki": {
            "ready": {"ok": True},
            "labels": {"ok": True, "labels": ["source"]},
            "trace_context": {"ok": True, "entry_count": 0},
        },
    }
    tempo_ready = {
        "ok": False,
        "url": "http://127.0.0.1:3200/ready",
        "status_code": 200,
        "error": "invalid JSON: Expecting value",
    }

    probe = abyss_machine_module.self_awareness_trace_backend_probe(tempo_ready, stack)

    assert probe["backend"]["ready"]["ok"] is True
    assert probe["backend"]["ready"]["error"] is None
    assert probe["backend"]["ready"]["accepted_by_http_status"] is True
    assert probe["join_readiness"]["trace_backend_ready"] is True
    assert probe["join_readiness"]["trace_search_readable"] is True
    assert probe["join_readiness"]["span_log_metric_join_supported"] is True
    assert probe["join_readiness"]["missing"] == []


def test_self_awareness_trace_requirement_uses_pipeline_evidence_without_false_closure(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is absent but metric/log pipeline is readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    trace_backend = {
        "schema": "abyss_machine_stack_trace_backend_probe_v1",
        "backend": {
            "ready": {"url": "http://127.0.0.1:3200/ready", "ok": False, "status_code": None, "error": "connection refused"},
            "search": {"url": "http://127.0.0.1:3200/api/search?limit=1", "ok": False, "status_code": None, "error": "connection refused"},
        },
        "pipeline_evidence": {
            "prometheus_jobs_up": ["prometheus", "grafana", "loki", "alloy"],
            "alloy_seen": True,
            "alloy_prometheus_value": "1",
            "loki_ready": True,
            "loki_labels_readable": True,
            "logql_entries_seen": 2,
            "metrics_log_pipeline_readable": True,
        },
        "trace_context": {
            "traceparent_log_query": "{container=\"route-api\"} |= \"traceparent\"",
            "traceparent_log_query_ok": True,
            "traceparent_log_entries_seen": 0,
            "trace_context_query_safe_empty": True,
        },
        "join_readiness": {
            "trace_backend_ready": False,
            "trace_search_readable": False,
            "traceparent_queryable_in_logs": True,
            "span_log_metric_join_supported": False,
            "explicit_empty_traceparent_result": True,
            "missing": ["trace_backend_ready", "trace_search_readable", "span_log_metric_join_supported"],
        },
        "evidence_refs": [{"url": "http://127.0.0.1:3200/ready", "probe": "tempo_ready"}],
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {
            "trace_backend": trace_backend,
            "tempo_ready": {"ok": False, "url": "http://127.0.0.1:3200/ready", "error": "connection refused"},
        },
        "capabilities": [],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    current = probe["current_state"]
    assert probe["id"] == "stack.trace-backend"
    assert probe["status"] == "open"
    assert probe["closed_by_current_probe"] is False
    assert current["metrics_log_pipeline_readable"] is True
    assert current["traceparent_log_query_ok"] is True
    assert current["trace_context_query_safe_empty"] is True
    assert current["trace_backend_ready"] is False
    assert current["trace_search_readable"] is False
    assert current["span_log_metric_join_supported"] is False
    required_fields = probe["acceptance_contract"]["probe_plan"]["required_fields"]
    assert "alloy_pipeline_status" in required_fields
    assert "loki_traceparent_query_status" in required_fields
    checks = {check["key"]: check for check in probe["checks"]}
    assert checks["trace_pipeline_evidence_readable"]["ok"] is True
    assert checks["traceparent_log_context_queryable"]["ok"] is True
    assert checks["trace_backend_ready"]["level"] == "open"
    assert checks["trace_span_search_readable"]["level"] == "open"
    assert checks["span_log_metric_join_supported"]["level"] == "open"
    assert checks["host_layer_non_mutating"]["ok"] is True
    assert checks["no_secret_leakage"]["ok"] is True


def test_self_awareness_trace_context_fallback_exposes_links_without_false_stack_closure(
    abyss_machine_module,
) -> None:
    stack_observability = {
        "schema": "abyss_machine_stack_observability_v1",
        "summary": {
            "promql_jobs_up": ["prometheus", "grafana", "loki", "alloy"],
            "logql_queries_ok": 2,
            "logql_entries_seen": 4,
        },
        "loki": {
            "trace_context": {
                "ok": True,
                "query": "{container=\"route-api\"} |= \"traceparent\"",
                "entry_count": 0,
                "samples": [
                    {
                        "ts": "1",
                        "labels": {"container": "route-api"},
                        "line_hash": "abc123",
                        "line_preview": "raw log line must not be stored",
                    }
                ],
            },
        },
    }
    requirement_probes = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "probes": [
            {
                "id": "stack.trace-backend",
                "requirement_id": "stack.trace-backend",
                "owner": "abyss-stack",
                "status": "open",
                "closed_by_current_probe": False,
                "probe_kind": "trace_backend_inventory",
                "current_state": {
                    "metrics_log_pipeline_readable": True,
                    "alloy_seen": True,
                    "traceparent_log_query_ok": True,
                    "traceparent_log_entries_seen": 0,
                    "trace_context_query_safe_empty": True,
                    "trace_backend_ready": False,
                    "trace_search_readable": False,
                    "span_log_metric_join_supported": False,
                },
                "checks": [
                    {"key": "trace_pipeline_evidence_readable", "ok": True, "level": "ok", "message": "fixture"},
                    {"key": "trace_backend_ready", "ok": False, "level": "open", "message": "fixture"},
                ],
                "closure_readiness": {
                    "schema": "abyss_machine_stack_handoff_closure_readiness_v1",
                    "missing_checks": ["trace_backend_ready", "trace_search_readable", "span_log_metric_join_supported"],
                    "blocking_check_keys": ["trace_backend_ready"],
                    "safe_next_action": {"requires_human_approval": True, "host_layer_mutates_stack": False},
                },
            }
        ],
    }
    probe = {
        "schema": "abyss_machine_self_awareness_probe_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "run_id": "saprobe-fixture",
        "traceparent": "00-" + ("a" * 32) + "-" + ("b" * 16) + "-01",
    }
    context = {
        "schema": "abyss_machine_self_awareness_context_v1",
        "contexts": [
            {
                "key": "trace_id:" + ("a" * 32),
                "context": {
                    "traceparent": probe["traceparent"],
                    "trace_id": "a" * 32,
                    "span_id": "b" * 16,
                    "synthetic_run_id": "saprobe-fixture",
                },
            }
        ],
    }

    payload = abyss_machine_module.self_awareness_trace_context_fallback(
        write_latest=False,
        stack_observability_doc=stack_observability,
        requirement_probes_doc=requirement_probes,
        probe_doc=probe,
        context_doc=context,
        timeline_doc={"schema": "abyss_machine_self_awareness_timeline_v1", "events": []},
        episodes_doc={"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": []},
    )

    assert payload["schema"] == "abyss_machine_self_awareness_trace_context_fallback_v1"
    assert payload["ok"] is True
    assert payload["status"] == "fallback_ready_stack_trace_backend_open"
    assert payload["stack_requirement_id"] == "stack.trace-backend"
    assert payload["closes_stack_requirement"] is False
    assert payload["summary"]["traceparent_log_query_ok"] is True
    assert payload["summary"]["trace_backend_ready"] is False
    assert payload["summary"]["span_log_metric_join_supported"] is False
    assert payload["summary"]["stack_requirement_not_closed_by_fallback"] is True
    assert payload["fallback"]["loki_trace_context"]["raw_log_exports_stored"] is False
    assert payload["fallback"]["loki_trace_context"]["samples"][0]["line_hash"] == "abc123"
    assert "raw log line must not be stored" not in abyss_machine_module.json.dumps(payload)
    assert payload["safe_next_action"]["owner_route"] == "abyss-stack"
    assert payload["safe_next_action"]["host_layer_mutates_stack"] is False
    assert payload["policy"]["closes_stack_requirement"] is False
    assert payload["policy"]["adds_loki_labels"] is False
    assert payload["policy"]["raw_span_payloads_stored"] is False
    assert payload["policy"]["raw_log_exports_stored"] is False
    assert abyss_machine_module.self_awareness_trace_context_fallback_complete(payload) is True


def test_self_awareness_trace_context_fallback_routes_to_next_open_requirement_after_trace_closes(
    abyss_machine_module,
) -> None:
    stack_observability = {
        "schema": "abyss_machine_stack_observability_v1",
        "summary": {
            "promql_jobs_up": ["prometheus", "grafana", "loki", "alloy"],
            "logql_queries_ok": 1,
            "logql_entries_seen": 2,
        },
        "loki": {"trace_context": {"ok": True, "entry_count": 1, "samples": []}},
    }
    requirement_probes = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "open_requirements": [
            {
                "id": "stack.grafana.datasource-read",
                "owner": "abyss-stack",
                "summary": "Expose bounded Grafana datasource inventory",
                "safe_next_action": {
                    "owner_route": "abyss-stack",
                    "requirement_id": "stack.grafana.datasource-read",
                    "command": "abyss-machine self-awareness requirement-probes --json",
                    "stack_command_candidate": "expose bounded Grafana datasource inventory",
                    "requires_human_approval": True,
                    "host_layer_mutates_stack": False,
                    "executes_commands": False,
                    "automatic": False,
                },
            },
            {"id": "stack.database-graph.read-route", "owner": "abyss-stack"},
        ],
        "probes": [
            {
                "id": "stack.trace-backend",
                "requirement_id": "stack.trace-backend",
                "owner": "abyss-stack",
                "status": "closed_by_current_probe",
                "closed_by_current_probe": True,
                "probe_kind": "trace_backend_inventory",
                "current_state": {
                    "metrics_log_pipeline_readable": True,
                    "traceparent_log_query_ok": True,
                    "traceparent_log_entries_seen": 1,
                    "trace_backend_ready": True,
                    "trace_search_readable": True,
                    "span_log_metric_join_supported": True,
                },
                "checks": [],
                "closure_readiness": {"missing_checks": []},
            }
        ],
    }

    payload = abyss_machine_module.self_awareness_trace_context_fallback(
        write_latest=False,
        stack_observability_doc=stack_observability,
        requirement_probes_doc=requirement_probes,
        probe_doc={"schema": "abyss_machine_self_awareness_probe_v1", "ok": True},
        context_doc={"schema": "abyss_machine_self_awareness_context_v1", "contexts": []},
        timeline_doc={"schema": "abyss_machine_self_awareness_timeline_v1", "events": []},
        episodes_doc={"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": []},
    )

    assert payload["status"] == "stack_trace_backend_ready_observed"
    assert payload["safe_next_action"]["requirement_id"] == "stack.grafana.datasource-read"
    assert payload["summary"]["next_open_stack_requirement_id"] == "stack.grafana.datasource-read"
    assert payload["safe_next_action"]["host_layer_mutates_stack"] is False
    assert payload["safe_next_action"]["executes_commands"] is False


def test_self_awareness_probe_resource_preflight_denies_before_stack_calls(monkeypatch, abyss_machine_module) -> None:
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_proc_meminfo_bytes",
        lambda: {
            "MemAvailable": 512 * 1024 * 1024,
            "SwapTotal": 16 * 1024 * 1024 * 1024,
            "SwapFree": 0,
        },
    )
    monkeypatch.setattr(abyss_machine_module.os, "getloadavg", lambda: (0.0, 0.0, 0.0))

    def forbidden_stack_call(*_args, **_kwargs):
        raise AssertionError("resource-denied probe must not call stack HTTP")

    monkeypatch.setattr(abyss_machine_module, "self_awareness_http_status_with_headers", forbidden_stack_call)

    payload = abyss_machine_module.self_awareness_probe(write_latest=False)

    assert payload["schema"] == "abyss_machine_self_awareness_probe_v1"
    assert payload["ok"] is False
    assert payload["status"] == "resource_denied"
    assert payload["summary"]["resource_guard_ok"] is False
    assert set(payload["resource_preflight"]["denial_reasons"]) == {
        "mem_available_below_floor",
        "swap_free_below_floor",
    }


def test_self_awareness_cycle_resource_preflight_denies_before_probe(monkeypatch, abyss_machine_module) -> None:
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_proc_meminfo_bytes",
        lambda: {
            "MemAvailable": 512 * 1024 * 1024,
            "SwapTotal": 16 * 1024 * 1024 * 1024,
            "SwapFree": 0,
        },
    )
    monkeypatch.setattr(abyss_machine_module.os, "getloadavg", lambda: (0.0, 0.0, 0.0))

    def forbidden_probe(*_args, **_kwargs):
        raise AssertionError("resource-denied cycle must not call probe")

    monkeypatch.setattr(abyss_machine_module, "self_awareness_probe", forbidden_probe)

    payload = abyss_machine_module.self_awareness_cycle(write_latest=False)

    assert payload["schema"] == "abyss_machine_self_awareness_cycle_v1"
    assert payload["ok"] is False
    assert payload["status"] == "resource_denied"
    assert payload["summary"]["resource_guard_ok"] is False
    assert set(payload["resource_preflight"]["denial_reasons"]) == {
        "mem_available_below_floor",
        "swap_free_below_floor",
    }


def test_self_awareness_validate_probe_refresh_is_explicit(abyss_machine_module) -> None:
    signature = inspect.signature(abyss_machine_module.self_awareness_validate)

    assert signature.parameters["allow_probe_refresh"].default is False


def test_self_awareness_stack_closure_external_evidence_accepts_only_bounded_stack_rows(
    abyss_machine_module,
    tmp_path,
) -> None:
    config_path = tmp_path / "stack-closure-evidence.json"
    config_path.write_text(
        abyss_machine_module.json.dumps(
            {
                "entries": [
                    {
                        "schema": "abyss_machine_stack_requirement_closure_evidence_v1",
                        "requirement_id": "stack.trace-backend",
                        "owner_route": "abyss-stack",
                        "checks": {
                            "trace_backend_ready": True,
                            "trace_span_search_readable": True,
                            "span_log_metric_join_supported": True,
                        },
                        "current_state": {
                            "trace_backend_ready": True,
                            "trace_search_readable": True,
                            "span_log_metric_join_supported": True,
                            "private_payload": "must-not-pass-through",
                        },
                        "evidence_refs": [
                            {
                                "path": "/srv/abyss-stack/exports/trace-backend.json",
                                "schema": "abyss_machine_stack_requirement_closure_evidence_v1",
                                "sha256": "abc123",
                            }
                        ],
                        "policy": {
                            "read_only": True,
                            "bounded": True,
                            "host_layer_mutates_stack": False,
                            "raw_payloads_included": False,
                            "raw_secrets_included": False,
                        },
                    },
                    {
                        "schema": "abyss_machine_stack_requirement_closure_evidence_v1",
                        "requirement_id": "stack.grafana.datasource-read",
                        "owner_route": "abyss-stack",
                        "checks": {"grafana_datasource_inventory_readable": True},
                        "current_state": {"datasource_inventory_present": True, "datasource_inventory_count": 4},
                        "policy": {
                            "read_only": True,
                            "bounded": True,
                            "host_layer_mutates_stack": False,
                            "raw_payloads_included": False,
                            "raw_secrets_included": True,
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = abyss_machine_module.self_awareness_stack_closure_external_evidence(config_path)

    assert payload["schema"] == "abyss_machine_self_awareness_stack_closure_external_evidence_v1"
    assert payload["ok"] is True
    assert payload["status"] == "loaded"
    assert payload["summary"]["entries"] == 2
    assert payload["summary"]["accepted"] == 1
    assert payload["summary"]["rejected"] == 1
    assert payload["policy"]["host_layer_mutates_stack"] is False
    trace_row = payload["entries"]["stack.trace-backend"]
    assert trace_row["accepted"] is True
    assert trace_row["checks"]["span_log_metric_join_supported"] is True
    assert trace_row["current_state"]["trace_backend_ready"] is True
    assert "private_payload" not in trace_row["current_state"]
    assert trace_row["evidence_refs"][0]["path"].endswith("trace-backend.json")
    grafana_row = payload["entries"]["stack.grafana.datasource-read"]
    assert grafana_row["accepted"] is False
    assert grafana_row["checks"] == {}
    assert "policy" in grafana_row["rejection_reasons"]


def test_self_awareness_requirement_probes_accept_stack_closure_external_evidence(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is closed by bounded stack evidence",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    trace_backend = {
        "schema": "abyss_machine_stack_trace_backend_probe_v1",
        "backend": {
            "ready": {"url": "http://127.0.0.1:3200/ready", "ok": False, "status_code": None, "error": "connection refused"},
            "search": {"url": "http://127.0.0.1:3200/api/search?limit=1", "ok": False, "status_code": None, "error": "connection refused"},
        },
        "pipeline_evidence": {
            "alloy_seen": True,
            "loki_ready": True,
            "loki_labels_readable": True,
            "logql_entries_seen": 2,
            "metrics_log_pipeline_readable": True,
        },
        "trace_context": {
            "traceparent_log_query_ok": True,
            "traceparent_log_entries_seen": 1,
            "trace_context_query_safe_empty": False,
        },
        "join_readiness": {
            "trace_backend_ready": False,
            "trace_search_readable": False,
            "span_log_metric_join_supported": False,
            "missing": ["trace_backend_ready", "trace_search_readable", "span_log_metric_join_supported"],
        },
        "evidence_refs": [{"fixture": "trace_backend"}],
    }
    external_evidence = {
        "schema": "abyss_machine_self_awareness_stack_closure_external_evidence_v1",
        "entries": {
            "stack.trace-backend": {
                "schema": "abyss_machine_self_awareness_stack_closure_external_evidence_row_v1",
                "requirement_id": "stack.trace-backend",
                "accepted": True,
                "rejection_reasons": [],
                "checks": {
                    "trace_backend_ready": True,
                    "trace_span_search_readable": True,
                    "span_log_metric_join_supported": True,
                },
                "current_state": {
                    "trace_backend_ready": True,
                    "trace_search_readable": True,
                    "span_log_metric_join_supported": True,
                },
                "evidence_refs": [
                    {
                        "path": "/srv/abyss-stack/exports/trace-backend.json",
                        "schema": "abyss_machine_stack_requirement_closure_evidence_v1",
                    }
                ],
                "source": {"config_path": "/etc/abyss-machine/self-awareness-stack-closure-evidence.json"},
                "policy": {"read_only": True, "host_layer_mutates_stack": False},
            }
        },
        "policy": {"read_only": True, "host_layer_mutates_stack": False},
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {
            "trace_backend": trace_backend,
            "tempo_ready": {"ok": False, "url": "http://127.0.0.1:3200/ready", "error": "connection refused"},
            "stack_closure_external_evidence": external_evidence,
        },
        "capabilities": [],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    current = probe["current_state"]
    checks = {check["key"]: check for check in probe["checks"]}
    assert payload["status"] == "satisfied"
    assert payload["summary"]["open"] == 0
    assert payload["summary"]["closed_by_current_probe"] == 1
    assert probe["status"] == "closed"
    assert probe["closed_by_current_probe"] is True
    assert current["external_closure_evidence_present"] is True
    assert current["external_closure_evidence_accepted"] is True
    assert current["trace_backend_ready"] is True
    assert current["trace_search_readable"] is True
    assert current["span_log_metric_join_supported"] is True
    assert current["join_missing"] == []
    assert checks["trace_backend_ready"]["ok"] is True
    assert checks["trace_span_search_readable"]["ok"] is True
    assert checks["span_log_metric_join_supported"]["ok"] is True
    assert checks["host_layer_non_mutating"]["ok"] is True
    assert checks["no_secret_leakage"]["ok"] is True
    assert probe["closure_readiness"]["status"] == "closed"
    assert probe["closure_readiness"]["open_blocker_count"] == 0
    assert probe["host_layer_mutates_stack"] is False
    assert any(ref.get("path", "").endswith("trace-backend.json") for ref in probe["evidence_refs"])
    assert payload["closed_requirements"][0]["id"] == "stack.trace-backend"


def test_self_awareness_requirements_with_probe_readiness_closes_handoff_rows(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.grafana.datasource-read",
        "Grafana datasource read route",
        reason="fixture datasource inventory is closed by bounded stack evidence",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5402/observability/datasources"}]},
        expected_shape={"mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    probes = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "summary": {"open": 0, "closed_by_current_probe": 1},
        "probes": [
            {
                "schema": "abyss_machine_self_awareness_requirement_probe_v1",
                "id": "stack.grafana.datasource-read",
                "requirement_id": "stack.grafana.datasource-read",
                "owner": "abyss-stack",
                "status": "closed",
                "closed_by_current_probe": True,
                "probe_kind": "grafana_datasource_inventory",
                "current_state": {
                    "datasource_inventory_present": True,
                    "datasource_inventory_count": 3,
                    "datasource_types": ["loki", "prometheus", "tempo"],
                },
                "closure_readiness": {
                    "status": "closed",
                    "readiness_score": 1.0,
                    "fulfilled_check_count": 3,
                    "open_blocker_count": 0,
                    "missing_checks": [],
                    "fulfilled_checks": [
                        {"key": "grafana_datasource_inventory_readable", "ok": True, "level": "ok"},
                        {"key": "grafana_datasource_inventory_redacted", "ok": True, "level": "ok"},
                        {"key": "host_layer_non_mutating", "ok": True, "level": "ok"},
                    ],
                    "blocking_check_keys": [],
                    "dependency_requirement_ids": [],
                    "verifier_commands": ["abyss-machine self-awareness requirement-probes --json"],
                    "safe_next_action": {
                        "owner_route": "abyss-stack",
                        "requirement_id": "stack.grafana.datasource-read",
                        "host_layer_mutates_stack": False,
                        "executes_commands": False,
                    },
                },
                "evidence_refs": [
                    {
                        "path": "/var/lib/abyss-machine/self-awareness/requirement-probes/latest.json",
                        "requirement_id": "stack.grafana.datasource-read",
                    }
                ],
            }
        ],
    }

    enriched = abyss_machine_module.self_awareness_requirements_with_probe_readiness(document, probes)

    assert enriched["summary"]["open_stack_requirements"] == 0
    assert enriched["summary"]["closed_stack_requirements"] == 1
    assert enriched["open_stack_ids"] == []
    assert enriched["open_stack_requirement_ids"] == []
    assert enriched["closed_stack_ids"] == ["stack.grafana.datasource-read"]
    assert enriched["closed_stack_requirement_ids"] == ["stack.grafana.datasource-read"]
    for row in (enriched["requirements"][0], enriched["stack_handoff"][0]):
        assert row["status"] == "closed"
        assert row["probe_status"] == "closed"
        assert row["closed_by_current_probe"] is True
        assert row["closure_readiness"]["status"] == "closed"
        assert row["current_state"]["datasource_inventory_present"] is True
        assert row["current_state_digest"]["has_current_state"] is True
        assert row["evidence_refs"][0]["requirement_id"] == "stack.grafana.datasource-read"
        assert abyss_machine_module.SELF_AWARENESS_SECRET_RE.search(
            abyss_machine_module.json.dumps(row)
        ) is None


def test_self_awareness_requirement_probes_reject_unaccepted_stack_closure_external_evidence(
    abyss_machine_module,
) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture rejected stack evidence must not close the blocker",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {
            "trace_backend": {
                "schema": "abyss_machine_stack_trace_backend_probe_v1",
                "backend": {
                    "ready": {"url": "http://127.0.0.1:3200/ready", "ok": False, "error": "connection refused"},
                    "search": {"url": "http://127.0.0.1:3200/api/search?limit=1", "ok": False, "error": "connection refused"},
                },
                "pipeline_evidence": {"metrics_log_pipeline_readable": True},
                "trace_context": {"traceparent_log_query_ok": True},
                "join_readiness": {
                    "trace_backend_ready": False,
                    "trace_search_readable": False,
                    "span_log_metric_join_supported": False,
                    "missing": ["trace_backend_ready", "trace_search_readable", "span_log_metric_join_supported"],
                },
            },
            "stack_closure_external_evidence": {
                "schema": "abyss_machine_self_awareness_stack_closure_external_evidence_v1",
                "entries": {
                    "stack.trace-backend": {
                        "schema": "abyss_machine_self_awareness_stack_closure_external_evidence_row_v1",
                        "requirement_id": "stack.trace-backend",
                        "accepted": False,
                        "rejection_reasons": ["policy"],
                        "checks": {},
                        "current_state": {},
                        "evidence_refs": [{"path": "/srv/abyss-stack/exports/rejected-trace.json"}],
                        "source": {"config_path": "/etc/abyss-machine/self-awareness-stack-closure-evidence.json"},
                        "policy": {"read_only": True, "host_layer_mutates_stack": False},
                    }
                },
            },
        },
        "capabilities": [],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    current = probe["current_state"]
    checks = {check["key"]: check for check in probe["checks"]}
    assert payload["status"] == "open_requirements"
    assert probe["status"] == "open"
    assert probe["closed_by_current_probe"] is False
    assert current["external_closure_evidence_present"] is True
    assert current["external_closure_evidence_accepted"] is False
    assert current["external_closure_evidence_rejection_reasons"] == ["policy"]
    assert current["trace_backend_ready"] is False
    assert checks["trace_backend_ready"]["level"] == "open"
    assert checks["span_log_metric_join_supported"]["level"] == "open"
    assert checks["no_secret_leakage"]["ok"] is True


def test_self_awareness_requirement_probes_keep_stack_gaps_open_and_readonly(abyss_machine_module) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {
            "tempo_ready": {
                "ok": False,
                "url": "http://127.0.0.1:3200/ready",
                "status_code": None,
                "error": "connection refused",
            },
        },
        "capabilities": [],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    assert payload["schema"] == "abyss_machine_self_awareness_requirement_probes_v1"
    assert payload["ok"] is True
    assert payload["status"] == "open_requirements"
    assert payload["summary"]["probes"] == 1
    assert payload["summary"]["open"] == 1
    assert payload["summary"]["closed_by_current_probe"] == 0
    assert payload["summary"]["internal_contract_failures"] == []
    assert payload["summary"]["secret_leaks"] == 0
    assert payload["summary"]["mutating_routes"] == 0
    assert payload["summary"]["runbook_candidates"] == 1
    assert payload["summary"]["machine_closure_probes"] == 1
    assert payload["summary"]["acceptance_verifier_steps"] >= 1
    assert payload["summary"]["closure_readiness_packets"] == 1
    assert payload["summary"]["closure_readiness_missing_checks"] >= 1
    assert len(payload["closure_readiness"]) == 1
    assert len(payload["runbook_candidates"]) == 1

    probe = payload["probes"][0]
    assert probe["id"] == "stack.trace-backend"
    assert probe["status"] == "open"
    assert probe["stack_handoff"] is True
    assert probe["closed_by_current_probe"] is False
    assert probe["host_layer_mutates_stack"] is False
    assert probe["policy"]["handoff_only"] is True
    assert probe["policy"]["read_only"] is True
    assert probe["policy"]["host_layer_mutates_stack"] is False
    assert probe["policy"]["executes_commands"] is False
    assert probe["policy"]["action_execution"] is False
    assert probe["policy"]["raw_secrets_included"] is False
    assert probe["probe_kind"] == "trace_backend_inventory"
    assert probe["acceptance_contract"]["schema"] == "abyss_machine_stack_requirement_acceptance_contract_v1"
    assert probe["machine_closure_probe"]["kind"] == "trace_backend_inventory"
    assert "traceparent_supported" in probe["machine_closure_probe"]["required_fields"]
    assert probe["acceptance_verifiers"]
    assert probe["closure_semantics"]["host_layer_mutates_stack"] is False
    assert any(check["key"] == "trace_backend_ready" and check["level"] == "open" for check in probe["checks"])
    assert any(check["key"] == "no_secret_leakage" and check["ok"] is True for check in probe["checks"])
    assert any(check["key"] == "runbook_candidate_complete" and check["ok"] is True for check in probe["checks"])
    readiness = probe["closure_readiness"]
    assert readiness == payload["closure_readiness"][0]
    assert readiness["schema"] == "abyss_machine_stack_handoff_closure_readiness_v1"
    assert readiness["requirement_id"] == "stack.trace-backend"
    assert readiness["status"] == "open"
    assert readiness["readiness_score"] > 0
    assert readiness["fulfilled_checks"]
    assert readiness["missing_checks"]
    assert "trace_backend_ready" in readiness["blocking_check_keys"]
    assert readiness["open_blocker_count"] == len(readiness["missing_checks"])
    assert readiness["closure_evidence_needed"]
    assert readiness["verifier_commands"]
    assert readiness["safe_next_action"]["owner_route"] == "abyss-stack"
    assert readiness["safe_next_action"]["host_layer_mutates_stack"] is False
    assert readiness["policy"]["host_layer_mutates_stack"] is False
    assert readiness["policy"]["executes_commands"] is False
    runbook = probe["runbook_candidate"]
    assert runbook == payload["runbook_candidates"][0]
    assert runbook["schema"] == "abyss_machine_stack_requirement_runbook_candidate_v1"
    assert runbook["id"] == "stack-runbook-stack-trace-backend"
    assert runbook["requirement_id"] == "stack.trace-backend"
    assert runbook["owner_route"] == "abyss-stack"
    assert runbook["machine_action"] == "handoff_only"
    assert runbook["host_layer_mutates_stack"] is False
    assert runbook["machine_executes_stack_change"] is False
    assert runbook["stack_owner_may_mutate_stack"] is True
    assert runbook["operator_approval_required"] is True
    assert runbook["risk"]["risks"]
    assert runbook["blast_radius"]["affected_surfaces"]
    assert runbook["rollback"]["steps"]
    assert runbook["acceptance_steps"]
    assert runbook["acceptance_verifiers"]
    assert runbook["acceptance_verifiers"] == runbook["acceptance_steps"]
    assert runbook["evidence_refs"]
    assert payload["open_requirements"][0]["closure_readiness"]["requirement_id"] == "stack.trace-backend"
    assert payload["open_requirements"][0]["runbook_candidate_id"] == runbook["id"]
    assert payload["policy"]["open_stack_requirements_are_blockers_not_host_failures"] is True
    assert payload["policy"]["runbook_candidates_are_handoff_only"] is True

    enriched = abyss_machine_module.self_awareness_requirements_with_probe_readiness(document, payload)
    enriched_requirement = enriched["requirements"][0]
    enriched_handoff = enriched["stack_handoff"][0]
    assert enriched["open_stack_ids"] == ["stack.trace-backend"]
    assert enriched["open_stack_requirement_ids"] == ["stack.trace-backend"]
    assert enriched["summary"]["open_stack_requirements"] == 1
    assert enriched["summary"]["stack_handoff_acceptance_verifiers"] == 1
    assert enriched["summary"]["stack_handoff_acceptance_verifier_steps"] >= 1
    assert enriched["summary"]["stack_handoff_safe_next_actions"] == 1
    assert enriched["summary"]["stack_handoff_coverage_impact_entries"] == 1
    for item in (enriched_requirement, enriched_handoff):
        assert item["acceptance_contract"]["schema"] == "abyss_machine_stack_requirement_acceptance_contract_v1"
        assert item["machine_closure_probe"]["kind"] == "trace_backend_inventory"
        assert item["acceptance_verifiers"]
        assert item["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert item["safe_next_action"]["host_layer_mutates_stack"] is False
        assert item["current_state_digest"]["schema"] == "abyss_machine_self_awareness_requirement_current_state_digest_v1"
        assert item["current_state_digest"]["has_current_state"] is True
        assert item["current_state_digest"]["policy"]["raw_payloads_included"] is False
        assert item["current_state_digest"]["policy"]["raw_secrets_included"] is False
        assert item["closed_by_current_probe"] is False
        assert item["handoff_contract_complete"] is True
    assert enriched["stack_handoff_closure_order"][0]["acceptance_verifiers"]
    assert enriched["stack_handoff_closure_order"][0]["verifier_commands"]
    assert enriched["stack_handoff_closure_order"][0]["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"


def test_self_awareness_brief_stack_handoff_action_map_prioritizes_open_blockers(abyss_machine_module) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    probes = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities={
            "schema": "abyss_machine_self_awareness_capabilities_v1",
            "raw": {
                "tempo_ready": {
                    "ok": False,
                    "url": "http://127.0.0.1:3200/ready",
                    "status_code": None,
                    "error": "connection refused",
                },
            },
            "capabilities": [],
        },
    )

    action_map = abyss_machine_module.self_awareness_brief_stack_handoff_action_map(probes)

    assert action_map["schema"] == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert action_map["ok"] is True
    assert action_map["status"] == "open_requirements"
    assert action_map["summary"]["open_stack_requirements"] == 1
    assert action_map["summary"]["runbook_candidates"] == 1
    assert action_map["summary"]["acceptance_verifier_steps"] >= 1
    assert action_map["summary"]["closure_readiness_packets"] == 1
    assert action_map["summary"]["closure_readiness_missing_checks"] >= 1
    assert action_map["summary"]["coverage_impact_entries"] == 1
    assert "signal_fabric" in action_map["summary"]["blocked_coverage_planes"]
    assert action_map["summary"]["top_requirement_id"] == "stack.trace-backend"
    assert action_map["safe_next_action"]["requires_human_approval"] is True
    assert action_map["safe_next_action"]["automatic"] is False
    assert action_map["safe_next_action"]["host_layer_mutates_stack"] is False
    assert action_map["policy"]["executes_commands"] is False
    assert action_map["policy"]["raw_secrets_included"] is False

    action = action_map["actions"][0]
    assert action["priority_rank"] == 1
    assert action["priority_class"] == "critical_trace_join"
    assert action["owner_route"] == "abyss-stack"
    assert action["policy"]["handoff_only"] is True
    assert action["policy"]["host_layer_mutates_stack"] is False
    assert action["policy"]["executes_commands"] is False
    assert "trace_backend_ready" in action["closure_blocker_keys"]
    assert action["closure_readiness"]["requirement_id"] == "stack.trace-backend"
    assert action["closure_readiness"]["missing_checks"]
    assert action["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
    assert action["coverage_impact"]["organ"] == "trace_join_backbone"
    assert "signal_fabric" in action["coverage_impact"]["coverage_planes"]
    assert "langgraph_replay" in action["coverage_impact"]["coverage_planes"]
    assert action["coverage_impact"]["policy"]["host_layer_mutates_stack"] is False
    assert action["impact_organ"] == "trace_join_backbone"
    assert "causal_timeline" in action["coverage_planes"]
    assert action["runbook_candidate"]["machine_executes_stack_change"] is False
    assert action["runbook_candidate"]["host_layer_mutates_stack"] is False
    assert action["runbook_candidate"]["acceptance_verifiers"]
    assert action["verifier_commands"]
    assert "abyss-machine self-awareness validate --json" in action["verifier_commands"]
    assert action["safe_next_action"]["command"] == "abyss-machine self-awareness export --json"

    overlay = abyss_machine_module.self_awareness_stack_handoff_time_space_overlay(
        probes,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert overlay["schema"] == "abyss_machine_self_awareness_stack_handoff_time_space_overlay_v1"
    assert overlay["ok"] is True
    assert overlay["summary"]["open_stack_requirements"] == 1
    assert overlay["summary"]["timeline_markers"] == 1
    assert overlay["summary"]["spatial_nodes"] >= 4
    assert overlay["summary"]["spatial_edges"] >= 4
    assert overlay["policy"]["host_layer_mutates_stack"] is False
    assert overlay["policy"]["executes_commands"] is False
    marker = overlay["timeline_markers"][0]
    assert marker["schema"] == "abyss_machine_self_awareness_stack_handoff_timeline_marker_v1"
    assert marker["requirement_id"] == "stack.trace-backend"
    assert marker["time"]["bucket"] == "2026-01-01T00:00:00Z"
    assert marker["time"]["freshness_must_precede_reasoning"] is True
    assert marker["space"]["owner_surface"] == "abyss-stack"
    assert "service:trace-backend" in marker["space"]["service_nodes"]
    assert marker["impact_organ"] == "trace_join_backbone"
    assert "langgraph_replay" in marker["coverage_planes"]
    assert any(node["kind"] == "coverage_plane" and node["id"] == "coverage_plane:signal_fabric" for node in overlay["spatial_nodes"])
    assert any(edge["kind"] == "blocks_coverage_plane" for edge in overlay["spatial_edges"])
    assert marker["closure_blockers"]
    assert marker["closure_readiness"]["requirement_id"] == "stack.trace-backend"
    assert marker["runbook_candidate"]["machine_executes_stack_change"] is False
    assert marker["verifier_commands"]
    assert marker["safe_next_action"]["host_layer_mutates_stack"] is False
    node_by_id = {node["id"]: node for node in overlay["spatial_nodes"]}
    assert node_by_id["stack_requirement:stack.trace-backend"]["kind"] == "stack_requirement"
    assert node_by_id["stack_requirement:stack.trace-backend"]["closure_readiness"]["requirement_id"] == "stack.trace-backend"
    assert node_by_id["stack_handoff_action:stack-handoff:stack.trace-backend"]["kind"] == "stack_handoff_action"
    assert node_by_id["stack_runbook:stack-runbook-stack-trace-backend"]["kind"] == "stack_runbook_candidate"
    edge_kinds = {edge["kind"] for edge in overlay["spatial_edges"]}
    assert {"tracks_open_stack_requirement", "proposes_handoff_for", "has_runbook_candidate", "blocks_stack_surface"}.issubset(edge_kinds)


def test_self_awareness_stack_closure_dossier_joins_probe_readiness_and_runbook(abyss_machine_module) -> None:
    trace_requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    langchain_requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.langchain-api.graph-observability",
        "LangGraph observability",
        reason="fixture LangGraph checkpoint inventory lacks trace coupling",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5403/openapi.json"}]},
        expected_shape={"inventory": "threads/checkpoints/traces", "mutated_by": "abyss-stack"},
    )
    requirements_doc = abyss_machine_module.self_awareness_requirements_document(
        [trace_requirement, langchain_requirement],
        "2026-01-01T00:00:00+00:00",
    )
    probes = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=requirements_doc,
        capabilities={
            "schema": "abyss_machine_self_awareness_capabilities_v1",
            "raw": {
                "tempo_ready": {
                    "ok": False,
                    "url": "http://127.0.0.1:3200/ready",
                    "status_code": None,
                    "error": "connection refused",
                },
                "langchain_api": {
                    "health": {"ok": True, "url": "http://127.0.0.1:5403/health", "status_code": 200},
                    "openapi": {"ok": True, "url": "http://127.0.0.1:5403/openapi.json", "status_code": 200, "path_count": 3},
                    "runtime_surface": {
                        "run_route_present": True,
                        "federated_run_route_present": True,
                        "embeddings_route_present": True,
                    },
                    "observability": {
                        "health_readable": True,
                        "openapi_readable": True,
                        "runtime_routes_readable": True,
                        "thread_inventory_present": False,
                        "checkpoint_inventory_present": False,
                        "trace_inventory_present": False,
                    },
                },
            },
            "capabilities": [],
        },
    )
    working_stack_doc = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "ok": True,
        "summary": {"usage_gaps": 1, "full_stack_potential_covered": False},
        "organs": [
            {
                "schema": "abyss_machine_self_awareness_working_stack_organ_v1",
                "service": "aoa-browser",
                "owner_surface": "abyss-stack",
                "machine_usage_status": "tool_runtime_degraded",
                "usage_gap": "stack tool is reachable and guarded, but its functional runtime smoke failed",
                "deep_usage_proven": False,
                "endpoint_ok": True,
                "runtime": {"running": True, "container": "aoa-browser", "health": "healthy", "state": "running", "status": "Up"},
                "declared": {"present": True, "modules": ["browser"]},
                "endpoint_probes": [
                    {"service": "aoa-browser", "probe": "health", "ok": True, "kind": "http_status"},
                    {"service": "aoa-browser", "probe": "private-host-guard", "ok": True, "kind": "http_status", "status_code": 403},
                    {"service": "aoa-browser", "probe": "playwright-chromium-launch", "ok": False, "kind": "python_smoke", "error": "fixture launch failed"},
                ],
                "time_space_context_link": {
                    "schema": "abyss_machine_self_awareness_working_stack_time_space_context_link_v1",
                    "link_id": "saworklink-fixture",
                    "time": {"observed_at": "2026-01-01T00:00:00+00:00", "bucket": "2026-01-01T00:00:00+00:00"},
                    "context": {"working_stack_link_id": "saworklink-fixture"},
                },
                "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": "aoa-browser"}],
                "stack_source_refs": [{"path": "/srv/AbyssOS/abyss-stack/docker-compose.yml", "read_only": True, "host_layer_mutates_stack": False}],
                "model_bridge": {"active": False},
            }
        ],
    }

    dossier = abyss_machine_module.self_awareness_stack_closure_dossier(
        write_latest=False,
        requirements_doc=requirements_doc,
        requirement_probes_doc=probes,
        working_stack_doc=working_stack_doc,
    )

    assert dossier["schema"] == "abyss_machine_self_awareness_stack_closure_dossier_v1"
    assert dossier["ok"] is True
    assert dossier["status"] == "open_requirements_and_activation_gaps"
    assert dossier["summary"]["probes"] == 2
    assert dossier["summary"]["open_stack_requirements"] == 2
    assert dossier["summary"]["working_stack_activation_entries"] == 1
    assert dossier["summary"]["open_working_stack_activation_gaps"] == 1
    assert dossier["summary"]["working_stack_activation_entries_complete"] == 1
    assert dossier["summary"]["top_working_stack_activation_service"] == "aoa-browser"
    assert dossier["summary"]["open_working_stack_activation_gaps"] == 1
    assert dossier["summary"]["missing_checks"] == probes["summary"]["closure_readiness_missing_checks"]
    assert dossier["summary"]["dependency_edges"] == 1
    assert dossier["summary"]["reverse_dependency_edges"] == 1
    assert dossier["summary"]["unblocking_requirements"] == 1
    assert dossier["summary"]["compat_contract_entries"] == 2
    assert dossier["summary"]["closure_acceptance_packets"] == 2
    assert dossier["summary"]["closure_acceptance_packets_complete"] == 2
    assert dossier["summary"]["stack_requirement_compat_requirements"] == 2
    assert dossier["summary"]["runbook_candidates"] == 2
    assert dossier["summary"]["dossier_entries_complete"] == 2
    assert dossier["summary"]["top_requirement_id"] == "stack.trace-backend"
    assert dossier["summary"]["top_unblocking_requirement_id"] == "stack.trace-backend"
    assert dossier["policy"]["host_layer_mutates_stack"] is False
    assert dossier["policy"]["executes_commands"] is False
    assert dossier["policy"]["raw_secrets_included"] is False
    assert dossier["dependency_graph"]["ordered_requirement_ids"][0] == "stack.trace-backend"
    assert dossier["dependency_graph"]["edges"] == [
        {
            "from": "stack.langchain-api.graph-observability",
            "to": "stack.trace-backend",
            "kind": "requires_stack_requirement",
            "reason": ["LangGraph trace/checkpoint replay needs the trace backend coupling first."],
        }
    ]
    assert dossier["dependency_graph"]["reverse_edges"] == [
        {
            "from": "stack.trace-backend",
            "to": "stack.langchain-api.graph-observability",
            "kind": "unblocks_stack_requirement",
            "reason": ["LangGraph trace/checkpoint replay needs the trace backend coupling first."],
        }
    ]
    assert dossier["dependency_graph"]["dependency_root_requirement_ids"] == ["stack.trace-backend"]
    assert dossier["dependency_graph"]["dependent_requirement_ids"] == ["stack.langchain-api.graph-observability"]
    assert dossier["dependency_graph"]["unblocking_requirement_ids"] == ["stack.trace-backend"]
    assert dossier["stack_owner_handoff"]["open_requirement_ids"] == [
        "stack.trace-backend",
        "stack.langchain-api.graph-observability",
    ]
    assert dossier["stack_owner_handoff"]["policy"]["abyss_machine_executes_stack_change"] is False
    assert sorted(dossier["compat_contracts"]) == [
        "stack.langchain-api.graph-observability",
        "stack.trace-backend",
    ]
    assert dossier["closure_acceptance_matrix"]["schema"] == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_matrix_v1"
    assert dossier["closure_acceptance_matrix"]["ok"] is True
    assert set(dossier["closure_acceptance_matrix"]["packet_by_requirement"]) == {
        "stack.langchain-api.graph-observability",
        "stack.trace-backend",
    }
    assert dossier["stack_owner_handoff"]["closure_order"][0]["compat_contract"]["requirement_id"] == "stack.trace-backend"
    assert dossier["stack_owner_handoff"]["closure_order"][0]["closure_acceptance"]["requirement_id"] == "stack.trace-backend"
    activation_dossier = dossier["working_stack_activation_dossier"]
    assert activation_dossier["schema"] == "abyss_machine_self_awareness_working_stack_activation_dossier_v1"
    assert activation_dossier["summary"]["open_activation_gaps"] == 1
    assert activation_dossier["summary"]["synthetic_scenarios"] == 1
    assert activation_dossier["summary"]["synthetic_scenarios_complete"] == 1
    assert activation_dossier["summary"]["closure_acceptance_packets"] == 1
    assert activation_dossier["summary"]["closure_acceptance_packets_complete"] == 1
    assert activation_dossier["summary"]["activation_compat_requirements"] == 1
    assert activation_dossier["synthetic_scenario_matrix"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_synthetic_scenario_matrix_v1"
    assert activation_dossier["synthetic_scenario_matrix"]["ok"] is True
    assert activation_dossier["closure_acceptance_matrix"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_closure_acceptance_matrix_v1"
    assert activation_dossier["closure_acceptance_matrix"]["ok"] is True
    assert activation_dossier["working_stack_activation_handoff"]["policy"]["host_layer_mutates_stack"] is False
    activation_entry = activation_dossier["entries"][0]
    assert activation_entry["schema"] == "abyss_machine_self_awareness_working_stack_activation_entry_v1"
    assert activation_entry["service"] == "aoa-browser"
    assert activation_entry["activation_kind"] == "stack_tool_runtime_smoke_gap"
    assert activation_entry["working_stack_link_id"] == "saworklink-fixture"
    assert activation_entry["complete"] is True
    assert "probe_failed:playwright-chromium-launch" in activation_entry["closure_blocker_keys"]
    assert activation_entry["activation_readiness"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_readiness_v1"
    closure_acceptance = activation_entry["closure_acceptance"]
    assert closure_acceptance["schema"] == "abyss_machine_self_awareness_working_stack_activation_closure_acceptance_v1"
    assert closure_acceptance["complete"] is True
    assert closure_acceptance["service"] == "aoa-browser"
    assert closure_acceptance["working_stack_link_id"] == "saworklink-fixture"
    assert closure_acceptance["pre_close_identity"]["missing_check_keys"] == activation_entry["closure_blocker_keys"]
    assert closure_acceptance["stack_compat_requirement"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_compat_requirement_v1"
    assert closure_acceptance["stack_compat_requirement"]["owner"] == "abyss-stack"
    assert closure_acceptance["stack_compat_requirement"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
    assert closure_acceptance["policy"]["host_layer_mutates_stack"] is False
    assert activation_entry["runbook_candidate"]["machine_executes_stack_change"] is False
    assert activation_entry["safe_next_action"]["host_layer_mutates_stack"] is False
    assert activation_entry["safe_next_action"]["executes_commands"] is False
    scenario = activation_entry["synthetic_scenario"]
    assert scenario["schema"] == "abyss_machine_self_awareness_working_stack_activation_synthetic_scenario_v1"
    assert scenario["complete"] is True
    assert scenario["service"] == "aoa-browser"
    assert scenario["current_result"] == "functional_tool_smoke_failed"
    assert "probe_failed:playwright-chromium-launch" in scenario["current_observation"]["missing_check_keys"]
    assert scenario["policy"]["host_layer_mutates_stack"] is False
    assert scenario["policy"]["executes_commands"] is False
    assert "abyss-machine self-awareness coverage-audit --json" in activation_entry["verifier_commands"]
    assert any(step["command"] == "abyss-machine self-awareness stack-closure-dossier --json" for step in dossier["verifier_chain"])
    trace_entry = next(entry for entry in dossier["entries"] if entry["requirement_id"] == "stack.trace-backend")
    langchain_entry = next(entry for entry in dossier["entries"] if entry["requirement_id"] == "stack.langchain-api.graph-observability")
    assert trace_entry["unblocks_requirement_ids"] == ["stack.langchain-api.graph-observability"]
    assert trace_entry["closure_impact"]["is_unblocking_requirement"] is True
    assert trace_entry["closure_impact"]["downstream_open_requirements"] == 1
    assert trace_entry["closure_impact"]["policy"]["host_layer_mutates_stack"] is False
    assert trace_entry["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
    assert trace_entry["coverage_impact"]["organ"] == "trace_join_backbone"
    assert "signal_fabric" in trace_entry["coverage_impact"]["coverage_planes"]
    assert "langgraph_replay" in trace_entry["coverage_impact"]["coverage_planes"]
    assert trace_entry["coverage_impact"]["policy"]["host_layer_mutates_stack"] is False
    assert trace_entry["compat_contract"]["schema"] == "abyss_machine_self_awareness_stack_compat_contract_v1"
    assert trace_entry["compat_contract"]["surface_kind"] == "trace_backend_inventory"
    assert trace_entry["compat_contract"]["dependency_contract"]["unblocks_requirement_ids"] == ["stack.langchain-api.graph-observability"]
    assert trace_entry["compat_contract"]["coverage_contract"]["organ"] == "trace_join_backbone"
    assert trace_entry["closure_acceptance"]["schema"] == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
    assert trace_entry["closure_acceptance"]["complete"] is True
    assert trace_entry["closure_acceptance"]["requirement_id"] == "stack.trace-backend"
    assert trace_entry["closure_acceptance"]["pre_close_identity"]["missing_check_keys"] == trace_entry["blocking_check_keys"]
    assert trace_entry["closure_acceptance"]["stack_compat_requirement"]["schema"] == "abyss_machine_self_awareness_stack_requirement_compat_requirement_v1"
    assert trace_entry["closure_acceptance"]["stack_compat_requirement"]["owner"] == "abyss-stack"
    assert trace_entry["closure_acceptance"]["stack_compat_requirement"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
    assert trace_entry["closure_acceptance"]["policy"]["host_layer_mutates_stack"] is False
    assert langchain_entry["depends_on_requirement_ids"] == ["stack.trace-backend"]
    assert langchain_entry["closure_impact"]["is_dependency_root"] is False
    assert langchain_entry["coverage_impact"]["organ"] == "checkpointed_reasoning_runtime"
    assert "langgraph_loop" in langchain_entry["coverage_impact"]["coverage_planes"]
    assert "investigation_replay" in langchain_entry["coverage_impact"]["coverage_planes"]
    assert langchain_entry["compat_contract"]["dependency_contract"]["depends_on_requirement_ids"] == ["stack.trace-backend"]

    for entry in dossier["entries"]:
        assert entry["schema"] == "abyss_machine_self_awareness_stack_closure_dossier_entry_v1"
        assert entry["owner"] == "abyss-stack"
        assert entry["complete"] is True
        assert entry["closure_readiness"]["schema"] == "abyss_machine_stack_handoff_closure_readiness_v1"
        assert entry["closure_impact"]["schema"] == "abyss_machine_self_awareness_stack_closure_impact_v1"
        assert entry["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert entry["coverage_impact"]["coverage_planes"]
        assert entry["coverage_impact"]["proof_commands"]
        assert entry["compat_contract"]["schema"] == "abyss_machine_self_awareness_stack_compat_contract_v1"
        assert entry["compat_contract"]["machine_consumer_contract"]["post_close_verifiers"]
        assert entry["compat_contract"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
        assert entry["compat_contract"]["policy"]["host_layer_mutates_stack"] is False
        assert entry["compat_contract"]["redaction_contract"]["raw_secrets_allowed"] is False
        assert entry["closure_acceptance"]["schema"] == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
        assert entry["closure_acceptance"]["complete"] is True
        assert entry["closure_acceptance"]["requirement_id"] == entry["requirement_id"]
        assert entry["closure_acceptance"]["stack_compat_requirement"]["owner"] == "abyss-stack"
        assert entry["closure_acceptance"]["stack_compat_requirement"]["operator_boundary"]["host_layer_mutates_stack"] is False
        assert entry["closure_acceptance"]["closure_diff_contract"]["schema"] == "abyss_machine_self_awareness_stack_requirement_closure_diff_contract_v1"
        assert entry["closure_acceptance"]["negative_controls"]
        assert entry["closure_acceptance"]["policy"]["host_layer_mutates_stack"] is False
        assert entry["runbook_candidate"]["machine_executes_stack_change"] is False
        assert entry["acceptance_verifiers"]
        assert entry["verifier_commands"]
        assert entry["policy"]["host_layer_mutates_stack"] is False
        assert entry["safe_next_action"]["host_layer_mutates_stack"] is False


def _working_stack_activation_entry_fixture(abyss_machine_module, *, service: str, status: str, link_id: str) -> dict:
    verifier_commands = [
        "abyss-machine self-awareness working-stack --json",
        "abyss-machine self-awareness stack-closure-dossier --json",
        "abyss-machine self-awareness coverage-audit --json",
        "abyss-machine self-awareness activation-smoke --json",
        "abyss-machine self-awareness validate --json",
    ]
    usage_gap = "stack tool is reachable but functional runtime smoke failed"
    entry = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_entry_v1",
        "service": service,
        "owner": "abyss-stack",
        "activation_kind": abyss_machine_module.self_awareness_working_stack_gap_activation_kind(status),
        "machine_usage_status": status,
        "usage_gap": usage_gap,
        "working_stack_link_id": link_id,
        "runtime": {
            "present": True,
            "running": True,
            "container": service,
            "health": "healthy",
            "state": "running",
            "status": "Up",
            "stack_managed": True,
        },
        "declared": {"present": True, "modules": ["tools"]},
        "endpoint_ok": False,
        "deep_usage_proven": False,
        "coverage_planes": abyss_machine_module.self_awareness_working_stack_gap_coverage_planes(status),
        "closure_blocker_keys": ["probe_failed:playwright-chromium-launch"],
        "current_state": {
            "service": service,
            "machine_usage_status": status,
            "working_stack_link_id": link_id,
            "runtime": {"running": True, "container": service},
        },
        "current_state_digest": "fixture-state-digest",
        "fulfilled_checks": [{"key": "working_stack_time_space_context_link", "ok": True, "link_id": link_id}],
        "missing_checks": [
            {"key": "working_stack_usage_gap", "level": "open", "message": usage_gap, "status": status},
            {"key": "probe_failed:playwright-chromium-launch", "level": "open", "message": "bounded working-stack probe failed", "probe": "playwright-chromium-launch"},
        ],
        "failed_probe_names": ["playwright-chromium-launch"],
        "ok_probe_names": ["container-health", "private-host-guard"],
        "verifier_commands": verifier_commands,
        "safe_next_action": {
            "requires_human_approval": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "verifier_commands": verifier_commands,
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": service}],
    }
    generated_at = "2026-06-06T00:00:00-06:00"
    entry["closure_acceptance"] = abyss_machine_module.self_awareness_working_stack_activation_closure_acceptance(entry, generated_at)
    entry["synthetic_scenario"] = abyss_machine_module.self_awareness_working_stack_activation_synthetic_scenario(entry, generated_at)
    entry["complete"] = True
    return entry


def _working_stack_organ_fixture(entry: dict) -> dict:
    service = entry["service"]
    link_id = entry["working_stack_link_id"]
    return {
        "schema": "abyss_machine_self_awareness_working_stack_organ_v1",
        "service": service,
        "owner": "abyss-stack",
        "machine_usage_status": entry["machine_usage_status"],
        "usage_gap": entry["usage_gap"],
        "runtime": entry["runtime"],
        "declared": entry["declared"],
        "endpoint_ok": entry["endpoint_ok"],
        "endpoint_probes": [
            {"probe": "container-health", "ok": True},
            {"probe": "private-host-guard", "ok": True},
            {"probe": "playwright-chromium-launch", "ok": False},
        ],
        "deep_usage_proven": entry["deep_usage_proven"],
        "service_roots": 0,
        "model_roots": 0,
        "time_space_context_link": {
            "link_id": link_id,
            "time": {"observed_at": "2026-06-06T00:00:00-06:00"},
            "context": {"working_stack_link_id": link_id},
        },
        "evidence_refs": entry["evidence_refs"],
    }


def test_self_awareness_activation_smoke_builds_per_service_movement_packet(monkeypatch, abyss_machine_module) -> None:
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    link_id = "saworklink-fixture"
    episode_id = "saepisode-working-stack-gap-fixture"
    thread_id = "sainv-fixture"
    entry = _working_stack_activation_entry_fixture(abyss_machine_module, service=service, status=status, link_id=link_id)
    dossier = {
        "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        "summary": {"full_stack_potential_covered": False},
        "working_stack_activation_dossier": {
            "schema": "abyss_machine_self_awareness_working_stack_activation_dossier_v1",
            "summary": {"open_activation_gaps": 1},
            "entries": [entry],
        },
    }
    episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "summary": {"working_stack_gap_episodes": 1},
        "episodes": [
            {
                "episode_id": episode_id,
                "episode_kind": "working_stack_usage_gap",
                "service": service,
                "working_stack_link_id": link_id,
                "working_stack_gap": {
                    "service": service,
                    "machine_usage_status": status,
                    "working_stack_link_id": link_id,
                },
            }
        ],
    }
    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "ok": True,
        "summary": {"organs": 1, "usage_gaps": 1},
        "organs": [_working_stack_organ_fixture(entry)],
    }
    working_stack_gap_packet = {
        "schema": "abyss_machine_self_awareness_investigation_working_stack_gap_v1",
        "episode_kind": "working_stack_usage_gap",
        "truth_level": "working_stack_gap_candidate",
        "selected_episode_id": episode_id,
        "service": service,
        "owner_route": "abyss-stack",
        "working_stack_link_id": link_id,
        "machine_usage_status": status,
        "usage_gap": entry["usage_gap"],
        "closure_blocker_keys": entry["closure_blocker_keys"],
        "verifier_commands": entry["verifier_commands"],
        "safe_next_action": entry["safe_next_action"],
        "request": {
            "kind": "working_stack_usage_gap",
            "automatic": False,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/episodes/latest.json"}],
    }
    investigation_calls: list[dict] = []
    replay_calls: list[dict] = []

    def fake_load_latest_json(path, schema):
        if schema == "abyss_machine_self_awareness_episodes_v1":
            return episodes
        if schema == "abyss_machine_self_awareness_working_stack_inventory_v1":
            return working_stack
        return {"schema": schema, "ok": True, "summary": {}}

    def fake_investigate(*, query, episode_id, write_latest):
        investigation_calls.append({"query": query, "episode_id": episode_id, "write_latest": write_latest})
        return {
            "schema": "abyss_machine_self_awareness_investigation_v1",
            "ok": True,
            "thread_id": thread_id,
            "selected_episode_id": episode_id,
            "summary": {
                "selected_episode": episode_id,
                "checkpoints": len(abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER),
                "graph_nodes": len(abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER),
                "evidence_validation_fails": 0,
                "resident_worker_detail_complete": True,
                "resident_cognitive_packet_complete": True,
                "read_only_tools": 8,
                "hypothesis_tests": 4,
                "contradiction_notes": 2,
            },
            "working_stack_gap": working_stack_gap_packet,
            "policy": {"host_layer_mutates_stack": False, "action_execution": False},
        }

    def fake_replay(*, thread_id, write_latest):
        replay_calls.append({"thread_id": thread_id, "write_latest": write_latest})
        resident_replay = _resident_cognitive_replay_fixture()
        resident_replay["thread_id"] = thread_id
        return {
            "schema": "abyss_machine_self_awareness_replay_v1",
            "ok": True,
            "thread_id": thread_id,
            "summary": {
                "divergences": 0,
                "working_stack_gap_selected": True,
                "working_stack_gap_replayable": True,
                "node_order": abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER,
            },
            "working_stack_gap_replay": {
                "service": service,
                "machine_usage_status": status,
                "working_stack_link_id": link_id,
                "selected": True,
                "replayable": True,
            },
            "stack_handoff_replay": {"closure_readiness_replayable": True},
            "resident_cognitive_replay": resident_replay,
            "policy": {"host_layer_mutates_stack": False, "action_execution": False},
        }

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_investigate", fake_investigate)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_replay", fake_replay)

    smoke = abyss_machine_module.self_awareness_activation_smoke(write_latest=False, stack_closure_dossier_doc=dossier)
    row = smoke["rows"][0]
    compact = smoke["compact_by_service"][service]
    packet = row["stack_organ_use_packet"]

    assert smoke["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_v1"
    assert smoke["ok"] is True
    assert smoke["complete"] is True
    assert smoke["summary"]["activation_entries"] == 1
    assert smoke["summary"]["rows_ok"] == 1
    assert smoke["summary"]["actual_investigation_runs"] == 0
    assert smoke["summary"]["actual_replay_runs"] == 0
    assert smoke["summary"]["stack_organ_use_packets"] == 1
    assert smoke["summary"]["stack_organ_use_packets_complete"] == 1
    assert smoke["summary"]["failed_services"] == []
    assert investigation_calls == []
    assert replay_calls == []
    assert abyss_machine_module.self_awareness_working_stack_activation_smoke_row_complete(row) is True
    assert abyss_machine_module.self_awareness_stack_organ_use_packet_complete(packet) is True
    assert smoke["stack_organ_use_packet_by_service"][service] == packet
    assert row["row_kind"] == "organ_movement"
    assert row["service"] == service
    assert row["machine_usage_status"] == status
    assert row["working_stack_link_id"] == link_id
    assert row["episode_id"] is None
    assert packet["entity"]["entity_id"] == f"stack.organ.{service}"
    assert packet["event"]["working_stack_link_id"] == link_id
    assert packet["activation_gap"]["classification"] == "running_functional_smoke_failed"
    assert packet["closure_acceptance"]["compat_requirement_id"].startswith("stack.activation.")
    assert "self-awareness.completion-audit.latest" in packet["document_ids"]
    assert row["investigation"]["actual_run"] is False
    assert row["replay"]["actual_run"] is False
    assert row["replay"]["working_stack_gap_replayable"] is None
    assert row["replay"]["divergences"] is None
    assert row["policy"]["actual_investigate_replay_run"] is False
    assert row["policy"]["movement_packet"] is True
    assert row["policy"]["host_layer_mutates_stack"] is False
    assert compact["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1"
    assert compact["row_kind"] == "organ_movement"
    assert compact["complete"] is True
    assert compact["service"] == service
    assert compact["working_stack_link_id"] == link_id
    assert compact["stack_organ_use_packet_id"] == packet["packet_id"]
    assert compact["stack_organ_entity_id"] == f"stack.organ.{service}"
    assert compact["working_stack_gap_replayable"] is None
    assert compact["divergences"] is None
    assert compact["movement_categories"]
    assert compact["policy"]["host_layer_mutates_stack"] is False
    assert abyss_machine_module.self_awareness_activation_smoke_needs_refresh(smoke, [entry]) is False
    changed_entry = dict(entry, working_stack_link_id="saworklink-changed")
    assert abyss_machine_module.self_awareness_activation_smoke_needs_refresh(smoke, [changed_entry]) is True


def test_self_awareness_activation_smoke_refreshes_stale_episode_identity(monkeypatch, abyss_machine_module) -> None:
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    link_id = "saworklink-current"
    episode_id = "saepisode-working-stack-gap-current"
    thread_id = "sainv-current"
    entry = _working_stack_activation_entry_fixture(abyss_machine_module, service=service, status=status, link_id=link_id)
    dossier = {
        "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        "summary": {"full_stack_potential_covered": False},
        "working_stack_activation_dossier": {
            "schema": "abyss_machine_self_awareness_working_stack_activation_dossier_v1",
            "summary": {"open_activation_gaps": 1},
            "entries": [entry],
        },
    }
    stale_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "summary": {"working_stack_gap_episodes": 1},
        "episodes": [
            {
                "episode_id": "saepisode-working-stack-gap-stale",
                "episode_kind": "working_stack_usage_gap",
                "service": service,
                "working_stack_link_id": "saworklink-stale",
                "working_stack_gap": {
                    "service": service,
                    "machine_usage_status": status,
                    "working_stack_link_id": "saworklink-stale",
                },
            }
        ],
    }
    fresh_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "summary": {"working_stack_gap_episodes": 1},
        "episodes": [
            {
                "episode_id": episode_id,
                "episode_kind": "working_stack_usage_gap",
                "service": service,
                "working_stack_link_id": link_id,
                "working_stack_gap": {
                    "service": service,
                    "machine_usage_status": status,
                    "working_stack_link_id": link_id,
                },
            }
        ],
    }
    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "ok": True,
        "summary": {"organs": 1, "usage_gaps": 1},
        "organs": [_working_stack_organ_fixture(entry)],
    }
    refresh_calls: list[bool] = []

    def fake_load_latest_json(_path, schema):
        if schema == "abyss_machine_self_awareness_episodes_v1":
            return stale_episodes
        if schema == "abyss_machine_self_awareness_working_stack_inventory_v1":
            return working_stack
        return {"schema": schema, "ok": True, "summary": {}}

    def fake_episodes(write_latest=True):
        refresh_calls.append(write_latest)
        return fresh_episodes

    def fake_investigate(*, query, episode_id, write_latest):
        return {
            "schema": "abyss_machine_self_awareness_investigation_v1",
            "ok": True,
            "thread_id": thread_id,
            "selected_episode_id": episode_id,
            "summary": {
                "selected_episode": episode_id,
                "checkpoints": len(abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER),
                "graph_nodes": len(abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER),
                "evidence_validation_fails": 0,
                "resident_worker_detail_complete": True,
                "resident_cognitive_packet_complete": True,
                "read_only_tools": 8,
                "hypothesis_tests": 4,
                "contradiction_notes": 2,
            },
            "working_stack_gap": {
                "schema": "abyss_machine_self_awareness_investigation_working_stack_gap_v1",
                "episode_kind": "working_stack_usage_gap",
                "truth_level": "working_stack_gap_candidate",
                "selected_episode_id": episode_id,
                "service": service,
                "owner_route": "abyss-stack",
                "working_stack_link_id": link_id,
                "machine_usage_status": status,
                "usage_gap": entry["usage_gap"],
                "closure_blocker_keys": entry["closure_blocker_keys"],
                "verifier_commands": entry["verifier_commands"],
                "safe_next_action": entry["safe_next_action"],
                "request": {"kind": "working_stack_usage_gap", "automatic": False, "host_layer_mutates_stack": False, "executes_commands": False},
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "action_execution": False},
                "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/episodes/latest.json"}],
            },
            "policy": {"host_layer_mutates_stack": False, "action_execution": False},
        }

    def fake_replay(*, thread_id, write_latest):
        resident_replay = _resident_cognitive_replay_fixture()
        resident_replay["thread_id"] = thread_id
        return {
            "schema": "abyss_machine_self_awareness_replay_v1",
            "ok": True,
            "thread_id": thread_id,
            "summary": {
                "divergences": 0,
                "working_stack_gap_selected": True,
                "working_stack_gap_replayable": True,
                "node_order": abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER,
            },
            "working_stack_gap_replay": {
                "service": service,
                "machine_usage_status": status,
                "working_stack_link_id": link_id,
                "selected": True,
                "replayable": True,
            },
            "stack_handoff_replay": {"closure_readiness_replayable": True},
            "resident_cognitive_replay": resident_replay,
            "policy": {"host_layer_mutates_stack": False, "action_execution": False},
        }

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_episodes", fake_episodes)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_investigate", fake_investigate)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_replay", fake_replay)

    smoke = abyss_machine_module.self_awareness_activation_smoke(write_latest=False, stack_closure_dossier_doc=dossier)
    row = smoke["rows"][0]

    assert refresh_calls == [True]
    assert smoke["ok"] is True
    assert smoke["complete"] is True
    assert smoke["summary"]["episode_identity_missing_before_refresh"] == [service]
    assert smoke["summary"]["episodes_refreshed_for_identity"] is True
    assert smoke["summary"]["episode_identity_missing_after_refresh"] == []
    assert row["row_kind"] == "organ_movement"
    assert row["episode_id"] is None
    assert row["working_stack_link_id"] == link_id
    assert abyss_machine_module.self_awareness_working_stack_activation_smoke_row_complete(row) is True
    assert abyss_machine_module.self_awareness_stack_organ_use_packet_complete(row["stack_organ_use_packet"]) is True


def test_self_awareness_requirements_embed_compact_probe_readiness(abyss_machine_module) -> None:
    trace_requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    langchain_requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.langchain-api.graph-observability",
        "LangGraph observability",
        reason="fixture LangGraph checkpoint inventory lacks trace coupling",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5403/openapi.json"}]},
        expected_shape={"inventory": "threads/checkpoints/traces", "mutated_by": "abyss-stack"},
    )
    requirements_doc = abyss_machine_module.self_awareness_requirements_document(
        [trace_requirement, langchain_requirement],
        "2026-01-01T00:00:00+00:00",
    )
    probes = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=requirements_doc,
        capabilities={
            "schema": "abyss_machine_self_awareness_capabilities_v1",
            "raw": {
                "tempo_ready": {
                    "ok": False,
                    "url": "http://127.0.0.1:3200/ready",
                    "status_code": None,
                    "error": "connection refused",
                },
                "langchain_api": {
                    "health": {"ok": True, "url": "http://127.0.0.1:5403/health", "status_code": 200},
                    "openapi": {"ok": True, "url": "http://127.0.0.1:5403/openapi.json", "status_code": 200, "path_count": 3},
                    "runtime_surface": {
                        "run_route_present": True,
                        "federated_run_route_present": True,
                        "embeddings_route_present": True,
                    },
                    "observability": {
                        "health_readable": True,
                        "openapi_readable": True,
                        "runtime_routes_readable": True,
                        "thread_inventory_present": False,
                        "checkpoint_inventory_present": False,
                        "trace_inventory_present": False,
                    },
                },
            },
            "capabilities": [],
        },
    )

    enriched = abyss_machine_module.self_awareness_requirements_with_probe_readiness(requirements_doc, probes)

    assert enriched["summary"]["stack_handoff_closure_readiness_packets"] == 2
    assert enriched["summary"]["stack_handoff_closure_readiness_missing_checks"] == probes["summary"]["closure_readiness_missing_checks"]
    assert enriched["summary"]["stack_handoff_runbook_candidates"] == 2
    assert enriched["summary"]["top_stack_handoff_requirement"] == "stack.trace-backend"
    assert enriched["stack_handoff_action_summary"]["top_requirement_id"] == "stack.trace-backend"
    assert enriched["stack_handoff_closure_order"][0]["requirement_id"] == "stack.trace-backend"
    assert enriched["stack_handoff_closure_order"][0]["safe_next_action"]["host_layer_mutates_stack"] is False

    trace_requirement_row = next(item for item in enriched["requirements"] if item["id"] == "stack.trace-backend")
    trace_handoff = next(item for item in enriched["stack_handoff"] if item["id"] == "stack.trace-backend")
    assert trace_requirement_row["closure_readiness"]["schema"] == "abyss_machine_self_awareness_requirement_readiness_summary_v1"
    assert trace_requirement_row["closure_readiness"]["missing_check_count"] >= 1
    assert "trace_backend_ready" in trace_requirement_row["blocking_check_keys"]
    assert trace_requirement_row["runbook_candidate_id"] == "stack-runbook-stack-trace-backend"
    assert trace_requirement_row["verifier_commands"]
    assert trace_requirement_row["compat_contract"]["schema"] == "abyss_machine_self_awareness_stack_compat_contract_v1"
    assert trace_requirement_row["compat_contract"]["minimum_response_contract"]["current_blocking_check_keys"]
    assert trace_requirement_row["compat_contract"]["policy"]["host_layer_mutates_stack"] is False
    assert trace_handoff["closure_readiness"]["requirement_id"] == "stack.trace-backend"
    assert trace_handoff["coverage_impact"]["organ"] == "trace_join_backbone"
    assert trace_handoff["safe_next_action"]["requires_human_approval"] is True
    assert trace_handoff["compat_contract"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False


def test_self_awareness_requirement_probes_must_cover_current_requirements(abyss_machine_module) -> None:
    trace_requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    langchain_requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.langchain-api.graph-observability",
        "LangGraph observability",
        reason="fixture LangGraph checkpoint inventory lacks trace coupling",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5403/openapi.json"}]},
        expected_shape={"inventory": "threads/checkpoints/traces", "mutated_by": "abyss-stack"},
    )
    requirements_doc = abyss_machine_module.self_awareness_requirements_document(
        [trace_requirement, langchain_requirement],
        "2026-01-01T00:00:00+00:00",
    )
    stale_probes_doc = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "probes": [{"id": "stack.trace-backend", "requirement_id": "stack.trace-backend"}],
    }
    matching_probes_doc = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "probes": [
            {"id": "stack.trace-backend", "requirement_id": "stack.trace-backend"},
            {"id": "stack.langchain-api.graph-observability", "requirement_id": "stack.langchain-api.graph-observability"},
        ],
    }

    assert abyss_machine_module.self_awareness_requirement_probes_cover_requirements(requirements_doc, stale_probes_doc) is False
    assert abyss_machine_module.self_awareness_requirement_probes_cover_requirements(requirements_doc, matching_probes_doc) is True


def test_self_awareness_spatial_graph_refines_model_root_service_owner(monkeypatch, abyss_machine_module) -> None:
    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "ok": True,
        "status": "mapped_with_usage_gaps",
        "summary": {"organs": 1, "usage_gaps": 1, "time_space_context_links": 1},
        "model_roots": {
            "models": [
                {
                    "relative_path": "Models/stt/whisper-fixture",
                    "tags": ["stt"],
                    "service_candidates": ["stt"],
                }
            ],
        },
        "organs": [
            {
                "schema": "abyss_machine_self_awareness_working_stack_organ_v1",
                "service": "stt",
                "machine_usage_status": "model_root_visible",
                "deep_usage_proven": False,
                "roles": ["speech-to-text"],
                "runtime": {"present": False, "running": False},
                "declared": {"present": False},
                "service_roots": 0,
                "model_roots": 1,
                "endpoint_probes": [],
                "usage_gap": "stack model root is visible, but no direct runtime/service linkage is proven yet",
                "time_space_context_link": {
                    "link_id": "saworklink-stt-fixture",
                    "time": {"bucket": "2026-07-01T00:00:00Z"},
                    "context": {"working_stack_link_id": "saworklink-stt-fixture"},
                },
                "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": "stt"}],
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
    }
    timeline = {
        "schema": "abyss_machine_self_awareness_timeline_v1",
        "events": [],
        "stack_handoff_time_space_overlay": {"summary": {}, "spatial_nodes": [], "spatial_edges": []},
    }

    def fake_load_latest_json(path, schema, *args, **kwargs):
        if str(path) == str(abyss_machine_module.SELF_AWARENESS_TIMELINE_LATEST_PATH):
            return timeline
        if str(path) == str(abyss_machine_module.SELF_AWARENESS_WORKING_STACK_LATEST_PATH):
            return working_stack
        return {"schema": schema, "ok": True}

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_memory_space_overlay",
        lambda events: {"summary": {}, "policy": {}, "freshness_gates": [], "spatial_overlays": [], "stack_semantic_backends": []},
    )

    graph = abyss_machine_module.self_awareness_spatial_graph(write_latest=False)
    service_node = next(node for node in graph["nodes"] if node["id"] == "service:stt")

    assert graph["schema"] == "abyss_machine_self_awareness_spatial_graph_v1"
    assert service_node["owner_surface"] == "abyss-stack"
    assert service_node["machine_usage_status"] == "model_root_visible"
    assert service_node["model_roots"] == 1
    assert any(edge["from"] == "service:stt" and edge["kind"] == "has_unexhausted_potential" for edge in graph["edges"])


def test_self_awareness_stack_handoff_episodes_route_to_alert_candidates(monkeypatch, abyss_machine_module) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    requirements_doc = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    probes = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=requirements_doc,
        capabilities={
            "schema": "abyss_machine_self_awareness_capabilities_v1",
            "raw": {
                "tempo_ready": {
                    "ok": False,
                    "url": "http://127.0.0.1:3200/ready",
                    "status_code": None,
                    "error": "connection refused",
                },
            },
            "capabilities": [],
        },
    )
    stack_closure_dossier = abyss_machine_module.self_awareness_stack_closure_dossier(
        write_latest=False,
        requirements_doc=requirements_doc,
        requirement_probes_doc=probes,
        working_stack_doc={
            "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
            "summary": {"usage_gaps": 0},
            "organs": [],
        },
    )
    overlay = abyss_machine_module.self_awareness_stack_handoff_time_space_overlay(
        probes,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    timeline_doc = {
        "schema": "abyss_machine_self_awareness_timeline_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "events": [],
        "stack_handoff_time_space_overlay": overlay,
    }
    spatial_doc = {
        "schema": "abyss_machine_self_awareness_spatial_graph_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"nodes": len(overlay["spatial_nodes"])},
        "nodes": overlay["spatial_nodes"],
        "edges": overlay["spatial_edges"],
        "stack_handoff_time_space_overlay": overlay,
    }
    monkeypatch.setattr(abyss_machine_module, "self_awareness_timeline", lambda write_latest=True: timeline_doc)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_spatial_graph", lambda write_latest=True: spatial_doc)
    monkeypatch.setattr(
        abyss_machine_module,
        "load_latest_json",
        lambda path, schema, *args, **kwargs: (
            {
                "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
                "summary": {"usage_gaps": 0},
                "organs": [],
            }
            if str(path) == str(abyss_machine_module.SELF_AWARENESS_WORKING_STACK_LATEST_PATH)
            else {"schema": schema, "ok": True}
        ),
    )

    episodes = abyss_machine_module.self_awareness_episodes(write_latest=False)
    stack_episodes = [item for item in episodes["episodes"] if item.get("episode_kind") == "stack_handoff_blocker"]

    assert episodes["summary"]["stack_handoff_episodes"] == 1
    assert len(stack_episodes) == 1
    episode = stack_episodes[0]
    assert episode["requirement_id"] == "stack.trace-backend"
    assert episode["truth_level"] == "handoff_candidate"
    assert episode["event_ids"] == []
    assert "stack_handoff" in episode["primary_signals"]
    assert "stack_requirement:stack.trace-backend" in episode["affected_spatial_nodes"]
    assert "stack_handoff_action:stack-handoff:stack.trace-backend" in episode["affected_spatial_nodes"]
    assert episode["policy"]["handoff_only"] is True
    assert episode["policy"]["host_layer_mutates_stack"] is False
    assert episode["stack_handoff"]["verifier_commands"]

    investigation = {
        "schema": "abyss_machine_self_awareness_investigation_v1",
        "ok": True,
        "thread_id": "thread-stack-handoff",
        "selected_episode_id": episode["episode_id"],
        "summary": {},
    }
    replay = {
        "schema": "abyss_machine_self_awareness_replay_v1",
        "ok": True,
        "thread_id": "thread-stack-handoff",
        "summary": {"divergences": 0, "conclusion_diff_changed": False},
        "stack_handoff_replay": {
            "closure_readiness_replayable": True,
            "open_requirement_ids": ["stack.trace-backend"],
        },
    }

    def fake_load_latest_json(path, schema, *args, **kwargs):
        path_text = str(path)
        if path_text == str(abyss_machine_module.SELF_AWARENESS_EPISODES_LATEST_PATH):
            return episodes
        if path_text == str(abyss_machine_module.SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH):
            return probes
        if path_text == str(abyss_machine_module.SELF_AWARENESS_INVESTIGATE_LATEST_PATH):
            return investigation
        if path_text == str(abyss_machine_module.SELF_AWARENESS_REPLAY_LATEST_PATH):
            return replay
        if path_text == str(abyss_machine_module.SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH):
            return stack_closure_dossier
        if path_text == str(abyss_machine_module.SELF_AWARENESS_CONTEXT_LATEST_PATH):
            return _context_doc_fixture()
        if path_text == str(abyss_machine_module.SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH):
            return _completion_audit_doc_fixture()
        return {"schema": schema, "ok": True}

    monkeypatch.setattr(abyss_machine_module, "self_awareness_load_events", lambda refresh=True: [])
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)

    alerts = abyss_machine_module.self_awareness_alerts(write_latest=False)

    assert alerts["summary"]["reaction_candidates"] == 1
    assert alerts["summary"]["stack_handoff_candidates"] == 1
    assert alerts["summary"]["response_depth_missing"] == 0
    assert alerts["summary"]["body_trace_missing"] == 0
    candidate = alerts["candidates"][0]
    contract = candidate["response_contract"]
    assert candidate["stack_handoff_requirement_id"] == "stack.trace-backend"
    assert candidate["episode_id"] == episode["episode_id"]
    assert candidate["automatic"] is False
    assert contract["validated_episode"]["episode_kind"] == "stack_handoff_blocker"
    assert contract["validated_episode"]["truth_level"] == "handoff_candidate"
    assert contract["runbook_candidate"]["owner_route"] == "abyss-stack"
    assert contract["runbook_candidate"]["requirement_id"] == "stack.trace-backend"
    assert contract["runbook_candidate"]["machine_executes_stack_change"] is False
    assert contract["runbook_candidate"]["host_layer_mutates_stack"] is False
    assert contract["runbook_candidate"]["verifier_commands"]
    assert contract["stack_handoff"]["requirement_id"] == "stack.trace-backend"
    assert contract["stack_requirement_route"]["schema"] == "abyss_machine_self_awareness_stack_requirement_handoff_route_v1"
    assert contract["stack_requirement_route"]["complete"] is True
    assert contract["stack_requirement_route"]["requirement_id"] == "stack.trace-backend"
    assert contract["stack_requirement_route"]["impact"]["organ"] == "trace_join_backbone"
    assert contract["stack_requirement_route"]["lineage"]["stack_handoff_replayable"] is True
    assert contract["stack_requirement_route"]["safe_next_action"]["host_layer_mutates_stack"] is False
    assert candidate["stack_requirement_route"] == contract["stack_requirement_route"]
    assert contract["body_trace"]["complete"] is True
    assert contract["policy"]["host_layer_mutates_stack"] is False
    assert contract["policy"]["executes_commands"] is False
    assert abyss_machine_module.self_awareness_reaction_candidate_response_depth_complete(candidate) is True
    route = abyss_machine_module.response_route_from_candidate(candidate)
    assert route["stack_requirement_route"] == contract["stack_requirement_route"]
    assert abyss_machine_module.self_awareness_response_route_depth_complete(route) is True


def test_self_awareness_host_service_events_become_body_episodes(monkeypatch, abyss_machine_module) -> None:
    event = abyss_machine_module.self_awareness_make_event(
        "service",
        "host-service",
        event_time="2026-01-01T00:00:00+00:00",
        resource={"service": "abyss-dictation-server.service", "owner_surface": "abyss-machine", "write": False},
        context={
            "host_service_unit": "abyss-dictation-server.service",
            "host_service_scope": "user",
            "host_service_category": "dictation",
        },
        space={"host": "fixture", "owner_surface": "abyss-machine", "service": "abyss-dictation-server.service"},
        evidence_refs=[{"fixture": "host_service"}],
        truth_level="host_service_state",
    )
    timeline_doc = {
        "schema": "abyss_machine_self_awareness_timeline_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "events": [event],
        "stack_handoff_time_space_overlay": {
            "schema": "abyss_machine_self_awareness_stack_handoff_time_space_overlay_v1",
            "summary": {"open_stack_requirements": 0},
            "timeline_markers": [],
        },
    }
    spatial_doc = {
        "schema": "abyss_machine_self_awareness_spatial_graph_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"nodes": 1},
        "nodes": [{"id": "service:abyss-dictation-server.service"}],
        "edges": [],
    }

    monkeypatch.setattr(abyss_machine_module, "self_awareness_timeline", lambda write_latest=True: timeline_doc)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_spatial_graph", lambda write_latest=True: spatial_doc)
    monkeypatch.setattr(
        abyss_machine_module,
        "load_latest_json",
        lambda path, schema, *args, **kwargs: (
            {
                "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
                "summary": {"usage_gaps": 0},
                "organs": [],
            }
            if str(path) == str(abyss_machine_module.SELF_AWARENESS_WORKING_STACK_LATEST_PATH)
            else {"schema": schema, "ok": True}
        ),
    )

    episodes = abyss_machine_module.self_awareness_episodes(write_latest=False)
    host_episodes = [item for item in episodes["episodes"] if item.get("episode_kind") == "host_service_state"]

    assert episodes["summary"]["host_service_episodes"] == 1
    assert episodes["host_service_episode_ids"] == [host_episodes[0]["episode_id"]]
    assert len(host_episodes) == 1
    episode = host_episodes[0]
    assert episode["source_counts"]["host-service"] == 1
    assert episode["affected_services"] == ["abyss-dictation-server.service"]
    assert "service:abyss-dictation-server.service" in episode["affected_spatial_nodes"]
    assert "host_service_unit:abyss-dictation-server.service" in episode["context_keys"]
    assert episode["host_service"]["units"] == ["abyss-dictation-server.service"]
    assert episode["host_service"]["categories"] == ["dictation"]
    assert episode["host_service"]["policy"]["host_layer_mutates_stack"] is False


def test_self_awareness_working_stack_usage_gap_routes_to_alert_candidate(monkeypatch, abyss_machine_module) -> None:
    working_event = abyss_machine_module.self_awareness_make_event(
        "service",
        "working-stack",
        event_time="2026-01-01T00:00:00+00:00",
        resource={
            "service": "aoa-browser",
            "container": "aoa-browser",
            "owner_surface": "abyss-stack",
            "path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json",
            "write": False,
        },
        context={
            "working_stack_link_id": "saworklink-fixture",
            "machine_usage_status": "tool_runtime_degraded",
        },
        space={"host": "fixture", "owner_surface": "abyss-stack", "service": "aoa-browser"},
        severity="warning",
        body={"usage_gap": "stack tool is reachable and guarded, but its functional runtime smoke failed"},
        evidence_refs=[{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": "aoa-browser"}],
        truth_level="working_stack_inventory",
    )
    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"usage_gaps": 1},
        "organs": [
            {
                "schema": "abyss_machine_self_awareness_working_stack_organ_v1",
                "service": "aoa-browser",
                "owner_surface": "abyss-stack",
                "machine_usage_status": "tool_runtime_degraded",
                "usage_gap": "stack tool is reachable and guarded, but its functional runtime smoke failed",
                "deep_usage_proven": False,
                "runtime": {
                    "service": "aoa-browser",
                    "container": "aoa-browser",
                    "running": True,
                    "health": "healthy",
                },
                "declared": {"present": True},
                "endpoint_probes": [
                    {"service": "aoa-browser", "probe": "health", "ok": True, "url": "http://127.0.0.1:8000/health"},
                    {"service": "aoa-browser", "probe": "private-host-guard", "ok": True, "status_code": 403, "url": "http://127.0.0.1:8000/read"},
                    {"service": "aoa-browser", "probe": "playwright-chromium-launch", "ok": False, "url": "container://aoa-browser/playwright-chromium-launch"},
                ],
                "time_space_context_link": {
                    "schema": "abyss_machine_self_awareness_working_stack_time_space_context_link_v1",
                    "link_id": "saworklink-fixture",
                    "time": {
                        "observed_at": "2026-01-01T00:00:00+00:00",
                        "bucket": "2026-01-01T00:00:00Z",
                    },
                    "context": {
                        "working_stack_link_id": "saworklink-fixture",
                        "machine_usage_status": "tool_runtime_degraded",
                    },
                },
                "evidence_refs": [
                    {"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": "aoa-browser"},
                    {"path": "/var/lib/abyss-machine/processes/containers/latest.json", "service": "aoa-browser"},
                ],
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
    }
    timeline_doc = {
        "schema": "abyss_machine_self_awareness_timeline_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "events": [working_event],
        "stack_handoff_time_space_overlay": {
            "schema": "abyss_machine_self_awareness_stack_handoff_time_space_overlay_v1",
            "summary": {"open_stack_requirements": 0},
            "timeline_markers": [],
        },
    }
    spatial_doc = {
        "schema": "abyss_machine_self_awareness_spatial_graph_v1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"nodes": 4},
        "nodes": [
            {"id": "service:aoa-browser"},
            {"id": "working_stack_link:saworklink-fixture"},
        ],
        "edges": [],
    }
    investigation = {
        "schema": "abyss_machine_self_awareness_investigation_v1",
        "ok": True,
        "thread_id": "thread-working-gap",
        "selected_episode_id": "",
        "summary": {},
    }
    replay = {
        "schema": "abyss_machine_self_awareness_replay_v1",
        "ok": True,
        "thread_id": "thread-working-gap",
        "summary": {"divergences": 0, "conclusion_diff_changed": False},
    }

    monkeypatch.setattr(abyss_machine_module, "self_awareness_timeline", lambda write_latest=True: timeline_doc)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_spatial_graph", lambda write_latest=True: spatial_doc)

    def fake_load_latest_json(path, schema, *args, **kwargs):
        path_text = str(path)
        if path_text == str(abyss_machine_module.SELF_AWARENESS_WORKING_STACK_LATEST_PATH):
            return working_stack
        if path_text == str(abyss_machine_module.SELF_AWARENESS_INVESTIGATE_LATEST_PATH):
            return investigation
        if path_text == str(abyss_machine_module.SELF_AWARENESS_REPLAY_LATEST_PATH):
            return replay
        if path_text == str(abyss_machine_module.SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH):
            return {"schema": "abyss_machine_self_awareness_requirement_probes_v1", "summary": {"open": 0}}
        if path_text == str(abyss_machine_module.SELF_AWARENESS_CONTEXT_LATEST_PATH):
            return _context_doc_fixture()
        if path_text == str(abyss_machine_module.SELF_AWARENESS_COMPLETION_AUDIT_LATEST_PATH):
            return _completion_audit_doc_fixture()
        return {"schema": schema, "ok": True}

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)

    episodes = abyss_machine_module.self_awareness_episodes(write_latest=False)
    gap_episodes = [item for item in episodes["episodes"] if item.get("episode_kind") == "working_stack_usage_gap"]

    assert episodes["summary"]["working_stack_gap_episodes"] == 1
    assert len(gap_episodes) == 1
    episode = gap_episodes[0]
    assert episode["service"] == "aoa-browser"
    assert episode["truth_level"] == "working_stack_gap_candidate"
    assert "usage_gap" in episode["primary_signals"]
    assert "runtime_smoke" in episode["primary_signals"]
    assert "service:aoa-browser" in episode["affected_spatial_nodes"]
    assert any(node.startswith("usage_gap:") for node in episode["affected_spatial_nodes"])
    assert episode["working_stack_gap"]["working_stack_link_id"] == "saworklink-fixture"
    assert episode["working_stack_gap"]["safe_next_action"]["host_layer_mutates_stack"] is False
    assert episode["working_stack_gap"]["verifier_commands"]
    assert episode["policy"]["host_layer_mutates_stack"] is False
    assert episode["policy"]["executes_commands"] is False

    def fake_load_latest_json_for_alerts(path, schema, *args, **kwargs):
        path_text = str(path)
        if path_text == str(abyss_machine_module.SELF_AWARENESS_EPISODES_LATEST_PATH):
            return episodes
        return fake_load_latest_json(path, schema, *args, **kwargs)

    investigation["selected_episode_id"] = episode["episode_id"]
    monkeypatch.setattr(abyss_machine_module, "self_awareness_load_events", lambda refresh=True: [])
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json_for_alerts)

    alerts = abyss_machine_module.self_awareness_alerts(write_latest=False)

    assert alerts["summary"]["working_stack_gap_candidates"] == 1
    assert alerts["summary"]["response_depth_missing"] == 0
    assert alerts["summary"]["body_trace_missing"] == 0
    candidate = alerts["candidates"][0]
    contract = candidate["response_contract"]
    assert candidate["working_stack_gap_service"] == "aoa-browser"
    assert candidate["working_stack_gap_status"] == "tool_runtime_degraded"
    assert candidate["automatic"] is False
    assert contract["validated_episode"]["episode_kind"] == "working_stack_usage_gap"
    assert contract["validated_episode"]["truth_level"] == "working_stack_gap_candidate"
    assert contract["runbook_candidate"]["owner_route"] == "abyss-stack"
    assert contract["runbook_candidate"]["machine_executes_stack_change"] is False
    assert contract["runbook_candidate"]["host_layer_mutates_stack"] is False
    assert contract["runbook_candidate"]["verifier_commands"]
    assert contract["working_stack_gap"]["service"] == "aoa-browser"
    assert contract["body_trace"]["complete"] is True
    assert contract["working_stack_gap"]["safe_next_action"]["host_layer_mutates_stack"] is False
    assert contract["policy"]["automatic_action"] is False
    assert contract["policy"]["automatic_response"] is False
    assert contract["policy"]["executes_commands"] is False
    assert contract["policy"]["host_layer_mutates_stack"] is False
    assert abyss_machine_module.self_awareness_reaction_candidate_response_depth_complete(candidate) is True


def test_self_awareness_working_stack_gap_investigation_packet_is_replayable(abyss_machine_module) -> None:
    selected = {
        "schema": "abyss_machine_causal_episode_v1",
        "episode_id": "saepisode-working-stack-gap-fixture",
        "episode_kind": "working_stack_usage_gap",
        "truth_level": "working_stack_gap_candidate",
        "service": "aoa-browser",
        "owner_route": "abyss-stack",
        "event_ids": ["event-1"],
        "affected_spatial_nodes": ["service:aoa-browser", "usage_gap:fixture"],
        "working_stack_gap": {
            "schema": "abyss_machine_self_awareness_working_stack_usage_gap_v1",
            "service": "aoa-browser",
            "owner_route": "abyss-stack",
            "working_stack_link_id": "saworklink-fixture",
            "machine_usage_status": "tool_runtime_degraded",
            "usage_gap": "stack tool is reachable and guarded, but its functional runtime smoke failed",
            "closure_blocker_keys": ["tool_runtime_degraded", "usage_gap:fixture"],
            "safe_next_action": {
                "kind": "stack_owner_runtime_usage_gap_review",
                "command": "abyss-machine self-awareness working-stack --json",
                "automatic": False,
                "requires_human_approval": True,
                "executes_commands": False,
                "host_layer_mutates_stack": False,
            },
            "verifier_commands": ["abyss-machine self-awareness validate --json"],
            "policy": {
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "action_execution": False,
            },
        },
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
    }

    packet = abyss_machine_module.self_awareness_investigation_working_stack_gap_packet(selected)

    assert packet["schema"] == "abyss_machine_self_awareness_investigation_working_stack_gap_v1"
    assert packet["complete"] is True
    assert packet["service"] == "aoa-browser"
    assert packet["working_stack_link_id"] == "saworklink-fixture"
    assert packet["request"]["kind"] == "working_stack_usage_gap"
    assert packet["request"]["automatic"] is False
    assert packet["request"]["host_layer_mutates_stack"] is False
    assert packet["request"]["executes_commands"] is False
    assert packet["safe_next_action"]["host_layer_mutates_stack"] is False
    assert packet["verifier_commands"]
    assert packet["policy"]["host_layer_mutates_stack"] is False
    assert abyss_machine_module.self_awareness_investigation_working_stack_gap_complete(packet) is True


def test_self_awareness_investigation_embeds_stack_handoff_action_map_contract(monkeypatch, abyss_machine_module) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.trace-backend",
        "Trace backend",
        reason="fixture trace backend is not readable",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:3200/ready"}]},
        expected_shape={"backend": "Tempo", "mutated_by": "abyss-stack"},
    )
    requirements_doc = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    llm_escalation_detail = {
        "route_ready": True,
        "review_pipeline_ready": True,
        "gates": {"model_execution_now": {"allowed": False, "status": "blocked_by_preflight"}},
        "qwen_lazy_load": {"ready": True},
        "policy": {
            "human_approval_before_mutation": True,
            "operator_force_required_for_model_execution": True,
        },
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "summary": {"requirements": 1},
        "raw": {
            "tempo_ready": {
                "ok": False,
                "url": "http://127.0.0.1:3200/ready",
                "status_code": None,
                "error": "connection refused",
            },
        },
        "capabilities": [{"id": "llm.escalation.routes", "detail": llm_escalation_detail}],
        "requirements": requirements_doc["requirements"],
    }
    selected_episode = {
        "episode_id": "episode-fixture",
        "event_ids": ["event-1"],
        "time_window": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:01:00Z"},
        "affected_spatial_nodes": ["service:route-api"],
        "confidence": {"score": 0.64, "reasons": ["fixture"]},
        "suspected_cause_chain": ["trace backend unavailable"],
        "counter_evidence": ["no direct span evidence"],
        "open_questions": ["span inventory missing"],
        "context_keys": ["service:route-api", "source:observability"],
        "involved_contexts": [{"service": "route-api", "source": "observability"}],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/episodes/latest.json"}],
    }
    query_doc = {
        "schema": "abyss_machine_self_awareness_query_v1",
        "summary": {"event_hits": 1, "episode_hits": 1, "node_hits": 1, "memory_space_hits": 1},
        "query_plan": {
            "promql": ["up"],
            "logql": ['{container="route-api"}'],
            "context_keys": ["trace_id"],
            "readmodels": ["self_awareness"],
        },
        "results": {"episodes": [selected_episode]},
    }
    correlation = {
        "schema": "abyss_machine_self_awareness_correlation_v1",
        "summary": {"joins": 1},
        "slo_views": [],
        "anomaly_baselines": [],
    }
    context_doc = _context_doc_fixture()
    resident_detail = {
        "ok": True,
        "status": "running",
        "serving": {"owner": "abyss-stack", "stack_owned_serving": True},
        "health": {"ok": True, "health_latency_ms": 11.5, "model_id": "gemma4-e2b-it"},
        "monitor": {
            "ok": True,
            "monitor_timer_active": "active",
            "digest_timer_active": "active",
            "micro_timer_active": "active",
        },
        "resource_thermal": {"package_temp_c": 55.0},
        "candidate_context": {
            "digest_ok": True,
            "micro_ok": True,
            "candidates": 4,
            "review_required": 2,
            "action_execution": False,
            "candidate_readmodel": {"ok": True},
        },
        "evals": {"overall_score": 1.0},
        "policy": {
            "model_execution_in_self_awareness_graph": False,
            "candidate_synthesis_only": True,
            "host_layer_mutates_stack": False,
            "abyss_machine_writes_stack": False,
            "candidate_output_is_owner_truth": False,
        },
        "cognitive_contract": {
            "schema": "abyss_machine_self_awareness_resident_cognitive_contract_v1",
            "bounded_context_packet_required": True,
            "read_only_tool_inventory_required": True,
            "hypothesis_testing_required": True,
            "contradiction_notes_required": True,
            "resource_mode_gated_escalation_required": True,
            "direct_model_generation_in_self_awareness": False,
            "host_layer_mutates_stack": False,
        },
    }

    def fake_load_latest_json(path, schema):
        if "rag_validate" in schema:
            return {"schema": "abyss_machine_rag_validate_v1", "ok": True, "summary": {"status": "ok"}}
        if "nervous_brief" in schema:
            return {"schema": "abyss_machine_nervous_brief_v1", "readiness": {"status": "ready"}}
        if "self_awareness_context" in schema:
            return context_doc
        if "self_awareness_episodes" in schema:
            return {"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": [selected_episode]}
        return {"schema": schema, "ok": True, "status": "ok", "summary": {}}

    monkeypatch.setattr(abyss_machine_module, "self_awareness_capabilities", lambda write_latest=True: capabilities)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_correlation", lambda write_latest=True: correlation)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_query", lambda query, limit=30, write_latest=True: query_doc)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_requirements", lambda write_latest=True: requirements_doc)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_context", lambda write_latest=True: context_doc)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_resident_worker_detail", lambda *args: resident_detail)
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)

    payload = abyss_machine_module.self_awareness_investigate("trace backend handoff", write_latest=False)

    assert payload["schema"] == "abyss_machine_self_awareness_investigation_v1"
    assert payload["ok"] is True
    assert payload["summary"]["stack_handoff_actions"] == 1
    assert payload["summary"]["top_stack_handoff_requirement"] == "stack.trace-backend"
    assert payload["summary"]["stack_handoff_closure_readiness_packets"] == 1
    assert payload["summary"]["stack_handoff_closure_readiness_missing_checks"] >= 1
    assert payload["summary"]["body_trace_complete"] is True
    assert payload["body_trace"]["host_body"]["complete"] is True
    assert payload["stack_handoff_action_map"]["schema"] == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert payload["stack_handoff_action_map"]["summary"]["coverage_impact_entries"] == 1
    assert "signal_fabric" in payload["stack_handoff_action_map"]["summary"]["blocked_coverage_planes"]
    assert payload["stack_handoff_closure_readiness"]["schema"] == "abyss_machine_self_awareness_investigation_stack_handoff_closure_readiness_v1"
    assert payload["stack_handoff_closure_readiness"]["summary"]["complete"] is True
    assert payload["stack_handoff_closure_readiness"]["summary"]["packets"] == 1
    assert payload["stack_handoff_closure_readiness"]["summary"]["coverage_impact_entries"] == 1

    states = {row["node"]: row["state"] for row in payload["states"]}
    requests_state = states["request_more_evidence"]
    action_map = requests_state["stack_handoff_action_map"]
    closure_readiness = requests_state["stack_handoff_closure_readiness"]
    stack_requests = [request for request in requests_state["requests"] if request.get("kind") == "stack_handoff_action"]
    assert action_map["summary"]["open_stack_requirements"] == len(action_map["actions"]) == 1
    assert closure_readiness["summary"]["packets"] == len(action_map["actions"])
    assert closure_readiness["summary"]["coverage_impact_entries"] == len(action_map["actions"])
    assert "langgraph_replay" in closure_readiness["summary"]["blocked_coverage_planes"]
    assert closure_readiness["ordered_next_actions"][0]["requirement_id"] == "stack.trace-backend"
    assert closure_readiness["ordered_next_actions"][0]["coverage_impact"]["organ"] == "trace_join_backbone"
    assert closure_readiness["policy"]["host_layer_mutates_stack"] is False
    assert closure_readiness["policy"]["executes_commands"] is False
    assert stack_requests and len(stack_requests) == len(action_map["actions"])
    assert requests_state["stack_handoff_action_summary"]["top_requirement_id"] == "stack.trace-backend"
    assert requests_state["all_requests_non_mutating"] is True

    request = stack_requests[0]
    assert request["requirement_id"] == "stack.trace-backend"
    assert request["closure_blockers"]
    assert request["closure_blocker_keys"]
    assert request["runbook_candidate_id"] == "stack-runbook-stack-trace-backend"
    assert request["runbook_candidate"]["machine_executes_stack_change"] is False
    assert request["acceptance_verifiers"]
    assert request["verifier_commands"]
    assert request["closure_readiness"]["schema"] == "abyss_machine_stack_handoff_closure_readiness_v1"
    assert request["closure_readiness"]["blocking_check_keys"]
    assert request["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
    assert request["coverage_impact"]["organ"] == "trace_join_backbone"
    assert "causal_timeline" in request["coverage_planes"]
    assert request["safe_next_action"]["requires_human_approval"] is True
    assert request["safe_next_action"]["automatic"] is False
    assert request["policy"]["host_layer_mutates_stack"] is False
    assert request["policy"]["executes_commands"] is False

    validation_checks = {
        check["id"]: check
        for check in states["validate_evidence"]["validation"]["checks"]
    }
    assert validation_checks["stack_handoff_action_map_complete"]["ok"] is True
    assert validation_checks["stack_handoff_closure_readiness_complete"]["ok"] is True
    assert validation_checks["stack_handoff_coverage_impact_complete"]["ok"] is True
    assert states["validate_evidence"]["validation"]["summary"]["fails"] == 0

    brief_state = states["brief_reaction_candidate"]
    assert brief_state["stack_handoff_action_map"]["summary"]["top_requirement_id"] == "stack.trace-backend"
    assert brief_state["stack_handoff_closure_readiness"]["summary"]["packets"] == 1
    assert brief_state["top_stack_handoff_action"]["requirement_id"] == "stack.trace-backend"
    assert brief_state["top_stack_handoff_action"]["coverage_impact"]["organ"] == "trace_join_backbone"
    assert brief_state["safe_next_action"]["command"] == "abyss-machine self-awareness export --json"
    assert brief_state["safe_next_action"]["host_layer_mutates_stack"] is False

    conclusion = payload["conclusion"]
    assert conclusion["stack_handoff_action_map"]["schema"] == "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1"
    assert conclusion["stack_handoff_action_map"]["coverage_impact_by_requirement"]["stack.trace-backend"]["organ"] == "trace_join_backbone"
    assert conclusion["stack_handoff_closure_readiness"]["summary"]["packets"] == 1
    assert conclusion["stack_handoff_closure_readiness"]["policy"]["host_layer_mutates_stack"] is False
    assert conclusion["top_stack_handoff_action"]["requirement_id"] == "stack.trace-backend"
    assert conclusion["next_safe_action"]["requires_human_approval"] is True
    assert conclusion["next_safe_action"]["host_layer_mutates_stack"] is False


def test_self_awareness_langchain_requirement_probe_uses_live_api_metadata_without_false_closure(abyss_machine_module) -> None:
    requirement = abyss_machine_module.self_awareness_requirement_item(
        "stack.langchain-api.graph-observability",
        "LangChain graph observability",
        reason="fixture langchain-api is live but graph inventory is absent",
        detection={"evidence_refs": [{"url": "http://127.0.0.1:5403/openapi.json"}]},
        expected_shape={"endpoints": ["/health", "/openapi.json", "/threads", "/checkpoints", "/traces"], "mutated_by": "abyss-stack"},
    )
    document = abyss_machine_module.self_awareness_requirements_document(
        [requirement],
        "2026-01-01T00:00:00+00:00",
    )
    langchain_api = {
        "schema": "abyss_machine_stack_langchain_api_probe_v1",
        "base_url": "http://127.0.0.1:5403",
        "ok": True,
        "health": {"url": "http://127.0.0.1:5403/health", "ok": True, "status_code": 200, "service": "langchain-api"},
        "openapi": {
            "url": "http://127.0.0.1:5403/openapi.json",
            "ok": True,
            "status_code": 200,
            "path_count": 4,
            "paths": [
                {"path": "/health", "methods": ["GET"]},
                {"path": "/run", "methods": ["POST"]},
                {"path": "/run/federated", "methods": ["POST"]},
                {"path": "/embeddings", "methods": ["POST"]},
            ],
        },
        "observability": {
            "health_readable": True,
            "openapi_readable": True,
            "checkpoint_inventory_present": False,
            "trace_inventory_present": False,
            "graph_observability_complete": False,
        },
        "evidence_refs": [
            {"url": "http://127.0.0.1:5403/health", "status_code": 200},
            {"url": "http://127.0.0.1:5403/openapi.json", "status_code": 200},
        ],
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "raw": {"langchain_api": langchain_api},
        "capabilities": [
            {
                "id": "stack.langchain-api.health-openapi",
                "detail": {"base_url": "http://127.0.0.1:5403", "observability": langchain_api["observability"]},
                "evidence_refs": langchain_api["evidence_refs"],
            }
        ],
    }

    payload = abyss_machine_module.self_awareness_requirement_probes(
        write_latest=False,
        requirements_doc=document,
        capabilities=capabilities,
    )

    probe = payload["probes"][0]
    assert probe["id"] == "stack.langchain-api.graph-observability"
    assert probe["status"] == "open"
    assert probe["closed_by_current_probe"] is False
    assert probe["current_state"]["langchain_api_base_url"] == "http://127.0.0.1:5403"
    assert probe["current_state"]["api_health_ok"] is True
    assert probe["current_state"]["openapi_ok"] is True
    assert probe["current_state"]["checkpoint_inventory_present"] is False
    assert probe["current_state"]["trace_inventory_present"] is False
    assert any(row["path"] == "/health" for row in probe["current_state"]["openapi_paths"])
    assert "openapi_paths" in probe["machine_closure_probe"]["required_fields"]
    check_by_key = {check["key"]: check for check in probe["checks"]}
    assert check_by_key["langchain_api_health_readable"]["ok"] is True
    assert check_by_key["langchain_api_openapi_readable"]["ok"] is True
    assert check_by_key["langchain_langgraph_inventory_readable"]["level"] == "open"
    assert check_by_key["no_secret_leakage"]["ok"] is True
    assert probe["host_layer_mutates_stack"] is False


def test_self_awareness_governance_gate_detail_is_concrete_and_non_mutating(abyss_machine_module) -> None:
    detail = abyss_machine_module.self_awareness_governance_gate_detail(
        {
            "schema": "abyss_machine_memory_status_v1",
            "ok": True,
            "class": "warm",
            "reasons": ["fixture"],
            "meminfo": {"summary": {"mem_available_mib": 16000.0, "mem_available_percent": 50.0, "swap_used_percent": 20.0}},
            "psi": {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}},
            "zram": {"summary": {"total_memory_mib": 1024.0}},
            "policy": {"automatic_kill": False, "automatic_tuning": False},
        },
        {
            "schema": "abyss_machine_resource_status_v1",
            "ok": True,
            "latest_plan": {"decision": "allow", "request": {"class": "medium", "kind": "indexing", "unattended": True}},
            "latest_run": {"ok": True, "request": {"class": "medium", "kind": "indexing", "unattended": True}},
            "latest_orchestrator": {"summary": {"status": "ok", "fails": 0, "warnings": 0, "checks": 11}},
            "contract": {
                "launches_new_processes_only": True,
                "systemd_user_scope": True,
                "future_stack_consumption": "abyss-stack may consume resource plan before stack-owned launches.",
            },
        },
        {
            "schema": "abyss_machine_mode_status_v1",
            "selected_mode": "balanced",
            "effective_mode": "balanced",
            "degraded": False,
            "degraded_reasons": [],
            "target_power_profile": "balanced",
            "actual_power_profile": "balanced",
            "profile_matches_target": True,
            "power_profile_external_boost": False,
            "thermal": {"temperature_c_max": 76.0},
            "operating": {"thermal_class": "warm", "temperature": {"class": "warm"}},
            "launch_policy": {
                "max_unattended_class": "medium",
                "can_start_heavy_unattended": False,
                "can_start_sustained_unattended": False,
                "gate_new_unattended_tasks": True,
                "do_not_kill_running_tasks": True,
            },
        },
    )

    assert abyss_machine_module.self_awareness_governance_gate_detail_complete(detail) is True
    assert detail["memory_status"] == "warm"
    assert detail["resource_status"] == "ok"
    assert detail["mode_status"] == "balanced"
    assert detail["readiness"]["status"] == "ready"
    assert detail["memory"]["class"] == "warm"
    assert detail["resource"]["latest_plan_decision"] == "allow"
    assert detail["mode"]["effective_mode"] == "balanced"
    assert detail["policy"]["host_layer_mutates_stack"] is False
    assert detail["policy"]["mutates_existing_processes"] is False
    assert detail["policy"]["automatic_remediation"] is False


def test_self_awareness_resident_worker_detail_is_monitored_candidate_only(abyss_machine_module) -> None:
    detail = abyss_machine_module.self_awareness_resident_worker_detail(
        {
            "schema": "abyss_machine_gemma4_spark_resident_status_v1",
            "ok": True,
            "status": "running",
            "profile": "gemma4.spark",
            "model": {"path": "/srv/abyss-machine/cache/ai/gemma4/e2b/model.gguf", "exists": True, "size_bytes": 3184494720},
            "health": {
                "serving": {
                    "owner": "abyss-stack",
                    "base_url": "http://127.0.0.1:11435",
                    "external_endpoint": True,
                    "local_fallback_allowed": False,
                },
                "health": {"status": "ok", "_http": {"ok": True, "status": 200, "latency_ms": 12.5}},
                "models": {
                    "_http": {"ok": True, "status": 200, "latency_ms": 3.0},
                    "data": [{"id": "gemma4-e2b-it", "meta": {"n_ctx": 4096, "n_ctx_train": 131072, "n_embd": 1536, "n_params": 4647450147, "size": 3168675980}}],
                },
                "ok": True,
            },
        },
        {
            "schema": "abyss_machine_gemma4_spark_resident_monitor_v1",
            "ok": None,
            "status": {
                "ok": True,
                "status": "running",
                "service": {
                    "service": "abyss-gemma4-spark.service",
                    "active": "inactive",
                    "enabled": "linked",
                    "timer": {"unit": "abyss-gemma4-spark.timer", "active": "inactive"},
                    "monitor_timer": {"unit": "abyss-gemma4-spark-monitor.timer", "active": "active"},
                    "digest_timer": {"unit": "abyss-gemma4-spark-digest.timer", "active": "active"},
                    "jobs_timer": {"unit": "abyss-gemma4-spark-jobs.timer", "active": "active"},
                    "micro_timer": {"unit": "abyss-gemma4-spark-micro.timer", "active": "active"},
                },
                "metrics": {"package_temp_c": 73.0, "loadavg": "2.0 2.5 3.0 1/100 123", "power": {"profile": "balanced", "on_ac": True}},
            },
        },
        {"schema": "abyss_machine_gemma4_spark_resident_digest_v1", "ok": True, "status": "idle"},
        {
            "schema": "abyss_machine_gemma4_spark_resident_micro_tick_v1",
            "ok": True,
            "summary": {
                "selected_job": "risk_sentinel",
                "next_job": "action_card_compiler",
                "status": "ok_deterministic",
                "model_used": False,
                "fallback_used": False,
                "elapsed_ms": 65.6,
                "candidate_readmodel": {"ok": True, "status": "ok", "candidates": 64},
            },
        },
        {
            "schema": "abyss_machine_gemma4_spark_resident_heartbeat_evals_v1",
            "ok": True,
            "summary": {"overall_score": 1.0, "checks": 39, "fails": 0, "warnings": 0, "candidates": 69, "selected_for_e4b_review": 24, "degraded_or_fallback_jobs": 0, "elapsed_ms": 445.7},
        },
        {
            "schema": "abyss_machine_gemma4_spark_resident_candidate_readmodel_v2",
            "ok": True,
            "summary": {"candidates": 64, "review_required": 28, "selected": 24, "selected_for_heartbeat": 16, "selected_for_e4b_review": 24, "action_execution": False},
        },
    )

    assert abyss_machine_module.self_awareness_resident_worker_detail_complete(detail) is True
    assert detail["serving"]["owner"] == "abyss-stack"
    assert detail["serving"]["stack_owned_serving"] is True
    assert detail["health"]["health_latency_ms"] == 12.5
    assert detail["health"]["model_id"] == "gemma4-e2b-it"
    assert detail["health"]["n_ctx"] == 4096
    assert detail["monitor"]["monitor_timer_active"] == "active"
    assert detail["monitor"]["stack_owned_mode_legacy_service_expected_inactive"] is True
    assert detail["resource_thermal"]["package_temp_c"] == 73.0
    assert detail["candidate_context"]["micro_model_used"] is False
    assert detail["candidate_context"]["action_execution"] is False
    assert detail["candidate_context"]["candidates"] == 64
    assert detail["evals"]["overall_score"] == 1.0
    assert detail["policy"]["model_execution_in_self_awareness_graph"] is False
    assert detail["policy"]["host_layer_mutates_stack"] is False
    assert detail["policy"]["candidate_output_is_owner_truth"] is False
    assert detail["cognitive_contract"]["schema"] == "abyss_machine_self_awareness_resident_cognitive_contract_v1"
    assert detail["cognitive_contract"]["bounded_context_packet_required"] is True
    assert detail["cognitive_contract"]["read_only_tool_inventory_required"] is True
    assert detail["cognitive_contract"]["hypothesis_testing_required"] is True
    assert detail["cognitive_contract"]["contradiction_notes_required"] is True
    assert detail["cognitive_contract"]["direct_model_generation_in_self_awareness"] is False

    packet = abyss_machine_module.self_awareness_resident_cognitive_packet(
        query_text="warm e2b stack rag hypothesis",
        selected_episode={
            "episode_id": "episode-1",
            "time_window": {"start": "2026-01-01T00:00:00+00:00", "end": "2026-01-01T00:01:00+00:00"},
            "affected_spatial_nodes": ["service:route-api"],
            "context_keys": ["service:route-api", "source:synthetic"],
            "confidence": {"score": 0.62},
            "suspected_cause_chain": ["candidate context/resource/time link"],
            "counter_evidence": ["trace backend absent"],
            "event_ids": ["event-1"],
        },
        resident_detail=detail,
        query_doc={"query_plan": {"promql": ["up"], "logql": ['{container="route-api"}'], "context_keys": ["trace_id"]}, "summary": {"event_hits": 1}},
        correlation={"summary": {"joins": 1}, "slo_views": [], "anomaly_baselines": []},
        memory_space={"summary": {"blocked_gates": 1, "retrieval_packets": 1}},
        llm_escalation_detail={
            "route_ready": True,
            "review_pipeline_ready": True,
            "gates": {"model_execution_now": {"allowed": False, "status": "blocked_by_preflight"}},
            "qwen_lazy_load": {"ready": True},
            "policy": {"human_approval_before_mutation": True, "operator_force_required_for_model_execution": True},
        },
        rag_validation={"ok": True, "summary": {"status": "ok"}},
        nervous={"readiness": {"status": "ready"}},
        artifact_refs=[{"path": "/var/lib/abyss-machine/self-awareness/query/latest.json"}],
        context_doc=_context_doc_fixture(),
        completion_audit_doc=_completion_audit_doc_fixture(),
    )

    assert abyss_machine_module.self_awareness_resident_cognitive_packet_complete(packet) is True
    assert packet["schema"] == "abyss_machine_self_awareness_resident_cognitive_packet_v1"
    assert packet["body_trace"]["complete"] is True
    assert packet["completion_route_context"]["complete"] is True
    assert packet["completion_route_context"]["top_packet"]["route_id"] == "observability.trace_join_backbone"
    assert packet["completion_route_context"]["top_packet"]["entity_ids"] == ["stack.requirement.stack.trace-backend"]
    assert packet["body_trace"]["host_body"]["complete"] is True
    assert packet["bounded_context"]["raw_private_content"] is False
    assert packet["bounded_context"]["freshness_must_precede_reasoning"] is True
    assert len(packet["read_only_tools"]) >= 9
    assert all(tool["read_only"] is True and tool["host_layer_mutates_stack"] is False for tool in packet["read_only_tools"])
    assert "completion_route_packets" in {tool["kind"] for tool in packet["read_only_tools"]}
    assert len(packet["hypothesis_tests"]) >= 3
    assert any(test["id"] == "completion_route_packet_context" for test in packet["hypothesis_tests"])
    assert packet["contradiction_notes"]
    assert any(note["id"] == "completion_route_owner_boundary" for note in packet["contradiction_notes"])
    assert packet["escalation_gate"]["human_approval_before_mutation"] is True
    assert packet["escalation_gate"]["action_execution"] is False
    assert packet["policy"]["direct_model_prompt_executed"] is False
    assert packet["policy"]["read_only_tools_only"] is True


def test_self_awareness_resident_completion_route_context_accepts_complete_empty_no_actions(
    abyss_machine_module,
) -> None:
    completion_audit_doc = {
        "schema": "abyss_machine_self_awareness_completion_audit_v1",
        "completion_route_map": {"summary": {"routes": 0}},
        "action_backlog": {"summary": {"actions": 0}},
        "completion_route_packets": {
            "schema": "abyss_machine_self_awareness_completion_route_packet_index_v1",
            "ok": True,
            "summary": {
                "routes": 0,
                "packets": 0,
                "packets_complete": 0,
                "actions": 0,
                "covered_actions": 0,
                "unmapped_actions": [],
                "unmapped_routes": [],
                "automation_ready": True,
            },
            "packets": [],
            "automation": {
                "mode": "latest_only_readmodel",
                "runs_probe": False,
                "runs_cycle": False,
                "runs_indexing": False,
                "runs_stack_http_probes": False,
                "executes_verifiers": False,
                "validation_contract": {
                    "every_completion_route_has_packet": True,
                    "every_completion_action_has_route_packet": True,
                    "every_packet_has_entities_events_documents": True,
                    "host_layer_mutates_stack": False,
                },
            },
            "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
        },
        "entity_event_document_map": {"schema": "abyss_machine_self_awareness_entity_event_document_map_v1"},
    }

    context = abyss_machine_module.self_awareness_resident_completion_route_context(completion_audit_doc)

    assert context["complete"] is True
    assert context["state"] == "complete_empty_no_actions"
    assert context["top_packet"] == {}
    assert context["ordered_packets"] == []
    assert context["expected_actions"] == 0
    assert abyss_machine_module.self_awareness_resident_completion_route_context_complete(context) is True


def test_self_awareness_resident_cognitive_replay_summary_preserves_packet_across_states(
    abyss_machine_module,
) -> None:
    resident_detail = {
        "ok": True,
        "status": "running",
        "serving": {"owner": "abyss-stack", "stack_owned_serving": True},
        "health": {"ok": True, "health_latency_ms": 12.5, "model_id": "gemma4-e2b-it"},
        "monitor": {"ok": True, "monitor_timer_active": "active", "digest_timer_active": "active", "micro_timer_active": "active"},
        "resource_thermal": {"package_temp_c": 67.0},
        "candidate_context": {"digest_ok": True, "micro_ok": True, "candidates": 64, "action_execution": False},
        "evals": {"overall_score": 1.0},
        "policy": {
            "model_execution_in_self_awareness_graph": False,
            "candidate_synthesis_only": True,
            "host_layer_mutates_stack": False,
            "abyss_machine_writes_stack": False,
            "candidate_output_is_owner_truth": False,
        },
        "cognitive_contract": {
            "schema": "abyss_machine_self_awareness_resident_cognitive_contract_v1",
            "bounded_context_packet_required": True,
            "read_only_tool_inventory_required": True,
            "hypothesis_testing_required": True,
            "contradiction_notes_required": True,
            "resource_mode_gated_escalation_required": True,
            "direct_model_generation_in_self_awareness": False,
            "host_layer_mutates_stack": False,
        },
    }
    selected_episode = {
        "episode_id": "episode-1",
        "time_window": {"start": "2026-01-01T00:00:00+00:00", "end": "2026-01-01T00:01:00+00:00"},
        "affected_spatial_nodes": ["service:route-api"],
        "context_keys": ["service:route-api", "source:synthetic"],
        "event_ids": ["event-1"],
        "confidence": {"score": 0.62},
        "suspected_cause_chain": ["candidate context/resource/time link"],
        "counter_evidence": ["trace backend absent"],
    }
    packet = abyss_machine_module.self_awareness_resident_cognitive_packet(
        query_text="warm e2b replay export",
        selected_episode=selected_episode,
        resident_detail=resident_detail,
        query_doc={"query_plan": {"promql": ["up"], "logql": ['{container="route-api"}']}},
        correlation={"summary": {"joins": 1}},
        memory_space={"summary": {"blocked_gates": 1}},
        llm_escalation_detail={
            "route_ready": True,
            "review_pipeline_ready": True,
            "gates": {"model_execution_now": {"allowed": False, "status": "blocked_by_preflight"}},
            "qwen_lazy_load": {"ready": True},
            "policy": {"human_approval_before_mutation": True, "operator_force_required_for_model_execution": True},
        },
        rag_validation={"ok": True, "summary": {"status": "ok"}},
        nervous={"readiness": {"status": "ready"}},
        artifact_refs=[{"path": "/var/lib/abyss-machine/self-awareness/query/latest.json"}],
        context_doc=_context_doc_fixture(),
        completion_audit_doc=_completion_audit_doc_fixture(),
    )
    state_by_node = {
        "resident_context_packet": {"resident_cognitive_packet": packet, "body_trace": packet["body_trace"]},
        "reason_over_evidence": {
            "body_trace": packet["body_trace"],
            "completion_route_context": packet["completion_route_context"],
            "hypotheses": [{"statement": "base"}] + packet["hypothesis_tests"],
            "contradiction_notes": packet["contradiction_notes"],
        },
    }
    investigation = {
        "thread_id": "sainv-fixture",
        "selected_episode_id": "episode-1",
        "resident_cognitive_packet": packet,
        "body_trace": packet["body_trace"],
        "completion_route_context": packet["completion_route_context"],
        "conclusion": {
            "resident_worker": {"profile": "gemma4.spark", "status": "running"},
            "body_trace": packet["body_trace"],
            "completion_route_context": packet["completion_route_context"],
            "resident_cognitive_packet": {
                "schema": packet["schema"],
                "read_only_tools": len(packet["read_only_tools"]),
                "hypothesis_tests": len(packet["hypothesis_tests"]),
                "contradiction_notes": len(packet["contradiction_notes"]),
                "complete": True,
                "completion_route_context_complete": True,
                "top_completion_route_id": "observability.trace_join_backbone",
            },
        },
    }

    replay = abyss_machine_module.self_awareness_resident_cognitive_replay_summary(investigation, state_by_node)

    assert abyss_machine_module.self_awareness_resident_cognitive_replay_complete(replay) is True
    assert replay["schema"] == "abyss_machine_self_awareness_resident_cognitive_replay_v1"
    assert replay["complete"] is True
    assert replay["state_preservation"] == {
        "investigation_top_level": True,
        "resident_context_packet": True,
        "reason_over_evidence": True,
        "write_semantic_conclusion": True,
        "body_trace": True,
        "completion_route_context": True,
    }
    assert replay["body_trace"]["complete"] is True
    assert replay["summary"]["body_trace_complete"] is True
    assert replay["summary"]["completion_route_context_complete"] is True
    assert replay["summary"]["top_completion_route_id"] == "observability.trace_join_backbone"
    assert replay["summary"]["read_only_tools"] >= 9
    assert replay["summary"]["hypothesis_tests"] >= 3
    assert replay["summary"]["contradiction_notes"] >= 1
    assert replay["packet_digest"] == replay["checkpoint_packet_digest"]
    assert replay["completion_route_context"]["top_packet"]["route_id"] == "observability.trace_join_backbone"
    assert replay["policy"]["direct_model_prompt_executed"] is False
    assert replay["policy"]["host_layer_mutates_stack"] is False
    assert replay["evidence_cited_summary"]["evidence_refs"]


def test_self_awareness_bounded_context_packet_joins_memory_handoff_resident_and_governance(abyss_machine_module) -> None:
    resident_detail = {
        "ok": True,
        "status": "running",
        "serving": {"owner": "abyss-stack", "stack_owned_serving": True},
        "health": {"ok": True, "health_latency_ms": 12.5, "model_id": "gemma4-e2b-it"},
        "monitor": {"ok": True, "monitor_timer_active": "active", "digest_timer_active": "active", "micro_timer_active": "active"},
        "resource_thermal": {"package_temp_c": 67.0},
        "candidate_context": {"digest_ok": True, "micro_ok": True, "candidates": 64, "action_execution": False},
        "evals": {"overall_score": 1.0},
        "policy": {
            "model_execution_in_self_awareness_graph": False,
            "candidate_synthesis_only": True,
            "host_layer_mutates_stack": False,
            "abyss_machine_writes_stack": False,
            "candidate_output_is_owner_truth": False,
        },
        "cognitive_contract": {
            "schema": "abyss_machine_self_awareness_resident_cognitive_contract_v1",
            "bounded_context_packet_required": True,
            "read_only_tool_inventory_required": True,
            "hypothesis_testing_required": True,
            "contradiction_notes_required": True,
            "resource_mode_gated_escalation_required": True,
            "direct_model_generation_in_self_awareness": False,
            "host_layer_mutates_stack": False,
        },
    }
    governance_detail = {
        "memory_status": "warm",
        "resource_status": "ok",
        "mode_status": "balanced",
        "readiness": {"status": "ready"},
        "memory": {"class": "warm"},
        "resource": {"orchestrator_summary": {"status": "ok"}},
        "mode": {"effective_mode": "balanced"},
        "policy": {"host_layer_mutates_stack": False, "mutates_existing_processes": False, "automatic_remediation": False},
    }
    readiness = {
        "schema": "abyss_machine_stack_handoff_closure_readiness_v1",
        "readiness_score": 0.67,
        "open_blocker_count": 1,
        "missing_checks": [{"key": "trace_backend_ready"}],
        "blocking_check_keys": ["trace_backend_ready"],
        "dependency_requirement_ids": [],
        "safe_next_action": {"requires_human_approval": True, "automatic": False, "host_layer_mutates_stack": False, "executes_commands": False},
        "verifier_commands": ["abyss-machine self-awareness requirement-probes --json"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/requirement-probes/latest.json"}],
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "action_execution": False},
    }
    coverage_impact = abyss_machine_module.self_awareness_stack_requirement_coverage_impact("stack.trace-backend")
    action_map = {
        "schema": "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1",
        "summary": {
            "open_stack_requirements": 1,
            "actions": 1,
            "coverage_impact_entries": 1,
            "blocked_coverage_planes": coverage_impact["coverage_planes"],
            "top_requirement_id": "stack.trace-backend",
        },
        "open_requirement_ids": ["stack.trace-backend"],
        "actions": [
            {
                "requirement_id": "stack.trace-backend",
                "priority_rank": 1,
                "priority_class": "critical_trace_join",
                "impact_organ": coverage_impact["organ"],
                "coverage_planes": coverage_impact["coverage_planes"],
                "coverage_impact": coverage_impact,
                "closure_blocker_keys": ["trace_backend_ready"],
                "closure_readiness": readiness,
                "verifier_commands": readiness["verifier_commands"],
                "safe_next_action": readiness["safe_next_action"],
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
                "evidence_refs": readiness["evidence_refs"],
            }
        ],
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False, "raw_secrets_included": False},
    }
    memory_space = {
        "schema": "abyss_machine_self_awareness_memory_space_overlay_v1",
        "summary": {"retrieval_packets": 1, "blocked_gates": 1},
        "freshness_gates": [
            {
                "gate_id": "nervous_freshness",
                "status": "stale",
                "blocks_deep_reasoning": True,
                "maintenance_route": abyss_machine_module.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
                "freshness_must_precede_reasoning": True,
                "raw_evidence_is_not_truth": True,
                "evidence_refs": [
                    {
                        "path": "/var/lib/abyss-machine/nervous/indexes/semantic/maintain/latest.json",
                        "schema": "abyss_machine_nervous_semantic_maintain_v1",
                        "truth_level": "nervous_semantic_maintain",
                        "ok": True,
                    }
                ],
                "details": {
                    "readiness": {"status": "degraded", "semantic_stale": True, "semantic_maintenance_needed": True},
                    "semantic_maintain": {
                        "decision": "blocked_index_refresh",
                        "reason": "resource gate blocked source index refresh before semantic maintenance",
                        "ok": True,
                        "resource": {"class": "medium", "kind": "indexing", "unattended": True},
                        "assessment": {"needed": True, "stale": True, "reasons": ["stale_age_minutes=1742.1"]},
                        "index_refresh_assessment": {"needed": True, "stale": True, "records_lag": 18},
                        "index_refresh_blocked_reasons": ["indexing_unattended_swap_used_pressure"],
                        "index_refresh_denied_reasons": [],
                        "build_blocked_reasons": [],
                        "build_denied_reasons": [],
                    },
                    "resource_denial_is_safe_gate": True,
                    "policy": {"does_not_bypass_resource_gate": True, "automatic_remediation": False, "host_layer_mutates_stack": False},
                },
            }
        ],
        "retrieval_packets": [{"id": "rag:fixture"}],
        "stack_semantic_backends": [{"id": "postgres"}, {"id": "neo4j"}, {"id": "rag-api"}, {"id": "embeddings"}],
        "policy": {"bounded_retrieval": True, "freshness_must_precede_reasoning": True, "raw_evidence_is_not_truth": True, "host_layer_mutates_stack": False},
    }
    capabilities = {
        "capabilities": [
            {"id": "warm-e2b.resident-cognitive-worker", "detail": resident_detail},
            {"id": "host.governance-gates", "detail": governance_detail},
            {"id": "llm.escalation.routes", "detail": {"route_ready": True, "gates": {"model_execution_now": {"allowed": False, "status": "blocked_by_preflight"}}, "qwen_lazy_load": {"ready": True}, "policy": {"host_layer_mutates_stack": False, "action_execution": False}}},
        ]
    }
    trace_context = {
        "schema": "abyss_machine_self_awareness_trace_context_fallback_v1",
        "status": "fallback_ready_stack_trace_backend_open",
        "stack_requirement_id": "stack.trace-backend",
        "closes_stack_requirement": False,
        "summary": {
            "trace_backend_ready": False,
            "trace_search_readable": False,
            "span_log_metric_join_supported": False,
            "metrics_log_pipeline_readable": True,
            "traceparent_log_query_ok": True,
            "traceparent_log_entries_seen": 0,
            "trace_context_query_safe_empty": True,
            "bounded_trace_context_links": 3,
            "stack_requirement_not_closed_by_fallback": True,
            "blocked_coverage_planes": ["signal_fabric", "causal_timeline", "spatial_graph", "langgraph_replay"],
            "missing_checks": [
                {"key": "trace_backend_ready", "level": "open"},
                {"key": "trace_span_search_readable", "level": "open"},
                {"key": "span_log_metric_join_supported", "level": "open"},
            ],
        },
        "fallback": {
            "loki_trace_context": {
                "query": "{job=~\".+\"} |= \"traceparent\"",
                "query_ok": True,
                "entries_seen": 0,
                "safe_empty_result": True,
                "stores_line_hashes_only": True,
                "raw_log_exports_stored": False,
            },
            "alloy_loki_pipeline": {"alloy_seen": True, "metrics_log_pipeline_readable": True},
        },
        "safe_next_action": {
            "owner_route": "abyss-stack",
            "requirement_id": "stack.trace-backend",
            "command": "abyss-machine self-awareness requirement-probes --json",
            "requires_human_approval": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic": False,
        },
        "evidence_refs": [
            {"path": "/var/lib/abyss-machine/stack-bridge/observability/latest.json", "schema": "abyss_machine_stack_observability_v1", "section": "loki.trace_context"},
            {"path": "/var/lib/abyss-machine/self-awareness/requirement-probes/latest.json", "schema": "abyss_machine_self_awareness_requirement_probes_v1", "requirement_id": "stack.trace-backend"},
        ],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "closes_stack_requirement": False,
            "adds_loki_labels": False,
            "high_cardinality_labels_added": False,
            "raw_span_payloads_stored": False,
            "raw_log_exports_stored": False,
            "raw_trace_payloads_stored": False,
            "fallback_is_not_backend": True,
        },
    }
    contexts = {
        "trace-1": {
            "key": "trace-1",
            "event_ids": ["evt-1"],
            "signals": {"log": 1},
            "sources": {"loki": 1},
            "context": {"trace_id": "trace-1", "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"},
        },
        "scheduler_category:warm_e2b": {
            "key": "scheduler_category:warm_e2b",
            "event_ids": ["evt-scheduler"],
            "signals": {"service": 1},
            "sources": {"scheduler": 1},
            "context": {"scheduler_category": "warm_e2b", "context_index_key": "scheduler_category:warm_e2b"},
        },
        "host_service_unit:abyss-dictation-server.service": {
            "key": "host_service_unit:abyss-dictation-server.service",
            "event_ids": ["evt-host-service"],
            "signals": {"service": 1},
            "sources": {"host-service": 1},
            "context": {"host_service_unit": "abyss-dictation-server.service", "context_index_key": "host_service_unit:abyss-dictation-server.service"},
        }
    }

    packet = abyss_machine_module.self_awareness_bounded_context_packet(
        contexts,
        memory_space,
        action_map,
        capabilities,
        "2026-01-01T00:00:00+00:00",
        trace_context,
    )

    assert packet["schema"] == "abyss_machine_self_awareness_bounded_context_packet_v1"
    assert packet["complete"] is True
    assert packet["sections"]["stack_handoff"]["ordered_actions"][0]["requirement_id"] == "stack.trace-backend"
    assert packet["sections"]["stack_handoff"]["ordered_actions"][0]["coverage_impact"]["organ"] == "trace_join_backbone"
    assert "langgraph_replay" in packet["sections"]["stack_handoff"]["ordered_actions"][0]["coverage_planes"]
    assert packet["sections"]["host_body"]["schema"] == "abyss_machine_self_awareness_host_body_context_packet_v1"
    assert packet["sections"]["host_body"]["scheduler"]["category_contexts"] == 1
    assert packet["sections"]["host_body"]["scheduler"]["categories"] == ["warm_e2b"]
    assert packet["sections"]["host_body"]["host_services"]["unit_contexts"] == 1
    assert packet["sections"]["host_body"]["host_services"]["sample_units"] == ["abyss-dictation-server.service"]
    assert packet["sections"]["host_body"]["policy"]["host_layer_mutates_stack"] is False
    trace_join = packet["sections"]["trace_join"]
    assert trace_join["schema"] == "abyss_machine_self_awareness_trace_join_context_packet_v1"
    assert trace_join["complete"] is True
    assert trace_join["stack_requirement_id"] == "stack.trace-backend"
    assert trace_join["closes_stack_requirement"] is False
    assert trace_join["stack_requirement_not_closed_by_fallback"] is True
    assert trace_join["trace_backend"]["missing_check_keys"] == [
        "trace_backend_ready",
        "trace_span_search_readable",
        "span_log_metric_join_supported",
    ]
    assert trace_join["fallback"]["metrics_log_pipeline_readable"] is True
    assert trace_join["fallback"]["raw_log_exports_stored"] is False
    assert trace_join["policy"]["adds_loki_labels"] is False
    assert trace_join["policy"]["host_layer_mutates_stack"] is False
    blocked_gate = packet["sections"]["memory_space"]["blocked_gates"][0]
    assert blocked_gate["gate_id"] == "nervous_freshness"
    assert blocked_gate["maintenance_route"] == abyss_machine_module.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND
    assert blocked_gate["semantic_maintain"]["decision"] == "blocked_index_refresh"
    assert blocked_gate["blocked_reasons"] == ["indexing_unattended_swap_used_pressure"]
    assert blocked_gate["resource_denial_is_safe_gate"] is True
    assert blocked_gate["policy"]["does_not_bypass_resource_gate"] is True
    assert blocked_gate["evidence_refs"][0]["truth_level"] == "nervous_semantic_maintain"
    assert packet["summary"]["host_body_complete"] is True
    assert packet["summary"]["trace_join_complete"] is True
    assert packet["summary"]["trace_backend_ready"] is False
    assert packet["summary"]["trace_join_closes_stack_requirement"] is False
    assert packet["summary"]["coverage_impact_entries"] == 1
    assert "signal_fabric" in packet["summary"]["blocked_coverage_planes"]
    assert packet["sections"]["resident_worker"]["complete"] is True
    assert packet["sections"]["governance_gates"]["complete"] is True
    assert packet["bounds"]["raw_private_content"] is False
    assert packet["bounds"]["stores_raw_context_values"] is False
    assert packet["policy"]["host_layer_mutates_stack"] is False
    assert packet["policy"]["action_execution"] is False
    assert {"promql_read", "logql_read", "trace_context", "requirements_handoff", "resident_worker", "governance_gates"}.issubset(
        {tool["kind"] for tool in packet["read_only_tools"]}
    )


def test_self_awareness_investigation_loop_order_replays_full_contract(monkeypatch, abyss_machine_module) -> None:
    expected = [
        "plan_queries",
        "query_evidence",
        "resident_context_packet",
        "reason_over_evidence",
        "request_more_evidence",
        "validate_evidence",
        "record_artifact",
        "brief_reaction_candidate",
        "write_semantic_conclusion",
    ]
    assert abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER == expected

    artifact_refs = [{"path": "/var/lib/abyss-machine/self-awareness/investigate/latest.json"}]
    body_trace = _body_trace_fixture("episode-fixture")
    checkpoints = []
    states = []
    parent = None
    for node in expected:
        state = {"node": node, "artifact_refs": artifact_refs, "policy": {"host_layer_mutates_stack": False}}
        if node in {"resident_context_packet", "reason_over_evidence"}:
            state["body_trace"] = body_trace
        checkpoint = abyss_machine_module.self_awareness_checkpoint("thread-1", node, state, parent)
        checkpoints.append(checkpoint)
        states.append({"node": node, "state": state})
        parent = checkpoint["checkpoint_id"]

    investigation = {
        "schema": "abyss_machine_self_awareness_investigation_v1",
        "thread_id": "thread-1",
        "checkpoints": checkpoints,
        "states": states,
        "body_trace": body_trace,
        "conclusion": {"evidence_refs": artifact_refs, "body_trace": body_trace},
    }
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", lambda path, schema: investigation)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_resident_cognitive_replay_summary",
        lambda investigation, state_by_node=None: _resident_cognitive_replay_fixture(),
    )

    replay = abyss_machine_module.self_awareness_replay(thread_id="thread-1", write_latest=False)

    assert replay["ok"] is True
    assert replay["summary"]["node_order"] == expected
    assert replay["summary"]["divergences"] == 0
    assert replay["expected_node_order"] == expected
    assert replay["conclusion_diff"]["changed"] is False
    assert replay["body_trace_replay"]["replayable"] is True
    assert replay["resume"]["supported"] is True
    assert replay["failure_recovery"]["supported"] is True
    assert replay["policy"]["host_layer_mutates_stack"] is False
    assert replay["policy"]["action_execution"] is False
    assert replay["policy"]["human_approval_before_mutation"] is True


def test_self_awareness_replay_preserves_stack_handoff_closure_readiness(monkeypatch, abyss_machine_module) -> None:
    expected = list(abyss_machine_module.SELF_AWARENESS_INVESTIGATION_NODE_ORDER)
    artifact_refs = [{"path": "/var/lib/abyss-machine/self-awareness/investigate/latest.json"}]
    body_trace = _body_trace_fixture("episode-fixture")
    safe_next_action = {
        "kind": "stack_owner_closure_readiness_review",
        "command": "abyss-machine self-awareness export --json",
        "automatic": False,
        "requires_human_approval": True,
        "executes_commands": False,
        "host_layer_mutates_stack": False,
        "action_execution": False,
    }
    readiness = {
        "schema": "abyss_machine_stack_handoff_closure_readiness_v1",
        "requirement_id": "stack.trace-backend",
        "fulfilled_check_count": 1,
        "fulfilled_checks": [{"key": "traceparent_log_queryable"}],
        "missing_checks": [{"key": "trace_backend_ready"}],
        "open_blocker_count": 1,
        "blocking_check_keys": ["trace_backend_ready"],
        "dependency_requirement_ids": [],
        "dependency_reasons": [],
        "safe_next_action": safe_next_action,
        "verifier_commands": ["abyss-machine self-awareness requirement-probes --json"],
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/requirement-probes/latest.json"}],
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
        },
    }
    coverage_impact = abyss_machine_module.self_awareness_stack_requirement_coverage_impact("stack.trace-backend")
    action = {
        "id": "stack-handoff:stack.trace-backend",
        "requirement_id": "stack.trace-backend",
        "priority_rank": 1,
        "priority_class": "critical_trace_join",
        "impact_organ": coverage_impact["organ"],
        "coverage_planes": coverage_impact["coverage_planes"],
        "coverage_impact": coverage_impact,
        "closure_blockers": readiness["missing_checks"],
        "closure_blocker_keys": readiness["blocking_check_keys"],
        "runbook_candidate_id": "stack-runbook-stack-trace-backend",
        "runbook_candidate": {"machine_executes_stack_change": False},
        "acceptance_verifiers": [{"command": "abyss-machine self-awareness requirement-probes --json"}],
        "verifier_commands": readiness["verifier_commands"],
        "closure_readiness": readiness,
        "safe_next_action": safe_next_action,
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
        },
        "evidence_refs": readiness["evidence_refs"],
    }
    action_map = {
        "schema": "abyss_machine_self_awareness_brief_stack_handoff_action_map_v1",
        "summary": {
            "open_stack_requirements": 1,
            "actions": 1,
            "acceptance_verifier_steps": 1,
            "closure_readiness_packets": 1,
            "closure_readiness_missing_checks": 1,
            "coverage_impact_entries": 1,
            "blocked_coverage_planes": coverage_impact["coverage_planes"],
            "top_requirement_id": "stack.trace-backend",
        },
        "open_requirement_ids": ["stack.trace-backend"],
        "actions": [action],
        "safe_next_action": safe_next_action,
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "raw_secrets_included": False,
        },
        "evidence_refs": readiness["evidence_refs"],
    }
    closure_packet = abyss_machine_module.self_awareness_stack_handoff_closure_readiness_replay_packet(action_map)
    checkpoints = []
    states = []
    parent = None
    for node in expected:
        state = {"node": node, "artifact_refs": artifact_refs, "policy": {"host_layer_mutates_stack": False}}
        if node in {"resident_context_packet", "reason_over_evidence"}:
            state["body_trace"] = body_trace
        if node == "request_more_evidence":
            state.update({
                "stack_handoff_action_map": action_map,
                "stack_handoff_closure_readiness": closure_packet,
                "requests": [{**action, "kind": "stack_handoff_action"}],
            })
        if node == "brief_reaction_candidate":
            state.update({
                "stack_handoff_action_map": action_map,
                "stack_handoff_closure_readiness": closure_packet,
            })
        checkpoint = abyss_machine_module.self_awareness_checkpoint("thread-readiness", node, state, parent)
        checkpoints.append(checkpoint)
        states.append({"node": node, "state": state})
        parent = checkpoint["checkpoint_id"]
    investigation = {
        "schema": "abyss_machine_self_awareness_investigation_v1",
        "thread_id": "thread-readiness",
        "stack_handoff_action_map": action_map,
        "stack_handoff_closure_readiness": closure_packet,
        "body_trace": body_trace,
        "checkpoints": checkpoints,
        "states": states,
        "conclusion": {
            "evidence_refs": artifact_refs,
            "body_trace": body_trace,
            "stack_handoff_action_map": {
                "schema": action_map["schema"],
                "summary": action_map["summary"],
                "open_requirement_ids": action_map["open_requirement_ids"],
                "coverage_impact_by_requirement": {"stack.trace-backend": coverage_impact},
                "policy": action_map["policy"],
            },
            "stack_handoff_closure_readiness": closure_packet,
        },
    }
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", lambda path, schema: investigation)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_resident_cognitive_replay_summary",
        lambda investigation, state_by_node=None: _resident_cognitive_replay_fixture(),
    )

    replay = abyss_machine_module.self_awareness_replay(thread_id="thread-readiness", write_latest=False)

    assert replay["ok"] is True
    assert replay["summary"]["stack_handoff_closure_readiness_packets"] == 1
    assert replay["summary"]["stack_handoff_closure_readiness_replayable"] is True
    assert replay["summary"]["stack_handoff_coverage_impact_entries"] == 1
    assert replay["summary"]["body_trace_replayable"] is True
    assert "signal_fabric" in replay["summary"]["stack_handoff_blocked_coverage_planes"]
    assert replay["stack_handoff_closure_readiness"]["summary"]["packets"] == 1
    assert replay["stack_handoff_closure_readiness"]["summary"]["coverage_impact_entries"] == 1
    assert replay["stack_handoff_closure_readiness"]["ordered_next_actions"][0]["requirement_id"] == "stack.trace-backend"
    assert replay["stack_handoff_closure_readiness"]["ordered_next_actions"][0]["coverage_impact"]["organ"] == "trace_join_backbone"
    assert replay["stack_handoff_replay"]["closure_readiness_replayable"] is True
    assert replay["body_trace_replay"]["replayable"] is True
    assert replay["stack_handoff_replay"]["coverage_impact_summary"]["coverage_impact_by_requirement"]["stack.trace-backend"]["organ"] == "trace_join_backbone"
    assert all(replay["stack_handoff_replay"]["state_preservation"].values())
    assert replay["stack_handoff_replay"]["policy"]["host_layer_mutates_stack"] is False


def test_self_awareness_response_contract_preserves_episode_lineage(abyss_machine_module) -> None:
    episode = {
        "schema": "abyss_machine_causal_episode_v1",
        "episode_id": "saepisode-fixture",
        "time_window": {"start": "2026-06-05T00:00:00Z", "end": "2026-06-05T00:01:00Z"},
        "event_ids": ["event-1"],
        "primary_signals": ["alert", "trace_context"],
        "affected_spatial_nodes": ["service:grafana"],
        "context_keys": ["service:grafana", "source:synthetic"],
        "confidence": {"score": 0.78, "reasons": ["fixture"]},
        "truth_level": "inferred",
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/episodes/latest.json"}],
    }
    source_event = {
        "event_id": "event-1",
        "signal": "alert",
        "source": "synthetic",
        "severity": "notice",
        "resource": {"service": "grafana", "write": False},
        "context": {"synthetic_run_id": "saprobe-fixture"},
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/probe/latest.json"}],
    }
    investigation = {
        "thread_id": "sainv-fixture",
        "selected_episode_id": "saepisode-fixture",
        "summary": {"checkpoints": 9},
    }
    replay = {
        "thread_id": "sainv-fixture",
        "ok": True,
        "summary": {"divergences": 0, "conclusion_diff_changed": False},
    }

    contract = abyss_machine_module.self_awareness_episode_response_contract(
        candidate_id="self-awareness-fixture",
        episode=episode,
        source_event=source_event,
        investigation=investigation,
        replay=replay,
        context_doc=_context_doc_fixture(),
        completion_audit_doc=_completion_audit_doc_fixture(),
    )

    assert abyss_machine_module.self_awareness_response_contract_complete(contract) is True
    assert contract["schema"] == "abyss_machine_self_awareness_response_contract_v1"
    assert contract["validated_episode"]["episode_id"] == "saepisode-fixture"
    assert contract["investigation"]["matches_episode"] is True
    assert contract["replay"]["matches_investigation"] is True
    assert contract["response_lineage"]["schema"] == "abyss_machine_self_awareness_response_lineage_v1"
    assert contract["response_lineage"]["complete"] is True
    assert contract["response_lineage"]["latest_investigation_matches_episode"] is True
    assert contract["response_lineage"]["latest_replay_matches_investigation"] is True
    assert contract["body_trace"]["complete"] is True
    assert contract["body_trace"]["host_body"]["complete"] is True
    assert contract["entity_event_document_context"]["complete"] is True
    assert contract["entity_event_document_context"]["entity_ids"]
    assert "self-awareness.completion-audit.latest" in contract["entity_event_document_context"]["document_ids"]
    assert contract["risk"]["risks"]
    assert contract["blast_radius"]["stack_mutation"] is False
    assert contract["rollback"]["stack_rollback_required"] is False
    assert contract["runbook_candidate"]["schema"] == "abyss_machine_self_awareness_response_runbook_candidate_v1"
    assert contract["approval"]["required"] is True
    assert contract["policy"]["executes_commands"] is False

    candidate = abyss_machine_module.reaction_candidate(
        "self-awareness-fixture",
        title="Fixture self-awareness candidate",
        severity="notice",
        category="self-awareness",
        reason="fixture",
        command="abyss-machine self-awareness brief --json",
        owner_route="abyss-machine:self-awareness",
        evidence=contract["evidence_refs"],
    )
    candidate.update({
        "episode_id": contract["validated_episode"]["episode_id"],
        "validated_episode": contract["validated_episode"],
        "response_contract": contract,
        "body_trace": contract["body_trace"],
        "entity_event_document_context": contract["entity_event_document_context"],
        "risk": contract["risk"],
        "blast_radius": contract["blast_radius"],
        "rollback": contract["rollback"],
        "runbook_candidate": contract["runbook_candidate"],
    })
    assert abyss_machine_module.self_awareness_reaction_candidate_response_depth_complete(candidate) is True

    route = abyss_machine_module.response_route_from_candidate(candidate)
    assert abyss_machine_module.self_awareness_response_route_depth_complete(route) is True
    assert route["route_id"] == "self-awareness-fixture-response-route"
    assert route["validated_episode"]["episode_id"] == "saepisode-fixture"
    assert route["body_trace"] == contract["body_trace"]
    assert route["entity_event_document_context"] == contract["entity_event_document_context"]
    assert route["suggestion"]["command_profile"]["kind"] == "self_awareness_brief"
    assert route["policy"]["host_layer_mutates_stack"] is False


def test_working_stack_activation_gap_route_is_classified_and_preserved(monkeypatch, abyss_machine_module) -> None:
    episode_id = "saepisode-working-stack-gap-fixture"
    thread_id = "sainv-working-gap-fixture"
    service = "aoa-browser"
    status = "tool_runtime_degraded"
    usage_gap = "stack tool is reachable and guarded, but its functional runtime smoke failed"
    safe_next = abyss_machine_module.self_awareness_working_stack_gap_safe_next_action(service, status, usage_gap)
    working_stack_gap = {
        "schema": "abyss_machine_self_awareness_working_stack_usage_gap_v1",
        "service": service,
        "owner_route": "abyss-stack",
        "working_stack_link_id": "saworklink-fixture",
        "machine_usage_status": status,
        "activation_kind": "stack_tool_runtime_smoke_gap",
        "usage_gap": usage_gap,
        "runtime_present": True,
        "runtime_running": True,
        "container": "aoa-browser",
        "health": "healthy",
        "runtime_state": "running",
        "runtime_status": "Up 1 minute (healthy)",
        "runtime_stack_managed": True,
        "declared": True,
        "declared_modules": ["51-browser-tools.yml"],
        "endpoint_ok": True,
        "service_roots": 1,
        "model_roots": 0,
        "deep_usage_proven": False,
        "failed_probe_names": ["playwright-chromium-launch"],
        "ok_probe_names": ["health", "private-host-guard"],
        "endpoint_probe_count": 3,
        "closure_blocker_keys": [status, "usage_gap:fixture"],
        "safe_next_action": safe_next,
        "verifier_commands": safe_next["verifier_commands"],
        "policy": {
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }
    episode = {
        "schema": "abyss_machine_causal_episode_v1",
        "episode_id": episode_id,
        "episode_kind": "working_stack_usage_gap",
        "service": service,
        "owner_route": "abyss-stack",
        "working_stack_link_id": "saworklink-fixture",
        "time_window": {"start": "2026-06-05T00:00:00Z", "end": "2026-06-05T00:01:00Z"},
        "event_ids": [],
        "primary_signals": ["working_stack", "spatial_graph", "usage_gap", "runtime_smoke"],
        "affected_spatial_nodes": ["service:aoa-browser", "container:aoa-browser", "usage_gap:fixture"],
        "context_keys": ["service:aoa-browser", "owner_surface:abyss-stack", "machine_usage_status:tool_runtime_degraded"],
        "confidence": {"score": 0.9, "reasons": ["fixture"]},
        "truth_level": "working_stack_gap_candidate",
        "working_stack_gap": working_stack_gap,
        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
    }
    activation_smoke = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1",
        "rows": [
            {
                "service": service,
                "machine_usage_status": status,
                "episode_id": episode_id,
                "complete": True,
                "investigation": {
                    "ok": True,
                    "thread_id": thread_id,
                    "selected_episode_id": episode_id,
                    "selected_episode_matches": True,
                    "working_stack_gap_complete": True,
                },
                "replay": {
                    "ok": True,
                    "thread_id": thread_id,
                    "thread_matches": True,
                    "working_stack_gap_selected": True,
                    "working_stack_gap_replayable": True,
                    "working_stack_gap_matches": True,
                },
            }
        ],
    }

    def fake_load_latest_json(path, schema):
        if schema == "abyss_machine_self_awareness_working_stack_activation_smoke_v1":
            return activation_smoke
        return {}

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)

    contract = abyss_machine_module.self_awareness_episode_response_contract(
        candidate_id="self-awareness-working-gap-fixture",
        episode=episode,
        source_event={},
        investigation={},
        replay={},
        context_doc=_context_doc_fixture(),
        completion_audit_doc=_completion_audit_doc_fixture(),
    )

    activation_route = contract["activation_gap_route"]
    assert abyss_machine_module.self_awareness_response_contract_complete(contract) is True
    assert abyss_machine_module.self_awareness_working_stack_activation_gap_route_complete(activation_route) is True
    assert activation_route["classification"] == "running_functional_smoke_failed"
    assert activation_route["current_state"]["runtime"]["running"] is True
    assert activation_route["current_state"]["endpoint"]["failed_probe_names"] == ["playwright-chromium-launch"]
    assert activation_route["activation_smoke"]["row_complete"] is True
    assert activation_route["activation_smoke"]["working_stack_gap_replayable"] is True
    assert activation_route["safe_next_action"]["host_layer_mutates_stack"] is False
    assert activation_route["policy"]["executes_commands"] is False
    assert contract["entity_event_document_context"]["complete"] is True

    candidate = abyss_machine_module.reaction_candidate(
        "self-awareness-working-gap-fixture",
        title="Fixture working-stack gap candidate",
        severity="warning",
        category="self-awareness",
        reason="fixture",
        command="abyss-machine self-awareness working-stack --json",
        owner_route="abyss-machine:self-awareness",
        action_mode="owner_handoff_review",
        evidence=contract["evidence_refs"],
    )
    candidate.update({
        "episode_id": contract["validated_episode"]["episode_id"],
        "working_stack_gap_service": service,
        "working_stack_gap_status": status,
        "activation_gap_route": activation_route,
        "validated_episode": contract["validated_episode"],
        "response_contract": contract,
        "body_trace": contract["body_trace"],
        "entity_event_document_context": contract["entity_event_document_context"],
        "risk": contract["risk"],
        "blast_radius": contract["blast_radius"],
        "rollback": contract["rollback"],
        "runbook_candidate": contract["runbook_candidate"],
    })
    assert abyss_machine_module.self_awareness_reaction_candidate_response_depth_complete(candidate) is True

    route = abyss_machine_module.response_route_from_candidate(candidate)
    assert abyss_machine_module.self_awareness_response_route_depth_complete(route) is True
    assert route["activation_gap_route"] == activation_route
    assert route["entity_event_document_context"] == contract["entity_event_document_context"]
    assert route["activation_gap_route"]["classification"] == "running_functional_smoke_failed"
    assert route["executes"] is False

    exited_route = abyss_machine_module.self_awareness_working_stack_activation_gap_route(
        {
            **working_stack_gap,
            "service": "qwen-tts",
            "machine_usage_status": "declared_not_running",
            "activation_kind": "stack_declared_service_activation_gap",
            "runtime_running": False,
            "container": "qwen-tts",
            "runtime_state": "exited",
            "runtime_status": "Exited (0) 39 minutes ago (healthy)",
            "failed_probe_names": [],
            "ok_probe_names": [],
            "endpoint_ok": False,
            "usage_gap": "declared stack service is not running in the current runtime body",
            "working_stack_link_id": "saworklink-qwen-fixture",
            "safe_next_action": abyss_machine_module.self_awareness_working_stack_gap_safe_next_action(
                "qwen-tts",
                "declared_not_running",
                "declared stack service is not running in the current runtime body",
            ),
        },
        episode_id="saepisode-qwen-fixture",
    )
    assert abyss_machine_module.self_awareness_working_stack_activation_gap_route_complete(exited_route) is True
    assert exited_route["classification"] == "exited_stack_managed_container"


def test_memory_hotpath_probe_route_is_measurement_only_and_preserved(abyss_machine_module) -> None:
    hotpath = {
        "available": True,
        "fresh": True,
        "path": "/var/lib/abyss-machine/memory/hotpath/latest.json",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "age_sec": 12.0,
        "max_age_sec": 3600.0,
        "ok": False,
        "status": "failed",
        "measurement_status": "latest_failed",
        "issues": ["active_memory_stalls_after_probe", "first_tts_slow"],
        "findings": ["tts_second_run_faster_after_swapin"],
        "summary": {
            "first_tts_wall_sec": 21.04,
            "last_tts_wall_sec": 1.381,
            "command_stt_client_sec": None,
            "quality_stt_client_sec": None,
            "swap_used_percent_before": 65.52,
            "swap_used_percent_after": 65.775,
        },
    }
    route = abyss_machine_module.memory_hotpath_probe_route(hotpath)

    assert route["schema"] == "abyss_machine_memory_hotpath_probe_route_v1"
    assert route["complete"] is True
    assert abyss_machine_module.memory_hotpath_probe_route_complete(route) is True
    assert route["measurement_status"] == "latest_failed"
    assert route["latency"]["first_tts_wall_sec"] == 21.04
    assert route["latency"]["last_tts_wall_sec"] == 1.381
    assert route["swap"]["used_percent_before"] == 65.52
    assert route["safe_next_action"]["executes_commands"] is False
    assert route["safe_next_action"]["host_layer_mutates_stack"] is False
    assert route["safe_next_action"]["does_not_apply_cgroup_properties"] is True
    assert route["policy"]["does_not_stop_disable_restart_or_throttle_services"] is True

    candidate = abyss_machine_module.reaction_candidate(
        "memory-hotpath-probe-failed",
        title="Memory hot-path latency probe failed",
        severity="warning",
        category="memory",
        reason="Latest hot-path latency probe is fresh but failed.",
        command="abyss-machine memory hotpath-probe --json",
        evidence=[{"path": "/var/lib/abyss-machine/memory/hotpath/latest.json"}],
    )
    candidate["memory_hotpath_route"] = route
    candidate["safe_next_action"] = route["safe_next_action"]

    response_route = abyss_machine_module.response_route_from_candidate(candidate)
    assert response_route["memory_hotpath_route"] == route
    assert response_route["safe_next_action"] == route["safe_next_action"]
    assert response_route["suggestion"]["command_profile"]["mutating_if_run"] is False
    assert response_route["executes"] is False


def test_doctor_warning_route_is_review_only_and_preserved(abyss_machine_module) -> None:
    doctor_doc = {
        "schema": "abyss_machine_doctor_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"status": "warn", "fails": 0, "warnings": 2, "checks": 64},
        "checks": [
            {"key": "machine_topology_validate", "level": "warn", "message": "topology validate warn", "data": {"summary": {"warnings": 1}}},
            {"key": "nervous_brief", "level": "warn", "message": "nervous brief readiness degraded", "data": {"readiness": {"status": "degraded"}}},
            {"key": "memory_validate", "level": "ok", "message": "memory ok"},
        ],
    }
    machine_report = {
        "schema": "abyss_machine_doctor_machine_report_v1",
        "ok": False,
        "status": "blocked",
        "generated_at": "2026-01-01T00:00:01+00:00",
        "summary": {
            "doctor_status": "warn",
            "doctor_warnings": 2,
            "nervous_readiness": "degraded",
            "semantic_stale": True,
            "semantic_maintenance_needed": True,
            "memory_residency_status": "runtime_pilot_active_needs_warmup",
            "ai_policy_class": "battery_saver",
            "ai_heavy_policy": "defer",
            "ai_can_run_heavy": False,
        },
    }
    route = abyss_machine_module.doctor_warning_route(
        doctor_doc=doctor_doc,
        machine_report=machine_report,
        doctor_unit={"active": "active", "state": "running"},
        doctor_unit_show={"ActiveState": "active", "SubState": "running", "Result": "success"},
    )

    assert route["schema"] == "abyss_machine_doctor_warning_route_v1"
    assert route["complete"] is True
    assert abyss_machine_module.doctor_warning_route_complete(route) is True
    assert route["doctor"]["warnings"] == 2
    assert route["warning_keys"] == ["machine_topology_validate", "nervous_brief"]
    assert route["machine_report"]["nervous_readiness"] == "degraded"
    assert route["safe_next_action"]["executes_commands"] is False
    assert route["safe_next_action"]["host_layer_mutates_stack"] is False
    assert route["safe_next_action"]["clears_change_ledger"] is False
    assert route["policy"]["review_only"] is True

    candidate = abyss_machine_module.reaction_candidate(
        "doctor-warnings-present",
        title="Doctor has warning-level checks",
        severity="warning",
        category="doctor",
        reason="Doctor status is usable but still carries warning checks.",
        command="abyss-machine doctor --json",
        evidence=[{"path": "/var/lib/abyss-machine/doctor/latest.json"}],
    )
    candidate["doctor_warning_route"] = route
    candidate["safe_next_action"] = route["safe_next_action"]

    response_route = abyss_machine_module.response_route_from_candidate(candidate)
    assert response_route["doctor_warning_route"] == route
    assert response_route["safe_next_action"] == route["safe_next_action"]
    assert response_route["suggestion"]["command_profile"]["mutating_if_run"] is False
    assert response_route["executes"] is False


def test_desktop_compositor_pressure_route_is_observe_only_and_preserved(abyss_machine_module) -> None:
    desktop_doc = {
        "schema": "abyss_machine_process_desktop_compositor_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {
            "classification": "panel_telemetry_compositor_churn",
            "findings": [
                "high_refresh_display_active",
                "panel_telemetry_metric_label_churn",
                "gnome_shell_high_refresh_compositor_cpu_pressure",
            ],
            "cpu_avg_one_core_percent": 25.8,
            "cpu_max_one_core_percent": 30.3,
            "refresh_hz": 120.0,
            "high_refresh_active": True,
            "windows_changed_rate_hz": 20.156,
            "running_applications_changed_rate_hz": 0.0,
            "panel_metric_label_rate_hz": 45.824,
            "status_notifier_count": 1,
            "enabled_extension_count": 7,
            "atspi_window_count": 24,
            "atspi_window_apps": {"Chromium": 14, "gnome-shell": 2},
            "x11_window_count": 0,
            "wayland_client_count": 12,
            "screencast_or_remote_session_like_paths": 0,
            "top_desktop_cpu_candidate": {
                "pid": 335109,
                "ppid": 1,
                "comm": "firefox",
                "cpu_percent_ps": 31.5,
                "mem_percent_ps": 2.1,
                "rss_kib": 561820,
                "etime": "14:53",
                "cmdline": "firefox --private-content-should-not-be-preserved",
            },
            "route_guidance": "treat as panel telemetry churn evidence and preserve display quality",
            "non_claim": "controlled A/B is required before attributing CPU cost to an extension",
        },
        "policy": {
            "automation": "observe_only",
            "do_not_kill_or_throttle_from_this_result": True,
            "do_not_toggle_gnome_extensions_from_this_result": True,
            "safe_next_step": "Use repeated samples; do not lower display refresh/quality.",
        },
    }
    resource_orch = {
        "schema": "abyss_machine_resource_orchestrator_v2_v1",
        "generated_at": "2026-01-01T00:00:01+00:00",
        "summary": {"status": "watch"},
    }
    route = abyss_machine_module.desktop_compositor_pressure_route(desktop_doc, resource_orch)

    assert route["schema"] == "abyss_machine_desktop_compositor_pressure_route_v1"
    assert route["complete"] is True
    assert abyss_machine_module.desktop_compositor_pressure_route_complete(route) is True
    assert route["classification"] == "panel_telemetry_compositor_churn"
    assert route["pressure"]["cpu_avg_one_core_percent"] == 25.8
    assert route["display"]["refresh_hz"] == 120.0
    assert route["display"]["high_refresh_active"] is True
    assert route["churn"]["panel_metric_label_rate_hz"] == 45.824
    assert route["desktop_context"]["wayland_client_count"] == 12
    assert route["pressure"]["top_desktop_cpu_candidate"]["comm"] == "firefox"
    assert "cmdline" not in route["pressure"]["top_desktop_cpu_candidate"]
    assert route["safe_next_action"]["executes_commands"] is False
    assert route["safe_next_action"]["host_layer_mutates_stack"] is False
    assert route["safe_next_action"]["does_not_kill_or_throttle"] is True
    assert route["safe_next_action"]["does_not_toggle_gnome_extensions"] is True
    assert route["safe_next_action"]["does_not_lower_refresh_or_quality"] is True
    assert route["policy"]["observe_only"] is True
    assert route["policy"]["mutates_desktop_state"] is False
    assert route["policy"]["redacts_process_cmdline"] is True

    candidate = abyss_machine_module.reaction_candidate(
        "desktop-compositor-pressure-review",
        title="Desktop compositor pressure should stay visible",
        severity="notice",
        category="desktop",
        reason="GNOME Shell compositor pressure should stay visible.",
        command="abyss-machine processes desktop-compositor --seconds 3 --interval 0.5 --json",
        owner_route="abyss-machine:desktop",
        action_mode="observe_only_review",
        evidence=[{"path": "/var/lib/abyss-machine/processes/desktop-compositor/latest.json"}],
    )
    candidate["desktop_compositor_route"] = route
    candidate["safe_next_action"] = route["safe_next_action"]

    response_route = abyss_machine_module.response_route_from_candidate(candidate)
    assert response_route["desktop_compositor_route"] == route
    assert response_route["safe_next_action"] == route["safe_next_action"]
    assert response_route["suggestion"]["command_profile"]["kind"] == "read_only_probe"
    assert response_route["suggestion"]["command_profile"]["mutating_if_run"] is False
    assert response_route["executes"] is False


def test_nervous_retention_privacy_route_is_dry_run_first_and_preserved(abyss_machine_module) -> None:
    retention_plan = {
        "schema": "abyss_machine_nervous_retention_plan_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {
            "files": 3463,
            "bytes": 4937303800,
            "candidates": 1391,
            "candidate_bytes": 1685217180,
            "route_errors": 0,
            "by_layer": {
                "private_capture_artifacts": {
                    "files": 3182,
                    "bytes": 3045194367,
                    "candidates": 1373,
                    "candidate_bytes": 1628354407,
                },
                "browser_content": {
                    "files": 27,
                    "bytes": 65313321,
                    "candidates": 16,
                    "candidate_bytes": 56635910,
                },
                "retrieval": {
                    "files": 39,
                    "bytes": 19509891,
                    "candidates": 2,
                    "candidate_bytes": 226863,
                },
                "facts": {
                    "files": 34,
                    "bytes": 1725439599,
                    "candidates": 0,
                    "candidate_bytes": 0,
                },
            },
        },
        "policy": {
            "facts_delete_behavior": "explicit forget only",
            "default_apply": "dry-run",
            "no_project_repo_mutation": True,
            "no_symlink_tails_required": True,
        },
        "route_errors": [],
    }
    route = abyss_machine_module.nervous_retention_privacy_route(retention_plan)

    assert route["schema"] == "abyss_machine_nervous_retention_privacy_route_v1"
    assert route["complete"] is True
    assert abyss_machine_module.nervous_retention_privacy_route_complete(route) is True
    assert route["summary"]["candidates"] == 1391
    assert route["summary"]["candidate_bytes"] == 1685217180
    assert route["candidate_layers"][0]["layer"] == "private_capture_artifacts"
    assert route["candidate_layers"][1]["layer"] == "browser_content"
    assert route["by_layer"]["facts"]["candidates"] == 0
    assert route["safe_next_action"]["dry_run_command"] == "abyss-machine nervous retention-apply --dry-run --json"
    assert route["safe_next_action"]["requires_explicit_confirm_for_deletion"] is True
    assert route["safe_next_action"]["executes_commands"] is False
    assert route["safe_next_action"]["host_layer_mutates_stack"] is False
    assert route["safe_next_action"]["does_not_delete_facts"] is True
    assert route["safe_next_action"]["does_not_delete_project_roots"] is True
    assert route["policy"]["dry_run_first"] is True
    assert route["policy"]["default_apply_dry_run"] is True
    assert route["policy"]["facts_delete_behavior_explicit_forget_only"] is True
    assert route["policy"]["no_project_repo_mutation"] is True
    assert route["policy"]["raw_private_content"] is False

    candidate = abyss_machine_module.reaction_candidate(
        "nervous-retention-review",
        title="Nervous retention has cleanup review work",
        severity="notice",
        category="privacy",
        reason="Nervous retention candidates exist; any cleanup must stay owner-gated.",
        command="abyss-machine nervous retention-apply --dry-run --json",
        owner_route="abyss-machine:nervous-privacy",
        action_mode="owner_gated_retention_review",
        evidence=[{"path": "/var/lib/abyss-machine/nervous/retention/latest.json"}],
    )
    candidate["nervous_retention_route"] = route
    candidate["safe_next_action"] = route["safe_next_action"]

    response_route = abyss_machine_module.response_route_from_candidate(candidate)
    assert response_route["nervous_retention_route"] == route
    assert response_route["safe_next_action"] == route["safe_next_action"]
    assert response_route["suggestion"]["command_profile"]["kind"] == "owner_gated_retention_dry_run"
    assert response_route["suggestion"]["command_profile"]["mutating_if_run"] is False
    assert response_route["executes"] is False


def test_host_owner_gap_reactions_route_to_non_executing_responses(abyss_machine_module) -> None:
    stack_bridge_validate = {
        "schema": "abyss_machine_stack_bridge_validate_v1",
        "ok": True,
        "summary": {"status": "warn", "warnings": 1, "fails": 0},
        "checks": [
            {
                "key": "static_bridge_sync",
                "level": "warn",
                "message": "static /etc bridge manifests lag dynamic bridge routes",
                "data": {
                    "bridge_missing_commands": ["self_awareness_autolink_json"],
                    "stack_missing_commands": ["self_awareness_activation_smoke_json"],
                },
            }
        ],
    }
    manual_collect = {
        "schema": "abyss_machine_observability_manual_collect_probe_v1",
        "status": "operator_authorization_required",
        "missing_or_unwritable": ["samples", "events", "summary"],
        "directories": [
            {
                "name": "samples",
                "path": "/var/lib/abyss-machine/observability/thermal-battery/samples/2026/06",
                "effective_write": False,
            }
        ],
    }

    candidates = abyss_machine_module.reaction_host_owner_gap_candidates(
        stack_bridge_validate_doc=stack_bridge_validate,
        manual_collect_doc=manual_collect,
    )
    by_id = {candidate["id"]: candidate for candidate in candidates}

    assert set(by_id) == {
        "host-static-bridge-sync-root-review",
        "host-observability-manual-collect-permission-review",
    }
    for candidate in candidates:
        assert candidate["automatic"] is False
        assert candidate["owner_route"] == "abyss-machine:root-operator"
        assert candidate["host_owner_gap"]["policy"]["host_layer_mutates_stack"] is False
        assert candidate["host_owner_gap"]["policy"]["executes_commands"] is False
        assert candidate["safe_next_action"]["requires_human_approval"] is True
        assert candidate["safe_next_action"]["executes_commands"] is False
        assert candidate["runbook_candidate"]["policy"]["executes_commands"] is False

        route = abyss_machine_module.response_route_from_candidate(candidate)
        assert route["automatic"] is False
        assert route["executes"] is False
        assert route["approval"]["required"] is True
        assert route["host_owner_gap"] == candidate["host_owner_gap"]
        assert route["safe_next_action"] == candidate["safe_next_action"]
        assert route["runbook_candidate"] == candidate["runbook_candidate"]
        assert route["policy"]["host_owner_gap_route"] is True
        assert route["policy"]["host_layer_mutates_stack"] is False
        assert route["suggestion"]["command_profile"]["mutating_if_run"] is False


def test_static_bridge_sync_handoff_prefers_existing_closed_change(abyss_machine_module, tmp_path, monkeypatch) -> None:
    change_id = abyss_machine_module.STATIC_BRIDGE_ROOT_SYNC_CHANGE_ID
    active_root = tmp_path / "active"
    closed_root = tmp_path / "closed"
    closed_change = closed_root / change_id
    closed_change.mkdir(parents=True)
    active_root.mkdir(parents=True)

    monkeypatch.setattr(abyss_machine_module, "CHANGE_ACTIVE_ROOT", active_root)
    monkeypatch.setattr(abyss_machine_module, "CHANGE_CLOSED_ROOT", closed_root)

    handoff = abyss_machine_module.stack_bridge_static_sync_change_ref()

    assert handoff["id"] == change_id
    assert handoff["path"] == str(closed_change)
    assert handoff["status"] == "closed_handoff"
    assert handoff["exists"] is True


def test_abyssvault_backup_plane_route_to_non_executing_response(abyss_machine_module) -> None:
    active_change = {
        "id": abyss_machine_module.ABYSSVAULT_BACKUP_PLANE_CHANGE_ID,
        "title": "ABYSSVAULT backup plane setup",
        "status": "active",
        "path": "/var/lib/abyss-machine/changes/active/abyssvault-backup-plane-20260523",
        "surfaces": ["/var/lib/abyss-machine/backup", "/abyss/Backups"],
        "updated_at": "2026-06-10T16:29:37-06:00",
    }
    backup_status = {
        "schema": "abyss_backup_latest_v1",
        "generated_at": "2026-06-10T22:50:33Z",
        "status": "ok",
        "vault": "/abyss",
        "backup_root": "/abyss/Backups",
        "vault_mounted": False,
        "restic_binary": "/abyss/Backups/bin/restic",
        "restic_binary_exists": False,
        "restic_repo": "/abyss/Backups/restic/system",
        "restic_repo_initialized": False,
        "privileged_install": {
            "etc_policy_exists": True,
            "usr_local_command_exists": True,
            "system_timer_exists": True,
            "sessions_timer_exists": True,
            "sessions_checksum_timer_exists": True,
        },
    }

    route = abyss_machine_module.abyssvault_backup_plane_route(backup_status, active_change)
    assert abyss_machine_module.abyssvault_backup_plane_route_complete(route)
    assert route["blockers"] == ["vault_not_mounted", "restic_binary_missing", "restic_repo_not_initialized"]
    assert route["safe_next_action"]["review_command"] == "abyss-backup status --json"
    assert route["safe_next_action"]["executes_commands"] is False
    assert route["safe_next_action"]["writes_abyss_vault"] is False
    assert route["safe_next_action"]["runs_backup"] is False
    assert route["policy"]["keeps_change_open_until_verified"] is True

    candidate = abyss_machine_module.reaction_candidate(
        "abyssvault-backup-plane-open",
        title="ABYSSVAULT backup plane remains open",
        severity="warning",
        category="backup",
        reason="Backup-plane change is active and live backup status still has blockers.",
        command="abyss-backup status --json",
        owner_route="abyss-machine:backup-operator",
        action_mode="operator_mount_and_verify",
        evidence=[{"path": str(abyss_machine_module.BACKUP_LATEST_PATH)}],
    )
    candidate["backup_plane_route"] = route
    candidate["safe_next_action"] = route["safe_next_action"]
    candidate["runbook_candidate"] = route["runbook_candidate"]

    response_route = abyss_machine_module.response_route_from_candidate(candidate)
    assert response_route["backup_plane_route"] == route
    assert response_route["safe_next_action"] == route["safe_next_action"]
    assert response_route["policy"]["backup_plane_route"] is True
    assert response_route["policy"]["requires_backup_operator_approval"] is True
    assert response_route["suggestion"]["command_profile"]["kind"] == "backup_status_probe"
    assert response_route["suggestion"]["command_profile"]["mutating_if_run"] is False
    assert response_route["executes"] is False


def test_nervous_semantic_resource_gate_is_preserved_in_responses(abyss_machine_module) -> None:
    nervous_brief = {
        "schema": "abyss_machine_nervous_brief_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
    }
    readiness = {
        "status": "degraded",
        "semantic_stale": True,
        "semantic_maintenance_needed": True,
    }
    semantic_maintain = {
        "schema": "abyss_machine_nervous_semantic_maintain_v1",
        "ok": True,
        "dry_run": True,
        "decision": "dry_run_blocked_index_refresh",
        "assessment": {
            "needed": True,
            "stale": True,
            "reasons": ["stale_delta_chunks=149"],
            "source_chunks": 206157,
            "vectors": 206008,
            "delta_chunks": 149,
            "min_delta_chunks": 128,
            "semantic_age_minutes": 106.1,
            "source_index_changed": True,
        },
        "index_refresh": {
            "assessment": {"needed": True, "stale": True, "records_lag": 68},
            "command": ["abyss-machine", "nervous", "index-build", "--json"],
            "launch": {
                "ok": False,
                "blocked_reasons": ["game_guard_active"],
                "request": {
                    "class": "medium",
                    "kind": "indexing",
                    "unattended": True,
                    "timeout_sec": 300,
                    "command": ["abyss-machine", "nervous", "index-build", "--json"],
                },
                "plan": {
                    "decision": "force_required",
                    "blocked_reasons": ["game_guard_unattended_medium_or_heavier"],
                },
            },
        },
    }
    game_guard = {
        "schema": "abyss_machine_process_game_guard_v1",
        "active": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "summary": {"active_game_processes": 1},
    }

    gate = abyss_machine_module.nervous_semantic_resource_gate_evidence(
        nervous_brief=nervous_brief,
        readiness=readiness,
        semantic_maintain=semantic_maintain,
        game_guard=game_guard,
    )
    assert gate["schema"] == "abyss_machine_nervous_semantic_resource_gate_v1"
    assert gate["status"] == "blocked"
    assert gate["resource_plan_decision"] == "force_required"
    assert gate["semantic"]["delta_chunks"] == 149
    assert gate["game_guard"]["active"] is True
    assert "game_guard_active" in gate["blocked_reasons"]
    assert gate["policy"]["does_not_bypass_resource_gate"] is True
    assert gate["safe_next_action"]["executes_commands"] is False
    assert gate["safe_next_action"]["host_layer_mutates_stack"] is False

    candidate = abyss_machine_module.reaction_candidate(
        "nervous-readiness-not-ready",
        title="Nervous readiness is not ready",
        severity="watch",
        category="nervous",
        reason="fixture",
        command=gate["safe_next_action"]["review_command"],
        evidence=[{"semantic_resource_gate": gate}],
    )
    candidate["resource_gate"] = gate
    candidate["safe_next_action"] = gate["safe_next_action"]
    route = abyss_machine_module.response_route_from_candidate(candidate)

    assert route["resource_gate"] == gate
    assert route["safe_next_action"] == gate["safe_next_action"]
    assert route["executes"] is False
    assert route["suggestion"]["command"] == "abyss-machine nervous semantic-maintain --dry-run --refresh-index-first --json"
    assert route["suggestion"]["command_profile"]["kind"] == "gated_maintenance"
    assert route["suggestion"]["command_profile"]["mutating_if_run"] is False
    assert route["policy"]["host_layer_mutates_stack"] is False


def test_self_awareness_ai_multimodal_detail_is_concrete_and_non_promoting(abyss_machine_module) -> None:
    ai_caps = {
        "schema": "abyss_machine_ai_capabilities_v1",
        "capabilities": {
            "stt": {
                "status": "ready",
                "host_recommended_backend": "OpenVINO Whisper AUTO:GPU,CPU",
                "primary_bridge": "abyss-machine dictation transcribe AUDIO.wav --profile auto --json",
                "source_models": [{"profile": "quality", "model_dir": "/srv/AbyssOS/abyss-stack/Models/stt/whisper/openvino/large", "device": "AUTO:GPU,CPU"}],
                "non_claims": ["fixture"],
            },
            "embeddings": {
                "status": "ready",
                "primary_bridge": "abyss-machine ai eval --suite embeddings --json",
                "source_models": [{"kind": "directory", "category": "ovms_openvino", "name": "Qwen3-Embedding", "path": "/srv/AbyssOS/abyss-stack/Models/ovms/OpenVINO/Qwen3-Embedding", "root": "/srv/AbyssOS/abyss-stack/Models", "read_only_source": True}],
            },
            "llm_text": {
                "status": "resident-running",
                "primary_bridge": "abyss-machine ai llm registry --json",
                "resident_bridge": "abyss-machine ai llm resident status --json",
                "eval_bridge": "abyss-machine ai eval --suite text --json",
                "source_models": [{"kind": "directory", "category": "openvino_ir", "name": "Qwen3-4B", "path": "/srv/AbyssOS/abyss-stack/Models/ovms-text-lab/OpenVINO/Qwen3-4B", "root": "/srv/AbyssOS/abyss-stack/Models", "read_only_source": True}],
                "stack_bridge_hint": "stack owns promotion",
            },
            "tts": {
                "status": "runtime-proven",
                "primary_bridge": "abyss-machine ai tts profiles --json",
                "eval_bridge": "abyss-machine ai tts eval --profile quality --json",
                "server_bridge": "abyss-machine ai tts server status --json",
                "source_models": [{"kind": "directory", "category": "huggingface_local", "name": "Qwen3-TTS", "path": "/srv/AbyssOS/abyss-stack/Models/hf/local/Qwen3-TTS", "root": "/srv/AbyssOS/abyss-stack/Models", "read_only_source": True}],
                "non_claims": ["not promoted"],
            },
            "npu": {
                "status": "runtime-ready",
                "primary_bridge": "abyss-machine ai benchmark --quick --devices NPU --json",
                "source_models": [],
                "non_claims": ["NPU readiness is not model-family readiness"],
            },
        },
    }
    detail = abyss_machine_module.self_awareness_ai_multimodal_detail(
        ai_caps,
        {
            "schema": "abyss_machine_ai_devices_v1",
            "ready": {"openvino": True, "cpu": True, "gpu": True, "npu": True},
            "openvino": {
                "ok": True,
                "openvino_version": "fixture",
                "available_devices": ["CPU", "GPU", "NPU"],
                "device_properties": {
                    "CPU": {"FULL_DEVICE_NAME": "cpu"},
                    "GPU": {"FULL_DEVICE_NAME": "gpu"},
                    "NPU": {"FULL_DEVICE_NAME": "npu", "OPTIMIZATION_CAPABILITIES": ["FP16", "INT8"]},
                },
            },
        },
        {
            "schema": "abyss_machine_ai_models_v1",
            "summary": {"entries": 7, "by_category": {"openvino_ir": 2}, "truncated": False},
            "roots": [{"path": "/srv/AbyssOS/abyss-stack/Models", "exists": True, "entries_seen": 7}],
        },
        {
            "schema": "abyss_machine_ai_tts_profiles_v1",
            "summary": {"profiles": 2, "executable": 1, "disabled": 1},
            "profiles": {
                "quality": {
                    "status": "executable",
                    "engine": "qwen3_tts_openvino",
                    "declared_class": "heavy",
                    "device": "GPU",
                    "precision": "fp16",
                    "model": {"path": "/srv/AbyssOS/abyss-stack/Models/hf/local/Qwen3-TTS", "exists": True, "complete": True, "read_only_source": True},
                    "openvino": {"path": "/srv/abyss-machine/cache/ai/tts/qwen3-openvino/quality", "complete": True, "host_managed": True},
                    "runtime": {"ready": True, "synth_supported": True},
                    "policy": {"host_layer_mutates_stack": False},
                }
            },
        },
        {"schema": "abyss_machine_ai_tts_eval_v1", "ok": True, "generated_at": "2026-01-01T00:00:00+00:00", "profile": "quality", "summary": {"rtf": 1.5}},
        {
            "schema": "abyss_machine_ai_llm_registry_v1",
            "summary": {"profiles": 2, "ready_profiles": 2, "runtime_ok": True},
            "profiles": {
                "gemma4.spark": {"status": "ready", "role": "resident_small_brain", "backend": "llama.cpp", "declared_class": "medium", "local_exists": True, "runtime": {"ok": True}, "storage": {"under_host_cache": True}, "policy": {"host_layer_mutates_stack": False}},
                "qwen36.ordinary": {"status": "ready", "role": "lazy_load_deep_reasoning", "backend": "llama.cpp", "declared_class": "heavy", "local_exists": True, "runtime": {"ok": True}, "storage": {"under_host_cache": True}, "policy": {"host_layer_mutates_stack": False}},
            },
        },
    )

    assert abyss_machine_module.self_awareness_ai_multimodal_detail_complete(detail) is True
    assert detail["status"] == "ready"
    assert {"CPU", "GPU", "NPU"}.issubset(set(detail["devices"]["available_devices"]))
    assert detail["model_inventory"]["entries"] == 7
    assert detail["modalities"]["stt"]["source_model_count"] == 1
    assert detail["modalities"]["embeddings"]["source_model_count"] == 1
    assert detail["modalities"]["llm_text"]["registry_summary"]["ready_profiles"] == 2
    assert detail["modalities"]["llm_text"]["profiles"]["qwen36.ordinary"]["resource_gated"] is True
    assert detail["modalities"]["tts"]["profile_summary"]["executable"] == 1
    assert detail["modalities"]["tts"]["profiles"]["quality"]["openvino_host_managed"] is True
    assert detail["modalities"]["npu"]["device_ready"] is True
    assert detail["policy"]["host_layer_mutates_stack"] is False
    assert detail["policy"]["capability_presence_is_stack_promotion"] is False
    assert detail["policy"]["future_stack_must_run_own_promotion_gates"] is True


def test_self_awareness_llm_escalation_detail_is_gated_review_only(abyss_machine_module) -> None:
    ai_llm = {
        "schema": "abyss_machine_ai_llm_registry_v1",
        "ok": True,
        "summary": {"profiles": 4, "ready_profiles": 4, "runtime_ok": True},
        "profiles": {
            "gemma4.workhorse": {
                "status": "ready",
                "role": "on_demand_better_reasoning",
                "backend": "llama.cpp",
                "declared_class": "heavy",
                "warm_policy": "on_demand_warm_after_resource_gate",
                "local_exists": True,
                "size_bytes": 6656152736,
                "local_path": "/srv/abyss-machine/cache/ai/gemma4/e4b/model.gguf",
                "runtime": {"ok": True},
                "storage": {"under_host_cache": True},
                "policy": {"host_layer_mutates_stack": False},
                "launch": {"cli_smoke": ["llama-cli", "-c", "8192"], "server_base": ["llama-server", "-c", "8192"]},
            },
            "qwen36.ordinary": {
                "status": "ready",
                "role": "lazy_load_deep_reasoning",
                "backend": "llama.cpp",
                "declared_class": "heavy",
                "warm_policy": "on_demand_lazy_load_single_model_server",
                "local_exists": True,
                "size_bytes": 13586217184,
                "local_path": "/srv/abyss-machine/cache/ai/qwen3.6/ordinary/model.gguf",
                "runtime": {"ok": True},
                "storage": {"under_host_cache": True},
                "policy": {"host_layer_mutates_stack": False},
                "max_context_size": 32768,
                "server": {
                    "host": "127.0.0.1",
                    "port_base": 18180,
                    "threads": 6,
                    "batch": 512,
                    "ubatch": 256,
                    "flash_attention": True,
                    "kv_cache": "q8_0",
                    "slot_cache_root": "/srv/abyss-machine/cache/ai/qwen3.6/prefill-cache/slots/ordinary",
                    "prefill_evidence_root": "/var/lib/abyss-machine/ai/llm/evals/qwen36/prefill-cache",
                    "resource_class": "heavy",
                    "resource_kind": "ai",
                    "cpuset": "0-1,6-11,14-15",
                },
                "lazy_load": {
                    "tool": "/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server",
                    "start_command": "abyss-qwen36-lazy-server start --profile ordinary --ctx 8192 --json",
                    "prefill_command": "abyss-qwen36-lazy-server prefill --profile ordinary --ctx 8192 --prompt-file FILE --save-slot SLOT.bin --json",
                    "restore_command": "abyss-qwen36-lazy-server restore-slot --profile ordinary --ctx 8192 --filename SLOT.bin --json",
                    "request_command": "abyss-qwen36-lazy-server request --profile ordinary --ctx 8192 --prompt-file FILE --json",
                    "stop_command": "abyss-qwen36-lazy-server stop --profile ordinary --ctx 8192 --json",
                },
            },
            "qwen36.heretic": {
                "status": "ready",
                "role": "lazy_load_uncensored_deep_reasoning",
                "backend": "llama.cpp",
                "declared_class": "heavy",
                "warm_policy": "on_demand_lazy_load_single_model_server_exclusive",
                "local_exists": True,
                "size_bytes": 13301446272,
                "local_path": "/srv/abyss-machine/cache/ai/qwen3.6/heretic/model.gguf",
                "runtime": {"ok": True},
                "storage": {"under_host_cache": True},
                "policy": {"host_layer_mutates_stack": False},
                "max_context_size": 32768,
                "server": {
                    "host": "127.0.0.1",
                    "port_base": 18190,
                    "threads": 6,
                    "batch": 512,
                    "ubatch": 256,
                    "flash_attention": True,
                    "kv_cache": "q8_0",
                    "slot_cache_root": "/srv/abyss-machine/cache/ai/qwen3.6/prefill-cache/slots/heretic",
                    "prefill_evidence_root": "/var/lib/abyss-machine/ai/llm/evals/qwen36/prefill-cache",
                    "resource_class": "heavy",
                    "resource_kind": "ai",
                    "cpuset": "0-1,6-11,14-15",
                },
                "lazy_load": {
                    "tool": "/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server",
                    "start_command": "abyss-qwen36-lazy-server start --profile heretic --ctx 8192 --json",
                    "prefill_command": "abyss-qwen36-lazy-server prefill --profile heretic --ctx 8192 --prompt-file FILE --save-slot SLOT.bin --json",
                    "restore_command": "abyss-qwen36-lazy-server restore-slot --profile heretic --ctx 8192 --filename SLOT.bin --json",
                    "request_command": "abyss-qwen36-lazy-server request --profile heretic --ctx 8192 --prompt-file FILE --json",
                    "stop_command": "abyss-qwen36-lazy-server stop --profile heretic --ctx 8192 --json",
                },
            },
        },
    }
    detail = abyss_machine_module.self_awareness_llm_escalation_detail(
        ai_llm,
        {
            "schema": "abyss_machine_gemma4_workhorse_harness_e4b_review_pack_v2",
            "ok": True,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {"items": 24, "review_required": 24, "source_ids": 23, "selected_candidates": 24},
            "allowed_source_ids": ["source-1", "source-2"],
            "policy": {"e4b_may_review_only": True, "e4b_may_not_execute": True, "derived_candidate_not_truth": True},
        },
        {
            "schema": "abyss_machine_gemma4_workhorse_harness_review_v1",
            "ok": True,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {"checks": 31, "fails": 0, "warnings": 0, "model_used": False, "parsed": False},
            "policy": {"action_execution": False, "final_safety_gate": False, "requires_downstream_validator": True, "resident_service": False, "starts_llama_server": False},
        },
        {
            "schema": "abyss_machine_gemma4_workhorse_harness_validate_v1",
            "ok": True,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {"checks": 34, "fails": 0, "warnings": 0},
            "checks": [{"level": "ok", "key": "source_ids_allowed"}],
        },
        {
            "schema": "abyss_machine_gemma4_workhorse_harness_preflight_v1",
            "ok": False,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "decision": "block",
            "blocked_reasons": ["resource_decision=force_required"],
            "resource": {"decision": "force_required", "blocked_reasons": ["game_guard_active"], "systemd": {"properties": {"AllowedCPUs": "0-1,6-11,14-15"}}},
            "memory": {"class": "warm", "swap_free_mib": 2994.5},
            "model": {"context_size": 8192, "local_exists": True},
            "policy": {"action_execution": False, "default_review_runs_model": False, "resident_service": False, "starts_llama_server": False},
        },
        {
            "schema": "abyss_machine_resource_status_v1",
            "ok": True,
            "latest_plan": {"decision": "force_required", "request": {"class": "heavy", "kind": "ai"}},
        },
        {
            "schema": "abyss_machine_mode_status_v1",
            "selected_mode": "balanced",
            "effective_mode": "balanced",
            "degraded": False,
            "launch_policy": {
                "max_unattended_class": "medium",
                "can_start_heavy_unattended": False,
                "operator_force_supported": True,
                "cpu_routed_heavy": {
                    "can_start": True,
                    "can_start_unattended": True,
                    "requires_route_application": True,
                    "command": "abyss-machine ai cpu route --class heavy --json",
                    "policy": {"route": {"cpuset": "0-1,6-11,14-15", "thread_limit": 6}, "distribution": {"thermal_class": "green", "package_temperature_c_max": 72.0}},
                },
            },
        },
    )

    assert abyss_machine_module.self_awareness_llm_escalation_detail_complete(detail) is True
    assert detail["status"] == "ready_review_only"
    assert detail["route_ready"] is True
    assert detail["review_pipeline_ready"] is True
    assert detail["workhorse"]["review"]["summary"]["model_used"] is False
    assert detail["workhorse"]["preflight"]["decision"] == "block"
    assert detail["gates"]["model_execution_now"]["allowed"] is False
    assert detail["gates"]["model_execution_now"]["status"] == "blocked_by_preflight"
    assert detail["qwen_lazy_load"]["ready"] is True
    assert detail["qwen_lazy_load"]["profiles"]["qwen36.ordinary"]["default_context_size"] == 8192
    assert detail["qwen_lazy_load"]["profiles"]["qwen36.heretic"]["lazy_load"]["request_command"]
    assert detail["gates"]["mode"]["cpu_routed_heavy"]["cpuset"] == "0-1,6-11,14-15"
    assert detail["policy"]["host_layer_mutates_stack"] is False
    assert detail["policy"]["model_execution_in_self_awareness_graph"] is False
    assert detail["policy"]["default_model_execution"] is False
    assert detail["policy"]["action_execution"] is False
    assert detail["policy"]["qwen_lazy_load_is_not_resident_brain"] is True


def test_self_awareness_query_builder_is_bounded_redacted_and_non_mutating(abyss_machine_module) -> None:
    query = abyss_machine_module.self_awareness_query(
        "route-api Authorization: Bearer sk-example-redacted",
        limit=5000,
        write_latest=False,
    )
    plan = query["query_plan"]

    assert query["schema"] == "abyss_machine_self_awareness_query_v1"
    assert query["ok"] is True
    assert query["summary"]["limit"] == 100
    assert "<redacted>" in query["query"]
    assert "sk-example-redacted" not in query["query"].lower()
    assert plan["bounded"] is True
    assert plan["raw_secret_storage"] is False
    assert plan["promql"]
    assert plan["logql"]
    assert plan["readmodels"]
    assert query["policy"]["does_not_mutate_stack"] is True


def test_self_awareness_from_zero_cycle_proof_requires_step_artifacts(abyss_machine_module) -> None:
    chain_sources = abyss_machine_module.self_awareness_cycle_from_zero_chain_sources()
    chain = {key: True for key in chain_sources}
    step_ids = sorted({step_id for step_ids in chain_sources.values() for step_id in step_ids} | {"requirements"})
    steps = [
        {
            "id": step_id,
            "command": f"abyss-machine self-awareness {step_id} --json",
            "ok": True,
            "artifact": {
                "path": f"/var/lib/abyss-machine/self-awareness/{step_id}/latest.json",
                "schema": f"abyss_machine_fixture_{step_id}_v1",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "exists": True,
                "size_bytes": 128,
                "sha256": "a" * 64,
                "mtime_ns": 1,
                "mtime_iso": "2026-01-01T00:00:00+00:00",
            },
        }
        for step_id in step_ids
    ]

    proof = abyss_machine_module.self_awareness_cycle_from_zero_proof(
        generated_at="2026-01-01T00:00:00+00:00",
        cycle_id="sacycle-fixture",
        probe_run_id="saprobe-fixture",
        cycle_chain=chain,
        steps=steps,
        failed_steps=[],
        missing_chain=[],
    )

    assert proof["schema"] == "abyss_machine_self_awareness_from_zero_cycle_proof_v1"
    assert proof["ok"] is True
    assert proof["summary"]["proof_steps"] == len(steps)
    assert proof["summary"]["chain_obligations"] == len(chain)
    assert proof["summary"]["proof_bad_steps"] == []
    assert proof["summary"]["missing_obligations"] == []
    assert abyss_machine_module.self_awareness_cycle_from_zero_proof_complete(proof) is True

    broken = dict(proof)
    broken["proof_steps"] = [dict(item) for item in proof["proof_steps"]]
    broken["proof_steps"][0] = dict(broken["proof_steps"][0])
    broken["proof_steps"][0]["artifact"] = dict(broken["proof_steps"][0]["artifact"])
    broken["proof_steps"][0]["artifact"]["sha256"] = None

    assert abyss_machine_module.self_awareness_cycle_from_zero_proof_complete(broken) is False


def test_self_awareness_e2e_lineage_proof_links_required_cycle_rows(monkeypatch, abyss_machine_module) -> None:
    def fake_artifact_ref(name, path, schema):
        return {
            "name": name,
            "path": f"/var/lib/abyss-machine/self-awareness/{name}/latest.json",
            "history_path": f"/var/lib/abyss-machine/self-awareness/{name}/YYYY/MM/YYYY-MM-DD.jsonl",
            "exists": True,
            "schema": schema,
            "expected_schema": schema,
            "schema_ok": True,
            "ok": True,
            "status": "ok",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {"fixture": name},
            "sha256": "b" * 64,
        }

    monkeypatch.setattr(abyss_machine_module, "self_awareness_latest_artifact_ref", fake_artifact_ref)
    chain = {
        "request": True,
        "metric": True,
        "log": True,
        "trace_context": True,
        "trace_context_fallback": True,
        "context": True,
        "observation_events": True,
        "working_stack": True,
        "query": True,
        "correlation": True,
        "timeline": True,
        "spatial_graph": True,
        "causal_episode": True,
        "alert": True,
        "warm_e2b": True,
        "rag_memory": True,
        "nervous_freshness": True,
        "langgraph_investigation": True,
        "replay": True,
        "resident_cognitive_replay": True,
        "resident_cognitive_export": True,
        "reaction_candidate": True,
        "governed_response": True,
        "body_trace": True,
        "entity_event_document": True,
        "autolink": True,
        "export": True,
    }

    proof = abyss_machine_module.self_awareness_e2e_lineage_proof(
        generated_at="2026-01-01T00:00:00+00:00",
        run_id="saprobe-fixture",
        traceparent="00-" + ("a" * 32) + "-" + ("b" * 16) + "-01",
        chain=chain,
        synthetic_events=[{"event_id": "saevt-fixture-probe"}, {"event_id": "saevt-fixture-alert"}],
        include_probe=False,
    )

    row_ids = {row["id"] for row in proof["rows"]}
    assert proof["schema"] == "abyss_machine_self_awareness_e2e_lineage_proof_v1"
    assert proof["ok"] is True
    assert proof["summary"]["rows"] == len(abyss_machine_module.self_awareness_e2e_lineage_specs())
    assert proof["summary"]["missing_rows"] == []
    assert proof["summary"]["synthetic_event_ids"] == 2
    assert "synthetic_request" in row_ids
    assert "trace_context_fallback" in row_ids
    assert "working_stack_body" in row_ids
    assert "query_and_correlation" in row_ids
    assert "warm_e2b_context" in row_ids
    assert "resident_cognitive_replay" in row_ids
    assert "body_trace" in row_ids
    assert "entity_event_document_context" in row_ids
    assert "resident_cognitive_export" in row_ids
    assert "governed_response" in row_ids
    assert "autolink" in row_ids
    assert "export" in row_ids
    assert abyss_machine_module.self_awareness_e2e_lineage_proof_complete(proof) is True
    assert all(row["policy"]["host_layer_mutates_stack"] is False for row in proof["rows"])
    assert all(row["evidence_refs"] for row in proof["rows"])

    broken = dict(proof)
    broken["rows"] = [dict(row) for row in proof["rows"]]
    broken["rows"][0] = dict(broken["rows"][0])
    broken["rows"][0]["evidence_refs"] = []

    assert abyss_machine_module.self_awareness_e2e_lineage_proof_complete(broken) is False


def test_self_awareness_top_level_lineage_packet_binds_cycle_probe_replay_and_response(abyss_machine_module) -> None:
    steps = [
        {
            "id": "probe",
            "command": "abyss-machine self-awareness probe --json",
            "ok": True,
            "artifact": {
                "path": "/var/lib/abyss-machine/self-awareness/probe/latest.json",
                "schema": "abyss_machine_self_awareness_probe_v1",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "exists": True,
                "ok": True,
                "sha256": "c" * 64,
            },
        },
        {
            "id": "replay",
            "command": "abyss-machine self-awareness replay --thread-id THREAD --json",
            "ok": True,
            "artifact": {
                "path": "/var/lib/abyss-machine/self-awareness/replay/latest.json",
                "schema": "abyss_machine_self_awareness_replay_v1",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "exists": True,
                "ok": True,
                "sha256": "d" * 64,
            },
        },
    ]
    chain = {"synthetic_request": True, "replay": True, "governed_response": True}
    e2e = {
        "schema": "abyss_machine_self_awareness_e2e_lineage_proof_v1",
        "ok": True,
        "summary": {"missing_rows": [], "rows": 22},
    }
    packet = abyss_machine_module.self_awareness_top_level_lineage_packet(
        generated_at="2026-01-01T00:00:00+00:00",
        source="cycle",
        cycle_id="sacycle-fixture",
        run_id="saprobe-fixture",
        traceparent="00-" + ("a" * 32) + "-" + ("b" * 16) + "-01",
        chain=chain,
        steps=steps,
        e2e_lineage_proof=e2e,
        from_zero_proof={"ok": True, "summary": {"proof_steps": 2}},
        investigation={"ok": True, "thread_id": "thread-fixture"},
        replay={"ok": True, "thread_id": "thread-fixture", "summary": {"divergences": 0}},
        reactions={"candidates": [{"id": "self-awareness-synthetic-alert-saprobe-fixture"}]},
        responses={"routes": [{"id": "self-awareness-response-saprobe-fixture"}], "summary": {"automatic_responses": 0, "approval_required": 1}},
        export={"ok": True, "summary": {"artifacts": 24}},
        synthetic_events=[{"event_id": "saevt-fixture-probe"}],
    )

    assert packet["schema"] == "abyss_machine_self_awareness_top_level_lineage_v1"
    assert packet["complete"] is True
    assert packet["cycle_bound"] is True
    assert packet["cycle_id"] == "sacycle-fixture"
    assert packet["run_id"] == "saprobe-fixture"
    assert packet["trace"]["trace_id"] == "a" * 32
    assert packet["trace"]["span_id"] == "b" * 16
    assert packet["trace"]["synthetic_event_ids"] == ["saevt-fixture-probe"]
    assert packet["thread"]["investigation_thread_id"] == "thread-fixture"
    assert packet["thread"]["replay_thread_id"] == "thread-fixture"
    assert packet["reaction_response"]["reaction_candidate_ids"] == ["self-awareness-synthetic-alert-saprobe-fixture"]
    assert packet["reaction_response"]["response_route_ids"] == ["self-awareness-response-saprobe-fixture"]
    assert packet["summary"]["chain_missing"] == []
    assert packet["summary"]["artifact_missing"] == []
    assert len(packet["evidence_refs"]) == len(steps)
    assert packet["policy"]["host_layer_mutates_stack"] is False
    assert packet["policy"]["actions_executed"] is False
    assert abyss_machine_module.self_awareness_top_level_lineage_complete(packet, require_cycle=True) is True

    broken = abyss_machine_module.self_awareness_top_level_lineage_packet(
        generated_at="2026-01-01T00:00:00+00:00",
        source="cycle",
        cycle_id="sacycle-fixture",
        run_id="saprobe-fixture",
        chain={"synthetic_request": True, "replay": False},
        steps=steps,
        e2e_lineage_proof=e2e,
        from_zero_proof={"ok": True},
        replay={"ok": True},
        export={"ok": True},
    )

    assert broken["complete"] is False
    assert broken["summary"]["chain_missing"] == ["replay"]
    assert abyss_machine_module.self_awareness_top_level_lineage_complete(broken, require_cycle=True) is False


def test_self_awareness_cycle_bridge_proof_requires_all_machine_bridges(abyss_machine_module) -> None:
    surfaces = abyss_machine_module.self_awareness_cycle_bridge_surfaces()
    rows = [
        {
            "schema": "abyss_machine_self_awareness_cycle_bridge_proof_row_v1",
            "id": surface["id"],
            "organ": surface["organ"],
            "command": surface["command"],
            "validator": surface["validator"],
            "coverage": surface["coverage"],
            "ok": True,
            "artifact": {
                "name": surface["id"],
                "path": f"/var/lib/abyss-machine/{surface['id']}/latest.json",
                "history_path": f"/var/lib/abyss-machine/{surface['id']}/YYYY/MM/YYYY-MM-DD.jsonl",
                "exists": True,
                "schema": surface["schema"],
                "expected_schema": surface["schema"],
                "schema_ok": True,
                "ok": True,
                "sha256": "b" * 64,
                "machine_owned_path": True,
            },
            "evidence_refs": [
                {
                    "path": f"/var/lib/abyss-machine/{surface['id']}/latest.json",
                    "schema": surface["schema"],
                    "sha256": "b" * 64,
                    "bridge_id": surface["id"],
                }
            ],
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
        for surface in surfaces
    ]
    proof = {
        "schema": "abyss_machine_self_awareness_cycle_bridge_proof_v1",
        "version": "fixture",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "cycle_id": "sacycle-fixture",
        "probe_run_id": "saprobe-fixture",
        "ok": True,
        "summary": {
            "bridges": len(rows),
            "missing": [],
            "schema_mismatch": [],
            "failed": [],
            "machine_bridge_obligations": [row["id"] for row in rows],
        },
        "rows": rows,
        "evidence_refs": [row["evidence_refs"][0] for row in rows],
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

    assert abyss_machine_module.self_awareness_cycle_bridge_proof_complete(proof) is True

    missing_row = dict(proof)
    missing_row["rows"] = rows[:-1]
    assert abyss_machine_module.self_awareness_cycle_bridge_proof_complete(missing_row) is False

    mutating = dict(proof)
    mutating["rows"] = [dict(row) for row in rows]
    mutating["rows"][0] = dict(mutating["rows"][0])
    mutating["rows"][0]["policy"] = dict(mutating["rows"][0]["policy"])
    mutating["rows"][0]["policy"]["host_layer_mutates_stack"] = True
    assert abyss_machine_module.self_awareness_cycle_bridge_proof_complete(mutating) is False


def test_bridge_manifest_includes_stack_bridge_extension_commands(tmp_path, monkeypatch, abyss_machine_module) -> None:
    manifest_path = tmp_path / "bridge.json"
    manifest_path.write_text(
        json.dumps({"schema": "abyss_machine_bridge_v1", "id": "fixture", "commands": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(abyss_machine_module, "MANIFEST_PATH", manifest_path)

    payload = abyss_machine_module.bridge_manifest()
    commands = payload["commands"]

    assert commands["self_awareness_trace_context_json"] == [
        "abyss-machine",
        "self-awareness",
        "trace-context",
        "--json",
    ]
    assert set(abyss_machine_module.stack_bridge_extension_commands()).issubset(commands)


def test_self_awareness_failure_matrix_covers_required_negative_paths(abyss_machine_module) -> None:
    matrix = abyss_machine_module.self_awareness_failure_matrix(write_latest=False)
    row_ids = {row["id"] for row in matrix["rows"]}

    assert matrix["schema"] == "abyss_machine_self_awareness_failure_matrix_v1"
    assert matrix["ok"] is True
    assert matrix["summary"]["failure_modes"] >= 15
    assert matrix["summary"]["requirements_rows"] >= 4
    assert matrix["summary"]["missing_required"] == []
    assert matrix["summary"]["malformed"] == []
    assert {
        "machine.resource-denial",
        "machine.nervous-semantic-stale",
        "machine.secret-redaction",
        "stack.loki-logql-missing-or-cardinality-risk",
        "stack.downtime-bounded-readonly",
        "requirement:stack.trace-backend",
        "requirement:stack.grafana.datasource-read",
        "requirement:stack.database-graph.read-route",
        "requirement:stack.langchain-api.graph-observability",
    }.issubset(row_ids)
    closed_requirement_rows = [
        row for row in matrix["rows"]
        if str(row.get("id", "")).startswith("requirement:")
        and row.get("current_state", {}).get("closed_by_current_probe") is True
    ]
    cycle_open_requirement_rows = [
        row for row in matrix["rows"]
        if abyss_machine_module.self_awareness_failure_matrix_row_is_open_requirement(row)
    ]
    assert all(row["failure_kind"] == "closed_requirement_regression_guard" for row in closed_requirement_rows)
    assert all(row["failure_kind"] == "open_requirement" for row in cycle_open_requirement_rows)
    assert not any(row in cycle_open_requirement_rows for row in closed_requirement_rows)
    assert all(row["host_layer_mutates_stack"] is False for row in matrix["rows"])
    assert all(row["automatic_remediation"] is False for row in matrix["rows"])


def test_self_awareness_working_stack_link_integrity_matrix_tracks_each_organ(abyss_machine_module) -> None:
    generated_at = "2026-01-01T00:00:00+00:00"
    services = [
        ("prometheus", "active_machine_signal", None),
        ("aoa-browser", "tool_runtime_degraded", "fixture browser launch failed"),
    ]
    organs = []
    events = []
    nodes = [{"id": "host:fixture", "kind": "host"}]
    edges = []
    contexts = []
    episodes = []
    coverage_rows = []

    for service, status, usage_gap in services:
        link = abyss_machine_module.self_awareness_working_stack_link(
            service,
            generated_at,
            status=status,
            container=service,
            endpoint_ok=True,
        )
        link_id = link["link_id"]
        movement_packet_id = "samove-fixture-" + service
        current_state_digest = "state-fixture-" + service
        organs.append({
            "schema": "abyss_machine_self_awareness_working_stack_organ_v1",
            "service": service,
            "machine_usage_status": status,
            "usage_gap": usage_gap,
            "time_space_context_link": link,
            "runtime": {"running": True, "container": service},
            "deep_usage_proven": usage_gap is None,
            "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": service}],
            "policy": {"host_layer_mutates_stack": False},
        })
        event = abyss_machine_module.self_awareness_make_event(
            "organ_movement",
            "working-stack",
            event_time=generated_at,
            resource={
                "service": service,
                "container": service,
                "owner_surface": "abyss-stack",
                "movement_packet_id": movement_packet_id,
                "current_state_digest": current_state_digest,
                "movement_categories": ["raw_signal", "episode_candidate"] if usage_gap else ["raw_signal"],
                "selected_for_episode": usage_gap is not None,
                "write": False,
            },
            context={
                "working_stack_link_id": link_id,
                "movement_packet_id": movement_packet_id,
                "current_state_digest": current_state_digest,
            },
            space={"host": "fixture", "owner_surface": "abyss-stack", "service": service, "container": service},
            evidence_refs=[{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json", "service": service}],
            truth_level="working_stack_inventory",
        )
        events.append(event)
        service_node = "service:" + service
        link_node = "working_stack_link:" + link_id
        nodes.extend([
            {"id": service_node, "kind": "service"},
            {"id": link_node, "kind": "working_stack_context_link"},
        ])
        edges.append({"from": service_node, "to": link_node, "kind": "has_time_space_context_link"})
        contexts.append({"key": link_id, "event_ids": [event["event_id"]], "context": {"working_stack_link_id": link_id}})
        episodes.append({
            "episode_id": "episode-" + service,
            "event_ids": [event["event_id"]],
            "affected_spatial_nodes": [service_node, link_node],
        })
        if usage_gap:
            coverage_rows.append({
                "id": "working_stack_gap:" + service,
                "service": service,
                "working_stack_link_id": link_id,
                "activation_smoke": {
                    "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1",
                    "complete": True,
                    "service": service,
                    "working_stack_link_id": link_id,
                    "policy": {"host_layer_mutates_stack": False},
                },
            })

    matrix = abyss_machine_module.self_awareness_working_stack_link_integrity_matrix(
        working_stack_doc={
            "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
            "summary": {"organs": len(organs), "usage_gaps": 1},
            "organs": organs,
        },
        events_doc={"schema": "abyss_machine_self_awareness_events_v1", "events": events},
        timeline_doc={"schema": "abyss_machine_self_awareness_timeline_v1", "windows": [{"event_ids": [event["event_id"] for event in events]}]},
        spatial_doc={"schema": "abyss_machine_self_awareness_spatial_graph_v1", "nodes": nodes, "edges": edges},
        context_doc={"schema": "abyss_machine_self_awareness_context_v1", "contexts": contexts},
        episodes_doc={"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": episodes},
        coverage_gap_rows=coverage_rows,
        generated_at=generated_at,
    )

    assert matrix["schema"] == "abyss_machine_self_awareness_working_stack_link_integrity_matrix_v1"
    assert matrix["ok"] is True
    assert abyss_machine_module.self_awareness_working_stack_link_integrity_matrix_complete(matrix) is True
    assert matrix["summary"]["rows"] == 2
    assert matrix["summary"]["complete_rows"] == 2
    assert matrix["summary"]["usage_gap_rows"] == 1
    assert matrix["summary"]["usage_gap_rows_with_coverage"] == 1
    assert matrix["summary"]["usage_gap_rows_with_activation_smoke"] == 1
    assert matrix["summary"]["missing_rows"] == []
    assert set(matrix["rows_by_service"]) == {"prometheus", "aoa-browser"}
    for row in matrix["rows"]:
        assert row["complete"] is True
        assert row["working_stack_link_id"]
        assert row["event_id"]
        assert row["movement_packet_id"]
        assert row["current_state_digest"]
        if row["episode_required"] is True:
            assert row["episode_ids"]
        else:
            assert row["adjacent_episode_ids"]
        assert row["checks"]["event_fabric_link"] is True
        assert row["checks"]["movement_packet"] is True
        assert row["checks"]["timeline_window"] is True
        assert row["checks"]["spatial_service_to_link_edge"] is True
        assert row["checks"]["context_indexed"] is True
        assert row["policy"]["host_layer_mutates_stack"] is False


def test_self_awareness_working_stack_link_identity_is_stable_across_time_buckets(abyss_machine_module) -> None:
    first = abyss_machine_module.self_awareness_working_stack_link(
        "aoa-browser",
        "2026-01-01T00:01:00+00:00",
        status="tool_runtime_degraded",
        container="aoa-browser",
        endpoint_ok=True,
    )
    second = abyss_machine_module.self_awareness_working_stack_link(
        "aoa-browser",
        "2026-01-01T00:08:00+00:00",
        status="tool_runtime_degraded",
        container="aoa-browser",
        endpoint_ok=True,
    )

    assert first["link_id"] == second["link_id"]
    assert first["time"]["bucket"] != second["time"]["bucket"]
    assert first["context"]["working_stack_link_id"] == first["link_id"]
    assert abyss_machine_module.self_awareness_working_stack_expected_link_id("aoa-browser", "tool_runtime_degraded") == first["link_id"]


def test_self_awareness_autolink_requires_time_space_context_and_stack_blocker_links(abyss_machine_module) -> None:
    doc = {
        "schema": "abyss_machine_self_awareness_autolink_v1",
        "ok": True,
        "state_digest": "a" * 32,
        "state_delta": {
            "schema": "abyss_machine_self_awareness_autolink_state_delta_v1",
            "previous_seen": True,
            "previous_state_digest": "b" * 32,
            "current_state_digest": "a" * 32,
            "state_changed": True,
            "added_services": ["aoa-browser"],
            "removed_services": [],
            "changed_services": [],
            "added_requirements": ["stack.trace-backend"],
            "removed_requirements": [],
            "changed_requirements": [],
            "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
        },
        "summary": {
            "organ_links": 1,
            "organ_links_complete": 1,
            "stack_requirement_links": 1,
            "stack_requirement_links_complete": 1,
            "synthetic_scenarios": 1,
            "synthetic_scenarios_complete": 1,
        },
        "organ_links": [
            {
                "schema": "abyss_machine_self_awareness_autolink_organ_row_v1",
                "complete": True,
                "service": "aoa-browser",
                "working_stack_link_id": "saworklink-fixture",
                "machine_usage_status": "tool_runtime_degraded",
                "usage_gap": "fixture browser launch failed",
                "event_id": "saevt-fixture",
                "movement_packet_id": "samove-fixture",
                "movement_current_state_digest": "state-fixture",
                "episode_required": True,
                "time": {"bucket": "2026-01-01T00:00:00Z"},
                "space": {"nodes": ["service:aoa-browser", "working_stack_link:saworklink-fixture"]},
                "context": {"key": "saworklink-fixture"},
                "episode_ids": ["saepisode-fixture"],
                "activation_smoke": {
                    "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1",
                    "complete": True,
                    "working_stack_link_id": "saworklink-fixture",
                },
                "checks": {
                    "time_linked": True,
                    "space_linked": True,
                    "context_linked": True,
                    "movement_packet_linked": True,
                    "episode_linked": True,
                    "gap_has_activation_smoke": True,
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
        "stack_requirement_links": [
            {
                "schema": "abyss_machine_self_awareness_autolink_stack_requirement_row_v1",
                "complete": True,
                "requirement_id": "stack.trace-backend",
                "owner": "abyss-stack",
                "episode_ids": ["saepisode-stack-fixture"],
                "checks": {
                    "closure_acceptance": True,
                    "coverage_impact": True,
                    "owner_route": True,
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
        "synthetic_scenarios": [
            {
                "schema": "abyss_machine_self_awareness_autolink_synthetic_scenario_v1",
                "id": "state_delta_digest",
                "complete": True,
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
            }
        ],
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }

    assert abyss_machine_module.self_awareness_autolink_complete(doc) is True

    broken = dict(doc)
    broken["organ_links"] = [dict(doc["organ_links"][0])]
    broken["organ_links"][0]["episode_ids"] = []

    assert abyss_machine_module.self_awareness_autolink_complete(broken) is False

    stale_smoke = dict(doc)
    stale_smoke["organ_links"] = [dict(doc["organ_links"][0])]
    stale_smoke["organ_links"][0]["activation_smoke"] = dict(stale_smoke["organ_links"][0]["activation_smoke"])
    stale_smoke["organ_links"][0]["activation_smoke"]["working_stack_link_id"] = "saworklink-stale"

    assert abyss_machine_module.self_awareness_autolink_complete(stale_smoke) is False


def test_self_awareness_autolink_allows_closed_stack_requirement_without_open_episode(abyss_machine_module) -> None:
    doc = {
        "schema": "abyss_machine_self_awareness_autolink_v1",
        "ok": True,
        "state_digest": "c" * 32,
        "state_delta": {
            "schema": "abyss_machine_self_awareness_autolink_state_delta_v1",
            "previous_seen": True,
            "previous_state_digest": "b" * 32,
            "current_state_digest": "c" * 32,
            "state_changed": True,
            "added_services": [],
            "removed_services": [],
            "changed_services": [],
            "added_requirements": [],
            "removed_requirements": [],
            "changed_requirements": ["stack.grafana.datasource-read"],
            "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
        },
        "summary": {
            "organ_links": 1,
            "organ_links_complete": 1,
            "stack_requirement_links": 1,
            "stack_requirement_links_complete": 1,
            "synthetic_scenarios": 1,
            "synthetic_scenarios_complete": 1,
        },
        "organ_links": [
            {
                "schema": "abyss_machine_self_awareness_autolink_organ_row_v1",
                "complete": True,
                "service": "prometheus",
                "working_stack_link_id": "saworklink-prometheus",
                "event_id": "saevt-prometheus",
                "movement_packet_id": "samove-prometheus",
                "movement_current_state_digest": "state-prometheus",
                "time": {"bucket": "2026-01-01T00:00:00Z"},
                "space": {"nodes": ["service:prometheus"]},
                "context": {"key": "saworklink-prometheus"},
                "episode_ids": ["saepisode-prometheus"],
                "checks": {
                    "time_linked": True,
                    "space_linked": True,
                    "context_linked": True,
                    "movement_packet_linked": True,
                    "episode_linked": True,
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
        "stack_requirement_links": [
            {
                "schema": "abyss_machine_self_awareness_autolink_stack_requirement_row_v1",
                "complete": True,
                "requirement_id": "stack.grafana.datasource-read",
                "owner": "abyss-stack",
                "status": "closed",
                "closed_by_current_probe": True,
                "automatic_link_state": "closed",
                "episode_ids": [],
                "checks": {
                    "closure_acceptance": True,
                    "coverage_impact": True,
                    "owner_route": True,
                    "episode_linked": True,
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
        "synthetic_scenarios": [
            {
                "schema": "abyss_machine_self_awareness_autolink_synthetic_scenario_v1",
                "id": "stack_blocker_owner_routed_context",
                "complete": True,
                "checks": {"episode_or_closed_state": True},
                "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
            }
        ],
        "policy": {
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }

    assert abyss_machine_module.self_awareness_autolink_complete(doc) is True


def test_self_awareness_episodes_must_cover_current_open_stack_requirements(abyss_machine_module) -> None:
    dossier = {
        "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        "entries": [
            {"requirement_id": "stack.database-graph.read-route", "status": "open"},
            {"requirement_id": "stack.trace-backend", "status": "closed"},
        ],
    }
    stale_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "episodes": [
            {
                "episode_id": "saepisode-trace",
                "affected_spatial_nodes": ["stack_requirement:stack.trace-backend"],
            }
        ],
    }
    fresh_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "episodes": [
            {
                "episode_id": "saepisode-db",
                "affected_spatial_nodes": ["stack_requirement:stack.database-graph.read-route"],
            }
        ],
    }

    assert abyss_machine_module.self_awareness_episodes_cover_stack_requirements(stale_episodes, dossier) is False
    assert abyss_machine_module.self_awareness_episodes_cover_stack_requirements(fresh_episodes, dossier) is True
    assert abyss_machine_module.self_awareness_episodes_cover_stack_requirements(stale_episodes, {"entries": [dossier["entries"][1]]}) is True


def test_self_awareness_autolink_refreshes_stale_stack_requirement_episodes(monkeypatch, abyss_machine_module) -> None:
    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "summary": {"usage_gaps": 0},
    }
    coverage_audit = {
        "schema": "abyss_machine_self_awareness_objective_coverage_audit_v1",
        "working_stack_link_integrity": {
            "summary": {"rows": 1, "complete_rows": 1, "missing_rows": []},
            "rows": [
                {
                    "service": "route-api",
                    "complete": True,
                    "working_stack_link_id": "saworklink-route-api",
                    "machine_usage_status": "runtime_running",
                    "event_id": "saevt-route-api",
                    "movement_packet_id": "samove-route-api",
                    "current_state_digest": "state-route-api",
                    "timeline_bucket": "2026-07-01T00:00:00Z",
                    "spatial_nodes": ["service:route-api"],
                    "context_key": "saworklink-route-api",
                    "episode_required": False,
                    "policy": {"host_layer_mutates_stack": False},
                }
            ],
        },
    }
    stack_closure_dossier = {
        "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        "summary": {"open_stack_requirements": 1},
        "entries": [
            {
                "requirement_id": "stack.database-graph.read-route",
                "owner": "abyss-stack",
                "status": "open",
                "complete": True,
                "blocking_check_keys": ["database_graph_inventory_route_present"],
                "current_state_digest": "state-db-route",
                "closure_acceptance": {"acceptance_id": "saclose-db"},
                "coverage_impact": {
                    "coverage_planes": ["spatial_graph"],
                    "affected_stack_surfaces": ["Neo4j", "rag-api"],
                    "affected_machine_surfaces": ["spatial-graph"],
                },
                "policy": {"host_layer_mutates_stack": False},
            }
        ],
    }
    stale_episodes = {"schema": "abyss_machine_self_awareness_episodes_v1", "episodes": []}
    fresh_episodes = {
        "schema": "abyss_machine_self_awareness_episodes_v1",
        "episodes": [
            {
                "episode_id": "saepisode-db-route",
                "affected_spatial_nodes": ["stack_requirement:stack.database-graph.read-route"],
            }
        ],
    }
    refresh_calls: list[str] = []

    def fake_load_latest_json(path, schema, *args, **kwargs):
        if str(path) == str(abyss_machine_module.SELF_AWARENESS_EPISODES_LATEST_PATH):
            return stale_episodes
        if str(path) == str(abyss_machine_module.SELF_AWARENESS_AUTOLINK_LATEST_PATH):
            return {"schema": schema}
        return {"schema": schema}

    def fake_episodes(write_latest=True, *, working_stack_doc=None):
        refresh_calls.append("episodes")
        return fresh_episodes

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_episodes", fake_episodes)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_links_match_stable_identity", lambda _doc: True)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_link_integrity_matrix_complete", lambda _doc: True)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_link_integrity_matches_working_stack", lambda _working, _links: True)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_activation_smoke_needs_refresh", lambda _doc, _entries: False)

    doc = abyss_machine_module.self_awareness_autolink(
        write_latest=False,
        working_stack_doc=working_stack,
        coverage_audit_doc=coverage_audit,
        stack_closure_dossier_doc=stack_closure_dossier,
        activation_smoke_doc={"schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1", "by_service": {}},
    )

    assert refresh_calls
    assert set(refresh_calls) == {"episodes"}
    assert doc["stack_requirement_links_by_requirement"]["stack.database-graph.read-route"]["episode_ids"] == ["saepisode-db-route"]


def test_self_awareness_export_overlay_completes_only_current_export_step(abyss_machine_module) -> None:
    required_steps = [
        "inventory",
        "space",
        "causal_episode",
        "reaction_response_contract",
        "investigation_replay_contract",
        "coverage_row",
        "export",
        "cycle",
        "boundary_policy",
    ]
    proof = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_synthetic_proof_v1",
        "proof_id": "saproof-working-stack-activation-fixture",
        "service": "tts",
        "owner": "abyss-stack",
        "machine_usage_status": "model_root_visible",
        "usage_gap": "fixture gap",
        "working_stack_link_id": "saworklink-tts",
        "proof_status": "proof_incomplete",
        "proof_steps": [
            {
                "step": step,
                "ok": step != "export",
                "evidence_refs": [{"path": f"/tmp/{step}.json"}],
                "details": {},
            }
            for step in required_steps
        ],
        "summary": {"steps": len(required_steps), "ok_steps": len(required_steps) - 1, "failed_steps": ["export"]},
        "evidence_refs": [{"path": "/tmp/proof.json"}],
        "policy": {
            "readmodel_smoke": True,
            "synthetic_scenario_contract": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
        },
    }
    export_entry = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_entry_v1",
        "service": "tts",
        "complete": True,
        "working_stack_link_id": "saworklink-tts",
        "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
    }

    adjusted = abyss_machine_module.self_awareness_export_overlay_working_stack_activation_proof(
        proof,
        {"tts": export_entry},
        generated_at="2026-07-01T00:00:00Z",
    )

    assert adjusted["complete"] is True
    assert adjusted["proof_status"] == "proved_open_activation_gap"
    assert adjusted["summary"]["failed_steps"] == []
    export_step = next(step for step in adjusted["proof_steps"] if step["step"] == "export")
    assert export_step["ok"] is True
    assert export_step["details"]["export_handoff_overlay_applied"] is True


def test_self_awareness_working_stack_dependent_link_readmodels_fresh_ignores_gap_coverage(abyss_machine_module) -> None:
    fresh = {
        "schema": "abyss_machine_self_awareness_working_stack_link_integrity_matrix_v1",
        "summary": {
            "rows": 33,
            "timeline_linked": 33,
            "spatial_linked": 33,
            "context_indexed": 33,
            "episode_required_rows": 9,
            "episode_linked": 9,
            "usage_gap_rows_with_coverage": 0,
        },
    }
    stale = {
        "schema": "abyss_machine_self_awareness_working_stack_link_integrity_matrix_v1",
        "summary": {
            "rows": 33,
            "timeline_linked": 0,
            "spatial_linked": 0,
            "context_indexed": 33,
            "episode_required_rows": 9,
            "episode_linked": 9,
        },
    }

    assert abyss_machine_module.self_awareness_working_stack_dependent_link_readmodels_fresh(fresh) is True
    assert abyss_machine_module.self_awareness_working_stack_dependent_link_readmodels_fresh(stale) is False


def test_self_awareness_dependency_refresh_preserves_supplied_working_stack_snapshot(monkeypatch, abyss_machine_module) -> None:
    working_stack = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        "generated_at": "2026-07-01T00:00:00+00:00",
        "summary": {"organs": 1, "usage_gaps": 0},
        "organs": [
            {
                "service": "alertmanager",
                "machine_usage_status": "active_machine_signal",
                "time_space_context_link": {"link_id": "saworklink-current"},
            }
        ],
    }
    calls: list[tuple[str, bool]] = []
    writes: list[dict] = []

    def fake_write_latest_and_history(data, path, root):
        writes.append({"data": data, "path": path, "root": root})
        return []

    def fake_collect(write_latest=True, synthetic_events=None, *, working_stack_doc=None):
        calls.append(("collect", working_stack_doc is working_stack))
        return {"schema": "abyss_machine_self_awareness_collect_v1", "ok": True, "summary": {"events": 1}}

    def fake_timeline(write_latest=True):
        calls.append(("timeline", True))
        return {"schema": "abyss_machine_self_awareness_timeline_v1", "ok": True, "summary": {"events": 1}, "events": []}

    def fake_spatial_graph(write_latest=True, *, working_stack_doc=None, timeline_doc=None):
        calls.append(("spatial_graph", working_stack_doc is working_stack and timeline_doc is not None))
        return {"schema": "abyss_machine_self_awareness_spatial_graph_v1", "ok": True, "summary": {"nodes": 1}}

    def fake_context(write_latest=True):
        calls.append(("context", True))
        return {"schema": "abyss_machine_self_awareness_context_v1", "ok": True, "summary": {"contexts": 1}}

    def fake_episodes(write_latest=True, *, working_stack_doc=None):
        calls.append(("episodes", working_stack_doc is working_stack))
        return {"schema": "abyss_machine_self_awareness_episodes_v1", "ok": True, "summary": {"episodes": 1}}

    def fail_inventory(*args, **kwargs):
        raise AssertionError("dependency refresh must not resample working-stack after a snapshot is supplied")

    monkeypatch.setattr(abyss_machine_module, "write_latest_and_history", fake_write_latest_and_history)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_collect", fake_collect)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_timeline", fake_timeline)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_spatial_graph", fake_spatial_graph)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_context", fake_context)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_episodes", fake_episodes)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_working_stack_inventory", fail_inventory)

    refresh = abyss_machine_module.self_awareness_refresh_working_stack_dependent_readmodels(working_stack_doc=working_stack)

    assert refresh["schema"] == "abyss_machine_self_awareness_working_stack_dependency_refresh_v1"
    assert refresh["write_errors"] == []
    assert writes and writes[0]["data"] is working_stack
    assert calls == [
        ("collect", True),
        ("timeline", True),
        ("spatial_graph", True),
        ("context", True),
        ("episodes", True),
    ]


def test_self_awareness_objective_coverage_audit_maps_stack_usage_surfaces(monkeypatch, abyss_machine_module) -> None:
    capability_ids = sorted({
        capability_id
        for spec in abyss_machine_module.self_awareness_objective_coverage_specs()
        for capability_id in (spec.get("capabilities") if isinstance(spec.get("capabilities"), list) else [])
    })
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "ok": True,
        "capabilities": [
            {
                "id": capability_id,
                "ok": capability_id != "tempo.trace.backend",
                "owner": "abyss-stack" if capability_id.startswith(("stack.", "tempo.", "grafana", "loki", "prometheus", "alloy", "alertmanager")) else "abyss-machine",
                "evidence_refs": [{"path": f"/var/lib/abyss-machine/self-awareness/capabilities/{capability_id}.json"}],
            }
            for capability_id in capability_ids
        ],
    }
    stack_requirement_ids = [
        "stack.grafana.datasource-read",
        "stack.trace-backend",
        "stack.database-graph.read-route",
        "stack.langchain-api.graph-observability",
    ]
    requirements = {
        "schema": "abyss_machine_self_awareness_requirements_v1",
        "ok": True,
        "summary": {"stack_owned": len(stack_requirement_ids)},
        "requirements": [
            {
                "id": requirement_id,
                "owner": "abyss-stack",
                "status": "open",
                "title": requirement_id,
                "closure_readiness": {
                    "schema": "abyss_machine_self_awareness_requirement_readiness_summary_v1",
                    "coverage_impact": {
                        "schema": "abyss_machine_self_awareness_stack_coverage_impact_v1",
                        "requirement_id": requirement_id,
                        "organ": "fixture-organ-" + requirement_id,
                        "coverage_planes": ["fixture_plane_" + requirement_id.replace(".", "_")],
                        "affected_stack_surfaces": ["fixture-stack-surface"],
                        "affected_machine_surfaces": ["fixture-machine-surface"],
                        "blocks_stack_usage_requirements": ["fixture-stack-usage"],
                        "closure_value": "fixture closure value",
                        "proof_commands": ["abyss-machine self-awareness coverage-audit --json"],
                        "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
                    },
                },
                "blocking_check_keys": ["fixture_blocker"],
                "runbook_candidate_id": "stack-runbook-" + requirement_id.replace(".", "-"),
            }
            for requirement_id in stack_requirement_ids
        ],
        "stack_handoff": [{"id": requirement_id} for requirement_id in stack_requirement_ids],
    }
    probes = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "ok": True,
        "probes": [{"id": requirement_id, "requirement_id": requirement_id, "status": "open"} for requirement_id in stack_requirement_ids],
    }
    chain = {
        "synthetic_request": True,
        "capability_inventory": True,
        "requirement_probes": True,
            "stack_closure_dossier": True,
            "failure_matrix": True,
            "working_stack": True,
            "signal_fabric": True,
        "query": True,
        "correlation": True,
        "timeline": True,
        "spatial_graph": True,
        "causal_episode": True,
        "alert": True,
        "warm_e2b_worker": True,
        "rag_memory": True,
        "nervous_freshness": True,
        "langgraph_investigation": True,
        "replay": True,
        "resident_cognitive_replay": True,
        "stack_handoff_readiness_replay": True,
        "semantic_brief": True,
        "reaction_candidate": True,
        "governed_response": True,
        "body_trace": True,
        "entity_event_document": True,
        "machine_bridges": True,
        "export": True,
        "resident_cognitive_export": True,
    }

    def fixture_closure_acceptance(requirement_id: str) -> dict:
        requirement = {
            "id": requirement_id,
            "owner": "abyss-stack",
            "status": "open",
            "expected_shape": {"fixture": requirement_id},
        }
        acceptance_contract = abyss_machine_module.self_awareness_requirement_acceptance_contract(requirement)
        compat_contract = abyss_machine_module.self_awareness_stack_requirement_compat_contract(
            requirement,
            acceptance_contract=acceptance_contract,
            readiness={
                "status": "open",
                "blocking_check_keys": ["fixture_blocker"],
                "missing_checks": [{"key": "fixture_blocker", "level": "open", "message": "fixture open blocker"}],
                "dependency_requirement_ids": [],
                "verifier_commands": ["abyss-machine self-awareness validate --json"],
            },
            current_state={"fixture": requirement_id},
            coverage_impact=abyss_machine_module.self_awareness_stack_requirement_coverage_impact(requirement_id),
            dependency_requirement_ids=[],
        )
        return abyss_machine_module.self_awareness_stack_requirement_closure_acceptance(
            {
                "requirement_id": requirement_id,
                "owner": "abyss-stack",
                "status": "open",
                "closed_by_current_probe": False,
                "probe_kind": compat_contract["surface_kind"],
                "current_state": {"fixture": requirement_id},
                "current_state_digest": "d" * 24,
                "missing_checks": [{"key": "fixture_blocker", "level": "open", "message": "fixture open blocker"}],
                "fulfilled_checks": [{"key": "acceptance_contract_probeable"}],
                "blocking_check_keys": ["fixture_blocker"],
                "depends_on_requirement_ids": [],
                "unblocks_requirement_ids": [],
                "success_predicates": ["fixture closure success predicate"],
                "verifier_commands": ["abyss-machine self-awareness validate --json"],
                "acceptance_contract": acceptance_contract,
                "compat_contract": compat_contract,
                "coverage_impact": abyss_machine_module.self_awareness_stack_requirement_coverage_impact(requirement_id),
                "safe_next_action": {"requires_human_approval": True, "host_layer_mutates_stack": False, "executes_commands": False},
                "evidence_refs": [{"path": f"/var/lib/abyss-machine/self-awareness/requirements/{requirement_id}.json"}],
            },
            "2026-01-01T00:00:00+00:00",
        )

    def fake_load_latest_json(path, schema):
        if schema == "abyss_machine_self_awareness_capabilities_v1":
            return capabilities
        if schema == "abyss_machine_self_awareness_requirements_v1":
            return requirements
        if schema == "abyss_machine_self_awareness_requirement_probes_v1":
            return probes
        if schema == "abyss_machine_self_awareness_stack_closure_dossier_v1":
            packets = [fixture_closure_acceptance(requirement_id) for requirement_id in stack_requirement_ids]
            return {
                "schema": schema,
                "ok": True,
                "status": "open_requirements",
                "summary": {
                    "probes": len(stack_requirement_ids),
                    "open_stack_requirements": len(stack_requirement_ids),
                    "closure_acceptance_packets": len(packets),
                    "closure_acceptance_packets_complete": len(packets),
                    "stack_requirement_compat_requirements": len(packets),
                    "working_stack_activation_entries": 0,
                    "open_working_stack_activation_gaps": 0,
                    "full_stack_potential_covered": False,
                },
                "entries": [
                    {"requirement_id": requirement_id, "closure_acceptance": packet}
                    for requirement_id, packet in zip(stack_requirement_ids, packets)
                ],
                "closure_acceptance_matrix": {
                    "schema": "abyss_machine_self_awareness_stack_requirement_closure_acceptance_matrix_v1",
                    "ok": True,
                    "packets": packets,
                    "packet_by_requirement": {packet["requirement_id"]: packet for packet in packets},
                    "summary": {"packets": len(packets), "complete": len(packets), "compat_requirements": len(packets)},
                },
                "working_stack_activation_dossier": {
                    "schema": "abyss_machine_self_awareness_working_stack_activation_dossier_v1",
                    "summary": {"entries": 0},
                    "entries": [],
                    "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
                },
            }
        if schema == "abyss_machine_self_awareness_cycle_v1":
            return {"schema": schema, "ok": True, "status": "covered", "summary": {"chain_passed": len(chain), "chain_total": len(chain), "e2e_lineage_ok": True}, "cycle_chain": chain}
        if schema == "abyss_machine_self_awareness_export_v1":
            return {"schema": schema, "ok": True, "summary": {"missing": 0}}
        if schema == "abyss_machine_self_awareness_failure_matrix_v1":
            return {"schema": schema, "ok": True, "summary": {"missing_required": []}, "rows": []}
        if schema == "abyss_machine_self_awareness_validate_v1":
            return {"schema": schema, "ok": True, "summary": {"status": "ok", "fails": 0, "warnings": 0, "checks": 113}}
        return {"schema": schema, "ok": True, "summary": {}}

    def fake_artifact_ref(name, path, schema):
        return {
            "name": name,
            "path": f"/var/lib/abyss-machine/self-awareness/{name}/latest.json",
            "history_path": f"/var/lib/abyss-machine/self-awareness/{name}/YYYY/MM/YYYY-MM-DD.jsonl",
            "exists": True,
            "schema": schema,
            "expected_schema": schema,
            "schema_ok": True,
            "ok": True,
            "status": "ok",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {"fixture": name},
            "sha256": "c" * 64,
        }

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_latest_artifact_ref", fake_artifact_ref)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_resident_cognitive_cycle_chain_overlay",
        lambda cycle_chain, **kwargs: (cycle_chain, kwargs.get("replay_doc") or {}, kwargs.get("export_doc") or {}),
    )

    audit = abyss_machine_module.self_awareness_objective_coverage_audit(write_latest=False)
    row_by_id = {row["id"]: row for row in audit["rows"]}

    assert audit["schema"] == "abyss_machine_self_awareness_objective_coverage_audit_v1"
    assert audit["ok"] is True
    assert audit["status"] == "covered_with_stack_blockers"
    assert audit["summary"]["incomplete"] == 0
    assert audit["summary"]["blocked_stack_owned"] >= 4
    assert audit["status"] == "covered_with_stack_blockers"
    assert audit["summary"]["working_stack_gap_rows"] == len(audit.get("working_stack_gap_rows", []))
    assert set(stack_requirement_ids) == set(audit["open_stack_requirement_ids"])
    assert audit["summary"]["blocked_coverage_planes"]
    assert audit["summary"]["objective_coverage_planes"]
    assert audit["summary"]["covered_coverage_planes"]
    assert {"prometheus_promql", "trace_backend", "warm_e2b_resident_worker", "e2e_probe_export_replay", "owner_boundary"}.issubset(row_by_id)
    assert "metrics_query" in row_by_id["prometheus_promql"]["objective_coverage_planes"]
    assert row_by_id["prometheus_promql"]["covered_coverage_planes"] == row_by_id["prometheus_promql"]["objective_coverage_planes"]
    assert row_by_id["prometheus_promql"]["coverage_planes"] == row_by_id["prometheus_promql"]["objective_coverage_planes"]
    assert row_by_id["trace_backend"]["status"] == "blocked_stack_owned"
    assert row_by_id["trace_backend"]["blocked_by_requirement_ids"] == ["stack.trace-backend"]
    assert row_by_id["trace_backend"]["open_stack_requirement_ids"] == row_by_id["trace_backend"]["blocked_by_requirement_ids"]
    assert row_by_id["trace_backend"]["blocking_check_keys"] == ["fixture_blocker"]
    assert row_by_id["trace_backend"]["coverage_impacts"][0]["requirement_id"] == "stack.trace-backend"
    assert row_by_id["trace_backend"]["objective_coverage_planes"]
    assert row_by_id["trace_backend"]["covered_coverage_planes"] == []
    assert row_by_id["trace_backend"]["coverage_planes"] == row_by_id["trace_backend"]["blocked_coverage_planes"]
    assert "fixture_plane_stack_trace-backend" in row_by_id["trace_backend"]["blocked_coverage_planes"]
    assert abyss_machine_module.self_awareness_coverage_audit_blocker_linkage_issues(audit) == []
    assert row_by_id["warm_e2b_resident_worker"]["status"] == "covered"
    assert "resident_worker" in row_by_id["warm_e2b_resident_worker"]["covered_coverage_planes"]
    assert row_by_id["owner_boundary"]["policy"]["host_layer_mutates_stack"] is False
    assert all(row["schema"] == "abyss_machine_self_awareness_objective_coverage_row_v1" for row in audit["rows"])
    assert all(row["evidence_refs"] for row in audit["rows"])
    assert all(row["objective_coverage_planes"] for row in audit["rows"])


def test_self_awareness_objective_coverage_audit_does_not_reopen_absent_capability_covered_requirements(
    monkeypatch,
    abyss_machine_module,
) -> None:
    capability_ids = sorted({
        capability_id
        for spec in abyss_machine_module.self_awareness_objective_coverage_specs()
        for capability_id in (spec.get("capabilities") if isinstance(spec.get("capabilities"), list) else [])
    })
    chain = {
        str(chain_key): True
        for spec in abyss_machine_module.self_awareness_objective_coverage_specs()
        for chain_key in (spec.get("chain_keys") if isinstance(spec.get("chain_keys"), list) else [])
    }
    capabilities = {
        "schema": "abyss_machine_self_awareness_capabilities_v1",
        "ok": True,
        "capabilities": [
            {
                "id": capability_id,
                "ok": True,
                "owner": "abyss-stack" if capability_id.startswith(("stack.", "tempo.", "grafana", "loki", "prometheus", "alloy", "alertmanager")) else "abyss-machine",
                "evidence_refs": [{"path": f"/var/lib/abyss-machine/self-awareness/capabilities/{capability_id}.json"}],
            }
            for capability_id in capability_ids
        ],
    }
    closed_requirement_ids = [
        "stack.grafana.datasource-read",
        "stack.database-graph.read-route",
    ]
    requirements = {
        "schema": "abyss_machine_self_awareness_requirements_v1",
        "ok": True,
        "status": "satisfied",
        "summary": {
            "stack_owned": len(closed_requirement_ids),
            "open_stack_requirements": 0,
            "closed_stack_requirements": len(closed_requirement_ids),
        },
        "requirements": [
            {
                "id": requirement_id,
                "owner": "abyss-stack",
                "status": "closed",
                "closed_by_current_probe": True,
                "title": requirement_id,
                "blocking_check_keys": [],
                "coverage_impact": {
                    "schema": "abyss_machine_self_awareness_stack_coverage_impact_v1",
                    "requirement_id": requirement_id,
                    "organ": "fixture-organ-" + requirement_id,
                    "coverage_planes": ["fixture_plane_" + requirement_id.replace(".", "_")],
                    "affected_stack_surfaces": [],
                    "affected_machine_surfaces": [],
                    "blocks_stack_usage_requirements": [],
                    "closure_value": "fixture closed by current stack route",
                    "proof_commands": ["abyss-machine self-awareness requirement-probes --json"],
                    "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
                },
                "closure_readiness": {
                    "schema": "abyss_machine_self_awareness_requirement_readiness_summary_v1",
                    "coverage_impact": {
                        "schema": "abyss_machine_self_awareness_stack_coverage_impact_v1",
                        "requirement_id": requirement_id,
                        "organ": "fixture-organ-" + requirement_id,
                        "coverage_planes": ["fixture_plane_" + requirement_id.replace(".", "_")],
                    },
                },
                "runbook_candidate_id": "stack-runbook-" + requirement_id.replace(".", "-"),
            }
            for requirement_id in closed_requirement_ids
        ],
        "stack_handoff": [
            {"id": requirement_id, "status": "closed", "closed_by_current_probe": True}
            for requirement_id in closed_requirement_ids
        ],
        "closed_stack_ids": closed_requirement_ids,
        "open_stack_ids": [],
    }
    probes = {
        "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        "ok": True,
        "summary": {"probes": len(closed_requirement_ids), "open": 0, "closed": len(closed_requirement_ids)},
        "probes": [
            {
                "id": requirement_id,
                "requirement_id": requirement_id,
                "status": "closed",
                "closed_by_current_probe": True,
            }
            for requirement_id in closed_requirement_ids
        ],
    }

    def fake_load_latest_json(path, schema):
        if schema == "abyss_machine_self_awareness_capabilities_v1":
            return capabilities
        if schema == "abyss_machine_self_awareness_requirements_v1":
            return requirements
        if schema == "abyss_machine_self_awareness_requirement_probes_v1":
            return probes
        if schema == "abyss_machine_self_awareness_stack_closure_dossier_v1":
            return {
                "schema": schema,
                "ok": True,
                "status": "closed",
                "summary": {
                    "open_stack_requirements": 0,
                    "closure_acceptance_packets": len(closed_requirement_ids),
                    "closure_acceptance_packets_complete": len(closed_requirement_ids),
                    "stack_requirement_compat_requirements": len(closed_requirement_ids),
                    "working_stack_activation_entries": 0,
                    "open_working_stack_activation_gaps": 0,
                    "full_stack_potential_covered": False,
                },
                "entries": [{"requirement_id": requirement_id, "status": "closed"} for requirement_id in closed_requirement_ids],
                "working_stack_activation_dossier": {
                    "schema": "abyss_machine_self_awareness_working_stack_activation_dossier_v1",
                    "summary": {"entries": 0},
                    "entries": [],
                    "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
                },
            }
        if schema == "abyss_machine_self_awareness_cycle_v1":
            return {"schema": schema, "ok": True, "status": "covered", "summary": {"chain_passed": len(chain), "chain_total": len(chain), "e2e_lineage_ok": True}, "cycle_chain": chain}
        if schema == "abyss_machine_self_awareness_working_stack_inventory_v1":
            return {"schema": schema, "ok": True, "summary": {"organs": 0, "usage_gaps": 0, "full_stack_potential_covered": False}, "organs": []}
        if schema == "abyss_machine_self_awareness_export_v1":
            return {"schema": schema, "ok": True, "summary": {"missing": 0}}
        if schema == "abyss_machine_self_awareness_failure_matrix_v1":
            return {"schema": schema, "ok": True, "summary": {"missing_required": []}, "rows": []}
        if schema == "abyss_machine_self_awareness_validate_v1":
            return {"schema": schema, "ok": True, "summary": {"status": "ok", "fails": 0, "warnings": 0, "checks": 113}}
        return {"schema": schema, "ok": True, "summary": {}, "rows": []}

    def fake_artifact_ref(name, path, schema):
        return {
            "name": name,
            "path": f"/var/lib/abyss-machine/self-awareness/{name}/latest.json",
            "history_path": f"/var/lib/abyss-machine/self-awareness/{name}/YYYY/MM/YYYY-MM-DD.jsonl",
            "exists": True,
            "schema": schema,
            "expected_schema": schema,
            "schema_ok": True,
            "ok": True,
            "status": "ok",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "summary": {"fixture": name},
            "sha256": "d" * 64,
        }

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_latest_artifact_ref", fake_artifact_ref)
    monkeypatch.setattr(
        abyss_machine_module,
        "self_awareness_resident_cognitive_cycle_chain_overlay",
        lambda cycle_chain, **kwargs: (cycle_chain, kwargs.get("replay_doc") or {}, kwargs.get("export_doc") or {}),
    )

    audit = abyss_machine_module.self_awareness_objective_coverage_audit(write_latest=False)
    row_by_id = {row["id"]: row for row in audit["rows"]}

    assert audit["ok"] is True
    assert audit["status"] == "covered"
    assert audit["summary"]["incomplete"] == 0
    assert audit["summary"]["blocked_stack_owned"] == 0
    assert audit["summary"]["open_stack_requirements"] == 0
    assert row_by_id["trace_backend"]["status"] == "covered"
    assert row_by_id["trace_backend"]["missing_requirements"] == []
    assert row_by_id["trace_backend"]["requirements"][0]["id"] == "stack.trace-backend"
    assert row_by_id["trace_backend"]["requirements"][0]["present"] is False
    assert row_by_id["trace_backend"]["requirements"][0]["absence_covered_by_current_capability"] is True
    assert row_by_id["trace_backend"]["requirements"][0]["requirement_missing_blocks_coverage"] is False
    assert row_by_id["trace_backend"]["requirements"][0]["coverage_capability_ids"] == ["tempo.trace.backend"]
    assert row_by_id["langchain_langgraph_stack"]["status"] == "covered"
    assert row_by_id["langchain_langgraph_stack"]["missing_requirements"] == []
    assert row_by_id["langchain_langgraph_stack"]["requirements"][0]["present"] is False
    assert row_by_id["langchain_langgraph_stack"]["requirements"][0]["absence_covered_by_current_capability"] is True
    assert row_by_id["langchain_langgraph_stack"]["requirements"][0]["requirement_missing_blocks_coverage"] is False
    assert row_by_id["langchain_langgraph_stack"]["requirements"][0]["coverage_capability_ids"] == [
        "stack.langchain-api.health-openapi",
        "langgraph.investigator.runtime",
    ]


def test_self_awareness_status_surfaces_autolink_and_open_stack_potential(abyss_machine_module, monkeypatch) -> None:
    working_stack_link_id = "saworklink-status-test"

    def fake_load_latest_json(path, schema):
        base = {"schema": schema, "ok": True, "generated_at": "2026-01-01T00:00:00+00:00", "summary": {}}
        if schema == "abyss_machine_self_awareness_requirements_v1":
            return {
                **base,
                "summary": {"requirements": 2},
                "requirements": [
                    {
                        "id": "stack.trace-backend",
                        "title": "Trace backend read route",
                        "owner": "abyss-stack",
                        "blocking_check_keys": ["trace_backend_read_route"],
                        "coverage_impact": {"coverage_planes": ["trace_backend", "correlation_trace"]},
                        "runbook_candidate_id": "runbook-stack.trace-backend",
                    },
                    {
                        "id": "stack.grafana.datasource-read",
                        "title": "Grafana datasource read route",
                        "owner": "abyss-stack",
                        "blocking_check_keys": ["grafana_datasource_read"],
                        "coverage_impact": {"coverage_planes": ["grafana_datasource", "dashboard_context"]},
                        "runbook_candidate_id": "runbook-stack.grafana.datasource-read",
                    },
                ],
            }
        if schema == "abyss_machine_self_awareness_requirement_probes_v1":
            return {**base, "summary": {"probes": 2, "open": 2}}
        if schema == "abyss_machine_self_awareness_stack_closure_dossier_v1":
            return {
                **base,
                "summary": {
                    "open_stack_requirements": 2,
                    "full_stack_potential_covered": False,
                },
                "entries": [
                    {
                        "requirement_id": "stack.trace-backend",
                        "title": "Trace backend read route",
                        "blocking_check_keys": ["trace_backend_read_route"],
                        "coverage_impact": {"coverage_planes": ["trace_backend", "correlation_trace"]},
                        "closure_readiness": {"missing_checks": ["trace_backend_query_smoke"]},
                        "closure_acceptance": {
                            "acceptance_id": "accept-stack.trace-backend",
                            "stack_compat_requirement": {"requirement_id": "stack.trace-backend"},
                        },
                        "runbook_candidate_id": "runbook-stack.trace-backend",
                        "verifier_commands": [["abyss-machine", "self-awareness", "probe", "--json"]],
                        "safe_next_action": {
                            "requires_human_approval": True,
                            "host_layer_mutates_stack": False,
                            "executes_commands": False,
                        },
                        "evidence_refs": ["latest:self-awareness/stack-closure-dossier"],
                    },
                    {
                        "requirement_id": "stack.grafana.datasource-read",
                        "title": "Grafana datasource read route",
                        "blocking_check_keys": ["grafana_datasource_read"],
                        "coverage_impact": {"coverage_planes": ["grafana_datasource", "dashboard_context"]},
                        "closure_readiness": {"missing_checks": ["grafana_datasource_smoke"]},
                        "closure_acceptance": {
                            "acceptance_id": "accept-stack.grafana.datasource-read",
                            "stack_compat_requirement": {"requirement_id": "stack.grafana.datasource-read"},
                        },
                        "runbook_candidate_id": "runbook-stack.grafana.datasource-read",
                        "verifier_commands": [["abyss-machine", "self-awareness", "requirements", "--json"]],
                        "safe_next_action": {
                            "requires_human_approval": True,
                            "host_layer_mutates_stack": False,
                            "executes_commands": False,
                        },
                        "evidence_refs": ["latest:self-awareness/stack-closure-dossier"],
                    },
                ],
                "working_stack_activation_dossier": {
                    "entries": [
                        {
                            "service": "aoa-browser",
                            "activation_kind": "stack_tool_runtime_smoke_gap",
                            "machine_usage_status": "tool_runtime_degraded",
                            "usage_gap": "runtime smoke failed",
                            "working_stack_link_id": working_stack_link_id,
                            "runtime": {
                                "present": True,
                                "running": True,
                                "container": "aoa-browser",
                                "health": "healthy",
                                "state": "running",
                                "status": "Up 1 minute (healthy)",
                            },
                            "declared": {"present": True, "modules": ["51-browser-tools.yml"]},
                            "endpoint_ok": True,
                            "deep_usage_proven": False,
                            "failed_probe_names": ["playwright-chromium-launch"],
                            "ok_probe_names": ["health", "private-host-guard"],
                            "closure_blocker_keys": ["playwright_chromium_launch"],
                            "missing_checks": ["browser_launch_smoke"],
                            "verifier_commands": [["abyss-machine", "self-awareness", "activation-smoke", "--json"]],
                            "safe_next_action": {
                                "requires_human_approval": True,
                                "host_layer_mutates_stack": False,
                                "executes_commands": False,
                            },
                        },
                    ],
                },
            }
        if schema == "abyss_machine_self_awareness_working_stack_inventory_v1":
            return {
                **base,
                "summary": {
                    "organs": 2,
                    "usage_gaps": 1,
                    "full_stack_potential_covered": False,
                },
            }
        if schema == "abyss_machine_self_awareness_objective_coverage_audit_v1":
            return {
                **base,
                "summary": {
                    "blocked_stack_owned": 2,
                    "incomplete": 0,
                    "full_stack_potential_covered": False,
                },
            }
        if schema == "abyss_machine_self_awareness_working_stack_activation_smoke_v1":
            return {
                **base,
                "summary": {
                    "rows": 1,
                    "rows_ok": 1,
                    "open_activation_gaps": 1,
                    "full_stack_potential_covered": False,
                },
                "rows": [
                    {
                        "service": "aoa-browser",
                        "machine_usage_status": "tool_runtime_degraded",
                        "episode_id": "saepisode-working-stack-gap-aoa-browser",
                        "complete": True,
                        "investigation": {
                            "ok": True,
                            "thread_id": "sathread-aoa-browser",
                            "selected_episode_matches": True,
                        },
                        "replay": {
                            "ok": True,
                            "thread_id": "sathread-aoa-browser",
                            "thread_matches": True,
                            "working_stack_gap_replayable": True,
                        },
                    }
                ],
            }
        if schema == "abyss_machine_self_awareness_autolink_v1":
            return {
                **base,
                "state_digest": "f" * 32,
                "summary": {
                    "organ_links": 2,
                    "organ_links_complete": 2,
                    "stack_requirement_links": 2,
                    "stack_requirement_links_complete": 2,
                    "working_stack_usage_gaps": 1,
                    "open_stack_requirements": 2,
                    "synthetic_scenarios": 1,
                    "synthetic_scenarios_complete": 1,
                    "service_ids": ["prometheus", "aoa-browser"],
                    "requirement_ids": ["stack.trace-backend", "stack.grafana.datasource-read"],
                    "state_changed": False,
                    "full_stack_potential_covered": False,
                },
                "organ_links": [
                    {"service": "prometheus", "usage_gap": None},
                    {
                        "service": "aoa-browser",
                        "owner": "abyss-stack",
                        "machine_usage_status": "tool_runtime_degraded",
                        "usage_gap": "runtime smoke failed",
                        "working_stack_link_id": working_stack_link_id,
                        "event_id": "saevt-aoa-browser",
                            "episode_ids": ["saepisode-working-stack-gap-aoa-browser"],
                        "activation_smoke": {
                            "complete": True,
                            "thread_id": "sathread-aoa-browser",
                            "working_stack_link_id": working_stack_link_id,
                        },
                        "evidence_refs": ["latest:self-awareness/autolink"],
                    },
                ],
                "stack_requirement_links": [
                    {
                        "requirement_id": "stack.trace-backend",
                        "owner": "abyss-stack",
                        "automatic_link_state": "open_stack_blocker",
                        "episode_ids": ["saepisode-trace-backend"],
                        "evidence_refs": ["latest:self-awareness/autolink"],
                    },
                    {
                        "requirement_id": "stack.grafana.datasource-read",
                        "owner": "abyss-stack",
                        "automatic_link_state": "open_stack_blocker",
                        "episode_ids": ["saepisode-grafana-datasource"],
                        "evidence_refs": ["latest:self-awareness/autolink"],
                    },
                ],
            }
        if schema == "abyss_machine_self_awareness_validate_v1":
            return {**base, "summary": {"status": "ok", "checks": 135, "fails": 0, "warnings": 0}}
        if schema == "abyss_machine_self_awareness_completion_audit_v1":
            return {
                **base,
                "ok": False,
                "status": "incomplete",
                "summary": {
                    "stack_usage_closure_complete": False,
                    "validator_green_but_stack_usage_incomplete": True,
                    "completion_actions": 3,
                    "top_completion_action_id": "stack-requirement:stack.trace-backend",
                    "top_completion_priority_class": "critical_trace_join",
                },
                "action_backlog": {
                    "summary": {
                        "drilldowns": 3,
                        "drilldowns_complete": 3,
                        "top_action_drilldown_id": "sacompletiondrill-trace",
                        "top_action_drilldown_complete": True,
                    }
                },
                "completion_route_map": {
                    "summary": {
                        "routes": 6,
                        "next_route_id": "observability.trace_join_backbone",
                        "next_route_path": "observability/trace/join-backbone",
                        "next_route_action_ids": ["stack-requirement:stack.trace-backend"],
                    }
                },
                "entity_event_document_map": {
                    "summary": {
                        "entities": 4,
                        "events": 4,
                        "documents": 15,
                        "stack_organs": 1,
                        "machine_bridges": 1,
                        "body_surfaces": 2,
                        "automation_ready": True,
                    }
                },
            }
        return base

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)

    payload = abyss_machine_module.self_awareness_status()
    summary = payload["summary"]

    assert payload["schema"] == "abyss_machine_self_awareness_status_v1"
    assert payload["ok"] is True
    assert payload["status"] == "ready_with_open_stack_usage"
    assert summary["readmodel_status"] == "ready"
    assert summary["open_stack_requirements"] == 2
    assert summary["working_stack_usage_gaps"] == 1
    assert summary["coverage_audit_ok"] is True
    assert summary["coverage_blocked_stack_owned"] == 2
    assert summary["activation_smoke_ok"] is True
    assert summary["activation_smoke_rows"] == 1
    assert summary["activation_smoke_rows_ok"] == 1
    assert summary["activation_smoke_open_activation_gaps"] == 1
    assert summary["autolink_organ_links"] == summary["autolink_organ_links_complete"] == 2
    assert summary["autolink_stack_requirement_links"] == summary["autolink_stack_requirement_links_complete"] == 2
    assert summary["autolink_stack_requirement_links"] == summary["open_stack_requirements"]
    assert summary["autolink_synthetic_scenarios"] == summary["autolink_synthetic_scenarios_complete"] == 1
    assert summary["autolink_state_digest"] == "f" * 32
    assert summary["autolink_service_ids"] == ["prometheus", "aoa-browser"]
    assert summary["open_potential_services"] == ["aoa-browser"]
    assert summary["open_stack_requirement_ids"] == ["stack.trace-backend", "stack.grafana.datasource-read"]
    assert payload["open_potential"]["services"] == 1
    assert payload["open_potential"]["activation_gap_routes"] == 1
    open_potential = payload["open_potential"]["rows"][0]
    assert open_potential["service"] == "aoa-browser"
    assert open_potential["working_stack_link_id"] == working_stack_link_id
    assert open_potential["activation_smoke"]["link_matches_current"] is True
    assert open_potential["activation_gap_classification"] == "running_functional_smoke_failed"
    assert open_potential["activation_gap_route"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_gap_route_v1"
    assert open_potential["activation_gap_route"]["complete"] is True
    assert open_potential["activation_gap_route"]["service"] == "aoa-browser"
    assert open_potential["activation_gap_route"]["classification"] == "running_functional_smoke_failed"
    assert open_potential["activation_gap_route"]["current_state"]["runtime"]["running"] is True
    assert open_potential["activation_gap_route"]["current_state"]["endpoint"]["failed_probe_names"] == ["playwright-chromium-launch"]
    assert open_potential["activation_gap_route"]["activation_smoke"]["working_stack_gap_replayable"] is True
    assert open_potential["activation_gap_route"]["policy"]["host_layer_mutates_stack"] is False
    assert open_potential["closure_blocker_keys"] == ["playwright_chromium_launch"]
    assert open_potential["missing_checks"] == ["browser_launch_smoke"]
    assert open_potential["verifier_commands"]
    assert open_potential["safe_next_action"]["requires_human_approval"] is True
    assert open_potential["policy"]["host_layer_mutates_stack"] is False
    assert payload["open_potential"]["policy"]["host_layer_mutates_stack"] is False
    assert payload["open_stack_requirements"]["requirements"] == 2
    open_requirements = {row["requirement_id"]: row for row in payload["open_stack_requirements"]["rows"]}
    assert set(open_requirements) == {"stack.trace-backend", "stack.grafana.datasource-read"}
    assert open_requirements["stack.trace-backend"]["coverage_planes"] == ["trace_backend", "correlation_trace"]
    assert open_requirements["stack.trace-backend"]["verifier_commands"]
    assert open_requirements["stack.trace-backend"]["safe_next_action"]["requires_human_approval"] is True
    assert all(row["policy"]["host_layer_mutates_stack"] is False for row in open_requirements.values())
    assert payload["open_stack_requirements"]["policy"]["host_layer_mutates_stack"] is False
    assert payload["latest"]["coverage_audit"]["ok"] is True
    assert payload["latest"]["activation_smoke"]["ok"] is True
    assert payload["latest"]["completion_audit"]["schema"] == "abyss_machine_self_awareness_completion_audit_v1"
    assert summary["completion_audit_ok"] is False
    assert summary["stack_usage_closure_complete"] is False
    assert summary["validator_green_but_stack_usage_incomplete"] is True
    assert summary["completion_actions"] == 3
    assert summary["top_completion_action_id"] == "stack-requirement:stack.trace-backend"
    assert summary["top_completion_priority_class"] == "critical_trace_join"
    assert summary["completion_drilldowns"] == 3
    assert summary["completion_drilldowns_complete"] == 3
    assert summary["top_completion_drilldown_id"] == "sacompletiondrill-trace"
    assert summary["top_completion_drilldown_complete"] is True
    assert summary["completion_routes"] == 6
    assert summary["next_completion_route_id"] == "observability.trace_join_backbone"
    assert summary["next_completion_route_path"] == "observability/trace/join-backbone"
    assert summary["next_completion_route_action_ids"] == ["stack-requirement:stack.trace-backend"]
    assert summary["entity_event_document_entities"] == 4
    assert summary["entity_event_document_events"] == 4
    assert summary["entity_event_document_documents"] == 15
    assert summary["entity_event_document_stack_organs"] == 1
    assert summary["entity_event_document_machine_bridges"] == 1
    assert summary["entity_event_document_body_surfaces"] == 2
    assert summary["entity_event_document_automation_ready"] is True


def test_self_awareness_status_separates_stack_completion_from_body_watch(abyss_machine_module, monkeypatch) -> None:
    prefix = abyss_machine_module.SCHEMA_PREFIX

    def fake_load_latest_json(path, schema):  # noqa: ANN001
        base = {"schema": schema, "ok": True, "generated_at": "2026-01-01T00:00:00+00:00", "summary": {}}
        if schema == f"{prefix}_self_awareness_validate_v1":
            return {**base, "summary": {"status": "ok", "checks": 153, "fails": 0, "warnings": 0}}
        if schema == f"{prefix}_self_awareness_completion_audit_v1":
            return {
                **base,
                "status": "complete",
                "summary": {
                    "stack_usage_closure_complete": True,
                    "validator_green_but_stack_usage_incomplete": False,
                    "completion_actions": 0,
                },
            }
        if schema == f"{prefix}_heartbeat_pulse_v1":
            return {**base, "status": "watch", "summary": {"status": "watch", "reaction_candidates": 2, "response_routes": 2, "active_changes": 1}}
        if schema == f"{prefix}_reactions_status_v1":
            return {**base, "status": "watch", "summary": {"status": "watch", "candidates": 2, "by_category": {"backup": 1, "stack-bridge": 1}}}
        if schema == f"{prefix}_responses_status_v1":
            return {**base, "status": "watch", "summary": {"status": "watch", "routes": 2, "by_category": {"backup": 1, "stack-bridge": 1}}}
        if schema == f"{prefix}_doctor_v1":
            return {**base, "summary": {"status": "warn", "warnings": 2, "fails": 0}}
        if schema == f"{prefix}_topology_validate_v1":
            return {**base, "summary": {"status": "warn", "warnings": 1, "fails": 0}}
        if schema == f"{prefix}_stack_bridge_validate_v1":
            return {**base, "summary": {"status": "warn", "warnings": 1, "fails": 0}}
        if schema == f"{prefix}_changes_index_v1":
            return {
                **base,
                "summary": {"active_records": 1},
                "active": [{"id": abyss_machine_module.ABYSSVAULT_BACKUP_PLANE_CHANGE_ID, "status": "active"}],
            }
        if schema == f"{prefix}_nervous_brief_v1":
            return {**base, "readiness": {"status": "degraded", "index_fresh": False, "semantic_stale": True}}
        if schema == "abyss_backup_latest_v1":
            return {
                **base,
                "vault_mounted": False,
                "restic_binary_exists": False,
                "restic_repo_initialized": False,
                "privileged_install": {
                    "etc_policy_exists": True,
                    "usr_local_command_exists": True,
                    "system_timer_exists": True,
                    "sessions_timer_exists": True,
                    "sessions_checksum_timer_exists": True,
                },
            }
        return base

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest_json)

    payload = abyss_machine_module.self_awareness_status()
    summary = payload["summary"]

    assert payload["status"] == "watch"
    assert summary["stack_usage_status"] == "complete"
    assert summary["stack_usage_closure_complete"] is True
    assert summary["body_status"] == "watch"
    assert summary["body_closure_complete"] is False
    assert summary["body_open_routes"] == 2
    assert summary["body_watch_sources"] >= 1
    assert payload["body_closure"]["summary"]["backup_blockers"] == [
        "vault_not_mounted",
        "restic_binary_missing",
        "restic_repo_not_initialized",
    ]
    assert payload["body_closure"]["policy"]["separates_stack_usage_from_body_closure"] is True


def test_self_awareness_completion_audit_keeps_body_watch_open(abyss_machine_module, monkeypatch) -> None:
    prefix = abyss_machine_module.SCHEMA_PREFIX
    body_closure = {
        "schema": f"{prefix}_self_awareness_body_closure_v1",
        "ok": True,
        "status": "watch",
        "complete": False,
        "summary": {
            "watch_sources": 3,
            "reaction_candidates": 2,
            "response_routes": 2,
            "doctor_warnings": 1,
            "doctor_fails": 0,
            "topology_warnings": 1,
            "topology_fails": 0,
            "stack_bridge_warnings": 1,
            "stack_bridge_fails": 0,
            "active_changes": 1,
            "nervous_status": "degraded",
            "backup_blockers": ["vault_not_mounted"],
        },
        "policy": {"separates_stack_usage_from_body_closure": True},
    }
    status_doc = {
        "schema": f"{prefix}_self_awareness_status_v1",
        "ok": True,
        "status": "watch",
        "summary": {
            "stack_usage_status": "complete",
            "stack_usage_closure_complete": True,
            "full_stack_potential_covered": True,
            "open_stack_requirements": 0,
            "requirement_probes_open": 0,
            "working_stack_usage_gaps": 0,
            "body_status": "watch",
            "body_closure_complete": False,
            "body_open_routes": 2,
            "body_watch_sources": 3,
        },
        "open_stack_requirements": {"rows": [], "policy": {"host_layer_mutates_stack": False}},
        "open_potential": {"rows": [], "policy": {"host_layer_mutates_stack": False}},
        "body_closure": body_closure,
    }

    def fake_artifact_ref(name, path, schema):  # noqa: ANN001
        return {
            "schema": f"{prefix}_self_awareness_latest_artifact_ref_v1",
            "name": name,
            "path": str(path),
            "expected_schema": schema,
            "exists": True,
            "schema_ok": True,
            "sha256": "a" * 64,
        }

    def fake_load_latest(path, schema):  # noqa: ANN001
        base = {"schema": schema, "ok": True, "generated_at": "2026-01-01T00:00:00+00:00", "summary": {}}
        if schema == f"{prefix}_self_awareness_validate_v1":
            return {**base, "summary": {"status": "ok", "fails": 0, "warnings": 0}}
        if schema == f"{prefix}_self_awareness_cycle_v1":
            return {**base, "status": "ready", "summary": {"steps": 35}}
        if schema == f"{prefix}_self_awareness_objective_coverage_audit_v1":
            return {
                **base,
                "summary": {"blocked_stack_owned": 0, "incomplete": 0, "full_stack_potential_covered": True},
                "rows": [],
                "blocked_rows": [],
                "incomplete_rows": [],
                "policy": {"host_layer_mutates_stack": False},
            }
        if schema == f"{prefix}_self_awareness_working_stack_activation_smoke_v1":
            return {**base, "summary": {"rows": 1, "rows_ok": 1, "open_activation_gaps": 0}}
        if schema == f"{prefix}_self_awareness_autolink_v1":
            return {
                **base,
                "state_digest": "digest-fixture",
                "summary": {
                    "organ_links": 1,
                    "organ_links_complete": 1,
                    "stack_requirement_links": 1,
                    "stack_requirement_links_complete": 1,
                    "synthetic_scenarios": 1,
                    "synthetic_scenarios_complete": 1,
                    "full_stack_potential_covered": True,
                },
            }
        if schema == f"{prefix}_self_awareness_working_stack_inventory_v1":
            return {**base, "summary": {"organs": 2, "usage_gaps": 0, "full_stack_potential_covered": True}}
        if schema == f"{prefix}_self_awareness_requirements_v1":
            return {**base, "summary": {"requirements": 0}, "requirements": []}
        if schema == f"{prefix}_self_awareness_requirement_probes_v1":
            return {**base, "summary": {"probes": 0, "open": 0}, "probes": []}
        if schema == f"{prefix}_self_awareness_stack_closure_dossier_v1":
            return {
                **base,
                "summary": {"open_stack_requirements": 0, "full_stack_potential_covered": True},
                "entries": [],
                "working_stack_activation_dossier": {"entries": []},
            }
        return base

    monkeypatch.setattr(abyss_machine_module, "self_awareness_status", lambda: status_doc)
    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_latest_artifact_ref", fake_artifact_ref)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_resource_preflight", lambda purpose: {"ok": True, "purpose": purpose})

    audit = abyss_machine_module.self_awareness_completion_audit(write_latest=False)

    assert audit["ok"] is True
    assert audit["status"] == "watch"
    assert audit["summary"]["stack_usage_status"] == "complete"
    assert audit["summary"]["stack_usage_closure_complete"] is True
    assert audit["summary"]["body_status"] == "watch"
    assert audit["summary"]["body_closure_complete"] is False
    assert audit["summary"]["body_open_routes"] == 2
    assert audit["summary"]["body_watch_sources"] == 3
    assert audit["summary"]["stack_usage_complete_but_body_watch"] is True
    assert audit["body_closure"]["summary"]["backup_blockers"] == ["vault_not_mounted"]
    assert audit["policy"]["stack_usage_completion_is_not_body_closure"] is True


def test_self_awareness_completion_audit_rejects_green_validator_with_open_stack_potential(abyss_machine_module, monkeypatch) -> None:
    def fake_artifact_ref(name, path, schema):
        return {
            "schema": "abyss_machine_self_awareness_latest_artifact_ref_v1",
            "name": name,
            "path": str(path),
            "expected_schema": schema,
            "exists": True,
            "schema_ok": True,
            "sha256": "a" * 64,
        }

    def fake_load_latest(path, schema):
        base = {"schema": schema, "ok": True, "generated_at": "2026-01-01T00:00:00+00:00", "summary": {}}
        if schema == "abyss_machine_self_awareness_events_v1":
            return {**base, "summary": {"events": 1}}
        if schema == "abyss_machine_self_awareness_episodes_v1":
            return {**base, "summary": {"episodes": 1}}
        if schema == "abyss_machine_self_awareness_alerts_v1":
            return {**base, "summary": {"reaction_candidates": 1}}
        if schema == "abyss_machine_self_awareness_capabilities_v1":
            return {**base, "summary": {"capabilities": 1}}
        if schema == "abyss_machine_self_awareness_requirements_v1":
            return {
                **base,
                "summary": {"requirements": 1},
                "requirements": [
                    {
                        "id": "stack.trace-backend",
                        "title": "Trace backend",
                        "owner": "abyss-stack",
                        "status": "open",
                        "blocking_check_keys": ["tempo_query_route"],
                        "coverage_impact": {"coverage_planes": ["trace_backend"]},
                    }
                ],
            }
        if schema == "abyss_machine_self_awareness_requirement_probes_v1":
            return {
                **base,
                "summary": {"probes": 1, "open": 1},
                "probes": [
                    {
                        "id": "stack.trace-backend",
                        "requirement_id": "stack.trace-backend",
                        "status": "open",
                        "closed_by_current_probe": False,
                        "current_state": {
                            "trace_backend_ready": False,
                            "trace_search_readable": False,
                            "span_log_metric_join_supported": False,
                        },
                        "checks": [
                            {"key": "acceptance_contract_probeable", "ok": True, "level": "ok", "message": "fixture", "data": {}},
                            {"key": "trace_backend_ready", "ok": False, "level": "open", "message": "fixture", "data": {"url": "http://127.0.0.1:3200/ready"}},
                            {"key": "span_log_metric_join_supported", "ok": False, "level": "open", "message": "fixture", "data": {"join_missing": ["trace_backend_ready"]}},
                        ],
                    }
                ],
            }
        if schema == "abyss_machine_self_awareness_stack_closure_dossier_v1":
            return {
                **base,
                "summary": {"open_stack_requirements": 1, "full_stack_potential_covered": False},
                "entries": [
                    {
                            "requirement_id": "stack.trace-backend",
                            "title": "Trace backend",
                            "blocking_check_keys": ["tempo_query_route"],
                            "coverage_impact": {"coverage_planes": ["trace_backend"]},
                            "current_state_digest": "trace-digest",
                            "closure_readiness": {
                                "missing_checks": [
                                    {"key": "trace_backend_ready", "level": "open", "message": "fixture", "evidence_hint": {"url": "http://127.0.0.1:3200/ready"}},
                                    {"key": "span_log_metric_join_supported", "level": "open", "message": "fixture", "evidence_hint": {"join_missing": ["trace_backend_ready"]}},
                                ],
                                "fulfilled_checks": [
                                    {"key": "acceptance_contract_probeable", "message": "fixture", "evidence_hint": {}},
                                    {"key": "host_layer_non_mutating", "message": "fixture", "evidence_hint": {"host_layer_mutates_stack": False}},
                                ],
                                "blocking_check_keys": ["trace_backend_ready", "span_log_metric_join_supported"],
                                "readiness_score": 0.5,
                            },
                            "closure_acceptance": {
                                "schema": "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1",
                                "acceptance_id": "saclose-trace-fixture",
                                "requirement_id": "stack.trace-backend",
                                "owner": "abyss-stack",
                                "status": "awaiting_stack_owner_change",
                                "requirement_status": "open",
                                "surface_kind": "trace_backend_inventory",
                                "complete": True,
                                "pre_close_identity": {
                                    "current_state_digest": "trace-digest",
                                    "current_state_keys": ["trace_backend_ready", "span_log_metric_join_supported"],
                                    "missing_check_keys": ["trace_backend_ready", "span_log_metric_join_supported"],
                                    "fulfilled_check_keys": ["acceptance_contract_probeable", "host_layer_non_mutating"],
                                    "coverage_planes": ["trace_backend"],
                                    "depends_on_requirement_ids": [],
                                    "unblocks_requirement_ids": ["stack.langchain-api.graph-observability"],
                                },
                                "stack_compat_requirement": {
                                    "minimum_response_contract": {
                                        "required_fields": ["backend", "ready_status", "span_log_metric_join_supported"],
                                        "success_predicates": ["ready endpoint reports healthy", "span/log/metric join supported"],
                                    },
                                    "dependency_contract": {
                                        "depends_on_requirement_ids": [],
                                        "unblocks_requirement_ids": ["stack.langchain-api.graph-observability"],
                                    },
                                    "coverage_contract": {
                                        "coverage_planes": ["trace_backend"],
                                        "blocks_stack_usage_requirements": ["span/log/metric correlation"],
                                    },
                                    "redaction_contract": {"raw_secrets_allowed": False, "raw_private_payloads_allowed": False},
                                    "operator_boundary": {
                                        "host_layer_mutates_stack": False,
                                        "abyss_machine_executes_stack_change": False,
                                        "automatic_remediation": False,
                                    },
                                },
                                "closure_diff_contract": {
                                    "no_partial_credit_conditions": ["HTTP 2xx alone is not closure"],
                                },
                                "post_close_success_predicates": ["ready endpoint reports healthy", "span/log/metric join supported"],
                                "post_close_verifier_chain": [
                                    {"command": "abyss-machine self-awareness capabilities --json", "must": ["fixture"]},
                                    {"command": "abyss-machine self-awareness validate --json", "must": ["fixture"]},
                                ],
                                "negative_controls": [{"key": "ready_only_without_trace_search_does_not_close"}],
                                "safe_next_action": {
                                    "requires_human_approval": True,
                                    "executes_commands": False,
                                    "host_layer_mutates_stack": False,
                                },
                            },
                            "unblocks_requirement_ids": ["stack.langchain-api.graph-observability"],
                            "unblocks_dependency_edges": [
                                {
                                    "from": "stack.trace-backend",
                                    "to": "stack.langchain-api.graph-observability",
                                    "kind": "unblocks_stack_requirement",
                                }
                            ],
                            "safe_next_action": {"requires_human_approval": True, "executes_commands": False, "host_layer_mutates_stack": False},
                        }
                    ],
                "working_stack_activation_dossier": {
                    "schema": "abyss_machine_self_awareness_working_stack_activation_dossier_v1",
                    "entries": [
                        {
                            "service": "n8n",
                            "machine_usage_status": "unused",
                            "usage_gap": "declared without running runtime",
                            "activation_kind": "stack_managed_container",
                            "current_state": {
                                "runtime": {"present": True, "running": False, "container": "n8n"},
                                "declared": {"present": True, "modules": ["n8n"]},
                            },
                            "closure_blocker_keys": ["runtime_not_running"],
                            "missing_checks": ["activation_smoke"],
                            "safe_next_action": {"host_layer_mutates_stack": False},
                            "verifier_commands": ["abyss-machine self-awareness activation-smoke --json"],
                        }
                    ],
                },
            }
        if schema == "abyss_machine_self_awareness_working_stack_inventory_v1":
            return {**base, "summary": {"organs": 2, "usage_gaps": 1, "full_stack_potential_covered": False}}
        if schema == "abyss_machine_self_awareness_objective_coverage_audit_v1":
            return {
                **base,
                "summary": {"blocked_stack_owned": 1, "incomplete": 0, "full_stack_potential_covered": False},
                "rows": [{"id": "trace_backend", "status": "blocked_stack_owned", "open_stack_requirement_ids": ["stack.trace-backend"]}],
                "blocked_rows": ["trace_backend"],
                "incomplete_rows": [],
                "policy": {"host_layer_mutates_stack": False},
            }
        if schema == "abyss_machine_self_awareness_working_stack_activation_smoke_v1":
            return {**base, "summary": {"rows": 1, "rows_ok": 0, "open_activation_gaps": 1}}
        if schema == "abyss_machine_self_awareness_autolink_v1":
            return {
                **base,
                "state_digest": "digest-fixture",
                "summary": {
                    "organ_links": 1,
                    "organ_links_complete": 1,
                    "stack_requirement_links": 1,
                    "stack_requirement_links_complete": 1,
                    "synthetic_scenarios": 1,
                    "synthetic_scenarios_complete": 1,
                    "full_stack_potential_covered": False,
                },
                "organ_links": [
                    {
                        "service": "n8n",
                        "owner": "abyss-stack",
                        "machine_usage_status": "unused",
                        "usage_gap": "declared without running runtime",
                        "working_stack_link_id": "wslink-n8n",
                        "episode_ids": ["saepisode-working-stack-gap-n8n"],
                        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"}],
                    }
                ],
                "stack_requirement_links": [
                    {
                        "requirement_id": "stack.trace-backend",
                        "owner": "abyss-stack",
                        "automatic_link_state": "open_stack_blocker",
                        "episode_ids": ["saepisode-stack-trace"],
                        "evidence_refs": [{"path": "/var/lib/abyss-machine/self-awareness/requirements/latest.json"}],
                    }
                ],
            }
        if schema == "abyss_machine_self_awareness_validate_v1":
            return {**base, "summary": {"status": "ok", "fails": 0, "warnings": 0}}
        if schema == "abyss_machine_self_awareness_cycle_v1":
            return {
                **base,
                "status": "ready",
                "summary": {"steps": 35},
                "bridge_proof": {
                    "schema": "abyss_machine_self_awareness_cycle_bridge_proof_v1",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "rows": [
                        {
                            "schema": "abyss_machine_self_awareness_cycle_bridge_proof_row_v1",
                            "id": "heartbeats",
                            "organ": "heartbeat_bridge",
                            "command": "abyss-machine heartbeats pulse --json",
                            "validator": "abyss-machine heartbeats validate --json",
                            "coverage": ["heartbeat", "candidate_lifecycle"],
                            "ok": True,
                            "artifact": {
                                "name": "heartbeats",
                                "path": "/var/lib/abyss-machine/heartbeats/latest.json",
                                "schema": "abyss_machine_heartbeat_pulse_v1",
                                "expected_schema": "abyss_machine_heartbeat_pulse_v1",
                                "ok": True,
                                "schema_ok": True,
                                "sha256": "b" * 64,
                                "machine_owned_path": True,
                            },
                            "evidence_refs": [
                                {
                                    "path": "/var/lib/abyss-machine/heartbeats/latest.json",
                                    "schema": "abyss_machine_heartbeat_pulse_v1",
                                    "sha256": "b" * 64,
                                    "bridge_id": "heartbeats",
                                }
                            ],
                            "policy": {
                                "read_only": True,
                                "host_layer_mutates_stack": False,
                                "executes_commands": False,
                                "actions_executed": False,
                                "automatic_remediation": False,
                            },
                        }
                    ],
                },
            }
        if schema == "abyss_machine_self_awareness_probe_v1":
            return {**base, "run_id": "saprobe-fixture"}
        return base

    monkeypatch.setattr(abyss_machine_module, "load_latest_json", fake_load_latest)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_latest_artifact_ref", fake_artifact_ref)
    monkeypatch.setattr(abyss_machine_module, "self_awareness_resource_preflight", lambda purpose: {"ok": True, "purpose": purpose})

    audit = abyss_machine_module.self_awareness_completion_audit(write_latest=False)

    assert audit["schema"] == "abyss_machine_self_awareness_completion_audit_v1"
    assert audit["ok"] is False
    assert audit["status"] == "incomplete"
    assert audit["summary"]["validator_green"] is True
    assert audit["summary"]["cycle_green"] is True
    assert audit["summary"]["coverage_green"] is True
    assert audit["summary"]["stack_usage_closure_complete"] is False
    assert audit["summary"]["validator_green_but_stack_usage_incomplete"] is True
    assert audit["summary"]["open_stack_requirements"] == 1
    assert audit["summary"]["working_stack_usage_gaps"] == 1
    assert audit["summary"]["completion_actions"] == 2
    assert audit["summary"]["top_completion_action_id"] == "stack-requirement:stack.trace-backend"
    assert audit["action_backlog"]["schema"] == "abyss_machine_self_awareness_completion_action_backlog_v1"
    assert audit["action_backlog"]["summary"]["stack_requirement_actions"] == 1
    assert audit["action_backlog"]["summary"]["working_stack_usage_gap_actions"] == 1
    assert audit["action_backlog"]["summary"]["executable_now"] == 0
    assert audit["action_backlog"]["top_action"]["requirement_id"] == "stack.trace-backend"
    assert audit["action_backlog"]["summary"]["drilldowns"] == 2
    assert audit["action_backlog"]["summary"]["drilldowns_complete"] >= 1
    assert audit["action_backlog"]["summary"]["top_action_drilldown_complete"] is True
    assert audit["action_backlog"]["top_action_drilldown"]["schema"] == "abyss_machine_self_awareness_completion_action_drilldown_v1"
    assert audit["action_backlog"]["top_action_drilldown"]["complete"] is True
    assert audit["action_backlog"]["top_action_drilldown"]["requirement_id"] == "stack.trace-backend"
    assert audit["action_backlog"]["top_action_drilldown"]["checks"]["missing"][0]["key"] == "trace_backend_ready"
    assert audit["action_backlog"]["top_action_drilldown"]["checks"]["fulfilled"][0]["key"] == "acceptance_contract_probeable"
    assert audit["action_backlog"]["top_action_drilldown"]["closure_acceptance"]["complete"] is True
    assert audit["action_backlog"]["top_action_drilldown"]["closure_acceptance"]["negative_controls"][0]["key"] == "ready_only_without_trace_search_does_not_close"
    assert audit["action_backlog"]["top_action_drilldown"]["dependency_edges"]["unblocks_requirement_ids"] == ["stack.langchain-api.graph-observability"]
    assert audit["action_backlog"]["top_action_drilldown"]["acceptance"]["required_fields"] == ["backend", "ready_status", "span_log_metric_join_supported"]
    assert "abyss-machine self-awareness validate --json" in audit["action_backlog"]["top_action_drilldown"]["acceptance"]["verifier_commands"]
    assert audit["action_backlog"]["top_action_drilldown"]["resource_gate"]["completion_audit_runs_cycle"] is False
    assert audit["action_backlog"]["top_action_drilldown"]["policy"]["executes_commands"] is False
    assert audit["action_backlog"]["top_action_drilldown"]["policy"]["host_layer_mutates_stack"] is False
    assert audit["action_backlog"]["drilldowns_by_action"]["stack-requirement:stack.trace-backend"]["id"] == audit["action_backlog"]["summary"]["top_action_drilldown_id"]
    assert audit["completion_route_map"]["schema"] == "abyss_machine_self_awareness_completion_route_map_v1"
    assert audit["completion_route_map"]["ok"] is True
    assert audit["completion_route_map"]["summary"]["actions"] == 2
    assert audit["completion_route_map"]["summary"]["covered_actions"] == 2
    assert audit["completion_route_map"]["summary"]["unassigned_actions"] == 0
    assert audit["completion_route_map"]["summary"]["next_route_id"] == "observability.trace_join_backbone"
    assert audit["completion_route_map"]["summary"]["next_route_path"] == "observability/trace/join-backbone"
    assert audit["completion_route_map"]["next_route"]["actions"] == ["stack-requirement:stack.trace-backend"]
    assert audit["completion_route_map"]["next_route"]["route_path"] == "observability/trace/join-backbone"
    assert audit["completion_route_map"]["next_route"]["unblocks_requirement_ids"] == ["stack.langchain-api.graph-observability"]
    assert audit["completion_route_map"]["next_route"]["resource_gate"]["route_map_runs_cycle"] is False
    assert audit["completion_route_map"]["next_route"]["policy"]["executes_commands"] is False
    assert audit["completion_route_map"]["next_route"]["policy"]["host_layer_mutates_stack"] is False
    assert audit["action_backlog"]["completion_route_map"]["summary"]["next_route_id"] == "observability.trace_join_backbone"
    route_packets = audit["completion_route_packets"]
    assert route_packets["schema"] == "abyss_machine_self_awareness_completion_route_packet_index_v1"
    assert route_packets["ok"] is True
    assert route_packets["summary"]["routes"] == audit["completion_route_map"]["summary"]["routes"]
    assert route_packets["summary"]["packets"] == audit["completion_route_map"]["summary"]["routes"]
    assert route_packets["summary"]["actions"] == 2
    assert route_packets["summary"]["covered_actions"] == 2
    assert route_packets["summary"]["unmapped_actions"] == []
    assert route_packets["summary"]["unmapped_routes"] == []
    assert route_packets["summary"]["top_route_id"] == "observability.trace_join_backbone"
    assert route_packets["summary"]["automation_ready"] is True
    assert route_packets["top_packet"]["schema"] == "abyss_machine_self_awareness_completion_route_packet_v1"
    assert route_packets["top_packet"]["route_id"] == "observability.trace_join_backbone"
    assert route_packets["top_packet"]["route_path"] == "observability/trace/join-backbone"
    assert route_packets["top_packet"]["action_ids"] == ["stack-requirement:stack.trace-backend"]
    assert route_packets["top_packet"]["entity_ids"] == ["stack.requirement.stack.trace-backend"]
    assert len(route_packets["top_packet"]["event_ids"]) == 1
    assert "self-awareness.requirements.latest" in route_packets["top_packet"]["document_ids"]
    assert route_packets["top_packet"]["verifier_commands"]
    assert route_packets["top_packet"]["automation"]["runs_cycle"] is False
    assert route_packets["top_packet"]["automation"]["executes_verifiers"] is False
    assert route_packets["top_packet"]["policy"]["host_layer_mutates_stack"] is False
    assert route_packets["automation"]["validation_contract"]["every_completion_route_has_packet"] is True
    assert route_packets["automation"]["validation_contract"]["every_completion_action_has_route_packet"] is True
    assert audit["action_backlog"]["completion_route_packets"]["summary"]["automation_ready"] is True
    assert audit["action_backlog"]["summary"]["route_packet_automation_ready"] is True
    assert audit["summary"]["completion_route_packet_automation_ready"] is True
    assert audit["entity_event_document_map"]["schema"] == "abyss_machine_self_awareness_entity_event_document_map_v1"
    assert audit["entity_event_document_map"]["ok"] is True
    assert audit["entity_event_document_map"]["summary"]["actions"] == 2
    assert audit["entity_event_document_map"]["summary"]["entities"] == 4
    assert audit["entity_event_document_map"]["summary"]["events"] == 4
    assert audit["entity_event_document_map"]["summary"]["documents"] == 15
    assert audit["entity_event_document_map"]["summary"]["completion_action_entities"] == 2
    assert audit["entity_event_document_map"]["summary"]["stack_organs"] == 1
    assert audit["entity_event_document_map"]["summary"]["machine_bridges"] == 1
    assert audit["entity_event_document_map"]["summary"]["body_surfaces"] == 2
    assert audit["entity_event_document_map"]["summary"]["unmapped_stack_organs"] == []
    assert audit["entity_event_document_map"]["summary"]["unmapped_machine_bridges"] == []
    assert audit["entity_event_document_map"]["summary"]["automation_ready"] is True
    assert audit["entity_event_document_map"]["top_entity"]["entity_id"] == "stack.requirement.stack.trace-backend"
    assert audit["entity_event_document_map"]["top_entity"]["entity_path"] == "stack/requirement/stack.trace-backend"
    assert audit["entity_event_document_map"]["top_event"]["event_kind"] == "stack_requirement_open"
    assert audit["entity_event_document_map"]["top_event"]["route_path"] == "observability/trace/join-backbone"
    assert "self-awareness.requirements.latest" in audit["entity_event_document_map"]["top_entity"]["document_ids"]
    assert audit["entity_event_document_map"]["stack_organ_entities"][0]["entity_id"] == "stack.organ.n8n"
    assert audit["entity_event_document_map"]["stack_organ_entities"][0]["route_path"] == "body/stack-organs"
    assert "self-awareness.autolink.latest" in audit["entity_event_document_map"]["stack_organ_entities"][0]["document_ids"]
    assert audit["entity_event_document_map"]["machine_bridge_entities"][0]["entity_id"] == "machine.bridge.heartbeats"
    assert audit["entity_event_document_map"]["machine_bridge_entities"][0]["route_path"] == "body/machine-bridges"
    assert "machine.bridge.heartbeats.latest" in audit["entity_event_document_map"]["machine_bridge_entities"][0]["document_ids"]
    assert audit["entity_event_document_map"]["automation"]["runs_cycle"] is False
    assert audit["entity_event_document_map"]["automation"]["validation_contract"]["every_action_has_entity"] is True
    assert audit["entity_event_document_map"]["automation"]["validation_contract"]["every_action_has_event"] is True
    assert audit["entity_event_document_map"]["automation"]["validation_contract"]["every_stack_organ_has_entity"] is True
    assert audit["entity_event_document_map"]["automation"]["validation_contract"]["every_machine_bridge_has_entity"] is True
    assert audit["entity_event_document_map"]["automation"]["validation_contract"]["host_layer_mutates_stack"] is False
    assert audit["entity_event_document_map"]["policy"]["host_layer_mutates_stack"] is False
    assert audit["action_backlog"]["entity_event_document_map"]["summary"]["automation_ready"] is True
    action_ids = {action["id"] for action in audit["action_backlog"]["actions"]}
    assert action_ids == {"stack-requirement:stack.trace-backend", "working-stack:n8n"}
    assert all(action["resource_gate"]["completion_audit_runs_cycle"] is False for action in audit["action_backlog"]["actions"])
    assert all(action["policy"]["executes_commands"] is False for action in audit["action_backlog"]["actions"])
    assert all(action["policy"]["host_layer_mutates_stack"] is False for action in audit["action_backlog"]["actions"])
    assert {blocker["id"] for blocker in audit["blockers"]} >= {
        "abyss-stack.requirements.open",
        "abyss-stack.working-potential.open",
    }
    assert audit["source_commands"]["runs_probe"] is False
    assert audit["source_commands"]["runs_cycle"] is False
    assert audit["policy"]["validator_green_is_not_stack_usage_closure"] is True
    assert audit["policy"]["host_layer_mutates_stack"] is False


def test_self_awareness_refresh_exported_artifacts_reloads_latest_refs(tmp_path: Path, abyss_machine_module) -> None:
    schema = "abyss_machine_self_awareness_objective_coverage_audit_v1"
    artifact_path = tmp_path / "coverage-audit" / "latest.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps({"schema": schema, "generated_at": "2026-01-01T00:00:00+00:00", "summary": {"version": 1}}),
        encoding="utf-8",
    )
    exported = {
        "coverage_audit": abyss_machine_module.self_awareness_export_artifact_entry(
            "coverage_audit",
            artifact_path,
            schema,
        )
    }
    old_sha = exported["coverage_audit"]["sha256"]

    artifact_path.write_text(
        json.dumps({"schema": schema, "generated_at": "2026-01-01T00:01:00+00:00", "summary": {"version": 2}}),
        encoding="utf-8",
    )
    artifact_list, missing, malformed = abyss_machine_module.self_awareness_refresh_exported_artifacts(
        exported,
        {"coverage_audit": (artifact_path, schema)},
        ["coverage_audit"],
    )

    refreshed = exported["coverage_audit"]
    refs = abyss_machine_module.self_awareness_export_artifact_refs(exported, ["coverage_audit"])
    assert missing == []
    assert malformed == []
    assert refreshed["sha256"] != old_sha
    assert refreshed["summary"] == {"version": 2}
    assert artifact_list == [refreshed]
    assert refs["coverage_audit"]["sha256"] == refreshed["sha256"]


def test_self_awareness_include_coverage_audit_artifact_adds_late_spec(tmp_path: Path, monkeypatch, abyss_machine_module) -> None:
    latest = tmp_path / "coverage" / "latest.json"
    artifacts: dict[str, tuple[Path, str]] = {}
    monkeypatch.setattr(abyss_machine_module, "SELF_AWARENESS_COVERAGE_AUDIT_LATEST_PATH", latest)

    abyss_machine_module.self_awareness_include_coverage_audit_artifact(artifacts)
    abyss_machine_module.self_awareness_include_coverage_audit_artifact(artifacts)

    assert sorted(artifacts) == ["coverage_audit"]
    assert artifacts["coverage_audit"] == (
        latest,
        "abyss_machine_self_awareness_objective_coverage_audit_v1",
    )


def test_self_awareness_export_manifest_indexes_artifacts(abyss_machine_module) -> None:
    payload = abyss_machine_module.self_awareness_export(write_latest=False)

    assert payload["schema"] == "abyss_machine_self_awareness_export_v1"
    assert payload["ok"] is True
    assert payload["summary"]["missing"] == 0
    assert payload["summary"]["malformed"] == 0
    assert payload["summary"]["manifest_digest"]
    assert payload["policy"]["host_layer_mutates_stack"] is False
    assert payload["policy"]["actions_executed"] is False
    assert payload["portable_contract"]["actions_executed"] is False
    assert payload["portable_contract"]["open_stack_requirements_preserved"] is True
    assert payload["portable_contract"]["working_stack_activation_dossier_included"] is True

    manifest = payload["manifest"]
    artifact_list = payload["artifact_list"]
    artifacts = payload["artifacts"]
    assert manifest["schema"] == "abyss_machine_self_awareness_export_manifest_v1"
    assert manifest["manifest_digest"] == payload["summary"]["manifest_digest"]
    assert manifest["artifact_count"] == len(artifact_list) == len(artifacts)
    assert manifest["portable_contract"]["artifacts_are_machine_owned_readmodels"] is True
    assert manifest["portable_contract"]["stack_handoff_included"] is True
    assert manifest["portable_contract"]["stack_owner_acceptance_verifiers_included"] is True
    assert manifest["portable_contract"]["stack_closure_dossier_included"] is True
    assert manifest["portable_contract"]["stack_requirement_closure_acceptance_included"] is True
    assert manifest["portable_contract"]["working_stack_activation_dossier_included"] is True
    assert manifest["portable_contract"]["working_stack_activation_synthetic_proofs_included"] is True
    assert manifest["portable_contract"]["working_stack_activation_smoke_included"] is True
    assert manifest["portable_contract"]["memory_space_freshness_included"] is True
    assert manifest["portable_contract"]["entity_event_document_map_included"] is True
    assert manifest["portable_contract"]["response_entity_event_document_context_included"] is True
    assert manifest["portable_contract"]["completion_route_packets_included"] is True
    assert manifest["portable_contract"]["body_entity_event_document_map_included"] is True
    assert manifest["portable_contract"]["stack_organ_entities_included"] is True
    assert manifest["portable_contract"]["machine_bridge_entities_included"] is True
    assert manifest["owner_boundary"]["host_layer_mutates_stack"] is False
    assert {item["name"] for item in artifact_list} == set(artifacts)
    assert "stack_closure_dossier" in artifacts
    assert "completion_audit" in artifacts
    for item in artifact_list:
        assert item["exists"] is True
        assert item["schema_ok"] is True
        assert item["sha256"]
        assert item["evidence_ref"]["path"] == item["path"]

    requirements = payload["requirements"]
    handoff = payload["stack_handoff"]
    dossier = payload["stack_closure_dossier"]
    entity_map = payload["entity_event_document_map"]
    entity_handoff = payload["entity_event_document_handoff"]
    response_entity_handoff = payload["response_entity_event_document_handoff"]
    route_packets = payload["completion_route_packets"]
    route_packet_handoff = payload["completion_route_packet_handoff"]
    memory_space_freshness = payload["memory_space_freshness_handoff"]
    assert requirements["schema"] == "abyss_machine_self_awareness_export_requirements_summary_v1"
    assert handoff["schema"] == "abyss_machine_self_awareness_export_stack_handoff_v1"
    assert dossier["schema"] == "abyss_machine_self_awareness_stack_closure_dossier_v1"
    assert entity_map["schema"] == "abyss_machine_self_awareness_entity_event_document_map_v1"
    assert entity_map["summary"]["automation_ready"] is True
    assert entity_map["summary"]["stack_organs"] == entity_map["summary"]["working_stack_organs"]
    assert entity_map["summary"]["machine_bridges"] == entity_map["summary"]["machine_bridge_rows"]
    assert entity_map["summary"]["unmapped_stack_organs"] == []
    assert entity_map["summary"]["unmapped_machine_bridges"] == []
    assert entity_handoff["schema"] == "abyss_machine_self_awareness_export_entity_event_document_handoff_v1"
    assert entity_handoff["complete"] is True
    assert entity_handoff["summary"] == entity_map["summary"]
    assert entity_handoff["policy"]["host_layer_mutates_stack"] is False
    assert response_entity_handoff["schema"] == "abyss_machine_self_awareness_export_response_entity_event_document_handoff_v1"
    assert response_entity_handoff["complete"] is True
    assert response_entity_handoff["entity_event_document_missing"] == 0
    assert response_entity_handoff["policy"]["host_layer_mutates_stack"] is False
    assert route_packets["schema"] == "abyss_machine_self_awareness_completion_route_packet_index_v1"
    assert route_packets["summary"]["automation_ready"] is True
    assert route_packets["summary"]["covered_actions"] == payload["summary"]["completion_route_packet_actions"]
    assert route_packet_handoff["schema"] == "abyss_machine_self_awareness_export_completion_route_packet_handoff_v1"
    assert route_packet_handoff["complete"] is True
    assert route_packet_handoff["summary"] == route_packets["summary"]
    assert route_packet_handoff["policy"]["host_layer_mutates_stack"] is False
    assert payload["portable_contract"]["response_entity_event_document_context_included"] is True
    assert payload["portable_contract"]["completion_route_packets_included"] is True
    assert payload["portable_contract"]["memory_space_freshness_included"] is True
    assert memory_space_freshness["schema"] == "abyss_machine_self_awareness_memory_space_freshness_handoff_v1"
    assert memory_space_freshness["complete"] is True
    assert memory_space_freshness["policy"]["freshness_must_precede_reasoning"] is True
    assert memory_space_freshness["policy"]["host_layer_mutates_stack"] is False
    assert requirements["policy"]["host_layer_mutates_stack"] is False
    assert requirements["policy"]["handoff_only"] is True
    assert handoff["policy"]["host_layer_mutates_stack"] is False
    assert dossier["policy"]["host_layer_mutates_stack"] is False
    assert dossier["policy"]["executes_commands"] is False
    assert handoff["policy"]["runbook_candidates_are_handoff_only"] is True
    assert handoff["policy"]["raw_secrets_included"] is False
    assert handoff["summary"]["stack_owned_requirements"] == requirements["summary"]["stack_owned"]
    assert handoff["summary"]["open"] == len(handoff["open_requirements"]) == len(requirements["open_stack_ids"])
    ordered_ids = handoff["ordered_requirement_ids"]
    closure_order_ids = [item["requirement_id"] for item in handoff["closure_order"]]
    assert ordered_ids == closure_order_ids
    assert set(ordered_ids) == set(handoff["open_requirement_ids"])
    assert handoff["summary"]["closure_order_entries"] == len(handoff["closure_order"])
    assert handoff["stack_owner_handoff"]["closure_order_ids"] == ordered_ids
    assert handoff["stack_owner_handoff"]["policy"]["abyss_machine_executes_stack_change"] is False
    assert handoff["stack_owner_handoff"]["policy"]["host_layer_mutates_stack"] is False
    graph_ordered_ids = handoff["dependency_graph"]["ordered_requirement_ids"]
    assert set(ordered_ids).issubset(set(graph_ordered_ids))
    assert set(handoff["dependency_graph"]["open_requirement_ids"]) == set(handoff["open_requirement_ids"])
    assert handoff["dependency_graph"]["policy"]["host_layer_mutates_stack"] is False
    assert handoff["dependency_graph"]["policy"]["executes_commands"] is False
    if ordered_ids:
        assert handoff["summary"]["top_requirement_id"] == ordered_ids[0]
        assert handoff["stack_owner_handoff"]["top_requirement_id"] == ordered_ids[0]
    if "stack.trace-backend" in ordered_ids and "stack.langchain-api.graph-observability" in ordered_ids:
        assert ordered_ids.index("stack.trace-backend") < ordered_ids.index("stack.langchain-api.graph-observability")
        assert {
            "from": "stack.langchain-api.graph-observability",
            "to": "stack.trace-backend",
            "kind": "requires_stack_requirement",
            "reason": ["LangGraph trace/checkpoint replay needs the trace backend coupling first."],
        } in handoff["dependency_graph"]["edges"]
    assert requirements["summary"]["stack_handoff_acceptance_verifiers"] >= len(handoff["open_requirements"])
    assert requirements["summary"]["acceptance_verifier_steps"] >= len(handoff["open_requirements"])
    assert requirements["summary"]["stack_handoff_coverage_impact_entries"] >= len(handoff["open_requirements"])
    assert requirements["summary"]["stack_handoff_safe_next_actions"] >= len(handoff["open_requirements"])
    assert dossier["summary"]["open_stack_requirements"] == handoff["summary"]["open"]
    assert dossier["summary"]["probes"] == handoff["summary"]["stack_handoff"]
    assert dossier["summary"]["missing_checks"] == handoff["summary"]["closure_readiness_missing_checks"]
    assert dossier["summary"]["closure_acceptance_packets"] == handoff["summary"]["stack_requirement_closure_acceptance_packets"]
    assert dossier["summary"]["closure_acceptance_packets_complete"] == handoff["summary"]["stack_requirement_closure_acceptance_packets_complete"]
    assert dossier["summary"]["stack_requirement_compat_requirements"] == handoff["summary"]["stack_requirement_compat_requirements"]
    assert dossier["summary"]["reverse_dependency_edges"] == dossier["summary"]["dependency_edges"]
    assert dossier["summary"]["coverage_impact_entries"] == dossier["summary"]["probes"]
    assert dossier["summary"]["blocked_coverage_planes"]
    assert isinstance(dossier["dependency_graph"]["reverse_edges"], list)
    for entry in dossier["open_requirements"]:
        assert entry["closure_impact"]["schema"] == "abyss_machine_self_awareness_stack_closure_impact_v1"
        assert entry["closure_impact"]["policy"]["host_layer_mutates_stack"] is False
        assert entry["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert entry["coverage_impact"]["policy"]["host_layer_mutates_stack"] is False
        assert entry["coverage_impact"]["coverage_planes"]
    assert set(handoff["open_requirement_ids"]) == set(requirements["open_stack_ids"])
    assert set(handoff["open_requirement_ids"]) == set(requirements["open_stack_requirement_ids"])
    assert {"requirements", "requirement_probes", "stack_closure_dossier", "coverage_audit", "working_stack", "activation_smoke"}.issubset(handoff["artifact_refs"])
    assert handoff["artifact_refs"]["coverage_audit"]["schema"] == "abyss_machine_self_awareness_objective_coverage_audit_v1"
    assert handoff["artifact_refs"]["activation_smoke"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_v1"
    assert handoff["coverage_audit_ref"] == handoff["artifact_refs"]["coverage_audit"]
    assert handoff["summary"]["coverage_impact_entries"] == len(handoff["coverage_impacts"]) == len(handoff["open_requirements"])
    assert handoff["blocked_coverage_planes"] == handoff["summary"]["blocked_coverage_planes"]
    assert handoff["blocked_coverage_planes"]
    assert set(handoff["coverage_impacts_by_requirement"]) == set(handoff["open_requirement_ids"])
    assert {impact["requirement_id"] for impact in handoff["coverage_impacts"]} == set(handoff["open_requirement_ids"])
    assert handoff["stack_owner_handoff"]["coverage_impacts_by_requirement"] == handoff["coverage_impacts_by_requirement"]
    assert handoff["stack_owner_handoff"]["blocked_coverage_planes"] == handoff["blocked_coverage_planes"]
    assert set(handoff["blocked_coverage_planes"]) == {
        plane
        for impact in handoff["coverage_impacts"]
        for plane in impact["coverage_planes"]
    }
    verifier_matrix = handoff["stack_owner_verifier_matrix"]
    assert handoff["summary"]["stack_owner_verifier_matrix_entries"] == len(verifier_matrix) == len(handoff["open_requirements"])
    assert set(handoff["stack_owner_verifier_matrix_by_requirement"]) == set(handoff["open_requirement_ids"])
    assert {item["requirement_id"] for item in verifier_matrix} == set(handoff["open_requirement_ids"])
    assert handoff["stack_owner_handoff"]["verifier_matrix"] == verifier_matrix
    assert handoff["stack_owner_handoff"]["verifier_matrix_by_requirement"] == handoff["stack_owner_verifier_matrix_by_requirement"]
    assert handoff["summary"]["stack_owner_verifier_commands"] == sum(len(item["verifier_commands"]) for item in verifier_matrix)
    assert handoff["summary"]["stack_owner_post_close_verifiers"] == sum(len(item["post_close_verifiers"]) for item in verifier_matrix)
    closure_summary = handoff["stack_requirement_closure_acceptance_summary"]
    closure_packets = handoff["stack_requirement_closure_acceptance_packets"]
    closure_by_requirement = handoff["stack_requirement_closure_acceptance_packets_by_requirement"]
    assert closure_summary["schema"] == "abyss_machine_self_awareness_export_stack_requirement_closure_acceptance_summary_v1"
    assert closure_summary["packets"] == len(closure_packets) == dossier["summary"]["probes"]
    assert closure_summary["packets_complete"] == len(closure_packets)
    assert closure_summary["policy"]["host_layer_mutates_stack"] is False
    assert set(closure_by_requirement) == {entry["requirement_id"] for entry in dossier["entries"]}
    assert handoff["stack_owner_handoff"]["closure_acceptance_summary"] == closure_summary
    assert handoff["stack_owner_handoff"]["closure_acceptance_packets_by_requirement"] == closure_by_requirement
    for packet in closure_packets:
        assert packet["schema"] == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
        assert packet["complete"] is True
        assert packet["owner"] == "abyss-stack"
        assert packet["stack_compat_requirement"]["schema"] == "abyss_machine_self_awareness_stack_requirement_compat_requirement_v1"
        assert packet["stack_compat_requirement"]["owner"] == "abyss-stack"
        assert packet["stack_compat_requirement"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
        assert packet["policy"]["host_layer_mutates_stack"] is False
    activation_dossier = handoff["working_stack_activation_dossier"]
    activation_entries = handoff["working_stack_activation_entries"]
    assert activation_dossier["schema"] == "abyss_machine_self_awareness_working_stack_activation_dossier_v1"
    assert handoff["working_stack_activation_handoff"]["policy"]["host_layer_mutates_stack"] is False
    assert handoff["working_stack_activation_handoff"]["policy"]["abyss_machine_executes_stack_change"] is False
    assert handoff["summary"]["working_stack_activation_entries"] == len(activation_entries)
    assert set(handoff["working_stack_activation_service_ids"]) == {entry["service"] for entry in activation_entries}
    assert activation_dossier["summary"]["activation_entries_complete"] == len(activation_entries)
    assert activation_dossier["summary"]["synthetic_scenarios"] == len(activation_entries)
    assert activation_dossier["summary"]["synthetic_scenarios_complete"] == len(activation_entries)
    assert activation_dossier["summary"]["closure_acceptance_packets"] == len(activation_entries)
    assert activation_dossier["summary"]["closure_acceptance_packets_complete"] == len(activation_entries)
    assert activation_dossier["summary"]["activation_compat_requirements"] == len(activation_entries)
    assert activation_dossier["synthetic_scenario_matrix"]["ok"] is True
    assert activation_dossier["closure_acceptance_matrix"]["ok"] is True
    proof_summary = handoff["working_stack_activation_synthetic_proof_summary"]
    proofs_by_service = handoff["working_stack_activation_synthetic_proofs_by_service"]
    smoke_summary = handoff["working_stack_activation_smoke_summary"]
    smoke_by_service = handoff["working_stack_activation_smoke_by_service"]
    smoke_compact_by_service = handoff["working_stack_activation_smoke_compact_by_service"]
    organ_use_summary = handoff["stack_organ_use_packet_summary"]
    organ_use_by_service = handoff["stack_organ_use_packet_by_service"]
    assert proof_summary["schema"] == "abyss_machine_self_awareness_export_working_stack_activation_synthetic_proof_summary_v1"
    assert proof_summary["proofs"] == len(activation_entries)
    assert proof_summary["proofs_complete"] == len(activation_entries)
    assert proof_summary["failed_services"] == []
    assert set(proof_summary["services"]) == set(handoff["working_stack_activation_service_ids"])
    assert set(proofs_by_service) == set(handoff["working_stack_activation_service_ids"])
    assert smoke_summary["schema"] == "abyss_machine_self_awareness_export_working_stack_activation_smoke_summary_v1"
    assert smoke_summary["rows"] >= len(activation_entries)
    assert smoke_summary["rows_complete"] == smoke_summary["rows"]
    assert smoke_summary["failed_services"] == []
    assert smoke_summary["policy"]["host_layer_mutates_stack"] is False
    assert set(handoff["working_stack_activation_service_ids"]).issubset(set(smoke_summary["services"]))
    assert set(smoke_by_service) == set(smoke_summary["services"])
    assert set(smoke_compact_by_service) == set(smoke_summary["services"])
    assert organ_use_summary["schema"] == "abyss_machine_self_awareness_export_stack_organ_use_packet_summary_v1"
    assert organ_use_summary["packets"] >= len(activation_entries)
    assert organ_use_summary["packets_complete"] == organ_use_summary["packets"]
    assert organ_use_summary["failed_services"] == []
    assert organ_use_summary["policy"]["host_layer_mutates_stack"] is False
    assert set(handoff["working_stack_activation_service_ids"]).issubset(set(organ_use_summary["services"]))
    assert set(organ_use_by_service) == set(organ_use_summary["services"])
    for entry in activation_entries:
        assert entry["schema"] == "abyss_machine_self_awareness_working_stack_activation_entry_v1"
        assert entry["owner"] == "abyss-stack"
        assert entry["complete"] is True
        assert entry["activation_readiness"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_readiness_v1"
        closure_acceptance = entry["closure_acceptance"]
        assert closure_acceptance["schema"] == "abyss_machine_self_awareness_working_stack_activation_closure_acceptance_v1"
        assert closure_acceptance["complete"] is True
        assert closure_acceptance["service"] == entry["service"]
        assert closure_acceptance["machine_usage_status"] == entry["machine_usage_status"]
        assert closure_acceptance["working_stack_link_id"] == entry["working_stack_link_id"]
        assert closure_acceptance["stack_compat_requirement"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_compat_requirement_v1"
        assert closure_acceptance["stack_compat_requirement"]["owner"] == "abyss-stack"
        assert closure_acceptance["stack_compat_requirement"]["operator_boundary"]["abyss_machine_executes_stack_change"] is False
        assert closure_acceptance["policy"]["host_layer_mutates_stack"] is False
        assert entry["synthetic_scenario"]["schema"] == "abyss_machine_self_awareness_working_stack_activation_synthetic_scenario_v1"
        assert entry["synthetic_scenario"]["complete"] is True
        assert entry["synthetic_scenario"]["policy"]["host_layer_mutates_stack"] is False
        proof = proofs_by_service[entry["service"]]
        assert proof["schema"] == "abyss_machine_self_awareness_working_stack_activation_synthetic_proof_v1"
        assert proof["complete"] is True
        assert proof["service"] == entry["service"]
        assert proof["machine_usage_status"] == entry["machine_usage_status"]
        assert proof["working_stack_link_id"] == entry["working_stack_link_id"]
        assert proof["policy"]["host_layer_mutates_stack"] is False
        smoke = smoke_by_service[entry["service"]]
        compact = smoke_compact_by_service[entry["service"]]
        assert smoke["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_row_v1"
        assert smoke["complete"] is True
        assert smoke["service"] == entry["service"]
        assert smoke["machine_usage_status"] == entry["machine_usage_status"]
        assert smoke["working_stack_link_id"] == entry["working_stack_link_id"]
        if smoke.get("row_kind") == "organ_movement":
            assert smoke["replay"]["actual_run"] is False
            assert smoke["replay"]["divergences"] is None
            assert smoke["replay"]["working_stack_gap_replayable"] is None
            assert smoke["policy"]["actual_investigate_replay_run"] is False
            assert smoke["policy"]["movement_packet"] is True
        else:
            assert smoke["replay"]["divergences"] == 0
            assert smoke["replay"]["working_stack_gap_replayable"] is True
        assert smoke["policy"]["host_layer_mutates_stack"] is False
        organ_packet = organ_use_by_service[entry["service"]]
        assert organ_packet["schema"] == "abyss_machine_self_awareness_stack_organ_use_packet_v1"
        assert organ_packet["complete"] is True
        assert organ_packet["service"] == entry["service"]
        assert organ_packet["entity"]["entity_id"] == f"stack.organ.{entry['service']}"
        assert organ_packet["event"]["machine_usage_status"] == entry["machine_usage_status"]
        assert organ_packet["event"]["working_stack_link_id"] == entry["working_stack_link_id"]
        assert organ_packet["activation_gap"]["route_complete"] is True
        assert organ_packet["synthetic_scenario"]["complete"] is True
        assert organ_packet["closure_acceptance"]["complete"] is True
        assert organ_packet["investigation_replay"]["complete"] is (smoke.get("row_kind") != "organ_movement")
        assert "self-awareness.completion-audit.latest" in organ_packet["document_ids"]
        assert organ_packet["policy"]["host_layer_mutates_stack"] is False
        assert compact["schema"] == "abyss_machine_self_awareness_working_stack_activation_smoke_compact_v1"
        assert compact["complete"] is True
        assert compact["service"] == entry["service"]
        assert compact["working_stack_link_id"] == entry["working_stack_link_id"]
        assert compact["stack_organ_use_packet_id"] == organ_packet["packet_id"]
        if compact.get("row_kind") == "organ_movement":
            assert compact["working_stack_gap_replayable"] is None
            assert compact["divergences"] is None
            assert compact["movement_categories"]
        assert compact["policy"]["host_layer_mutates_stack"] is False
        assert entry["missing_checks"]
        assert entry["runbook_candidate"]["machine_executes_stack_change"] is False
        assert entry["safe_next_action"]["host_layer_mutates_stack"] is False
        assert entry["safe_next_action"]["executes_commands"] is False
    assert payload["summary"]["open_stack_requirements"] == handoff["summary"]["open"]
    assert payload["summary"]["stack_closure_dossier_entries"] == dossier["summary"]["probes"]
    assert payload["summary"]["stack_requirement_closure_acceptance_packets"] == handoff["summary"]["stack_requirement_closure_acceptance_packets"]
    assert payload["summary"]["stack_requirement_closure_acceptance_packets_complete"] == handoff["summary"]["stack_requirement_closure_acceptance_packets_complete"]
    assert payload["summary"]["stack_requirement_compat_requirements"] == handoff["summary"]["stack_requirement_compat_requirements"]
    assert payload["summary"]["working_stack_activation_entries"] == handoff["summary"]["working_stack_activation_entries"]
    assert payload["summary"]["working_stack_activation_closure_acceptance_packets"] == handoff["summary"]["working_stack_activation_closure_acceptance_packets"]
    assert payload["summary"]["working_stack_activation_closure_acceptance_packets_complete"] == handoff["summary"]["working_stack_activation_closure_acceptance_packets_complete"]
    assert payload["summary"]["working_stack_activation_compat_requirements"] == handoff["summary"]["working_stack_activation_compat_requirements"]
    assert payload["summary"]["working_stack_activation_synthetic_proofs"] == handoff["summary"]["working_stack_activation_synthetic_proofs"]
    assert payload["summary"]["working_stack_activation_synthetic_proofs_complete"] == handoff["summary"]["working_stack_activation_synthetic_proofs_complete"]
    assert payload["summary"]["working_stack_activation_smoke_rows"] == handoff["summary"]["working_stack_activation_smoke_rows"]
    assert payload["summary"]["working_stack_activation_smoke_rows_complete"] == handoff["summary"]["working_stack_activation_smoke_rows_complete"]
    assert payload["summary"]["working_stack_activation_smoke_failed_services"] == []
    assert payload["summary"]["stack_organ_use_packets"] == handoff["summary"]["stack_organ_use_packets"]
    assert payload["summary"]["stack_organ_use_packets_complete"] == handoff["summary"]["stack_organ_use_packets_complete"]
    assert payload["summary"]["stack_organ_use_packet_failed_services"] == []
    assert payload["summary"]["entity_event_document_body_surfaces"] == entity_map["summary"]["body_surfaces"]
    assert payload["summary"]["entity_event_document_automation_ready"] is True
    assert payload["summary"]["entity_event_document_export_issues"] == []
    assert payload["portable_contract"]["open_stack_requirements_preserved"] is True
    assert payload["portable_contract"]["stack_closure_dossier_included"] is True
    assert payload["portable_contract"]["stack_requirement_closure_acceptance_included"] is True
    assert payload["portable_contract"]["working_stack_activation_dossier_included"] is True
    assert payload["portable_contract"]["working_stack_activation_closure_acceptance_included"] is True
    assert payload["portable_contract"]["working_stack_activation_synthetic_proofs_included"] is True
    assert payload["portable_contract"]["working_stack_activation_smoke_included"] is True
    assert payload["portable_contract"]["stack_organ_use_packets_included"] is True
    assert payload["portable_contract"]["entity_event_document_map_included"] is True
    assert payload["portable_contract"]["body_entity_event_document_map_included"] is True
    assert payload["portable_contract"]["stack_organ_entities_included"] is True
    assert payload["portable_contract"]["machine_bridge_entities_included"] is True
    assert payload["policy"]["open_stack_requirements_are_blockers_not_host_failures"] is True

    for requirement in handoff["open_requirements"]:
        assert requirement["owner"] == "abyss-stack"
        assert requirement["closed_by_current_probe"] is False
        assert requirement["closure_blockers"]
        assert requirement["current_state"]
        assert requirement["acceptance_verifiers"]
        assert requirement["machine_closure_probe"]["success_predicates"]
        assert requirement["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert requirement["coverage_impact"]["policy"]["host_layer_mutates_stack"] is False
        assert requirement["closure_acceptance"]["schema"] == "abyss_machine_self_awareness_stack_requirement_closure_acceptance_v1"
        assert requirement["closure_acceptance"]["complete"] is True
        assert requirement["closure_acceptance"]["requirement_id"] == requirement["id"]
        assert requirement["closure_acceptance"]["stack_compat_requirement"]["owner"] == "abyss-stack"
        assert requirement["closure_acceptance"]["policy"]["host_layer_mutates_stack"] is False
        assert requirement["safe_next_action"]["host_layer_mutates_stack"] is False
        assert requirement["current_state_digest"]["schema"] == "abyss_machine_self_awareness_requirement_current_state_digest_v1"
        assert requirement["current_state_digest"]["policy"]["raw_payloads_included"] is False
        assert requirement["current_state_digest"]["policy"]["raw_secrets_included"] is False
        assert requirement["handoff_contract_complete"] is True
        runbook = requirement["runbook_candidate"]
        assert runbook["machine_executes_stack_change"] is False
        assert runbook["host_layer_mutates_stack"] is False
        assert runbook["acceptance_steps"]
        assert runbook["acceptance_verifiers"]
        assert runbook["rollback"]
    for impact in handoff["coverage_impacts"]:
        assert impact["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert impact["coverage_planes"]
        assert impact["proof_commands"]
        assert impact["policy"]["host_layer_mutates_stack"] is False
        assert impact["policy"]["executes_commands"] is False
        assert impact["policy"]["raw_secrets_included"] is False
    for item in verifier_matrix:
        assert item["schema"] == "abyss_machine_self_awareness_export_stack_owner_verifier_v1"
        assert item["owner"] == "abyss-stack"
        assert item["blocking_check_keys"]
        assert item["verifier_commands"]
        assert item["acceptance_verifiers"]
        assert item["post_close_verifiers"]
        assert item["coverage_planes"]
        assert item["coverage_impact"]["schema"] == "abyss_machine_self_awareness_stack_coverage_impact_v1"
        assert item["safe_next_action"]["host_layer_mutates_stack"] is False
        assert item["policy"]["host_layer_mutates_stack"] is False
        assert item["policy"]["executes_commands"] is False
        assert item["policy"]["actions_executed"] is False
        assert item["policy"]["raw_secrets_included"] is False
    for entry in dossier["open_requirements"]:
        assert entry["owner"] == "abyss-stack"
        assert entry["closure_readiness"]["schema"] == "abyss_machine_stack_handoff_closure_readiness_v1"
        assert entry["runbook_candidate"]["machine_executes_stack_change"] is False
        assert entry["safe_next_action"]["host_layer_mutates_stack"] is False


@pytest.mark.live
@pytest.mark.parametrize(
    ("args", "schema"),
    [
        (("self-awareness", "paths", "--json"), "abyss_machine_self_awareness_paths_v1"),
        (("self-awareness", "requirements", "--json"), "abyss_machine_self_awareness_requirements_v1"),
        (("self-awareness", "requirement-probes", "--json"), "abyss_machine_self_awareness_requirement_probes_v1"),
        (("self-awareness", "stack-closure-dossier", "--json"), "abyss_machine_self_awareness_stack_closure_dossier_v1"),
        (("self-awareness", "failure-matrix", "--json"), "abyss_machine_self_awareness_failure_matrix_v1"),
        (("self-awareness", "coverage-audit", "--json"), "abyss_machine_self_awareness_objective_coverage_audit_v1"),
        (("self-awareness", "validate", "--json"), "abyss_machine_self_awareness_validate_v1"),
        (("self-awareness", "export", "--json"), "abyss_machine_self_awareness_export_v1"),
    ],
)
def test_self_awareness_readonly_cli_commands_emit_schema_envelopes(run_abyss_machine, args: tuple[str, ...], schema: str) -> None:
    payload = parse_json_stdout(run_abyss_machine(*args, timeout=120.0))

    assert payload.get("schema") == schema
    assert payload.get("ok") is not False
    assert payload.get("policy", {}).get("host_layer_mutates_stack") is not True
