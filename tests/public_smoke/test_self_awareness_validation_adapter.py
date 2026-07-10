from __future__ import annotations

from pathlib import Path
from typing import Any

from abyss_machine import self_awareness_adapters as adapters


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
