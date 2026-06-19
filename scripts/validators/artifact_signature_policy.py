#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

from _common import REPO_ROOT, fail, load_json, ok, rel, require


POLICY = REPO_ROOT / "manifests" / "artifact_signature_policy.manifest.json"
VALIDATION_LANES = REPO_ROOT / "docs" / "validation" / "validation_lanes.json"
GENERATED_SURFACE = "generated/contract_abi_signatures.min.json"
REQUIRED_POLICY_KEYS = ("abi_signature", "sbom", "ml_bom", "slsa_in_toto", "sigstore_cosign", "c2pa")
REQUIRED_IDENTITY_KEYS = (
    "artifact_class",
    "surface_state",
    "owner_repo",
    "authority_ref",
    "producer",
    "consumer_expectation",
    "privacy_boundary",
    "content_identity",
    "abi_epoch",
    "trust_layer",
    "verification",
    "action",
)
REQUIRED_LOCAL_PROVENANCE_FIELDS = (
    "schema",
    "artifact_class",
    "surface_state",
    "owner_repo",
    "authority_ref",
    "producer",
    "producer_command",
    "source_refs",
    "activity",
    "agent_or_tool",
    "created_at",
    "privacy_boundary",
    "content_identity",
    "consumer_expectation",
    "verification",
    "promotion_status",
)
ALLOWED_ACTIONS = {
    "KEEP",
    "DEFINE_ABI",
    "ADD_CONTRACT_SIGNATURE",
    "ADD_LOCAL_PROVENANCE",
    "ADD_CONSUMER_EXPECTATION",
    "HARDEN_VALIDATOR",
    "ADD_TEST",
    "ADD_RELEASE_PROVENANCE",
    "ADD_BOM",
    "ADD_ML_BOM",
    "ADD_COSIGN",
    "ADD_C2PA",
    "PREPARE_TUF",
    "PREPARE_SCITT",
    "ROUTE_TO_OWNER",
    "DEFER_WITH_RATIONALE",
}
ALLOWED_TRUST_LAYERS = {
    "abi_contract_signature",
    "local_provenance",
    "w3c_prov_lineage",
    "sbom",
    "ml_bom",
    "slsa_in_toto",
    "sigstore_cosign",
    "c2pa",
    "tuf",
    "scitt",
}
REQUIRED_ENTRYPOINT_SOURCES = {
    "docs/validation/validation_lanes.json",
    "scripts/validation_lanes.py",
    "scripts/ci_gate.py",
    "scripts/release_check.py",
}
REQUIRED_RUNNER_CONTEXTS = {
    "os_abyss_local_cli",
    "os_abyss_host_scheduler",
    "release_pipeline",
}
REQUIRED_ENTRYPOINTS = {
    "source-fast": ("python", "scripts/ci_gate.py", "--mode", "source-fast"),
    "release-artifact": ("python", "scripts/ci_gate.py", "--mode", "release-artifact"),
    "release-check": ("python", "scripts/release_check.py"),
}
FORBIDDEN_SOURCE_PREFIXES = (
    "/var/lib/abyss-machine",
    "/srv/abyss-machine/cache",
    "/srv/abyss-machine/runtimes",
    "/srv/abyss-machine/storage",
    "/srv/abyss-machine/tmp",
    "/srv/abyss-machine/backups",
    "/abyss/Backups",
)


def tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return {line for line in result.stdout.splitlines() if line and (REPO_ROOT / line).is_file()}


def tracked_under(path_text: str, tracked: set[str]) -> list[str]:
    path = REPO_ROOT / path_text
    if path.is_file():
        return [path_text] if path_text in tracked else []
    if path.is_dir():
        prefix = path_text.rstrip("/") + "/"
        return sorted(item for item in tracked if item.startswith(prefix))
    return []


def main() -> int:
    policy = load_json(POLICY)
    lanes_manifest = load_json(VALIDATION_LANES)
    failures: list[str] = []
    tracked = tracked_files()

    require(policy.get("schema") == "abyss_machine_artifact_signature_policy_manifest_v1", f"{rel(POLICY)} schema mismatch", failures)
    abi = policy.get("abi_signature")
    require(isinstance(abi, dict), "artifact signature policy must define abi_signature", failures)
    if isinstance(abi, dict):
        require(abi.get("algorithm") == "sha256-tree-v1", "ABI signature algorithm must be sha256-tree-v1", failures)
        require(abi.get("generated_surface") == GENERATED_SURFACE, f"ABI generated_surface must be {GENERATED_SURFACE}", failures)

    lane_runner_contexts = lanes_manifest.get("runner_contexts")
    require(isinstance(lane_runner_contexts, dict) and bool(lane_runner_contexts), "validation lanes must define runner_contexts", failures)

    runner_contract = policy.get("portable_runner_contract")
    require(isinstance(runner_contract, dict), "artifact signature policy must define portable_runner_contract", failures)
    if isinstance(runner_contract, dict):
        entrypoint_sources = runner_contract.get("entrypoint_sources")
        if not isinstance(entrypoint_sources, list) or not all(isinstance(item, str) and item for item in entrypoint_sources):
            failures.append("portable_runner_contract.entrypoint_sources must be a non-empty string list")
        else:
            missing_sources = sorted(REQUIRED_ENTRYPOINT_SOURCES - set(entrypoint_sources))
            if missing_sources:
                failures.append(f"portable_runner_contract.entrypoint_sources missing: {', '.join(missing_sources)}")

        runner_contexts = runner_contract.get("runner_contexts")
        if not isinstance(runner_contexts, list) or not all(isinstance(item, str) and item for item in runner_contexts):
            failures.append("portable_runner_contract.runner_contexts must be a non-empty string list")
        else:
            missing_contexts = sorted(REQUIRED_RUNNER_CONTEXTS - set(runner_contexts))
            if missing_contexts:
                failures.append(f"portable_runner_contract.runner_contexts missing: {', '.join(missing_contexts)}")
            if isinstance(lane_runner_contexts, dict):
                for context_id in runner_contexts:
                    if context_id not in lane_runner_contexts:
                        failures.append(f"portable_runner_contract references unknown validation runner_context: {context_id}")
                        continue
                    lane_context = lane_runner_contexts[context_id]
                    if isinstance(lane_context, dict) and lane_context.get("requires_private_host_state") is True:
                        failures.append(f"portable_runner_contract uses private host runner_context: {context_id}")

        entrypoints = runner_contract.get("required_entrypoints")
        if not isinstance(entrypoints, list) or not entrypoints:
            failures.append("portable_runner_contract.required_entrypoints must be a non-empty list")
        else:
            entrypoint_commands: dict[str, tuple[str, ...]] = {}
            for entrypoint in entrypoints:
                if not isinstance(entrypoint, dict):
                    failures.append("portable_runner_contract.required_entrypoints entries must be objects")
                    continue
                entrypoint_id = str(entrypoint.get("id") or "")
                command = entrypoint.get("command")
                if not entrypoint_id:
                    failures.append("portable_runner_contract.required_entrypoints entries must define id")
                    continue
                if not isinstance(command, list) or not all(isinstance(part, str) and part for part in command):
                    failures.append(f"portable_runner_contract entrypoint {entrypoint_id} must define a string command list")
                    continue
                entrypoint_commands[entrypoint_id] = tuple(command)
            for entrypoint_id, command in sorted(REQUIRED_ENTRYPOINTS.items()):
                if entrypoint_commands.get(entrypoint_id) != command:
                    failures.append(
                        f"portable_runner_contract entrypoint {entrypoint_id} must be: {' '.join(command)}"
                    )

    classes = policy.get("artifact_classes")
    require(isinstance(classes, dict) and bool(classes), "artifact signature policy must define artifact_classes", failures)
    if isinstance(classes, dict):
        for class_id, item in sorted(classes.items()):
            if not isinstance(item, dict):
                failures.append(f"artifact class {class_id} must be an object")
                continue
            missing = [key for key in REQUIRED_POLICY_KEYS if key not in item]
            if missing:
                failures.append(f"artifact class {class_id} missing policy keys: {', '.join(missing)}")
            for key in REQUIRED_POLICY_KEYS:
                rule = item.get(key)
                if not isinstance(rule, dict):
                    failures.append(f"artifact class {class_id}.{key} must be an object")
                    continue
                if "required" not in rule:
                    failures.append(f"artifact class {class_id}.{key} must state required")
            identity = item.get("identity")
            if not isinstance(identity, dict):
                failures.append(f"artifact class {class_id} must define identity posture")
                continue
            missing_identity = [key for key in REQUIRED_IDENTITY_KEYS if key not in identity]
            if missing_identity:
                failures.append(f"artifact class {class_id}.identity missing keys: {', '.join(missing_identity)}")
            if identity.get("artifact_class") != class_id:
                failures.append(f"artifact class {class_id}.identity.artifact_class must match class id")
            authority_ref = identity.get("authority_ref")
            if not isinstance(authority_ref, list) or not all(isinstance(item, str) and item for item in authority_ref):
                failures.append(f"artifact class {class_id}.identity.authority_ref must be a non-empty string list")
            trust_layer = identity.get("trust_layer")
            if not isinstance(trust_layer, list) or not all(isinstance(item, str) and item for item in trust_layer):
                failures.append(f"artifact class {class_id}.identity.trust_layer must be a non-empty string list")
            else:
                unknown_layers = sorted(set(trust_layer) - ALLOWED_TRUST_LAYERS)
                if unknown_layers:
                    failures.append(f"artifact class {class_id}.identity.trust_layer unknown values: {', '.join(unknown_layers)}")
                if item.get("abi_signature", {}).get("required") is True and "abi_contract_signature" not in trust_layer:
                    failures.append(f"artifact class {class_id} requires abi_signature but identity omits abi_contract_signature")
                if item.get("ml_bom", {}).get("required") is True and "ml_bom" not in trust_layer:
                    failures.append(f"artifact class {class_id} requires ml_bom but identity omits ml_bom")
            verification = identity.get("verification")
            if not isinstance(verification, list) or not all(isinstance(item, str) and item for item in verification):
                failures.append(f"artifact class {class_id}.identity.verification must be a non-empty string list")
            if identity.get("action") not in ALLOWED_ACTIONS:
                failures.append(f"artifact class {class_id}.identity.action must be one of the allowed actions")
            if class_id == "host_local_evidence":
                if isinstance(trust_layer, list) and not {"local_provenance", "w3c_prov_lineage"} <= set(trust_layer):
                    failures.append("host_local_evidence identity must use local_provenance and w3c_prov_lineage")
                privacy = str(identity.get("privacy_boundary") or "")
                if "private" not in privacy.lower():
                    failures.append("host_local_evidence identity must state a private privacy boundary")

    identity_fields = policy.get("identity_fields")
    if not isinstance(identity_fields, list) or not all(isinstance(item, str) and item for item in identity_fields):
        failures.append("artifact signature policy must define identity_fields as a non-empty string list")
    else:
        missing_identity_fields = sorted(set(REQUIRED_IDENTITY_KEYS) - set(identity_fields))
        if missing_identity_fields:
            failures.append(f"identity_fields missing required keys: {', '.join(missing_identity_fields)}")

    local_packet = policy.get("local_provenance_packet")
    require(isinstance(local_packet, dict), "artifact signature policy must define local_provenance_packet", failures)
    if isinstance(local_packet, dict):
        require(
            local_packet.get("schema") == "abyss_machine_local_provenance_packet_v1",
            "local_provenance_packet schema mismatch",
            failures,
        )
        applies_to = local_packet.get("applies_to_artifact_classes")
        if not isinstance(applies_to, list) or "host_local_evidence" not in applies_to:
            failures.append("local_provenance_packet must apply to host_local_evidence")
        storage_route = str(local_packet.get("storage_route") or "")
        if not storage_route.startswith("/var/lib/abyss-machine"):
            failures.append("local_provenance_packet.storage_route must stay under /var/lib/abyss-machine")
        if local_packet.get("not_public_repo_content") is not True:
            failures.append("local_provenance_packet.not_public_repo_content must be true")
        required_fields = local_packet.get("required_fields")
        if not isinstance(required_fields, list) or not all(isinstance(item, str) and item for item in required_fields):
            failures.append("local_provenance_packet.required_fields must be a non-empty string list")
        else:
            missing_fields = sorted(set(REQUIRED_LOCAL_PROVENANCE_FIELDS) - set(required_fields))
            if missing_fields:
                failures.append(f"local_provenance_packet.required_fields missing: {', '.join(missing_fields)}")
        consumer_checks = local_packet.get("consumer_checks")
        if not isinstance(consumer_checks, list) or not consumer_checks:
            failures.append("local_provenance_packet.consumer_checks must be a non-empty list")
        promotion_controls = local_packet.get("promotion_controls")
        if not isinstance(promotion_controls, list) or not promotion_controls:
            failures.append("local_provenance_packet.promotion_controls must be a non-empty list")
        lineage_mapping = local_packet.get("lineage_mapping")
        if not isinstance(lineage_mapping, dict) or not {"entity", "activity", "agent"} <= set(lineage_mapping):
            failures.append("local_provenance_packet.lineage_mapping must define entity, activity, and agent")

    surfaces = policy.get("contract_surfaces")
    require(isinstance(surfaces, list) and bool(surfaces), "artifact signature policy must define contract_surfaces", failures)
    seen_surface_ids: set[str] = set()
    if isinstance(surfaces, list):
        for surface in surfaces:
            if not isinstance(surface, dict):
                failures.append("contract surface entries must be objects")
                continue
            surface_id = str(surface.get("id") or "")
            artifact_class = str(surface.get("artifact_class") or "")
            source_paths = surface.get("source_paths")
            if not surface_id:
                failures.append("contract surface must define id")
            elif surface_id in seen_surface_ids:
                failures.append(f"duplicate contract surface id: {surface_id}")
            seen_surface_ids.add(surface_id)
            if isinstance(classes, dict) and artifact_class not in classes:
                failures.append(f"contract surface {surface_id} references unknown artifact_class {artifact_class}")
            if not isinstance(source_paths, list) or not source_paths:
                failures.append(f"contract surface {surface_id} must define source_paths")
                continue
            for source in source_paths:
                source_text = str(source)
                if source_text.startswith("/") or ".." in Path(source_text).parts:
                    failures.append(f"contract surface {surface_id} has unsafe source path: {source_text}")
                    continue
                if any(source_text.startswith(prefix.lstrip("/")) or source_text.startswith(prefix) for prefix in FORBIDDEN_SOURCE_PREFIXES):
                    failures.append(f"contract surface {surface_id} uses forbidden live-state source path: {source_text}")
                matched = tracked_under(source_text, tracked)
                if not matched:
                    failures.append(f"contract surface {surface_id} source path has no tracked files: {source_text}")

    forbidden_inputs = policy.get("forbidden_public_inputs")
    require(isinstance(forbidden_inputs, list) and bool(forbidden_inputs), "artifact signature policy must declare forbidden_public_inputs", failures)
    if isinstance(forbidden_inputs, list):
        for prefix in FORBIDDEN_SOURCE_PREFIXES:
            require(prefix in forbidden_inputs, f"forbidden_public_inputs must include {prefix}", failures)

    deferred_layers = policy.get("deferred_trust_layers")
    require(isinstance(deferred_layers, dict), "artifact signature policy must define deferred_trust_layers", failures)
    if isinstance(deferred_layers, dict):
        for layer in ("tuf", "scitt"):
            item = deferred_layers.get(layer)
            if not isinstance(item, dict):
                failures.append(f"deferred_trust_layers.{layer} must be an object")
                continue
            if item.get("action") not in ALLOWED_ACTIONS:
                failures.append(f"deferred_trust_layers.{layer}.action must be one of the allowed actions")
            for key in ("trigger", "reason"):
                if not isinstance(item.get(key), str) or not item.get(key):
                    failures.append(f"deferred_trust_layers.{layer}.{key} must be a non-empty string")

    if failures:
        return fail("artifact signature policy validation failed", failures)
    return ok("artifact signature policy validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
