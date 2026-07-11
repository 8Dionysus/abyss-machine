from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_adapters as adapters
from abyss_machine import self_awareness_validation_contracts as validation_contracts


def _latest_paths(root: Path) -> dict[str, Path]:
    names = {name for name, _schema in adapters.READMODEL_SCHEMA_SUFFIXES}
    names.add("completion_audit")
    return {name: root / name / "latest.json" for name in names}


def _paths(root: Path) -> adapters.SelfAwarenessValidationPaths:
    return adapters.SelfAwarenessValidationPaths(
        document=root / "SELF_AWARENESS.md",
        agent_card=root / "AGENTS.md",
        roots={
            "root": root,
            "events": root / "events",
            "validate": root / "validate",
            "cycle": root / "cycle",
        },
        latest=_latest_paths(root),
        validate_latest=root / "validate" / "latest.json",
        validate_history_root=root / "validate",
    )


def _refresh_port(calls: list[str]) -> adapters.SelfAwarenessValidationRefreshPort:
    def refresh(name: str):
        def run() -> dict[str, Any]:
            calls.append(name)
            return {"schema": f"fixture_{name}_v1", "ok": True}

        return run

    return adapters.SelfAwarenessValidationRefreshPort(
        capabilities=refresh("capabilities"),
        requirement_probes=refresh("requirement_probes"),
        failure_matrix=refresh("failure_matrix"),
        working_stack=refresh("working_stack"),
        collect=refresh("collect"),
        query_latest=refresh("query"),
        correlation=refresh("correlation"),
        timeline=refresh("timeline"),
        spatial_graph=refresh("spatial_graph"),
        context=refresh("context"),
        episodes=refresh("episodes"),
        trace_context=refresh("trace_context"),
        alerts=refresh("alerts"),
        investigate_latest=refresh("investigate"),
        replay=refresh("replay"),
        brief=refresh("brief"),
        stack_closure_dossier=refresh("stack_closure_dossier"),
        activation_smoke=refresh("activation_smoke"),
        autolink=refresh("autolink"),
        completion_audit=refresh("completion_audit"),
        export=refresh("export"),
        cycle=refresh("cycle"),
        coverage_audit=refresh("coverage_audit"),
    )


def _runtime_port(calls: list[tuple[Any, ...]]) -> adapters.SelfAwarenessValidationRuntimePort:
    def add_path_exists(
        checks: list[dict[str, Any]],
        key: str,
        path: Path,
        kind: str,
        *,
        required: bool,
    ) -> None:
        calls.append(("path", key, path, kind, required))
        checks.append({"key": key, "status": "ok"})

    def validate_json_file(
        checks: list[dict[str, Any]],
        key: str,
        path: Path,
        schema: str,
        *,
        required: bool,
    ) -> dict[str, Any]:
        calls.append(("json", key, path, schema, required))
        checks.append({"key": key, "status": "ok"})
        return {"schema": schema, "ok": True}

    def history_status(path: Path) -> dict[str, Any]:
        calls.append(("history", path))
        return {"exists": True, "invalid": 0, "checked": 1}

    def daily_jsonl_path(root: Path) -> Path:
        calls.append(("daily_path", root))
        return root / "2026-07-10.jsonl"

    def add_check(
        checks: list[dict[str, Any]],
        status: str,
        key: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        calls.append(("check", status, key, message, data))
        checks.append({"key": key, "status": status})

    return adapters.SelfAwarenessValidationRuntimePort(
        add_path_exists=add_path_exists,
        validate_json_file=validate_json_file,
        history_status=history_status,
        daily_jsonl_path=daily_jsonl_path,
        add_check=add_check,
    )


def test_validation_intake_preserves_refresh_and_latest_history_order(tmp_path: Path) -> None:
    refresh_calls: list[str] = []
    runtime_calls: list[tuple[Any, ...]] = []
    paths = _paths(tmp_path)

    intake = adapters.run_validation_intake(
        schema_prefix="abyss_machine",
        refresh=True,
        require_cycle=True,
        paths=paths,
        refresh_port=_refresh_port(refresh_calls),
        runtime_port=_runtime_port(runtime_calls),
    )

    expected_refresh = [
        "capabilities",
        "requirement_probes",
        "failure_matrix",
        "working_stack",
        "collect",
        "query",
        "correlation",
        "timeline",
        "spatial_graph",
        "context",
        "episodes",
        "trace_context",
        "alerts",
        "investigate",
        "replay",
        "brief",
        "stack_closure_dossier",
        "activation_smoke",
        "autolink",
        "completion_audit",
        "export",
        "cycle",
        "coverage_audit",
    ]
    expected_specs = adapters.validation_latest_specs(
        schema_prefix="abyss_machine",
        paths=paths.latest,
        require_cycle=True,
    )

    assert refresh_calls == expected_refresh
    assert intake.refresh_steps == tuple(expected_refresh)
    assert [call[1] for call in runtime_calls if call[0] == "path"] == [
        "doc:self_awareness",
        "agent_card",
        "dir:root",
        "dir:events",
        "dir:validate",
        "dir:cycle",
    ]
    assert [call[1] for call in runtime_calls if call[0] == "json"] == [
        f"json:{spec.name}" for spec in expected_specs
    ]
    assert [call[2] for call in runtime_calls if call[0] == "check"] == [
        f"history:{spec.name}" for spec in expected_specs
    ]
    assert list(intake.documents) == [spec.name for spec in expected_specs]
    assert all(call[1] == "ok" for call in runtime_calls if call[0] == "check")


def test_validation_intake_without_refresh_or_cycle_stays_read_only(tmp_path: Path) -> None:
    refresh_calls: list[str] = []
    runtime_calls: list[tuple[Any, ...]] = []

    intake = adapters.run_validation_intake(
        schema_prefix="abyss_machine",
        refresh=False,
        require_cycle=False,
        paths=_paths(tmp_path),
        refresh_port=_refresh_port(refresh_calls),
        runtime_port=_runtime_port(runtime_calls),
    )

    assert refresh_calls == []
    assert intake.refresh_steps == ()
    assert "cycle" not in intake.documents
    assert "dir:cycle" not in [call[1] for call in runtime_calls if call[0] == "path"]


def test_validation_persistence_is_optional_and_fails_closed(tmp_path: Path) -> None:
    writes: list[tuple[Path, Path]] = []
    paths = _paths(tmp_path)

    def write_latest_and_history(
        _document: dict[str, Any],
        latest: Path,
        history_root: Path,
    ) -> list[dict[str, Any]]:
        writes.append((latest, history_root))
        return [{"stage": "latest", "error": "fixture write failure"}]

    port = adapters.SelfAwarenessValidationPersistencePort(
        write_latest_and_history=write_latest_and_history,
    )
    no_write = {"schema": "fixture", "ok": True}
    assert adapters.persist_validation_document(
        no_write,
        write_latest=False,
        paths=paths,
        persistence_port=port,
    ) == no_write
    assert writes == []

    written = adapters.persist_validation_document(
        {"schema": "fixture", "ok": True},
        write_latest=True,
        paths=paths,
        persistence_port=port,
    )
    assert writes == [(paths.validate_latest, paths.validate_history_root)]
    assert written["ok"] is False
    assert written["write_errors"] == [{"stage": "latest", "error": "fixture write failure"}]


def test_cli_validation_binds_intake_contract_and_persistence_ports(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_intake(**kwargs: Any) -> adapters.SelfAwarenessValidationIntake:
        calls["intake"] = kwargs
        return adapters.SelfAwarenessValidationIntake(
            checks=[{"key": "fixture", "status": "ok"}],
            documents={"fixture": {"schema": "fixture_latest_v1"}},
            refresh_steps=("fixture",),
        )

    def fake_build(**kwargs: Any) -> dict[str, Any]:
        calls["build"] = kwargs
        return {
            "schema": "abyss_machine_self_awareness_validate_v1",
            "ok": True,
            "summary": {"status": "ok", "checks": 1, "fails": 0, "warnings": 0},
        }

    def fake_persist(document: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls["persist"] = {"document": document, **kwargs}
        return document

    monkeypatch.setattr(adapters, "run_validation_intake", fake_intake)
    monkeypatch.setattr(validation_contracts, "build_validation_document", fake_build)
    monkeypatch.setattr(adapters, "persist_validation_document", fake_persist)

    result = cli.self_awareness_validate(
        strict=True,
        write_latest=False,
        refresh=True,
        require_cycle=False,
        allow_probe_refresh=True,
    )

    assert result["schema"] == "abyss_machine_self_awareness_validate_v1"
    assert calls["intake"]["refresh"] is True
    assert calls["intake"]["require_cycle"] is False
    assert calls["intake"]["runtime_port"].validate_json_file is cli.topology_validate_json_file
    build = calls["build"]
    assert build["strict"] is True
    assert build["allow_probe_refresh"] is True
    assert build["checks"] == [{"key": "fixture", "status": "ok"}]
    assert build["loaded"] == {"fixture": {"schema": "fixture_latest_v1"}}
    assert build["constants"].stack_user_source_root == cli.ABYSS_STACK_USER_SOURCE_ROOT
    assert build["constants"].requirement_probes_latest == cli.SELF_AWARENESS_REQUIREMENT_PROBES_LATEST_PATH
    assert build["repair_port"].requirement_probes is cli.self_awareness_requirement_probes
    assert build["repair_port"].objective_coverage_audit is cli.self_awareness_objective_coverage_audit
    assert build["repair_port"].probe is cli.self_awareness_probe
    assert build["contract_port"].add_check is cli.topology_validation_add
    assert build["contract_port"].coverage_audit_blocker_linkage_issues is cli.self_awareness_coverage_audit_blocker_linkage_issues
    assert build["contract_port"].validate_document_from_checks is cli.self_awareness_validate_document_from_checks
    assert calls["persist"]["write_latest"] is False
    assert calls["persist"]["persistence_port"].write_latest_and_history is cli.write_latest_and_history


def test_installed_self_tests_are_hermetic_from_live_host_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_live_io(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("synthetic self-tests reached live host IO")

    for name in (
        "self_awareness_query",
        "self_awareness_failure_matrix",
        "self_awareness_load_events",
        "self_awareness_spatial_graph",
        "self_awareness_capabilities",
        "load_latest_json",
        "write_latest_and_history",
    ):
        monkeypatch.setattr(cli, name, unexpected_live_io)

    checks = cli.self_awareness_self_tests()
    by_key = {str(check.get("key")): check for check in checks}

    assert len(checks) >= 14
    assert all(check.get("level") == "ok" for check in checks)
    assert "fixture_bounded_query_builders" in by_key
    assert "fixture_failure_matrix_required_rows" in by_key
    assert "fixture_redaction" in by_key


def test_cli_self_tests_only_bind_validation_fixture_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_self_tests(**kwargs: Any) -> list[dict[str, Any]]:
        captured.update(kwargs)
        return [{"key": "fixture", "status": "ok"}]

    monkeypatch.setattr(validation_contracts, "self_tests", fake_self_tests)

    checks = cli.self_awareness_self_tests()

    assert checks == [{"key": "fixture", "status": "ok"}]
    assert isinstance(captured["now_utc"], dt.datetime)
    assert captured["now_utc"].tzinfo is not None
    assert isinstance(
        captured["contract_port"],
        validation_contracts.SelfAwarenessSelfTestPort,
    )
