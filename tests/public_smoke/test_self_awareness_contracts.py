from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import self_awareness_contracts


FAKE_OPENAI_KEY = "sk-" + "testsecret1234567890"


def test_paths_and_bridge_contracts_are_read_only_handoffs(tmp_path: Path) -> None:
    surfaces = {
        "events": (tmp_path / "events", tmp_path / "events" / "latest.json"),
        "collect": (tmp_path / "collect", tmp_path / "collect" / "latest.json"),
        "validate": (tmp_path / "validate", tmp_path / "validate" / "latest.json"),
    }
    paths = self_awareness_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        root=tmp_path / "self-awareness",
        doc_path=tmp_path / "SELF-AWARENESS.md",
        agents_path=tmp_path / "AGENTS.md",
        index_path=tmp_path / "index.json",
        surfaces=surfaces,
        inputs={"stack_observability": tmp_path / "stack-observability.json"},
    )
    assert paths["schema"] == "abyss_machine_self_awareness_paths_v1"
    assert paths["events"]["daily_glob"].endswith("events/YYYY/MM/YYYY-MM-DD.jsonl")
    assert paths["commands"]["cycle"] == "abyss-machine self-awareness cycle --json"
    assert paths["policy"]["read_only_stack_consumer"] is True
    assert paths["policy"]["host_layer_mutates_stack"] is False
    assert paths["policy"]["automatic_remediation"] is False

    bridge = self_awareness_contracts.bridge_contract(
        agents_path=tmp_path / "AGENTS.md",
        doc_path=tmp_path / "SELF-AWARENESS.md",
        collect_latest_path=tmp_path / "collect" / "latest.json",
        capabilities_latest_path=tmp_path / "capabilities" / "latest.json",
        requirements_latest_path=tmp_path / "requirements" / "latest.json",
        requirement_probes_latest_path=tmp_path / "requirement-probes" / "latest.json",
        stack_closure_dossier_latest_path=tmp_path / "stack-closure-dossier" / "latest.json",
        trace_context_latest_path=tmp_path / "trace-context" / "latest.json",
        failure_matrix_latest_path=tmp_path / "failure-matrix" / "latest.json",
        working_stack_latest_path=tmp_path / "working-stack" / "latest.json",
        coverage_audit_latest_path=tmp_path / "coverage-audit" / "latest.json",
        activation_smoke_latest_path=tmp_path / "activation-smoke" / "latest.json",
        autolink_latest_path=tmp_path / "autolink" / "latest.json",
        completion_audit_latest_path=tmp_path / "completion-audit" / "latest.json",
        correlation_latest_path=tmp_path / "correlation" / "latest.json",
        investigate_latest_path=tmp_path / "investigate" / "latest.json",
        replay_latest_path=tmp_path / "replay" / "latest.json",
        export_latest_path=tmp_path / "export" / "latest.json",
        validate_latest_path=tmp_path / "validate" / "latest.json",
        probe_latest_path=tmp_path / "probe" / "latest.json",
        cycle_latest_path=tmp_path / "cycle" / "latest.json",
    )
    assert bridge["commands"]["validate"] == "abyss-machine self-awareness validate --json"
    assert "does not mutate abyss-stack" in bridge["non_claim"]


def test_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T15:40:00Z"
    checks = [
        {"level": "ok", "key": "paths", "message": "paths readable"},
        {"level": "warn", "key": "probe", "message": "probe has not run"},
    ]
    paths = {"schema": "abyss_machine_self_awareness_paths_v1"}
    summary_extra = {"events": 2, "probe_run_id": "probe-1"}
    expected = self_awareness_contracts.validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        paths=paths,
        summary_extra=summary_extra,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.self_awareness_validate_document_from_checks(
        checks,
        strict=True,
        paths=paths,
        summary_extra=summary_extra,
    ) == expected
    assert expected["schema"] == "abyss_machine_self_awareness_validate_v1"
    assert expected["scope"] == "Abyss Machine self-awareness observability layer"
    assert expected["ok"] is False
    assert expected["summary_extra"] == summary_extra
    assert expected["policy"]["read_only"] is True


def test_event_contract_redacts_and_rejects_unbounded_labels() -> None:
    traceparent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    context = self_awareness_contracts.context_from_text(f"traceparent={traceparent}")
    assert context["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert context["span_id"] == "0123456789abcdef"

    event = self_awareness_contracts.make_event(
        "log",
        "prometheus",
        event_time="2026-06-25T10:07:12+00:00",
        observed_at="2026-06-25T10:07:13+00:00",
        source_query=f"Authorization: Bearer {FAKE_OPENAI_KEY}",
        resource={
            "service": "route-api",
            "labels": {"trace_id": "0123456789abcdef0123456789abcdef"},
            "path": "/private/evidence",
            "write": True,
        },
        context=context,
        space={"host": "test-host"},
        body="password=supersecret",
        evidence_refs=[{"path": "/var/lib/abyss-machine/self-awareness/events/latest.json"}],
        host="test-host",
    )
    assert event["source_query"] == "<redacted>"
    assert event["body_preview"] == "<redacted>"
    assert event["fabric"]["policy"]["host_layer_mutates_stack"] is False
    assert event["fabric"]["policy"]["raw_body_stored"] is False
    assert event["fabric"]["temporal"]["time_bucket"] == "2026-06-25T10:05:00Z"
    assert "trace_id:0123456789abcdef0123456789abcdef" in event["fabric"]["context_links"]["correlation_keys"]

    issues = self_awareness_contracts.event_issues(
        event,
        path_protection_decision=lambda path: "deny" if path == "/private/evidence" else "allow",
    )
    assert "fabric_forbidden_label_keys" in issues
    assert "unbounded_label:trace_id" in issues
    assert "protected_write_claim" in issues


def test_query_time_and_probe_helpers_are_bounded() -> None:
    assert self_awareness_contracts.query_terms("latest RAG graph freshness") == [
        "rag",
        "retrieval",
        "graphrag",
        "context",
        "graph",
        "spatial",
        "neo4j",
        "dependency",
        "freshness",
        "stale",
        "generated_at",
        "gate",
    ]
    assert self_awareness_contracts.match_score({"service": "rag-api", "status": "freshness ok"}, "rag freshness") >= 2
    assert self_awareness_contracts.time_bucket("2026-06-25T10:09:59Z") == "2026-06-25T10:05:00Z"
    assert self_awareness_contracts.stack_handoff_impacted_services("stack.database-graph.read-route") == [
        "route-api",
        "rag-api",
        "postgres",
        "neo4j",
        "embeddings",
    ]
    summary = self_awareness_contracts.http_probe_summary(
        {"ok": True, "url": "http://127.0.0.1", "json": {"secret": FAKE_OPENAI_KEY}},
        "health",
    )
    assert summary["body_stored"] is False
    assert summary["raw_private_content"] is False
    assert summary["json_shape"]["secret"] == "<redacted>"


def test_working_stack_activation_gap_contract_is_read_only_handoff() -> None:
    observed_at = "2026-06-25T10:07:12+00:00"
    link = self_awareness_contracts.working_stack_link(
        "qwen-tts",
        observed_at,
        status="tool_runtime_degraded",
        container="abyss_qwen-tts-api_1",
        pid=4242,
        endpoint_ok=False,
    )
    assert link["schema"] == "abyss_machine_self_awareness_working_stack_time_space_context_link_v1"
    assert link["link_id"] == self_awareness_contracts.working_stack_expected_link_id("qwen-tts", "tool_runtime_degraded")
    assert link["space"]["owner_surface"] == "abyss-stack"
    assert link["policy"]["host_layer_mutates_stack"] is False
    assert self_awareness_contracts.working_stack_links_match_stable_identity({
        "organs": [
            {
                "service": "qwen-tts",
                "machine_usage_status": "tool_runtime_degraded",
                "time_space_context_link": link,
            }
        ]
    })

    assert self_awareness_contracts.working_stack_status(
        "prometheus",
        running=True,
        declared=True,
        endpoint_ok=False,
        model_roots=0,
    ) == "active_machine_signal"
    assert self_awareness_contracts.working_stack_status(
        "qdrant",
        running=True,
        declared=True,
        endpoint_ok=False,
        model_roots=0,
    ) == "active_dependency_signal"
    assert self_awareness_contracts.working_stack_policy_status(
        "declared_not_running",
        {"posture": "explicit_opt_in"},
    ) == "policy_deferred_opt_in"

    gap = {
        "service": "qwen-tts",
        "machine_usage_status": "tool_runtime_degraded",
        "usage_gap": "bounded TTS synth smoke failed",
        "working_stack_link_id": link["link_id"],
        "runtime_present": True,
        "runtime_running": True,
        "runtime_state": "running",
        "runtime_status": "Up",
        "runtime_stack_managed": True,
        "container": "abyss_qwen-tts-api_1",
        "endpoint_ok": False,
        "endpoint_probe_count": 1,
        "failed_probe_names": ["tts-synth-smoke"],
        "ok_probe_names": ["health"],
        "closure_blocker_keys": ["probe_failed:tts-synth-smoke"],
    }
    route = self_awareness_contracts.working_stack_activation_gap_route(
        gap,
        episode_id="episode-1",
        activation_row={
            "complete": True,
            "investigation": {"thread_id": "thread-1", "selected_episode_matches": True},
            "replay": {"thread_matches": True, "working_stack_gap_replayable": True},
        },
        evidence_refs=[
            {"path": "/var/lib/abyss-machine/self-awareness/working-stack/latest.json"},
            {"path": "/var/lib/abyss-machine/self-awareness/activation-smoke/latest.json"},
        ],
    )
    assert route["classification"] == "running_functional_smoke_failed"
    assert route["activation_kind"] == "stack_tool_runtime_smoke_gap"
    assert route["safe_next_action"]["owner_route"] == "abyss-stack"
    assert route["safe_next_action"]["requires_human_approval"] is True
    assert route["policy"]["executes_commands"] is False
    assert route["policy"]["host_layer_mutates_stack"] is False
    assert route["complete"] is True
    assert self_awareness_contracts.working_stack_activation_gap_route_complete(route)


def test_cli_working_stack_wrappers_match_contract_module() -> None:
    from abyss_machine import cli

    assert cli.self_awareness_working_stack_gap_activation_kind(
        "endpoint_visible_unproven_deep_use"
    ) == self_awareness_contracts.working_stack_gap_activation_kind(
        "endpoint_visible_unproven_deep_use"
    )
    assert cli.self_awareness_working_stack_gap_coverage_planes(
        "model_root_visible"
    ) == self_awareness_contracts.working_stack_gap_coverage_planes(
        "model_root_visible"
    )
    assert cli.self_awareness_working_stack_expected_link_id(
        "rag-api",
        "active_machine_signal",
    ) == self_awareness_contracts.working_stack_expected_link_id(
        "rag-api",
        "active_machine_signal",
    )


def test_self_awareness_paths_cli_surface_is_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "self-awareness", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_self_awareness_paths_v1"
    assert payload["commands"]["validate"] == "abyss-machine self-awareness validate --json"
    assert payload["policy"]["host_layer_mutates_stack"] is False
