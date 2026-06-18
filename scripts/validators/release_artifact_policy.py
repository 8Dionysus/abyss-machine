#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import subprocess
from typing import Any

from _common import REPO_ROOT, fail, load_json, ok, require


POLICY = REPO_ROOT / "manifests" / "artifact_signature_policy.manifest.json"
ALLOWED_CONTROLS = {"abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign", "c2pa"}
PUBLISHABLE_REQUIRED_CONTROLS = {"sbom", "slsa_in_toto", "sigstore_cosign", "c2pa"}
VALID_PUBLIC_REPO_POLICIES = {"not_tracked", "source_review_required"}
NON_PUBLISHABLE_CLASSES = {"host_local_evidence"}


def tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return {line for line in result.stdout.splitlines() if line}


def matches_any(path_text: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_text, pattern) for pattern in patterns)


def control_required(class_rule: dict[str, Any], control: str) -> bool:
    rule = class_rule.get(control)
    return isinstance(rule, dict) and bool(rule.get("required"))


def main() -> int:
    policy = load_json(POLICY)
    classes = policy.get("artifact_classes")
    rules = policy.get("release_artifact_rules")
    tracked = tracked_files()
    failures: list[str] = []

    require(isinstance(classes, dict) and bool(classes), "artifact signature policy must define artifact_classes", failures)
    require(isinstance(rules, list) and bool(rules), "artifact signature policy must define release_artifact_rules", failures)
    if not isinstance(classes, dict) or not isinstance(rules, list):
        return fail("release artifact policy validation failed", failures)

    seen_rule_ids: set[str] = set()
    covered_classes: set[str] = set()
    matched_tracked_artifacts: list[str] = []

    for rule in rules:
        if not isinstance(rule, dict):
            failures.append("release artifact rules must be objects")
            continue
        rule_id = str(rule.get("id") or "")
        artifact_class = str(rule.get("artifact_class") or "")
        patterns = [str(item) for item in rule.get("artifact_patterns", [])]
        required_controls = [str(item) for item in rule.get("required_controls", [])]
        sidecars = rule.get("sidecar_extensions", {})
        public_repo_policy = str(rule.get("public_repo_policy") or "")
        staging_route = str(rule.get("staging_route") or "")

        if not rule_id:
            failures.append("release artifact rule must define id")
        elif rule_id in seen_rule_ids:
            failures.append(f"duplicate release artifact rule id: {rule_id}")
        seen_rule_ids.add(rule_id)

        if artifact_class in NON_PUBLISHABLE_CLASSES:
            failures.append(f"release artifact rule {rule_id} must not publish {artifact_class}")
        if artifact_class not in classes:
            failures.append(f"release artifact rule {rule_id} references unknown artifact_class {artifact_class}")
            continue
        covered_classes.add(artifact_class)

        if public_repo_policy not in VALID_PUBLIC_REPO_POLICIES:
            failures.append(f"release artifact rule {rule_id} has invalid public_repo_policy {public_repo_policy}")
        if public_repo_policy == "not_tracked" and not staging_route.startswith("/srv/abyss-machine/artifacts"):
            failures.append(f"release artifact rule {rule_id} must stage outside the repo under /srv/abyss-machine/artifacts")
        if not patterns:
            failures.append(f"release artifact rule {rule_id} must define artifact_patterns")
        if not required_controls:
            failures.append(f"release artifact rule {rule_id} must define required_controls")

        class_rule = classes[artifact_class]
        if not isinstance(class_rule, dict):
            failures.append(f"artifact class {artifact_class} must be an object")
            continue
        for control in required_controls:
            if control not in ALLOWED_CONTROLS:
                failures.append(f"release artifact rule {rule_id} has unknown control {control}")
                continue
            if not control_required(class_rule, control):
                failures.append(f"release artifact rule {rule_id} requires {control}, but artifact class {artifact_class} does not")
            if control in PUBLISHABLE_REQUIRED_CONTROLS:
                extensions = sidecars.get(control) if isinstance(sidecars, dict) else None
                if not isinstance(extensions, list) or not extensions:
                    failures.append(f"release artifact rule {rule_id} must define sidecar_extensions for {control}")

        if public_repo_policy == "not_tracked":
            matched = sorted(path for path in tracked if matches_any(path, patterns))
            matched_tracked_artifacts.extend(f"{rule_id}: {path}" for path in matched)

    for class_id, class_rule in sorted(classes.items()):
        if not isinstance(class_rule, dict) or class_id in NON_PUBLISHABLE_CLASSES:
            continue
        needs_release_rule = any(control_required(class_rule, control) for control in PUBLISHABLE_REQUIRED_CONTROLS)
        if needs_release_rule and class_id not in covered_classes:
            failures.append(f"artifact class {class_id} has publishable signing/provenance requirements but no release_artifact_rule")

    if matched_tracked_artifacts:
        failures.append("publishable release artifacts must not be tracked in the public source repo:")
        failures.extend(matched_tracked_artifacts)

    if failures:
        return fail("release artifact policy validation failed", failures)
    return ok("release artifact policy validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
