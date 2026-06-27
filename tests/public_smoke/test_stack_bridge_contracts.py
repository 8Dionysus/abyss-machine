from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import stack_bridge_contracts


def test_stack_bridge_paths_and_bridge_contracts_are_portable(tmp_path: Path) -> None:
    paths = stack_bridge_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        root=tmp_path / "stack-bridge",
        agents_path=tmp_path / "stack-bridge" / "AGENTS.md",
        latest_path=tmp_path / "stack-bridge" / "latest.json",
        today=tmp_path / "stack-bridge" / "2026" / "06" / "2026-06-25.jsonl",
        validate_root=tmp_path / "stack-bridge" / "validate",
        validate_latest_path=tmp_path / "stack-bridge" / "validate" / "latest.json",
        static_sync_root=tmp_path / "stack-bridge" / "static-sync",
        static_sync_latest_path=tmp_path / "stack-bridge" / "static-sync" / "latest.json",
        observability_root=tmp_path / "stack-bridge" / "observability",
        observability_latest_path=tmp_path / "stack-bridge" / "observability" / "latest.json",
        self_awareness_root=tmp_path / "self-awareness",
        self_awareness_latest_path=tmp_path / "self-awareness" / "collect" / "latest.json",
        self_awareness_probe_path=tmp_path / "self-awareness" / "probe" / "latest.json",
        self_awareness_validate_path=tmp_path / "self-awareness" / "validate" / "latest.json",
        manifest_path=tmp_path / "etc" / "stack-bridge.json",
        doc_path=tmp_path / "etc" / "STACK-BRIDGE.md",
        main_bridge_path=tmp_path / "etc" / "bridge.json",
        hooks_etc_dir=tmp_path / "etc" / "hooks.d" / "stack-bridge",
        hooks_srv_dir=tmp_path / "srv" / "hooks.d" / "stack-bridge",
    )
    assert paths["schema"] == "abyss_machine_stack_bridge_paths_v1"
    assert paths["commands"]["export"] == "abyss-machine stack-bridge export --json"
    assert paths["hooks"]["automatic_execution"] is False

    typing_bridge = stack_bridge_contracts.typing_bridge_contract(
        typing_agents_path=tmp_path / "typing" / "AGENTS.md",
        events_latest_path=tmp_path / "typing" / "events.json",
        coverage_latest_path=tmp_path / "typing" / "coverage.json",
        process_latest_path=tmp_path / "typing" / "process.json",
        nervous_refresh_latest_path=tmp_path / "typing" / "nervous-refresh.json",
        validate_latest_path=tmp_path / "typing" / "validate.json",
    )
    assert typing_bridge["stable_causal_fields"] == ["input", "where", "recipient", "task", "policy"]
    assert "not raw keylogging" in typing_bridge["non_claim"]

    observability_bridge = stack_bridge_contracts.observability_bridge_contract(latest_path=tmp_path / "observability.json")
    assert observability_bridge["commands"]["observability"] == "abyss-machine stack-bridge observability --json"
    assert "does not import, write, start, stop, or reconfigure abyss-stack" in observability_bridge["non_claim"]


def test_heartbeat_readiness_requires_read_only_artifacts_and_validate_checks(tmp_path: Path) -> None:
    stable_fields = ("source", "rhythm", "readiness")
    required_checks = ("stable_fields", "read_only_policy")
    latest = {
        "schema": "abyss_machine_heartbeat_pulse_v1",
        "source": {},
        "rhythm": {},
        "readiness": {},
        "policy": {
            "read_model": True,
            "automatic_action": False,
            "executes_reaction_commands": False,
            "executes_response_commands": False,
            "automatic_repo_write": False,
        },
    }
    validation = {
        "schema": "abyss_machine_heartbeats_validate_v1",
        "ok": True,
        "summary": {"fails": 0},
        "checks": [
            {"key": "stable_fields", "level": "ok"},
            {"key": "read_only_policy", "level": "ok"},
        ],
    }
    ready = stack_bridge_contracts.heartbeat_readiness(
        schema_prefix="abyss_machine",
        latest=latest,
        validation=validation,
        stable_fields=stable_fields,
        required_validate_checks=required_checks,
        latest_path=tmp_path / "heartbeats" / "latest.json",
        validate_path=tmp_path / "heartbeats" / "validate.json",
        artifacts={"latest": {"write": False}, "validate": {"write": False}},
    )
    assert ready["ok"] is True
    assert ready["status"] == "ready"

    blocked = stack_bridge_contracts.heartbeat_readiness(
        schema_prefix="abyss_machine",
        latest=latest,
        validation={"schema": "abyss_machine_heartbeats_validate_v1", "ok": True, "summary": {"fails": 0}, "checks": []},
        stable_fields=stable_fields,
        required_validate_checks=required_checks,
        latest_path=tmp_path / "heartbeats" / "latest.json",
        validate_path=tmp_path / "heartbeats" / "validate.json",
        artifacts={"latest": {"write": True}},
    )
    assert blocked["ok"] is False
    assert "validate" in blocked["missing_artifacts"]
    assert "latest" in blocked["non_readonly_artifacts"]
    assert blocked["missing_validate_checks"] == ["stable_fields", "read_only_policy"]


def test_stack_bridge_export_and_latest_read_documents_are_handoff_only(tmp_path: Path) -> None:
    export = stack_bridge_contracts.export_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        root=tmp_path / "stack-bridge",
        latest_path=tmp_path / "stack-bridge" / "latest.json",
        config_path=tmp_path / "etc" / "stack-bridge.json",
        config_exists=True,
        manifest={
            "schema": "abyss_machine_stack_bridge_manifest_v1",
            "contract": {"host_layer_mutates_stack": False},
            "first_commands": ["abyss-machine stack-bridge --json"],
            "validation_commands": ["abyss-machine stack-bridge validate --json"],
            "mutation_gates": ["abyss-machine changes preflight --intent TEXT --surface SURFACE --json"],
            "commands": {"stack_bridge_json": ["abyss-machine", "stack-bridge", "--json"]},
            "non_claims": ["This bridge does not start abyss-stack services."],
        },
        paths={"commands": {"status": "abyss-machine stack-bridge --json"}},
        stack_roots={"host_layer_mutates_stack": False},
        protected_roots=[{"path": "/srv/AbyssOS", "decision": "deny"}],
        bridges={"typing_bridge": {"contract": "typing"}},
        artifacts={"machine": {"bridge": {"path": "/etc/abyss-machine/bridge.json"}}},
        refs={"machine": {"bridge": {"exists": True, "schema_ok": True}}},
        required_missing=[],
        schema_mismatches=[],
        stack_command_keys=["stack_bridge_json"],
    )
    assert export["schema"] == "abyss_machine_stack_bridge_v1"
    assert export["ok"] is True
    assert export["summary"]["refs"] == 1
    assert "Do not write to abyss-stack or project roots from this host bridge." in export["handoff_rules"]
    assert export["contract"]["host_layer_mutates_stack"] is False

    missing_latest = stack_bridge_contracts.latest_read_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        latest_path=tmp_path / "stack-bridge" / "latest.json",
        data=None,
        error="missing",
    )
    assert missing_latest["schema"] == "abyss_machine_stack_bridge_latest_read_v1"
    assert missing_latest["ok"] is False

    read_latest = stack_bridge_contracts.latest_read_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        latest_path=tmp_path / "stack-bridge" / "latest.json",
        data={"schema": "abyss_machine_stack_bridge_v1", "ok": True},
        error=None,
    )
    assert read_latest["read_schema"] == "abyss_machine_stack_bridge_latest_read_v1"
    assert read_latest["read_at"] == "2026-06-25T00:00:00+00:00"


def test_stack_bridge_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T15:35:00Z"
    checks = [
        {"level": "ok", "key": "export", "message": "export ready"},
        {"level": "warn", "key": "static_bridge_sync", "message": "root sync needs review"},
    ]
    paths = {"schema": "abyss_machine_stack_bridge_paths_v1"}
    export_summary = {"refs": 12, "required_missing": 0}
    expected = stack_bridge_contracts.validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        export_summary=export_summary,
        paths=paths,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.stack_bridge_validate_document_from_checks(
        checks,
        strict=True,
        export_summary=export_summary,
        paths=paths,
    ) == expected
    assert expected["schema"] == "abyss_machine_stack_bridge_validate_v1"
    assert expected["scope"] == "stack bridge handoff"
    assert expected["ok"] is False
    assert expected["policy"]["does_not_mutate_stack"] is True
    assert expected["export_summary"] == export_summary


def test_stack_bridge_paths_cli_surface_is_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "stack-bridge", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_stack_bridge_paths_v1"
    assert payload["commands"]["validate"] == "abyss-machine stack-bridge validate --json"
