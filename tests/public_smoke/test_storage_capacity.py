from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[2]
CAPACITY_SUCCESS_SCRIPT = dedent(
    """
    from abyss_machine import storage_capacity, storage_forecast

    def fixture_measure(path, timestamp):
        return {
            "path": str(path),
            "timestamp": timestamp,
            "filesystem_key": "fixture:" + str(path),
            "total_bytes": 100 * 1024**3,
            "available_to_user_bytes": 20 * 1024**3,
            "reserved_bytes": 0,
        }

    storage_forecast._measure = fixture_measure
    raise SystemExit(storage_capacity.main(["--json"]))
    """
)
CAPACITY_FAILURE_SCRIPT = dedent(
    """
    from abyss_machine import storage_capacity, storage_forecast

    def fixture_measure_failure(path, timestamp):
        return {
            "path": str(path),
            "timestamp": timestamp,
            "error": "fixture_mount_missing",
        }

    storage_forecast._measure = fixture_measure_failure
    raise SystemExit(storage_capacity.main(["--json"]))
    """
)


def _run_capacity(state_root: Path) -> dict:
    env = {**os.environ, "ABYSS_MACHINE_STATE_ROOT": str(state_root), "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-c", CAPACITY_SUCCESS_SCRIPT],
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


def test_capacity_measurement_failure_returns_nonzero_without_rewriting_history(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_path = state_root / "storage" / "monitor" / "capacity.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        '{"schema":"abyss_machine_capacity_samples_v1","samples":[{"path":"/","filesystem_key":"old","timestamp":1,"available_to_user_bytes":1}]}\n',
        encoding="utf-8",
    )
    before = state_path.read_bytes()
    env = {**os.environ, "ABYSS_MACHINE_STATE_ROOT": str(state_root), "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-c", CAPACITY_FAILURE_SCRIPT],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert all(root["status"] == "measurement_error" for root in payload["roots"])
    assert state_path.read_bytes() == before
