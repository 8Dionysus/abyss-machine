from __future__ import annotations

from pathlib import Path

import pytest

from conftest import parse_json_stdout


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def _quiet_evidence(monkeypatch, machine, backup_status: str = "heavy-latest") -> None:
    monkeypatch.setattr(
        machine,
        "artifact_backup_state",
        lambda path: {
            "status": backup_status,
            "latest": {"exists": backup_status == "heavy-latest", "path": "/abyss/Backups/heavy/latest/example"},
            "offload": {"exists": backup_status == "explicit-offload", "path": "/abyss/Backups/heavy/offloaded/example"},
            "preserved_deleted": [],
            "restore_command": f"rsync -aHAX /abyss/Backups/heavy/latest/example/ {path}/",
        },
    )
    monkeypatch.setattr(machine, "artifact_process_refs", lambda path: {"active": False, "refs": [], "ref_count": 0})
    monkeypatch.setattr(
        machine,
        "artifact_config_refs",
        lambda path, tokens: {
            "hits": [],
            "hit_count": 0,
            "strong_hit_count": 0,
            "strong_live_hit_count": 0,
            "strong_source_config_hit_count": 0,
            "active_evidence_hit_count": 0,
            "by_source_kind": {},
        },
    )
    monkeypatch.setattr(machine, "artifact_service_refs", lambda spec: {"active": False, "units": []})
    monkeypatch.setattr(machine, "artifact_container_refs", lambda path, spec: {"active": False, "containers": []})
    monkeypatch.setattr(machine, "storage_path_protection", lambda path: {"decision": "allow_candidate", "class": "host_owned_allowed"})


def test_artifact_decision_never_grants_delete_ok_from_cache_like_shape(abyss_machine_module) -> None:
    machine = abyss_machine_module
    decision = machine.artifact_decision(
        {
            "kind": "openvino-compile-cache",
            "path_state": {"exists": True, "size_bytes": 10_000_000_000, "mtime": "2026-05-01T00:00:00Z"},
            "protection": {"decision": "allow_candidate"},
            "process_refs": {"active": False, "ref_count": 0},
            "service_refs": {"active": False},
            "container_refs": {"active": False},
            "config_refs": {"hit_count": 0, "strong_live_hit_count": 0},
            "backup_state": {"status": "not-backed-up-or-unknown"},
        }
    )

    assert decision["classification"] == "regenerable"
    assert decision["confidence"] == "low"
    assert decision["decision"] == "not-delete-ok-without-backup-or-workload-proof"


def test_context_config_ref_without_cache_path_is_not_active_route(abyss_machine_module) -> None:
    machine = abyss_machine_module
    decision = machine.artifact_decision(
        {
            "kind": "openvino-compile-cache",
            "path_state": {"exists": True},
            "protection": {"decision": "allow_candidate"},
            "process_refs": {"active": False, "ref_count": 0},
            "service_refs": {"active": False},
            "container_refs": {"active": False},
            "config_refs": {"hit_count": 1, "strong_hit_count": 0, "strong_live_hit_count": 0},
            "backup_state": {"status": "heavy-latest"},
        }
    )

    assert decision["classification"] == "quarantine-first"
    assert decision["confidence"] == "medium"


def test_docs_and_bak_refs_do_not_count_as_live_config(tmp_path: Path, monkeypatch, abyss_machine_module) -> None:
    machine = abyss_machine_module
    artifact = tmp_path / "cache" / "semantic-embedding-Qwen3"
    artifact.mkdir(parents=True)
    docs = tmp_path / "commands.md"
    old = tmp_path / "route.json.bak"
    source = tmp_path / "route.json"
    docs.write_text(f"docs mention {artifact}\n", encoding="utf-8")
    old.write_text(f"old backup mentions {artifact}\n", encoding="utf-8")
    source.write_text(f'{{"cache_dir": "{artifact}"}}\n', encoding="utf-8")
    monkeypatch.setattr(machine, "artifact_config_scan_files", lambda: [docs, old, source])

    refs = machine.artifact_config_refs(artifact, [])

    assert refs["hit_count"] == 3
    assert refs["strong_hit_count"] == 3
    assert refs["strong_live_hit_count"] == 0
    assert refs["strong_source_config_hit_count"] == 1
    assert refs["by_source_kind"]["docs_ref"] == 1
    assert refs["by_source_kind"]["historical_config"] == 1
    assert refs["by_source_kind"]["source_config"] == 1
    non_live = [hit for hit in refs["hits"] if hit["source_kind"] in {"docs_ref", "historical_config"}]
    assert non_live
    assert all(hit["active_evidence"] is False for hit in non_live)


def test_decision_ignores_strong_docs_or_historical_refs(abyss_machine_module) -> None:
    machine = abyss_machine_module
    decision = machine.artifact_decision(
        {
            "kind": "openvino-compile-cache",
            "path_state": {"exists": True},
            "protection": {"decision": "allow_candidate"},
            "process_refs": {"active": False, "ref_count": 0},
            "service_refs": {"active": False},
            "container_refs": {"active": False},
            "config_refs": {"hit_count": 7, "strong_hit_count": 7, "strong_live_hit_count": 0},
            "backup_state": {"status": "heavy-latest"},
        }
    )

    assert decision["classification"] == "quarantine-first"
    assert decision["decision"] == "controlled-quarantine-plus-workload-probe-before-removal"


def test_semantic_probe_uses_bounded_rebuild_not_status_only(abyss_machine_module) -> None:
    machine = abyss_machine_module
    probe = machine.artifact_real_probe({"workload_probe": "nervous-semantic"})

    assert any(
        "semantic-build --max-chunks 8 --batch-size 1 --device CPU --rebuild" in command
        for command in probe["commands"]
    )
    assert "abyss-machine nervous semantic-maintain --dry-run --json" in probe["insufficient_commands"]


def test_artifact_inspection_process_is_not_live_usage(tmp_path: Path, abyss_machine_module) -> None:
    machine = abyss_machine_module
    artifact = tmp_path / "cache"
    artifact.mkdir()

    assert machine.artifact_process_ref_is_inspection(
        artifact,
        "zsh",
        f"zsh -c abyss-machine artifacts usage {artifact} --json | jq .summary",
    )
    assert not machine.artifact_process_ref_is_inspection(
        artifact,
        "server",
        f"/usr/local/bin/server --cache-dir {artifact}",
    )


def test_dictation_openvino_artifact_classifies_active_route_high(tmp_path: Path, monkeypatch, abyss_machine_module) -> None:
    machine = abyss_machine_module
    artifact = tmp_path / "openvino" / "dictation-server"
    artifact.mkdir(parents=True)
    _quiet_evidence(monkeypatch, machine)
    monkeypatch.setattr(machine, "artifact_service_refs", lambda spec: {"active": True, "units": [{"unit": "abyss-dictation-server.service"}]})

    record = machine.artifact_record_for_spec(
        {
            "id": "ai_openvino_dictation_server",
            "path": str(artifact),
            "kind": "openvino-compile-cache",
            "owner_guess": "abyss-machine:dictation",
            "source_route": "abyss-dictation-server.service with ABYSS_OPENVINO_CACHE_DIR",
            "config_tokens": ["ABYSS_OPENVINO_CACHE_DIR", "abyss-dictation-server"],
            "expected_services": ["abyss-dictation-server.service"],
            "cleanup_posture": "do-not-clean-without-controlled-dictation-test",
            "workload_probe": "dictation",
        }
    )

    assert record["classification"] == "active-route"
    assert record["confidence"] == "high"
    assert record["decision"]["decision"] == "do-not-clean-without-controlled-workload-test"
    assert "active_service_route" in record["decision"]["reasons"]


def test_semantic_embedding_with_backup_and_no_live_refs_is_quarantine_first(tmp_path: Path, monkeypatch, abyss_machine_module) -> None:
    machine = abyss_machine_module
    artifact = tmp_path / "openvino" / "semantic-embedding-Qwen3-Embedding-0.6B-int8-ov-44a80578e6d51bf5"
    artifact.mkdir(parents=True)
    _quiet_evidence(monkeypatch, machine)

    record = machine.artifact_record_for_spec(
        {
            "id": "ai_openvino_semantic_embedding_qwen3",
            "path": str(artifact),
            "kind": "openvino-compile-cache",
            "owner_guess": "abyss-machine:nervous-semantic",
            "source_route": "OpenVINO embedding eval/canary cache",
            "config_tokens": ["semantic-embedding-Qwen3", "Qwen3-Embedding-0.6B"],
            "historical_ref_paths": [str(tmp_path / "canary.json")],
            "cleanup_posture": "quarantine-first",
            "workload_probe": "nervous-semantic",
        }
    )

    assert record["classification"] == "quarantine-first"
    assert record["confidence"] == "medium"
    assert record["decision"]["decision"] == "controlled-quarantine-plus-workload-probe-before-removal"
    assert "backup_state_known" in record["decision"]["reasons"]


def test_artifact_cli_paths_emits_json_contract(run_abyss_machine) -> None:
    result = run_abyss_machine("artifacts", "paths", "--json")

    assert result.returncode == 0, result.stderr[-1000:]
    payload = parse_json_stdout(result)
    assert payload["schema"] == "abyss_machine_artifacts_paths_v1"
    assert payload["policy"]["automatic_deletion"] is False
    assert "usage" in payload
    assert "timeline" in payload
