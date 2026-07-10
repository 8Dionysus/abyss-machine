from dataclasses import replace
from pathlib import Path

from abyss_machine import self_awareness_completion_contracts as completion_contracts


def _paths(tmp_path: Path) -> completion_contracts.CompletionAuditPaths:
    return completion_contracts.CompletionAuditPaths(
        completion_audit=tmp_path / "completion-audit/latest.json",
        coverage_audit=tmp_path / "coverage-audit/latest.json",
        autolink=tmp_path / "autolink/latest.json",
        validate=tmp_path / "validate/latest.json",
        cycle=tmp_path / "cycle/latest.json",
        requirement_probes=tmp_path / "requirement-probes/latest.json",
        stack_closure_dossier=tmp_path / "stack-closure-dossier/latest.json",
        working_stack=tmp_path / "working-stack/latest.json",
        activation_smoke=tmp_path / "activation-smoke/latest.json",
    )


def _readiness() -> completion_contracts.CompletionAuditReadiness:
    return completion_contracts.CompletionAuditReadiness(
        artifact_refs={"cycle": {"path": "/fixture/cycle/latest.json"}},
        missing_artifacts=[],
        validation_summary={"fails": 0},
        validate_green=True,
        cycle={"ok": True, "status": "complete", "summary": {"steps": 36}},
        cycle_green=True,
        coverage_audit={"ok": True, "incomplete_rows": []},
        coverage_summary={"incomplete": 0, "blocked_stack_owned": 1},
        coverage_green=True,
        coverage_incomplete=0,
        open_requirement_rows=[{"requirement_id": "stack.trace-backend"}],
        status_open_stack_requirements=1,
        requirement_probes_open=1,
        coverage_blocked_stack_owned=1,
        open_potential_rows=[{"service": "aoa-browser"}],
        working_stack_usage_gaps=1,
        activation_open_gaps=1,
        autolink_summary={
            "organ_links": 2,
            "organ_links_complete": 2,
            "stack_requirement_links": 1,
            "stack_requirement_links_complete": 1,
            "synthetic_scenarios": 1,
            "synthetic_scenarios_complete": 1,
        },
        autolink_complete=True,
        resource_preflight={"ok": True},
        owner_boundary_ok=True,
    )


def test_completion_readiness_builders_preserve_open_potential_and_owner_boundary(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    readiness = _readiness()

    gates = completion_contracts.completion_gates(
        schema_prefix="abyss_machine",
        readiness=readiness,
        paths=paths,
    )
    blockers = completion_contracts.completion_blockers(
        schema_prefix="abyss_machine",
        readiness=readiness,
        paths=paths,
    )

    assert len(gates) == 9
    gate_by_id = {gate["id"]: gate for gate in gates}
    assert gate_by_id["latest_artifacts_available"]["ok"] is True
    assert gate_by_id["no_open_stack_requirements"]["ok"] is False
    assert gate_by_id["no_working_stack_usage_gaps"]["ok"] is False
    assert gate_by_id["owner_boundary_readonly"]["ok"] is True

    blocker_by_id = {blocker["id"]: blocker for blocker in blockers}
    assert set(blocker_by_id) == {
        "abyss-stack.requirements.open",
        "abyss-stack.working-potential.open",
    }
    assert blocker_by_id["abyss-stack.requirements.open"]["owner_route"] == "abyss-stack"
    assert blocker_by_id["abyss-stack.requirements.open"]["count"] == 1
    assert blocker_by_id["abyss-stack.working-potential.open"]["count"] == 1
    assert all(blocker["policy"]["host_layer_mutates_stack"] is False for blocker in blockers)
    assert all(blocker["policy"]["executes_commands"] is False for blocker in blockers)


def test_completion_readiness_helpers_require_complete_counts_and_readonly_sources() -> None:
    autolink = {
        "ok": True,
        "state_digest": "digest-fixture",
        "summary": {
            "organ_links": 2,
            "organ_links_complete": 2,
            "stack_requirement_links": 1,
            "stack_requirement_links_complete": 1,
            "synthetic_scenarios": 3,
            "synthetic_scenarios_complete": 3,
        },
    }
    readonly = {"policy": {"host_layer_mutates_stack": False}}

    assert completion_contracts.completion_autolink_ready(autolink) is True
    autolink["summary"]["organ_links_complete"] = 1
    assert completion_contracts.completion_autolink_ready(autolink) is False
    assert completion_contracts.completion_owner_boundary_readonly(readonly, readonly, readonly) is True
    assert completion_contracts.completion_owner_boundary_readonly(
        readonly,
        {"policy": {"host_layer_mutates_stack": True}},
        readonly,
    ) is False


def test_completion_blockers_project_all_machine_owned_failure_classes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    readiness = replace(
        _readiness(),
        missing_artifacts=["cycle"],
        validate_green=False,
        cycle={"ok": False, "status": "resource_denied", "summary": {"failed_steps": 1}},
        cycle_green=False,
        coverage_audit={"ok": False, "incomplete_rows": [{"id": "coverage-fixture"}]},
        coverage_summary={"incomplete": 1, "blocked_stack_owned": 0},
        coverage_green=False,
        coverage_incomplete=1,
        open_requirement_rows=[],
        status_open_stack_requirements=0,
        requirement_probes_open=0,
        coverage_blocked_stack_owned=0,
        open_potential_rows=[],
        working_stack_usage_gaps=0,
        activation_open_gaps=0,
        autolink_complete=False,
        resource_preflight={"ok": False},
        owner_boundary_ok=False,
    )

    blockers = completion_contracts.completion_blockers(
        schema_prefix="abyss_machine",
        readiness=readiness,
        paths=paths,
    )

    assert [blocker["id"] for blocker in blockers] == [
        "self-awareness.latest-artifacts.missing",
        "self-awareness.validate.not-green",
        "self-awareness.cycle.not-green",
        "self-awareness.coverage.incomplete",
        "self-awareness.autolink.incomplete",
        "self-awareness.resource-guard.not-safe",
        "self-awareness.owner-boundary.not-readonly",
    ]
    assert blockers[0]["items"] == ["cycle"]
    assert blockers[3]["count"] == 1
    assert blockers[3]["items"] == [{"id": "coverage-fixture"}]
    assert all(blocker["owner_route"] == "abyss-machine" for blocker in blockers)


def test_completion_actions_rank_stable_core_routes_without_executing_them(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    actions = completion_contracts.completion_actions(
        schema_prefix="abyss_machine",
        open_requirement_rows=[
            {
                "requirement_id": "stack.database-graph.read-route",
                "blocking_check_keys": ["postgres", "neo4j"],
            },
            {
                "requirement_id": "stack.trace-backend",
                "blocking_check_keys": ["tempo"],
                "owner": "abyss-stack",
            },
        ],
        open_potential_rows=[
            {
                "service": "aoa-browser",
                "activation_gap_classification": "running_functional_smoke_failed",
                "closure_blocker_keys": ["browser_tool_probe"],
                "missing_checks": ["tool_roundtrip"],
            }
        ],
        resource_guard_ok=True,
        paths=paths,
    )

    assert [action["id"] for action in actions] == [
        "stack-requirement:stack.trace-backend",
        "stack-requirement:stack.database-graph.read-route",
        "working-stack:aoa-browser",
    ]
    assert [action["priority_rank"] for action in actions] == [1, 2, 3]
    assert actions[0]["priority_class"] == "critical_trace_join"
    assert actions[2]["priority_class"] == "browser_tool_runtime"
    assert actions[0]["drilldown_id"].startswith("sacompletiondrill-")
    assert actions[0]["evidence_refs"] == [
        {"path": str(paths.requirement_probes), "requirement_id": "stack.trace-backend"}
    ]
    assert actions[2]["evidence_refs"] == [
        {"path": str(paths.working_stack), "service": "aoa-browser"}
    ]
    assert all(action["resource_gate"]["current_audit_resource_guard_ok"] is True for action in actions)
    assert all(action["policy"]["executes_commands"] is False for action in actions)
    assert all(action["policy"]["actions_executed"] is False for action in actions)
