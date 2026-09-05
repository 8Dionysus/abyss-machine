from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_capacity(state_root: Path) -> dict:
    env = {**os.environ, "ABYSS_MACHINE_STATE_ROOT": str(state_root), "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.storage_capacity", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    return json.loads(result.stdout)


def test_capacity_sampling_writes_bounded_state_under_configured_state_root(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    first = _run_capacity(state_root)
    second = _run_capacity(state_root)

    assert first["schema"] == "abyss_machine_storage_capacity_v1"
    assert first["state_path"] == str(state_root / "storage" / "monitor" / "capacity.json")
    assert first["paths"] == ["/", "/srv"]
    assert first["minimum_span_seconds"] == 3 * 3600
    assert first["history_limit_per_root"] == 168
    assert all(root["free_floor_bytes"] == 5 * 1024**3 for root in first["roots"])

    state_path = state_root / "storage" / "monitor" / "capacity.json"
    document = json.loads(state_path.read_text(encoding="utf-8"))
    assert document["schema"] == "abyss_machine_capacity_samples_v1"
    assert len(document["samples"]) == 2
    assert second["roots"]
