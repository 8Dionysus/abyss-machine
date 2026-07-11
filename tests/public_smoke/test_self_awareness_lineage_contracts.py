from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from abyss_machine import cli
from abyss_machine import self_awareness_lineage_contracts as lineage


def _paths(tmp_path: Path) -> lineage.SelfAwarenessLineagePaths:
    return lineage.SelfAwarenessLineagePaths(
        **{
            name: tmp_path / name / "latest.json"
            for name in lineage.SelfAwarenessLineagePaths.__dataclass_fields__
        }
    )


def _runtime() -> lineage.SelfAwarenessLineageRuntimePort:
    return lineage.SelfAwarenessLineageRuntimePort(
        latest_artifact_ref=lambda name, path, schema: {
            "name": name,
            "path": str(path),
            "exists": True,
            "schema": schema,
            "schema_ok": True,
            "sha256": "a" * 64,
        },
        path_exists=lambda _path: True,
        path_stat=lambda _path: SimpleNamespace(st_size=42),
        path_is_file=lambda _path: True,
        sha256_path=lambda _path: "b" * 64,
    )


def test_lineage_contracts_build_complete_e2e_proof(tmp_path: Path) -> None:
    chain = {
        str(key): True
        for spec in lineage.e2e_lineage_specs()
        for group in spec["chain_key_groups"]
        for key in group
    }
    proof = lineage.e2e_lineage_proof(
        generated_at="2026-07-11T00:00:00Z",
        run_id="saprobe-test",
        chain=chain,
        traceparent="00-" + ("a" * 32) + "-" + ("b" * 16) + "-01",
        synthetic_events=[{"event_id": "saevt-test"}],
        paths=_paths(tmp_path),
        config=lineage.SelfAwarenessLineageConfig("abyss_machine", "test"),
        runtime_port=_runtime(),
    )

    assert proof["ok"] is True
    assert proof["summary"]["missing_rows"] == []
    assert proof["summary"]["synthetic_event_ids"] == 1
    assert lineage.e2e_lineage_proof_complete(
        proof,
        config=lineage.SelfAwarenessLineageConfig("abyss_machine", "test"),
    )
    assert all(row["evidence_refs"] for row in proof["rows"])
    assert proof["policy"]["host_layer_mutates_stack"] is False


def test_lineage_contracts_use_runtime_port_for_path_fallback() -> None:
    path = Path("/var/lib/abyss-machine/self-awareness/probe/latest.json")
    packet = lineage.top_level_lineage_packet(
        generated_at="2026-07-11T00:00:00Z",
        source="probe",
        run_id="saprobe-test",
        chain={"probe": True},
        artifacts={"probe": path},
        e2e_lineage_proof={"ok": True, "summary": {"missing_rows": []}},
        config=lineage.SelfAwarenessLineageConfig("abyss_machine", "test"),
        runtime_port=_runtime(),
    )

    assert packet["complete"] is True
    assert packet["artifact_chain"] == [
        {
            "order": 1,
            "name": "probe",
            "path": str(path),
            "exists": True,
            "size_bytes": 42,
            "sha256": "b" * 64,
            "machine_owned_path": True,
        }
    ]
    assert (
        lineage.top_level_lineage_complete(
            packet,
            config=lineage.SelfAwarenessLineageConfig("abyss_machine", "test"),
        )
        is True
    )


def test_cli_lineage_proof_only_binds_typed_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_proof(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"schema": "synthetic-lineage"}

    monkeypatch.setattr(lineage, "e2e_lineage_proof", fake_proof)
    result = cli.self_awareness_e2e_lineage_proof(
        generated_at="2026-07-11T00:00:00Z",
        run_id="saprobe-test",
        chain={"probe": True},
    )

    assert result == {"schema": "synthetic-lineage"}
    assert isinstance(captured["paths"], lineage.SelfAwarenessLineagePaths)
    assert isinstance(captured["config"], lineage.SelfAwarenessLineageConfig)
    assert isinstance(captured["runtime_port"], lineage.SelfAwarenessLineageRuntimePort)
