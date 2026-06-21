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
    registered = artifact_bundles.write_bundle_registry_record(
        bundle_dir,
        registry_dir,
        lifecycle_state="manually-verified",
        consumer_refs=["validator:artifact_bundle_roundtrip"],
        evidence_refs=["validator:manual-positive-synthetic"],
    )
    latest = artifact_bundles.read_bundle_registry(registry_dir, artifact_class=artifact_class)
    latest_record = latest.get("latest_by_artifact_class", {}).get(artifact_class)
    revoked = artifact_bundles.write_bundle_registry_record(
        bundle_dir,
        registry_dir,
        lifecycle_state="revoked",
        revocation_reason="validator terminal-state negative",
    )
    after_revoke = artifact_bundles.read_bundle_registry(registry_dir, artifact_class=artifact_class)
    return {
        "ok": bool(
            registered.get("ok")
            and isinstance(latest_record, dict)
            and latest_record.get("record_id") == registered.get("record", {}).get("record_id")
            and revoked.get("ok")
            and not after_revoke.get("latest_by_artifact_class")
        ),
        "registered": registered,
        "latest": latest,
        "revoked": revoked,
        "after_revoke": after_revoke,
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
