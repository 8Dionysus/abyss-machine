from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_failure_matrix_contracts as failure_matrix


def _paths(tmp_path: Path) -> failure_matrix.SelfAwarenessFailureMatrixPaths:
    return failure_matrix.SelfAwarenessFailureMatrixPaths(
        capabilities_latest=tmp_path / "capabilities" / "latest.json",
        requirements_latest=tmp_path / "requirements" / "latest.json",
        requirement_probes_latest=tmp_path / "requirement-probes" / "latest.json",
        stack_observability_latest=tmp_path / "stack-observability" / "latest.json",
        collect_latest=tmp_path / "collect" / "latest.json",
        rag_validate_latest=tmp_path / "rag-validate" / "latest.json",
        llm_resident_status_latest=tmp_path / "resident" / "status" / "latest.json",
        nervous_brief_latest=tmp_path / "nervous-brief" / "latest.json",
        nervous_semantic_maintain_latest=tmp_path / "semantic-maintain" / "latest.json",
        typing_validate_latest=tmp_path / "typing-validate" / "latest.json",
        context_latest=tmp_path / "context" / "latest.json",
        validate_latest=tmp_path / "validate" / "latest.json",
        failure_matrix_latest=tmp_path / "failure-matrix" / "latest.json",
        failure_matrix_root=tmp_path / "failure-matrix",
    )


def _config() -> failure_matrix.SelfAwarenessFailureMatrixConfig:
    return failure_matrix.SelfAwarenessFailureMatrixConfig(
        schema_prefix="abyss_machine",
        version="0.test",
        unbounded_labels=("request_id", "trace_id"),
        semantic_maintain_review_command="abyss-machine nervous semantic-maintain --json",
        semantic_maintain_retry_command="abyss-machine nervous semantic-maintain --apply --json",
    )


def test_failure_matrix_reads_bounded_latest_inputs_and_persists_complete_rows(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    reads: list[Path] = []
    writes: list[tuple[str, Path, Path]] = []
    refresh_calls: list[bool] = []

    documents = {
        paths.requirements_latest: {
            "schema": "abyss_machine_self_awareness_requirements_v1",
            "requirements": [],
        },
        paths.requirement_probes_latest: {
            "schema": "abyss_machine_self_awareness_requirement_probes_v1",
            "probes": [],
        },
        paths.stack_observability_latest: {
            "schema": "abyss_machine_stack_observability_v1",
            "summary": {"promql_jobs_up": []},
        },
        paths.collect_latest: {
            "schema": "abyss_machine_self_awareness_collect_v1",
            "summary": {"degraded_sources": []},
        },
        paths.rag_validate_latest: {"schema": "abyss_machine_rag_validate_v1"},
        paths.llm_resident_status_latest: {
            "schema": "abyss_machine_gemma4_spark_resident_status_v1",
            "status": "absent",
        },
        paths.nervous_brief_latest: {"schema": "abyss_machine_nervous_brief_v1"},
        paths.nervous_semantic_maintain_latest: {
            "schema": "abyss_machine_nervous_semantic_maintain_v1",
            "decision": "not_needed",
        },
        paths.typing_validate_latest: {"schema": "abyss_machine_typing_validate_v1"},
        paths.context_latest: {
            "schema": "abyss_machine_self_awareness_context_v1",
            "summary": {"forbidden_loki_labels": []},
        },
    }

    def load_latest_json(path: Path, _schema: str) -> dict[str, Any]:
        reads.append(path)
        return documents.get(path, {})

    def write_latest_and_history(
        document: dict[str, Any], latest: Path, root: Path
    ) -> list[str]:
        writes.append((str(document.get("schema")), latest, root))
        return []

    def refresh_capabilities(*, write_latest: bool = True) -> dict[str, Any]:
        refresh_calls.append(write_latest)
        return {
            "schema": "abyss_machine_self_awareness_capabilities_v1",
            "raw": {},
        }

    document = failure_matrix.failure_matrix(
        write_latest=True,
        paths=paths,
        config=_config(),
        runtime_port=failure_matrix.SelfAwarenessFailureMatrixRuntimePort(
            load_latest_json=load_latest_json,
            now_iso=lambda: "2026-07-10T10:00:00-06:00",
            write_latest_and_history=write_latest_and_history,
        ),
        refresh_port=failure_matrix.SelfAwarenessFailureMatrixRefreshPort(
            capabilities=refresh_capabilities,
        ),
    )

    assert document["ok"] is True
    assert document["status"] == "covered"
    assert document["summary"]["requirements_rows"] == 4
    assert document["summary"]["missing_required"] == []
    assert document["summary"]["malformed"] == []
    assert refresh_calls == [True]
    assert reads == [
        paths.capabilities_latest,
        paths.requirements_latest,
        paths.requirement_probes_latest,
        paths.stack_observability_latest,
        paths.collect_latest,
        paths.rag_validate_latest,
        paths.llm_resident_status_latest,
        paths.nervous_brief_latest,
        paths.nervous_semantic_maintain_latest,
        paths.typing_validate_latest,
        paths.context_latest,
    ]
    assert writes == [
        (
            "abyss_machine_self_awareness_failure_matrix_v1",
            paths.failure_matrix_latest,
            paths.failure_matrix_root,
        )
    ]
    assert all(row["host_layer_mutates_stack"] is False for row in document["rows"])
    assert all(row["automatic_remediation"] is False for row in document["rows"])


def test_cli_failure_matrix_only_binds_current_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_failure_matrix(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic"}

    monkeypatch.setattr(failure_matrix, "failure_matrix", fake_failure_matrix)

    document = cli.self_awareness_failure_matrix(write_latest=False)

    assert document == {"schema": "synthetic"}
    assert captured["write_latest"] is False
    assert isinstance(captured["paths"], failure_matrix.SelfAwarenessFailureMatrixPaths)
    assert isinstance(captured["config"], failure_matrix.SelfAwarenessFailureMatrixConfig)
    assert isinstance(
        captured["runtime_port"],
        failure_matrix.SelfAwarenessFailureMatrixRuntimePort,
    )
    assert isinstance(
        captured["refresh_port"],
        failure_matrix.SelfAwarenessFailureMatrixRefreshPort,
    )


def test_failure_matrix_fixture_builds_required_rows_without_host_io(
    tmp_path: Path,
) -> None:
    document = failure_matrix.failure_matrix_fixture(
        generated_at="2026-07-11T09:00:00-06:00",
        paths=_paths(tmp_path),
        config=_config(),
    )

    row_ids = {
        str(row.get("id"))
        for row in document.get("rows", [])
        if isinstance(row, dict)
    }
    assert document["schema"] == "abyss_machine_self_awareness_failure_matrix_v1"
    assert {
        "machine.resource-denial",
        "machine.secret-redaction",
        "stack.downtime-bounded-readonly",
    }.issubset(row_ids)
    assert document["summary"]["missing_required"] == []
    assert all(row["host_layer_mutates_stack"] is False for row in document["rows"])
