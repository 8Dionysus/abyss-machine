from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import runtime_evidence_contracts
from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessActivationSmokePaths:
    stack_closure_dossier_latest: Path
    working_stack_latest: Path
    activation_smoke_latest: Path
    activation_smoke_root: Path
    episodes_latest: Path
    investigate_latest: Path
    replay_latest: Path


@dataclass(frozen=True)
class SelfAwarenessActivationSmokeConfig:
    schema_prefix: str
    version: str


@dataclass(frozen=True)
class SelfAwarenessActivationSmokeRuntimePort:
    load_latest_json: DocumentPort
    now_iso: DocumentPort
    write_latest_and_history: DocumentPort
    host_name: DocumentPort
    process_id: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessActivationSmokeRefreshPort:
    stack_closure_dossier: DocumentPort
    working_stack_inventory: DocumentPort
    episodes: DocumentPort


@dataclass(frozen=True)
class SelfAwarenessActivationSmokeContractPort:
    activation_missing_episode_services: DocumentPort
    movement_smoke_row: DocumentPort
    stack_organ_use_packet_complete: DocumentPort
    activation_smoke_row_complete: DocumentPort
    activation_smoke_compact: DocumentPort
    activation_smoke_complete: DocumentPort


def activation_smoke(
    write_latest: bool = True,
    *,
    stack_closure_dossier_doc: dict[str, Any] | None = None,
    working_stack_doc: dict[str, Any] | None = None,
    paths: SelfAwarenessActivationSmokePaths,
    config: SelfAwarenessActivationSmokeConfig,
    runtime_port: SelfAwarenessActivationSmokeRuntimePort,
    refresh_port: SelfAwarenessActivationSmokeRefreshPort,
    contract_port: SelfAwarenessActivationSmokeContractPort,
) -> dict[str, Any]:
    SCHEMA_PREFIX = config.schema_prefix
    VERSION = config.version
    SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH = paths.stack_closure_dossier_latest
    SELF_AWARENESS_WORKING_STACK_LATEST_PATH = paths.working_stack_latest
    SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH = paths.activation_smoke_latest
    SELF_AWARENESS_ACTIVATION_SMOKE_ROOT = paths.activation_smoke_root
    SELF_AWARENESS_EPISODES_LATEST_PATH = paths.episodes_latest
    SELF_AWARENESS_INVESTIGATE_LATEST_PATH = paths.investigate_latest
    SELF_AWARENESS_REPLAY_LATEST_PATH = paths.replay_latest
    load_latest_json = runtime_port.load_latest_json
    now_iso = runtime_port.now_iso
    write_latest_and_history = runtime_port.write_latest_and_history
    nested_get = self_awareness_contracts.nested_get
    safe_int = runtime_evidence_contracts.safe_int
    stable_hash_json = self_awareness_contracts.stable_hash_json
    self_awareness_stack_closure_dossier = refresh_port.stack_closure_dossier
    self_awareness_working_stack_inventory = refresh_port.working_stack_inventory
    self_awareness_episodes = refresh_port.episodes
    self_awareness_working_stack_activation_missing_episode_services = contract_port.activation_missing_episode_services
    self_awareness_working_stack_movement_smoke_row = contract_port.movement_smoke_row
    self_awareness_stack_organ_use_packet_complete = contract_port.stack_organ_use_packet_complete
    self_awareness_working_stack_activation_smoke_row_complete = contract_port.activation_smoke_row_complete
    self_awareness_working_stack_activation_smoke_compact = contract_port.activation_smoke_compact
    self_awareness_working_stack_activation_smoke_complete = contract_port.activation_smoke_complete
    generated_at = now_iso()
    run_id = "saactsmoke-" + stable_hash_json({"at": generated_at, "host": runtime_port.host_name(), "pid": runtime_port.process_id()}, length=16)
    working_stack_doc_supplied = isinstance(working_stack_doc, dict)
    stack_closure_dossier = stack_closure_dossier_doc if isinstance(stack_closure_dossier_doc, dict) else load_latest_json(SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1")
    if stack_closure_dossier.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_stack_closure_dossier_v1":
        stack_closure_dossier = self_awareness_stack_closure_dossier(write_latest=True)
    working_stack_doc = working_stack_doc if isinstance(working_stack_doc, dict) else load_latest_json(SELF_AWARENESS_WORKING_STACK_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1")
    if working_stack_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_working_stack_inventory_v1":
        working_stack_doc = self_awareness_working_stack_inventory(write_latest=True)
    working_stack_organs = [
        organ for organ in (working_stack_doc.get("organs") if isinstance(working_stack_doc.get("organs"), list) else [])
        if isinstance(organ, dict) and organ.get("service")
    ]
    expected_stack_organ_services = sorted(str(organ.get("service")) for organ in working_stack_organs)
    activation_dossier = stack_closure_dossier.get("working_stack_activation_dossier") if isinstance(stack_closure_dossier.get("working_stack_activation_dossier"), dict) else {}
    activation_entries = activation_dossier.get("entries") if isinstance(activation_dossier.get("entries"), list) else []
    activation_entry_by_service = {
        str(entry.get("service")): entry
        for entry in activation_entries
        if isinstance(entry, dict) and entry.get("service")
    }
    previous_smoke = load_latest_json(SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_smoke_v1")
    previous_by_service = previous_smoke.get("by_service") if isinstance(previous_smoke.get("by_service"), dict) else {}
    episodes_doc = load_latest_json(SELF_AWARENESS_EPISODES_LATEST_PATH, f"{SCHEMA_PREFIX}_self_awareness_episodes_v1")
    episode_identity_missing_before_refresh = self_awareness_working_stack_activation_missing_episode_services(activation_entries, episodes_doc)
    episodes_refreshed_for_identity = False
    if (
        episodes_doc.get("schema") != f"{SCHEMA_PREFIX}_self_awareness_episodes_v1"
        or safe_int(nested_get(episodes_doc, ["summary", "working_stack_gap_episodes"]), -1) < len(activation_entries)
        or episode_identity_missing_before_refresh
    ):
        if working_stack_doc_supplied:
            episodes_doc = self_awareness_episodes(write_latest=True, working_stack_doc=working_stack_doc)
        else:
            episodes_doc = self_awareness_episodes(write_latest=True)
        episodes_refreshed_for_identity = True
    episode_identity_missing_after_refresh = self_awareness_working_stack_activation_missing_episode_services(activation_entries, episodes_doc)

    rows: list[dict[str, Any]] = []
    for organ in working_stack_organs:
        if not isinstance(organ, dict) or not organ.get("service"):
            continue
        service = str(organ.get("service") or "")
        rows.append(self_awareness_working_stack_movement_smoke_row(
            organ,
            activation_entry_by_service.get(service),
            previous_by_service.get(service) if isinstance(previous_by_service.get(service), dict) else None,
            generated_at=generated_at,
            run_id=run_id,
        ))

    by_service = {
        str(row.get("service")): row
        for row in rows
        if isinstance(row, dict) and row.get("service")
    }
    stack_organ_use_packets = [
        row.get("stack_organ_use_packet")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("stack_organ_use_packet"), dict)
    ]
    stack_organ_use_packet_by_service = {
        str(packet.get("service")): packet
        for packet in stack_organ_use_packets
        if isinstance(packet, dict) and packet.get("service")
    }
    stack_organ_use_packet_services = sorted(str(service) for service in stack_organ_use_packet_by_service)
    stack_organs_without_use_packets = sorted(set(expected_stack_organ_services) - set(stack_organ_use_packet_services))
    all_stack_organs_have_use_packets = (
        bool(expected_stack_organ_services)
        and not stack_organs_without_use_packets
        and len(stack_organ_use_packets) == len(expected_stack_organ_services)
        and all(self_awareness_stack_organ_use_packet_complete(packet) for packet in stack_organ_use_packets)
    )
    failed_services = [str(row.get("service") or "unknown") for row in rows if not self_awareness_working_stack_activation_smoke_row_complete(row)]
    service_ids = [str(row.get("service")) for row in rows if isinstance(row, dict) and row.get("service")]
    selected_for_resident_reasoning = sorted(
        str(row.get("service"))
        for row in rows
        if nested_get(row, ["stack_organ_use_packet", "movement_selection", "selected_for_resident_reasoning"]) is True
    )
    selected_for_episode = sorted(
        str(row.get("service"))
        for row in rows
        if nested_get(row, ["stack_organ_use_packet", "movement_selection", "selected_for_episode"]) is True
    )
    movement_category_counts: dict[str, int] = {}
    for row in rows:
        categories = nested_get(row, ["stack_organ_use_packet", "movement_selection", "categories"])
        for category in categories if isinstance(categories, list) else []:
            key = str(category)
            movement_category_counts[key] = movement_category_counts.get(key, 0) + 1
    activation_gap_classifications = sorted({
        str(nested_get(packet, ["activation_gap", "classification"]))
        for packet in stack_organ_use_packets
        if nested_get(packet, ["activation_gap", "classification"])
    })
    data = {
        "schema": f"{SCHEMA_PREFIX}_self_awareness_working_stack_activation_smoke_v1",
        "version": VERSION,
        "generated_at": generated_at,
        "run_id": run_id,
        "ok": bool(rows) and all_stack_organs_have_use_packets and not failed_services and set(service_ids) == set(expected_stack_organ_services),
        "status": "complete" if bool(rows) and all_stack_organs_have_use_packets and not failed_services and set(service_ids) == set(expected_stack_organ_services) else "incomplete",
        "summary": {
            "activation_entries": len([entry for entry in activation_entries if isinstance(entry, dict) and entry.get("service")]),
            "stack_organs_expected": len(expected_stack_organ_services),
            "stack_organs_expected_services": expected_stack_organ_services,
            "rows": len(rows),
            "rows_ok": sum(1 for row in rows if self_awareness_working_stack_activation_smoke_row_complete(row)),
            "actual_investigation_runs": sum(1 for row in rows if nested_get(row, ["investigation", "actual_run"]) is True),
            "actual_replay_runs": sum(1 for row in rows if nested_get(row, ["replay", "actual_run"]) is True),
            "stack_organ_use_packets": len(stack_organ_use_packets),
            "stack_organ_use_packets_complete": sum(1 for packet in stack_organ_use_packets if self_awareness_stack_organ_use_packet_complete(packet)),
            "stack_organ_use_packet_services": stack_organ_use_packet_services,
            "stack_organs_without_use_packets": stack_organs_without_use_packets,
            "all_stack_organs_have_use_packets": all_stack_organs_have_use_packets,
            "selected_for_episode": selected_for_episode,
            "selected_for_resident_reasoning": selected_for_resident_reasoning,
            "movement_category_counts": movement_category_counts,
            "activation_gap_classifications": activation_gap_classifications,
            "divergences": sum(safe_int(nested_get(row, ["replay", "divergences"]), 0) for row in rows),
            "failed_services": failed_services,
            "service_ids": service_ids,
            "open_activation_gaps": safe_int(nested_get(activation_dossier, ["summary", "open_activation_gaps"]), len(rows)),
            "episode_identity_missing_before_refresh": episode_identity_missing_before_refresh,
            "episodes_refreshed_for_identity": episodes_refreshed_for_identity,
            "episode_identity_missing_after_refresh": episode_identity_missing_after_refresh,
            "latest_artifact_overwrite_note": "investigate/latest.json and replay/latest.json contain the last row run; this matrix preserves every per-service thread and replay result.",
        },
        "rows": rows,
        "by_service": by_service,
        "stack_organ_use_packets": stack_organ_use_packets,
        "stack_organ_use_packet_by_service": stack_organ_use_packet_by_service,
        "compact_by_service": {
            service: self_awareness_working_stack_activation_smoke_compact(row)
            for service, row in by_service.items()
        },
        "activation_dossier_summary": activation_dossier.get("summary") if isinstance(activation_dossier.get("summary"), dict) else {},
        "source_commands": {
            "activation_smoke": "abyss-machine self-awareness activation-smoke --json",
            "stack_closure_dossier": "abyss-machine self-awareness stack-closure-dossier --json",
            "episodes": "abyss-machine self-awareness episodes --json",
            "investigate": "abyss-machine self-awareness investigate --episode-id EPISODE_ID --json",
            "replay": "abyss-machine self-awareness replay --thread-id THREAD_ID --json",
        },
        "evidence_refs": [
            {"path": str(SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH), "section": "working_stack_activation_dossier"},
            {"path": str(SELF_AWARENESS_EPISODES_LATEST_PATH), "section": "working_stack_gap_episodes"},
            *[
                {"path": str(SELF_AWARENESS_INVESTIGATE_LATEST_PATH), "thread_id": nested_get(row, ["investigation", "thread_id"]), "service": row.get("service")}
                for row in rows
                if nested_get(row, ["investigation", "thread_id"])
            ],
            *[
                {"path": str(SELF_AWARENESS_REPLAY_LATEST_PATH), "thread_id": nested_get(row, ["replay", "thread_id"]), "service": row.get("service")}
                for row in rows
                if nested_get(row, ["replay", "thread_id"])
            ],
        ],
        "policy": {
            "readmodel_smoke": True,
            "per_service_actual_investigate_replay": True,
            "read_only": True,
            "handoff_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
            "open_activation_gaps_are_unexhausted_potential_not_host_failures": True,
        },
    }
    data["complete"] = self_awareness_working_stack_activation_smoke_complete(data)
    if write_latest:
        errors = write_latest_and_history(data, SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH, SELF_AWARENESS_ACTIVATION_SMOKE_ROOT)
        if errors:
            data["ok"] = False
            data["complete"] = False
            data["write_errors"] = errors
    return data
