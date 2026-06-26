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
    monkeypatch.setattr(cli, "ARTIFACTS_TRUST_TOOLS_PROOF_ROOT", state_root / "trust-tools" / "proofs")
    monkeypatch.setattr(cli, "ARTIFACTS_TRUST_TOOLS_PROOF_LATEST_PATH", state_root / "trust-tools" / "proofs" / "latest.json")
    monkeypatch.setattr(cli, "ARTIFACTS_INDEX_PATH", state_root / "index.json")
    monkeypatch.setattr(cli, "ABYSS_MACHINE_TMP_ROOT", tmp_path / "tmp")
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


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _fake_proof_runtime(roots: dict[str, Path], *, negative_in_toto_fails: bool = True) -> None:
    runtime_root = roots["runtime_root"]
    bin_dir = runtime_root / "bin"
    venv_bin = runtime_root / "python" / "bin"
    _write_executable(
        venv_bin / "python",
        "#!/bin/sh\n"
        "set -eu\n"
        "if [ \"${1:-}\" = \"-c\" ]; then\n"
        "  root=\"$3\"\n"
        "  mkdir -p \"$root/links\" \"$root/work\"\n"
        "  printf '%s\\n' '{\"fixture\":\"positive\"}' > \"$root/root.layout\"\n"
        "  printf '%s\\n' '{\"fixture\":\"negative\"}' > \"$root/root-negative.layout\"\n"
        "  printf '%s\\n' 'PUBLIC KEY' > \"$root/functionary.pub\"\n"
        "  printf '%s\\n' '{\"link\":\"package\"}' > \"$root/links/package.fake.link\"\n"
        "  printf '%s\\n' '{\"ok\":true,\"returncode\":0,\"root_layout\":\"'\"$root\"'/root.layout\",\"negative_layout\":\"'\"$root\"'/root-negative.layout\",\"public_key\":\"'\"$root\"'/functionary.pub\",\"link_dir\":\"'\"$root\"'/links\",\"link_files\":[\"'\"$root\"'/links/package.fake.link\"],\"work_dir\":\"'\"$root\"'/work\",\"keyid\":\"fake-keyid\"}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
    )
    _write_executable(
        venv_bin / "in-toto-run",
        "#!/bin/sh\n"
        "printf '%s\\n' 'fake in-toto-run should only be called by fake builder'\n",
    )
    _write_executable(
        bin_dir / "in-toto-verify",
        "#!/bin/sh\n"
        "set -eu\n"
        "if [ \"${1:-}\" = \"--version\" ]; then\n"
        "  printf '%s\\n' 'in-toto-verify 3.1.0'\n"
        "  exit 0\n"
        "fi\n"
        "layout=''\n"
        "prev=''\n"
        "for arg in \"$@\"; do\n"
        "  if [ \"$prev\" = '--layout' ]; then layout=\"$arg\"; fi\n"
        "  prev=\"$arg\"\n"
        "done\n"
        + (
            "case \"$layout\" in *negative*) printf '%s\\n' 'RuleVerificationError: expected negative fixture' >&2; exit 1 ;; esac\n"
            if negative_in_toto_fails
            else "case \"$layout\" in *negative*) printf '%s\\n' 'unexpected pass' >&2; exit 0 ;; esac\n"
        )
        + "exit 0\n",
    )
    _write_executable(
        bin_dir / "cyclonedx-py",
        "#!/bin/sh\n"
        "set -eu\n"
        "if [ \"${1:-}\" = \"--version\" ]; then\n"
        "  printf '%s\\n' '7.3.0'\n"
        "  exit 0\n"
        "fi\n"
        "req=''\n"
        "out=''\n"
        "prev=''\n"
        "for arg in \"$@\"; do\n"
        "  if [ \"$prev\" = 'requirements' ]; then req=\"$arg\"; fi\n"
        "  if [ \"$prev\" = '-o' ]; then out=\"$arg\"; fi\n"
        "  prev=\"$arg\"\n"
        "done\n"
        "if grep -qx 'idna' \"$req\"; then\n"
        "  printf '%s\\n' '{\"bomFormat\":\"CycloneDX\",\"specVersion\":\"1.6\",\"components\":[{\"type\":\"library\",\"name\":\"idna\"}]}' > \"$out\"\n"
        "else\n"
        "  printf '%s\\n' '{\"bomFormat\":\"CycloneDX\",\"specVersion\":\"1.6\",\"components\":[{\"type\":\"library\",\"name\":\"idna\",\"version\":\"3.7\",\"purl\":\"pkg:pypi/idna@3.7\"}]}' > \"$out\"\n"
        "fi\n",
    )


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


def test_artifact_trust_tools_proof_runs_positive_and_negative_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _patch_artifact_trust_roots(monkeypatch, tmp_path)
    _fake_proof_runtime(roots)

    payload = cli.artifact_trust_tools_proof(write_latest=True)

    assert payload["ok"] is True
    assert payload["summary"]["positive_checks"] >= 4
    assert payload["summary"]["negative_checks"] == 2
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["in_toto_verify_positive"]["ok"] is True
    assert checks["in_toto_verify_negative_product_rule"]["ok"] is True
    assert checks["cyclonedx_py_positive_python_package_sbom"]["ok"] is True
    assert checks["cyclonedx_py_negative_unfrozen_inventory_semantics"]["ok"] is True
    assert len(payload["artifacts"]["cyclonedx_py_positive_sbom_sha256"]) == 64
    assert (roots["state_root"] / "trust-tools" / "proofs" / "latest.json").is_file()


def test_artifact_trust_tools_proof_fails_if_negative_in_toto_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _patch_artifact_trust_roots(monkeypatch, tmp_path)
    _fake_proof_runtime(roots, negative_in_toto_fails=False)

    payload = cli.artifact_trust_tools_proof(write_latest=False)

    checks = {item["id"]: item for item in payload["checks"]}
    assert payload["ok"] is False
    assert checks["in_toto_verify_negative_product_rule"]["ok"] is False


def test_cyclonedx_python_sbom_semantic_check_rejects_empty_inventory() -> None:
    check = cli.artifact_trust_cyclonedx_python_sbom_check(
        {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": None},
        expected_name="idna",
        expected_version="3.7",
    )

    assert check["ok"] is False
    assert "sbom must include at least one component" in check["errors"]
