from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli


def _patch_artifact_trust_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    runtime_root = tmp_path / "srv" / "abyss-machine" / "runtimes" / "artifact-trust"
    cache_root = tmp_path / "srv" / "abyss-machine" / "cache" / "artifact-trust"
    state_root = tmp_path / "var" / "lib" / "abyss-machine" / "artifacts"
    monkeypatch.setattr(cli, "ARTIFACT_TRUST_RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(cli, "ARTIFACT_TRUST_BIN_DIR", runtime_root / "bin")
    monkeypatch.setattr(cli, "ARTIFACT_TRUST_CACHE_ROOT", cache_root)
    monkeypatch.setattr(cli, "ARTIFACT_TRUST_PYTHON_VENV_DIR", runtime_root / "python")
    monkeypatch.setattr(cli, "ARTIFACT_TRUST_PYTHON_RECORD_PATH", runtime_root / "python-tools.json")
    monkeypatch.setattr(cli, "ARTIFACTS_TRUST_TOOLS_ROOT", state_root / "trust-tools")
    monkeypatch.setattr(cli, "ARTIFACTS_TRUST_TOOLS_LATEST_PATH", state_root / "trust-tools" / "latest.json")
    monkeypatch.setattr(cli, "ARTIFACTS_INDEX_PATH", state_root / "index.json")
    return {"runtime_root": runtime_root, "cache_root": cache_root, "state_root": state_root}


def _fake_python(path: Path) -> Path:
    script = path / "fake-python"
    script.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        "  venv=\"$3\"\n"
        "  mkdir -p \"$venv/bin\"\n"
        "  cat > \"$venv/bin/python\" <<'EOF'\n"
        "#!/bin/sh\n"
        "set -eu\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ]; then\n"
        "  bindir=$(dirname \"$0\")\n"
        "  cat > \"$bindir/in-toto-verify\" <<'TOOL'\n"
        "#!/bin/sh\n"
        "printf '%s\\n' 'in-toto-verify 3.1.0'\n"
        "TOOL\n"
        "  cat > \"$bindir/cyclonedx-py\" <<'TOOL'\n"
        "#!/bin/sh\n"
        "printf '%s\\n' '7.3.0'\n"
        "TOOL\n"
        "  chmod +x \"$bindir/in-toto-verify\" \"$bindir/cyclonedx-py\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n"
        "EOF\n"
        "  chmod +x \"$venv/bin/python\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_artifact_trust_tools_python_dry_run_does_not_create_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _patch_artifact_trust_roots(monkeypatch, tmp_path)
    fake_python = _fake_python(tmp_path)

    payload = cli.artifacts_trust_tools_python(
        apply=False,
        python_executable=str(fake_python),
        write_latest=False,
    )

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["package_lock"][0]["package"] == "in-toto"
    assert roots["runtime_root"].exists() is False
    assert "in-toto==3.1.0" in payload["actions"][1]["packages"]
    assert "cyclonedx-bom==7.3.0" in payload["actions"][1]["packages"]


def test_artifact_trust_tools_python_apply_exposes_managed_binaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _patch_artifact_trust_roots(monkeypatch, tmp_path)
    fake_python = _fake_python(tmp_path)

    payload = cli.artifacts_trust_tools_python(
        apply=True,
        python_executable=str(fake_python),
        write_latest=False,
    )

    assert payload["ok"] is True
    assert payload["dry_run"] is False
    assert (roots["runtime_root"] / "bin" / "in-toto-verify").is_symlink()
    assert (roots["runtime_root"] / "bin" / "cyclonedx-py").is_symlink()
    assert (roots["runtime_root"] / "python-tools.json").is_file()
    trust_tools = cli.artifacts_trust_tools(write_latest=False)
    assert trust_tools["tools"]["in_toto_verify"]["source"] == "host-managed-runtime"
    assert trust_tools["tools"]["in_toto_verify"]["version"]["version"] == "3.1.0"
    assert trust_tools["tools"]["cyclonedx_py"]["source"] == "host-managed-runtime"
    assert trust_tools["tools"]["cyclonedx_py"]["version"]["version"] == "7.3.0"
    assert "in_toto_verify" not in trust_tools["summary"]["missing_tools"]
    assert "cyclonedx_py" not in trust_tools["summary"]["missing_tools"]
    assert "slsa_in_toto" not in trust_tools["summary"]["missing_controls"]
    assert "sbom" not in trust_tools["summary"]["missing_controls"]


def test_artifact_trust_tools_python_refuses_to_overwrite_unmanaged_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _patch_artifact_trust_roots(monkeypatch, tmp_path)
    fake_python = _fake_python(tmp_path)
    unmanaged = roots["runtime_root"] / "bin" / "in-toto-verify"
    unmanaged.parent.mkdir(parents=True)
    unmanaged.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    unmanaged.chmod(0o755)

    payload = cli.artifacts_trust_tools_python(
        apply=True,
        python_executable=str(fake_python),
        write_latest=False,
    )

    assert payload["ok"] is False
    assert payload["failures"][0]["result"]["error"] == "target_exists_without_force"
    assert os.path.islink(unmanaged) is False
