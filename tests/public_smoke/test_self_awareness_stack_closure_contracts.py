from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_stack_closure_contracts as closure


SCHEMA_PREFIX = "abyss_machine"
VERSION = "0.test"
NOW = "2026-07-10T09:00:00-06:00"


def _paths(tmp_path: Path) -> closure.SelfAwarenessStackClosurePaths:
    return closure.SelfAwarenessStackClosurePaths(
        requirements_latest=tmp_path / "requirements" / "latest.json",
        requirements_root=tmp_path / "requirements",
        capabilities_latest=tmp_path / "capabilities" / "latest.json",
        requirement_probes_latest=tmp_path / "requirement-probes" / "latest.json",
        requirement_probes_root=tmp_path / "requirement-probes",
        failure_matrix_latest=tmp_path / "failure-matrix" / "latest.json",
        brief_latest=tmp_path / "brief" / "latest.json",
        investigate_latest=tmp_path / "investigate" / "latest.json",
        replay_latest=tmp_path / "replay" / "latest.json",
        export_latest=tmp_path / "export" / "latest.json",
        validate_latest=tmp_path / "validate" / "latest.json",
        working_stack_latest=tmp_path / "working-stack" / "latest.json",
        stack_closure_dossier_latest=tmp_path / "stack-closure" / "latest.json",
        stack_closure_dossier_root=tmp_path / "stack-closure",
    )


def _requirements() -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_requirements_v1",
        "summary": {"stack_owned": 1},
        "requirements": [
            {
                "id": "stack.trace-backend",
                "title": "Trace backend",
                "owner": "abyss-stack",
            }
        ],
        "stack_handoff": [
            {
                "id": "stack.trace-backend",
                "owner": "abyss-stack",
                "machine_read_command": "abyss-machine self-awareness requirements --json",
            }
        ],
    }


def _probe() -> dict[str, Any]:
    return {
        "id": "stack.trace-backend",
        "requirement_id": "stack.trace-backend",
        "owner": "abyss-stack",
        "status": "closed",
        "closed_by_current_probe": True,
        "host_layer_mutates_stack": False,
        "probe_kind": "trace_backend",
        "source_handoff_command": "abyss-machine self-awareness requirements --json",
        "acceptance_contract": {"schema": "acceptance"},
        "acceptance_verifiers": [{"command": "abyss-machine self-awareness validate --json"}],
        "current_state": {"trace_backend_ready": True},
        "checks": [{"key": "trace_backend_ready", "ok": True, "level": "pass"}],
        "closure_readiness": {
            "schema": f"{SCHEMA_PREFIX}_stack_handoff_closure_readiness_v1",
            "readiness_score": 1.0,
            "fulfilled_checks": ["trace_backend_ready"],
            "missing_checks": [],
            "open_blocker_count": 0,
            "fulfilled_check_count": 1,
            "blocking_check_keys": [],
            "dependency_requirement_ids": [],
            "dependency_reasons": [],
            "closure_evidence_needed": [],
            "required_fields": ["trace_backend_ready"],
            "success_predicates": ["trace_backend_ready == true"],
            "redaction_rules": ["no raw spans"],
            "boundedness": {"bounded": True},
            "verifier_commands": ["abyss-machine self-awareness validate --json"],
            "safe_next_action": {"action": "verify"},
            "policy": {"host_layer_mutates_stack": False, "executes_commands": False},
        },
        "evidence_refs": [{"path": "/synthetic/trace.json"}],
        "runbook_candidate": {"id": "runbook-trace", "handoff_only": True},
    }


def _ports(
    tmp_path: Path,
) -> tuple[
    closure.SelfAwarenessStackClosurePaths,
    closure.SelfAwarenessStackClosureRuntimePort,
    closure.SelfAwarenessStackClosureRefreshPort,
    closure.SelfAwarenessStackClosureContractPort,
    list[str],
    list[str],
]:
    paths = _paths(tmp_path)
    writes: list[str] = []
    artifact_names: list[str] = []

    def write_latest_and_history(
        document: dict[str, Any], _: Path, __: Path
    ) -> list[str]:
        writes.append(str(document.get("schema")))
        return []

    def latest_artifact_ref(name: str, path: Path, schema: str) -> dict[str, Any]:
        artifact_names.append(name)
        return {"name": name, "path": str(path), "schema": schema, "exists": True}

    runtime_port = closure.SelfAwarenessStackClosureRuntimePort(
        now_iso=lambda: NOW,
        write_latest_and_history=write_latest_and_history,
    )
    refresh_port = closure.SelfAwarenessStackClosureRefreshPort(
        capabilities=lambda **_: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_capabilities_v1"
        },
        requirements=lambda **_: _requirements(),
        requirement_probes=lambda **_: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1",
            "summary": {"internal_contract_failures": [], "secret_leaks": 0, "mutating_routes": 0},
            "probes": [_probe()],
        },
        working_stack_activation_dossier=lambda *_args, **_kwargs: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_dossier_v1",
            "ok": True,
            "summary": {"activation_entries_complete": 0, "open_activation_gaps": 0},
            "entries": [],
            "working_stack_activation_handoff": {"activation_order": []},
        },
    )
    contract_port = closure.SelfAwarenessStackClosureContractPort(
        requirement_probe_evaluate=lambda *_: _probe(),
        requirements_with_probe_readiness=lambda document, _probes: {
            **document,
            "enriched_with_probe_readiness": True,
        },
        brief_stack_handoff_action_map=lambda _probes: {
            "actions": [
                {
                    "requirement_id": "stack.trace-backend",
                    "priority_class": "critical_trace_join",
                }
            ]
        },
        latest_artifact_ref=latest_artifact_ref,
        requirement_acceptance_contract=lambda _requirement: {"schema": "acceptance"},
        stack_requirement_coverage_impact=lambda requirement_id: {
            "schema": f"{SCHEMA_PREFIX}_self_awareness_stack_coverage_impact_v1",
            "requirement_id": requirement_id,
            "organ": "trace_join_backbone",
            "coverage_planes": ["signal_fabric"],
            "closure_value": "trace joins become readable",
            "proof_commands": ["abyss-machine self-awareness validate --json"],
            "policy": {
                "host_layer_mutates_stack": False,
                "executes_commands": False,
                "raw_secrets_included": False,
            },
        },
        stack_requirement_compat_contract=lambda *_args, **_kwargs: {
            "schema": "compat",
            "dependency_contract": {},
        },
        stack_compat_contract_complete=lambda _contract: True,
        stack_requirement_closure_acceptance=lambda entry, _generated_at: {
            "schema": "closure-acceptance",
            "requirement_id": entry["requirement_id"],
            "acceptance_id": "accept-trace",
            "complete": True,
            "stack_compat_requirement": {"requirement_id": "compat.trace"},
        },
        stack_requirement_closure_acceptance_complete=lambda packet: packet.get("complete") is True,
    )
    return paths, runtime_port, refresh_port, contract_port, writes, artifact_names


def test_requirement_probes_refreshes_inputs_and_persists_enriched_requirements(
    tmp_path: Path,
) -> None:
    paths, runtime_port, refresh_port, contract_port, writes, _ = _ports(tmp_path)

    document = closure.requirement_probes(
        write_latest=True,
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        paths=paths,
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
    )

    assert document["ok"] is True
    assert document["status"] == "satisfied"
    assert document["summary"]["closed_by_current_probe"] == 1
    assert writes == [
        f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1",
        f"{SCHEMA_PREFIX}_self_awareness_requirements_v1",
    ]


def test_stack_closure_dossier_assembles_handoff_and_artifact_refs(
    tmp_path: Path,
) -> None:
    paths, runtime_port, refresh_port, contract_port, writes, artifact_names = _ports(tmp_path)
    probe_document = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_requirement_probes_v1",
        "summary": {"internal_contract_failures": [], "secret_leaks": 0, "mutating_routes": 0},
        "probes": [_probe()],
    }

    document = closure.stack_closure_dossier(
        write_latest=True,
        requirements_doc=_requirements(),
        requirement_probes_doc=probe_document,
        working_stack_doc={"schema": "synthetic-working-stack"},
        schema_prefix=SCHEMA_PREFIX,
        version=VERSION,
        paths=paths,
        runtime_port=runtime_port,
        refresh_port=refresh_port,
        contract_port=contract_port,
    )

    assert document["ok"] is True
    assert document["status"] == "satisfied"
    assert document["summary"]["dossier_entries_complete"] == 1
    assert document["policy"]["host_layer_mutates_stack"] is False
    assert document["policy"]["executes_commands"] is False
    assert artifact_names == [
        "requirements",
        "requirement_probes",
        "failure_matrix",
        "brief",
        "investigate",
        "replay",
        "export",
        "validate",
        "working_stack",
    ]
    assert writes == [f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1"]


@pytest.mark.parametrize(
    ("cli_name", "module_name", "kwargs"),
    [
        ("self_awareness_requirement_probes", "requirement_probes", {}),
        ("self_awareness_stack_closure_dossier", "stack_closure_dossier", {}),
    ],
)
def test_cli_stack_closure_commands_only_bind_current_ports(
    monkeypatch: pytest.MonkeyPatch,
    cli_name: str,
    module_name: str,
    kwargs: dict[str, Any],
) -> None:
    captured: dict[str, Any] = {}

    def fake_command(**call_kwargs: Any) -> dict[str, Any]:
        captured.update(call_kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(closure, module_name, fake_command)

    result = getattr(cli, cli_name)(write_latest=False, **kwargs)

    assert result == {"schema": "synthetic"}
    assert captured["write_latest"] is False
    assert isinstance(captured["paths"], closure.SelfAwarenessStackClosurePaths)
    assert isinstance(captured["runtime_port"], closure.SelfAwarenessStackClosureRuntimePort)
    assert isinstance(captured["refresh_port"], closure.SelfAwarenessStackClosureRefreshPort)
    assert isinstance(captured["contract_port"], closure.SelfAwarenessStackClosureContractPort)
