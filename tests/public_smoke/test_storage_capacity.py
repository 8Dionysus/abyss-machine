from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import storage_capacity  # noqa: E402


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


def test_expected_code_generation_guard_accepts_only_exact_installed_module_path() -> None:
    generation = "a" * 64
    expected_module = (
        storage_capacity.CODE_GENERATIONS_ROOT
        / generation
        / "abyss_machine"
        / "storage_capacity.py"
    )

    accepted = storage_capacity.expected_code_generation_guard(
        generation,
        module_path=expected_module,
    )
    source_checkout = storage_capacity.expected_code_generation_guard(
        generation,
        module_path=Path("/tmp/source-checkout/abyss_machine/storage_capacity.py"),
    )
    invalid = storage_capacity.expected_code_generation_guard("not-a-generation")

    assert accepted["ok"] is True
    assert accepted["module_path"] == str(expected_module)
    assert source_checkout["ok"] is False
    assert source_checkout["error"] == "expected_code_generation_mismatch"
    assert invalid["ok"] is False
    assert invalid["error"] == "expected_code_generation_invalid"


def test_expected_code_generation_guard_rejects_generation_symlink_escape(
    monkeypatch,
    tmp_path: Path,
) -> None:
    generation = "c" * 64
    generations_root = tmp_path / "generations"
    escaped_module = tmp_path / "escaped" / "abyss_machine" / "storage_capacity.py"
    escaped_module.parent.mkdir(parents=True)
    escaped_module.touch()
    generation_dir = generations_root / generation
    generation_dir.parent.mkdir(parents=True)
    generation_dir.symlink_to(escaped_module.parents[1], target_is_directory=True)
    monkeypatch.setattr(storage_capacity, "CODE_GENERATIONS_ROOT", generations_root)

    result = storage_capacity.expected_code_generation_guard(
        generation,
        module_path=generation_dir / "abyss_machine" / "storage_capacity.py",
    )

    assert result["ok"] is False
    assert result["error"] == "expected_code_generation_mismatch"
    assert result["expected_module_path"] == str(
        generation_dir / "abyss_machine" / "storage_capacity.py"
    )
    assert result["resolved_module_path"] == str(escaped_module.resolve())


def test_expected_code_generation_failure_is_json_and_does_not_observe_or_write_state(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state" / "storage" / "monitor" / "capacity.json"

    def forbidden_observation() -> dict[str, object]:
        raise AssertionError("capacity observation must not run after generation rejection")

    monkeypatch.setattr(storage_capacity, "capacity_observation", forbidden_observation)
    monkeypatch.setattr(storage_capacity, "CAPACITY_STATE_PATH", state_path)

    exit_code = storage_capacity.main(
        ["--expected-code-generation", "b" * 64, "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"] == "expected_code_generation_mismatch"
    assert payload["code_generation_guard"]["checked"] is True
    assert not state_path.exists()
