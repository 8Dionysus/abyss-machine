from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import context_contracts


def test_graph_query_and_index_are_portable_read_models(tmp_path: Path) -> None:
    graph = {
        "summary": {"nodes": 3, "edges": 2},
        "nodes": [
            context_contracts.graph_node("machine", "root", "Abyss Machine"),
            context_contracts.graph_node("subsystem:maps", "subsystem", "maps"),
            context_contracts.graph_node("subsystem:rag", "subsystem", "rag"),
        ],
        "edges": [
            context_contracts.graph_edge("machine", "subsystem:maps", "has_subsystem"),
            context_contracts.graph_edge("subsystem:maps", "subsystem:rag", "feeds"),
        ],
    }
    query = context_contracts.graph_query_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        query="maps",
        graph=graph,
    )
    assert query["schema"] == "abyss_machine_graph_query_v1"
    assert query["summary"] == {"nodes": 1, "edges": 2}
    assert {edge["relation"] for edge in query["edges"]} == {"has_subsystem", "feeds"}

    index = context_contracts.graph_index_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        graph_root=tmp_path / "graph",
        latest_path=tmp_path / "graph" / "latest.json",
        validate_latest_path=tmp_path / "graph" / "validate" / "latest.json",
        graph=graph,
    )
    assert index["schema"] == "abyss_machine_graph_index_v1"
    assert index["commands"]["validate"] == ["abyss-machine", "graph", "validate", "--json"]
    assert index["latest_summary"] == {"nodes": 3, "edges": 2}


def test_graph_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T13:40:00Z"
    checks = [
        {"level": "ok", "key": "required_nodes", "message": "required graph nodes present", "data": {"missing": []}},
        {"level": "warn", "key": "bridge_commands_represented", "message": "graph command nodes lag bridge", "data": {"bridge_commands": 12, "command_nodes": 10}},
    ]
    graph_summary = {"nodes": 18, "edges": 31}
    expected = context_contracts.graph_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        graph_summary=graph_summary,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.graph_validate_document_from_checks(
        checks,
        strict=True,
        graph_summary=graph_summary,
    ) == expected
    assert expected["schema"] == "abyss_machine_graph_validate_v1"
    assert expected["scope"] == "machine graph"
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["ok"] is False
    assert expected["graph_summary"] == graph_summary
    assert expected["policy"]["read_only"] is True


def test_maps_packet_preserves_context_boundary_contract(tmp_path: Path) -> None:
    entry = context_contracts.maps_entry(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        axis="by-eval-packet",
        label="machine RAG eval latest",
        route="Open eval",
        summary="Evaluation material is host-side evidence.",
        evidence_refs=[{"path": str(tmp_path / "eval.json"), "truth_level": "eval_packet"}],
        tags=["eval_packet"],
    )
    assert entry["truth_status"] == "generated_route_signal_not_source_truth"
    assert entry["policy"]["automatic_action"] is False

    query = context_contracts.maps_query_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        axis="by-eval-packet",
        query="RAG",
        entries_by_axis={"by-eval-packet": [entry]},
    )
    packet = context_contracts.maps_packet_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        axis="by-eval-packet",
        query="RAG",
        reader_profile="agent",
        limit=20,
        consumer="aoa-evals",
        query_result=query,
        maps_doc_path=tmp_path / "MAPS.md",
        maps_policy_path=tmp_path / "maps-policy.json",
        maps_latest_path=tmp_path / "maps" / "latest.json",
    )
    assert packet["schema"] == "abyss_machine_maps_packet_v1"
    assert packet["reader_profile"] == "proof-context"
    assert packet["summary"]["entries"] == 1
    assert packet["summary"]["automatic_action"] is False
    assert packet["summary"]["proof_verdict"] is False
    assert packet["summary"]["memory_writeback"] is False
    assert packet["summary"]["kag_truth_publication"] is False
    assert "does not deliver evidence into AoA organs" in packet["authority_boundary"]["non_claims"]
    assert packet["policy"]["consumers_are_context_labels_not_destinations"] is True


def test_maps_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T13:55:00Z"
    checks = [
        {"level": "ok", "key": "axis_indexes", "message": "all required atlas axis indexes exist", "data": {"missing": []}},
        {"level": "warn", "key": "axis_entries", "message": "some atlas axes have no generated entries", "data": {"empty_axes": ["by-owner"]}},
    ]
    maps_summary = {
        "axes": 5,
        "entries": 14,
        "automatic_action": False,
        "automatic_response": False,
    }
    expected = context_contracts.maps_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=False,
        maps_summary=maps_summary,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.maps_validate_document_from_checks(
        checks,
        strict=False,
        maps_summary=maps_summary,
    ) == expected
    assert expected["schema"] == "abyss_machine_maps_validate_v1"
    assert expected["scope"] == "machine atlas maps"
    assert expected["ok"] is True
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["maps_summary"] == maps_summary
    assert expected["truth_status"] == "generated_route_signal_not_source_truth"
    assert "do not authorize automatic action" in expected["non_claims"][1]


def test_rag_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T14:10:00Z"
    checks = [
        {"level": "ok", "key": "trace_contract", "message": "latest/sample RAG trace schema is current", "data": {"schema": "abyss_machine_rag_trace_v1"}},
        {"level": "warn", "key": "unit:context_refresh_timer_enabled", "message": "context refresh timer is not enabled", "data": {"is_enabled": False}},
    ]
    paths = {
        "schema": "abyss_machine_rag_paths_v1",
        "commands": {"validate": "abyss-machine rag validate --json"},
    }
    latest_trace = {"trace_id": "rag:abc", "summary": {"packet_entries": 3, "evidence_opened": 2}}
    latest_eval = {"ok": True, "summary": {"status": "ok", "fails": 0, "warnings": 0}}
    expected = context_contracts.rag_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        paths=paths,
        latest_trace=latest_trace,
        latest_eval=latest_eval,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.rag_validate_document_from_checks(
        checks,
        strict=True,
        paths=paths,
        latest_trace=latest_trace,
        latest_eval=latest_eval,
    ) == expected
    assert expected["schema"] == "abyss_machine_rag_validate_v1"
    assert expected["scope"] == "machine RAG trace loop"
    assert expected["ok"] is False
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["latest_trace"]["trace_id"] == "rag:abc"
    assert expected["latest_trace"]["summary"] == {"packet_entries": 3, "evidence_opened": 2}
    assert expected["latest_eval"]["ok"] is True
    assert "do not create proof verdicts" in expected["non_claims"][1]


def test_rag_eval_missing_trace_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T15:25:00Z"
    expected = context_contracts.rag_eval_missing_trace_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        trace_latest_path=cli.RAG_TRACE_LATEST_PATH,
        error="missing",
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.rag_eval_missing_trace_document("missing") == expected
    assert expected["schema"] == "abyss_machine_rag_eval_v1"
    assert expected["scope"] == "machine RAG trace eval"
    assert expected["ok"] is False
    assert expected["summary"] == {"status": "fail", "fails": 1, "warnings": 0, "checks": 1}
    assert expected["policy"] == {"proof_verdict": False, "memory_writeback": False, "automatic_action": False}


def test_rag_trace_and_eval_preserve_non_action_boundaries(tmp_path: Path) -> None:
    entry = context_contracts.maps_entry(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        axis="by-rag-run",
        label="machine atlas",
        route="Open atlas",
        summary="RAG source route.",
        evidence_refs=[{"path": str(tmp_path / "atlas.json"), "truth_level": "generated_route_atlas"}],
    )
    query = context_contracts.maps_query_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        axis="by-rag-run",
        query=None,
        entries_by_axis={"by-rag-run": [entry]},
    )
    packet = context_contracts.maps_packet_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        axis="by-rag-run",
        query=None,
        reader_profile="retrieval-context",
        limit=8,
        consumer=None,
        query_result=query,
        maps_doc_path=tmp_path / "MAPS.md",
        maps_policy_path=tmp_path / "maps-policy.json",
        maps_latest_path=tmp_path / "maps" / "latest.json",
    )
    snapshots = [
        {
            "schema": "abyss_machine_rag_evidence_snapshot_v1",
            "path": str(tmp_path / "atlas.json"),
            "truth_level": "generated_route_atlas",
            "exists": True,
            "status": "json_summary",
            "raw_private_content": False,
        }
    ]
    answer = context_contracts.rag_answer_from_trace_seed(
        schema_prefix="abyss_machine",
        query="machine context",
        packet=packet,
        evidence_snapshots=snapshots,
    )
    policy = context_contracts.default_rag_policy(
        schema_prefix="abyss_machine",
        version="test",
        rag_doc_path=tmp_path / "MAPS.md",
        rag_policy_path=tmp_path / "maps-policy.json",
        maps_doc_path=tmp_path / "MAPS.md",
    )
    trace = context_contracts.rag_trace_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        query_text="machine context",
        axis_id="by-rag-run",
        profile="retrieval-context",
        packet=packet,
        evidence_snapshots=snapshots,
        answer=answer,
        policy=policy,
        rag_doc_path=tmp_path / "MAPS.md",
        rag_policy_path=tmp_path / "maps-policy.json",
        maps_doc_path=tmp_path / "MAPS.md",
        query_fallback=False,
    )
    eval_doc = context_contracts.rag_eval_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        trace=trace,
    )
    assert trace["ok"] is True
    assert trace["summary"]["automatic_action"] is False
    assert trace["summary"]["memory_writeback"] is False
    assert trace["summary"]["proof_verdict"] is False
    assert trace["summary"]["kag_truth_publication"] is False
    assert "not reviewed memory" in trace["authority_boundary"]["non_claims"]
    assert eval_doc["ok"] is True
    assert eval_doc["score"]["fails"] == 0
    assert eval_doc["policy"]["evaluates_trace_quality_only"] is True


def test_maps_and_rag_path_cli_surfaces_are_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    for command, schema in (
        (["maps", "paths", "--json"], "abyss_machine_maps_paths_v1"),
        (["rag", "paths", "--json"], "abyss_machine_rag_paths_v1"),
    ):
        result = subprocess.run(
            [sys.executable, "-m", "abyss_machine.cli", *command],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        payload = json.loads(result.stdout)
        assert payload["schema"] == schema
        assert payload["commands"]["validate"].startswith("abyss-machine")
