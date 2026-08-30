from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abyss_machine import code_intelligence_gate as subject


def _provider_config() -> dict:
    return {
        "$schema": "schemas/live-code-intelligence-provider.schema.json",
        "schema_version": "abyss-stack-live-code-intelligence-provider-v1",
        "provider": {
            "id": "python-ast-bootstrap",
            "version": "1.1.0",
            "language": "python",
            "mode": "bootstrap",
            "observation_schema": "abyss-stack-code-observation-v1",
            "boundary_schema": "abyss-stack-live-code-intelligence-provider-boundary-v1",
            "executable": "python3",
            "entrypoint": "mechanics/runtime-lifecycle/parts/live-code-intelligence/live_code_intelligence.py",
            "protocol": "json-command-v1",
            "operations": ["discover", "refresh", "status", "definitions", "references"],
        },
        "source": {
            "include_suffixes": [".py"],
            "exclude_dirs": [".git", ".hg", ".venv", "__pycache__", "node_modules"],
            "max_file_bytes": 1_000_000,
        },
        "state": {
            "relative_root": "Knowledge/code-intelligence/live/python",
            "promotion": "complete-observation-only",
            "fallback": "current-then-last-good",
        },
        "machine_binding": {
            "schema_version": "abyss-machine-code-intelligence-provider-binding-v1",
            "owner": "abyss-machine",
            "installation_identity": "source-local-provider-candidate",
            "artifact_subject": {
                "kind": "source-local-provider",
                "source_ref": "mechanics/runtime-lifecycle/parts/live-code-intelligence/live_code_intelligence.py",
                "trust_state": "not-admitted",
                "admission_state": "unknown",
            },
            "resource_envelope": {"max_file_bytes": 1_000_000, "max_query_results": 100},
            "live_measurement": {"required_for_admission": True, "state": "unobserved"},
        },
        "owner_boundaries": {
            "runtime_lifecycle": "abyss-stack",
            "observation_meaning": "aoa-kag",
            "installation_and_admission": "abyss-machine",
            "proof_and_verdict": "aoa-evals",
        },
    }


def _signing_identity(root: Path) -> tuple[Path, Path, Ed25519PrivateKey]:
    private_key = Ed25519PrivateKey.generate()
    key_path = root / "issuer.pem"
    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    anchor_path = root / "anchor.json"
    anchor_path.write_text(
        json.dumps(
            {
                "schema_version": "abyss-machine-code-intelligence-gate-public-key-v1",
                "owner": "abyss-machine",
                "key_id": "key:test",
                "algorithm": "ed25519",
                "public_key": base64.b64encode(public_key).decode("ascii"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    anchor_path.chmod(0o644)
    return key_path, anchor_path, private_key


def test_issue_runtime_gate_binds_live_probe_and_exact_signed_bytes(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    node_root = runtime / "providers" / "node-providers"
    bin_root = node_root / "node_modules" / ".bin"
    bin_root.mkdir(parents=True)
    executable = bin_root / "typescript-language-server"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    (node_root / "installation.json").write_text(
        json.dumps(
            {
                "subject_digest": "sha256:" + "a" * 64,
                "source_ref": "commit:" + "b" * 40,
                "versions": {"lsp": "6.0.0"},
                "bin_root": str(bin_root),
            }
        ),
        encoding="utf-8",
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "sample.py").write_text("def sample():\n    return 1\n", encoding="utf-8")
    (source_root / "sample.ts").write_text("export const sample = 1;\n", encoding="utf-8")
    provider_source = tmp_path / "live_code_intelligence.py"
    provider_source.write_text("# provider source\n", encoding="utf-8")
    provider_config = tmp_path / "provider.json"
    provider_config.write_text(json.dumps(_provider_config()), encoding="utf-8")
    key_path, anchor_path, private_key = _signing_identity(tmp_path)
    output = tmp_path / "gate.json"
    monkeypatch.setattr(
        subject,
        "trust_gate",
        lambda *args, **kwargs: {
            "ok": True,
            "verdict": "allow",
            "record_id": "sha256:" + "c" * 64,
        },
    )
    probes: list[list[str]] = []

    def fake_probe(command, root):
        probes.append(list(command))
        assert root == source_root
        return {"returncode": 0, "message_count": 2}

    monkeypatch.setattr(subject, "_probe_lsp", fake_probe)
    result = subject.issue_runtime_gate(
        registry_dir=tmp_path / "registry",
        runtime_root=runtime,
        source_root=source_root,
        stack_provider_source=provider_source,
        stack_provider_config=provider_config,
        private_key_path=key_path,
        trust_anchor_path=anchor_path,
        output_path=output,
        require_root_owned_identity=False,
    )

    assert result["status"] == "issued"
    assert len(probes) == 2
    bundle = json.loads(output.read_text(encoding="utf-8"))
    assert bundle["bundle_digest"] == subject.bundle_digest(bundle)
    assert bundle["gate"]["gate_digest"] == subject.gate_digest(bundle["gate"])
    assert bundle["evidence"]["receipt_digest"] == subject.evidence_digest(bundle["evidence"])
    assert bundle["evidence"]["lsp_sessions"][0]["source_root"] == str(source_root)
    assert bundle["evidence"]["lifecycle"]["restart"]["state"] == "observed"
    private_key.public_key().verify(
        base64.b64decode(bundle["gate"]["signature"]),
        subject._canonical_json(bundle["gate"]["signed_payload"]),
    )


def test_live_issuer_rejects_non_root_signing_identity(tmp_path: Path) -> None:
    key_path, anchor_path, _ = _signing_identity(tmp_path)
    try:
        subject._load_signing_identity(
            key_path,
            anchor_path,
            require_root_owned=True,
        )
    except ValueError as exc:
        assert "root-owned" in str(exc)
    else:  # pragma: no cover - the test process is intentionally unprivileged
        assert key_path.stat().st_uid == 0
