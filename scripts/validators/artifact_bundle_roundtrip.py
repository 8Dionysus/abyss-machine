#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import artifact_bundles  # noqa: E402


def run_bundle(bundle_dir: Path, *, manifest_ref: str, artifact_class: str) -> dict:
    build = artifact_bundles.build_sidecars(bundle_dir, manifest_ref=manifest_ref)
    sign = artifact_bundles.sign_bundle(bundle_dir)
    verify = artifact_bundles.verify_bundle(bundle_dir)
    release = artifact_bundles.release_check(bundle_dir, enforcement="blocking")
    return {
        "ok": bool(build.get("ok") and sign.get("ok") and verify.get("ok") and release.get("ok")),
        "artifact_class": artifact_class,
        "bundle_dir": str(bundle_dir),
        "steps": {
            "build_sidecars": build,
            "sign": sign,
            "verify": verify,
            "release_check": release,
        },
    }


def run_registry_roundtrip(bundle_dir: Path, registry_dir: Path, *, artifact_class: str) -> dict:
    registered = artifact_bundles.promote_bundle_evidence(
        bundle_dir,
        registry_dir,
        lifecycle_state="manually-verified",
        consumer_refs=["validator:artifact_bundle_roundtrip"],
        evidence_refs=["validator:manual-positive-synthetic"],
        trust_root_mode="host_managed",
    )
    latest = artifact_bundles.read_bundle_registry(registry_dir, artifact_class=artifact_class)
    latest_record = latest.get("latest_by_artifact_class", {}).get(artifact_class)
    allow_gate = artifact_bundles.trust_gate(
        registry_dir,
        artifact_class=artifact_class,
        subject_digest=str(registered.get("record", {}).get("subject_digest") or ""),
        consumer_intent="agent",
        expected_trust_root_mode="host_managed",
    )
    requirements = artifact_bundles.artifact_requirements(
        artifact_class,
        registry_dir=registry_dir,
    )
    affected = artifact_bundles.artifact_affected(
        ["src/abyss_machine/artifact_bundles.py"],
        artifact_class=artifact_class,
        registry_dir=registry_dir,
    )
    affected_row = affected.get("rows", [{}])[0] if affected.get("rows") else {}
    revoked = artifact_bundles.promote_bundle_evidence(
        bundle_dir,
        registry_dir,
        lifecycle_state="revoked",
        revocation_reason="validator terminal-state negative",
        trust_root_mode="host_managed",
    )
    deny_gate = artifact_bundles.trust_gate(
        registry_dir,
        artifact_class=artifact_class,
        record_id=str(registered.get("record", {}).get("record_id") or ""),
        consumer_intent="agent",
    )
    after_revoke = artifact_bundles.read_bundle_registry(registry_dir, artifact_class=artifact_class)
    legacy_registry_dir = registry_dir.parent / f"{registry_dir.name}-legacy"
    legacy_registered = artifact_bundles.promote_bundle_evidence(
        bundle_dir,
        legacy_registry_dir,
        lifecycle_state="manually-verified",
        trust_root_mode="host_managed",
    )
    legacy_record_id = str(legacy_registered.get("record", {}).get("record_id") or "")
    legacy_record_path = (
        legacy_registry_dir
        / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
        / f"{legacy_record_id.removeprefix('sha256:')}.json"
    )
    legacy_record = json.loads(legacy_record_path.read_text(encoding="utf-8"))
    for field in artifact_bundles.DURABLE_EVIDENCE_FIELDS:
        legacy_record.pop(field, None)
    legacy_record_path.write_text(
        json.dumps(legacy_record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    legacy_denied = artifact_bundles.trust_gate(legacy_registry_dir, artifact_class=artifact_class, consumer_intent="agent")
    legacy_dry_run = artifact_bundles.upgrade_legacy_bundle_registry(legacy_registry_dir, dry_run=True)
    legacy_upgrade = artifact_bundles.upgrade_legacy_bundle_registry(legacy_registry_dir, trust_root_mode="host_managed")
    legacy_allow = artifact_bundles.trust_gate(
        legacy_registry_dir,
        artifact_class=artifact_class,
        consumer_intent="agent",
        expected_trust_root_mode="host_managed",
    )
    allow_claims = allow_gate.get("inspected_claims", {})
    deny_claims = deny_gate.get("inspected_claims", {})
    return {
        "ok": bool(
            registered.get("ok")
            and isinstance(latest_record, dict)
            and latest_record.get("record_id") == registered.get("record", {}).get("record_id")
            and allow_gate.get("verdict") == "allow"
            and allow_gate.get("decision", {}).get("model") == "fail_closed_consumer_admission"
            and allow_claims.get("registry_latest", {}).get("selected_record_is_latest") is True
            and allow_claims.get("controls", {}).get("required_controls_missing") == []
            and requirements.get("ok")
            and requirements.get("rows", [{}])[0].get("source_route", {}).get("contract_surface_status") == "local_contract_surface"
            and affected_row.get("verdict") == "needs_rebuild"
            and affected_row.get("freshness") == "stale"
            and revoked.get("ok")
            and deny_gate.get("verdict") == "deny"
            and deny_gate.get("decision", {}).get("allow") is False
            and deny_claims.get("lifecycle", {}).get("terminal_state") is True
            and not after_revoke.get("latest_by_artifact_class")
            and legacy_denied.get("verdict") == "deny"
            and legacy_dry_run.get("summary", {}).get("upgraded") == 1
            and legacy_dry_run.get("written") == []
            and legacy_upgrade.get("ok")
            and legacy_allow.get("verdict") == "allow"
        ),
        "registered": registered,
        "latest": latest,
        "allow_gate": allow_gate,
        "requirements": requirements,
        "affected": affected,
        "revoked": revoked,
        "deny_gate": deny_gate,
        "after_revoke": after_revoke,
        "legacy_upgrade": {
            "denied": legacy_denied,
            "dry_run": legacy_dry_run,
            "applied": legacy_upgrade,
            "allow": legacy_allow,
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="abyss-machine-artifact-bundle-") as tmp:
        public_seed = run_bundle(
            Path(tmp) / "public-source-seed",
            manifest_ref=artifact_bundles.DEFAULT_BUNDLE_MANIFEST_REF,
            artifact_class="public_source_seed",
        )
        host_local = run_bundle(
            Path(tmp) / "host-local-evidence",
            manifest_ref="manifests/artifact_bundles/host_local_evidence.sample.bundle.json",
            artifact_class="host_local_evidence",
        )
        public_seed_registry = run_registry_roundtrip(
            Path(tmp) / "public-source-seed",
            Path(tmp) / "registry",
            artifact_class="public_source_seed",
        )
        payload = {
            "ok": bool(public_seed.get("ok") and host_local.get("ok") and public_seed_registry.get("ok")),
            "schema": "abyss_machine_artifact_bundle_roundtrip_v1",
            "bundle_layout": artifact_bundles.BUNDLE_LAYOUT,
            "bundles": {
                "public_source_seed": public_seed,
                "host_local_evidence": host_local,
            },
            "registry_roundtrip": {
                "public_source_seed": public_seed_registry,
            },
        }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if payload["ok"]:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
