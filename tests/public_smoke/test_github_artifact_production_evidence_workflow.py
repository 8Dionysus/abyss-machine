from __future__ import annotations

from pathlib import Path
import tomllib


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
    assert "--certificate-oidc-issuer \"https://token.actions.githubusercontent.com\"" in text
    assert "--certificate-github-workflow-sha \"${GITHUB_SHA}\"" in text
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
    assert "--source-ref \"commit:${GITHUB_SHA}\"" in text
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
