#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / "validation" / "validation_lanes.json"
REQUIRED_RUNNER_CONTEXTS = {
    "os_abyss_local_cli",
    "os_abyss_host_scheduler",
    "release_pipeline",
}
REQUIRED_CONTEXTS_BY_LANE = {
    "source-fast": {"os_abyss_local_cli"},
    "release-artifact": {"os_abyss_local_cli", "release_pipeline"},
}


@dataclass(frozen=True)
class CommandStep:
    label: str
    command: tuple[str, ...]


class ManifestError(ValueError):
    pass


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"missing validation lane manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path} must contain valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("validation lane manifest must contain a JSON object")
    validate_manifest(payload)
    return payload


def validate_manifest(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ManifestError("validation lane manifest schema_version must be 1")
    lanes = payload.get("lanes")
    sequences = payload.get("command_sequences")
    runner_contexts = payload.get("runner_contexts")
    if not isinstance(lanes, dict) or not lanes:
        raise ManifestError("validation lane manifest must define lanes")
    if not isinstance(sequences, dict) or not sequences:
        raise ManifestError("validation lane manifest must define command_sequences")
    if not isinstance(runner_contexts, dict) or not runner_contexts:
        raise ManifestError("validation lane manifest must define runner_contexts")

    missing_contexts = sorted(REQUIRED_RUNNER_CONTEXTS - set(runner_contexts))
    if missing_contexts:
        raise ManifestError(f"validation lane manifest missing runner_contexts: {', '.join(missing_contexts)}")

    for context_id, context in runner_contexts.items():
        if not isinstance(context, dict):
            raise ManifestError(f"runner_context {context_id!r} must be an object")
        for key in ("role", "runner_type"):
            if not isinstance(context.get(key), str) or not context[key]:
                raise ManifestError(f"runner_context {context_id!r} must define {key}")
        if not isinstance(context.get("requires_private_host_state"), bool):
            raise ManifestError(f"runner_context {context_id!r} must define boolean requires_private_host_state")

    for lane_id, lane in lanes.items():
        if not isinstance(lane, dict):
            raise ManifestError(f"lane {lane_id!r} must be an object")
        sequence_id = lane.get("command_sequence")
        if not isinstance(sequence_id, str) or not sequence_id:
            raise ManifestError(f"lane {lane_id!r} must name a command_sequence")
        if sequence_id not in sequences:
            raise ManifestError(f"lane {lane_id!r} references missing command_sequence {sequence_id!r}")
        for key in ("owner_surface", "failure_route"):
            if not isinstance(lane.get(key), str) or not lane[key]:
                raise ManifestError(f"lane {lane_id!r} must define {key}")
        lane_contexts = lane.get("runner_contexts")
        if not isinstance(lane_contexts, list) or not lane_contexts:
            raise ManifestError(f"lane {lane_id!r} must define runner_contexts")
        if not all(isinstance(item, str) and item for item in lane_contexts):
            raise ManifestError(f"lane {lane_id!r} runner_contexts must be non-empty strings")
        unknown_contexts = sorted(set(lane_contexts) - set(runner_contexts))
        if unknown_contexts:
            raise ManifestError(f"lane {lane_id!r} references unknown runner_contexts: {', '.join(unknown_contexts)}")
        required_contexts = REQUIRED_CONTEXTS_BY_LANE.get(lane_id, set())
        missing_required = sorted(required_contexts - set(lane_contexts))
        if missing_required:
            raise ManifestError(f"lane {lane_id!r} missing required runner_contexts: {', '.join(missing_required)}")
        public_safe = lane.get("public_safe")
        if not isinstance(public_safe, bool):
            raise ManifestError(f"lane {lane_id!r} must define boolean public_safe")
        if public_safe:
            private_contexts = sorted(
                context_id
                for context_id in lane_contexts
                if runner_contexts[context_id].get("requires_private_host_state") is True
            )
            if private_contexts:
                raise ManifestError(
                    f"lane {lane_id!r} is public_safe but uses private runner_contexts: {', '.join(private_contexts)}"
                )

    for sequence_id, steps in sequences.items():
        if not isinstance(steps, list) or not steps:
            raise ManifestError(f"command_sequence {sequence_id!r} must be a non-empty list")
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ManifestError(f"{sequence_id}[{index}] must be an object")
            label = step.get("label")
            command = step.get("command")
            if not isinstance(label, str) or not label:
                raise ManifestError(f"{sequence_id}[{index}] must have a label")
            if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                raise ManifestError(f"{sequence_id}[{index}] must have a string command list")


def lane_ids(path: Path = MANIFEST_PATH) -> tuple[str, ...]:
    return tuple(sorted(load_manifest(path)["lanes"]))


def lane_command_sequence(lane_id: str, path: Path = MANIFEST_PATH) -> tuple[CommandStep, ...]:
    manifest = load_manifest(path)
    lanes = manifest["lanes"]
    if lane_id not in lanes:
        available = ", ".join(sorted(lanes))
        raise ManifestError(f"unknown validation lane {lane_id!r}; available lanes: {available}")
    return command_sequence(lanes[lane_id]["command_sequence"], path)


def command_sequence(sequence_id: str, path: Path = MANIFEST_PATH) -> tuple[CommandStep, ...]:
    manifest = load_manifest(path)
    sequences = manifest["command_sequences"]
    if sequence_id not in sequences:
        available = ", ".join(sorted(sequences))
        raise ManifestError(f"unknown command sequence {sequence_id!r}; available sequences: {available}")
    steps = []
    for step in sequences[sequence_id]:
        command = tuple(sys.executable if part == "python" else part for part in step["command"])
        steps.append(CommandStep(label=step["label"], command=command))
    return tuple(steps)


def main() -> int:
    try:
        manifest = load_manifest()
    except ManifestError as exc:
        print(f"[fail] validation lane manifest failed: {exc}")
        return 1
    print("[ok] validation lane manifest passed")
    for lane_id in sorted(manifest["lanes"]):
        lane = manifest["lanes"][lane_id]
        contexts = ", ".join(lane["runner_contexts"])
        print(f"- {lane_id}: {lane['command_sequence']} [{contexts}] -> {lane['failure_route']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
