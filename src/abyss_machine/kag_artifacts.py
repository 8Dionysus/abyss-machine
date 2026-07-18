from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from . import artifact_bundles


OWNER_RELEASE_ARTIFACT_CLASS = "kag_owner_family_release"
OWNER_RELEASE_ABI_EPOCH = "aoa-kag-owner-family-release-v1"
OS_COMPOSITION_ARTIFACT_CLASS = "kag_os_composition"
OS_COMPOSITION_ABI_EPOCH = "aoa-kag-os-composition-v1"
OWNER_RELEASE_FILENAME = "owner-family-release.json"
OS_COMPOSITION_FILENAME = "os-kag-composition.json"
TRUST_DIRNAME = "trust"
IDENTITY_SUBJECT_FILENAME = "kag-identity.subject.json"
SIGSTORE_BUNDLE_FILENAME = "kag-identity.sigstore.json"
SIGNATURE_FILENAME = "kag-identity.cosign.signature"
PUBLIC_KEY_FILENAME = "kag-identity.cosign.pub"
VERIFY_RECEIPT_FILENAME = "kag-identity.verify.json"
RETENTION_PLAN_SCHEMA = "abyss_machine_kag_retention_plan_v1"
RETENTION_RECEIPT_SCHEMA = "abyss_machine_kag_retention_receipt_v1"
ZERO_DIGEST = "sha256:" + ("0" * 64)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_uri(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _is_sha256_uri(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest)


def _require_sha256_uri(value: object, *, field: str) -> str:
    if not _is_sha256_uri(value):
        raise ValueError(f"{field} must be a lowercase sha256 URI")
    return str(value)


def _is_exact_git_commit_ref(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("commit:"):
        return False
    commit = value.removeprefix("commit:")
    return (
        len(commit) in {40, 64}
        and all(ch in "0123456789abcdef" for ch in commit)
    )


def _file_digest(path: Path) -> str:
    return _sha256_uri(path.read_bytes())


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _identity_descriptor(payload: Mapping[str, Any]) -> tuple[str, str, str, Mapping[str, Any]]:
    if payload.get("schema_version") == OWNER_RELEASE_ABI_EPOCH:
        identity = payload.get("release_identity")
        expected_class = OWNER_RELEASE_ARTIFACT_CLASS
        expected_epoch = OWNER_RELEASE_ABI_EPOCH
    elif payload.get("schema_version") == OS_COMPOSITION_ABI_EPOCH:
        identity = payload.get("composition_identity")
        expected_class = OS_COMPOSITION_ARTIFACT_CLASS
        expected_epoch = OS_COMPOSITION_ABI_EPOCH
    else:
        raise ValueError("unsupported KAG identity payload schema")
    if not isinstance(identity, Mapping):
        raise ValueError("KAG identity payload is missing its identity object")
    artifact_class = str(identity.get("artifact_class") or "")
    abi_epoch = str(identity.get("abi_epoch") or "")
    digest = str(identity.get("content_digest") or "")
    if artifact_class != expected_class:
        raise ValueError(f"KAG artifact_class mismatch: {artifact_class} != {expected_class}")
    if abi_epoch != expected_epoch:
        raise ValueError(f"KAG abi_epoch mismatch: {abi_epoch} != {expected_epoch}")
    _require_sha256_uri(digest, field="KAG identity content_digest")
    return artifact_class, abi_epoch, digest, identity


def kag_identity_signature_subject(payload: Mapping[str, Any]) -> dict[str, Any]:
    artifact_class, abi_epoch, identity_digest, identity = _identity_descriptor(payload)
    subject: dict[str, Any] = {
        "schema": "abyss_machine_kag_identity_signature_subject_v1",
        "artifact_class": artifact_class,
        "abi_epoch": abi_epoch,
        "identity_digest": identity_digest,
    }
    if artifact_class == OWNER_RELEASE_ARTIFACT_CLASS:
        repo = payload.get("repo") if isinstance(payload.get("repo"), Mapping) else {}
        source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
        repo_owner = str(repo.get("name") or "")
        source_owner = str(source.get("owner") or "")
        if not repo_owner or not source_owner:
            raise ValueError(
                "KAG owner release must define matching repo and source owners"
            )
        if repo_owner != source_owner:
            raise ValueError("KAG owner release repo and source owner do not match")
        repo_source_ref = str(repo.get("git_ref") or "")
        release_source_ref = str(source.get("ref") or "")
        if not repo_source_ref or not release_source_ref:
            raise ValueError(
                "KAG owner release must define matching repo and source refs"
            )
        if release_source_ref != repo_source_ref:
            raise ValueError("KAG owner release repo and source refs do not match")
        if not _is_exact_git_commit_ref(release_source_ref):
            raise ValueError(
                "KAG owner release source_ref must be an exact "
                "commit:<40-or-64-lowercase-hex> ref"
            )
        source_snapshot = _require_sha256_uri(
            source.get("snapshot"),
            field="KAG owner release source snapshot",
        )
        corpus_digest = _require_sha256_uri(
            identity.get("corpus_digest"),
            field="KAG owner release corpus digest",
        )
        distribution_digest = _require_sha256_uri(
            identity.get("distribution_digest"),
            field="KAG owner release distribution digest",
        )
        subject.update(
            {
                "owner": repo_owner,
                "source_ref": release_source_ref,
                "source_snapshot": source_snapshot,
                "corpus_digest": corpus_digest,
                "distribution_digest": distribution_digest,
            }
        )
    else:
        federation = payload.get("federation") if isinstance(payload.get("federation"), Mapping) else {}
        provenance = payload.get("provenance") if isinstance(payload.get("provenance"), Mapping) else {}
        owners = payload.get("owners") if isinstance(payload.get("owners"), list) else []
        owner_names = [
            str(item.get("owner") or "")
            for item in owners
            if isinstance(item, Mapping)
        ]
        if (
            int(federation.get("owner_count") or 0) != 24
            or len(owners) != 24
            or len(owner_names) != 24
            or any(not owner for owner in owner_names)
            or len(set(owner_names)) != 24
        ):
            raise ValueError(
                "KAG OS composition signature requires 24 unique owners"
            )
        for item in owners:
            if not isinstance(item, Mapping):
                raise ValueError("KAG OS composition owner entry must be an object")
            owner = str(item.get("owner") or "")
            if not _is_exact_git_commit_ref(item.get("source_ref")):
                raise ValueError(
                    f"KAG OS composition owner {owner} requires an exact source_ref"
                )
            for field in (
                "corpus_digest",
                "release_digest",
                "distribution_digest",
            ):
                _require_sha256_uri(
                    item.get(field),
                    field=f"KAG OS composition owner {owner} {field}",
                )
            if item.get("verification_state") != "verified":
                raise ValueError(
                    f"KAG OS composition owner {owner} is not verified"
                )
        membership_digest = _require_sha256_uri(
            federation.get("membership_digest"),
            field="KAG OS composition membership digest",
        )
        expected_membership_digest = _sha256_uri(
            _canonical_bytes(sorted(owner_names))
        )
        if membership_digest != expected_membership_digest:
            raise ValueError(
                "KAG OS composition membership digest does not match owners"
            )
        if provenance.get("builder_owner") != "aoa-kag":
            raise ValueError(
                "KAG OS composition provenance builder_owner must be aoa-kag"
            )
        subject.update(
            {
                "owner": "aoa-kag",
                "owner_count": 24,
                "membership_digest": membership_digest,
            }
        )
    return subject


def _trust_paths(payload_path: Path) -> dict[str, Path]:
    trust_root = payload_path.parent / TRUST_DIRNAME
    return {
        "root": trust_root,
        "subject": trust_root / IDENTITY_SUBJECT_FILENAME,
        "sigstore": trust_root / SIGSTORE_BUNDLE_FILENAME,
        "signature": trust_root / SIGNATURE_FILENAME,
        "public_key": trust_root / PUBLIC_KEY_FILENAME,
        "verification": trust_root / VERIFY_RECEIPT_FILENAME,
    }


def verify_kag_identity_signature(
    payload_path: str | Path,
    *,
    write_receipt: bool = True,
) -> dict[str, Any]:
    path = Path(payload_path).resolve()
    errors: list[str] = []
    try:
        payload = _load_json(path)
        artifact_class, abi_epoch, identity_digest, _identity = _identity_descriptor(payload)
        expected_subject = kag_identity_signature_subject(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "schema": "abyss_machine_kag_identity_signature_verify_v1",
            "payload": path.name,
            "errors": [str(exc)],
        }
    paths = _trust_paths(path)
    signature = payload.get("signature") if isinstance(payload.get("signature"), Mapping) else {}
    if str(signature.get("algorithm") or "") != "ecdsa-p256-sha256":
        errors.append("KAG identity signature algorithm must be ecdsa-p256-sha256")
    if str(signature.get("subject_digest") or "") != identity_digest:
        errors.append("KAG identity signature targets the wrong identity digest")
    if str(signature.get("signature_ref") or "") != f"{TRUST_DIRNAME}/{SIGSTORE_BUNDLE_FILENAME}":
        errors.append("KAG identity signature_ref does not name the Sigstore bundle")
    for label in ("subject", "sigstore", "signature", "public_key"):
        if not paths[label].is_file():
            errors.append(f"KAG identity signature file is missing: {paths[label].name}")
    if paths["subject"].is_file():
        expected_bytes = _canonical_bytes(expected_subject) + b"\n"
        if paths["subject"].read_bytes() != expected_bytes:
            errors.append("KAG identity signature subject does not match payload identity")
    key_id = _file_digest(paths["public_key"]) if paths["public_key"].is_file() else ""
    if artifact_class == OS_COMPOSITION_ARTIFACT_CLASS and str(signature.get("key_id") or "") != key_id:
        errors.append("KAG OS composition key_id does not match the signing public key")
    cosign = artifact_bundles._cosign_binary()
    if not cosign:
        errors.append("cosign binary is unavailable")
    elif all(paths[label].is_file() for label in ("subject", "sigstore", "public_key")):
        proc = subprocess.run(
            [
                cosign,
                "verify-blob",
                "--key",
                str(paths["public_key"]),
                "--bundle",
                str(paths["sigstore"]),
                str(paths["subject"]),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        if proc.returncode != 0:
            errors.append("cosign verify-blob rejected the KAG identity signature")
    if signature.get("verification_state") == "revoked":
        errors.append("KAG identity signature state is revoked")
    receipt = {
        "ok": not errors,
        "schema": "abyss_machine_kag_identity_signature_verify_v1",
        "artifact_class": artifact_class,
        "abi_epoch": abi_epoch,
        "identity_digest": identity_digest,
        "payload": path.name,
        "subject_ref": f"{TRUST_DIRNAME}/{IDENTITY_SUBJECT_FILENAME}",
        "signature_ref": f"{TRUST_DIRNAME}/{SIGSTORE_BUNDLE_FILENAME}",
        "public_key_digest": key_id or None,
        "verification_state": signature.get("verification_state"),
        "errors": errors,
    }
    if write_receipt:
        _write_json(paths["verification"], receipt)
    return receipt


def sign_kag_identity(
    payload_path: str | Path,
    *,
    backend: str = "cosign-local-key",
) -> dict[str, Any]:
    path = Path(payload_path).resolve()
    payload = _load_json(path)
    artifact_class, _abi_epoch, identity_digest, _identity = _identity_descriptor(payload)
    if backend != "cosign-local-key":
        return {
            "ok": False,
            "schema": "abyss_machine_kag_identity_sign_v1",
            "artifact_class": artifact_class,
            "errors": ["KAG identity signing requires backend=cosign-local-key"],
        }
    cosign = artifact_bundles._cosign_binary()
    key_path = Path(os.environ.get("ABYSS_MACHINE_COSIGN_KEY") or "")
    public_key_path = Path(os.environ.get("ABYSS_MACHINE_COSIGN_PUB") or "")
    missing = []
    if not cosign:
        missing.append("cosign binary")
    if not key_path.is_file():
        missing.append("ABYSS_MACHINE_COSIGN_KEY file")
    if not public_key_path.is_file():
        missing.append("ABYSS_MACHINE_COSIGN_PUB file")
    if missing:
        return {
            "ok": False,
            "schema": "abyss_machine_kag_identity_sign_v1",
            "artifact_class": artifact_class,
            "identity_digest": identity_digest,
            "errors": ["missing signing input: " + ", ".join(missing)],
        }
    paths = _trust_paths(path)
    paths["root"].mkdir(parents=True, exist_ok=True)
    subject = kag_identity_signature_subject(payload)
    paths["subject"].write_bytes(_canonical_bytes(subject) + b"\n")
    proc = subprocess.run(
        [
            cosign,
            "sign-blob",
            "--yes",
            "--key",
            str(key_path),
            "--bundle",
            str(paths["sigstore"]),
            str(paths["subject"]),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if proc.returncode != 0 or not paths["sigstore"].is_file():
        return {
            "ok": False,
            "schema": "abyss_machine_kag_identity_sign_v1",
            "artifact_class": artifact_class,
            "identity_digest": identity_digest,
            "errors": ["cosign sign-blob failed for KAG identity"],
        }
    paths["signature"].write_text(proc.stdout.strip() + "\n", encoding="utf-8")
    shutil.copyfile(public_key_path, paths["public_key"])
    signature: dict[str, Any] = {
        "algorithm": "ecdsa-p256-sha256",
        "subject_digest": identity_digest,
        "signature_ref": f"{TRUST_DIRNAME}/{SIGSTORE_BUNDLE_FILENAME}",
        "verification_state": "verified",
    }
    if artifact_class == OS_COMPOSITION_ARTIFACT_CLASS:
        signature["key_id"] = _file_digest(paths["public_key"])
    payload["signature"] = signature
    _write_json(path, payload)
    verification = verify_kag_identity_signature(path, write_receipt=True)
    if not verification.get("ok"):
        payload["signature"]["verification_state"] = "invalid"
        _write_json(path, payload)
    return {
        "ok": bool(verification.get("ok")),
        "schema": "abyss_machine_kag_identity_sign_v1",
        "artifact_class": artifact_class,
        "identity_digest": identity_digest,
        "payload": path.name,
        "written": [
            path.name,
            f"{TRUST_DIRNAME}/{IDENTITY_SUBJECT_FILENAME}",
            f"{TRUST_DIRNAME}/{SIGSTORE_BUNDLE_FILENAME}",
            f"{TRUST_DIRNAME}/{SIGNATURE_FILENAME}",
            f"{TRUST_DIRNAME}/{PUBLIC_KEY_FILENAME}",
            f"{TRUST_DIRNAME}/{VERIFY_RECEIPT_FILENAME}",
        ],
        "verification": verification,
        "errors": verification.get("errors", []),
    }


def _external_identity(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("external_artifact_identity")
    return value if isinstance(value, Mapping) else {}


def _record_release_digest(record: Mapping[str, Any]) -> str:
    return str(_external_identity(record).get("content_digest") or "")


def _subject_store_path(record: Mapping[str, Any]) -> Path | None:
    status = record.get("artifact_subject_store")
    if not isinstance(status, Mapping) or status.get("ok") is not True:
        return None
    value = str(status.get("path") or "")
    return Path(value).resolve() if value else None


def _retention_plan_digest(payload: Mapping[str, Any]) -> str:
    candidate = json.loads(json.dumps(payload, ensure_ascii=False))
    identity = candidate.get("plan_identity")
    if not isinstance(identity, dict):
        raise ValueError("retention plan identity is missing")
    identity["content_digest"] = ZERO_DIGEST
    return _sha256_uri(_canonical_bytes(candidate))


def build_kag_retention_plan(
    cas_root: str | Path,
    registry_dir: str | Path,
    *,
    pinned_record_ids: list[str] | None = None,
) -> dict[str, Any]:
    cas = Path(cas_root).resolve()
    registry = artifact_bundles.read_bundle_registry(registry_dir)
    records = [row for row in registry.get("records", []) if isinstance(row, dict)]
    pins = {str(item) for item in pinned_record_ids or [] if str(item)}
    blockers: list[str] = []
    retained_record_ids: set[str] = set(pins)
    latest_scoped = registry.get("latest_by_artifact_class_and_source_repo", {})
    owner_latest = latest_scoped.get(OWNER_RELEASE_ARTIFACT_CLASS, {}) if isinstance(latest_scoped, dict) else {}
    if isinstance(owner_latest, dict):
        retained_record_ids.update(
            str(row.get("record_id") or "")
            for row in owner_latest.values()
            if isinstance(row, dict)
        )
    for record in records:
        if (
            record.get("artifact_class") == OWNER_RELEASE_ARTIFACT_CLASS
            and record.get("lifecycle_state") == "published"
            and record.get("terminal_state") is not True
        ):
            retained_record_ids.add(str(record.get("record_id") or ""))

    composition_latest = registry.get("latest_by_artifact_class", {}).get(OS_COMPOSITION_ARTIFACT_CLASS)
    composition_records = [
        record
        for record in records
        if record.get("artifact_class") == OS_COMPOSITION_ARTIFACT_CLASS
        and (
            record.get("lifecycle_state") == "published"
            or str(record.get("record_id") or "") in pins
            or (
                isinstance(composition_latest, dict)
                and record.get("record_id") == composition_latest.get("record_id")
            )
        )
    ]
    if not composition_records:
        blockers.append("no_retained_kag_os_composition")
    referenced_release_digests: set[str] = set()
    retained_compositions: list[dict[str, Any]] = []
    for record in composition_records:
        store = _subject_store_path(record)
        if store is None:
            blockers.append(f"composition_subject_store_missing:{record.get('record_id')}")
            continue
        path = store / OS_COMPOSITION_FILENAME
        if not path.is_file():
            blockers.append(f"composition_payload_missing:{record.get('record_id')}")
            continue
        composition = _load_json(path)
        owners = composition.get("owners") if isinstance(composition.get("owners"), list) else []
        if len(owners) != 24:
            blockers.append(f"composition_owner_count_not_24:{record.get('record_id')}")
        for owner in owners:
            if isinstance(owner, Mapping) and owner.get("release_digest"):
                referenced_release_digests.add(str(owner["release_digest"]))
        retained_compositions.append(
            {
                "record_id": record.get("record_id"),
                "composition_digest": _record_release_digest(record),
                "owners": len(owners),
                "store": str(store),
            }
        )

    owner_records_by_digest: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("artifact_class") != OWNER_RELEASE_ARTIFACT_CLASS:
            continue
        digest = _record_release_digest(record)
        if digest:
            owner_records_by_digest.setdefault(digest, []).append(record)
    for digest in sorted(referenced_release_digests):
        candidates = owner_records_by_digest.get(digest, [])
        if not candidates:
            blockers.append(f"composition_release_record_missing:{digest}")
            continue
        retained_record_ids.add(str(candidates[-1].get("record_id") or ""))

    reachable: set[str] = set()
    retained_releases: list[dict[str, Any]] = []
    for record in records:
        record_id = str(record.get("record_id") or "")
        if record.get("artifact_class") != OWNER_RELEASE_ARTIFACT_CLASS or record_id not in retained_record_ids:
            continue
        store = _subject_store_path(record)
        if store is None:
            blockers.append(f"owner_release_subject_store_missing:{record_id}")
            continue
        release_path = store / OWNER_RELEASE_FILENAME
        if not release_path.is_file():
            blockers.append(f"owner_release_payload_missing:{record_id}")
            continue
        release = _load_json(release_path)
        for item in release.get("objects", []) if isinstance(release.get("objects"), list) else []:
            if isinstance(item, Mapping) and item.get("object_key"):
                reachable.add(str(item["object_key"]))
        for item in release.get("packs", []) if isinstance(release.get("packs"), list) else []:
            if isinstance(item, Mapping) and item.get("object_key"):
                reachable.add(str(item["object_key"]))
        retained_releases.append(
            {
                "record_id": record_id,
                "owner": record.get("source_repo"),
                "release_digest": _record_release_digest(record),
                "lifecycle_state": record.get("lifecycle_state"),
                "pinned": record_id in pins,
                "store": str(store),
            }
        )
    if not retained_releases:
        blockers.append("no_retained_kag_owner_releases")

    candidates: list[dict[str, Any]] = []
    all_cas_files = 0
    all_cas_bytes = 0
    for prefix in (Path("objects/sha256"), Path("packs/sha256")):
        root = cas / prefix
        if not root.is_dir():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(cas).as_posix()
            size = path.stat().st_size
            all_cas_files += 1
            all_cas_bytes += size
            if relative in reachable:
                continue
            candidates.append(
                {
                    "path": relative,
                    "bytes": size,
                    "digest": _file_digest(path),
                }
            )
    plan: dict[str, Any] = {
        "schema": RETENTION_PLAN_SCHEMA,
        "plan_identity": {
            "content_digest": ZERO_DIGEST,
            "cas_root_digest": _sha256_uri(str(cas).encode("utf-8")),
        },
        "created_at": _utc_now(),
        "cas_root": str(cas),
        "registry_dir": str(Path(registry_dir).resolve()),
        "pins": sorted(pins),
        "retained_compositions": retained_compositions,
        "retained_releases": retained_releases,
        "reachable_keys": sorted(reachable),
        "candidates": candidates,
        "summary": {
            "cas_files": all_cas_files,
            "cas_bytes": all_cas_bytes,
            "reachable_keys": len(reachable),
            "candidate_files": len(candidates),
            "candidate_bytes": sum(int(item["bytes"]) for item in candidates),
            "retained_releases": len(retained_releases),
            "retained_compositions": len(retained_compositions),
        },
        "blockers": sorted(set(blockers)),
        "deletion_allowed": not blockers,
        "claim_limit": "Only unreachable CAS objects are candidates. Published, source-scoped latest, composition-referenced, and explicitly pinned releases remain reachable through verified subject-store copies.",
    }
    plan["plan_identity"]["content_digest"] = _retention_plan_digest(plan)
    return plan


def write_kag_retention_plan(
    cas_root: str | Path,
    registry_dir: str | Path,
    output_path: str | Path,
    *,
    pinned_record_ids: list[str] | None = None,
) -> dict[str, Any]:
    plan = build_kag_retention_plan(
        cas_root,
        registry_dir,
        pinned_record_ids=pinned_record_ids,
    )
    _write_json(Path(output_path).resolve(), plan)
    return plan


def apply_kag_retention_plan(
    plan_path: str | Path,
    receipt_path: str | Path,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    path = Path(plan_path).resolve()
    plan = _load_json(path)
    errors: list[str] = []
    if plan.get("schema") != RETENTION_PLAN_SCHEMA:
        errors.append("retention plan schema mismatch")
    identity = plan.get("plan_identity") if isinstance(plan.get("plan_identity"), Mapping) else {}
    if str(identity.get("content_digest") or "") != _retention_plan_digest(plan):
        errors.append("retention plan digest mismatch")
    if plan.get("blockers"):
        errors.append("retention plan has blockers")
    if not confirm:
        errors.append("retention apply requires explicit confirmation")
    cas = Path(str(plan.get("cas_root") or "")).resolve()
    reachability_recheck: dict[str, Any] = {
        "performed": False,
        "registry_dir": str(plan.get("registry_dir") or ""),
        "planned_candidates": len(
            plan.get("candidates", [])
            if isinstance(plan.get("candidates"), list)
            else []
        ),
    }
    if not errors:
        try:
            current_plan = build_kag_retention_plan(
                cas,
                str(plan.get("registry_dir") or ""),
                pinned_record_ids=[
                    str(item)
                    for item in plan.get("pins", [])
                    if str(item)
                ]
                if isinstance(plan.get("pins"), list)
                else [],
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"retention reachability recheck failed:{exc}")
        else:
            reachability_recheck = {
                "performed": True,
                "registry_dir": str(plan.get("registry_dir") or ""),
                "planned_candidates": len(
                    plan.get("candidates", [])
                    if isinstance(plan.get("candidates"), list)
                    else []
                ),
                "current_candidates": len(
                    current_plan.get("candidates", [])
                    if isinstance(current_plan.get("candidates"), list)
                    else []
                ),
                "current_reachable_keys": current_plan.get(
                    "summary",
                    {},
                ).get("reachable_keys"),
                "current_blockers": current_plan.get("blockers", []),
            }
            if current_plan.get("blockers"):
                errors.append("current retention reachability plan has blockers")
            current_candidates = {
                str(item.get("path") or ""): item
                for item in current_plan.get("candidates", [])
                if isinstance(item, dict) and str(item.get("path") or "")
            }
            for item in (
                plan.get("candidates", [])
                if isinstance(plan.get("candidates"), list)
                else []
            ):
                if not isinstance(item, dict):
                    continue
                candidate_path = str(item.get("path") or "")
                current = current_candidates.get(candidate_path)
                if current is None:
                    errors.append(
                        "retention candidate is now reachable or no longer "
                        f"eligible:{candidate_path}"
                    )
                    continue
                if (
                    int(current.get("bytes") or -1)
                    != int(item.get("bytes") or -1)
                    or str(current.get("digest") or "")
                    != str(item.get("digest") or "")
                ):
                    errors.append(
                        f"retention candidate changed during reachability recheck:{candidate_path}"
                    )
    preflight: list[tuple[Path, dict[str, Any]]] = []
    for item in plan.get("candidates", []) if isinstance(plan.get("candidates"), list) else []:
        if not isinstance(item, dict):
            continue
        relative = Path(str(item.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"unsafe retention candidate path:{relative}")
            continue
        target = (cas / relative).resolve()
        try:
            target.relative_to(cas)
        except ValueError:
            errors.append(f"retention candidate escapes CAS root:{relative}")
            continue
        if not target.is_file():
            errors.append(f"retention candidate missing:{relative.as_posix()}")
            continue
        if target.stat().st_size != int(item.get("bytes") or -1):
            errors.append(f"retention candidate size drift:{relative.as_posix()}")
            continue
        if _file_digest(target) != str(item.get("digest") or ""):
            errors.append(f"retention candidate digest drift:{relative.as_posix()}")
            continue
        preflight.append((target, item))
    deleted: list[dict[str, Any]] = []
    if not errors:
        for target, item in preflight:
            target.unlink()
            deleted.append(dict(item))
    receipt = {
        "ok": not errors,
        "schema": RETENTION_RECEIPT_SCHEMA,
        "applied_at": _utc_now(),
        "plan_ref": path.name,
        "plan_digest": identity.get("content_digest"),
        "cas_root": str(cas),
        "reachability_recheck": reachability_recheck,
        "deleted": deleted,
        "summary": {
            "deleted_files": len(deleted),
            "deleted_bytes": sum(int(item.get("bytes") or 0) for item in deleted),
        },
        "errors": errors,
    }
    _write_json(Path(receipt_path).resolve(), receipt)
    return receipt
