from __future__ import annotations

import json
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
    assert report["privacy"]["raw_runtime_json_included"] is False


def test_source_install_runtime_parity_script_supports_advisory_mode(tmp_path: Path) -> None:
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
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == host_lifecycle_parity.SCHEMA
    assert payload["ok"] is False
    assert payload["content_parity"]["cli"]["status"] == "failed"
