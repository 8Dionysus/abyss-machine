from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "artifact-production-evidence.yml"
PYPROJECT = ROOT / "pyproject.toml"


def test_artifact_production_evidence_workflow_is_public_safe() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "if: ${{ inputs.artifact == 'bootstrap_install_bundle' }}" in text
    assert "if: ${{ inputs.artifact == 'code_intelligence_provider' }}" in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "id-token: write" in text
    assert "attestations: write" in text
    assert "contents: read" in text
    assert "sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6" in text
    assert "cosign-release: v3.1.1" in text
    assert "--backend cosign-github-oidc" in text
    assert (
        '--certificate-oidc-issuer "https://token.actions.githubusercontent.com"'
        in text
    )
    assert '--certificate-github-workflow-sha "${GITHUB_SHA}"' in text
    assert "abyss-machine-bootstrap-evidence-${GITHUB_SHA}.tar.gz" in text
    assert "actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "python scripts/ci_gate.py --mode release-artifact" in text
    assert "tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner" in text
    assert "generated \\" in text
    assert "manifests \\" in text
    assert "subject-path: dist/abyss-machine-bootstrap-${{ github.sha }}.tar.gz" in text
    assert "scripts/build_code_intelligence_adjacent_providers.py" in text
    assert "scripts/build_code_intelligence_node_providers.py" in text
    assert "scripts/build_code_intelligence_provider.py" in text
    assert "b8eb0da4121372b5d74a90fc36cba6a31f147f3c" in text
    assert "manifests/artifact_bundles/code_intelligence_provider.bundle.json" in text
    assert '--source-ref "commit:${GITHUB_SHA}"' in text
    assert "abyss-machine-code-intelligence-evidence-${GITHUB_SHA}.tar.gz" in text
    assert "subject-path: dist/code-intelligence/*.tar.gz" in text
    assert (ROOT / "generated" / "contract_abi_signatures.min.json").is_file()
    assert (ROOT / "manifests" / "artifact_signature_policy.manifest.json").is_file()

    forbidden_host_roots = (
        "/etc/abyss-machine",
        "/usr/local",
        "/var/lib/abyss-machine",
        "/srv/abyss-machine",
        "/srv/AbyssOS",
    )
    for root in forbidden_host_roots:
        assert root not in text


def test_cryptography_is_runtime_dependency_for_installed_artifact_tools() -> None:
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]

    assert any(item.startswith("cryptography>=") for item in dependencies)


def _python_producer_step() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text.split("      - name: Build deterministic SCIP Python archive\n", 1)[1]
    step = step.split("\n      - name:", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


def test_python_producer_toolchain_matches_owner_lock() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    lock = json.loads(
        (ROOT / "manifests/code_intelligence_python_provider.lock.json").read_text()
    )
    step = _python_producer_step()
    assert "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38" in text
    assert f'node-version: "{lock["build"]["node_version"]}"' in text
    assert "package-manager-cache: false" in text
    assert f'test "$(node --version)" = "v{lock["build"]["node_version"]}"' in step
    assert f'test "$(npm --version)" = "{lock["build"]["npm_version"]}"' in step


@pytest.mark.parametrize(
    "fault", ["none", "node-version", "npm-version", "nonreproducible"]
)
def test_python_production_step_fails_closed_before_signing(
    tmp_path: Path, fault: str
) -> None:
    """Execute the actual workflow shell with synthetic tools, never an indexer."""
    workspace, runner, bin_dir = (
        tmp_path / name for name in ("workspace", "runner", "bin")
    )
    for path in (workspace, runner, bin_dir):
        path.mkdir()
    calls = tmp_path / "calls.jsonl"
    shim = f"#!{sys.executable}\n" + textwrap.dedent("""\
        import json, os, sys
        from pathlib import Path
        name = Path(sys.argv[0]).name
        args = sys.argv[1:]
        with open(os.environ["TEST_CALLS"], "a") as output:
            output.write(json.dumps([name, *args]) + "\\n")
        fault = os.environ["TEST_FAULT"]
        if name == "node":
            assert args == ["--version"], "provider execution forbidden"
            print("v0.0.0" if fault == "node-version" else "v22.23.1")
        elif name == "npm":
            if args == ["--version"]:
                print("0.0.0" if fault == "npm-version" else "10.9.8")
            else:
                assert args[0] == "ci"
                assert {"--ignore-scripts", "--no-audit", "--no-fund"} <= set(args)
        elif name == "python":
            assert args[:2] == ["scripts/code_intelligence_python_provider.py", "build"]
            output = Path(args[args.index("--output") + 1])
            payload = b"synthetic archive, not provider proof"
            if fault == "nonreproducible" and output.name == "repeat.tar.gz":
                payload += b" drift"
            output.write_bytes(payload)
        else:
            raise AssertionError(name)
        """)
    for name in ("node", "npm", "python"):
        path = bin_dir / name
        path.write_text(shim)
        path.chmod(0o755)
    commit = "a" * 40
    result = subprocess.run(
        ["bash", "-c", _python_producer_step()],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "GITHUB_WORKSPACE": str(workspace),
            "GITHUB_SHA": commit,
            "RUNNER_TEMP": str(runner),
            "TEST_CALLS": str(calls),
            "TEST_FAULT": fault,
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    invoked = [json.loads(line) for line in calls.read_text().splitlines()]
    if fault.endswith("version"):
        assert result.returncode != 0
        assert all(row[1:] == ["--version"] for row in invoked)
        assert not (workspace / "dist").exists()
        return
    ci = next(row for row in invoked if row[:2] == ["npm", "ci"])
    for option in ("--userconfig", "--globalconfig"):
        assert ci[ci.index(option) + 1] == "/dev/null"
    assert ci[ci.index("--cache") + 1] == str(runner / "npm-cache")
    prefix = Path(ci[ci.index("--prefix") + 1])
    inputs = ROOT / "mechanics/code-intelligence/parts/scip-python"
    for name in ("package.json", "package-lock.json"):
        assert (prefix / name).read_bytes() == (inputs / name).read_bytes()
    builds = [row for row in invoked if row[0] == "python"]
    assert len(builds) == 2
    assert all(
        row[row.index("--source-ref") + 1] == f"commit:{commit}" for row in builds
    )
    assert all(row[row.index("--runtime") + 1] == str(prefix) for row in builds)
    artifact_root = workspace / "dist/code-intelligence"
    archives = list(artifact_root.glob("*.tar.gz"))
    assert len(archives) == 1  # Repeat is outside the signed aggregate.
    checksum = Path(str(archives[0]) + ".sha256")
    if fault == "nonreproducible":
        assert result.returncode != 0
        assert not checksum.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (
            checksum.read_text().split()[0]
            == hashlib.sha256(archives[0].read_bytes()).hexdigest()
        )
