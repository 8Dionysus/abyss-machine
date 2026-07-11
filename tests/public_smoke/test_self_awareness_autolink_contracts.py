from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abyss_machine import self_awareness_autolink_contracts as autolink


def _paths(tmp_path: Path) -> autolink.SelfAwarenessAutolinkPaths:
    fields = autolink.SelfAwarenessAutolinkPaths.__dataclass_fields__
    return autolink.SelfAwarenessAutolinkPaths(
        **{name: tmp_path / name.replace("_", "-") for name in fields}
    )


def _documents(
    paths: autolink.SelfAwarenessAutolinkPaths,
) -> dict[Path, dict[str, Any]]:
    return {
        paths.working_stack_latest: {
            "schema": "abyss_machine_self_awareness_working_stack_inventory_v1",
        },
        paths.coverage_audit_latest: {
            "schema": "abyss_machine_self_awareness_objective_coverage_audit_v1",
            "working_stack_link_integrity": {
                "rows": [{"service": "route-api"}],
            },
        },
        paths.stack_closure_dossier_latest: {
            "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
            "working_stack_activation_dossier": {
                "entries": [{"service": "route-api"}],
            },
        },
        paths.activation_smoke_latest: {
            "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1",
        },
        paths.episodes_latest: {
            "schema": "abyss_machine_self_awareness_episodes_v1",
        },
        paths.autolink_latest: {
            "schema": "abyss_machine_self_awareness_autolink_v1",
            "state_digest": "previous",
        },
    }


def _contract_port(
    captured: dict[str, Any],
) -> autolink.SelfAwarenessAutolinkContractPort:
    def build(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "schema": "abyss_machine_self_awareness_autolink_v1",
            "ok": True,
            "policy": {"host_layer_mutates_stack": False},
        }

    return autolink.SelfAwarenessAutolinkContractPort(
        working_stack_links_match_stable_identity=lambda _doc: True,
        link_integrity_matrix_complete=lambda _doc: True,
        link_integrity_matches_working_stack=lambda _working, _links: True,
        activation_entries_from_link_rows=lambda rows: [
            {"service": row["service"]} for row in rows
        ],
        activation_entries_cover_expected=lambda _actual, _expected: True,
        activation_smoke_needs_refresh=lambda _doc, _entries: False,
        episodes_cover_stack_requirements=lambda _episodes, _dossier: True,
        autolink_document=build,
        activation_smoke_compact=lambda row: {"service": row.get("service")},
        stack_requirement_closure_acceptance_complete=lambda _row: True,
        stack_coverage_impact_complete=lambda _row: True,
    )


def _refresh_port(**overrides: Any) -> autolink.SelfAwarenessAutolinkRefreshPort:
    defaults = {
        "working_stack_inventory": lambda **_kwargs: pytest.fail(
            "complete working-stack input must be reused"
        ),
        "dependent_readmodels": lambda **_kwargs: pytest.fail(
            "complete dependencies must be reused"
        ),
        "objective_coverage_audit": lambda **_kwargs: pytest.fail(
            "complete coverage input must be reused"
        ),
        "stack_closure_dossier": lambda **_kwargs: pytest.fail(
            "complete dossier input must be reused"
        ),
        "activation_smoke": lambda **_kwargs: pytest.fail(
            "complete activation smoke must be reused"
        ),
        "episodes": lambda **_kwargs: pytest.fail(
            "complete episodes must be reused"
        ),
    }
    defaults.update(overrides)
    return autolink.SelfAwarenessAutolinkRefreshPort(**defaults)


def test_autolink_reuses_complete_inputs_and_persists(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)
    captured: dict[str, Any] = {}
    writes: list[tuple[Path, Path]] = []

    result = autolink.autolink(
        cycle_id="cycle-1",
        probe_run_id="probe-1",
        working_stack_doc=documents[paths.working_stack_latest],
        coverage_audit_doc=documents[paths.coverage_audit_latest],
        stack_closure_dossier_doc=documents[paths.stack_closure_dossier_latest],
        activation_smoke_doc=documents[paths.activation_smoke_latest],
        paths=paths,
        config=autolink.SelfAwarenessAutolinkConfig("abyss_machine", "test"),
        runtime_port=autolink.SelfAwarenessAutolinkRuntimePort(
            load_latest_json=lambda path, _schema: documents[path],
            now_iso=lambda: "2026-07-11T12:00:00Z",
            write_latest_and_history=lambda _data, latest, root: writes.append(
                (latest, root)
            )
            or [],
        ),
        refresh_port=_refresh_port(),
        contract_port=_contract_port(captured),
    )

    assert result["ok"] is True
    assert captured["working_stack_doc"] is documents[paths.working_stack_latest]
    assert captured["coverage_audit_doc"] is documents[paths.coverage_audit_latest]
    assert captured["dependency_refresh"] == {}
    assert captured["previous"] is documents[paths.autolink_latest]
    assert captured["cycle_id"] == "cycle-1"
    assert captured["probe_run_id"] == "probe-1"
    assert writes == [(paths.autolink_latest, paths.autolink_root)]


def test_autolink_refreshes_stale_chain_in_dependency_order(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = {path: {} for path in _documents(paths)}
    calls: list[str] = []
    captured: dict[str, Any] = {}

    fresh_working = {
        "schema": "abyss_machine_self_awareness_working_stack_inventory_v1"
    }
    fresh_coverage = {
        "schema": "abyss_machine_self_awareness_objective_coverage_audit_v1",
        "working_stack_link_integrity": {"rows": [{"service": "route-api"}]},
    }
    fresh_dossier = {
        "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
        "working_stack_activation_dossier": {
            "entries": [{"service": "route-api"}]
        },
    }
    fresh_smoke = {
        "schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1"
    }
    fresh_episodes = {"schema": "abyss_machine_self_awareness_episodes_v1"}

    def inventory(**_kwargs: Any) -> dict[str, Any]:
        calls.append("working_stack_inventory")
        documents[paths.working_stack_latest] = fresh_working
        return fresh_working

    def dependent(**_kwargs: Any) -> dict[str, Any]:
        calls.append("dependent_readmodels")
        return {"schema": "dependency-refresh", "ok": True}

    contract_port = _contract_port(captured)
    contract_port = autolink.SelfAwarenessAutolinkContractPort(
        **{
            **contract_port.__dict__,
            "working_stack_links_match_stable_identity": lambda doc: doc
            is fresh_working,
            "link_integrity_matrix_complete": lambda doc: doc
            is fresh_coverage["working_stack_link_integrity"],
            "activation_smoke_needs_refresh": lambda doc, _entries: doc
            is not fresh_smoke,
            "episodes_cover_stack_requirements": lambda episodes, _dossier: episodes
            is fresh_episodes,
        }
    )

    result = autolink.autolink(
        write_latest=False,
        paths=paths,
        config=autolink.SelfAwarenessAutolinkConfig("abyss_machine", "test"),
        runtime_port=autolink.SelfAwarenessAutolinkRuntimePort(
            load_latest_json=lambda path, _schema: documents[path],
            now_iso=lambda: "2026-07-11T12:00:00Z",
            write_latest_and_history=lambda *_args: pytest.fail(
                "write_latest=False must not persist"
            ),
        ),
        refresh_port=_refresh_port(
            working_stack_inventory=inventory,
            dependent_readmodels=dependent,
            objective_coverage_audit=lambda **_kwargs: calls.append(
                "objective_coverage_audit"
            )
            or fresh_coverage,
            stack_closure_dossier=lambda **_kwargs: calls.append(
                "stack_closure_dossier"
            )
            or fresh_dossier,
            activation_smoke=lambda **_kwargs: calls.append("activation_smoke")
            or fresh_smoke,
            episodes=lambda **_kwargs: calls.append("episodes") or fresh_episodes,
        ),
        contract_port=contract_port,
    )

    assert result["ok"] is True
    assert calls == [
        "working_stack_inventory",
        "dependent_readmodels",
        "objective_coverage_audit",
        "stack_closure_dossier",
        "activation_smoke",
        "episodes",
    ]
    assert captured["dependency_refresh"] == {
        "schema": "dependency-refresh",
        "ok": True,
    }


def test_autolink_projects_persistence_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    documents = _documents(paths)

    result = autolink.autolink(
        working_stack_doc=documents[paths.working_stack_latest],
        coverage_audit_doc=documents[paths.coverage_audit_latest],
        stack_closure_dossier_doc=documents[paths.stack_closure_dossier_latest],
        activation_smoke_doc=documents[paths.activation_smoke_latest],
        paths=paths,
        config=autolink.SelfAwarenessAutolinkConfig("abyss_machine", "test"),
        runtime_port=autolink.SelfAwarenessAutolinkRuntimePort(
            load_latest_json=lambda path, _schema: documents[path],
            now_iso=lambda: "2026-07-11T12:00:00Z",
            write_latest_and_history=lambda *_args: ["disk-full"],
        ),
        refresh_port=_refresh_port(),
        contract_port=_contract_port({}),
    )

    assert result["ok"] is False
    assert result["write_errors"] == ["disk-full"]
