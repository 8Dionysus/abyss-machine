from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import benchmark_nervous_pipeline_dag as benchmark


def _fact_snapshot(generated_at: str) -> dict[str, object]:
    return {
        "schema": "abyss_machine_nervous_fact_snapshot_v1",
        "version": "test",
        "generated_at": generated_at,
        "capture": {
            "sources": ["abyss_machine_facts"],
            "trigger": "test",
            "manual": True,
            "raw_private_content": False,
        },
        "privacy": {"global_pause": False, "private_mode": False},
        "summary": {"facts": 1, "skipped": 0},
        "facts": [
            {
                "name": "storage_latest",
                "summary": {
                    "root_used_percent": 84.0,
                    "srv_used_percent": 40.0,
                    "root_warning": False,
                    "root_critical": False,
                    "podman_migration_status": "not_started",
                },
            }
        ],
    }


def test_real_session_pipeline_benchmark_proves_delta_oracle_parity_without_source_disclosure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    facts_root = tmp_path / "private-fixture-root"
    fact_path = facts_root / "2026" / "08" / "2026-08-13.jsonl"
    fact_path.parent.mkdir(parents=True)
    fact_path.write_text(
        json.dumps(_fact_snapshot("2026-08-13T22:00:00+00:00")) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        benchmark.cli,
        "nervous_effective_privacy",
        lambda *, write_latest: {"global_pause": False, "private_mode": False},
    )
    monkeypatch.setattr(
        benchmark.cli,
        "nervous_effective_sources",
        lambda *, write_latest: {
            "safe_now": {
                "abyss_machine_facts": {"enabled": True, "allowed": True},
            },
        },
    )
    monkeypatch.setattr(
        benchmark.cli,
        "nervous_thermal_event_thresholds",
        benchmark.cli.nervous_events_contracts.thermal_event_thresholds,
    )
    monkeypatch.setattr(
        benchmark.index_benchmark,
        "_git_source",
        lambda: {
            "head": "fixture",
            "dirty": False,
            "source_file_count": 1,
            "source_tree_sha256": "fixture",
        },
    )

    result = benchmark.run_pipeline(
        facts_source_root=facts_root,
        work_root=tmp_path / "work",
        keep_workdir=False,
        session_deltas=3,
    )

    assert result["comparison"]["logical_parity"] is True
    assert len(result["fixture"]["snapshot_identity_sha256"]) == 64
    assert len(result["environment"]["privacy_identity_sha256"]) == 64
    assert len(result["environment"]["sources_identity_sha256"]) == 64
    assert len(result["environment"]["event_derivation_identity"]) == 64
    assert len(result["environment"]["episode_derivation_identity"]) == 64
    assert len(result["environment"]["index_projection_identity"]) == 64
    assert result["comparison"]["parity"] == {
        "events": True,
        "episodes": True,
        "index": True,
    }
    assert result["fixture"]["session_deltas"] == 3
    assert len(result["session_deltas"]) == 3
    assert all(
        session["events"]["attestations"] == 2
        and session["index"]["source_scan"]["source_delta_attestations_admitted"] == 2
        for session in result["session_deltas"]
    )
    assert result["delta"]["events"]["strategy"] == "append_state_delta"
    assert result["delta"]["events"]["attestations"] == 2
    assert result["delta"]["episodes"]["strategy"] == "file_partition_delta"
    assert result["delta"]["index"]["strategy"] == "hybrid_partition_append_delta"
    assert result["delta"]["index"]["source_scan"]["source_delta_attestations_admitted"] == 2
    assert result["delta"]["index"]["delta"]["documents"] <= 8
    assert result["fixed_point"]["index"]["source_partitions"]["changed"] == 0
    assert str(facts_root) not in json.dumps(result, ensure_ascii=False)


def test_real_session_pipeline_failure_receipt_does_not_disclose_source_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    private_source = tmp_path / "private-customer-history"
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(
        benchmark.index_benchmark,
        "_git_source",
        lambda: {
            "head": "fixture",
            "dirty": False,
            "source_scope": "fixture",
            "source_file_count": 1,
            "source_tree_sha256": "fixture",
        },
    )

    returncode = benchmark.main([
        "--facts-root",
        str(private_source),
        "--work-root",
        str(tmp_path / "work"),
        "--receipt",
        str(receipt),
        "--quiet",
    ])
    result = json.loads(receipt.read_text(encoding="utf-8"))

    assert returncode == 1
    assert result["ok"] is False
    assert result["error_type"] == "ValueError"
    assert str(private_source) not in json.dumps(result, ensure_ascii=False)
