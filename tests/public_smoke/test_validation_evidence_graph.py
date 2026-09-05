from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

pytest_scheduler_experiment = importlib.import_module("scripts.pytest_scheduler_experiment")
release_check = importlib.import_module("scripts.release_check")
validation_evidence_graph = importlib.import_module("scripts.validation_evidence_graph")
validation_scheduler_experiment = importlib.import_module(
    "scripts.validation_scheduler_experiment"
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sdk_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "aoa-sdk"
    runner = root / validation_evidence_graph.SDK_RUNNER_RELATIVE_PATH
    runner.parent.mkdir(parents=True)
    runner.write_text("raise SystemExit(0)\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "validation@example.invalid")
    _git(root, "config", "user.name", "Validation Test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    monkeypatch.setattr(validation_evidence_graph, "SDK_PIN", _git(root, "rev-parse", "HEAD"))
    return root


def test_owner_graph_preserves_serial_leaf_scope_with_only_pinned_scheduler_delta() -> None:
    validation_evidence_graph.require_schedule_equivalent_serial_inventory()


def test_public_smoke_node_owns_first_run_projection_evidence() -> None:
    manifest = json.loads(
        validation_evidence_graph.MANIFEST_PATH.read_text(encoding="utf-8")
    )
    first_run_nodes = [
        node for node in manifest["nodes"] if node["id"] == "first-run-installed-projection"
    ]
    public_smoke = next(
        node for node in manifest["nodes"] if node["id"] == "public-smoke-tests"
    )

    assert first_run_nodes == []
    assert "first-run-installed-projection" in public_smoke["provides_evidence"]
    assert public_smoke["steps"][0]["argv"] == [
        "{python}",
        "-m",
        "pytest",
        "-q",
        "-n",
        "2",
        "--dist",
        "loadfile",
    ]


def test_inventory_guard_reports_an_omitted_serial_obligation(tmp_path: Path) -> None:
    payload = json.loads(validation_evidence_graph.MANIFEST_PATH.read_text(encoding="utf-8"))
    source_node = next(node for node in payload["nodes"] if node["id"] == "public-source-contracts")
    source_node["steps"].pop()
    manifest = tmp_path / "validation-graph.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(validation_evidence_graph.AdapterError, match="serial leaf scope"):
        validation_evidence_graph.require_schedule_equivalent_serial_inventory(manifest)


def test_inventory_guard_rejects_a_pytest_selection_change(tmp_path: Path) -> None:
    payload = json.loads(validation_evidence_graph.MANIFEST_PATH.read_text(encoding="utf-8"))
    pytest_node = next(node for node in payload["nodes"] if node["id"] == "public-smoke-tests")
    pytest_node["steps"][0]["argv"].append("tests/public_smoke/test_bootstrap.py")
    manifest = tmp_path / "validation-graph.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(validation_evidence_graph.AdapterError, match="serial leaf scope"):
        validation_evidence_graph.require_schedule_equivalent_serial_inventory(manifest)


def test_pytest_scheduler_requires_exact_distribution_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        validation_evidence_graph.metadata,
        "version",
        lambda _distribution: validation_evidence_graph.PYTEST_XDIST_PIN,
    )
    validation_evidence_graph.require_pinned_pytest_scheduler()

    monkeypatch.setattr(validation_evidence_graph.metadata, "version", lambda _name: "9.9.9")
    with pytest.raises(validation_evidence_graph.AdapterError, match="pin mismatch"):
        validation_evidence_graph.require_pinned_pytest_scheduler()


def test_sdk_runner_requires_exact_clean_git_top_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk_root = _sdk_checkout(tmp_path, monkeypatch)
    runner = validation_evidence_graph.require_pinned_sdk_runner(sdk_root)
    assert runner == sdk_root / validation_evidence_graph.SDK_RUNNER_RELATIVE_PATH

    nested = sdk_root / "nested"
    nested.mkdir()
    with pytest.raises(validation_evidence_graph.AdapterError, match="Git top-level"):
        validation_evidence_graph.require_pinned_sdk_runner(nested)

    runner.write_text("raise SystemExit(1)\n", encoding="utf-8")
    with pytest.raises(validation_evidence_graph.AdapterError, match="must be clean"):
        validation_evidence_graph.require_pinned_sdk_runner(sdk_root)


def test_explicit_sdk_root_propagates_to_nested_graph_contract(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    environment = validation_evidence_graph.runner_environment(sdk_root)

    assert environment[validation_evidence_graph.SDK_ROOT_ENV] == str(sdk_root.resolve())


def test_release_check_uses_graph_default_and_keeps_explicit_serial_rollback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.delenv(release_check.VALIDATION_MODE_ENV, raising=False)
    monkeypatch.setattr(
        release_check,
        "run_step",
        lambda label, command: calls.append((label, command)) or 0,
    )
    monkeypatch.setattr(release_check, "run_lane", lambda lane: 0)

    assert release_check.main([]) == 0
    assert calls == [
        (
            "full owner claim/evidence validation graph",
            (
                sys.executable,
                release_check.GRAPH_ADAPTER,
                "--profile",
                "full",
            ),
        )
    ]

    calls.clear()
    assert release_check.main(["--mode", "serial"]) == 0
    assert calls == []

    receipt = tmp_path / "receipt.json"
    sdk_root = tmp_path / "sdk"
    assert (
        release_check.main(
            [
                "--mode",
                "graph",
                "--receipt",
                str(receipt),
                "--max-workers",
                "2",
                "--sdk-root",
                str(sdk_root),
            ]
        )
        == 0
    )
    assert calls == [
        (
            "full owner claim/evidence validation graph",
            (
                sys.executable,
                release_check.GRAPH_ADAPTER,
                "--profile",
                "full",
                "--receipt",
                str(receipt),
                "--max-workers",
                "2",
                "--sdk-root",
                str(sdk_root),
            ),
        )
    ]


def test_static_pytest_shards_are_disjoint_complete_and_deterministic() -> None:
    files = pytest_scheduler_experiment.public_test_files()
    first = pytest_scheduler_experiment.static_shards(files)
    second = pytest_scheduler_experiment.static_shards(files)

    assert first == second
    assert all(first)
    assert set(first[0]).isdisjoint(first[1])
    assert sorted([*first[0], *first[1]]) == files
    commands, recorded = pytest_scheduler_experiment.method_commands("static-2")
    assert len(commands) == len(recorded) == 2
    assert sorted(path for shard in recorded for path in shard) == [
        path.relative_to(REPO_ROOT).as_posix() for path in files
    ]


def test_duration_node_shards_are_disjoint_complete_deterministic_and_balanced() -> None:
    nodeids = ["tests/a.py::test_a", "tests/b.py::test_b", "tests/c.py::test_c", "tests/d.py::test_d"]
    durations = {
        nodeids[0]: 8.0,
        nodeids[1]: 6.0,
        nodeids[2]: 2.0,
        nodeids[3]: 1.0,
    }

    first, first_profile = pytest_scheduler_experiment.duration_node_shards(
        nodeids,
        durations,
    )
    second, second_profile = pytest_scheduler_experiment.duration_node_shards(
        nodeids,
        durations,
    )
    commands, recorded, command_profile = pytest_scheduler_experiment.duration_shard_commands(
        nodeids,
        durations,
    )

    assert first == second == recorded == [
        [nodeids[0], nodeids[3]],
        [nodeids[1], nodeids[2]],
    ]
    assert first_profile == second_profile == command_profile
    assert set(first[0]).isdisjoint(first[1])
    assert sorted([*first[0], *first[1]]) == sorted(nodeids)
    assert first_profile["matching_nodeids"] == 4
    assert first_profile["missing_nodeids"] == []
    assert first_profile["extra_nodeids"] == []
    assert first_profile["shard_estimated_seconds"] == [9.0, 8.0]
    assert [command[4:] for command in commands] == first


def test_host_contract_scheduler_keeps_exact_quick_suite_and_disjoint_static_shards() -> None:
    files = pytest_scheduler_experiment.suite_test_files("host-contract-quick")
    commands, recorded = pytest_scheduler_experiment.method_commands(
        "static-2",
        "host-contract-quick",
    )

    assert len(commands) == len(recorded) == 2
    assert sorted(path for shard in recorded for path in shard) == [
        path.relative_to(REPO_ROOT).as_posix() for path in files
    ]
    assert set(recorded[0]).isdisjoint(recorded[1])
    for command in commands:
        assert command[-2:] == [
            "-m",
            pytest_scheduler_experiment.HOST_CONTRACT_QUICK_MARKERS,
        ]


@pytest.mark.parametrize(
    ("method", "workers", "distribution"),
    [
        ("xdist-2", "2", "load"),
        ("xdist-3", "3", "load"),
        ("xdist-4", "4", "load"),
        ("xdist-2-loadfile", "2", "loadfile"),
        ("xdist-2-loadscope", "2", "loadscope"),
        ("xdist-2-worksteal", "2", "worksteal"),
    ],
)
def test_host_contract_scheduler_names_worker_count_and_distribution(
    method: str,
    workers: str,
    distribution: str,
) -> None:
    commands, recorded = pytest_scheduler_experiment.method_commands(
        method,
        "host-contract-quick",
    )

    assert recorded == []
    assert len(commands) == 1
    assert commands[0][3:8] == ["-q", "-n", workers, "--dist", distribution]
    assert pytest_scheduler_experiment._collection_command(commands[0]) == [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "tests/host_contract",
        "-m",
        pytest_scheduler_experiment.HOST_CONTRACT_QUICK_MARKERS,
    ]


def test_scheduler_inventory_comparison_fails_closed_on_missing_extra_or_duplicate_nodes() -> None:
    exact = pytest_scheduler_experiment._inventory_comparison(
        ["tests/a.py::test_a", "tests/b.py::test_b"],
        [["tests/b.py::test_b"], ["tests/a.py::test_a"]],
    )
    changed = pytest_scheduler_experiment._inventory_comparison(
        ["tests/a.py::test_a", "tests/b.py::test_b"],
        [["tests/a.py::test_a", "tests/a.py::test_a", "tests/c.py::test_c"]],
    )

    assert exact["exact"] is True
    assert exact["expected_sha256"] == exact["actual_sha256"]
    assert changed["exact"] is False
    assert changed["duplicates"] == ["tests/a.py::test_a"]
    assert changed["missing"] == ["tests/b.py::test_b"]
    assert changed["extra"] == ["tests/a.py::test_a", "tests/c.py::test_c"]


def test_scheduler_execution_inventory_requires_one_terminal_report_per_expected_node() -> None:
    expected = ["tests/a.py::test_a", "tests/b.py::test_b"]
    exact = pytest_scheduler_experiment._execution_inventory_from_events(
        expected,
        [
            {"event": "collection", "worker": "gw0", "nodeids": expected},
            {"event": "collection", "worker": "gw1", "nodeids": expected},
            {"event": "report", "nodeid": expected[0], "when": "setup", "outcome": "passed", "duration_seconds": 0.1, "worker": "gw0"},
            {"event": "report", "nodeid": expected[0], "when": "call", "outcome": "passed", "duration_seconds": 0.4, "worker": "gw0"},
            {"event": "report", "nodeid": expected[0], "when": "teardown", "outcome": "passed", "duration_seconds": 0.1, "worker": "gw0"},
            {"event": "report", "nodeid": expected[1], "when": "setup", "outcome": "skipped", "duration_seconds": 0.2, "worker": "gw1"},
        ],
    )
    duplicate = pytest_scheduler_experiment._execution_inventory_from_events(
        expected,
        [
            {"event": "collection", "worker": "gw0", "nodeids": expected},
            {"event": "report", "nodeid": expected[0], "when": "call", "outcome": "passed"},
            {"event": "report", "nodeid": expected[0], "when": "call", "outcome": "passed"},
            {"event": "report", "nodeid": expected[1], "when": "call", "outcome": "passed"},
        ],
    )

    assert exact["passed"] is True
    assert exact["terminal_outcomes"] == {"passed": 1, "skipped": 1}
    assert exact["duration_summary"] == {
        "test_phase_total_seconds": 0.8,
        "worker_test_phase_seconds": {"gw0": 0.6, "gw1": 0.2},
        "slowest": [
            {"nodeid": expected[0], "duration_seconds": 0.6, "worker": "gw0"},
            {"nodeid": expected[1], "duration_seconds": 0.2, "worker": "gw1"},
        ],
    }
    assert duplicate["passed"] is False
    assert duplicate["ambiguous_terminal_nodeids"] == [expected[0]]
    assert duplicate["comparison"]["duplicates"] == [expected[0]]


def test_scheduler_timeout_terminates_only_its_owned_process_group() -> None:
    result = pytest_scheduler_experiment._run_captured_process(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        env=pytest_scheduler_experiment._test_environment(),
        timeout_seconds=0.05,
    )

    assert result["returncode"] == 124
    assert result["timed_out"] is True
    assert result["timeout_seconds"] == 0.05
    assert "scheduler process group timed out" in result["stderr"]


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("xdist-2", ["{python}", "-m", "pytest", "-q", "-n", "2"]),
        ("xdist-4", ["{python}", "-m", "pytest", "-q", "-n", "4"]),
        (
            "static-2",
            [
                "{python}",
                "scripts/pytest_scheduler_experiment.py",
                "--method",
                "static-2",
                "--receipt",
                "tmp/pytest.json",
            ],
        ),
    ],
)
def test_combined_experiment_changes_only_the_pytest_scheduler(
    method: str, expected: list[str]
) -> None:
    manifest = validation_scheduler_experiment.build_experimental_manifest(
        method,
        REPO_ROOT / "tmp" / "pytest.json",
    )
    pytest_node = next(
        node for node in manifest["nodes"] if node["id"] == "public-smoke-tests"
    )
    assert pytest_node["steps"][0]["argv"] == expected

    canonical = json.loads(
        validation_evidence_graph.MANIFEST_PATH.read_text(encoding="utf-8")
    )
    pytest_node["steps"][0]["argv"] = validation_scheduler_experiment.CANONICAL_PYTEST_ARGV
    manifest["graph_id"] = canonical["graph_id"]
    assert manifest == canonical
