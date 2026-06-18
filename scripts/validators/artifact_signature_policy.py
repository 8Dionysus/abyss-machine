#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

from _common import REPO_ROOT, fail, load_json, ok, rel, require


POLICY = REPO_ROOT / "manifests" / "artifact_signature_policy.manifest.json"
VALIDATION_LANES = REPO_ROOT / "docs" / "validation" / "validation_lanes.json"
GENERATED_SURFACE = "generated/contract_abi_signatures.min.json"
REQUIRED_POLICY_KEYS = ("abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign", "c2pa")
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
    return {line for line in result.stdout.splitlines() if line}


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

    if failures:
        return fail("artifact signature policy validation failed", failures)
    return ok("artifact signature policy validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
