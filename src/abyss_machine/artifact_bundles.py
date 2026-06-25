from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import tomllib
import uuid
from pathlib import Path
from typing import Any


POLICY_REF = "manifests/artifact_signature_policy.manifest.json"
POLICY_REF_REPO_QUALIFIED = f"repo:abyss-machine/{POLICY_REF}"
POLICY_REF_ALIASES = frozenset({POLICY_REF, POLICY_REF_REPO_QUALIFIED})
ABI_REF = "generated/contract_abi_signatures.min.json"
BUNDLE_LAYOUT = "abyss_machine_artifact_bundle_v1"
IDENTITY_SIDECAR = "artifact.identity.json"
ABI_SIDECAR = "artifact.abi.json"
PROVENANCE_SIDECAR = "artifact.provenance.json"
LOCAL_PROVENANCE_SIDECAR = "artifact.local-provenance.json"
SIGNATURE_DECISION_SIDECAR = "artifact.signature-decision.json"
VERIFY_SIDECAR = "artifact.verify.json"
SUBJECTS_SIDECAR = "artifact.subjects.json"
SBOM_CYCLONEDX_SIDECAR = "artifact.sbom.cdx.json"
SBOM_SPDX_SIDECAR = "artifact.sbom.spdx.json"
SLSA_INTOTO_SIDECAR = "artifact.provenance.intoto.jsonl"
COSIGN_SIGNATURE_SIDECAR = "artifact.cosign.signature"
COSIGN_PUBLIC_KEY_SIDECAR = "artifact.cosign.pub"
SIGSTORE_BUNDLE_SIDECAR = "artifact.sigstore.json"
MLBOM_CYCLONEDX_SIDECAR = "artifact.mlbom.cdx.json"
C2PA_MANIFEST_SIDECAR = "artifact.c2pa"
C2PA_REPORT_SIDECAR = "artifact.c2pa.json"
TUF_UPDATE_METADATA_SIDECAR = "artifact.update.tuf.json"
DEFAULT_BUNDLE_MANIFEST_REF = "manifests/artifact_bundles/public_source_seed.bundle.json"
CONTROL_FILES = {
    "abi_signature": [ABI_SIDECAR],
    "local_provenance": [LOCAL_PROVENANCE_SIDECAR],
    "sbom": [SBOM_CYCLONEDX_SIDECAR, SBOM_SPDX_SIDECAR],
    "ml_bom": [MLBOM_CYCLONEDX_SIDECAR],
    "slsa_in_toto": [SLSA_INTOTO_SIDECAR],
    "sigstore_cosign": [SIGSTORE_BUNDLE_SIDECAR, COSIGN_SIGNATURE_SIDECAR, COSIGN_PUBLIC_KEY_SIDECAR],
    "c2pa": [C2PA_MANIFEST_SIDECAR, C2PA_REPORT_SIDECAR],
}
ML_BOM_CATEGORIES = ("models", "datasets", "conversions", "framework_configs")
RELEASE_ENFORCEMENT_LEVELS = {"warn", "required-for-release", "blocking", "consumer-blocking"}
BUNDLE_LIFECYCLE_STATES = (
    "candidate",
    "built-local",
    "manually-verified",
    "release-ready",
    "published",
    "superseded",
    "deprecated",
    "revoked",
    "quarantined",
)
BUNDLE_LATEST_ELIGIBLE_STATES = frozenset({"manually-verified", "release-ready", "published"})
BUNDLE_TERMINAL_STATES = frozenset({"superseded", "deprecated", "revoked", "quarantined"})
BUNDLE_LATEST_STATE_RANK = {"manually-verified": 10, "release-ready": 20, "published": 30}
TRUST_ROOT_MODES = (
    "local_dev",
    "host_managed",
    "github_oidc",
    "oci_registry",
    "public_release",
)
TRUST_GATE_VERDICTS = ("allow", "deny", "warn", "unknown", "manual_review_required")
PRODUCTION_CONSUMER_INTENTS = frozenset({"installer", "runtime", "release_consumer", "update_client", "public_release"})
PUBLIC_PRIVACY_BOUNDARY_PREFIXES = (
    "public",
    "public-safe",
    "public-derived",
    "publishable",
    "package contains code only",
)
PRIVATE_PRIVACY_BOUNDARY_MARKERS = (
    "private host evidence",
    "not public",
    "must not publish",
    "must not be published",
    "not release-signed",
)
ARTIFACT_AFFECTED_VERDICTS = (
    "fresh",
    "stale",
    "needs_rebuild",
    "needs_reverify",
    "blocked_by_missing_sibling",
    "accepted_lag",
    "manual_review_required",
)
UPDATE_LANE_VERDICTS = ("allow", "deny", "manual_review_required")
DURABLE_EVIDENCE_FIELDS = ("source_repo", "source_ref", "producer", "trust_root_mode", "verifier_versions")
BUNDLE_REGISTRY_INDEX = "index.json"
BUNDLE_REGISTRY_RECORDS_DIR = "records"
DEFAULT_ARTIFACT_SUBJECT_STORE_ROOT = Path("/var/lib/abyss-machine/artifacts/subjects")
ARTIFACT_SUBJECT_STORE_META = "subject-store.json"


def _root_has_artifact_policy(root: Path) -> bool:
    return (root / POLICY_REF).is_file() and (root / ABI_REF).is_file()


def _candidate_public_seed_roots() -> list[Path]:
    module_path = Path(__file__).resolve()
    candidates: list[Path] = []
    env_root = os.environ.get("ABYSS_MACHINE_PUBLIC_SEED_ROOT") or os.environ.get("ABYSS_MACHINE_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    for root in [Path.cwd(), *Path.cwd().parents]:
        candidates.append(root)
    for root in module_path.parents:
        candidates.append(root)
        candidates.append(root / "share" / "abyss-machine")
    candidates.append(Path("/usr/local/share/abyss-machine"))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def resolve_public_seed_root() -> Path:
    for root in _candidate_public_seed_roots():
        if _root_has_artifact_policy(root):
            return root
    return Path(__file__).resolve().parents[2]


REPO_ROOT = resolve_public_seed_root()


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _stable_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _parse_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _file_digest_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return _read_json(repo_root / POLICY_REF)


def load_abi_signatures(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    return _read_json(repo_root / ABI_REF)


def artifact_class_rule(artifact_class: str, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    policy = load_policy(repo_root)
    classes = policy.get("artifact_classes")
    if not isinstance(classes, dict) or artifact_class not in classes:
        raise ValueError(f"unknown artifact_class: {artifact_class}")
    rule = classes[artifact_class]
    if not isinstance(rule, dict):
        raise ValueError(f"artifact_class rule must be an object: {artifact_class}")
    return rule


def _producer_profile_rows(policy: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = policy.get("producer_profiles")
    if not isinstance(profiles, dict):
        return []
    rows: list[dict[str, Any]] = []
    for profile_id, profile in sorted(profiles.items()):
        if not isinstance(profile, dict):
            continue
        row = {**profile}
        row["profile_id"] = str(row.get("profile_id") or profile_id)
        row["owner_repo"] = str(row.get("owner_repo") or "")
        row["artifact_classes"] = [str(item) for item in row.get("artifact_classes", []) if str(item)]
        row["owner_route_refs"] = [str(item) for item in row.get("owner_route_refs", []) if str(item)]
        row["release_export_triggers"] = [str(item) for item in row.get("release_export_triggers", []) if str(item)]
        row["validator_commands"] = [str(item) for item in row.get("validator_commands", []) if str(item)]
        row["produced_sidecars"] = [str(item) for item in row.get("produced_sidecars", []) if str(item)]
        row["consumer_expectations"] = [str(item) for item in row.get("consumer_expectations", []) if str(item)]
        row["owner_boundaries"] = [str(item) for item in row.get("owner_boundaries", []) if str(item)]
        row["trust_root_modes"] = [str(item) for item in row.get("trust_root_modes", []) if str(item)]
        rows.append(row)
    return rows


def _producer_profiles_for_artifact_class(policy: dict[str, Any], artifact_class: str) -> list[dict[str, Any]]:
    return [
        profile
        for profile in _producer_profile_rows(policy)
        if artifact_class in set(profile.get("artifact_classes", []))
    ]


def artifact_producer_profiles(
    *,
    profile_id: str = "",
    owner_repo: str = "",
    artifact_class: str = "",
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    policy = load_policy(repo_root)
    classes = policy.get("artifact_classes") if isinstance(policy.get("artifact_classes"), dict) else {}
    rows = _producer_profile_rows(policy)
    errors: list[str] = []
    if profile_id:
        rows = [row for row in rows if row.get("profile_id") == profile_id]
        if not rows:
            errors.append(f"unknown producer profile: {profile_id}")
    if owner_repo:
        rows = [row for row in rows if row.get("owner_repo") == owner_repo]
        if not rows:
            errors.append(f"unknown producer owner_repo: {owner_repo}")
    if artifact_class:
        if artifact_class not in classes:
            errors.append(f"unknown artifact_class: {artifact_class}")
        rows = [row for row in rows if artifact_class in set(row.get("artifact_classes", []))]
    artifact_classes = sorted({class_id for row in rows for class_id in row.get("artifact_classes", [])})
    owner_repos = sorted({str(row.get("owner_repo")) for row in rows if row.get("owner_repo")})
    return {
        "ok": not errors,
        "schema": "abyss_machine_artifact_producer_profiles_v1",
        "policy_ref": POLICY_REF,
        "policy_version": policy.get("policy_version"),
        "abi_ref": ABI_REF,
        "profile_filter": profile_id or None,
        "owner_repo_filter": owner_repo or None,
        "artifact_class_filter": artifact_class or None,
        "summary": {
            "profiles": len(rows),
            "owner_repos": owner_repos,
            "artifact_classes": artifact_classes,
            "artifact_class_count": len(artifact_classes),
        },
        "rows": rows,
        "agent_loop": {
            "classify": "abyss-machine artifacts classify --artifact-class ARTIFACT_CLASS --json",
            "requirements": "abyss-machine artifacts requirements --artifact-class ARTIFACT_CLASS --json",
            "producer_profiles": "abyss-machine artifacts producer-profiles --artifact-class ARTIFACT_CLASS --json",
            "build_sidecars": "abyss-machine artifacts build-sidecars --artifact-class ARTIFACT_CLASS --bundle-dir BUNDLE_DIR --json",
            "evidence_promote": "abyss-machine artifacts evidence-promote BUNDLE_DIR --json",
            "trust_gate": "abyss-machine artifacts trust-gate --artifact-class ARTIFACT_CLASS --json",
            "affected": "abyss-machine artifacts affected --source-repo OWNER_REPO --source-ref SOURCE_REF --json",
        },
        "claim_limits": [
            "Producer profiles are OS Abyss policy/read-model data; they do not run owner validators or produce sidecars by themselves.",
            "A profile names expected owner routes and controls; the owning repo remains authoritative for its source truth.",
            "GitHub Actions/OIDC is one producer adapter, not the whole OS Abyss trust plane.",
        ],
        "errors": errors,
    }


def validate_bundle_lifecycle(lifecycle: Any, *, manifest_ref: str) -> dict[str, Any] | None:
    if lifecycle is None:
        return None
    if not isinstance(lifecycle, dict):
        raise ValueError(f"{manifest_ref} lifecycle must be an object")
    initial_state = str(lifecycle.get("initial_state") or "")
    if initial_state not in BUNDLE_LIFECYCLE_STATES:
        raise ValueError(f"{manifest_ref} lifecycle.initial_state has unknown state: {initial_state}")
    promotion_path = lifecycle.get("promotion_path")
    if not isinstance(promotion_path, list) or not promotion_path:
        raise ValueError(f"{manifest_ref} lifecycle.promotion_path must be a non-empty list")
    normalized_path = [str(item) for item in promotion_path]
    unknown_path = sorted(set(normalized_path) - set(BUNDLE_LIFECYCLE_STATES))
    if unknown_path:
        raise ValueError(f"{manifest_ref} lifecycle.promotion_path has unknown states: {', '.join(unknown_path)}")
    if initial_state not in normalized_path:
        raise ValueError(f"{manifest_ref} lifecycle.initial_state must appear in lifecycle.promotion_path")
    latest_states = lifecycle.get("latest_eligible_states", sorted(BUNDLE_LATEST_ELIGIBLE_STATES))
    if not isinstance(latest_states, list):
        raise ValueError(f"{manifest_ref} lifecycle.latest_eligible_states must be a list")
    normalized_latest = [str(item) for item in latest_states]
    unknown_latest = sorted(set(normalized_latest) - BUNDLE_LATEST_ELIGIBLE_STATES)
    if unknown_latest:
        raise ValueError(f"{manifest_ref} lifecycle.latest_eligible_states has non-latest states: {', '.join(unknown_latest)}")
    return {
        **lifecycle,
        "initial_state": initial_state,
        "promotion_path": normalized_path,
        "latest_eligible_states": normalized_latest,
    }


def load_bundle_manifest(manifest_ref: str | Path, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    path = Path(manifest_ref)
    if not path.is_absolute():
        cwd_candidate = Path.cwd() / path
        path = cwd_candidate if cwd_candidate.is_file() else repo_root / path
    manifest = _read_json(path)
    if manifest.get("schema") != "abyss_machine_artifact_bundle_manifest_v1":
        raise ValueError(f"{path} must use schema abyss_machine_artifact_bundle_manifest_v1")
    if manifest.get("policy_ref") not in POLICY_REF_ALIASES:
        allowed = ", ".join(sorted(POLICY_REF_ALIASES))
        raise ValueError(f"{path} policy_ref must be one of: {allowed}")
    if not manifest.get("artifact_class"):
        raise ValueError(f"{path} must define artifact_class")
    if "lifecycle" in manifest:
        manifest["lifecycle"] = validate_bundle_lifecycle(manifest.get("lifecycle"), manifest_ref=str(path))
    consumer_contract = manifest.get("consumer_contract")
    if consumer_contract is not None and not isinstance(consumer_contract, dict):
        raise ValueError(f"{path} consumer_contract must be an object")
    manifest["_manifest_path"] = str(path)
    return manifest


def required_controls_for_rule(rule: dict[str, Any]) -> list[str]:
    controls = []
    for control in CONTROL_FILES:
        control_rule = rule.get(control)
        if isinstance(control_rule, dict) and control_rule.get("required") is True:
            controls.append(control)
    return controls


def deferred_controls_for_rule(rule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    deferred: dict[str, dict[str, Any]] = {}
    for control in CONTROL_FILES:
        control_rule = rule.get(control)
        if not isinstance(control_rule, dict) or control_rule.get("required") is True:
            continue
        deferred[control] = {
            "required": False,
            "reason": str(control_rule.get("trigger") or "not required by artifact signature policy"),
        }
    return deferred


def contract_surface_for_class(
    artifact_class: str,
    *,
    contract_surface_id: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    abi = load_abi_signatures(repo_root)
    surfaces = abi.get("contract_surfaces")
    if not isinstance(surfaces, list):
        raise ValueError(f"{ABI_REF} must define contract_surfaces")
    candidates = [
        surface
        for surface in surfaces
        if isinstance(surface, dict)
        and surface.get("artifact_class") == artifact_class
        and (contract_surface_id is None or surface.get("id") == contract_surface_id)
    ]
    if not candidates:
        if contract_surface_id:
            raise ValueError(f"no ABI contract surface {contract_surface_id!r} for artifact_class {artifact_class}")
        raise ValueError(f"no ABI contract surface for artifact_class {artifact_class}")
    return dict(candidates[0])


def classify_artifact(
    target: str | Path | None = None,
    *,
    artifact_class: str = "public_source_seed",
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    bundle_dir = Path(target) if target else None
    identity: dict[str, Any] | None = None
    if bundle_dir is not None and bundle_dir.is_dir() and (bundle_dir / IDENTITY_SIDECAR).is_file():
        identity = _read_json(bundle_dir / IDENTITY_SIDECAR)
        artifact_class = str(identity.get("artifact_class") or artifact_class)

    policy = load_policy(repo_root)
    rule = artifact_class_rule(artifact_class, repo_root=repo_root)
    required = required_controls_for_rule(rule)
    deferred = deferred_controls_for_rule(rule)
    return {
        "ok": True,
        "schema": "abyss_machine_artifact_bundle_classification_v1",
        "artifact_class": artifact_class,
        "bundle_layout": BUNDLE_LAYOUT,
        "target": str(bundle_dir) if bundle_dir else None,
        "policy_ref": POLICY_REF,
        "policy_version": policy.get("policy_version"),
        "identity": identity or rule.get("identity"),
        "required_controls": required,
        "deferred_controls": deferred,
        "required_sidecars": {control: CONTROL_FILES[control] for control in required},
        "signature_required": "sigstore_cosign" in required,
    }


def consumer_intent_for_artifact_class(artifact_class: str) -> str:
    if artifact_class == "bootstrap_install_bundle":
        return "installer"
    if artifact_class == "aoa_session_memory_portable_bundle":
        return "update_client"
    if artifact_class in {"runtime_or_container_artifact", "ai_model_or_runtime_bundle"}:
        return "runtime"
    if artifact_class in {"browser_extension_package", "public_media_export"}:
        return "release_consumer"
    return "agent"


def _release_rules_for_class(policy: dict[str, Any], artifact_class: str) -> list[dict[str, Any]]:
    rules = policy.get("release_artifact_rules")
    if not isinstance(rules, list):
        return []
    return [
        dict(rule)
        for rule in rules
        if isinstance(rule, dict) and str(rule.get("artifact_class") or "") == artifact_class
    ]


def _contract_surfaces_for_class(policy: dict[str, Any], artifact_class: str) -> list[dict[str, Any]]:
    surfaces = policy.get("contract_surfaces")
    if not isinstance(surfaces, list):
        return []
    return [
        dict(surface)
        for surface in surfaces
        if isinstance(surface, dict) and str(surface.get("artifact_class") or "") == artifact_class
    ]


def _generated_contract_surfaces_for_class(repo_root: Path, artifact_class: str) -> list[dict[str, Any]]:
    try:
        abi = load_abi_signatures(repo_root)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return []
    surfaces = abi.get("contract_surfaces")
    if not isinstance(surfaces, list):
        return []
    return [
        dict(surface)
        for surface in surfaces
        if isinstance(surface, dict) and str(surface.get("artifact_class") or "") == artifact_class
    ]


def _bundle_manifest_refs_for_class(repo_root: Path, artifact_class: str) -> list[str]:
    bundle_root = repo_root / "manifests" / "artifact_bundles"
    if not bundle_root.is_dir():
        return []
    refs: list[str] = []
    for path in sorted(bundle_root.glob("*.json")):
        try:
            manifest = _read_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if str(manifest.get("artifact_class") or "") != artifact_class:
            continue
        try:
            refs.append(path.relative_to(repo_root).as_posix())
        except ValueError:
            refs.append(path.as_posix())
    return refs


def _repo_relative_text(path: str | Path, *, repo_root: Path = REPO_ROOT) -> str:
    text = str(path).replace("\\", "/").strip()
    if not text:
        return ""
    candidate = Path(text)
    if candidate.is_absolute():
        try:
            return candidate.relative_to(repo_root).as_posix()
        except ValueError:
            return candidate.as_posix()
    while text.startswith("./"):
        text = text[2:]
    return text


def _path_matches_ref(path_text: str, ref_text: str) -> bool:
    path = _repo_relative_text(path_text)
    ref = _repo_relative_text(ref_text)
    if not path or not ref:
        return False
    if any(char in ref for char in "*?["):
        return fnmatch.fnmatch(path, ref)
    ref = ref.rstrip("/")
    return path == ref or path.startswith(ref + "/")


def _trust_root_expectations(rule: dict[str, Any], *, consumer_intent: str) -> dict[str, Any]:
    required = set(required_controls_for_rule(rule))
    artifact_class = str(rule.get("identity", {}).get("artifact_class") or "")
    release_modes = ["public_release"]
    if "sigstore_cosign" in required:
        release_modes.append("github_oidc")
    if artifact_class in {"runtime_or_container_artifact", "ai_model_or_runtime_bundle"}:
        release_modes.append("oci_registry")
    if consumer_intent not in PRODUCTION_CONSUMER_INTENTS:
        recommended = ["host_managed", "local_dev"]
    elif artifact_class == "host_local_evidence":
        recommended = ["host_managed"]
    else:
        recommended = release_modes
    return {
        "known_modes": list(TRUST_ROOT_MODES),
        "recommended_for_consumer_intent": sorted(dict.fromkeys(recommended)),
        "local_dev": {
            "allowed_for_local_development": True,
            "production_consumer_result": "manual_review_required",
        },
        "host_managed": {
            "role": "durable OS Abyss host registry assertion or local host-managed evidence",
        },
        "github_oidc": {
            "role": "GitHub Actions/OIDC producer adapter for release provenance",
            "adapter_only": True,
        },
        "oci_registry": {
            "role": "OCI/ORAS image or bundle publication by digest",
            "required_when": "runtime/container/model artifacts are consumed through OCI distribution",
        },
        "public_release": {
            "role": "public release asset with publishable attestations or signatures",
        },
    }


def update_transparency_lane(*, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    policy = load_policy(repo_root)
    lane = policy.get("update_transparency_lane")
    if not isinstance(lane, dict):
        deferred = policy.get("deferred_trust_layers") if isinstance(policy.get("deferred_trust_layers"), dict) else {}
        lane = {
            "schema": "abyss_machine_update_transparency_lane_v1",
            "tuf": {
                **(deferred.get("tuf") if isinstance(deferred.get("tuf"), dict) else {}),
                "status": "not_configured",
                "applies_to_artifact_classes": [],
            },
            "scitt": {
                **(deferred.get("scitt") if isinstance(deferred.get("scitt"), dict) else {}),
                "status": "future_integration_point",
                "blocking_v1": False,
            },
        }
    return dict(lane)


def update_lane_status(
    *,
    artifact_class: str = "",
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    lane = update_transparency_lane(repo_root=repo_root)
    tuf = lane.get("tuf") if isinstance(lane.get("tuf"), dict) else {}
    scitt = lane.get("scitt") if isinstance(lane.get("scitt"), dict) else {}
    classes = load_policy(repo_root).get("artifact_classes")
    policy_classes = set(classes) if isinstance(classes, dict) else set()
    applies = [str(item) for item in tuf.get("applies_to_artifact_classes", []) if str(item)]
    selected = [artifact_class] if artifact_class else applies
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for class_id in selected:
        if class_id not in policy_classes:
            errors.append(f"unknown artifact_class: {class_id}")
            continue
        applies_to_class = class_id in applies
        rows.append({
            "schema": "abyss_machine_update_lane_row_v1",
            "artifact_class": class_id,
            "applies": applies_to_class,
            "consumer_intent": "update_client" if applies_to_class else consumer_intent_for_artifact_class(class_id),
            "metadata_sidecar": tuf.get("metadata_sidecar"),
            "required_when": tuf.get("required_when"),
            "client_checks": tuf.get("client_checks", []),
            "status": "TUF_REQUIRED_FOR_UPDATE_CLIENT" if applies_to_class else "NOT_UPDATEABLE_BY_POLICY",
        })
    return {
        "ok": not errors,
        "schema": "abyss_machine_update_transparency_lane_status_v1",
        "policy_ref": POLICY_REF,
        "artifact_class_filter": artifact_class or None,
        "summary": {
            "tuf_status": tuf.get("status") or "unknown",
            "scitt_status": scitt.get("status") or "unknown",
            "updateable_artifact_classes": len(applies),
            "selected_rows": len(rows),
            "blocking_v1": bool(scitt.get("blocking_v1")),
        },
        "tuf": tuf,
        "scitt": scitt,
        "rows": rows,
        "errors": errors,
        "claim_limits": [
            "This lane is a TUF-style OS Abyss metadata gate, not a full external TUF repository implementation.",
            "SCITT is recorded as an external transparency integration point and is not a v1 blocker until an external transparency service exists.",
        ],
    }


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _record_source_ref_tokens(record: dict[str, Any] | None) -> list[str]:
    if not isinstance(record, dict):
        return []
    tokens: list[str] = []
    for key in ("source_ref", "bundle_manifest_ref", "producer", "producer_command"):
        value = str(record.get(key) or "").strip()
        if value:
            tokens.append(value)
    for key in ("source_refs", "evidence_refs"):
        values = record.get(key)
        if isinstance(values, list):
            tokens.extend(str(item).strip() for item in values if str(item).strip())
    return sorted(dict.fromkeys(tokens))


def _source_ref_status(row: dict[str, Any], changed_source_ref: str) -> dict[str, Any]:
    expected = str(changed_source_ref or "").strip()
    registry = row.get("registry_status") if isinstance(row.get("registry_status"), dict) else {}
    known_refs = [str(item) for item in registry.get("latest_source_ref_tokens", []) if str(item)]
    if not expected:
        return {
            "required": False,
            "expected": None,
            "matched": None,
            "matched_ref": None,
            "known_refs": known_refs,
        }
    matched = expected in known_refs
    return {
        "required": True,
        "expected": expected,
        "matched": matched,
        "matched_ref": expected if matched else None,
        "known_refs": known_refs,
    }


def verify_update_metadata(
    metadata: dict[str, Any],
    *,
    previous_trusted: dict[str, Any] | None = None,
    now: dt.datetime | str | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    lane = update_transparency_lane(repo_root=repo_root)
    tuf = lane.get("tuf") if isinstance(lane.get("tuf"), dict) else {}
    applies = {str(item) for item in tuf.get("applies_to_artifact_classes", []) if str(item)}
    previous = previous_trusted if isinstance(previous_trusted, dict) else {}
    now_dt = _parse_time(now) if isinstance(now, str) else now
    if now_dt is None:
        now_dt = dt.datetime.now(dt.UTC)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=dt.UTC)
    now_dt = now_dt.astimezone(dt.UTC)

    errors: list[str] = []
    warnings: list[str] = []
    artifact_class = str(metadata.get("artifact_class") or "")
    target = metadata.get("target") if isinstance(metadata.get("target"), dict) else {}
    version = _positive_int(metadata.get("version"))
    snapshot_version = _positive_int(metadata.get("snapshot_version"))
    timestamp_version = _positive_int(metadata.get("timestamp_version"))
    expires_at = _parse_time(metadata.get("expires_at"))
    generated_at = _parse_time(metadata.get("generated_at"))
    metadata_digest = _stable_digest(metadata)

    if metadata.get("schema") != "abyss_machine_tuf_update_metadata_v1":
        errors.append("schema_mismatch")
    if artifact_class not in applies:
        errors.append("artifact_class_not_updateable")
    if not target.get("path"):
        errors.append("target_path_missing")
    if not str(target.get("sha256") or "").startswith("sha256:"):
        errors.append("target_digest_missing")
    if version is None:
        errors.append("version_missing")
    if snapshot_version is None:
        errors.append("snapshot_version_missing")
    if timestamp_version is None:
        errors.append("timestamp_version_missing")
    if expires_at is None:
        errors.append("expires_at_missing")
    elif expires_at <= now_dt:
        errors.append("expired_metadata")
    if generated_at is None:
        warnings.append("generated_at_missing")

    previous_version = _positive_int(previous.get("version"))
    previous_snapshot = _positive_int(previous.get("snapshot_version"))
    previous_timestamp = _positive_int(previous.get("timestamp_version"))
    if version is not None and previous_version is not None and version < previous_version:
        errors.append("rollback_version")
    if snapshot_version is not None and previous_snapshot is not None and snapshot_version < previous_snapshot:
        errors.append("rollback_snapshot_version")
    if timestamp_version is not None and previous_timestamp is not None and timestamp_version < previous_timestamp:
        errors.append("rollback_timestamp_version")

    last_seen = _parse_time(previous.get("last_seen_at"))
    max_freeze_seconds = _positive_int(tuf.get("max_freeze_seconds")) or 0
    if (
        max_freeze_seconds
        and last_seen is not None
        and str(previous.get("metadata_sha256") or "") == metadata_digest
        and (now_dt - last_seen).total_seconds() > max_freeze_seconds
    ):
        errors.append("freeze_attack_or_stale_metadata")

    ok = not errors
    return {
        "ok": ok,
        "schema": "abyss_machine_update_metadata_verify_v1",
        "policy_ref": POLICY_REF,
        "artifact_class": artifact_class,
        "metadata_schema": metadata.get("schema"),
        "metadata_sha256": metadata_digest,
        "verdict": "allow" if ok else "deny",
        "known_verdicts": list(UPDATE_LANE_VERDICTS),
        "errors": errors,
        "warnings": warnings,
        "checked": {
            "artifact_class_updateable": artifact_class in applies,
            "target_digest": target.get("sha256"),
            "version": version,
            "snapshot_version": snapshot_version,
            "timestamp_version": timestamp_version,
            "expires_at": expires_at.isoformat().replace("+00:00", "Z") if expires_at else None,
            "generated_at": generated_at.isoformat().replace("+00:00", "Z") if generated_at else None,
            "now": now_dt.isoformat().replace("+00:00", "Z"),
            "previous": {
                "version": previous_version,
                "snapshot_version": previous_snapshot,
                "timestamp_version": previous_timestamp,
                "metadata_sha256": previous.get("metadata_sha256"),
                "last_seen_at": previous.get("last_seen_at"),
            },
        },
        "claim_limits": [
            "This verifies OS Abyss TUF-style metadata invariants and does not claim a complete external TUF repository or delegated key ceremony.",
            "A passing result only admits update-client consideration; artifact trust-gate verification is still required for the target artifact.",
        ],
    }


def production_privacy_boundary_review_reason(privacy_boundary: object) -> str:
    normalized = " ".join(str(privacy_boundary or "").lower().split())
    if not normalized:
        return "production_consumer_requires_privacy_boundary"
    if normalized.startswith(PUBLIC_PRIVACY_BOUNDARY_PREFIXES):
        return ""
    if "public-safe" in normalized or "publishable" in normalized:
        return ""
    if any(marker in normalized for marker in PRIVATE_PRIVACY_BOUNDARY_MARKERS):
        return "production_consumer_requires_public_privacy_boundary"
    if "private" in normalized:
        return "production_consumer_requires_public_privacy_boundary"
    return "production_consumer_requires_public_privacy_boundary"


def artifact_requirement_row(
    artifact_class: str,
    *,
    registry_dir: str | Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    policy = load_policy(repo_root)
    rule = artifact_class_rule(artifact_class, repo_root=repo_root)
    identity = rule.get("identity") if isinstance(rule.get("identity"), dict) else {}
    required = required_controls_for_rule(rule)
    deferred = deferred_controls_for_rule(rule)
    release_rules = _release_rules_for_class(policy, artifact_class)
    policy_surfaces = _contract_surfaces_for_class(policy, artifact_class)
    generated_surfaces = _generated_contract_surfaces_for_class(repo_root, artifact_class)
    manifest_refs = _bundle_manifest_refs_for_class(repo_root, artifact_class)
    automation_profiles = _producer_profiles_for_artifact_class(policy, artifact_class)
    consumer_intent = consumer_intent_for_artifact_class(artifact_class)
    if "abi_signature" not in required:
        contract_surface_status = "abi_not_required"
    elif policy_surfaces or generated_surfaces:
        contract_surface_status = "local_contract_surface"
    else:
        contract_surface_status = "external_subject_or_owner_bundle_required"

    registry_status: dict[str, Any] = {"checked": False}
    trust_gate_status: dict[str, Any] = {"checked": False}
    if registry_dir is not None:
        registry = read_bundle_registry(registry_dir, artifact_class=artifact_class)
        latest = registry.get("latest_by_artifact_class", {}).get(artifact_class)
        class_records = [
            record
            for record in registry.get("records", [])
            if isinstance(record, dict) and str(record.get("artifact_class") or "") == artifact_class
        ]
        registry_status = {
            "checked": True,
            "registry_dir": registry.get("registry_dir"),
            "record_count": len(class_records),
            "has_latest": isinstance(latest, dict),
            "latest_record_id": latest.get("record_id") if isinstance(latest, dict) else None,
            "latest_state": latest.get("lifecycle_state") if isinstance(latest, dict) else None,
            "latest_source_ref": latest.get("source_ref") if isinstance(latest, dict) else None,
            "latest_source_refs": latest.get("source_refs", []) if isinstance(latest, dict) else [],
            "latest_source_repo": latest.get("source_repo") if isinstance(latest, dict) else None,
            "latest_producer": latest.get("producer") if isinstance(latest, dict) else None,
            "latest_producer_command": latest.get("producer_command") if isinstance(latest, dict) else None,
            "latest_evidence_refs": latest.get("evidence_refs", []) if isinstance(latest, dict) else [],
            "latest_source_ref_tokens": _record_source_ref_tokens(latest if isinstance(latest, dict) else None),
            "latest_trust_root_mode": latest.get("trust_root_mode") if isinstance(latest, dict) else None,
            "latest_verified_controls": latest.get("verified_controls", []) if isinstance(latest, dict) else [],
        }
        gate = trust_gate(registry_dir, artifact_class=artifact_class, consumer_intent=consumer_intent) if isinstance(latest, dict) else {}
        trust_gate_status = {
            "checked": isinstance(latest, dict),
            "consumer_intent": consumer_intent,
            "verdict": gate.get("verdict") if isinstance(gate, dict) else None,
            "ok": gate.get("ok") if isinstance(gate, dict) else False,
            "reasons": gate.get("reasons", []) if isinstance(gate, dict) else [],
        }

    source_paths = sorted({
        str(path)
        for surface in policy_surfaces
        for path in surface.get("source_paths", [])
        if str(path)
    })
    authority_refs = [str(item) for item in identity.get("authority_ref", [])] if isinstance(identity.get("authority_ref"), list) else []
    release_patterns = [
        str(pattern)
        for rule_item in release_rules
        for pattern in rule_item.get("artifact_patterns", [])
        if str(pattern)
    ]
    return {
        "schema": "abyss_machine_artifact_requirements_row_v1",
        "artifact_class": artifact_class,
        "owner_repo": identity.get("owner_repo"),
        "producer_profile": {
            "surface_state": identity.get("surface_state"),
            "producer": identity.get("producer"),
            "producer_action": identity.get("action"),
            "authority_ref": authority_refs,
            "content_identity": identity.get("content_identity"),
            "privacy_boundary": identity.get("privacy_boundary"),
            "consumer_expectation": identity.get("consumer_expectation"),
            "verification": identity.get("verification", []),
            "automation_profile_ids": [profile.get("profile_id") for profile in automation_profiles],
        },
        "producer_profiles": automation_profiles,
        "consumer": {
            "intent": consumer_intent,
            "trust_gate": f"abyss-machine artifacts trust-gate --artifact-class {artifact_class} --consumer-intent {consumer_intent} --json",
            "registry_query": f"abyss-machine artifacts bundle-registry --artifact-class {artifact_class} --json",
        },
        "controls": {
            "required": required,
            "deferred": deferred,
            "required_sidecars": {control: CONTROL_FILES[control] for control in required},
            "signature_required": "sigstore_cosign" in required,
            "trust_layers": identity.get("trust_layer", []),
        },
        "trust_roots": _trust_root_expectations(rule, consumer_intent=consumer_intent),
        "source_route": {
            "contract_surface_status": contract_surface_status,
            "contract_surfaces": policy_surfaces,
            "generated_contract_surfaces": generated_surfaces,
            "contract_source_paths": source_paths,
            "bundle_manifest_refs": manifest_refs,
            "release_artifact_patterns": release_patterns,
        },
        "release_rules": release_rules,
        "registry_status": registry_status,
        "trust_gate_status": trust_gate_status,
        "agent_loop": {
            "producer_profiles": f"abyss-machine artifacts producer-profiles --artifact-class {artifact_class} --json",
            "requirements": f"abyss-machine artifacts requirements --artifact-class {artifact_class} --json",
            "affected": f"abyss-machine artifacts affected --artifact-class {artifact_class} --json",
            "build_sidecars": f"abyss-machine artifacts build-sidecars --artifact-class {artifact_class} --bundle-dir BUNDLE_DIR --json",
            "evidence_promote": "abyss-machine artifacts evidence-promote BUNDLE_DIR --json",
            "trust_gate": f"abyss-machine artifacts trust-gate --artifact-class {artifact_class} --consumer-intent {consumer_intent} --json",
        },
        "claim_limits": [
            "Requirements are a policy/read-model projection; they do not produce evidence or prove an artifact is safe.",
            "Sibling-owned producer profiles name owner expectations but do not replace owner-repo validators or release decisions.",
            "GitHub OIDC is one producer adapter, not the OS Abyss trust plane itself.",
        ],
    }


def artifact_requirements(
    artifact_class: str = "",
    *,
    registry_dir: str | Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    policy = load_policy(repo_root)
    classes = policy.get("artifact_classes") if isinstance(policy.get("artifact_classes"), dict) else {}
    selected = [artifact_class] if artifact_class else sorted(str(item) for item in classes)
    rows = [
        artifact_requirement_row(class_id, registry_dir=registry_dir, repo_root=repo_root)
        for class_id in selected
        if class_id in classes
    ]
    missing = [class_id for class_id in selected if class_id not in classes]
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("source_route", {}).get("contract_surface_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "ok": not missing,
        "schema": "abyss_machine_artifact_requirements_v1",
        "policy_ref": POLICY_REF,
        "policy_version": policy.get("policy_version"),
        "abi_ref": ABI_REF,
        "artifact_class_filter": artifact_class or None,
        "summary": {
            "artifact_classes": len(rows),
            "missing_artifact_classes": missing,
            "contract_surface_status_counts": status_counts,
        },
        "rows": rows,
        "errors": [f"unknown artifact_class: {class_id}" for class_id in missing],
    }


def _artifact_affected_matches(
    row: dict[str, Any],
    changed_paths: list[str],
    *,
    changed_source_repo: str = "",
) -> tuple[list[str], list[dict[str, Any]]]:
    source_route = row.get("source_route") if isinstance(row.get("source_route"), dict) else {}
    profile = row.get("producer_profile") if isinstance(row.get("producer_profile"), dict) else {}
    automation_profiles = [
        item for item in row.get("producer_profiles", []) if isinstance(item, dict)
    ] if isinstance(row.get("producer_profiles"), list) else []
    profile_owner_repos = {
        str(item.get("owner_repo"))
        for item in automation_profiles
        if str(item.get("owner_repo") or "")
    }
    owner_repo = str(row.get("owner_repo") or "")
    local_policy_scope = not changed_source_repo or changed_source_repo == "abyss-machine"
    owner_scope = not changed_source_repo or not owner_repo or changed_source_repo == owner_repo or changed_source_repo in profile_owner_repos
    refs: list[tuple[str, str]] = []
    refs.extend(("contract_source", str(item)) for item in source_route.get("contract_source_paths", []) if str(item))
    refs.extend(("bundle_manifest", str(item)) for item in source_route.get("bundle_manifest_refs", []) if str(item))
    refs.extend(("authority_ref", str(item)) for item in profile.get("authority_ref", []) if str(item) and not str(item).startswith("/"))
    for automation_profile in automation_profiles:
        refs.extend(
            ("producer_profile_route", str(item))
            for item in automation_profile.get("owner_route_refs", [])
            if str(item) and not str(item).startswith("/")
        )
    refs.extend(("release_artifact_pattern", str(item)) for item in source_route.get("release_artifact_patterns", []) if str(item))
    matches: list[dict[str, Any]] = []
    reasons: set[str] = set()
    for changed in changed_paths:
        if local_policy_scope and _path_matches_ref(changed, POLICY_REF):
            matches.append({"reason": "policy_manifest_changed", "changed_path": changed, "matched_ref": POLICY_REF})
            reasons.add("policy_manifest_changed")
            continue
        if local_policy_scope and _path_matches_ref(changed, ABI_REF):
            matches.append({"reason": "abi_signature_readmodel_changed", "changed_path": changed, "matched_ref": ABI_REF})
            reasons.add("abi_signature_readmodel_changed")
            continue
        if not owner_scope:
            continue
        for ref_kind, ref in refs:
            if _path_matches_ref(changed, ref):
                matches.append({"reason": f"{ref_kind}_changed", "changed_path": changed, "matched_ref": ref})
                reasons.add(f"{ref_kind}_changed")
    return sorted(reasons), matches


def _artifact_affected_verdict(
    row: dict[str, Any],
    *,
    affected_reasons: list[str],
    changed_source_repo: str,
    changed_source_ref: str,
    accept_sibling_lag: bool,
) -> str:
    owner_repo = str(row.get("owner_repo") or "")
    automation_profiles = [
        item for item in row.get("producer_profiles", []) if isinstance(item, dict)
    ] if isinstance(row.get("producer_profiles"), list) else []
    profile_owner_repos = {
        str(item.get("owner_repo"))
        for item in automation_profiles
        if str(item.get("owner_repo") or "")
    }
    registry = row.get("registry_status") if isinstance(row.get("registry_status"), dict) else {}
    gate = row.get("trust_gate_status") if isinstance(row.get("trust_gate_status"), dict) else {}
    source_status = _source_ref_status(row, changed_source_ref)
    owner_repo_changed = bool(changed_source_repo and owner_repo and changed_source_repo == owner_repo)
    profile_owner_changed = bool(changed_source_repo and changed_source_repo in profile_owner_repos)
    external_owner_changed = bool(changed_source_repo and changed_source_repo != "abyss-machine" and (owner_repo_changed or profile_owner_changed))
    if external_owner_changed:
        if source_status.get("matched") is True:
            if registry.get("checked") and not registry.get("has_latest"):
                return "needs_rebuild"
            if gate.get("verdict") == "manual_review_required":
                return "manual_review_required"
            if gate.get("checked") and gate.get("verdict") not in {None, "allow", "warn"}:
                return "needs_reverify"
            return "fresh"
        return "accepted_lag" if accept_sibling_lag else "blocked_by_missing_sibling"
    if any(reason in affected_reasons for reason in ("contract_source_changed", "bundle_manifest_changed", "authority_ref_changed", "producer_profile_route_changed", "release_artifact_pattern_changed")):
        return "needs_rebuild"
    if any(reason in affected_reasons for reason in ("policy_manifest_changed", "abi_signature_readmodel_changed")):
        return "needs_reverify"
    if owner_repo_changed:
        return "needs_rebuild"
    if registry.get("checked") and not registry.get("has_latest"):
        return "needs_rebuild"
    if gate.get("verdict") == "manual_review_required":
        return "manual_review_required"
    if gate.get("checked") and gate.get("verdict") not in {None, "allow", "warn"}:
        return "needs_reverify"
    return "fresh"


def artifact_affected(
    changed_paths: list[str] | None = None,
    *,
    changed_source_repo: str = "",
    changed_source_ref: str = "",
    artifact_class: str = "",
    registry_dir: str | Path | None = None,
    accept_sibling_lag: bool = False,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    normalized_paths = sorted({_repo_relative_text(path, repo_root=repo_root) for path in changed_paths or [] if str(path)})
    requirements = artifact_requirements(artifact_class, registry_dir=registry_dir, repo_root=repo_root)
    rows: list[dict[str, Any]] = []
    for requirement in requirements.get("rows", []):
        if not isinstance(requirement, dict):
            continue
        reasons, matches = _artifact_affected_matches(
            requirement,
            normalized_paths,
            changed_source_repo=changed_source_repo,
        )
        owner_repo = str(requirement.get("owner_repo") or "")
        automation_profiles = [
            item for item in requirement.get("producer_profiles", []) if isinstance(item, dict)
        ] if isinstance(requirement.get("producer_profiles"), list) else []
        profile_owner_repos = {
            str(item.get("owner_repo"))
            for item in automation_profiles
            if str(item.get("owner_repo") or "")
        }
        owner_repo_changed = bool(changed_source_repo and owner_repo and changed_source_repo == owner_repo)
        profile_owner_changed = bool(changed_source_repo and changed_source_repo in profile_owner_repos)
        source_status = _source_ref_status(requirement, changed_source_ref)
        if owner_repo_changed and source_status.get("matched") is not True and "owner_repo_changed" not in reasons:
            reasons.append("owner_repo_changed")
        if (
            profile_owner_changed
            and not owner_repo_changed
            and source_status.get("matched") is not True
            and "producer_profile_owner_changed" not in reasons
        ):
            reasons.append("producer_profile_owner_changed")
        verdict = _artifact_affected_verdict(
            requirement,
            affected_reasons=reasons,
            changed_source_repo=changed_source_repo,
            changed_source_ref=changed_source_ref,
            accept_sibling_lag=accept_sibling_lag,
        )
        if verdict == "fresh" and source_status.get("matched") is True:
            reasons = []
        freshness = "fresh"
        if verdict in {"needs_rebuild", "needs_reverify", "blocked_by_missing_sibling", "accepted_lag"}:
            freshness = "stale"
        source_route = requirement.get("source_route") if isinstance(requirement.get("source_route"), dict) else {}
        registry = requirement.get("registry_status") if isinstance(requirement.get("registry_status"), dict) else {}
        gate = requirement.get("trust_gate_status") if isinstance(requirement.get("trust_gate_status"), dict) else {}
        next_actions = [
            f"abyss-machine artifacts requirements --artifact-class {requirement.get('artifact_class')} --json",
        ]
        if verdict in {"needs_rebuild", "stale"}:
            next_actions.append("rebuild artifact sidecars in the source owner route")
            next_actions.append("abyss-machine artifacts evidence-promote BUNDLE_DIR --json")
        if verdict in {"needs_reverify", "manual_review_required"}:
            next_actions.append(f"abyss-machine artifacts trust-gate --artifact-class {requirement.get('artifact_class')} --json")
        if verdict in {"blocked_by_missing_sibling", "accepted_lag"}:
            producer_owner = changed_source_repo if profile_owner_changed else owner_repo
            next_actions.append(f"run the producer profile in owner repo {producer_owner}")
            next_actions.append("promote the new owner-produced evidence into the host registry")
        rows.append({
            "schema": "abyss_machine_artifact_affected_row_v1",
            "artifact_class": requirement.get("artifact_class"),
            "owner_repo": owner_repo,
            "affected": bool(reasons or verdict not in {"fresh", "manual_review_required"}),
            "verdict": verdict,
            "freshness": freshness,
            "reasons": reasons,
            "matches": matches,
            "changed_source_repo": changed_source_repo or None,
            "contract_surface_status": source_route.get("contract_surface_status"),
            "registry": {
                "checked": registry.get("checked"),
                "has_latest": registry.get("has_latest"),
                "latest_record_id": registry.get("latest_record_id"),
                "latest_state": registry.get("latest_state"),
                "latest_source_repo": registry.get("latest_source_repo"),
                "latest_source_ref": registry.get("latest_source_ref"),
                "latest_source_refs": registry.get("latest_source_refs", []),
                "latest_producer": registry.get("latest_producer"),
                "latest_evidence_refs": registry.get("latest_evidence_refs", []),
            },
            "trust_gate": {
                "checked": gate.get("checked"),
                "verdict": gate.get("verdict"),
                "reasons": gate.get("reasons", []),
            },
            "source_ref_status": source_status,
            "next_actions": next_actions,
            "claim_limit": "Affected detects declared source/profile drift and closes source-ref drift only when latest durable evidence proves the ref; it does not rebuild or consume artifacts by itself.",
        })
    status_counts: dict[str, int] = {}
    affected_count = 0
    for row in rows:
        verdict = str(row.get("verdict") or "unknown")
        status_counts[verdict] = status_counts.get(verdict, 0) + 1
        if row.get("affected"):
            affected_count += 1
    return {
        "ok": bool(requirements.get("ok")),
        "schema": "abyss_machine_artifact_affected_v1",
        "policy_ref": POLICY_REF,
        "abi_ref": ABI_REF,
        "artifact_class_filter": artifact_class or None,
        "changed_paths": normalized_paths,
        "changed_source_repo": changed_source_repo or None,
        "changed_source_ref": str(changed_source_ref or "") or None,
        "accept_sibling_lag": accept_sibling_lag,
        "known_verdicts": list(ARTIFACT_AFFECTED_VERDICTS),
        "summary": {
            "artifact_classes": len(rows),
            "affected": affected_count,
            "status_counts": status_counts,
        },
        "rows": rows,
        "errors": requirements.get("errors", []),
    }


def build_local_provenance_packet(
    identity: dict[str, Any],
    *,
    policy: dict[str, Any],
    manifest: dict[str, Any] | None,
    producer_command: str,
) -> dict[str, Any]:
    packet_contract = policy.get("local_provenance_packet")
    if not isinstance(packet_contract, dict):
        raise ValueError("artifact signature policy must define local_provenance_packet")
    local = manifest.get("local_provenance") if isinstance(manifest, dict) else None
    local = local if isinstance(local, dict) else {}

    content_identity = local.get("content_identity")
    if not isinstance(content_identity, dict):
        content_identity = {
            "path": "/var/lib/abyss-machine/artifacts/example/latest.json",
            "sha256": _stable_digest(identity),
        }
    activity = local.get("activity")
    if not isinstance(activity, dict):
        activity = {
            "type": "artifact_bundle_sidecar_generation",
            "mode": identity.get("mode"),
            "sample_public_safe_contract": bool(manifest and manifest.get("public_safe") is True),
        }
    source_refs = local.get("source_refs")
    if not isinstance(source_refs, list) or not all(isinstance(item, str) and item for item in source_refs):
        source_refs = [POLICY_REF, str(identity.get("bundle_manifest_ref") or "")]
        source_refs = [item for item in source_refs if item]
    verification = local.get("verification")
    if not isinstance(verification, list) or not all(isinstance(item, str) and item for item in verification):
        identity_verification = identity.get("verification")
        verification = identity_verification if isinstance(identity_verification, list) else ["abyss-machine artifacts validate --json"]

    return {
        "schema": packet_contract.get("schema"),
        "schema_ref": packet_contract.get("schema_ref"),
        "artifact_class": "host_local_evidence",
        "surface_state": identity.get("surface_state"),
        "owner_repo": identity.get("owner_repo"),
        "authority_ref": identity.get("authority_ref"),
        "producer": identity.get("producer"),
        "producer_command": str(local.get("producer_command") or producer_command),
        "source_refs": source_refs,
        "activity": activity,
        "agent_or_tool": str(local.get("agent_or_tool") or "abyss-machine"),
        "created_at": _utc_now(),
        "contract_version": identity.get("contract_version"),
        "privacy_boundary": identity.get("privacy_boundary"),
        "content_identity": content_identity,
        "consumer_expectation": identity.get("consumer_expectation"),
        "verification": verification,
        "promotion_status": str(local.get("promotion_status") or "local_private_evidence_only"),
        "bundle_layout": BUNDLE_LAYOUT,
        "policy_ref": POLICY_REF,
        "not_public_repo_content": True,
    }


def _json_pointer_get(payload: Any, pointer: str) -> Any:
    if not pointer:
        return payload
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer must start with '/': {pointer}")
    current = payload
    for raw_part in pointer.strip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise ValueError(f"JSON pointer cannot descend into {type(current).__name__}: {pointer}")
    return current


def _subject_repo_root(manifest: dict[str, Any]) -> Path:
    manifest_path = Path(str(manifest.get("_manifest_path") or ""))
    subject_root = Path(str(manifest.get("subject_repo_root") or "."))
    if not subject_root.is_absolute():
        subject_root = (manifest_path.parent / subject_root).resolve()
    return subject_root.resolve()


def _public_subject_root_ref(manifest: dict[str, Any]) -> str:
    subject_root_ref = str(manifest.get("subject_repo_root") or ".")
    if Path(subject_root_ref).is_absolute():
        return "absolute-subject-root"
    return subject_root_ref


def _public_manifest_ref(manifest: dict[str, Any] | None, manifest_ref: str | Path | None = None) -> str | None:
    if manifest_ref is not None:
        candidate = Path(str(manifest_ref))
        if not candidate.is_absolute():
            return candidate.as_posix()
    if not isinstance(manifest, dict) or not manifest.get("_manifest_path"):
        return None
    manifest_path = Path(str(manifest["_manifest_path"])).resolve()
    try:
        return manifest_path.relative_to(_subject_repo_root(manifest)).as_posix()
    except ValueError:
        return manifest_path.name


def _safe_repo_relative_path(path_text: str, *, field: str) -> Path:
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be repo-relative and safe: {path_text}")
    return path


def _safe_store_token(value: str, *, field: str) -> str:
    token = str(value)
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not token or any(ch not in allowed for ch in token):
        raise ValueError(f"{field} must be a safe artifact-store token: {value}")
    return token


def _artifact_subject_store_roots() -> list[Path]:
    raw_roots: list[str] = []
    for name in ("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOTS", "ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT"):
        raw = os.environ.get(name)
        if not raw:
            continue
        if name.endswith("_ROOTS"):
            raw_roots.extend(item for item in raw.split(os.pathsep) if item)
        else:
            raw_roots.append(raw)
    raw_roots.append(str(DEFAULT_ARTIFACT_SUBJECT_STORE_ROOT))

    roots: list[Path] = []
    seen: set[str] = set()
    for raw in raw_roots:
        path = Path(raw).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def artifact_subject_store_dir(subjects: dict[str, Any], *, store_root: Path | None = None) -> Path:
    artifact_class = _safe_store_token(str(subjects.get("artifact_class") or "unknown"), field="artifact_class")
    digest = str(subjects.get("aggregate_digest") or "")
    if not digest.startswith("sha256:"):
        raise ValueError("artifact.subjects.json aggregate_digest must be a sha256 digest")
    digest_token = _safe_store_token(digest.removeprefix("sha256:"), field="aggregate_digest")
    root = store_root if store_root is not None else _artifact_subject_store_roots()[0]
    return root / artifact_class / digest_token


def _portable_path_ref(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    resolved = path.resolve()
    for root in (Path.cwd().resolve(), REPO_ROOT.resolve()):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    return resolved.name


def _registry_path_ref(registry_dir: Path, path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    resolved = path.resolve()
    for root in (Path.cwd().resolve(), REPO_ROOT.resolve()):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    registry_root = registry_dir.resolve()
    try:
        relative = resolved.relative_to(registry_root)
    except ValueError:
        return resolved.name
    if str(relative) == ".":
        return registry_root.name
    return (Path(registry_root.name) / relative).as_posix()


def build_external_abi_subject(manifest: dict[str, Any]) -> dict[str, Any] | None:
    subject = manifest.get("abi_subject")
    if not isinstance(subject, dict):
        return None
    subject_root = _subject_repo_root(manifest)
    subject_path_text = str(subject.get("path") or "")
    if not subject_path_text:
        raise ValueError("abi_subject.path is required")
    _safe_repo_relative_path(subject_path_text, field="abi_subject.path")
    subject_path = subject_root / subject_path_text
    if not subject_path.is_file():
        raise ValueError(f"abi_subject.path does not exist: {subject_path}")
    raw = subject_path.read_bytes()
    external: dict[str, Any] = {
        "schema": "abyss_machine_external_abi_subject_v1",
        "artifact_class": manifest.get("artifact_class"),
        "owner_repo": manifest.get("owner_repo"),
        "repo_root_ref": _public_subject_root_ref(manifest),
        "path": subject_path_text,
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    pointer = str(subject.get("artifact_identity_pointer") or "")
    if pointer:
        payload = json.loads(raw.decode("utf-8"))
        artifact_identity = _json_pointer_get(payload, pointer)
        if not isinstance(artifact_identity, dict):
            raise ValueError("abi_subject.artifact_identity_pointer must resolve to an object")
        external["artifact_identity_pointer"] = pointer
        external["artifact_identity"] = artifact_identity
    return external


def build_artifact_subjects(manifest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    specs = manifest.get("artifact_subjects")
    if not isinstance(specs, list):
        return None
    subject_root = _subject_repo_root(manifest)
    files: dict[str, dict[str, Any]] = {}
    for idx, spec in enumerate(specs):
        if not isinstance(spec, dict):
            raise ValueError(f"artifact_subjects[{idx}] must be an object")
        role = str(spec.get("role") or "artifact")
        candidates: list[Path] = []
        if spec.get("path"):
            path_text = str(spec["path"])
            _safe_repo_relative_path(path_text, field=f"artifact_subjects[{idx}].path")
            candidates = [subject_root / path_text]
        elif spec.get("glob"):
            pattern = str(spec["glob"])
            _safe_repo_relative_path(pattern, field=f"artifact_subjects[{idx}].glob")
            candidates = sorted(path for path in subject_root.glob(pattern) if path.is_file())
        else:
            raise ValueError(f"artifact_subjects[{idx}] must define path or glob")
        if not candidates:
            raise ValueError(f"artifact_subjects[{idx}] matched no files")
        for path in candidates:
            resolved = path.resolve()
            try:
                rel = resolved.relative_to(subject_root).as_posix()
            except ValueError as exc:
                raise ValueError(f"artifact subject escapes subject_repo_root: {path}") from exc
            if not resolved.is_file():
                raise ValueError(f"artifact subject does not exist: {resolved}")
            digest = _file_digest_hex(resolved)
            files[rel] = {
                "path": rel,
                "role": role,
                "bytes": resolved.stat().st_size,
                "sha256": f"sha256:{digest}",
                "sha256_hex": digest,
            }
    entries = [files[key] for key in sorted(files)]
    return {
        "schema": "abyss_machine_artifact_subjects_v1",
        "bundle_layout": BUNDLE_LAYOUT,
        "owner_repo": manifest.get("owner_repo"),
        "artifact_class": manifest.get("artifact_class"),
        "repo_root_ref": _public_subject_root_ref(manifest),
        "path_basis": "repo_relative",
        "files": entries,
        "aggregate_digest": _stable_digest(entries),
    }


def _artifact_subject_store_status(subjects: dict[str, Any], *, store_root: Path | None = None) -> dict[str, Any]:
    subject_files = subjects.get("files") if isinstance(subjects.get("files"), list) else []
    if not subject_files:
        return {"required": False, "ok": True}
    candidates: list[dict[str, Any]] = []
    roots = [store_root] if store_root is not None else _artifact_subject_store_roots()
    for root in roots:
        try:
            store_dir = artifact_subject_store_dir(subjects, store_root=root)
        except ValueError as exc:
            candidates.append({"root": str(root), "ok": False, "error": str(exc)})
            continue
        missing: list[str] = []
        mismatched: list[str] = []
        present = 0
        for idx, item in enumerate(subject_files):
            if not isinstance(item, dict):
                continue
            path_text = str(item.get("path") or "")
            if not path_text:
                continue
            try:
                safe_path = _safe_repo_relative_path(path_text, field=f"artifact.subjects.json files[{idx}].path")
            except ValueError as exc:
                mismatched.append(str(exc))
                continue
            path = store_dir / safe_path
            if not path.is_file():
                missing.append(path_text)
                continue
            expected = str(item.get("sha256") or "")
            actual = _file_digest(path)
            if actual != expected:
                mismatched.append(path_text)
                continue
            present += 1
        candidate = {
            "root": str(root),
            "path": str(store_dir),
            "ok": not missing and not mismatched,
            "present_files": present,
            "missing": missing[:8],
            "mismatched": mismatched[:8],
        }
        if candidate["ok"]:
            return {
                "required": True,
                "ok": True,
                "path": str(store_dir),
                "path_basis": "local_host_state",
                "aggregate_digest": subjects.get("aggregate_digest"),
                "files": present,
            }
        candidates.append(candidate)
    return {
        "required": True,
        "ok": False,
        "aggregate_digest": subjects.get("aggregate_digest"),
        "candidates": candidates[:4],
    }


def materialize_artifact_subjects(
    bundle_dir: str | Path,
    *,
    store_root: Path | None = None,
    registry_dir: str | Path | None = None,
    manifest_ref: str | Path | None = None,
    consumer_intent: str = "",
    expected_source_repo: str = "",
    expected_trust_root_mode: str = "",
    record_id: str = "",
    require_latest: bool = True,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    identity = _read_json(bundle / IDENTITY_SIDECAR) if (bundle / IDENTITY_SIDECAR).is_file() else {}
    subjects = _read_json(bundle / SUBJECTS_SIDECAR) if (bundle / SUBJECTS_SIDECAR).is_file() else {}
    subject_files = subjects.get("files") if isinstance(subjects.get("files"), list) else []
    errors: list[str] = []
    manifest: dict[str, Any] = {}
    if manifest_ref:
        try:
            manifest = load_bundle_manifest(manifest_ref, repo_root=repo_root)
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"explicit bundle manifest did not resolve: {exc}")
    else:
        manifest = _bundle_manifest_for_identity(identity, repo_root=repo_root)
    if not subject_files:
        errors.append("artifact.subjects.json must define files before materialization")
    if not manifest:
        errors.append("artifact.identity.json bundle_manifest_ref must resolve before materialization or --manifest must be supplied")
    if manifest and identity.get("artifact_class") and manifest.get("artifact_class") != identity.get("artifact_class"):
        errors.append("explicit bundle manifest artifact_class does not match artifact.identity.json")
    if errors:
        return {
            "ok": False,
            "schema": "abyss_machine_artifact_subject_materialize_v1",
            "bundle_dir": _portable_path_ref(bundle),
            "manifest_ref": str(manifest_ref) if manifest_ref else identity.get("bundle_manifest_ref"),
            "errors": errors,
            "written": [],
        }

    artifact_class = str(subjects.get("artifact_class") or identity.get("artifact_class") or manifest.get("artifact_class") or "")
    aggregate_digest = str(subjects.get("aggregate_digest") or "")
    subject_root = _subject_repo_root(manifest)
    target_dir = artifact_subject_store_dir(subjects, store_root=store_root)
    copy_plan: list[tuple[Path, Path, dict[str, Any]]] = []
    for idx, item in enumerate(subject_files):
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path") or "")
        if not path_text:
            continue
        try:
            safe_path = _safe_repo_relative_path(path_text, field=f"artifact.subjects.json files[{idx}].path")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        source = subject_root / safe_path
        if not source.is_file():
            errors.append(f"artifact subject source file is missing: {path_text}")
            continue
        expected = str(item.get("sha256") or "")
        actual = _file_digest(source)
        if expected != actual:
            errors.append(f"artifact subject source digest mismatch: {path_text}")
            continue
        copy_plan.append((source, target_dir / safe_path, item))

    if errors:
        return {
            "ok": False,
            "schema": "abyss_machine_artifact_subject_materialize_v1",
            "bundle_dir": _portable_path_ref(bundle),
            "manifest_ref": str(manifest_ref) if manifest_ref else identity.get("bundle_manifest_ref"),
            "store_dir": str(target_dir),
            "errors": errors,
            "written": [],
        }

    gate: dict[str, Any] | None = None
    gate_consumer_intent = str(consumer_intent or consumer_intent_for_artifact_class(artifact_class))
    gate_expected_source_repo = str(
        expected_source_repo or manifest.get("owner_repo") or identity.get("owner_repo") or subjects.get("owner_repo") or ""
    )
    if registry_dir is None:
        errors.append("artifact subject materialization requires registry_dir for consumer trust-gate")
    else:
        gate = trust_gate(
            registry_dir,
            artifact_class=artifact_class,
            subject_digest=aggregate_digest,
            record_id=str(record_id or ""),
            consumer_intent=gate_consumer_intent,
            expected_source_repo=gate_expected_source_repo,
            expected_trust_root_mode=str(expected_trust_root_mode or ""),
            require_latest=require_latest,
        )
        if not gate.get("ok"):
            reasons = [str(item) for item in gate.get("reasons", []) if str(item)]
            reason_text = ",".join(reasons) or str(gate.get("verdict") or "unknown")
            errors.append(f"consumer trust-gate did not allow artifact subject materialization: {reason_text}")

    if errors:
        return {
            "ok": False,
            "schema": "abyss_machine_artifact_subject_materialize_v1",
            "bundle_dir": _portable_path_ref(bundle),
            "manifest_ref": str(manifest_ref) if manifest_ref else identity.get("bundle_manifest_ref"),
            "store_dir": str(target_dir),
            "artifact_class": artifact_class,
            "aggregate_digest": aggregate_digest,
            "consumer_intent": gate_consumer_intent,
            "registry_dir": str(registry_dir) if registry_dir is not None else None,
            "trust_gate": gate,
            "errors": errors,
            "written": [],
        }

    written: list[str] = []
    for source, target, _item in copy_plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written.append(str(target))
    meta = {
        "schema": "abyss_machine_artifact_subject_store_v1",
        "bundle_layout": BUNDLE_LAYOUT,
        "artifact_class": artifact_class,
        "owner_repo": subjects.get("owner_repo"),
        "aggregate_digest": aggregate_digest,
        "path_basis": "local_host_state",
        "store_dir": str(target_dir),
        "bundle_ref": _portable_path_ref(bundle),
        "bundle_manifest_ref": identity.get("bundle_manifest_ref"),
        "source_manifest_ref": str(manifest_ref) if manifest_ref else identity.get("bundle_manifest_ref"),
        "registry_dir": str(registry_dir),
        "consumer_intent": gate_consumer_intent,
        "trust_gate_record_id": gate.get("record_id") if isinstance(gate, dict) else None,
        "trust_gate_verdict": gate.get("verdict") if isinstance(gate, dict) else None,
        "materialized_at": _utc_now(),
        "files": subject_files,
    }
    _write_json(target_dir / ARTIFACT_SUBJECT_STORE_META, meta)
    written.append(str(target_dir / ARTIFACT_SUBJECT_STORE_META))
    status = _artifact_subject_store_status(subjects, store_root=store_root)
    return {
        "ok": bool(status.get("ok")),
        "schema": "abyss_machine_artifact_subject_materialize_v1",
        "bundle_dir": _portable_path_ref(bundle),
        "manifest_ref": str(manifest_ref) if manifest_ref else identity.get("bundle_manifest_ref"),
        "store_dir": str(target_dir),
        "artifact_class": artifact_class,
        "aggregate_digest": aggregate_digest,
        "consumer_intent": gate_consumer_intent,
        "registry_dir": str(registry_dir),
        "trust_gate": gate,
        "written": written,
        "status": status,
        "errors": [] if status.get("ok") else ["materialized artifact subject store did not verify"],
    }


def _package_metadata_from_manifest(manifest: dict[str, Any] | None, subjects: dict[str, Any] | None) -> dict[str, Any]:
    package = manifest.get("package") if isinstance(manifest, dict) else None
    package = package if isinstance(package, dict) else {}
    subject_root = _subject_repo_root(manifest) if isinstance(manifest, dict) else None
    pyproject_data: dict[str, Any] = {}
    pyproject_ref = str(package.get("pyproject") or "")
    if subject_root is not None and pyproject_ref:
        _safe_repo_relative_path(pyproject_ref, field="package.pyproject")
        pyproject_path = subject_root / pyproject_ref
        if pyproject_path.is_file():
            pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject_data.get("project") if isinstance(pyproject_data.get("project"), dict) else {}
    fallback_name = manifest.get("owner_repo") if isinstance(manifest, dict) else "artifact"
    name = str(package.get("name") or project.get("name") or fallback_name)
    version = str(package.get("version") or project.get("version") or "0")
    dependencies = project.get("dependencies") if isinstance(project.get("dependencies"), list) else []
    license_value = project.get("license")
    if isinstance(license_value, dict):
        license_text = str(license_value.get("text") or "NOASSERTION")
    elif isinstance(license_value, str):
        license_text = license_value
    else:
        license_text = str(package.get("license") or "NOASSERTION")
    subject_files = subjects.get("files") if isinstance(subjects, dict) and isinstance(subjects.get("files"), list) else []
    return {
        "name": name,
        "version": version,
        "purl": str(package.get("purl") or f"pkg:pypi/{name}@{version}"),
        "ecosystem": str(package.get("ecosystem") or "python"),
        "license": license_text,
        "dependencies": [str(item) for item in dependencies],
        "subject_count": len(subject_files),
    }


def _dependency_name(requirement: str) -> str:
    for marker in (";", "[", "<", ">", "=", "~", "!"):
        requirement = requirement.split(marker, 1)[0]
    return requirement.strip()


def build_sbom_sidecars(
    *,
    manifest: dict[str, Any] | None,
    identity: dict[str, Any],
    subjects: dict[str, Any],
    policy: dict[str, Any],
    created_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package = _package_metadata_from_manifest(manifest, subjects)
    subject_files = subjects.get("files") if isinstance(subjects.get("files"), list) else []
    serial = uuid.uuid5(uuid.NAMESPACE_URL, str(subjects.get("aggregate_digest") or _stable_digest(subjects)))
    cdx_components: list[dict[str, Any]] = [
        {
            "type": "file",
            "name": str(item["path"]),
            "bom-ref": f"file:{item['path']}",
            "hashes": [{"alg": "SHA-256", "content": str(item["sha256_hex"])}],
            "properties": [{"name": "abyss:artifactRole", "value": str(item.get("role") or "artifact")}],
        }
        for item in subject_files
    ]
    for dependency in package["dependencies"]:
        dep_name = _dependency_name(dependency)
        if dep_name:
            cdx_components.append(
                {
                    "type": "library",
                    "name": dep_name,
                    "bom-ref": f"dependency:{dep_name}",
                    "properties": [{"name": "abyss:requirement", "value": dependency}],
                }
            )
    cdx = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": created_at,
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "abyss-machine",
                        "version": str(policy.get("policy_version") or "unknown"),
                    }
                ]
            },
            "component": {
                "type": "library",
                "name": package["name"],
                "version": package["version"],
                "purl": package["purl"],
                "bom-ref": package["purl"],
            },
        },
        "components": cdx_components,
        "properties": [
            {"name": "abyss:artifactClass", "value": str(identity.get("artifact_class"))},
            {"name": "abyss:policyRef", "value": POLICY_REF},
            {"name": "abyss:subjectAggregateDigest", "value": str(subjects.get("aggregate_digest"))},
        ],
    }

    spdx_packages = [
        {
            "name": package["name"],
            "SPDXID": "SPDXRef-Package",
            "versionInfo": package["version"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": package["license"],
            "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": package["purl"]}],
        }
    ]
    relationships = []
    for idx, item in enumerate(subject_files, start=1):
        spdx_id = f"SPDXRef-Artifact-{idx}"
        spdx_packages.append(
            {
                "name": str(item["path"]),
                "SPDXID": spdx_id,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "checksums": [{"algorithm": "SHA256", "checksumValue": str(item["sha256_hex"])}],
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": spdx_id,
            }
        )
    spdx = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{package['name']}-{package['version']}-sbom",
        "documentNamespace": f"https://abyss.local/spdx/{serial}",
        "creationInfo": {
            "created": created_at,
            "creators": ["Tool: abyss-machine"],
        },
        "packages": spdx_packages,
        "relationships": relationships,
    }
    return cdx, spdx


def build_ml_bom_sidecar(
    *,
    manifest: dict[str, Any] | None,
    identity: dict[str, Any],
    subjects: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    ml_bom = manifest.get("ml_bom") if isinstance(manifest, dict) else None
    if not isinstance(ml_bom, dict):
        raise ValueError("ml_bom is required in the bundle manifest when policy requires ML-BOM")
    subject_by_path = {
        str(item.get("path")): item
        for item in subjects.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }
    subject_by_role = {
        str(item.get("role")): item
        for item in subjects.get("files", [])
        if isinstance(item, dict) and item.get("role")
    }
    not_applicable = ml_bom.get("not_applicable") if isinstance(ml_bom.get("not_applicable"), dict) else {}
    components: list[dict[str, Any]] = []
    type_by_category = {
        "models": "machine-learning-model",
        "datasets": "data",
        "conversions": "application",
        "framework_configs": "configuration",
    }
    for category in ML_BOM_CATEGORIES:
        entries = ml_bom.get(category)
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            raise ValueError(f"ml_bom.{category} must be a list")
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValueError(f"ml_bom.{category}[{idx}] must be an object")
            name = str(entry.get("name") or entry.get("path") or f"{category}-{idx + 1}")
            version = str(entry.get("version") or "0")
            component: dict[str, Any] = {
                "type": str(entry.get("type") or type_by_category[category]),
                "name": name,
                "version": version,
                "bom-ref": str(entry.get("bom_ref") or f"ml-bom:{category}:{name}"),
                "properties": [
                    {"name": "abyss.ml_bom.category", "value": category},
                    {"name": "abyss.ml_bom.role", "value": str(entry.get("role") or category.rstrip("s"))},
                    {"name": "abyss.ml_bom.included", "value": str(bool(entry.get("included", True))).lower()},
                ],
            }
            subject_path = str(entry.get("subject_path") or "")
            subject_role = str(entry.get("subject_role") or "")
            if not subject_path and subject_role and subject_role in subject_by_role:
                subject_path = str(subject_by_role[subject_role].get("path") or "")
            digest = str(entry.get("sha256") or "")
            if subject_path and subject_path in subject_by_path:
                subject = subject_by_path[subject_path]
                digest = str(subject.get("sha256") or "")
                component["properties"].append({"name": "abyss.ml_bom.subject_path", "value": subject_path})
                component["properties"].append({"name": "abyss.ml_bom.subject_digest", "value": digest})
            if digest.startswith("sha256:"):
                component["hashes"] = [{"alg": "SHA-256", "content": digest.removeprefix("sha256:")}]
            for field in ("source_ref", "license", "framework", "format", "precision", "device", "notes"):
                if entry.get(field) is not None:
                    component["properties"].append({"name": f"abyss.ml_bom.{field}", "value": str(entry[field])})
            components.append(component)

    metadata_properties = [
        {"name": "abyss:artifactClass", "value": str(identity.get("artifact_class"))},
        {"name": "abyss:subjectAggregateDigest", "value": str(subjects.get("aggregate_digest"))},
        {"name": "abyss.ml_bom.scope", "value": str(ml_bom.get("scope") or "ai_runtime_bundle")},
    ]
    for category in ML_BOM_CATEGORIES:
        reason = str(not_applicable.get(category) or "")
        if reason:
            metadata_properties.append({"name": f"abyss.ml_bom.{category}.not_applicable", "value": reason})

    serial = uuid.uuid5(uuid.NAMESPACE_URL, "ml-bom:" + str(subjects.get("aggregate_digest") or _stable_digest(subjects)))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": created_at,
            "component": {
                "type": "application",
                "name": str(ml_bom.get("name") or identity.get("artifact_class") or "ai-runtime-bundle"),
                "version": str(ml_bom.get("version") or "0"),
                "bom-ref": str(ml_bom.get("bom_ref") or "ml-bom:bundle"),
            },
            "properties": metadata_properties,
        },
        "components": components,
        "properties": [
            {"name": "abyss:policyRef", "value": POLICY_REF},
            {"name": "abyss:bundleLayout", "value": BUNDLE_LAYOUT},
        ],
    }


def build_slsa_statement(
    *,
    manifest: dict[str, Any] | None,
    identity: dict[str, Any],
    subjects: dict[str, Any],
    created_at: str,
    producer_command: str,
) -> dict[str, Any]:
    subject_files = subjects.get("files") if isinstance(subjects.get("files"), list) else []
    source_refs = [POLICY_REF]
    build_type = "https://abyssos.local/buildtypes/python-distribution/v1"
    if isinstance(manifest, dict):
        source_refs.append(str(_public_manifest_ref(manifest) or ""))
        if manifest.get("build_type"):
            build_type = str(manifest["build_type"])
    aggregate_digest = str(subjects.get("aggregate_digest") or "").removeprefix("sha256:")
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": str(item["path"]), "digest": {"sha256": str(item["sha256_hex"])}}
            for item in subject_files
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": build_type,
                "externalParameters": {
                    "artifact_class": identity.get("artifact_class"),
                    "mode": identity.get("mode"),
                    "producer_command": producer_command,
                    "bundle_manifest_ref": identity.get("bundle_manifest_ref"),
                },
                "internalParameters": {},
                "resolvedDependencies": [
                    {"uri": ref, "digest": {}} for ref in source_refs if ref
                ],
            },
            "runDetails": {
                "builder": {"id": "https://abyssos.local/builders/abyss-machine-artifacts"},
                "metadata": {
                    "invocationId": str(subjects.get("aggregate_digest")),
                    "startedOn": created_at,
                    "finishedOn": created_at,
                },
                "byproducts": [
                    {"name": SUBJECTS_SIDECAR, "digest": {"sha256": aggregate_digest}}
                ],
            },
        },
    }


def build_sidecars(
    bundle_dir: str | Path,
    *,
    artifact_class: str = "public_source_seed",
    contract_surface_id: str | None = None,
    manifest_ref: str | Path | None = None,
    mode: str = "os_abyss_local",
    repo_root: Path = REPO_ROOT,
    producer_command: str = "abyss-machine artifacts build-sidecars",
) -> dict[str, Any]:
    manifest: dict[str, Any] | None = None
    if manifest_ref:
        manifest = load_bundle_manifest(manifest_ref, repo_root=repo_root)
        artifact_class = str(manifest["artifact_class"])
        contract_surface_id = str(manifest.get("contract_surface_id") or contract_surface_id or "") or None
        mode = str(manifest.get("mode") or mode)
    policy = load_policy(repo_root)
    rule = artifact_class_rule(artifact_class, repo_root=repo_root)
    required = required_controls_for_rule(rule)
    deferred = deferred_controls_for_rule(rule)
    artifact_subjects = build_artifact_subjects(manifest)
    if any(control in required for control in ("sbom", "slsa_in_toto", "sigstore_cosign", "c2pa")) and artifact_subjects is None:
        raise ValueError(f"{artifact_class} requires artifact_subjects in the bundle manifest")
    surface: dict[str, Any] | None = None
    external_subject: dict[str, Any] | None = None
    if "abi_signature" in required:
        try:
            surface = contract_surface_for_class(artifact_class, contract_surface_id=contract_surface_id, repo_root=repo_root)
        except ValueError:
            if manifest is None:
                raise
            external_subject = build_external_abi_subject(manifest)
            if external_subject is None:
                raise
    bundle = Path(bundle_dir)
    bundle.mkdir(parents=True, exist_ok=True)
    bundle_manifest_public_ref = _public_manifest_ref(manifest, manifest_ref)

    identity = dict(rule["identity"])
    identity.update(
        {
            "schema": "abyss_machine_artifact_identity_sidecar_v1",
            "bundle_layout": BUNDLE_LAYOUT,
            "policy_ref": POLICY_REF,
            "policy_version": policy.get("policy_version"),
            "bundle_manifest_ref": bundle_manifest_public_ref,
            "contract_surface_id": surface.get("id") if surface else None,
            "mode": mode,
            "required_controls": required,
            "deferred_controls": deferred,
        }
    )
    source_refs = [POLICY_REF]
    if surface:
        source_refs.append(ABI_REF)
    if external_subject:
        source_refs.append(str(external_subject.get("path")))
    if bundle_manifest_public_ref:
        source_refs.append(bundle_manifest_public_ref)
    if surface:
        source_refs.extend(str(item) for item in surface.get("source_paths", []))
    created_at = _utc_now()
    provenance = {
        "schema": "abyss_machine_minimal_provenance_v1",
        "bundle_layout": BUNDLE_LAYOUT,
        "artifact_class": artifact_class,
        "mode": mode,
        "activity": "build_artifact_bundle_sidecars",
        "agent_or_tool": "abyss-machine",
        "producer_command": producer_command,
        "created_at": created_at,
        "source_refs": source_refs,
        "subject": {
            "contract_surface_id": surface.get("id") if surface else None,
            "digest": (
                surface.get("source_tree_hash")
                if surface
                else external_subject.get("sha256")
                if external_subject
                else _stable_digest(identity)
            ),
            "digest_algorithm": surface.get("hash_algorithm") if surface else "sha256",
        },
        "privacy_boundary": identity.get("privacy_boundary"),
        "public_repo_content": artifact_class != "host_local_evidence",
        "not_slsa_release_provenance": "minimal OS Abyss bundle provenance; SLSA/in-toto is required only when policy triggers a publishable release artifact",
    }
    if artifact_subjects is not None:
        provenance["artifact_subjects_ref"] = SUBJECTS_SIDECAR
        provenance["artifact_subjects_digest"] = artifact_subjects.get("aggregate_digest")

    written = [IDENTITY_SIDECAR, PROVENANCE_SIDECAR]
    _write_json(bundle / IDENTITY_SIDECAR, identity)
    if surface or external_subject:
        abi_sidecar = {
            "schema": "abyss_machine_artifact_abi_sidecar_v1",
            "bundle_layout": BUNDLE_LAYOUT,
            "artifact_class": artifact_class,
            "policy_ref": POLICY_REF,
            "abi_ref": ABI_REF,
        }
        if surface:
            abi_sidecar["contract_surface"] = surface
        if external_subject:
            abi_sidecar["external_subject"] = external_subject
        _write_json(bundle / ABI_SIDECAR, abi_sidecar)
        written.append(ABI_SIDECAR)
    _write_json(bundle / PROVENANCE_SIDECAR, provenance)
    if artifact_subjects is not None:
        _write_json(bundle / SUBJECTS_SIDECAR, artifact_subjects)
        written.append(SUBJECTS_SIDECAR)
    if "sbom" in required:
        cdx, spdx = build_sbom_sidecars(
            manifest=manifest,
            identity=identity,
            subjects=artifact_subjects or {},
            policy=policy,
            created_at=created_at,
        )
        _write_json(bundle / SBOM_CYCLONEDX_SIDECAR, cdx)
        _write_json(bundle / SBOM_SPDX_SIDECAR, spdx)
        written.extend([SBOM_CYCLONEDX_SIDECAR, SBOM_SPDX_SIDECAR])
    if "ml_bom" in required:
        ml_bom = build_ml_bom_sidecar(
            manifest=manifest,
            identity=identity,
            subjects=artifact_subjects or {},
            created_at=created_at,
        )
        _write_json(bundle / MLBOM_CYCLONEDX_SIDECAR, ml_bom)
        written.append(MLBOM_CYCLONEDX_SIDECAR)
    if "slsa_in_toto" in required:
        statement = build_slsa_statement(
            manifest=manifest,
            identity=identity,
            subjects=artifact_subjects or {},
            created_at=created_at,
            producer_command=producer_command,
        )
        (bundle / SLSA_INTOTO_SIDECAR).write_text(
            json.dumps(statement, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(SLSA_INTOTO_SIDECAR)
    if "local_provenance" in required:
        local_packet = build_local_provenance_packet(
            identity,
            policy=policy,
            manifest=manifest,
            producer_command=producer_command,
        )
        _write_json(bundle / LOCAL_PROVENANCE_SIDECAR, local_packet)
        written.append(LOCAL_PROVENANCE_SIDECAR)
    return {
        "ok": True,
        "schema": "abyss_machine_artifact_bundle_build_v1",
        "bundle_dir": str(bundle),
        "artifact_class": artifact_class,
        "bundle_manifest_ref": str(manifest_ref) if manifest_ref else None,
        "contract_surface_id": surface.get("id") if surface else None,
        "written": written,
        "required_controls": required,
        "deferred_controls": deferred,
    }


def build_sidecars_from_manifest(
    bundle_dir: str | Path,
    manifest_ref: str | Path = DEFAULT_BUNDLE_MANIFEST_REF,
    *,
    repo_root: Path = REPO_ROOT,
    producer_command: str = "abyss-machine artifacts build-sidecars",
) -> dict[str, Any]:
    return build_sidecars(
        bundle_dir,
        manifest_ref=manifest_ref,
        repo_root=repo_root,
        producer_command=producer_command,
    )


def _signature_subject_path(bundle: Path) -> Path:
    for sidecar in (SUBJECTS_SIDECAR, ABI_SIDECAR, LOCAL_PROVENANCE_SIDECAR, IDENTITY_SIDECAR):
        candidate = bundle / sidecar
        if candidate.is_file():
            return candidate
    return bundle / IDENTITY_SIDECAR


def _cosign_binary() -> str | None:
    env_binary = os.environ.get("ABYSS_MACHINE_COSIGN_BINARY")
    if env_binary:
        return env_binary
    managed_binary = Path("/srv/abyss-machine/runtimes/artifact-trust/bin/cosign")
    if managed_binary.is_file() and os.access(managed_binary, os.X_OK):
        return str(managed_binary)
    return shutil.which("cosign")


def _c2patool_binary() -> str | None:
    env_binary = os.environ.get("ABYSS_MACHINE_C2PATOOL_BINARY")
    if env_binary:
        return env_binary
    managed_binary = Path("/srv/abyss-machine/runtimes/artifact-trust/bin/c2patool")
    if managed_binary.is_file() and os.access(managed_binary, os.X_OK):
        return str(managed_binary)
    return shutil.which("c2patool")


def _resolved_artifact_subject_paths(
    *,
    bundle: Path,
    identity: dict[str, Any],
    subjects: dict[str, Any],
    repo_root: Path,
) -> list[tuple[str, Path, str]]:
    resolved: list[tuple[str, Path, str]] = []
    subject_files = subjects.get("files") if isinstance(subjects.get("files"), list) else []
    if not subject_files:
        return resolved
    manifest = _bundle_manifest_for_identity(identity, repo_root=repo_root)
    subject_root = _subject_repo_root(manifest) if manifest else None
    for idx, item in enumerate(subject_files):
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path") or "")
        if not path_text:
            continue
        expected = str(item.get("sha256") or "")
        try:
            safe_path = _safe_repo_relative_path(path_text, field=f"artifact.subjects.json files[{idx}].path")
        except ValueError:
            continue
        if subject_root is not None:
            subject_path = subject_root / safe_path
            if subject_path.is_file():
                resolved.append((path_text, subject_path, expected))
                continue
        adjacent_path = bundle.parent / safe_path
        if adjacent_path.is_file():
            resolved.append((path_text, adjacent_path, expected))
            continue
        for store_root in _artifact_subject_store_roots():
            try:
                store_dir = artifact_subject_store_dir(subjects, store_root=store_root)
            except ValueError:
                continue
            store_path = store_dir / safe_path
            if store_path.is_file():
                resolved.append((path_text, store_path, expected))
                break
    return resolved


def _cosign_claim_limits(*, backend: str) -> list[str]:
    return [
        "The signed blob is the bundle subject manifest, not a keyless public transparency-log release proof.",
        "Consumers must compare the release artifact digest against artifact.subjects.json before trusting the artifact.",
        f"{backend} proves possession of the configured local Cosign key at signing time; it does not prove Fulcio/Rekor identity.",
    ]


def _missing_cosign_backend_decision(
    *,
    artifact_class: str,
    backend: str,
    reason: str,
    required: bool,
    subject_path: Path,
) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "ok": False,
        "schema": "abyss_machine_artifact_signature_decision_v1",
        "artifact_class": artifact_class,
        "backend": backend,
        "status": "missing_backend",
        "required": required,
        "reason": reason,
        "claim_limits": _cosign_claim_limits(backend=backend),
    }
    if subject_path.is_file():
        decision["subject_ref"] = subject_path.name
        decision["subject_digest"] = _file_digest(subject_path)
    return decision


def sign_bundle(
    bundle_dir: str | Path,
    *,
    backend: str = "policy-decision",
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    identity = _read_json(bundle / IDENTITY_SIDECAR)
    artifact_class = str(identity.get("artifact_class") or "")
    rule = artifact_class_rule(artifact_class, repo_root=repo_root)
    sigstore_rule = rule.get("sigstore_cosign") if isinstance(rule.get("sigstore_cosign"), dict) else {}
    required = sigstore_rule.get("required") is True
    subject_path = _signature_subject_path(bundle)
    if required:
        if backend != "cosign-local-key":
            decision = _missing_cosign_backend_decision(
                artifact_class=artifact_class,
                backend=backend,
                reason="sigstore_cosign is required by policy; use backend=cosign-local-key with configured local key material",
                required=True,
                subject_path=subject_path,
            )
            _write_json(bundle / SIGNATURE_DECISION_SIDECAR, decision)
            return {
                **decision,
                "bundle_dir": str(bundle),
                "written": [SIGNATURE_DECISION_SIDECAR],
            }
        cosign = _cosign_binary()
        key_path = Path(os.environ.get("ABYSS_MACHINE_COSIGN_KEY") or "")
        public_key_path = Path(os.environ.get("ABYSS_MACHINE_COSIGN_PUB") or "")
        if not cosign or not key_path.is_file() or not public_key_path.is_file() or not subject_path.is_file():
            missing_parts = []
            if not cosign:
                missing_parts.append("cosign binary")
            if not key_path.is_file():
                missing_parts.append("ABYSS_MACHINE_COSIGN_KEY file")
            if not public_key_path.is_file():
                missing_parts.append("ABYSS_MACHINE_COSIGN_PUB file")
            if not subject_path.is_file():
                missing_parts.append("signature subject sidecar")
            decision = _missing_cosign_backend_decision(
                artifact_class=artifact_class,
                backend=backend,
                reason="missing required Cosign signing input: " + ", ".join(missing_parts),
                required=True,
                subject_path=subject_path,
            )
            _write_json(bundle / SIGNATURE_DECISION_SIDECAR, decision)
            return {
                **decision,
                "bundle_dir": str(bundle),
                "written": [SIGNATURE_DECISION_SIDECAR],
            }
        sigstore_bundle_path = bundle / SIGSTORE_BUNDLE_SIDECAR
        signature_path = bundle / COSIGN_SIGNATURE_SIDECAR
        public_key_sidecar_path = bundle / COSIGN_PUBLIC_KEY_SIDECAR
        proc = subprocess.run(
            [
                cosign,
                "sign-blob",
                "--yes",
                "--key",
                str(key_path),
                "--bundle",
                str(sigstore_bundle_path),
                str(subject_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        if proc.returncode != 0 or not sigstore_bundle_path.is_file():
            decision = {
                "ok": False,
                "schema": "abyss_machine_artifact_signature_decision_v1",
                "artifact_class": artifact_class,
                "backend": backend,
                "status": "signing_failed",
                "required": True,
                "reason": "cosign sign-blob failed or did not produce artifact.sigstore.json",
                "cosign_exit_code": proc.returncode,
                "subject_ref": subject_path.name,
                "subject_digest": _file_digest(subject_path),
                "claim_limits": _cosign_claim_limits(backend=backend),
            }
            _write_json(bundle / SIGNATURE_DECISION_SIDECAR, decision)
            return {
                **decision,
                "bundle_dir": str(bundle),
                "written": [SIGNATURE_DECISION_SIDECAR],
            }
        signature_path.write_text(proc.stdout.strip() + "\n", encoding="utf-8")
        shutil.copyfile(public_key_path, public_key_sidecar_path)
        decision = {
            "ok": True,
            "schema": "abyss_machine_artifact_signature_decision_v1",
            "artifact_class": artifact_class,
            "backend": backend,
            "status": "signed",
            "required": True,
            "reason": "sigstore_cosign is required by policy and was signed with a configured local Cosign key",
            "subject_ref": subject_path.name,
            "subject_digest": _file_digest(subject_path),
            "signature_scope": "bundle_subject_manifest",
            "signature_ref": COSIGN_SIGNATURE_SIDECAR,
            "sigstore_bundle_ref": SIGSTORE_BUNDLE_SIDECAR,
            "public_key_ref": COSIGN_PUBLIC_KEY_SIDECAR,
            "claim_limits": _cosign_claim_limits(backend=backend),
        }
        _write_json(bundle / SIGNATURE_DECISION_SIDECAR, decision)
        return {
            **decision,
            "bundle_dir": str(bundle),
            "written": [
                SIGNATURE_DECISION_SIDECAR,
                COSIGN_SIGNATURE_SIDECAR,
                SIGSTORE_BUNDLE_SIDECAR,
                COSIGN_PUBLIC_KEY_SIDECAR,
            ],
        }
    else:
        decision = {
            "ok": True,
            "schema": "abyss_machine_artifact_signature_decision_v1",
            "artifact_class": artifact_class,
            "backend": backend,
            "status": "not_required",
            "required": False,
            "reason": str(sigstore_rule.get("trigger") or "sigstore/cosign is not required for this artifact class"),
            "subject_ref": subject_path.name,
            "subject_digest": _file_digest(subject_path),
        }
    _write_json(bundle / SIGNATURE_DECISION_SIDECAR, decision)
    return {
        **decision,
        "bundle_dir": str(bundle),
        "written": [SIGNATURE_DECISION_SIDECAR],
    }


def _has_any(bundle: Path, names: list[str]) -> bool:
    return any((bundle / name).exists() for name in names)


def _validate_local_provenance_packet(
    packet: dict[str, Any],
    identity: dict[str, Any],
    policy: dict[str, Any],
    errors: list[str],
) -> None:
    packet_contract = policy.get("local_provenance_packet")
    if not isinstance(packet_contract, dict):
        errors.append("artifact signature policy must define local_provenance_packet")
        return
    required_fields = packet_contract.get("required_fields")
    if isinstance(required_fields, list):
        for field in required_fields:
            if field not in packet:
                errors.append(f"artifact.local-provenance.json missing required field: {field}")

    expected_pairs = {
        "schema": packet_contract.get("schema"),
        "schema_ref": packet_contract.get("schema_ref"),
        "artifact_class": "host_local_evidence",
        "surface_state": identity.get("surface_state"),
        "owner_repo": identity.get("owner_repo"),
        "contract_version": identity.get("contract_version"),
        "privacy_boundary": identity.get("privacy_boundary"),
    }
    for key, expected in expected_pairs.items():
        if packet.get(key) != expected:
            errors.append(f"artifact.local-provenance.json {key} does not match policy or identity")

    if packet.get("not_public_repo_content") is not True:
        errors.append("artifact.local-provenance.json must mark not_public_repo_content=true")
    if "private" not in str(packet.get("privacy_boundary") or "").lower():
        errors.append("artifact.local-provenance.json must keep a private privacy boundary")
    content_identity = packet.get("content_identity")
    if not isinstance(content_identity, dict):
        errors.append("artifact.local-provenance.json content_identity must be an object")
        return
    path = str(content_identity.get("path") or "")
    if not path.startswith("/var/lib/abyss-machine"):
        errors.append("artifact.local-provenance.json content_identity.path must stay under /var/lib/abyss-machine")
    if not (content_identity.get("sha256") or content_identity.get("tree_hash")):
        errors.append("artifact.local-provenance.json content_identity must include sha256 or tree_hash")
    for key in ("source_refs", "verification"):
        value = packet.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            errors.append(f"artifact.local-provenance.json {key} must be a non-empty string list")


def _subject_digest_hexes(subjects: dict[str, Any], errors: list[str]) -> set[str]:
    files = subjects.get("files")
    if not isinstance(files, list) or not files:
        errors.append("artifact.subjects.json must define non-empty files")
        return set()
    digests: set[str] = set()
    for idx, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"artifact.subjects.json files[{idx}] must be an object")
            continue
        path = item.get("path")
        digest = str(item.get("sha256_hex") or str(item.get("sha256") or "").removeprefix("sha256:"))
        if not isinstance(path, str) or not path:
            errors.append(f"artifact.subjects.json files[{idx}] must define path")
        if len(digest) != 64:
            errors.append(f"artifact.subjects.json files[{idx}] must define sha256")
        else:
            digests.add(digest)
    return digests


def _validate_sbom_sidecars(bundle: Path, subjects: dict[str, Any], errors: list[str]) -> None:
    expected = _subject_digest_hexes(subjects, errors)
    if not expected:
        return
    seen: set[str] = set()
    cdx_path = bundle / SBOM_CYCLONEDX_SIDECAR
    if cdx_path.is_file():
        cdx = _read_json(cdx_path)
        if cdx.get("bomFormat") != "CycloneDX":
            errors.append("artifact.sbom.cdx.json bomFormat must be CycloneDX")
        if not cdx.get("specVersion"):
            errors.append("artifact.sbom.cdx.json must define specVersion")
        components = cdx.get("components")
        if not isinstance(components, list):
            errors.append("artifact.sbom.cdx.json must define components")
        else:
            for component in components:
                if not isinstance(component, dict):
                    continue
                for digest in component.get("hashes", []) if isinstance(component.get("hashes"), list) else []:
                    if isinstance(digest, dict) and str(digest.get("alg") or "").upper() == "SHA-256":
                        seen.add(str(digest.get("content") or ""))
    spdx_path = bundle / SBOM_SPDX_SIDECAR
    if spdx_path.is_file():
        spdx = _read_json(spdx_path)
        if not str(spdx.get("spdxVersion") or "").startswith("SPDX-"):
            errors.append("artifact.sbom.spdx.json must define spdxVersion")
        packages = spdx.get("packages")
        if not isinstance(packages, list):
            errors.append("artifact.sbom.spdx.json must define packages")
        else:
            for package in packages:
                if not isinstance(package, dict):
                    continue
                for checksum in package.get("checksums", []) if isinstance(package.get("checksums"), list) else []:
                    if isinstance(checksum, dict) and str(checksum.get("algorithm") or "").upper() == "SHA256":
                        seen.add(str(checksum.get("checksumValue") or ""))
    missing = sorted(expected - seen)
    if missing:
        errors.append("SBOM sidecars do not cover artifact subject digests: " + ", ".join(missing))


def _component_properties(component: dict[str, Any]) -> dict[str, str]:
    properties: dict[str, str] = {}
    for item in component.get("properties", []) if isinstance(component.get("properties"), list) else []:
        if isinstance(item, dict) and item.get("name") is not None:
            properties[str(item["name"])] = str(item.get("value") or "")
    return properties


def _validate_ml_bom_sidecar(bundle: Path, subjects: dict[str, Any], errors: list[str]) -> None:
    path = bundle / MLBOM_CYCLONEDX_SIDECAR
    if not path.is_file():
        return
    cdx = _read_json(path)
    if cdx.get("bomFormat") != "CycloneDX":
        errors.append(f"{MLBOM_CYCLONEDX_SIDECAR} bomFormat must be CycloneDX")
    if not cdx.get("specVersion"):
        errors.append(f"{MLBOM_CYCLONEDX_SIDECAR} must define specVersion")
    components = cdx.get("components")
    if not isinstance(components, list):
        errors.append(f"{MLBOM_CYCLONEDX_SIDECAR} must define components")
        return
    seen_categories: set[str] = set()
    seen_hashes: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            continue
        properties = _component_properties(component)
        category = properties.get("abyss.ml_bom.category")
        if category:
            seen_categories.add(category)
        for digest in component.get("hashes", []) if isinstance(component.get("hashes"), list) else []:
            if isinstance(digest, dict) and str(digest.get("alg") or "").upper() == "SHA-256":
                seen_hashes.add(str(digest.get("content") or ""))
    metadata = cdx.get("metadata") if isinstance(cdx.get("metadata"), dict) else {}
    metadata_properties = _component_properties(metadata)
    for category in ML_BOM_CATEGORIES:
        if category in seen_categories:
            continue
        if not metadata_properties.get(f"abyss.ml_bom.{category}.not_applicable"):
            errors.append(f"{MLBOM_CYCLONEDX_SIDECAR} lacks {category} identity or not-applicable reason")
    expected = _subject_digest_hexes(subjects, errors)
    if expected and not expected.intersection(seen_hashes):
        errors.append(f"{MLBOM_CYCLONEDX_SIDECAR} does not cover any artifact subject digest")


def _load_slsa_statement(bundle: Path) -> dict[str, Any]:
    path = bundle / SLSA_INTOTO_SIDECAR
    if not path.is_file():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{SLSA_INTOTO_SIDECAR} must contain JSON objects")
            return payload
    return {}


def _validate_slsa_sidecar(bundle: Path, subjects: dict[str, Any], errors: list[str]) -> None:
    expected = _subject_digest_hexes(subjects, errors)
    if not expected:
        return
    statement = _load_slsa_statement(bundle)
    if not statement:
        errors.append(f"{SLSA_INTOTO_SIDECAR} must contain an in-toto statement")
        return
    if statement.get("_type") != "https://in-toto.io/Statement/v1":
        errors.append(f"{SLSA_INTOTO_SIDECAR} _type must be https://in-toto.io/Statement/v1")
    if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
        errors.append(f"{SLSA_INTOTO_SIDECAR} predicateType must be https://slsa.dev/provenance/v1")
    predicate = statement.get("predicate") if isinstance(statement.get("predicate"), dict) else {}
    build_definition = predicate.get("buildDefinition") if isinstance(predicate.get("buildDefinition"), dict) else {}
    run_details = predicate.get("runDetails") if isinstance(predicate.get("runDetails"), dict) else {}
    if not build_definition.get("buildType"):
        errors.append(f"{SLSA_INTOTO_SIDECAR} predicate.buildDefinition.buildType is required")
    builder = run_details.get("builder") if isinstance(run_details.get("builder"), dict) else {}
    if not builder.get("id"):
        errors.append(f"{SLSA_INTOTO_SIDECAR} predicate.runDetails.builder.id is required")
    seen: set[str] = set()
    for subject in statement.get("subject", []) if isinstance(statement.get("subject"), list) else []:
        if not isinstance(subject, dict):
            continue
        digest = subject.get("digest") if isinstance(subject.get("digest"), dict) else {}
        if digest.get("sha256"):
            seen.add(str(digest["sha256"]))
    missing = sorted(expected - seen)
    if missing:
        errors.append("SLSA/in-toto sidecar does not cover artifact subject digests: " + ", ".join(missing))


def _validate_artifact_subject_files(
    *,
    identity: dict[str, Any],
    subjects: dict[str, Any],
    repo_root: Path,
    errors: list[str],
    resolutions: list[dict[str, Any]],
) -> None:
    subject_files = subjects.get("files") if isinstance(subjects.get("files"), list) else []
    if not subject_files:
        return
    manifest = _bundle_manifest_for_identity(identity, repo_root=repo_root)
    subject_root = _subject_repo_root(manifest) if manifest else None
    for idx, item in enumerate(subject_files):
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path") or "")
        if not path_text:
            continue
        try:
            safe_path = _safe_repo_relative_path(path_text, field=f"artifact.subjects.json files[{idx}].path")
        except ValueError as exc:
            errors.append(str(exc))
            continue
        expected = str(item.get("sha256") or "")
        if subject_root is not None:
            subject_path = subject_root / safe_path
            if subject_path.is_file():
                actual = _file_digest(subject_path)
                ok = expected == actual
                resolutions.append(
                    {
                        "path": path_text,
                        "source": "manifest_subject_root",
                        "resolved_path": _portable_path_ref(subject_path),
                        "ok": ok,
                    }
                )
                if not ok:
                    errors.append(f"artifact subject file digest mismatch: {path_text}")
                continue

        store_error = ""
        for store_root in _artifact_subject_store_roots():
            try:
                store_dir = artifact_subject_store_dir(subjects, store_root=store_root)
            except ValueError as exc:
                store_error = str(exc)
                continue
            store_path = store_dir / safe_path
            if not store_path.is_file():
                continue
            actual = _file_digest(store_path)
            ok = expected == actual
            resolutions.append(
                {
                    "path": path_text,
                    "source": "artifact_subject_store",
                    "resolved_path": _portable_path_ref(store_path),
                    "ok": ok,
                }
            )
            if not ok:
                errors.append(f"artifact subject store digest mismatch: {path_text}")
            break
        else:
            if store_error:
                errors.append(store_error)
            if subject_root is None:
                resolutions.append(
                    {
                        "path": path_text,
                        "source": "bundle_manifest_unresolved",
                        "ok": True,
                        "checked": False,
                    }
                )
                continue
            errors.append(f"artifact subject file is missing: {path_text}")
            resolutions.append({"path": path_text, "source": "unresolved", "ok": False})


def _validate_c2pa_sidecar(
    *,
    bundle: Path,
    identity: dict[str, Any],
    subjects: dict[str, Any],
    repo_root: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    c2patool = _c2patool_binary()
    if not c2patool:
        errors.append("c2patool binary not found for required C2PA verification")
        return
    subject_paths = _resolved_artifact_subject_paths(
        bundle=bundle,
        identity=identity,
        subjects=subjects,
        repo_root=repo_root,
    )
    if not subject_paths:
        errors.append("C2PA verification requires a resolvable artifact subject")
        return
    if len(subject_paths) > 1:
        errors.append("C2PA verification currently requires exactly one artifact subject")
        return

    subject_ref, subject_path, expected_digest = subject_paths[0]
    if expected_digest and _file_digest(subject_path) != expected_digest:
        errors.append(f"artifact subject digest mismatch before C2PA verification: {subject_ref}")
        return
    command = [c2patool, str(subject_path)]
    sidecar = bundle / C2PA_MANIFEST_SIDECAR
    if sidecar.is_file():
        command.extend(["--external-manifest", str(sidecar)])
    proc = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=os.environ.copy(),
    )
    if not proc.stdout.strip():
        errors.append(f"c2patool produced no JSON report for {subject_ref}")
        if proc.stderr.strip():
            errors.append(proc.stderr.strip().splitlines()[-1][:240])
        return
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"c2patool report is not valid JSON for {subject_ref}: {exc}")
        return
    if not isinstance(report, dict):
        errors.append(f"c2patool report must be a JSON object for {subject_ref}")
        return
    state = str(report.get("validation_state") or "")
    if state != "Valid":
        errors.append(f"C2PA validation_state is not Valid for {subject_ref}: {state or 'missing'}")
    statuses = report.get("validation_status") if isinstance(report.get("validation_status"), list) else []
    status_codes = [str(item.get("code") or "") for item in statuses if isinstance(item, dict)]
    if any(code == "assertion.dataHash.mismatch" for code in status_codes):
        errors.append(f"C2PA asset hash mismatch for {subject_ref}")
    if any(code == "signingCredential.untrusted" for code in status_codes):
        warnings.append("C2PA signing credential is untrusted; this is local integrity evidence, not production trust-list proof")
    report_path = bundle / C2PA_REPORT_SIDECAR
    if report_path.is_file():
        try:
            recorded = _read_json(report_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{C2PA_REPORT_SIDECAR} must contain a JSON object: {exc}")
            return
        recorded_state = str(recorded.get("validation_state") or "")
        if recorded_state and recorded_state != state:
            errors.append(f"{C2PA_REPORT_SIDECAR} validation_state does not match c2patool output")


def _validate_cosign_signature(
    bundle: Path,
    signature: dict[str, Any],
    missing: list[str],
    errors: list[str],
) -> None:
    if signature.get("required") is not True:
        return
    if signature.get("status") != "signed" or signature.get("ok") is not True:
        errors.append("required cryptographic signature must use status=signed and ok=true")
        return
    subject_ref = str(signature.get("subject_ref") or "")
    if not subject_ref:
        errors.append("artifact.signature-decision.json signed signature must define subject_ref")
        return
    subject_rel = Path(subject_ref)
    if subject_rel.is_absolute() or ".." in subject_rel.parts:
        errors.append("artifact.signature-decision.json subject_ref must be a safe bundle-relative path")
        return
    subject_path = bundle / subject_rel
    if not subject_path.is_file():
        missing.append(subject_ref)
        return
    expected_digest = str(signature.get("subject_digest") or "")
    actual_digest = _file_digest(subject_path)
    if expected_digest != actual_digest:
        errors.append(f"artifact.signature-decision.json subject_digest does not match {subject_ref}")

    required_sidecars = {
        "signature_ref": COSIGN_SIGNATURE_SIDECAR,
        "sigstore_bundle_ref": SIGSTORE_BUNDLE_SIDECAR,
        "public_key_ref": COSIGN_PUBLIC_KEY_SIDECAR,
    }
    sidecar_paths: dict[str, Path] = {}
    for field, default_ref in required_sidecars.items():
        ref = str(signature.get(field) or default_ref)
        rel = Path(ref)
        if rel.is_absolute() or ".." in rel.parts:
            errors.append(f"artifact.signature-decision.json {field} must be a safe bundle-relative path")
            continue
        path = bundle / rel
        sidecar_paths[field] = path
        if not path.is_file():
            missing.append(ref)
    if any(not path.is_file() for path in sidecar_paths.values()):
        return

    cosign = _cosign_binary()
    if not cosign:
        errors.append("cosign binary not found for required sigstore_cosign verification")
        return
    proc = subprocess.run(
        [
            cosign,
            "verify-blob",
            "--key",
            str(sidecar_paths["public_key_ref"]),
            "--bundle",
            str(sidecar_paths["sigstore_bundle_ref"]),
            str(subject_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        errors.append("cosign verify-blob failed for required sigstore_cosign signature")


def verify_bundle(bundle_dir: str | Path, *, repo_root: Path = REPO_ROOT, write: bool = True) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    missing: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    for sidecar in (IDENTITY_SIDECAR, PROVENANCE_SIDECAR, SIGNATURE_DECISION_SIDECAR):
        if not (bundle / sidecar).is_file():
            missing.append(sidecar)
    identity = _read_json(bundle / IDENTITY_SIDECAR) if (bundle / IDENTITY_SIDECAR).is_file() else {}
    abi_sidecar = _read_json(bundle / ABI_SIDECAR) if (bundle / ABI_SIDECAR).is_file() else {}
    provenance = _read_json(bundle / PROVENANCE_SIDECAR) if (bundle / PROVENANCE_SIDECAR).is_file() else {}
    local_provenance = _read_json(bundle / LOCAL_PROVENANCE_SIDECAR) if (bundle / LOCAL_PROVENANCE_SIDECAR).is_file() else {}
    signature = _read_json(bundle / SIGNATURE_DECISION_SIDECAR) if (bundle / SIGNATURE_DECISION_SIDECAR).is_file() else {}
    subjects = _read_json(bundle / SUBJECTS_SIDECAR) if (bundle / SUBJECTS_SIDECAR).is_file() else {}
    artifact_class = str(identity.get("artifact_class") or "")
    subject_resolutions: list[dict[str, Any]] = []

    required_controls: list[str] = []
    policy_controls: set[str] = set()
    policy = load_policy(repo_root)
    if artifact_class:
        try:
            rule = artifact_class_rule(artifact_class, repo_root=repo_root)
            required_controls = required_controls_for_rule(rule)
            policy_controls = {control for control in CONTROL_FILES if isinstance(rule.get(control), dict)}
            expected_identity = rule.get("identity") if isinstance(rule.get("identity"), dict) else {}
            if expected_identity.get("contract_version") != identity.get("contract_version"):
                errors.append("artifact.identity.json contract_version does not match policy")
            if expected_identity.get("abi_epoch") != identity.get("abi_epoch"):
                errors.append("artifact.identity.json abi_epoch does not match policy")
        except ValueError as exc:
            errors.append(str(exc))
    else:
        errors.append("artifact.identity.json must define artifact_class")

    contract_surface = abi_sidecar.get("contract_surface") if isinstance(abi_sidecar.get("contract_surface"), dict) else {}
    external_subject = abi_sidecar.get("external_subject") if isinstance(abi_sidecar.get("external_subject"), dict) else {}
    if contract_surface:
        if identity.get("contract_surface_id") and contract_surface.get("id") != identity.get("contract_surface_id"):
            errors.append("artifact.abi.json contract surface id does not match artifact.identity.json")
        if artifact_class and contract_surface.get("artifact_class") != artifact_class:
            errors.append("artifact.abi.json artifact_class does not match artifact.identity.json")
        if provenance.get("subject", {}).get("digest") != contract_surface.get("source_tree_hash"):
            errors.append("artifact.provenance.json subject digest does not match ABI source_tree_hash")
    elif external_subject:
        if artifact_class and external_subject.get("artifact_class") != artifact_class:
            errors.append("artifact.abi.json external_subject artifact_class does not match artifact.identity.json")
        if not external_subject.get("path") or not external_subject.get("sha256"):
            errors.append("artifact.abi.json external_subject must define path and sha256")
        if provenance.get("subject", {}).get("digest") != external_subject.get("sha256"):
            errors.append("artifact.provenance.json subject digest does not match ABI external_subject sha256")
        artifact_identity = external_subject.get("artifact_identity")
        if isinstance(artifact_identity, dict):
            if artifact_identity.get("artifact_class") != artifact_class:
                errors.append("artifact.abi.json external artifact_identity artifact_class does not match")
            if artifact_identity.get("abi_epoch") != identity.get("abi_epoch"):
                errors.append("artifact.abi.json external artifact_identity abi_epoch does not match policy")
    elif "abi_signature" in required_controls:
        errors.append("artifact.abi.json must define contract_surface or external_subject when abi_signature is required")
    elif not provenance.get("subject", {}).get("digest"):
        errors.append("artifact.provenance.json subject digest is required")
    if "local_provenance" in required_controls:
        _validate_local_provenance_packet(local_provenance, identity, policy, errors)
    if "sbom" in required_controls:
        _validate_sbom_sidecars(bundle, subjects, errors)
    if "ml_bom" in required_controls:
        _validate_ml_bom_sidecar(bundle, subjects, errors)
    if "slsa_in_toto" in required_controls:
        _validate_slsa_sidecar(bundle, subjects, errors)
    if "c2pa" in required_controls:
        _validate_c2pa_sidecar(
            bundle=bundle,
            identity=identity,
            subjects=subjects,
            repo_root=repo_root,
            errors=errors,
            warnings=warnings,
        )
    _validate_artifact_subject_files(
        identity=identity,
        subjects=subjects,
        repo_root=repo_root,
        errors=errors,
        resolutions=subject_resolutions,
    )
    if signature.get("required") is False and signature.get("status") != "not_required":
        errors.append("artifact.signature-decision.json optional signature must use status=not_required")
    if signature.get("required") is True and signature.get("ok") is not True:
        errors.append("required cryptographic signature was not produced")
    if "sigstore_cosign" in required_controls:
        _validate_cosign_signature(bundle, signature, missing, errors)

    for control in required_controls:
        if not _has_any(bundle, CONTROL_FILES[control]):
            missing.append(" or ".join(CONTROL_FILES[control]))
    deferred_controls = identity.get("deferred_controls") if isinstance(identity.get("deferred_controls"), dict) else {}
    for control in policy_controls:
        if control in required_controls:
            continue
        decision = deferred_controls.get(control)
        if not isinstance(decision, dict) or decision.get("required") is not False or not decision.get("reason"):
            warnings.append(f"deferred control lacks explicit not-required reason: {control}")

    ok = not missing and not errors
    present_controls = [control for control in required_controls if _has_any(bundle, CONTROL_FILES[control])]
    payload = {
        "ok": ok,
        "schema": "abyss_machine_artifact_bundle_verify_v1",
        "bundle_dir": _portable_path_ref(bundle),
        "bundle_layout": BUNDLE_LAYOUT,
        "artifact_class": artifact_class,
        "required_controls": required_controls,
        "verified_controls": list(required_controls) if ok else [],
        "present_controls": present_controls,
        "missing": missing,
        "errors": errors,
        "warnings": warnings,
        "policy_ref": POLICY_REF,
        "abi_ref": ABI_REF,
    }
    if subject_resolutions:
        payload["artifact_subject_resolution"] = subject_resolutions
    if write:
        _write_json(bundle / VERIFY_SIDECAR, payload)
    return payload


def _bundle_manifest_for_identity(identity: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    manifest_ref = str(identity.get("bundle_manifest_ref") or "")
    if not manifest_ref:
        return {}
    try:
        return load_bundle_manifest(manifest_ref, repo_root=repo_root)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return {}


def _registry_record_id(artifact_class: str, subject_digest: str, bundle_manifest_ref: str) -> str:
    payload = {
        "artifact_class": artifact_class,
        "subject_digest": subject_digest,
        "bundle_manifest_ref": bundle_manifest_ref,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _verifier_versions(verification: dict[str, Any], override: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "artifact_bundle_verifier": {
            "id": "abyss-machine.artifact_bundles.verify_bundle",
            "schema": str(verification.get("schema") or "unknown"),
            "bundle_layout": BUNDLE_LAYOUT,
        },
        "policy": {"ref": POLICY_REF},
        "abi": {"ref": ABI_REF},
    }
    if override:
        base.update(override)
    return base


def _source_ref_from_evidence(
    *,
    explicit: str,
    identity: dict[str, Any],
    provenance: dict[str, Any],
    manifest: dict[str, Any],
) -> str:
    if explicit:
        return explicit
    bundle_manifest_ref = str(identity.get("bundle_manifest_ref") or "")
    if bundle_manifest_ref:
        return bundle_manifest_ref
    source_refs = provenance.get("source_refs") if isinstance(provenance.get("source_refs"), list) else []
    for item in source_refs:
        if str(item):
            return str(item)
    manifest_path = str(manifest.get("_manifest_path") or "")
    if manifest_path:
        return _portable_path_ref(Path(manifest_path))
    return ""


def _registry_record_path(registry_dir: Path, record_id: str) -> Path:
    filename = record_id.removeprefix("sha256:") + ".json"
    return registry_dir / BUNDLE_REGISTRY_RECORDS_DIR / filename


def bundle_registry_record(
    bundle_dir: str | Path,
    *,
    lifecycle_state: str = "manually-verified",
    consumer_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    supersedes: list[str] | None = None,
    revocation_reason: str = "",
    source_repo: str = "",
    source_ref: str = "",
    producer: str = "",
    trust_root_mode: str = "local_dev",
    verifier_versions: dict[str, Any] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if lifecycle_state not in BUNDLE_LIFECYCLE_STATES:
        raise ValueError(f"unknown lifecycle_state: {lifecycle_state}")
    if trust_root_mode not in TRUST_ROOT_MODES:
        raise ValueError(f"unknown trust_root_mode: {trust_root_mode}")
    bundle = Path(bundle_dir)
    verification = verify_bundle(bundle, repo_root=repo_root, write=True)
    identity = _read_json(bundle / IDENTITY_SIDECAR) if (bundle / IDENTITY_SIDECAR).is_file() else {}
    provenance = _read_json(bundle / PROVENANCE_SIDECAR) if (bundle / PROVENANCE_SIDECAR).is_file() else {}
    signature = _read_json(bundle / SIGNATURE_DECISION_SIDECAR) if (bundle / SIGNATURE_DECISION_SIDECAR).is_file() else {}
    subjects = _read_json(bundle / SUBJECTS_SIDECAR) if (bundle / SUBJECTS_SIDECAR).is_file() else {}
    manifest = _bundle_manifest_for_identity(identity, repo_root=repo_root)
    consumer_contract = manifest.get("consumer_contract") if isinstance(manifest.get("consumer_contract"), dict) else {}

    artifact_class = str(identity.get("artifact_class") or verification.get("artifact_class") or "")
    bundle_manifest_ref = str(identity.get("bundle_manifest_ref") or "")
    subject = provenance.get("subject") if isinstance(provenance.get("subject"), dict) else {}
    subject_digest = str(
        signature.get("subject_digest")
        or provenance.get("artifact_subjects_digest")
        or subjects.get("aggregate_digest")
        or subject.get("digest")
        or ""
    )
    record_id = _registry_record_id(artifact_class, subject_digest, bundle_manifest_ref)
    terminal_state = lifecycle_state in BUNDLE_TERMINAL_STATES
    latest_eligible = lifecycle_state in BUNDLE_LATEST_ELIGIBLE_STATES and bool(verification.get("ok"))
    source_refs = [str(item) for item in provenance.get("source_refs", []) if str(item)] if isinstance(provenance.get("source_refs"), list) else []

    errors: list[str] = []
    if not artifact_class:
        errors.append("artifact.identity.json must define artifact_class before registry registration")
    if not subject_digest:
        errors.append("artifact provenance or signature decision must define a subject digest before registry registration")
    if lifecycle_state in BUNDLE_LATEST_ELIGIBLE_STATES and not verification.get("ok"):
        errors.append("latest-eligible lifecycle_state requires successful bundle verification")
    if lifecycle_state == "revoked" and not revocation_reason:
        errors.append("revoked lifecycle_state requires revocation_reason")

    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": record_id,
        "artifact_class": artifact_class,
        "bundle_layout": BUNDLE_LAYOUT,
        "lifecycle_state": lifecycle_state,
        "latest_eligible": latest_eligible,
        "terminal_state": terminal_state,
        "verification_ok": bool(verification.get("ok")),
        "required_controls": verification.get("required_controls", []),
        "verified_controls": verification.get("verified_controls", []),
        "present_controls": verification.get("present_controls", []),
        "controls": {
            "required": verification.get("required_controls", []),
            "verified": verification.get("verified_controls", []),
            "present": verification.get("present_controls", []),
        },
        "verification_errors": verification.get("errors", []),
        "verification_missing": verification.get("missing", []),
        "verification_warnings": verification.get("warnings", []),
        "signature_status": signature.get("status"),
        "signature_required": bool(signature.get("required")),
        "bundle_ref": _portable_path_ref(bundle),
        "bundle_manifest_ref": bundle_manifest_ref,
        "contract_surface_id": identity.get("contract_surface_id"),
        "subject_digest": subject_digest,
        "source_repo": str(source_repo or identity.get("owner_repo") or manifest.get("owner_repo") or ""),
        "source_ref": _source_ref_from_evidence(
            explicit=str(source_ref or ""),
            identity=identity,
            provenance=provenance,
            manifest=manifest,
        ),
        "source_refs": source_refs,
        "producer": str(producer or identity.get("producer") or provenance.get("agent_or_tool") or ""),
        "producer_command": str(provenance.get("producer_command") or ""),
        "trust_root_mode": trust_root_mode,
        "verifier_versions": _verifier_versions(verification, verifier_versions),
        "privacy_boundary": identity.get("privacy_boundary"),
        "artifact_subjects_digest": provenance.get("artifact_subjects_digest") or subjects.get("aggregate_digest"),
        "artifact_subject_store": _artifact_subject_store_status(subjects),
        "abi_subject_digest": subject.get("digest"),
        "consumer_expectation": identity.get("consumer_expectation"),
        "consumer_contract": consumer_contract,
        "consumer_refs": [str(item) for item in consumer_refs or [] if str(item)],
        "evidence_refs": [str(item) for item in evidence_refs or [] if str(item)],
        "supersedes": [str(item) for item in supersedes or [] if str(item)],
        "revocation_reason": revocation_reason,
        "created_at": _utc_now(),
        "policy_ref": POLICY_REF,
        "abi_ref": ABI_REF,
    }
    return {
        "ok": not errors,
        "schema": "abyss_machine_artifact_bundle_registry_write_v1",
        "record": record,
        "errors": errors,
        "verification": verification,
    }


def _latest_sort_key(record: dict[str, Any]) -> tuple[int, str, str]:
    state = str(record.get("lifecycle_state") or "")
    return (
        BUNDLE_LATEST_STATE_RANK.get(state, 0),
        str(record.get("created_at") or ""),
        str(record.get("record_id") or ""),
    )


def read_bundle_registry(
    registry_dir: str | Path,
    *,
    artifact_class: str | None = None,
) -> dict[str, Any]:
    root = Path(registry_dir)
    records_dir = root / BUNDLE_REGISTRY_RECORDS_DIR
    records: list[dict[str, Any]] = []
    if records_dir.is_dir():
        for path in sorted(records_dir.glob("*.json")):
            try:
                record = _read_json(path)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                record = {
                    "schema": "abyss_machine_artifact_bundle_registry_record_v1",
                    "record_id": path.stem,
                    "artifact_class": "",
                    "lifecycle_state": "invalid",
                    "latest_eligible": False,
                    "terminal_state": True,
                    "verification_ok": False,
                    "read_error": str(exc),
                }
            if artifact_class and record.get("artifact_class") != artifact_class:
                continue
            records.append(record)

    latest_by_artifact_class: dict[str, dict[str, Any]] = {}
    state_counts: dict[str, int] = {}
    for record in records:
        state = str(record.get("lifecycle_state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1
        if not record.get("latest_eligible") or record.get("terminal_state") or not record.get("verification_ok"):
            continue
        class_id = str(record.get("artifact_class") or "")
        if not class_id:
            continue
        current = latest_by_artifact_class.get(class_id)
        if current is None or _latest_sort_key(record) > _latest_sort_key(current):
            latest_by_artifact_class[class_id] = record

    return {
        "ok": True,
        "schema": "abyss_machine_artifact_bundle_registry_v1",
        "registry_dir": _registry_path_ref(root, root),
        "records_dir": _registry_path_ref(root, records_dir),
        "index_ref": _registry_path_ref(root, root / BUNDLE_REGISTRY_INDEX),
        "artifact_class_filter": artifact_class,
        "summary": {
            "records": len(records),
            "latest": len(latest_by_artifact_class),
            "state_counts": state_counts,
        },
        "latest_by_artifact_class": latest_by_artifact_class,
        "records": records,
    }


def write_bundle_registry_record(
    bundle_dir: str | Path,
    registry_dir: str | Path,
    *,
    lifecycle_state: str = "manually-verified",
    consumer_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    supersedes: list[str] | None = None,
    revocation_reason: str = "",
    source_repo: str = "",
    source_ref: str = "",
    producer: str = "",
    trust_root_mode: str = "local_dev",
    verifier_versions: dict[str, Any] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    root = Path(registry_dir)
    payload = bundle_registry_record(
        bundle_dir,
        lifecycle_state=lifecycle_state,
        consumer_refs=consumer_refs,
        evidence_refs=evidence_refs,
        supersedes=supersedes,
        revocation_reason=revocation_reason,
        source_repo=source_repo,
        source_ref=source_ref,
        producer=producer,
        trust_root_mode=trust_root_mode,
        verifier_versions=verifier_versions,
        repo_root=repo_root,
    )
    if not payload.get("ok"):
        return {
            **payload,
            "registry_dir": _registry_path_ref(root, root),
            "written": [],
        }
    record = payload["record"]
    record_path = _registry_record_path(root, str(record["record_id"]))
    _write_json(record_path, record)
    index = read_bundle_registry(root)
    _write_json(root / BUNDLE_REGISTRY_INDEX, index)
    return {
        **payload,
        "registry_dir": _registry_path_ref(root, root),
        "record_ref": _registry_path_ref(root, record_path),
        "written": [
            _registry_path_ref(root, record_path),
            _registry_path_ref(root, root / BUNDLE_REGISTRY_INDEX),
        ],
        "registry": index,
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _manifest_for_registry_record(record: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    manifest_ref = str(record.get("bundle_manifest_ref") or "")
    if not manifest_ref:
        return {}
    try:
        return load_bundle_manifest(manifest_ref, repo_root=repo_root)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return {}


def _policy_identity_for_registry_record(record: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    artifact_class = str(record.get("artifact_class") or "")
    if not artifact_class:
        return {}
    try:
        rule = artifact_class_rule(artifact_class, repo_root=repo_root)
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return {}
    identity = rule.get("identity")
    return identity if isinstance(identity, dict) else {}


def _legacy_registry_upgrade_record(
    record: dict[str, Any],
    *,
    source_repo: str,
    producer: str,
    trust_root_mode: str,
    upgraded_at: str,
    repo_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    upgraded = json.loads(json.dumps(record, ensure_ascii=False))
    manifest = _manifest_for_registry_record(record, repo_root=repo_root)
    policy_identity = _policy_identity_for_registry_record(record, repo_root=repo_root)
    missing = [field for field in DURABLE_EVIDENCE_FIELDS if not upgraded.get(field)]

    if not upgraded.get("source_repo"):
        upgraded["source_repo"] = str(source_repo or manifest.get("owner_repo") or policy_identity.get("owner_repo") or "")
    if not upgraded.get("source_ref"):
        source_refs = _string_list(upgraded.get("source_refs"))
        upgraded["source_ref"] = str(upgraded.get("bundle_manifest_ref") or (source_refs[0] if source_refs else "") or upgraded.get("bundle_ref") or "")
    if not upgraded.get("producer"):
        upgraded["producer"] = str(producer or policy_identity.get("producer") or "abyss-machine legacy registry evidence upgrade")
    if not upgraded.get("producer_command"):
        upgraded["producer_command"] = "abyss-machine artifacts bundle-registry-upgrade"
    if not upgraded.get("trust_root_mode"):
        upgraded["trust_root_mode"] = trust_root_mode
    if not upgraded.get("verifier_versions"):
        upgraded["verifier_versions"] = _verifier_versions(
            {"schema": "legacy_registry_record_without_durable_evidence_fields"},
            {
                "legacy_registry_record": {
                    "schema": str(upgraded.get("schema") or "unknown"),
                    "upgraded_from": "pre_durable_evidence_fields",
                }
            },
        )
    if "verification_warnings" not in upgraded:
        upgraded["verification_warnings"] = []
    if "present_controls" not in upgraded:
        controls = upgraded.get("controls") if isinstance(upgraded.get("controls"), dict) else {}
        upgraded["present_controls"] = _string_list(controls.get("present")) or _string_list(upgraded.get("verified_controls"))
    if "controls" not in upgraded or not isinstance(upgraded.get("controls"), dict):
        upgraded["controls"] = {
            "required": _string_list(upgraded.get("required_controls")),
            "verified": _string_list(upgraded.get("verified_controls")),
            "present": _string_list(upgraded.get("present_controls")),
        }
    if not upgraded.get("privacy_boundary") and policy_identity.get("privacy_boundary"):
        upgraded["privacy_boundary"] = policy_identity.get("privacy_boundary")
    if not upgraded.get("consumer_expectation") and policy_identity.get("consumer_expectation"):
        upgraded["consumer_expectation"] = policy_identity.get("consumer_expectation")
    consumer_contract = upgraded.get("consumer_contract")
    manifest_contract = manifest.get("consumer_contract")
    if (not isinstance(consumer_contract, dict) or not consumer_contract) and isinstance(manifest_contract, dict):
        upgraded["consumer_contract"] = manifest_contract

    source_refs = _string_list(upgraded.get("source_refs"))
    for ref in (POLICY_REF, str(upgraded.get("bundle_manifest_ref") or ""), str(upgraded.get("source_ref") or "")):
        if ref and ref not in source_refs:
            source_refs.append(ref)
    upgraded["source_refs"] = source_refs

    evidence_refs = _string_list(upgraded.get("evidence_refs"))
    evidence_ref = f"abyss-machine:legacy-registry-upgrade:{upgraded_at}"
    if evidence_ref not in evidence_refs:
        evidence_refs.append(evidence_ref)
    upgraded["evidence_refs"] = evidence_refs
    upgraded["legacy_evidence_upgrade"] = {
        "schema": "abyss_machine_artifact_registry_legacy_evidence_upgrade_v1",
        "upgraded_at": upgraded_at,
        "reason": "registry record predates durable consumer trust-gate evidence fields",
        "missing_fields": missing,
        "method": "host-managed assertion over an already verified local registry record",
        "trust_root_mode": upgraded.get("trust_root_mode"),
        "source_repo": upgraded.get("source_repo"),
        "source_ref": upgraded.get("source_ref"),
        "producer": upgraded.get("producer"),
    }
    return upgraded, missing


def upgrade_legacy_bundle_registry(
    registry_dir: str | Path,
    *,
    artifact_class: str = "",
    source_repo: str = "",
    producer: str = "",
    trust_root_mode: str = "host_managed",
    dry_run: bool = False,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if trust_root_mode not in TRUST_ROOT_MODES:
        raise ValueError(f"unknown trust_root_mode: {trust_root_mode}")
    root = Path(registry_dir)
    registry = read_bundle_registry(root, artifact_class=artifact_class or None)
    upgraded_at = _utc_now()
    upgrades: list[dict[str, Any]] = []
    written: list[str] = []
    unchanged = 0
    errors: list[str] = []

    for record in registry.get("records", []):
        if not isinstance(record, dict):
            continue
        missing = [field for field in DURABLE_EVIDENCE_FIELDS if not record.get(field)]
        if not missing:
            unchanged += 1
            continue
        record_id = str(record.get("record_id") or "")
        if not record_id:
            errors.append("legacy registry record without record_id cannot be upgraded")
            continue
        upgraded, initial_missing = _legacy_registry_upgrade_record(
            record,
            source_repo=source_repo,
            producer=producer,
            trust_root_mode=trust_root_mode,
            upgraded_at=upgraded_at,
            repo_root=repo_root,
        )
        remaining_missing = [field for field in DURABLE_EVIDENCE_FIELDS if not upgraded.get(field)]
        record_path = _registry_record_path(root, record_id)
        upgrade = {
            "record_id": record_id,
            "artifact_class": upgraded.get("artifact_class"),
            "lifecycle_state": upgraded.get("lifecycle_state"),
            "initial_missing_fields": initial_missing,
            "remaining_missing_fields": remaining_missing,
            "record_ref": _registry_path_ref(root, record_path),
            "write_ready": not remaining_missing,
            "source_repo": upgraded.get("source_repo"),
            "source_ref": upgraded.get("source_ref"),
            "producer": upgraded.get("producer"),
            "trust_root_mode": upgraded.get("trust_root_mode"),
        }
        upgrades.append(upgrade)
        if remaining_missing:
            errors.append(f"{record_id} still lacks durable evidence fields: {', '.join(remaining_missing)}")
            continue
        if not dry_run:
            _write_json(record_path, upgraded)
            written.append(_registry_path_ref(root, record_path))

    if not dry_run and written:
        index = read_bundle_registry(root)
        _write_json(root / BUNDLE_REGISTRY_INDEX, index)
        written.append(_registry_path_ref(root, root / BUNDLE_REGISTRY_INDEX))

    return {
        "ok": not errors,
        "schema": "abyss_machine_artifact_bundle_registry_upgrade_v1",
        "registry_dir": _registry_path_ref(root, root),
        "artifact_class_filter": artifact_class or None,
        "dry_run": dry_run,
        "upgraded_at": upgraded_at,
        "summary": {
            "records_seen": len(registry.get("records", [])),
            "upgraded": len(upgrades),
            "unchanged": unchanged,
            "errors": len(errors),
        },
        "upgrades": upgrades,
        "written": written,
        "errors": errors,
    }


def promote_bundle_evidence(
    bundle_dir: str | Path,
    registry_dir: str | Path,
    *,
    lifecycle_state: str = "manually-verified",
    consumer_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    supersedes: list[str] | None = None,
    revocation_reason: str = "",
    source_repo: str = "",
    source_ref: str = "",
    producer: str = "",
    trust_root_mode: str = "local_dev",
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    registry_write = write_bundle_registry_record(
        bundle_dir,
        registry_dir,
        lifecycle_state=lifecycle_state,
        consumer_refs=consumer_refs,
        evidence_refs=evidence_refs,
        supersedes=supersedes,
        revocation_reason=revocation_reason,
        source_repo=source_repo,
        source_ref=source_ref,
        producer=producer,
        trust_root_mode=trust_root_mode,
        repo_root=repo_root,
    )
    record = registry_write.get("record") if isinstance(registry_write.get("record"), dict) else {}
    return {
        "ok": bool(registry_write.get("ok")),
        "schema": "abyss_machine_artifact_evidence_promotion_v1",
        "bundle_layout": BUNDLE_LAYOUT,
        "bundle_dir": _portable_path_ref(Path(bundle_dir)),
        "registry_dir": registry_write.get("registry_dir"),
        "record_ref": registry_write.get("record_ref"),
        "written": registry_write.get("written", []),
        "promotion": {
            "record_id": record.get("record_id"),
            "artifact_class": record.get("artifact_class"),
            "subject_digest": record.get("subject_digest"),
            "lifecycle_state": record.get("lifecycle_state"),
            "source_repo": record.get("source_repo"),
            "source_ref": record.get("source_ref"),
            "producer": record.get("producer"),
            "trust_root_mode": record.get("trust_root_mode"),
            "durable_registry": bool(registry_write.get("ok")),
        },
        "record": record,
        "registry": registry_write.get("registry"),
        "verification": registry_write.get("verification"),
        "errors": registry_write.get("errors", []),
    }


def _record_digest_values(record: dict[str, Any]) -> set[str]:
    digests: set[str] = set()
    for key in ("subject_digest", "artifact_subjects_digest", "abi_subject_digest", "record_id"):
        value = str(record.get(key) or "")
        if value:
            digests.add(value)
    return digests


def _find_registry_record(
    records: list[dict[str, Any]],
    *,
    record_id: str,
    subject_digest: str,
) -> dict[str, Any] | None:
    if record_id:
        for record in records:
            if str(record.get("record_id") or "") == record_id:
                return record
    if subject_digest:
        matches = [record for record in records if subject_digest in _record_digest_values(record)]
        if matches:
            return sorted(matches, key=_latest_sort_key)[-1]
    return None


def _trust_gate_decision(
    *,
    verdict: str,
    consumer_intent: str,
    blockers: list[str],
    manual_review: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "model": "fail_closed_consumer_admission",
        "allowed_verdicts": ["allow", "warn"],
        "verdict": verdict,
        "allow": verdict in {"allow", "warn"},
        "consumer_intent": consumer_intent,
        "blocks_on_unknown": True,
        "blockers": blockers,
        "manual_review": manual_review,
        "warnings": warnings,
    }


def _trust_gate_inspected_claims(
    selected: dict[str, Any],
    *,
    latest: dict[str, Any] | None,
    artifact_class: str,
    subject_digest: str,
    record_id: str,
    expected_source_repo: str,
    expected_trust_root_mode: str,
    require_latest: bool,
) -> dict[str, Any]:
    required_controls = [str(item) for item in selected.get("required_controls", [])]
    verified_controls = [str(item) for item in selected.get("verified_controls", [])]
    latest_record_id = str(latest.get("record_id") or "") if isinstance(latest, dict) else ""
    selected_record_id = str(selected.get("record_id") or "")
    digest_values = _record_digest_values(selected)
    privacy_boundary = selected.get("privacy_boundary")
    privacy_review_reason = production_privacy_boundary_review_reason(privacy_boundary)
    return {
        "registry_latest": {
            "required": require_latest,
            "latest_record_id": latest_record_id or None,
            "selected_record_id": selected_record_id or None,
            "selected_record_is_latest": bool(latest_record_id and selected_record_id == latest_record_id),
        },
        "record_identity": {
            "artifact_class_expected": artifact_class,
            "artifact_class_actual": selected.get("artifact_class"),
            "record_id_expected": record_id or None,
            "record_id_actual": selected_record_id or None,
            "record_id_matched": bool(not record_id or selected_record_id == record_id),
        },
        "subject_identity": {
            "subject_digest_expected": subject_digest or None,
            "known_digests": sorted(digest_values),
            "subject_digest_matched": bool(not subject_digest or subject_digest in digest_values),
        },
        "lifecycle": {
            "state": selected.get("lifecycle_state"),
            "latest_eligible": bool(selected.get("latest_eligible")),
            "terminal_state": bool(selected.get("terminal_state")),
        },
        "verification": {
            "ok": bool(selected.get("verification_ok")),
            "errors": selected.get("verification_errors", []),
            "missing": selected.get("verification_missing", []),
            "warnings": selected.get("verification_warnings", []),
        },
        "controls": {
            "required": required_controls,
            "verified": verified_controls,
            "present": [str(item) for item in selected.get("present_controls", [])],
            "required_controls_missing": sorted(set(required_controls) - set(verified_controls)),
        },
        "source": {
            "source_repo_expected": expected_source_repo or None,
            "source_repo_actual": selected.get("source_repo"),
            "source_repo_matched": bool(not expected_source_repo or str(selected.get("source_repo") or "") == expected_source_repo),
            "source_ref": selected.get("source_ref"),
            "producer": selected.get("producer"),
        },
        "trust_root": {
            "trust_root_mode_expected": expected_trust_root_mode or None,
            "trust_root_mode_actual": selected.get("trust_root_mode"),
            "trust_root_mode_matched": bool(
                not expected_trust_root_mode or str(selected.get("trust_root_mode") or "") == expected_trust_root_mode
            ),
        },
        "privacy_boundary": {
            "value": privacy_boundary,
            "production_review_reason": privacy_review_reason or None,
            "production_public_ready": not privacy_review_reason,
        },
        "artifact_subject_store": selected.get("artifact_subject_store"),
        "consumer_contract": selected.get("consumer_contract"),
    }


def trust_gate(
    registry_dir: str | Path,
    *,
    artifact_class: str,
    subject_digest: str = "",
    record_id: str = "",
    consumer_intent: str = "agent",
    expected_source_repo: str = "",
    expected_trust_root_mode: str = "",
    require_latest: bool = True,
) -> dict[str, Any]:
    registry = read_bundle_registry(registry_dir, artifact_class=artifact_class)
    records = [record for record in registry.get("records", []) if isinstance(record, dict)]
    latest = registry.get("latest_by_artifact_class", {}).get(artifact_class)
    selected = _find_registry_record(records, record_id=record_id, subject_digest=subject_digest)
    if selected is None and isinstance(latest, dict):
        selected = latest

    if selected is None:
        blockers = ["no_registry_record"]
        manual_review: list[str] = []
        warnings: list[str] = []
        verdict = "unknown"
        return {
            "ok": False,
            "schema": "abyss_machine_artifact_trust_gate_v1",
            "verdict": verdict,
            "decision": _trust_gate_decision(
                verdict=verdict,
                consumer_intent=consumer_intent,
                blockers=blockers,
                manual_review=manual_review,
                warnings=warnings,
            ),
            "artifact_class": artifact_class,
            "consumer_intent": consumer_intent,
            "subject_digest": subject_digest or None,
            "record_id": record_id or None,
            "require_latest": require_latest,
            "registry_dir": registry.get("registry_dir"),
            "latest_record_id": latest.get("record_id") if isinstance(latest, dict) else None,
            "reasons": blockers,
            "blockers": blockers,
            "manual_review": [],
            "warnings": [],
            "inspected_claims": {
                "registry_latest": {
                    "required": require_latest,
                    "latest_record_id": latest.get("record_id") if isinstance(latest, dict) else None,
                    "selected_record_id": None,
                    "selected_record_is_latest": False,
                },
                "record_identity": {
                    "artifact_class_expected": artifact_class,
                    "record_id_expected": record_id or None,
                    "record_id_actual": None,
                    "record_id_matched": False if record_id else None,
                },
                "subject_identity": {
                    "subject_digest_expected": subject_digest or None,
                    "known_digests": [],
                    "subject_digest_matched": False if subject_digest else None,
                },
            },
            "record": None,
            "registry_summary": registry.get("summary", {}),
        }

    blockers: list[str] = []
    manual_review: list[str] = []
    warnings: list[str] = []

    if selected.get("artifact_class") != artifact_class:
        blockers.append("artifact_class_mismatch")
    if subject_digest and subject_digest not in _record_digest_values(selected):
        blockers.append("subject_digest_mismatch")
    if record_id and str(selected.get("record_id") or "") != record_id:
        blockers.append("record_id_mismatch")
    if require_latest:
        if not isinstance(latest, dict):
            blockers.append("no_latest_record")
        elif str(latest.get("record_id") or "") != str(selected.get("record_id") or ""):
            blockers.append("record_not_latest")
    if selected.get("terminal_state") or selected.get("lifecycle_state") in BUNDLE_TERMINAL_STATES:
        blockers.append(f"terminal_lifecycle_state:{selected.get('lifecycle_state')}")
    if not selected.get("verification_ok"):
        blockers.append("verification_not_ok")
    if selected.get("verification_errors"):
        blockers.append("verification_errors_present")
    if selected.get("verification_missing"):
        blockers.append("verification_missing_required_sidecars")

    required_controls = {str(item) for item in selected.get("required_controls", [])}
    verified_controls = {str(item) for item in selected.get("verified_controls", [])}
    missing_verified = sorted(required_controls - verified_controls)
    if missing_verified:
        blockers.append("required_controls_not_verified:" + ",".join(missing_verified))

    required_record_fields = DURABLE_EVIDENCE_FIELDS
    missing_record_fields = [field for field in required_record_fields if not selected.get(field)]
    if missing_record_fields:
        blockers.append("record_missing_durable_evidence_fields:" + ",".join(missing_record_fields))

    trust_root_mode = str(selected.get("trust_root_mode") or "")
    if trust_root_mode and trust_root_mode not in TRUST_ROOT_MODES:
        blockers.append(f"unknown_trust_root_mode:{trust_root_mode}")
    if expected_source_repo and str(selected.get("source_repo") or "") != expected_source_repo:
        blockers.append("source_repo_mismatch")
    if expected_trust_root_mode and trust_root_mode != expected_trust_root_mode:
        blockers.append("trust_root_mode_mismatch")

    lifecycle_state = str(selected.get("lifecycle_state") or "")
    if consumer_intent in PRODUCTION_CONSUMER_INTENTS:
        if trust_root_mode == "local_dev":
            manual_review.append("production_consumer_requires_non_local_trust_root")
        if lifecycle_state not in {"release-ready", "published"}:
            manual_review.append("production_consumer_requires_release_lifecycle")
        privacy_review_reason = production_privacy_boundary_review_reason(selected.get("privacy_boundary"))
        if privacy_review_reason:
            manual_review.append(privacy_review_reason)

    if selected.get("verification_warnings"):
        warnings.extend(str(item) for item in selected.get("verification_warnings", []))

    if blockers:
        verdict = "deny"
    elif manual_review:
        verdict = "manual_review_required"
    elif warnings:
        verdict = "warn"
    else:
        verdict = "allow"

    return {
        "ok": verdict in {"allow", "warn"},
        "schema": "abyss_machine_artifact_trust_gate_v1",
        "verdict": verdict,
        "decision": _trust_gate_decision(
            verdict=verdict,
            consumer_intent=consumer_intent,
            blockers=blockers,
            manual_review=manual_review,
            warnings=warnings,
        ),
        "artifact_class": artifact_class,
        "consumer_intent": consumer_intent,
        "subject_digest": subject_digest or None,
        "record_id": str(selected.get("record_id") or "") or None,
        "require_latest": require_latest,
        "registry_dir": registry.get("registry_dir"),
        "latest_record_id": latest.get("record_id") if isinstance(latest, dict) else None,
        "reasons": [*blockers, *manual_review, *warnings],
        "blockers": blockers,
        "manual_review": manual_review,
        "warnings": warnings,
        "inspected_claims": _trust_gate_inspected_claims(
            selected,
            latest=latest if isinstance(latest, dict) else None,
            artifact_class=artifact_class,
            subject_digest=subject_digest,
            record_id=record_id,
            expected_source_repo=expected_source_repo,
            expected_trust_root_mode=expected_trust_root_mode,
            require_latest=require_latest,
        ),
        "record": selected,
        "registry_summary": registry.get("summary", {}),
    }


def release_check(
    bundle_dir: str | Path,
    *,
    enforcement: str = "blocking",
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    if enforcement not in RELEASE_ENFORCEMENT_LEVELS:
        raise ValueError(f"unknown enforcement level: {enforcement}")
    verification = verify_bundle(bundle_dir, repo_root=repo_root, write=True)
    allowed_by_enforcement = bool(verification.get("ok")) or enforcement == "warn"
    return {
        "ok": allowed_by_enforcement,
        "schema": "abyss_machine_artifact_bundle_release_check_v1",
        "bundle_dir": _portable_path_ref(Path(bundle_dir)),
        "enforcement": enforcement,
        "verification_ok": bool(verification.get("ok")),
        "verification": verification,
    }
