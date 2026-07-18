from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import artifact_bundles, kag_artifacts


def _write_fake_cosign(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path


def option_value(args, name):
    index = args.index(name)
    return args[index + 1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


args = sys.argv[1:]
if args[0] == "sign-blob":
    bundle = Path(option_value(args, "--bundle"))
    subject = args[-1]
    sha = digest(subject)
    bundle.write_text(json.dumps({"schema": "fake_sigstore_bundle_v1", "sha256": sha}) + "\\n", encoding="utf-8")
    print("fake-signature:" + sha)
    raise SystemExit(0)
if args[0] == "verify-blob":
    bundle = json.loads(Path(option_value(args, "--bundle")).read_text(encoding="utf-8"))
    raise SystemExit(0 if bundle.get("sha256") == digest(args[-1]) else 1)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _owner_release(owner: str, digest_char: str) -> dict[str, object]:
    digest = "sha256:" + digest_char * 64
    return {
        "schema_version": "aoa-kag-owner-family-release-v1",
        "repo": {"name": owner, "git_ref": f"commit:{digest_char * 40}"},
        "release_identity": {
            "artifact_class": "kag_owner_family_release",
            "abi_epoch": "aoa-kag-owner-family-release-v1",
            "artifact_kind": "kag_owner_family_release",
            "content_digest": digest,
            "corpus_digest": "sha256:" + "c" * 64,
            "distribution_digest": "sha256:" + "d" * 64,
        },
        "source": {
            "owner": owner,
            "ref": f"commit:{digest_char * 40}",
            "snapshot": "sha256:" + "e" * 64,
        },
        "objects": [],
        "packs": [],
        "signature": {
            "algorithm": "none",
            "subject_digest": digest,
            "signature_ref": "",
            "verification_state": "unsigned-candidate",
        },
    }


def _os_composition() -> dict[str, object]:
    owners = []
    owner_names = [f"owner-{index:02d}" for index in range(24)]
    for index, owner in enumerate(owner_names, start=1):
        owners.append(
            {
                "owner": owner,
                "source_ref": "commit:" + f"{index:040x}",
                "corpus_digest": "sha256:" + f"{index:064x}",
                "release_digest": "sha256:" + f"{index + 24:064x}",
                "distribution_digest": "sha256:" + f"{index + 48:064x}",
                "verification_state": "verified",
            }
        )
    membership_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            sorted(owner_names),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "aoa-kag-os-composition-v1",
        "composition_identity": {
            "artifact_class": "kag_os_composition",
            "abi_epoch": "aoa-kag-os-composition-v1",
            "content_digest": "sha256:" + "c" * 64,
            "schema_epoch": "repo-local-kag-corpus-v1",
            "canonicalization_epoch": "portable-record-normalization-v3",
        },
        "federation": {
            "owner_count": 24,
            "membership_digest": membership_digest,
        },
        "owners": owners,
        "aggregate": {
            "git_hot_bytes": 1,
            "corpus_total_bytes": 24,
            "artifact_unique_bytes": 24,
        },
        "unresolved_references": {},
        "provenance": {
            "builder_owner": "aoa-kag",
            "trust_owner": "abyss-machine",
            "source_scan": "owner-release-manifests-only",
        },
        "signature": {
            "algorithm": "none",
            "key_id": "",
            "subject_digest": "sha256:" + "c" * 64,
            "signature_ref": "",
            "verification_state": "unsigned-candidate",
        },
    }


def test_kag_identity_subject_rejects_conflicting_exact_source_ref() -> None:
    release = _owner_release("owner-a", "a")
    release["source"]["ref"] = "commit:" + ("b" * 40)  # type: ignore[index]

    with pytest.raises(ValueError, match="source refs do not match"):
        kag_artifacts.kag_identity_signature_subject(release)


def _build_signed_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    owner: str,
    digest_char: str,
) -> tuple[Path, Path, dict[str, object]]:
    fake_cosign = tmp_path / "cosign"
    if not fake_cosign.exists():
        _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))

    family = tmp_path / owner
    family.mkdir()
    release_path = family / kag_artifacts.OWNER_RELEASE_FILENAME
    release_path.write_text(
        json.dumps(_owner_release(owner, digest_char), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (family / "bundle.manifest.json").write_text("{}\n", encoding="utf-8")
    object_path = (
        family
        / "objects"
        / "sha256"
        / (digest_char * 2)
        / (digest_char * 64)
    )
    object_path.parent.mkdir(parents=True)
    object_path.write_text(f"object:{owner}\n", encoding="utf-8")

    signed_identity = kag_artifacts.sign_kag_identity(release_path)
    assert signed_identity["ok"] is True

    bundle = tmp_path / f"{owner}-trust-bundle"
    build = artifact_bundles.build_sidecars(
        bundle,
        manifest_ref="manifests/artifact_bundles/kag_owner_family_release.bundle.json",
        subject_root=family,
        owner_repo=owner,
        source_ref=f"commit:{digest_char * 40}",
        access_policy="public-kag",
    )
    signed_bundle = artifact_bundles.sign_bundle(bundle, backend="cosign-local-key")
    verified_bundle = artifact_bundles.verify_bundle(bundle, subject_root=family)
    assert build["ok"] is True
    assert signed_bundle["ok"] is True
    assert verified_bundle["ok"] is True
    signature_decision = json.loads(
        (bundle / artifact_bundles.SIGNATURE_DECISION_SIDECAR).read_text(
            encoding="utf-8"
        )
    )
    assert signature_decision["subject_ref"] == artifact_bundles.ABI_SIDECAR
    return family, bundle, signed_identity


def test_shared_kag_manifest_requires_runtime_owner_source_and_root(
    tmp_path: Path,
) -> None:
    manifest = (
        "manifests/artifact_bundles/"
        "kag_owner_family_release.bundle.json"
    )
    with pytest.raises(
        ValueError,
        match="subject_root, owner_repo, source_ref",
    ):
        artifact_bundles.build_sidecars(
            tmp_path / "missing-runtime-overrides",
            manifest_ref=manifest,
        )


def test_unsigned_inner_kag_identity_cannot_enter_outer_bundle(
    tmp_path: Path,
) -> None:
    owner = "owner-a"
    family = tmp_path / owner
    family.mkdir()
    (family / kag_artifacts.OWNER_RELEASE_FILENAME).write_text(
        json.dumps(_owner_release(owner, "a"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="KAG external identity admission failed",
    ):
        artifact_bundles.build_sidecars(
            tmp_path / "unsigned-outer-bundle",
            manifest_ref=(
                "manifests/artifact_bundles/"
                "kag_owner_family_release.bundle.json"
            ),
            subject_root=family,
            owner_repo=owner,
            source_ref="commit:" + "a" * 40,
            access_policy="public-kag",
        )


def test_kag_promotion_rejects_source_overrides_not_bound_by_outer_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, bundle, _signed_identity = _build_signed_family(
        tmp_path,
        monkeypatch,
        owner="owner-a",
        digest_char="a",
    )
    registry = tmp_path / "registry"

    wrong_owner = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="owner-b",
        source_ref="commit:" + "a" * 40,
        trust_root_mode="host_managed",
        subject_root=family,
    )
    assert wrong_owner["ok"] is False
    assert (
        "KAG promotion source_repo does not match the signed bundle identity"
        in wrong_owner["errors"]
    )
    assert wrong_owner["written"] == []

    wrong_ref = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="owner-a",
        source_ref="commit:" + "b" * 40,
        trust_root_mode="host_managed",
        subject_root=family,
    )
    assert wrong_ref["ok"] is False
    assert (
        "KAG promotion source_ref does not match the signed bundle identity"
        in wrong_ref["errors"]
    )
    assert wrong_ref["written"] == []


def test_kag_outer_identity_source_ref_tamper_fails_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, bundle, _signed_identity = _build_signed_family(
        tmp_path,
        monkeypatch,
        owner="owner-a",
        digest_char="a",
    )
    identity_path = bundle / artifact_bundles.IDENTITY_SIDECAR
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["source_ref"] = "commit:" + "b" * 40
    identity_path.write_text(
        json.dumps(identity, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    verification = artifact_bundles.verify_bundle(
        bundle,
        subject_root=family,
        write=False,
    )
    assert verification["ok"] is False
    assert (
        "artifact.abi.json KAG external_subject source_ref does not match "
        "artifact.identity.json"
        in verification["errors"]
    )


def test_signed_os_composition_roundtrip_binds_owner_membership_and_builder_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_cosign = tmp_path / "cosign"
    _write_fake_cosign(fake_cosign)
    key = tmp_path / "local-test.key"
    public_key = tmp_path / "local-test.pub"
    key.write_text("fake-private-key\n", encoding="utf-8")
    public_key.write_text("fake-public-key\n", encoding="utf-8")
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_BINARY", str(fake_cosign))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_KEY", str(key))
    monkeypatch.setenv("ABYSS_MACHINE_COSIGN_PUB", str(public_key))

    composition_root = tmp_path / "composition"
    composition_root.mkdir()
    composition_path = composition_root / kag_artifacts.OS_COMPOSITION_FILENAME
    composition_path.write_text(
        json.dumps(_os_composition(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    inner_signature = kag_artifacts.sign_kag_identity(composition_path)
    assert inner_signature["ok"] is True

    source_ref = "commit:" + "f" * 40
    bundle = tmp_path / "composition-bundle"
    build = artifact_bundles.build_sidecars(
        bundle,
        manifest_ref=(
            "manifests/artifact_bundles/"
            "kag_os_composition.bundle.json"
        ),
        subject_root=composition_root,
        owner_repo="aoa-kag",
        source_ref=source_ref,
        access_policy="public-kag",
    )
    outer_signature = artifact_bundles.sign_bundle(
        bundle,
        backend="cosign-local-key",
    )
    verification = artifact_bundles.verify_bundle(
        bundle,
        subject_root=composition_root,
    )
    assert build["ok"] is True
    assert outer_signature["ok"] is True
    assert verification["ok"] is True
    claims = verification["control_evidence"]["kag_identity_signature"][
        "claims"
    ]
    assert claims["owner"] == "aoa-kag"
    assert claims["owner_count"] == 24

    registry = tmp_path / "composition-registry"
    promoted = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="release-ready",
        source_repo="aoa-kag",
        source_ref=source_ref,
        producer="aoa-kag-federation-builder",
        trust_root_mode="host_managed",
        subject_root=composition_root,
    )
    assert promoted["ok"] is True
    assert promoted["record"]["source_repo"] == "aoa-kag"
    assert promoted["record"]["source_ref"] == source_ref


def test_owner_family_runtime_root_signature_admission_and_owner_scoped_latest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "registry"
    store = tmp_path / "subject-store"
    rows = []
    for owner, digest_char in (("owner-a", "a"), ("owner-b", "b")):
        family, bundle, _signed_identity = _build_signed_family(
            tmp_path,
            monkeypatch,
            owner=owner,
            digest_char=digest_char,
        )
        source_ref = f"commit:{digest_char * 40}"
        promoted = artifact_bundles.promote_bundle_evidence(
            bundle,
            registry,
            lifecycle_state="release-ready",
            source_repo=owner,
            source_ref=source_ref,
            producer="pytest-kag-owner-builder",
            trust_root_mode="host_managed",
            subject_root=family,
        )
        assert promoted["ok"] is True
        materialized = artifact_bundles.materialize_artifact_subjects(
            bundle,
            store_root=store,
            registry_dir=registry,
            manifest_ref="manifests/artifact_bundles/kag_owner_family_release.bundle.json",
            subject_root=family,
            consumer_intent="agent",
            expected_source_repo=owner,
            expected_source_ref=source_ref,
            expected_access_policy="public-kag",
            expected_trust_root_mode="host_managed",
        )
        assert materialized["ok"] is True
        rows.append((owner, source_ref, promoted["record"]["subject_digest"]))

    registry_view = artifact_bundles.read_bundle_registry(
        registry,
        artifact_class="kag_owner_family_release",
    )
    scoped = registry_view["latest_by_artifact_class_and_source_repo"][
        "kag_owner_family_release"
    ]
    assert set(scoped) == {"owner-a", "owner-b"}

    for owner, source_ref, subject_digest in rows:
        gate = artifact_bundles.trust_gate(
            registry,
            artifact_class="kag_owner_family_release",
            subject_digest=subject_digest,
            consumer_intent="agent",
            expected_source_repo=owner,
            expected_source_ref=source_ref,
            expected_access_policy="public-kag",
            expected_trust_root_mode="host_managed",
        )
        assert gate["ok"] is True
        assert gate["verdict"] == "allow"
        assert gate["inspected_claims"]["registry_latest"]["selected_record_is_latest"] is True

    wrong_source = artifact_bundles.trust_gate(
        registry,
        artifact_class="kag_owner_family_release",
        subject_digest=rows[0][2],
        consumer_intent="agent",
        expected_source_repo="owner-a",
        expected_source_ref="commit:" + "f" * 40,
        expected_access_policy="restricted-kag",
    )
    assert wrong_source["ok"] is False
    assert "source_ref_mismatch" in wrong_source["blockers"]
    assert "access_policy_mismatch" in wrong_source["blockers"]

    revoked = artifact_bundles.promote_bundle_evidence(
        bundle,
        registry,
        lifecycle_state="revoked",
        source_repo=rows[-1][0],
        source_ref=rows[-1][1],
        revocation_reason="pytest KAG revocation",
        producer="pytest-kag-owner-builder",
        trust_root_mode="host_managed",
        subject_root=family,
    )
    assert revoked["ok"] is True
    revoked_gate = artifact_bundles.trust_gate(
        registry,
        artifact_class="kag_owner_family_release",
        subject_digest=rows[-1][2],
        consumer_intent="agent",
        expected_source_repo=rows[-1][0],
        expected_source_ref=rows[-1][1],
        expected_access_policy="public-kag",
        expected_trust_root_mode="host_managed",
    )
    assert revoked_gate["ok"] is False
    assert "terminal_lifecycle_state:revoked" in revoked_gate["blockers"]


def test_kag_identity_signature_rejects_tampered_subject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, _bundle, _signed_identity = _build_signed_family(
        tmp_path,
        monkeypatch,
        owner="owner-a",
        digest_char="a",
    )
    subject = family / "trust" / kag_artifacts.IDENTITY_SUBJECT_FILENAME
    subject.write_text("{}\n", encoding="utf-8")
    verification = kag_artifacts.verify_kag_identity_signature(
        family / kag_artifacts.OWNER_RELEASE_FILENAME,
        write_receipt=False,
    )
    assert verification["ok"] is False
    assert "KAG identity signature subject does not match payload identity" in verification["errors"]
    assert "cosign verify-blob rejected the KAG identity signature" in verification["errors"]


def _registry_record(
    *,
    record_id: str,
    artifact_class: str,
    source_repo: str,
    lifecycle_state: str,
    store: Path,
    identity_digest: str,
) -> dict[str, object]:
    return {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": record_id,
        "artifact_class": artifact_class,
        "lifecycle_state": lifecycle_state,
        "latest_eligible": lifecycle_state in {"release-ready", "published"},
        "terminal_state": False,
        "verification_ok": True,
        "source_repo": source_repo,
        "source_ref": "commit:" + hashlib.sha1(source_repo.encode()).hexdigest(),
        "artifact_subject_store": {"required": True, "ok": True, "path": str(store)},
        "external_artifact_identity": {
            "artifact_class": artifact_class,
            "content_digest": identity_digest,
        },
        "created_at": f"2026-07-18T00:00:{record_id[-2:]}Z",
    }


def test_reachability_retention_preserves_composition_releases_and_receipts_gc(
    tmp_path: Path,
) -> None:
    cas = tmp_path / "cas"
    reachable_path = cas / "objects" / "sha256" / "aa" / ("a" * 64)
    unreachable_path = cas / "objects" / "sha256" / "bb" / ("b" * 64)
    reachable_path.parent.mkdir(parents=True)
    unreachable_path.parent.mkdir(parents=True)
    reachable_path.write_text("reachable\n", encoding="utf-8")
    unreachable_path.write_text("unreachable\n", encoding="utf-8")

    registry = tmp_path / "registry"
    records_dir = registry / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR
    records_dir.mkdir(parents=True)
    owner_entries = []
    for index in range(24):
        owner = f"owner-{index:02d}"
        release_digest = "sha256:" + f"{index:064x}"
        store = tmp_path / "stores" / owner
        store.mkdir(parents=True)
        release = _owner_release(owner, "a")
        release["release_identity"]["content_digest"] = release_digest  # type: ignore[index]
        release["objects"] = [  # type: ignore[index]
            {"object_key": "objects/sha256/aa/" + "a" * 64}
        ]
        (store / kag_artifacts.OWNER_RELEASE_FILENAME).write_text(
            json.dumps(release, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        record_id = f"owner-record-{index:02d}"
        record = _registry_record(
            record_id=record_id,
            artifact_class="kag_owner_family_release",
            source_repo=owner,
            lifecycle_state="published",
            store=store,
            identity_digest=release_digest,
        )
        (records_dir / f"{record_id}.json").write_text(
            json.dumps(record, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        owner_entries.append(
            {"owner": owner, "release_digest": release_digest}
        )

    composition_store = tmp_path / "stores" / "composition"
    composition_store.mkdir(parents=True)
    composition_digest = "sha256:" + "c" * 64
    composition = {
        "schema_version": "aoa-kag-os-composition-v1",
        "composition_identity": {
            "artifact_class": "kag_os_composition",
            "abi_epoch": "aoa-kag-os-composition-v1",
            "content_digest": composition_digest,
        },
        "owners": owner_entries,
    }
    (composition_store / kag_artifacts.OS_COMPOSITION_FILENAME).write_text(
        json.dumps(composition, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    composition_record = _registry_record(
        record_id="composition-record-00",
        artifact_class="kag_os_composition",
        source_repo="aoa-kag",
        lifecycle_state="published",
        store=composition_store,
        identity_digest=composition_digest,
    )
    (records_dir / "composition-record-00.json").write_text(
        json.dumps(composition_record, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    plan_path = tmp_path / "retention-plan.json"
    plan = kag_artifacts.write_kag_retention_plan(cas, registry, plan_path)
    assert plan["deletion_allowed"] is True
    assert plan["summary"]["retained_releases"] == 24
    assert [row["path"] for row in plan["candidates"]] == [
        "objects/sha256/bb/" + "b" * 64
    ]

    refused_receipt = tmp_path / "refused-receipt.json"
    refused = kag_artifacts.apply_kag_retention_plan(
        plan_path,
        refused_receipt,
        confirm=False,
    )
    assert refused["ok"] is False
    assert unreachable_path.is_file()
    assert refused_receipt.is_file()

    first_release_path = (
        tmp_path
        / "stores"
        / "owner-00"
        / kag_artifacts.OWNER_RELEASE_FILENAME
    )
    first_release = json.loads(first_release_path.read_text(encoding="utf-8"))
    original_objects = list(first_release["objects"])
    first_release["objects"].append(
        {"object_key": "objects/sha256/bb/" + "b" * 64}
    )
    first_release_path.write_text(
        json.dumps(first_release, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    race_receipt_path = tmp_path / "race-receipt.json"
    race_refused = kag_artifacts.apply_kag_retention_plan(
        plan_path,
        race_receipt_path,
        confirm=True,
    )
    assert race_refused["ok"] is False
    assert unreachable_path.is_file()
    assert race_refused["reachability_recheck"]["performed"] is True
    assert (
        "retention candidate is now reachable or no longer eligible:"
        "objects/sha256/bb/" + "b" * 64
        in race_refused["errors"]
    )

    first_release["objects"] = original_objects
    first_release_path.write_text(
        json.dumps(first_release, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt_path = tmp_path / "retention-receipt.json"
    applied = kag_artifacts.apply_kag_retention_plan(
        plan_path,
        receipt_path,
        confirm=True,
    )
    assert applied["ok"] is True
    assert applied["summary"]["deleted_files"] == 1
    assert reachable_path.is_file()
    assert not unreachable_path.exists()
    assert receipt_path.is_file()
