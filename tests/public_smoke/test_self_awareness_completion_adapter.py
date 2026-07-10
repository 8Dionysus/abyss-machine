from __future__ import annotations

from pathlib import Path
from typing import Any

from abyss_machine import self_awareness_adapters as adapters


def _paths(tmp_path: Path) -> adapters.SelfAwarenessCompletionPaths:
    return adapters.SelfAwarenessCompletionPaths(
        coverage_audit_latest=tmp_path / "coverage-audit/latest.json",
        activation_smoke_latest=tmp_path / "activation-smoke/latest.json",
        autolink_latest=tmp_path / "autolink/latest.json",
        working_stack_latest=tmp_path / "working-stack/latest.json",
        requirements_latest=tmp_path / "requirements/latest.json",
        requirement_probes_latest=tmp_path / "requirement-probes/latest.json",
        stack_closure_dossier_latest=tmp_path / "stack-closure-dossier/latest.json",
        validate_latest=tmp_path / "validate/latest.json",
        cycle_latest=tmp_path / "cycle/latest.json",
        probe_latest=tmp_path / "probe/latest.json",
        export_latest=tmp_path / "export/latest.json",
        completion_audit_latest=tmp_path / "completion-audit/latest.json",
        completion_audit_root=tmp_path / "completion-audit",
        collect_latest=tmp_path / "collect/latest.json",
        events_latest=tmp_path / "events/latest.json",
        timeline_latest=tmp_path / "timeline/latest.json",
        spatial_graph_latest=tmp_path / "spatial-graph/latest.json",
        context_latest=tmp_path / "context/latest.json",
    )


def _fixture_ports(
    paths: adapters.SelfAwarenessCompletionPaths,
    events: list[str],
    *,
    include_body_closure: bool = True,
    write_errors: list[dict[str, Any]] | None = None,
) -> tuple[
    adapters.SelfAwarenessCompletionInputPort,
    adapters.SelfAwarenessCompletionContractPort,
    adapters.SelfAwarenessCompletionPersistencePort,
]:
    status_doc = {
        "schema": "abyss_machine_self_awareness_status_v1",
        "summary": {
            "open_stack_requirements": 0,
            "working_stack_usage_gaps": 0,
            "requirement_probes_open": 0,
        },
        "open_stack_requirements": {
            "rows": [],
            "policy": {"host_layer_mutates_stack": False},
        },
        "open_potential": {
            "rows": [],
            "policy": {"host_layer_mutates_stack": False},
        },
    }
    if include_body_closure:
        status_doc["body_closure"] = {
            "complete": False,
            "status": "watch",
            "summary": {"response_routes": 1, "watch_sources": 1},
        }

    docs_by_path = {
        paths.coverage_audit_latest: {
            "schema": "abyss_machine_self_awareness_objective_coverage_audit_v1",
            "ok": True,
            "summary": {"incomplete": 0, "blocked_stack_owned": 0},
            "rows": [],
            "policy": {"host_layer_mutates_stack": False},
        },
        paths.activation_smoke_latest: {
            "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1",
            "summary": {"open_activation_gaps": 0},
        },
        paths.autolink_latest: {
            "schema": "abyss_machine_self_awareness_autolink_v1",
            "ok": True,
            "summary": {},
        },
        paths.working_stack_latest: {
            "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
            "summary": {},
            "organs": [],
        },
        paths.requirements_latest: {
            "schema": "abyss_machine_self_awareness_requirements_v1",
        },
        paths.requirement_probes_latest: {
            "schema": "abyss_machine_self_awareness_requirement_probes_v1",
        },
        paths.stack_closure_dossier_latest: {
            "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        },
        paths.validate_latest: {
            "schema": "abyss_machine_self_awareness_validate_v1",
            "ok": True,
            "summary": {"fails": 0},
        },
        paths.cycle_latest: {
            "schema": "abyss_machine_self_awareness_cycle_v1",
            "ok": True,
            "status": "complete",
        },
    }

    def status() -> dict[str, Any]:
        events.append("input:status")
        return status_doc

    def body_closure() -> dict[str, Any]:
        events.append("input:body_closure")
        return {
            "complete": False,
            "status": "watch",
            "summary": {"response_routes": 2, "watch_sources": 2},
        }

    def load_latest(path: Path, schema: str) -> dict[str, Any]:
        events.append(f"input:latest:{path.parent.name}")
        document = dict(docs_by_path[path])
        assert document["schema"] == schema
        return document

    def preflight(purpose: str) -> dict[str, Any]:
        events.append(f"input:preflight:{purpose}")
        return {"ok": True, "purpose": purpose}

    def artifact_ref(name: str, path: Path, schema: str) -> dict[str, Any]:
        events.append(f"input:artifact:{name}")
        return {
            "name": name,
            "path": str(path),
            "schema": schema,
            "exists": True,
            "schema_ok": True,
            "sha256": f"sha256:{name}",
        }

    input_port = adapters.SelfAwarenessCompletionInputPort(
        status=status,
        body_closure_status=body_closure,
        load_latest_json=load_latest,
        resource_preflight=preflight,
        latest_artifact_ref=artifact_ref,
    )

    def contract(name: str, result: Any):
        def call(*args: Any, **kwargs: Any) -> Any:
            events.append(f"contract:{name}")
            return result() if callable(result) else result

        return call

    action = {
        "id": "stack-requirement:stack.trace-backend",
        "category": "stack_requirement",
        "policy": {
            "requires_human_approval": True,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
        },
    }
    drilldown = {
        "id": "drilldown-trace",
        "action_id": action["id"],
        "complete": True,
        "policy": {"executes_commands": False, "host_layer_mutates_stack": False},
    }
    route_map = {"ok": True, "summary": {"routes": 1}}
    entity_map = {"ok": True, "summary": {"entities": 1}}
    route_packets = {
        "ok": True,
        "summary": {
            "packets": 1,
            "packets_complete": 1,
            "covered_actions": 1,
            "automation_ready": True,
            "top_packet_id": "packet-trace",
        },
    }
    backlog = {
        "ok": True,
        "status": "open",
        "summary": {"top_action_id": action["id"]},
        "actions": [action],
    }
    final_document = {
        "schema": "abyss_machine_self_awareness_completion_audit_v1",
        "ok": True,
        "status": "watch",
        "summary": {"audit_ok": True},
        "policy": {"host_layer_mutates_stack": False},
    }
    contract_port = adapters.SelfAwarenessCompletionContractPort(
        completion_paths=contract("completion_paths", object),
        entity_document_paths=contract("entity_document_paths", object),
        autolink_ready=contract("autolink_ready", True),
        owner_boundary_readonly=contract("owner_boundary_readonly", True),
        completion_readiness=contract("completion_readiness", object),
        completion_gates=contract("completion_gates", [{"id": "closure", "ok": True}]),
        completion_blockers=contract("completion_blockers", []),
        completion_actions=contract("completion_actions", [action]),
        drilldown_context=contract("drilldown_context", object),
        action_drilldown=contract("action_drilldown", drilldown),
        completion_route_map=contract("completion_route_map", route_map),
        entity_event_document_map=contract("entity_event_document_map", entity_map),
        completion_route_packet_index=contract("completion_route_packet_index", route_packets),
        completion_action_backlog=contract("completion_action_backlog", backlog),
        audit_document_context=contract("audit_document_context", object),
        completion_audit_document=contract("completion_audit_document", final_document),
    )

    def write_latest(document: dict[str, Any], latest: Path, root: Path) -> list[dict[str, Any]]:
        events.append("persistence:write")
        assert latest == paths.completion_audit_latest
        assert root == paths.completion_audit_root
        assert document["schema"] == "abyss_machine_self_awareness_completion_audit_v1"
        return list(write_errors or [])

    persistence_port = adapters.SelfAwarenessCompletionPersistencePort(
        write_latest_and_history=write_latest,
    )
    return input_port, contract_port, persistence_port


def test_completion_audit_orchestration_orders_inputs_contracts_and_persistence(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    events: list[str] = []
    input_port, contract_port, persistence_port = _fixture_ports(paths, events)

    document = adapters.run_completion_audit(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T08:00:00-06:00",
        write_latest=True,
        paths=paths,
        input_port=input_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert document["status"] == "watch"
    assert events[:11] == [
        "input:status",
        "input:latest:coverage-audit",
        "input:latest:activation-smoke",
        "input:latest:autolink",
        "input:latest:working-stack",
        "input:latest:requirements",
        "input:latest:requirement-probes",
        "input:latest:stack-closure-dossier",
        "input:latest:validate",
        "input:latest:cycle",
        "input:preflight:self-awareness-completion-audit",
    ]
    assert [event for event in events if event.startswith("input:artifact:")] == [
        "input:artifact:working_stack",
        "input:artifact:requirements",
        "input:artifact:requirement_probes",
        "input:artifact:stack_closure_dossier",
        "input:artifact:activation_smoke",
        "input:artifact:autolink",
        "input:artifact:coverage_audit",
        "input:artifact:probe",
        "input:artifact:cycle",
        "input:artifact:export",
        "input:artifact:validate",
    ]
    assert [event for event in events if event.startswith("contract:")] == [
        "contract:completion_paths",
        "contract:autolink_ready",
        "contract:owner_boundary_readonly",
        "contract:completion_readiness",
        "contract:completion_gates",
        "contract:completion_blockers",
        "contract:completion_actions",
        "contract:drilldown_context",
        "contract:action_drilldown",
        "contract:completion_route_map",
        "contract:entity_document_paths",
        "contract:entity_event_document_map",
        "contract:completion_route_packet_index",
        "contract:completion_action_backlog",
        "contract:audit_document_context",
        "contract:completion_audit_document",
    ]
    assert events[-1] == "persistence:write"


def test_completion_audit_orchestration_uses_body_fallback_and_skips_write(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    events: list[str] = []
    input_port, contract_port, persistence_port = _fixture_ports(
        paths,
        events,
        include_body_closure=False,
    )

    document = adapters.run_completion_audit(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T08:00:00-06:00",
        write_latest=False,
        paths=paths,
        input_port=input_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert document["ok"] is True
    assert events[0:2] == ["input:status", "input:body_closure"]
    assert "persistence:write" not in events


def test_completion_audit_orchestration_projects_write_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    events: list[str] = []
    error = {"operation": "write_latest", "error": "fixture-denied"}
    input_port, contract_port, persistence_port = _fixture_ports(
        paths,
        events,
        write_errors=[error],
    )

    document = adapters.run_completion_audit(
        schema_prefix="abyss_machine",
        version="0.test",
        generated_at="2026-07-10T08:00:00-06:00",
        write_latest=True,
        paths=paths,
        input_port=input_port,
        contract_port=contract_port,
        persistence_port=persistence_port,
    )

    assert document["ok"] is False
    assert document["status"] == "write_failed"
    assert document["write_errors"] == [error]
    assert document["summary"]["audit_ok"] is False
    assert events[-1] == "persistence:write"
