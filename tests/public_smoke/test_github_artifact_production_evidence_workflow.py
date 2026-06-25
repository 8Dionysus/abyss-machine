from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "artifact-production-evidence.yml"


def test_artifact_production_evidence_workflow_is_public_safe() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "if: ${{ inputs.artifact == 'bootstrap_install_bundle' }}" in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "id-token: write" in text
    assert "attestations: write" in text
    assert "contents: read" in text
    assert "actions/attest@59d89421af93a897026c735860bf21b6eb4f7b26" in text
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in text
    assert "python scripts/ci_gate.py --mode release-artifact" in text
    assert "tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner" in text
    assert "subject-path: dist/abyss-machine-bootstrap-${{ github.sha }}.tar.gz" in text

    forbidden_host_roots = (
        "/etc/abyss-machine",
        "/usr/local",
        "/var/lib/abyss-machine",
        "/srv/abyss-machine",
        "/srv/AbyssOS",
    )
    for root in forbidden_host_roots:
        assert root not in text
