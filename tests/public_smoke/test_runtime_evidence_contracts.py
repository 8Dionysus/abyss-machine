from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import runtime_evidence_contracts


def test_heartbeat_freshness_rhythm_and_lifecycle_are_module_owned() -> None:
    now = dt.datetime(2026, 6, 25, 12, 5, tzinfo=dt.timezone.utc)
    fresh_ref = runtime_evidence_contracts.heartbeat_input_ref(
        "doctor",
        "/var/lib/abyss-machine/doctor/latest.json",
        {"ok": True, "generated_at": "2026-06-25T12:00:00+00:00", "summary": {"status": "ok"}},
        now=now,
    )
    stale_ref = {
        "path": "/var/lib/abyss-machine/reactions/latest.json",
        "ok": True,
        "generated_at": "2026-06-25T10:00:00+00:00",
        "age_sec": 7200.0,
    }
    freshness = runtime_evidence_contracts.heartbeat_source_freshness(
        schema_prefix="abyss_machine",
        inputs={"doctor": fresh_ref, "reactions": stale_ref},
        ttl_config=runtime_evidence_contracts.heartbeat_source_freshness_ttls(900),
        previous_latest={
            "source_freshness": {
                "sources": {
                    "reactions": {"stale_streak": 2, "last_ok_at": "2026-06-25T10:00:00+00:00"}
                }
            }
        },
    )
    rhythm = runtime_evidence_contracts.heartbeat_rhythm_document(
        schema_prefix="abyss_machine",
        expected_interval_sec=900,
        previous_latest={"generated_at": "2026-06-25T11:30:00+00:00"},
        heartbeat_timer={"is_active": True, "is_enabled": True},
        jobs={"heartbeat_jobs": [], "waiting_heartbeat_jobs": []},
        generated_at="2026-06-25T12:00:00+00:00",
        timer_list={"next_beat_at": "Thu 2026-06-25 12:15:00 UTC"},
    )
    lifecycle = runtime_evidence_contracts.heartbeat_candidate_lifecycle(
        schema_prefix="abyss_machine",
        candidates=[{"id": "candidate-a", "severity": "warning", "category": "doctor"}],
        previous_latest={
            "candidate_lifecycle": {
                "active": [
                    {
                        "id": "candidate-a",
                        "first_seen_at": "2026-06-25T11:45:00+00:00",
                        "consecutive_beats": 1,
                        "total_beats": 1,
                        "severity_history": ["notice"],
                    },
                    {"id": "candidate-b", "first_seen_at": "2026-06-25T11:45:00+00:00"},
                ]
            }
        },
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert freshness["schema"] == "abyss_machine_heartbeat_source_freshness_v1"
    assert freshness["sources"]["doctor"]["age_sec"] == 300.0
    assert freshness["sources"]["reactions"]["freshness_class"] == "stale"
    assert freshness["sources"]["reactions"]["stale_streak"] == 3
    assert rhythm["schema"] == "abyss_machine_heartbeat_rhythm_v1"
    assert rhythm["missed_beats"] == 1
    assert rhythm["status"] == "missed"
    assert lifecycle["schema"] == "abyss_machine_heartbeat_candidate_lifecycle_v1"
    assert lifecycle["active"][0]["consecutive_beats"] == 2
    assert lifecycle["recently_resolved"][0]["id"] == "candidate-b"


def test_reaction_and_response_contracts_are_non_executing_owner_gated_readmodels() -> None:
    reaction = runtime_evidence_contracts.reaction_candidate(
        "abyss_machine",
        "doctor-warnings-present",
        title="Doctor has warning-level checks",
        severity="warning",
        category="doctor",
        reason="review warning checks",
        command="abyss-machine doctor --json",
        evidence=[{"path": "/var/lib/abyss-machine/doctor/latest.json"}],
    )
    second = runtime_evidence_contracts.reaction_candidate(
        "abyss_machine",
        "root-sync-review",
        title="Root sync review",
        severity="notice",
        category="stack-bridge",
        reason="dry-run only",
        command="abyss-machine stack-bridge sync-static --dry-run --json",
        evidence=[],
        owner_route="abyss-machine:root-operator",
    )
    status = runtime_evidence_contracts.reaction_status_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        candidates=[second, reaction],
        inputs={"doctor": {"path": "/var/lib/abyss-machine/doctor/latest.json"}},
        paths={"schema": "abyss_machine_reactions_paths_v1"},
        metrics={"doctor_warning_candidates": 1},
    )
    route = runtime_evidence_contracts.response_route_from_candidate("abyss_machine", reaction)
    mutating_profile = runtime_evidence_contracts.response_command_profile("sudo systemctl restart abyss-machine.service")
    responses = runtime_evidence_contracts.response_status_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        routes=[route],
        reactions={"ok": True, "status": "attention", "candidates": [reaction]},
        heartbeat={"ok": True, "status": "attention", "generated_at": "2026-06-25T12:00:00+00:00"},
        changes={"ok": True, "summary": {"active_records": 0}},
        paths={"schema": "abyss_machine_responses_paths_v1"},
        metrics={
            "doctor_warning_routes": 1,
            "heartbeats_path": "/var/lib/abyss-machine/heartbeats/latest.json",
            "reactions_path": "/var/lib/abyss-machine/reactions/latest.json",
            "changes_path": "/var/lib/abyss-machine/changes/index.json",
        },
        self_awareness_refs=[],
    )

    assert reaction["schema"] == "abyss_machine_reaction_candidate_v1"
    assert reaction["automatic"] is False
    assert status["schema"] == "abyss_machine_reactions_status_v1"
    assert [item["id"] for item in status["candidates"]] == ["doctor-warnings-present", "root-sync-review"]
    assert status["summary"]["automatic_actions"] == 0
    assert route["schema"] == "abyss_machine_response_route_v1"
    assert route["approval"]["required"] is True
    assert route["executes"] is False
    assert route["suggestion"]["command_profile"]["kind"] == "read_model_probe"
    assert mutating_profile["mutating_if_run"] is True
    assert mutating_profile["requires_change_preflight"] is True
    assert responses["summary"]["doctor_warning_routes"] == 1
    assert responses["policy"]["executes_commands"] is False
    assert responses["policy"]["routes_require_operator_or_owner_gate"] is True


def test_runtime_validate_documents_are_module_owned_with_cli_adapters(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T15:10:00Z"
    checks = [
        {"level": "ok", "key": "policy_non_executing", "message": "policy is non-executing"},
        {"level": "warn", "key": "timer_enabled", "message": "timer is not enabled", "data": {"is_enabled": False}},
    ]
    specs = [
        (
            runtime_evidence_contracts.heartbeats_validate_document,
            cli.heartbeats_validate_document_from_checks,
            "abyss_machine_heartbeats_validate_v1",
            "OS Abyss recurring Heartbeats readmodel",
            {"schema": "abyss_machine_heartbeats_paths_v1"},
        ),
        (
            runtime_evidence_contracts.reactions_validate_document,
            cli.reactions_validate_document_from_checks,
            "abyss_machine_reactions_validate_v1",
            "Abyss Machine reaction candidate readmodel",
            {"schema": "abyss_machine_reactions_paths_v1"},
        ),
        (
            runtime_evidence_contracts.responses_validate_document,
            cli.responses_validate_document_from_checks,
            "abyss_machine_responses_validate_v1",
            "OS Abyss owner-gated response routes readmodel",
            {"schema": "abyss_machine_responses_paths_v1"},
        ),
    ]
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    for contract_fn, wrapper_fn, schema, scope, paths in specs:
        expected = contract_fn(
            schema_prefix=cli.SCHEMA_PREFIX,
            version=cli.VERSION,
            generated_at=generated_at,
            checks=checks,
            strict=True,
            paths=paths,
        )
        assert wrapper_fn(checks, strict=True, paths=paths) == expected
        assert expected["schema"] == schema
        assert expected["scope"] == scope
        assert expected["ok"] is False
        assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
        assert expected["paths"] == paths
        assert expected["policy"]["read_only"] is True


def test_runtime_evidence_paths_cli_uses_public_contracts_without_live_status() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    for surface, schema in [
        ("heartbeats", "abyss_machine_heartbeats_paths_v1"),
        ("reactions", "abyss_machine_reactions_paths_v1"),
        ("responses", "abyss_machine_responses_paths_v1"),
    ]:
        result = subprocess.run(
            [sys.executable, "-m", "abyss_machine.cli", surface, "paths", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["schema"] == schema
        assert payload["policy"]["read_model"] is True
        assert payload["policy"].get("repo_mutation") is False
