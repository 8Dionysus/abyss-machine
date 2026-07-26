from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import host_lifecycle_parity


def _seed_source_tree(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    package = repo / "src" / "abyss_machine"
    package.mkdir(parents=True)
    (package / "cli.py").write_text("print('source cli')\n", encoding="utf-8")
    (package / "__init__.py").write_text("__version__ = 'test'\n", encoding="utf-8")
    (package / "extra.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "generated").mkdir()
    (repo / "generated" / "contract_abi_signatures.min.json").write_text("{}\n", encoding="utf-8")
    (repo / "manifests").mkdir()
    (repo / "manifests" / "repo_scaffold.manifest.json").write_text("{}\n", encoding="utf-8")
    return repo


def test_content_parity_summary_is_compact_and_detects_drift(tmp_path: Path) -> None:
    repo = _seed_source_tree(tmp_path)
    installed_libexec = tmp_path / "installed" / "libexec"
    installed_share = tmp_path / "installed" / "share" / "abyss-machine"
    installed_package = installed_libexec / "abyss_machine"
    installed_package.mkdir(parents=True)
    installed_share.mkdir(parents=True)
    installed_cli = installed_libexec / "abyss-machine"
    installed_cli.write_text("print('old cli')\n", encoding="utf-8")
    (installed_package / "__init__.py").write_text("__version__ = 'test'\n", encoding="utf-8")

    report = host_lifecycle_parity.content_parity_summary(
        repo_root=repo,
        installed_cli=installed_cli,
        installed_libexec_dir=installed_libexec,
        installed_share_root=installed_share,
        sample_limit=1,
    )

    assert report["status"] == "failed"
    assert report["cli"]["status"] == "failed"
    assert report["package"]["missing_count"] == 2
    assert len(report["package"]["missing_sample"]) == 1
    assert report["public_seed"]["generated"]["missing_count"] == 1
    assert "print('source cli')" not in json.dumps(report)


def test_runtime_projection_summarizes_json_without_raw_payload() -> None:
    stdout = json.dumps(
        {
            "schema": "example_v1",
            "ok": True,
            "summary": {"status": "warn"},
            "checks": [{"level": "ok"}, {"level": "warn"}],
            "private_detail": "do not copy me into reports",
        }
    )

    row = host_lifecycle_parity.compact_command_result(
        name="example",
        command=["abyss-machine", "example", "--json"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )

    assert row["status"] == "ok"
    assert row["json_ok"] is True
    assert row["projection"]["schema"] == "example_v1"
    assert row["projection"]["warning_count"] == 1
    assert "private_detail" not in json.dumps(row)
    assert "do not copy me" not in json.dumps(row)


def test_runtime_projection_omits_nested_status_payloads() -> None:
    stdout = json.dumps(
        {
            "schema": "example_v1",
            "ok": True,
            "status": {"private_path": "/var/lib/abyss-machine/private/latest.json"},
            "summary": {"status": "ok"},
        }
    )

    row = host_lifecycle_parity.compact_command_result(
        name="example",
        command=["abyss-machine", "example", "--json"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )

    assert row["projection"]["status"] == "ok"
    assert "/var/lib/abyss-machine/private" not in json.dumps(row)


def test_runtime_projection_omits_raw_stderr_for_non_json_failures() -> None:
    row = host_lifecycle_parity.compact_command_result(
        name="example",
        command=["abyss-machine", "example", "--json"],
        returncode=2,
        stdout="",
        stderr="private host path: /private/operator/secret",
    )

    rendered = json.dumps(row)
    assert row["status"] == "failed"
    assert row["stderr_bytes"] > 0
    assert "stderr_tail" not in row
    assert "/private/operator/secret" not in rendered


def test_runtime_check_profiles_are_module_owned_and_deduped() -> None:
    assert host_lifecycle_parity.select_runtime_check_names() == ["enter"]
    assert host_lifecycle_parity.select_runtime_check_names(runtime_profiles=["diagnostic-read"]) == ["doctor-paths"]
    assert host_lifecycle_parity.select_runtime_check_names(runtime_profiles=["storage-refresh"]) == ["storage-cleanup-plan"]
    assert host_lifecycle_parity.select_runtime_check_names(runtime_profiles=["typing-read"]) == ["typing-codex-hook-status"]
    assert host_lifecycle_parity.select_runtime_check_names(runtime_profiles=["ai-llm-refresh"]) == [
        "ai-validate",
        "ai-llm-validate",
        "ai-llm-resident-validate",
        "ai-llm-workhorse-validate",
    ]
    assert host_lifecycle_parity.select_runtime_check_names(
        runtime_profiles=["base", "ai-llm-refresh"],
        runtime_checks=["enter", "doctor-paths"],
    ) == [
        "enter",
        "ai-validate",
        "ai-llm-validate",
        "ai-llm-resident-validate",
        "ai-llm-workhorse-validate",
        "doctor-paths",
    ]
    assert host_lifecycle_parity.runtime_command_effect_catalog()["doctor-paths"] == "read_only"
    assert host_lifecycle_parity.runtime_command_effect_catalog()["typing-codex-hook-status"] == "read_only"
    assert host_lifecycle_parity.runtime_command_effect_catalog()["enter"] == "refresh_latest"
    assert host_lifecycle_parity.runtime_command_effect_catalog()["storage-cleanup-plan"] == "refresh_latest"
    assert set(host_lifecycle_parity.runtime_command_effect_catalog()) == set(host_lifecycle_parity.runtime_command_catalog())
    assert host_lifecycle_parity.runtime_refresh_check_names(["enter", "doctor", "ai-validate"]) == [
        "enter",
        "doctor",
        "ai-validate",
    ]
    assert host_lifecycle_parity.runtime_command_catalog()["doctor-machine-report"] == [
        "abyss-machine",
        "doctor",
        "machine-report",
        "--json",
        "--no-thermal-sample",
    ]
    assert host_lifecycle_parity.runtime_command_catalog()["typing-codex-hook-status"] == [
        "abyss-machine",
        "typing",
        "codex-hook-status",
        "--json",
        "--no-write",
    ]


def test_collect_runtime_checks_uses_fake_runner_and_catalog() -> None:
    calls: list[tuple[str, list[str], float]] = []

    def fake_run(name: str, command: list[str], timeout: float) -> dict[str, object]:
        calls.append((name, command, timeout))
        return {"name": name, "command": command, "status": "ok"}

    rows = host_lifecycle_parity.collect_runtime_checks(
        selected_checks=["enter", "ai-llm-validate"],
        command_catalog=host_lifecycle_parity.runtime_command_catalog(),
        run_check=fake_run,
        timeout=7.5,
    )

    assert [row["name"] for row in rows] == ["enter", "ai-llm-validate"]
    assert calls == [
        ("enter", ["abyss-machine", "enter", "--json"], 7.5),
        ("ai-llm-validate", ["abyss-machine", "ai", "llm", "validate", "--json"], 7.5),
    ]


def test_runtime_summary_treats_json_blocked_as_failure() -> None:
    row = host_lifecycle_parity.compact_command_result(
        name="doctor-machine-report",
        command=["abyss-machine", "doctor", "machine-report", "--json"],
        returncode=0,
        stdout=json.dumps({"ok": False, "status": "blocked", "checks": []}),
        stderr="",
    )

    summary = host_lifecycle_parity.runtime_summary([row])

    assert summary["status"] == "failed"
    assert summary["failure_checks"] == ["doctor-machine-report"]


def test_build_parity_document_combines_content_and_runtime(tmp_path: Path) -> None:
    repo = _seed_source_tree(tmp_path)
    installed_libexec = tmp_path / "installed" / "libexec"
    installed_share = tmp_path / "installed" / "share" / "abyss-machine"
    installed_package = installed_libexec / "abyss_machine"
    installed_package.mkdir(parents=True)
    (installed_share / "generated").mkdir(parents=True)
    (installed_share / "manifests").mkdir(parents=True)
    installed_cli = installed_libexec / "abyss-machine"
    installed_cli.write_text((repo / "src" / "abyss_machine" / "cli.py").read_text(encoding="utf-8"), encoding="utf-8")
    for source in (repo / "src" / "abyss_machine").glob("*.py"):
        (installed_package / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    for root_id in ("generated", "manifests"):
        for source in (repo / root_id).glob("*"):
            (installed_share / root_id / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    runtime = [
        host_lifecycle_parity.compact_command_result(
            name="enter",
            command=["abyss-machine", "enter", "--json"],
            returncode=0,
            stdout=json.dumps({"ok": True, "checks": []}),
            stderr="",
        )
    ]
    report = host_lifecycle_parity.build_parity_document(
        generated_at="2026-06-28T00:00:00+00:00",
        repo_root=repo,
        installed_cli=installed_cli,
        installed_libexec_dir=installed_libexec,
        installed_share_root=installed_share,
        runtime_checks=runtime,
    )

    assert report["ok"] is True
    assert report["content_parity"]["status"] == "ok"
    assert report["runtime"]["status"] == "ok"
    assert report["next_actions"] == [
        {
            "id": "no_action_required",
            "status": "ok",
            "reason": "source, installed projection, and selected runtime checks agree",
        }
    ]
    assert report["privacy"]["raw_runtime_stderr_included"] is False
    assert report["privacy"]["raw_runtime_json_included"] is False


def test_parity_summary_document_omits_paths_digests_and_raw_runtime_details(tmp_path: Path) -> None:
    repo = _seed_source_tree(tmp_path)
    installed_libexec = tmp_path / "installed" / "libexec"
    installed_share = tmp_path / "installed" / "share" / "abyss-machine"
    installed_package = installed_libexec / "abyss_machine"
    installed_package.mkdir(parents=True)
    installed_share.mkdir(parents=True)
    installed_cli = installed_libexec / "abyss-machine"
    installed_cli.write_text("print('old cli')\n", encoding="utf-8")
    (installed_package / "__init__.py").write_text("__version__ = 'test'\n", encoding="utf-8")

    runtime = [
        {
            "name": "enter",
            "command": ["abyss-machine", "enter", "--json"],
            "status": "failed",
            "returncode": 1,
            "timed_out": False,
            "json_ok": False,
            "stdout_bytes": 0,
            "stderr_bytes": 39,
            "stderr_tail": "/var/lib/abyss-machine/private/latest.json",
        }
    ]
    report = host_lifecycle_parity.build_parity_document(
        generated_at="2026-06-28T00:00:00+00:00",
        repo_root=repo,
        installed_cli=installed_cli,
        installed_libexec_dir=installed_libexec,
        installed_share_root=installed_share,
        runtime_checks=runtime,
        sample_limit=2,
    )

    summary = host_lifecycle_parity.parity_summary_document(report)
    rendered = json.dumps(summary, sort_keys=True)

    assert summary["projection"] == "summary"
    assert summary["ok"] is False
    assert summary["content_parity"]["package"]["missing_count"] == 2
    assert summary["runtime"]["failure_checks"] == ["enter"]
    assert "source_sha256" not in rendered
    assert "installed_sha256" not in rendered
    assert str(tmp_path) not in rendered
    assert "command" not in summary["runtime"]["checks"][0]
    assert "stderr_tail" not in rendered
    assert "/var/lib/abyss-machine/private" not in rendered


def test_source_install_runtime_parity_script_supports_advisory_mode(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validators" / "source_install_runtime_parity.py"),
            "--host-cli",
            str(tmp_path / "missing-cli"),
            "--host-libexec-dir",
            str(tmp_path / "missing-libexec"),
            "--host-share-root",
            str(tmp_path / "missing-share"),
            "--runtime-check",
            "enter",
            "--allow-runtime-refresh",
            "--runtime-timeout",
            "0.01",
            "--advisory",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
        env={**os.environ, "PATH": str(empty_path)},
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == host_lifecycle_parity.SCHEMA
    assert payload["ok"] is False
    assert payload["content_parity"]["cli"]["status"] == "failed"
    runtime_row = payload["runtime"]["checks"][0]
    assert runtime_row["returncode"] == 127
    assert runtime_row["error_kind"] == "missing_runtime_command"
    assert "stderr_tail" not in runtime_row
    assert payload["next_actions"][0]["id"] == "sync_installed_projection"
    assert payload["next_actions"][0]["status"] == "operator_required"
    assert payload["next_actions"][1]["id"] == "rerun_runtime_parity"
    assert payload["next_actions"][1]["status"] == "after_projection_sync"


def test_source_install_runtime_parity_default_enter_requires_refresh_allowance(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validators" / "source_install_runtime_parity.py"),
            "--host-cli",
            str(tmp_path / "missing-cli"),
            "--host-libexec-dir",
            str(tmp_path / "missing-libexec"),
            "--host-share-root",
            str(tmp_path / "missing-share"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["refresh_checks"] == ["enter"]
    assert "--allow-runtime-refresh" in payload["error"]


def test_source_install_runtime_parity_script_emits_summary_projection(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validators" / "source_install_runtime_parity.py"),
            "--host-cli",
            str(tmp_path / "missing-cli"),
            "--host-libexec-dir",
            str(tmp_path / "missing-libexec"),
            "--host-share-root",
            str(tmp_path / "missing-share"),
            "--runtime-check",
            "enter",
            "--allow-runtime-refresh",
            "--runtime-timeout",
            "0.01",
            "--advisory",
            "--summary",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    rendered = json.dumps(payload, sort_keys=True)
    assert payload["schema"] == host_lifecycle_parity.SCHEMA
    assert payload["projection"] == "summary"
    assert payload["ok"] is False
    assert payload["content_parity"]["cli"]["installed_exists"] is False
    assert "repo_root" not in payload
    assert "installed" not in payload
    assert "source_sha256" not in rendered
    assert "installed_sha256" not in rendered
    assert str(tmp_path) not in rendered


def test_source_install_runtime_parity_requires_explicit_refresh_allowance(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validators" / "source_install_runtime_parity.py"),
            "--host-cli",
            str(tmp_path / "missing-cli"),
            "--host-libexec-dir",
            str(tmp_path / "missing-libexec"),
            "--host-share-root",
            str(tmp_path / "missing-share"),
            "--runtime-profile",
            "ai-llm-refresh",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["refresh_checks"] == [
        "ai-validate",
        "ai-llm-validate",
        "ai-llm-resident-validate",
        "ai-llm-workhorse-validate",
    ]
    assert "--allow-runtime-refresh" in payload["error"]
