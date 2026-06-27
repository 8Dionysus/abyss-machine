from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import topology_contracts


def test_topology_paths_status_and_index_contracts(tmp_path: Path) -> None:
    docs = {"agent_entrypoint": "/etc/abyss-machine/AGENTS.md", "topology": "/etc/abyss-machine/TOPOLOGY.md"}
    roots = {
        "stable_config": "/etc/abyss-machine",
        "durable_facts": str(tmp_path / "state"),
        "large_machine_root": str(tmp_path / "srv"),
    }
    topology = {
        "root": str(tmp_path / "state" / "topology"),
        "latest": str(tmp_path / "state" / "topology" / "latest.json"),
        "index": str(tmp_path / "state" / "topology" / "index.json"),
        "validate_latest": str(tmp_path / "state" / "topology" / "validate" / "latest.json"),
        "audit_latest": str(tmp_path / "state" / "topology" / "audit" / "latest.json"),
    }
    paths = topology_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        docs=docs,
        roots=roots,
        topology=topology,
        changes={"commands": {"status": "abyss-machine changes status --json"}},
        doctor={"commands": {"status": "abyss-machine doctor --json"}},
        stack_bridge={"commands": {"status": "abyss-machine stack-bridge --json"}},
        mode={"commands": {"plan": "abyss-machine mode plan --json"}},
        bridge_commands={"topology": "abyss-machine topology --json"},
    )
    assert paths["schema"] == "abyss_machine_topology_paths_v1"
    assert paths["topology"]["latest"].endswith("latest.json")
    assert paths["bridge_commands"]["topology"] == "abyss-machine topology --json"

    states = topology_contracts.surface_states(
        cache_root=tmp_path / "srv" / "cache",
        runtime_root=tmp_path / "srv" / "runtimes",
        storage_root=tmp_path / "srv" / "storage",
        tmp_root=tmp_path / "srv" / "tmp",
        runtime_dir=tmp_path / "run",
        uid=1000,
        manifest_path=tmp_path / "etc" / "bridge.json",
        stack_bridge_config_path=tmp_path / "etc" / "stack-bridge.json",
        stack_bridge_latest_path=tmp_path / "state" / "stack-bridge" / "latest.json",
        topology_latest_path=tmp_path / "state" / "topology" / "latest.json",
        change_index_path=tmp_path / "state" / "changes" / "index.json",
        stack_user_source_root=tmp_path / "src" / "abyss-stack",
    )
    assert {item["state"] for item in states} == {
        "source-config",
        "host-fact",
        "history",
        "large-cache",
        "large-runtime",
        "runtime",
        "bridge",
        "project-readonly",
    }

    status = topology_contracts.status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        paths=paths,
        docs={"topology": {"exists": True}},
        roots={"stable_config": {"exists": True}},
        writable_roots=[str(tmp_path / "srv"), str(tmp_path / "state")],
        surface_states=states,
        protected_roots=[{"path": "/srv/AbyssOS", "decision": "deny"}],
        stack_user_source_root=tmp_path / "src" / "abyss-stack",
    )
    assert status["schema"] == "abyss_machine_topology_v1"
    assert status["write_policy"]["dependency_direction"].endswith("must not import or mutate abyss-stack.")
    assert str(tmp_path / "src" / "abyss-stack") in status["write_policy"]["project_roots_readonly_by_default"]
    assert "Generated/latest host facts accelerate orientation" in status["non_claims"][2]

    index = topology_contracts.index_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        topology_root=tmp_path / "state" / "topology",
        latest_path=tmp_path / "state" / "topology" / "latest.json",
        agent_entrypoint=tmp_path / "etc" / "AGENTS.md",
        topology_doc_path=tmp_path / "etc" / "TOPOLOGY.md",
        roadmap_doc_path=tmp_path / "etc" / "ROADMAP.md",
        changelog_doc_path=tmp_path / "etc" / "CHANGELOG.md",
        decisions_agents_path=tmp_path / "etc" / "decisions" / "AGENTS.md",
        bridge_manifest_path=tmp_path / "etc" / "bridge.json",
        topology_data={"generated_at": "2026-06-25T00:00:00+00:00", "ok": True},
    )
    assert index["schema"] == "abyss_machine_topology_index_v1"
    assert index["commands"]["topology_validate"] == ["abyss-machine", "topology", "validate", "--json"]
    assert index["latest_status"] == {"generated_at": "2026-06-25T00:00:00+00:00", "ok": True}


def test_topology_forbidden_root_classifier() -> None:
    assert topology_contracts.under_forbidden_root("/work") == "/work"
    assert topology_contracts.under_forbidden_root("/work/project") == "/work"
    assert topology_contracts.under_forbidden_root("/srv/work/client") == "/srv/work"
    assert topology_contracts.under_forbidden_root("/srv/abyss-machine/cache") is None


def test_topology_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T13:20:00Z"
    checks = [
        {"level": "ok", "key": "doc_exists:etc_agents", "message": "/etc/abyss-machine/AGENTS.md present", "data": {"path": "/etc/abyss-machine/AGENTS.md"}},
        {"level": "warn", "key": "changes_active_count", "message": "1 active host-layer changes remain", "data": {"active_records": 1}},
    ]
    expected = topology_contracts.validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.topology_validate_document_from_checks(checks, strict=True) == expected
    assert expected["schema"] == "abyss_machine_topology_validate_v1"
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["ok"] is False
    assert "scope" not in expected
    assert expected["policy"]["does_not_mutate_project_repos"] is True
    assert expected["non_claims"][0].startswith("This validator checks host-layer topology consistency")


def test_topology_paths_cli_surface_is_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "topology", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_topology_paths_v1"
    assert payload["topology"]["validate_command"] == "abyss-machine topology validate --json"
