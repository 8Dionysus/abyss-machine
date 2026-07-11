from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import runtime_evidence_contracts
from . import self_awareness_contracts


DocumentPort = Callable[..., Any]


@dataclass(frozen=True)
class SelfAwarenessActivationPaths:
    stack_closure_dossier_latest: Path
    episodes_latest: Path
    investigate_latest: Path
    replay_latest: Path
    working_stack_latest: Path
    activation_smoke_latest: Path
    autolink_latest: Path
    completion_audit_latest: Path


@dataclass(frozen=True)
class SelfAwarenessActivationConfig:
    schema_prefix: str
    investigation_node_count: int


@dataclass(frozen=True)
class SelfAwarenessActivationContractPort:
    event_issues: DocumentPort
    make_event: DocumentPort
    investigation_working_stack_gap_complete: DocumentPort
    resident_cognitive_replay_complete: DocumentPort
    activation_closure_acceptance_complete: DocumentPort
    activation_gap_classification: DocumentPort
    activation_gap_route: DocumentPort
    activation_gap_route_complete: DocumentPort
    activation_synthetic_scenario_complete: DocumentPort


def stack_organ_signal_route(service: str, organ: Mapping[str, Any]) -> dict[str, str]:
    service_l = service.lower()
    if service_l in {"prometheus"}:
        return {"signal": "metric", "source": "prometheus"}
    if service_l in {"loki"}:
        return {"signal": "log", "source": "loki"}
    if service_l in {"grafana"}:
        return {"signal": "service", "source": "grafana"}
    if service_l in {"alertmanager"}:
        return {"signal": "alert", "source": "alertmanager"}
    if service_l in {"alloy", "tempo"}:
        return {
            "signal": "trace_context",
            "source": "alloy" if service_l == "alloy" else "observability",
        }
    if service_l in {"postgres"}:
        return {"signal": "memory", "source": "postgres"}
    if service_l in {"neo4j"}:
        return {"signal": "memory", "source": "neo4j"}
    if service_l in {"rag-api", "qdrant", "rerank-api"}:
        return {
            "signal": "rag",
            "source": "rag-api" if service_l == "rag-api" else "rag",
        }
    if service_l in {"embeddings"}:
        return {"signal": "model", "source": "embeddings"}
    if service_l in {"route-api"}:
        return {"signal": "service", "source": "route-api"}
    if service_l in {"langchain-api", "langchain-api-llamacpp"}:
        return {"signal": "model", "source": "langchain-api"}
    if service_l in {"llama-cpp", "llm-registry", "litellm", "ollama", "ovms"}:
        return {"signal": "model", "source": "llm"}
    if "tts" in service_l or service_l in {"qwen-tts", "babelvox-tts"}:
        return {"signal": "model", "source": "tts"}
    if service_l == "stt":
        return {"signal": "model", "source": "stt"}
    if service_l in {"redis"}:
        return {"signal": "memory", "source": "memory"}
    if service_l in {"cadvisor"}:
        return {"signal": "container", "source": "processes"}
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    if runtime.get("container"):
        return {"signal": "container", "source": "podman"}
    return {"signal": "service", "source": "working-stack"}


def stack_organ_state_digest(organ: Mapping[str, Any]) -> str:
    endpoint_probes = (
        organ.get("endpoint_probes")
        if isinstance(organ.get("endpoint_probes"), list)
        else []
    )
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    return self_awareness_contracts.stable_hash_json(
        {
            "service": organ.get("service"),
            "machine_usage_status": organ.get("machine_usage_status"),
            "usage_gap": organ.get("usage_gap"),
            "runtime": {
                "container": runtime.get("container"),
                "pid": runtime.get("pid"),
                "pid_alive": runtime.get("pid_alive"),
                "running": runtime.get("running"),
                "state": runtime.get("state"),
                "health": runtime.get("health"),
                "restart_count": runtime.get("restart_count"),
            },
            "endpoint_ok": organ.get("endpoint_ok"),
            "endpoint_probes": [
                {
                    "probe": probe.get("probe"),
                    "ok": probe.get("ok"),
                    "status_code": probe.get("status_code"),
                    "error": probe.get("error"),
                }
                for probe in endpoint_probes
                if isinstance(probe, Mapping)
            ],
            "model_bridge": organ.get("model_bridge")
            if isinstance(organ.get("model_bridge"), Mapping)
            else {},
            "deep_usage_proven": organ.get("deep_usage_proven"),
        },
        length=24,
    )


def stack_organ_movement_selection(
    organ: Mapping[str, Any],
    *,
    current_state_digest: str,
    previous_row: Mapping[str, Any] | None,
    schema_prefix: str,
) -> dict[str, Any]:
    service = str(organ.get("service") or "")
    runtime = organ.get("runtime") if isinstance(organ.get("runtime"), Mapping) else {}
    declared = (
        organ.get("declared") if isinstance(organ.get("declared"), Mapping) else {}
    )
    status = str(organ.get("machine_usage_status") or "")
    endpoint_probes = (
        organ.get("endpoint_probes")
        if isinstance(organ.get("endpoint_probes"), list)
        else []
    )
    failed_probe_names = [
        str(probe.get("probe"))
        for probe in endpoint_probes
        if isinstance(probe, Mapping)
        and probe.get("ok") is not True
        and probe.get("probe")
    ]
    previous_digest = self_awareness_contracts.nested_get(
        previous_row or {},
        ["stack_organ_use_packet", "current_state", "current_state_digest"],
    )
    categories = ["raw_signal"]
    reasons: list[str] = ["organ observed in working-stack inventory"]
    state_changed = bool(previous_digest and previous_digest != current_state_digest)
    if previous_digest is None:
        reasons.append("baseline movement packet")
    elif state_changed:
        categories.append("state_change")
        reasons.append("state digest changed since previous activation-smoke")
    degradation_reasons: list[str] = []
    if organ.get("usage_gap"):
        degradation_reasons.append("usage_gap")
    runtime_expected = bool(
        runtime
        and declared.get("present") is True
        and (not status.startswith("policy_deferred_"))
        and (status not in {"active_model_root_bridge", "recent_on_demand_tool_signal"})
    )
    if runtime_expected and runtime.get("running") is False:
        degradation_reasons.append("runtime_not_running")
    if failed_probe_names:
        degradation_reasons.append("failed_endpoint_probe")
    if status.endswith("_degraded"):
        degradation_reasons.append("degraded_status")
    if degradation_reasons:
        categories.append("degradation")
        reasons.extend(degradation_reasons)
    if self_awareness_contracts.nested_get(
        organ, ["time_space_context_link", "link_id"]
    ):
        categories.append("correlation_candidate")
    selected_for_episode = bool(state_changed or degradation_reasons)
    if selected_for_episode:
        categories.append("episode_candidate")
    selected_for_resident = bool(degradation_reasons)
    if selected_for_resident:
        categories.append("needs_resident_reasoning")
    elif not selected_for_episode and previous_digest is not None:
        categories.append("ignore/noise")
    return {
        "schema": f"{schema_prefix}_self_awareness_stack_organ_movement_selection_v1",
        "service": service,
        "categories": list(dict.fromkeys(categories)),
        "state_changed": state_changed,
        "previous_state_digest": previous_digest,
        "current_state_digest": current_state_digest,
        "selected_for_timeline": True,
        "selected_for_spatial_graph": True,
        "selected_for_episode": selected_for_episode,
        "selected_for_resident_reasoning": selected_for_resident,
        "selected_reason": "; ".join(reasons)
        if selected_for_episode or selected_for_resident
        else None,
        "not_selected_reason": None
        if selected_for_episode or selected_for_resident
        else "stable observation retained as raw signal and spatial context",
        "degradation_reasons": degradation_reasons,
        "failed_probe_names": failed_probe_names,
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "automatic_remediation": False,
        },
    }


def working_stack_activation_episode_for_entry(
    entry: dict[str, Any], episodes_doc: dict[str, Any]
) -> dict[str, Any]:
    service = str(entry.get("service") or "")
    status = str(entry.get("machine_usage_status") or "")
    link_id = str(entry.get("working_stack_link_id") or "")
    episodes = (
        episodes_doc.get("episodes")
        if isinstance(episodes_doc.get("episodes"), list)
        else []
    )
    for episode in episodes:
        if (
            not isinstance(episode, dict)
            or episode.get("episode_kind") != "working_stack_usage_gap"
        ):
            continue
        gap = (
            episode.get("working_stack_gap")
            if isinstance(episode.get("working_stack_gap"), dict)
            else {}
        )
        if (
            str(gap.get("service") or episode.get("service") or "") == service
            and str(gap.get("machine_usage_status") or "") == status
            and (
                str(
                    gap.get("working_stack_link_id")
                    or episode.get("working_stack_link_id")
                    or ""
                )
                == link_id
            )
        ):
            return episode
    return {}


def working_stack_activation_missing_episode_services(
    activation_entries: list[dict[str, Any]], episodes_doc: dict[str, Any]
) -> list[str]:
    missing: list[str] = []
    for entry in activation_entries:
        if not isinstance(entry, dict) or not entry.get("service"):
            continue
        if not working_stack_activation_episode_for_entry(entry, episodes_doc):
            missing.append(str(entry.get("service")))
    return missing


def working_stack_organ_entry(
    organ: dict[str, Any],
    activation_entry: dict[str, Any] | None = None,
    *,
    state_digest: Callable[[Mapping[str, Any]], str] | None = None,
) -> dict[str, Any]:
    activation_entry = activation_entry if isinstance(activation_entry, dict) else {}
    entry = dict(organ)
    link = (
        organ.get("time_space_context_link")
        if isinstance(organ.get("time_space_context_link"), dict)
        else {}
    )
    endpoint_probes = (
        organ.get("endpoint_probes")
        if isinstance(organ.get("endpoint_probes"), list)
        else []
    )
    entry.update(
        {
            "working_stack_link_id": activation_entry.get("working_stack_link_id")
            or link.get("link_id"),
            "usage_gap": activation_entry.get("usage_gap") or organ.get("usage_gap"),
            "activation_kind": activation_entry.get("activation_kind")
            or "organ_movement",
            "coverage_planes": activation_entry.get("coverage_planes")
            if isinstance(activation_entry.get("coverage_planes"), list)
            else ["working_stack", "movement"],
            "closure_blocker_keys": activation_entry.get("closure_blocker_keys")
            if isinstance(activation_entry.get("closure_blocker_keys"), list)
            else [],
            "missing_checks": activation_entry.get("missing_checks")
            if isinstance(activation_entry.get("missing_checks"), list)
            else [],
            "fulfilled_checks": activation_entry.get("fulfilled_checks")
            if isinstance(activation_entry.get("fulfilled_checks"), list)
            else [],
            "closure_acceptance": activation_entry.get("closure_acceptance")
            if isinstance(activation_entry.get("closure_acceptance"), dict)
            else {},
            "synthetic_scenario": activation_entry.get("synthetic_scenario")
            if isinstance(activation_entry.get("synthetic_scenario"), dict)
            else {},
            "ok_probe_names": [
                str(probe.get("probe"))
                for probe in endpoint_probes
                if isinstance(probe, dict)
                and probe.get("ok") is True
                and probe.get("probe")
            ],
            "failed_probe_names": [
                str(probe.get("probe"))
                for probe in endpoint_probes
                if isinstance(probe, dict)
                and probe.get("ok") is not True
                and probe.get("probe")
            ],
            "current_state_digest": (state_digest or stack_organ_state_digest)(organ),
            "current_state": {
                "runtime": organ.get("runtime")
                if isinstance(organ.get("runtime"), dict)
                else {},
                "declared": organ.get("declared")
                if isinstance(organ.get("declared"), dict)
                else {},
                "roots": {
                    "service_roots": organ.get("service_roots"),
                    "model_roots": organ.get("model_roots"),
                },
                "endpoint_ok": organ.get("endpoint_ok"),
                "endpoint_probes": endpoint_probes,
                "model_bridge": organ.get("model_bridge")
                if isinstance(organ.get("model_bridge"), dict)
                else {},
                "deep_usage_proven": organ.get("deep_usage_proven"),
            },
        }
    )
    return entry


def working_stack_activation_smoke_row(
    entry: dict[str, Any],
    *,
    generated_at: str,
    run_id: str,
    episode: dict[str, Any],
    investigation: dict[str, Any],
    replay: dict[str, Any],
    paths: SelfAwarenessActivationPaths,
    config: SelfAwarenessActivationConfig,
    contract_port: SelfAwarenessActivationContractPort,
) -> dict[str, Any]:
    service = str(entry.get("service") or "")
    status = str(entry.get("machine_usage_status") or "")
    link_id = str(entry.get("working_stack_link_id") or "")
    episode_id = str(episode.get("episode_id") or "")
    working_gap = (
        investigation.get("working_stack_gap")
        if isinstance(investigation.get("working_stack_gap"), dict)
        else {}
    )
    replay_gap = (
        replay.get("working_stack_gap_replay")
        if isinstance(replay.get("working_stack_gap_replay"), dict)
        else {}
    )
    resident_replay = (
        replay.get("resident_cognitive_replay")
        if isinstance(replay.get("resident_cognitive_replay"), dict)
        else {}
    )
    inv_thread_id = str(investigation.get("thread_id") or "")
    replay_thread_id = str(replay.get("thread_id") or "")
    inv_matches = (
        investigation.get("ok") is True
        and str(
            investigation.get("selected_episode_id")
            or self_awareness_contracts.nested_get(
                investigation, ["summary", "selected_episode"]
            )
            or ""
        )
        == episode_id
        and (str(working_gap.get("selected_episode_id") or "") == episode_id)
        and (str(working_gap.get("service") or "") == service)
        and (str(working_gap.get("machine_usage_status") or "") == status)
        and (str(working_gap.get("working_stack_link_id") or "") == link_id)
        and contract_port.investigation_working_stack_gap_complete(working_gap)
        and (
            runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    investigation, ["summary", "evidence_validation_fails"]
                ),
                0,
            )
            == 0
        )
        and (
            self_awareness_contracts.nested_get(
                investigation, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                investigation, ["policy", "action_execution"]
            )
            is False
        )
    )
    replay_matches = (
        replay.get("ok") is True
        and replay_thread_id == inv_thread_id
        and (str(replay_gap.get("service") or "") == service)
        and (str(replay_gap.get("machine_usage_status") or "") == status)
        and (str(replay_gap.get("working_stack_link_id") or "") == link_id)
        and (replay_gap.get("selected") is True)
        and (replay_gap.get("replayable") is True)
        and (
            runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(replay, ["summary", "divergences"]),
                -1,
            )
            == 0
        )
        and (
            self_awareness_contracts.nested_get(
                replay, ["stack_handoff_replay", "closure_readiness_replayable"]
            )
            is True
        )
        and contract_port.resident_cognitive_replay_complete(resident_replay)
        and (
            self_awareness_contracts.nested_get(
                replay, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(replay, ["policy", "action_execution"])
            is False
        )
    )
    row_ok = bool(
        service and status and link_id and episode_id and inv_matches and replay_matches
    )
    row = {
        "schema": f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_row_v1",
        "run_id": run_id,
        "generated_at": generated_at,
        "service": service,
        "owner": "abyss-stack",
        "machine_usage_status": status,
        "usage_gap": entry.get("usage_gap"),
        "working_stack_link_id": link_id or None,
        "episode_id": episode_id or None,
        "ok": row_ok,
        "investigation": {
            "schema": f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_investigation_v1",
            "ok": investigation.get("ok") is True,
            "thread_id": inv_thread_id or None,
            "selected_episode_id": investigation.get("selected_episode_id")
            or self_awareness_contracts.nested_get(
                investigation, ["summary", "selected_episode"]
            ),
            "selected_episode_matches": str(
                investigation.get("selected_episode_id")
                or self_awareness_contracts.nested_get(
                    investigation, ["summary", "selected_episode"]
                )
                or ""
            )
            == episode_id,
            "working_stack_gap_complete": contract_port.investigation_working_stack_gap_complete(
                working_gap
            ),
            "working_stack_gap_matches": bool(inv_matches),
            "checkpoints": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    investigation, ["summary", "checkpoints"]
                ),
                0,
            ),
            "graph_nodes": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    investigation, ["summary", "graph_nodes"]
                ),
                0,
            ),
            "evidence_validation_fails": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    investigation, ["summary", "evidence_validation_fails"]
                ),
                0,
            ),
            "resident_worker_detail_complete": self_awareness_contracts.nested_get(
                investigation, ["summary", "resident_worker_detail_complete"]
            ),
            "resident_cognitive_packet_complete": self_awareness_contracts.nested_get(
                investigation, ["summary", "resident_cognitive_packet_complete"]
            ),
            "read_only_tools": self_awareness_contracts.nested_get(
                investigation, ["summary", "read_only_tools"]
            ),
            "hypothesis_tests": self_awareness_contracts.nested_get(
                investigation, ["summary", "hypothesis_tests"]
            ),
            "contradiction_notes": self_awareness_contracts.nested_get(
                investigation, ["summary", "contradiction_notes"]
            ),
        },
        "replay": {
            "schema": f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_replay_v1",
            "ok": replay.get("ok") is True,
            "thread_id": replay_thread_id or None,
            "thread_matches": replay_thread_id == inv_thread_id,
            "working_stack_gap_selected": self_awareness_contracts.nested_get(
                replay, ["summary", "working_stack_gap_selected"]
            ),
            "working_stack_gap_replayable": self_awareness_contracts.nested_get(
                replay, ["summary", "working_stack_gap_replayable"]
            ),
            "working_stack_gap_matches": bool(replay_matches),
            "divergences": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(replay, ["summary", "divergences"]),
                -1,
            ),
            "node_order": self_awareness_contracts.nested_get(
                replay, ["summary", "node_order"]
            )
            if isinstance(
                self_awareness_contracts.nested_get(replay, ["summary", "node_order"]),
                list,
            )
            else [],
            "stack_handoff_closure_readiness_replayable": self_awareness_contracts.nested_get(
                replay, ["stack_handoff_replay", "closure_readiness_replayable"]
            ),
            "resident_cognitive_replay_complete": resident_replay.get("complete"),
            "resident_cognitive_read_only_tools": self_awareness_contracts.nested_get(
                resident_replay, ["summary", "read_only_tools"]
            ),
            "resident_cognitive_hypothesis_tests": self_awareness_contracts.nested_get(
                resident_replay, ["summary", "hypothesis_tests"]
            ),
            "resident_cognitive_contradiction_notes": self_awareness_contracts.nested_get(
                resident_replay, ["summary", "contradiction_notes"]
            ),
        },
        "commands": {
            "investigate": f"abyss-machine self-awareness investigate --episode-id {episode_id or 'EPISODE_ID'} --json",
            "replay": f"abyss-machine self-awareness replay --thread-id {inv_thread_id or 'THREAD_ID'} --json",
        },
        "evidence_refs": [
            {
                "path": str(paths.stack_closure_dossier_latest),
                "service": service,
                "section": "working_stack_activation_dossier",
            },
            {
                "path": str(paths.episodes_latest),
                "episode_id": episode_id or None,
                "service": service,
            },
            {
                "path": str(paths.investigate_latest),
                "thread_id": inv_thread_id or None,
                "service": service,
            },
            {
                "path": str(paths.replay_latest),
                "thread_id": replay_thread_id or None,
                "service": service,
            },
        ],
        "policy": {
            "readmodel_smoke": True,
            "actual_investigate_replay_run": True,
            "handoff_only": True,
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
            "latest_investigate_replay_artifacts_are_overwritten_per_row": True,
        },
    }
    row["stack_organ_use_packet"] = stack_organ_use_packet(
        entry,
        row,
        generated_at=generated_at,
        run_id=run_id,
        paths=paths,
        config=config,
        contract_port=contract_port,
    )
    row["complete"] = working_stack_activation_smoke_row_complete(
        row,
        schema_prefix=config.schema_prefix,
        investigation_node_count=config.investigation_node_count,
        event_issues=contract_port.event_issues,
    )
    return row


def working_stack_movement_smoke_row(
    organ: dict[str, Any],
    activation_entry: dict[str, Any] | None,
    previous_row: dict[str, Any] | None,
    *,
    generated_at: str,
    run_id: str,
    paths: SelfAwarenessActivationPaths,
    config: SelfAwarenessActivationConfig,
    contract_port: SelfAwarenessActivationContractPort,
) -> dict[str, Any]:
    entry = working_stack_organ_entry(
        organ, activation_entry, state_digest=stack_organ_state_digest
    )
    service = str(entry.get("service") or "")
    status = str(entry.get("machine_usage_status") or "")
    link_id = str(entry.get("working_stack_link_id") or "")
    row = {
        "schema": f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_row_v1",
        "row_kind": "organ_movement",
        "run_id": run_id,
        "generated_at": generated_at,
        "service": service,
        "owner": "abyss-stack",
        "machine_usage_status": status,
        "usage_gap": entry.get("usage_gap"),
        "working_stack_link_id": link_id or None,
        "episode_id": None,
        "ok": False,
        "investigation": {
            "schema": f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_investigation_v1",
            "actual_run": False,
            "ok": None,
            "thread_id": None,
            "selected_episode_id": None,
            "selected_episode_matches": None,
            "working_stack_gap_complete": None,
            "working_stack_gap_matches": None,
            "resident_cognitive_packet_complete": None,
        },
        "replay": {
            "schema": f"{config.schema_prefix}_self_awareness_working_stack_activation_smoke_replay_v1",
            "actual_run": False,
            "ok": None,
            "thread_id": None,
            "thread_matches": None,
            "working_stack_gap_selected": None,
            "working_stack_gap_replayable": None,
            "working_stack_gap_matches": None,
            "divergences": None,
            "resident_cognitive_replay_complete": None,
        },
        "commands": {
            "movement": "abyss-machine self-awareness activation-smoke --json",
            "source": "abyss-machine self-awareness working-stack --json",
        },
        "evidence_refs": [
            {
                "path": str(paths.working_stack_latest),
                "service": service,
                "section": "organs",
            },
            {
                "path": str(paths.activation_smoke_latest),
                "service": service,
                "run_id": run_id,
            },
            *[
                ref
                for ref in (
                    entry.get("evidence_refs")
                    if isinstance(entry.get("evidence_refs"), list)
                    else []
                )
                if isinstance(ref, dict)
            ],
        ],
        "policy": {
            "readmodel_smoke": True,
            "actual_investigate_replay_run": False,
            "movement_packet": True,
            "read_only": True,
            "handoff_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
        },
    }
    row["stack_organ_use_packet"] = stack_organ_use_packet(
        entry,
        row,
        generated_at=generated_at,
        run_id=run_id,
        previous_row=previous_row,
        paths=paths,
        config=config,
        contract_port=contract_port,
    )
    movement_selection = (
        row["stack_organ_use_packet"].get("movement_selection")
        if isinstance(row["stack_organ_use_packet"], dict)
        else {}
    )
    row["movement_selection"] = movement_selection
    row["investigation"]["selected_for_resident_reasoning"] = movement_selection.get(
        "selected_for_resident_reasoning"
    )
    row["investigation"]["resident_reasoning_reason"] = movement_selection.get(
        "selected_reason"
    )
    row["ok"] = stack_organ_use_packet_complete(
        row["stack_organ_use_packet"],
        schema_prefix=config.schema_prefix,
        event_issues=contract_port.event_issues,
    )
    row["complete"] = working_stack_activation_smoke_row_complete(
        row,
        schema_prefix=config.schema_prefix,
        investigation_node_count=config.investigation_node_count,
        event_issues=contract_port.event_issues,
    )
    return row


def stack_organ_use_packet(
    entry: dict[str, Any],
    row: dict[str, Any],
    *,
    generated_at: str,
    run_id: str,
    previous_row: dict[str, Any] | None = None,
    paths: SelfAwarenessActivationPaths,
    config: SelfAwarenessActivationConfig,
    contract_port: SelfAwarenessActivationContractPort,
) -> dict[str, Any]:
    service = str(entry.get("service") or row.get("service") or "")
    status = str(
        entry.get("machine_usage_status") or row.get("machine_usage_status") or ""
    )
    usage_gap = str(entry.get("usage_gap") or row.get("usage_gap") or "")
    link_id = str(
        entry.get("working_stack_link_id") or row.get("working_stack_link_id") or ""
    )
    episode_id = str(row.get("episode_id") or "")
    runtime = (
        entry.get("runtime")
        if isinstance(entry.get("runtime"), dict)
        else self_awareness_contracts.nested_get(entry, ["current_state", "runtime"])
    )
    runtime = runtime if isinstance(runtime, dict) else {}
    declared = entry.get("declared") if isinstance(entry.get("declared"), dict) else {}
    failed_probe_names = [
        str(item)
        for item in (
            entry.get("failed_probe_names")
            if isinstance(entry.get("failed_probe_names"), list)
            else []
        )
        if item
    ]
    ok_probe_names = [
        str(item)
        for item in (
            entry.get("ok_probe_names")
            if isinstance(entry.get("ok_probe_names"), list)
            else []
        )
        if item
    ]
    closure_acceptance = (
        entry.get("closure_acceptance")
        if isinstance(entry.get("closure_acceptance"), dict)
        else {}
    )
    synthetic_scenario = (
        entry.get("synthetic_scenario")
        if isinstance(entry.get("synthetic_scenario"), dict)
        else {}
    )
    current_state_digest = str(
        entry.get("current_state_digest")
        or self_awareness_contracts.stable_hash_json(entry, length=24)
    )
    signal_route = stack_organ_signal_route(service, entry)
    movement_selection = stack_organ_movement_selection(
        entry,
        current_state_digest=current_state_digest,
        previous_row=previous_row,
        schema_prefix=config.schema_prefix,
    )
    link = (
        entry.get("time_space_context_link")
        if isinstance(entry.get("time_space_context_link"), dict)
        else {}
    )
    observed_signal = contract_port.make_event(
        signal_route["signal"],
        signal_route["source"],
        event_time=self_awareness_contracts.nested_get(link, ["time", "observed_at"])
        or generated_at,
        observed_at=generated_at,
        source_query=f"abyss-machine self-awareness working-stack --json#organs.{service}",
        resource={
            "service": service,
            "container": runtime.get("container"),
            "pid": runtime.get("pid"),
            "pid_alive": runtime.get("pid_alive"),
            "owner_surface": "abyss-stack",
            "labels": {"service": service},
            "write": False,
        },
        context={
            "working_stack_link_id": link_id or None,
            "machine_usage_status": status,
            "run_id": run_id,
            "selection_categories": movement_selection.get("categories"),
        },
        space={
            "service_node": f"service:{service}" if service else None,
            "container_node": f"container:{runtime.get('container')}"
            if runtime.get("container")
            else None,
            "process_node": f"process:{runtime.get('pid')}"
            if runtime.get("pid")
            else None,
            "route_path": f"body/stack-organs/{service}"
            if service
            else "body/stack-organs",
            "owner_surface": "abyss-stack",
        },
        severity="warning"
        if movement_selection.get("selected_for_resident_reasoning")
        else "info",
        confidence={
            "score": 0.75,
            "reason": "working-stack read-only inventory and bounded probes",
        },
        body={
            "service": service,
            "machine_usage_status": status,
            "container": runtime.get("container"),
            "pid": runtime.get("pid"),
            "pid_alive": runtime.get("pid_alive"),
            "runtime_running": runtime.get("running"),
            "runtime_state": runtime.get("state"),
            "endpoint_ok": entry.get("endpoint_ok"),
            "ok_probe_names": ok_probe_names,
            "failed_probe_names": failed_probe_names,
            "deep_usage_proven": entry.get("deep_usage_proven"),
            "selection_categories": movement_selection.get("categories"),
        },
        evidence_refs=[
            {
                "path": str(paths.working_stack_latest),
                "service": service,
                "section": "organs",
            },
            *[
                ref
                for ref in (
                    entry.get("evidence_refs")
                    if isinstance(entry.get("evidence_refs"), list)
                    else []
                )
                if isinstance(ref, dict)
            ],
        ],
        truth_level="working_stack_movement_observation",
    )
    activation_gap_source = dict(entry)
    activation_gap_source.update(
        {
            "runtime_present": runtime.get("present"),
            "runtime_running": runtime.get("running"),
            "container": runtime.get("container"),
            "health": runtime.get("health"),
            "runtime_state": runtime.get("state"),
            "runtime_status": runtime.get("status"),
            "runtime_stack_managed": runtime.get("stack_managed"),
            "declared": declared.get("present")
            if "present" in declared
            else bool(declared),
            "declared_modules": declared.get("modules")
            if isinstance(declared.get("modules"), list)
            else [],
            "endpoint_probe_count": len(ok_probe_names) + len(failed_probe_names),
            "endpoint_ok": entry.get("endpoint_ok"),
            "failed_probe_names": failed_probe_names,
            "ok_probe_names": ok_probe_names,
            "model_roots": runtime_evidence_contracts.safe_int(
                self_awareness_contracts.nested_get(
                    entry, ["current_state", "roots", "model_roots"]
                ),
                0,
            ),
        }
    )
    activation_gap_route = contract_port.activation_gap_route(
        activation_gap_source, episode_id=episode_id or None, activation_row=row
    )
    classification = activation_gap_route.get(
        "classification"
    ) or contract_port.activation_gap_classification(activation_gap_source)
    entity_id = "stack.organ." + service if service else None
    event_id = (
        observed_signal.get("event_id")
        or episode_id
        or "stack.organ.use."
        + self_awareness_contracts.stable_hash_json(
            {"service": service, "status": status, "link": link_id}, length=20
        )
    )
    document_refs = [
        {
            "document_id": "self-awareness.working-stack.latest",
            "path": str(paths.working_stack_latest),
            "section": f"organs.{service}" if service else "organs",
        },
        {
            "document_id": "self-awareness.stack-closure-dossier.latest",
            "path": str(paths.stack_closure_dossier_latest),
            "section": "working_stack_activation_dossier",
        },
        {
            "document_id": "self-awareness.activation-smoke.latest",
            "path": str(paths.activation_smoke_latest),
            "section": f"by_service.{service}" if service else "by_service",
        },
        {
            "document_id": "self-awareness.completion-audit.latest",
            "path": str(paths.completion_audit_latest),
            "section": "entity_event_document_map",
        },
        {
            "document_id": "self-awareness.autolink.latest",
            "path": str(paths.autolink_latest),
            "section": f"organ_links_by_service.{service}"
            if service
            else "organ_links_by_service",
        },
    ]
    investigation = (
        row.get("investigation") if isinstance(row.get("investigation"), dict) else {}
    )
    replay = row.get("replay") if isinstance(row.get("replay"), dict) else {}
    activation_smoke_ok = bool(
        row.get("ok") is True
        and investigation.get("working_stack_gap_matches") is True
        and (replay.get("working_stack_gap_matches") is True)
        and (replay.get("working_stack_gap_replayable") is True)
        and (runtime_evidence_contracts.safe_int(replay.get("divergences"), -1) == 0)
    )
    packet = {
        "schema": f"{config.schema_prefix}_self_awareness_stack_organ_use_packet_v1",
        "packet_id": "saorganuse-"
        + self_awareness_contracts.stable_hash_json(
            {
                "service": service,
                "machine_usage_status": status,
                "working_stack_link_id": link_id,
                "run_id": run_id,
            },
            length=24,
        ),
        "generated_at": generated_at,
        "run_id": run_id,
        "service": service,
        "owner": "abyss-stack",
        "entity": {
            "schema": f"{config.schema_prefix}_self_awareness_stack_organ_use_entity_v1",
            "entity_id": entity_id,
            "entity_kind": "stack_organ",
            "entity_path": f"body/stack-organs/{service}" if service else None,
            "route_id": "body.stack_organs",
            "owner_surface": "abyss-stack",
        },
        "event": {
            "schema": f"{config.schema_prefix}_self_awareness_stack_organ_use_event_v1",
            "event_id": event_id,
            "event_kind": "stack_organ_movement_observed",
            "episode_id": episode_id or None,
            "route_id": "body.stack_organs",
            "route_path": "body/stack-organs",
            "working_stack_link_id": link_id or None,
            "machine_usage_status": status,
            "classification": classification,
            "observed_at": generated_at,
        },
        "observed_signal": observed_signal,
        "movement_selection": movement_selection,
        "documents": document_refs,
        "document_ids": [
            str(item.get("document_id"))
            for item in document_refs
            if item.get("document_id")
        ],
        "current_state": {
            "runtime": runtime,
            "declared": declared,
            "endpoint": {
                "ok": entry.get("endpoint_ok"),
                "ok_probe_names": ok_probe_names,
                "failed_probe_names": failed_probe_names,
            },
            "deep_usage_proven": entry.get("deep_usage_proven"),
            "current_state_digest": current_state_digest,
        },
        "time_space_context": {
            "time": {
                "observed_at": generated_at,
                "source_observed_at": self_awareness_contracts.nested_get(
                    link, ["time", "observed_at"]
                ),
                "time_bucket": self_awareness_contracts.nested_get(
                    link, ["time", "bucket"]
                ),
                "episode_id": episode_id or None,
            },
            "space": {
                "service_node": f"service:{service}" if service else None,
                "container_node": f"container:{runtime.get('container')}"
                if runtime.get("container")
                else None,
                "process_node": f"process:{runtime.get('pid')}"
                if runtime.get("pid")
                else None,
                "working_stack_link_node": f"working_stack_link:{link_id}"
                if link_id
                else None,
                "route_path": f"body/stack-organs/{service}"
                if service
                else "body/stack-organs",
                "owner_surface": "abyss-stack",
            },
            "context": {
                "working_stack_link_id": link_id or None,
                "activation_kind": entry.get("activation_kind"),
                "coverage_planes": entry.get("coverage_planes")
                if isinstance(entry.get("coverage_planes"), list)
                else [],
                "closure_blocker_keys": entry.get("closure_blocker_keys")
                if isinstance(entry.get("closure_blocker_keys"), list)
                else [],
                "trace_id": None,
                "span_id": None,
                "thread_id": None,
                "checkpoint_id": None,
                "source_query": observed_signal.get("source_query"),
            },
        },
        "activation_gap": {
            "classification": classification,
            "route": activation_gap_route,
            "route_complete": contract_port.activation_gap_route_complete(
                activation_gap_route
            ),
        },
        "synthetic_scenario": {
            "scenario_id": synthetic_scenario.get("scenario_id"),
            "complete": contract_port.activation_synthetic_scenario_complete(
                synthetic_scenario
            ),
            "current_result": synthetic_scenario.get("current_result"),
        },
        "closure_acceptance": {
            "acceptance_id": closure_acceptance.get("acceptance_id"),
            "complete": contract_port.activation_closure_acceptance_complete(
                closure_acceptance
            ),
            "compat_requirement_id": self_awareness_contracts.nested_get(
                closure_acceptance, ["stack_compat_requirement", "requirement_id"]
            ),
            "owner": closure_acceptance.get("owner"),
        },
        "investigation_replay": {
            "complete": activation_smoke_ok,
            "episode_id": episode_id or None,
            "investigation_thread_id": investigation.get("thread_id"),
            "replay_thread_id": replay.get("thread_id"),
            "node_order": replay.get("node_order")
            if isinstance(replay.get("node_order"), list)
            else [],
            "divergences": replay.get("divergences"),
            "working_stack_gap_replayable": replay.get("working_stack_gap_replayable"),
        },
        "automation": {
            "generated_by": "abyss-machine self-awareness activation-smoke",
            "required_in": ["activation-smoke", "export", "validate"],
            "runs_stack_http_probes": False,
            "executes_stack_verifiers": False,
            "host_layer_mutates_stack": False,
        },
        "evidence_refs": [
            {
                "path": str(paths.activation_smoke_latest),
                "service": service,
                "run_id": run_id,
            },
            {
                "path": str(paths.stack_closure_dossier_latest),
                "service": service,
                "section": "working_stack_activation_dossier",
            },
            {
                "path": str(paths.completion_audit_latest),
                "section": "entity_event_document_map",
            },
            {
                "path": str(paths.working_stack_latest),
                "service": service,
                "section": "organs",
            },
            *[
                ref
                for ref in (
                    entry.get("evidence_refs")
                    if isinstance(entry.get("evidence_refs"), list)
                    else []
                )
                if isinstance(ref, dict)
            ],
        ],
        "policy": {
            "read_only": True,
            "handoff_only": True,
            "host_layer_mutates_stack": False,
            "writes_project_roots": False,
            "executes_commands": False,
            "action_execution": False,
            "automatic_remediation": False,
            "raw_secrets_included": False,
            "raw_private_content_included": False,
            "raw_evidence_is_not_truth": True,
        },
    }
    checks = {
        "entity_named": bool(
            self_awareness_contracts.nested_get(packet, ["entity", "entity_id"])
        ),
        "event_named": bool(
            self_awareness_contracts.nested_get(packet, ["event", "event_id"])
        ),
        "documents_bound": len(packet["document_ids"]) >= 5,
        "current_state_bound": bool(
            packet["current_state"].get("current_state_digest") or runtime or declared
        ),
        "time_space_context_bound": bool(
            self_awareness_contracts.nested_get(
                packet, ["time_space_context", "context", "working_stack_link_id"]
            )
        ),
        "observed_signal_complete": not contract_port.event_issues(observed_signal),
        "movement_selection_bound": bool(movement_selection.get("categories"))
        and (
            bool(movement_selection.get("selected_reason"))
            or bool(movement_selection.get("not_selected_reason"))
        ),
        "activation_gap_route_bound": not usage_gap
        or packet["activation_gap"]["route_complete"] is True,
        "synthetic_scenario_bound": not usage_gap
        or packet["synthetic_scenario"]["complete"] is True,
        "closure_acceptance_bound": not usage_gap
        or packet["closure_acceptance"]["complete"] is True,
        "investigation_replay_bound": True,
        "policy": self_awareness_contracts.nested_get(
            packet, ["policy", "host_layer_mutates_stack"]
        )
        is False
        and self_awareness_contracts.nested_get(packet, ["policy", "executes_commands"])
        is False,
    }
    packet["checks"] = checks
    packet["missing_checks"] = [key for key, ok in checks.items() if ok is not True]
    packet["complete"] = stack_organ_use_packet_complete(
        packet,
        schema_prefix=config.schema_prefix,
        event_issues=contract_port.event_issues,
    )
    return packet


def stack_organ_use_packet_complete(
    packet: Any,
    *,
    schema_prefix: str,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> bool:
    if not isinstance(packet, Mapping):
        return False
    entity = packet.get("entity") if isinstance(packet.get("entity"), Mapping) else {}
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    documents = (
        packet.get("documents") if isinstance(packet.get("documents"), list) else []
    )
    checks = packet.get("checks") if isinstance(packet.get("checks"), Mapping) else {}
    observed_signal = (
        packet.get("observed_signal")
        if isinstance(packet.get("observed_signal"), Mapping)
        else {}
    )
    movement_selection = (
        packet.get("movement_selection")
        if isinstance(packet.get("movement_selection"), Mapping)
        else {}
    )
    return (
        packet.get("schema")
        == f"{schema_prefix}_self_awareness_stack_organ_use_packet_v1"
        and bool(packet.get("packet_id"))
        and bool(packet.get("service"))
        and (packet.get("owner") == "abyss-stack")
        and (
            entity.get("schema")
            == f"{schema_prefix}_self_awareness_stack_organ_use_entity_v1"
        )
        and (entity.get("entity_kind") == "stack_organ")
        and bool(entity.get("entity_id"))
        and (
            event.get("schema")
            == f"{schema_prefix}_self_awareness_stack_organ_use_event_v1"
        )
        and bool(event.get("event_id"))
        and bool(event.get("working_stack_link_id"))
        and bool(event.get("classification"))
        and isinstance(documents, list)
        and (len(documents) >= 5)
        and all(
            (
                isinstance(item, Mapping)
                and item.get("document_id")
                and item.get("path")
                for item in documents
            )
        )
        and isinstance(packet.get("document_ids"), list)
        and (len(packet.get("document_ids")) == len(documents))
        and isinstance(packet.get("current_state"), Mapping)
        and bool(
            self_awareness_contracts.nested_get(
                packet, ["time_space_context", "context", "working_stack_link_id"]
            )
        )
        and (observed_signal.get("schema") == f"{schema_prefix}_observation_event_v1")
        and (not event_issues(dict(observed_signal)))
        and (
            movement_selection.get("schema")
            == f"{schema_prefix}_self_awareness_stack_organ_movement_selection_v1"
        )
        and isinstance(movement_selection.get("categories"), list)
        and bool(movement_selection.get("categories"))
        and (
            bool(movement_selection.get("selected_reason"))
            or bool(movement_selection.get("not_selected_reason"))
        )
        and (
            self_awareness_contracts.nested_get(packet, ["automation", "required_in"])
            == ["activation-smoke", "export", "validate"]
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["automation", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["automation", "executes_stack_verifiers"]
            )
            is False
        )
        and bool(packet.get("evidence_refs"))
        and all((ok is True for ok in checks.values()))
        and (packet.get("missing_checks") == [])
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "writes_project_roots"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(packet, ["policy", "executes_commands"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(packet, ["policy", "action_execution"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "automatic_remediation"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "raw_secrets_included"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                packet, ["policy", "raw_private_content_included"]
            )
            is False
        )
    )


def working_stack_activation_smoke_row_complete(
    row: Any,
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> bool:
    if not isinstance(row, Mapping):
        return False
    investigation = (
        row.get("investigation")
        if isinstance(row.get("investigation"), Mapping)
        else {}
    )
    replay = row.get("replay") if isinstance(row.get("replay"), Mapping) else {}
    stack_organ_use_packet = (
        row.get("stack_organ_use_packet")
        if isinstance(row.get("stack_organ_use_packet"), Mapping)
        else {}
    )
    packet_complete = stack_organ_use_packet_complete(
        stack_organ_use_packet, schema_prefix=schema_prefix, event_issues=event_issues
    )
    if row.get("row_kind") == "organ_movement":
        return (
            row.get("schema")
            == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_row_v1"
            and row.get("ok") is True
            and bool(row.get("service"))
            and (row.get("owner") == "abyss-stack")
            and bool(row.get("machine_usage_status"))
            and bool(row.get("working_stack_link_id"))
            and (
                investigation.get("schema")
                == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_investigation_v1"
            )
            and (investigation.get("actual_run") is False)
            and (
                replay.get("schema")
                == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_replay_v1"
            )
            and (replay.get("actual_run") is False)
            and packet_complete
            and (stack_organ_use_packet.get("service") == row.get("service"))
            and (
                self_awareness_contracts.nested_get(
                    stack_organ_use_packet, ["event", "working_stack_link_id"]
                )
                == row.get("working_stack_link_id")
            )
            and (
                self_awareness_contracts.nested_get(
                    stack_organ_use_packet, ["event", "machine_usage_status"]
                )
                == row.get("machine_usage_status")
            )
            and bool(row.get("evidence_refs"))
            and (
                self_awareness_contracts.nested_get(row, ["policy", "movement_packet"])
                is True
            )
            and (
                self_awareness_contracts.nested_get(
                    row, ["policy", "actual_investigate_replay_run"]
                )
                is False
            )
            and (
                self_awareness_contracts.nested_get(
                    row, ["policy", "host_layer_mutates_stack"]
                )
                is False
            )
            and (
                self_awareness_contracts.nested_get(
                    row, ["policy", "executes_commands"]
                )
                is False
            )
            and (
                self_awareness_contracts.nested_get(row, ["policy", "action_execution"])
                is False
            )
            and (
                self_awareness_contracts.nested_get(
                    row, ["policy", "automatic_remediation"]
                )
                is False
            )
        )
    return (
        row.get("schema")
        == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_row_v1"
        and row.get("ok") is True
        and bool(row.get("service"))
        and (row.get("owner") == "abyss-stack")
        and bool(row.get("machine_usage_status"))
        and bool(row.get("usage_gap"))
        and bool(row.get("working_stack_link_id"))
        and bool(row.get("episode_id"))
        and (
            investigation.get("schema")
            == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_investigation_v1"
        )
        and (investigation.get("ok") is True)
        and (investigation.get("selected_episode_matches") is True)
        and (investigation.get("working_stack_gap_complete") is True)
        and (investigation.get("working_stack_gap_matches") is True)
        and (
            runtime_evidence_contracts.safe_int(
                investigation.get("evidence_validation_fails"), -1
            )
            == 0
        )
        and (
            runtime_evidence_contracts.safe_int(investigation.get("checkpoints"), 0)
            == investigation_node_count
        )
        and (
            runtime_evidence_contracts.safe_int(investigation.get("graph_nodes"), 0)
            == investigation_node_count
        )
        and (
            replay.get("schema")
            == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_replay_v1"
        )
        and (replay.get("ok") is True)
        and (replay.get("thread_matches") is True)
        and (replay.get("working_stack_gap_selected") is True)
        and (replay.get("working_stack_gap_replayable") is True)
        and (replay.get("working_stack_gap_matches") is True)
        and (runtime_evidence_contracts.safe_int(replay.get("divergences"), -1) == 0)
        and (replay.get("stack_handoff_closure_readiness_replayable") is True)
        and (replay.get("resident_cognitive_replay_complete") is True)
        and packet_complete
        and (stack_organ_use_packet.get("service") == row.get("service"))
        and (
            self_awareness_contracts.nested_get(
                stack_organ_use_packet, ["event", "working_stack_link_id"]
            )
            == row.get("working_stack_link_id")
        )
        and (
            self_awareness_contracts.nested_get(
                stack_organ_use_packet, ["event", "machine_usage_status"]
            )
            == row.get("machine_usage_status")
        )
        and bool(row.get("evidence_refs"))
        and (
            self_awareness_contracts.nested_get(
                row, ["policy", "actual_investigate_replay_run"]
            )
            is True
        )
        and (
            self_awareness_contracts.nested_get(
                row, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(row, ["policy", "executes_commands"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(row, ["policy", "action_execution"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                row, ["policy", "automatic_remediation"]
            )
            is False
        )
    )


def working_stack_activation_smoke_compact(
    row: Any,
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    return {
        "schema": f"{schema_prefix}_self_awareness_working_stack_activation_smoke_compact_v1",
        "row_kind": row.get("row_kind"),
        "service": row.get("service"),
        "machine_usage_status": row.get("machine_usage_status"),
        "working_stack_link_id": row.get("working_stack_link_id"),
        "episode_id": row.get("episode_id"),
        "ok": row.get("ok"),
        "complete": working_stack_activation_smoke_row_complete(
            row,
            schema_prefix=schema_prefix,
            investigation_node_count=investigation_node_count,
            event_issues=event_issues,
        ),
        "thread_id": self_awareness_contracts.nested_get(
            row, ["investigation", "thread_id"]
        ),
        "divergences": self_awareness_contracts.nested_get(
            row, ["replay", "divergences"]
        ),
        "working_stack_gap_replayable": self_awareness_contracts.nested_get(
            row, ["replay", "working_stack_gap_replayable"]
        ),
        "resident_cognitive_replay_complete": self_awareness_contracts.nested_get(
            row, ["replay", "resident_cognitive_replay_complete"]
        ),
        "stack_organ_use_packet_id": self_awareness_contracts.nested_get(
            row, ["stack_organ_use_packet", "packet_id"]
        ),
        "stack_organ_entity_id": self_awareness_contracts.nested_get(
            row, ["stack_organ_use_packet", "entity", "entity_id"]
        ),
        "stack_organ_event_id": self_awareness_contracts.nested_get(
            row, ["stack_organ_use_packet", "event", "event_id"]
        ),
        "stack_organ_document_ids": self_awareness_contracts.nested_get(
            row, ["stack_organ_use_packet", "document_ids"]
        )
        if isinstance(
            self_awareness_contracts.nested_get(
                row, ["stack_organ_use_packet", "document_ids"]
            ),
            list,
        )
        else [],
        "activation_gap_classification": self_awareness_contracts.nested_get(
            row, ["stack_organ_use_packet", "activation_gap", "classification"]
        ),
        "movement_categories": self_awareness_contracts.nested_get(
            row, ["stack_organ_use_packet", "movement_selection", "categories"]
        )
        if isinstance(
            self_awareness_contracts.nested_get(
                row, ["stack_organ_use_packet", "movement_selection", "categories"]
            ),
            list,
        )
        else [],
        "selected_for_resident_reasoning": self_awareness_contracts.nested_get(
            row,
            [
                "stack_organ_use_packet",
                "movement_selection",
                "selected_for_resident_reasoning",
            ],
        ),
        "evidence_refs": row.get("evidence_refs")
        if isinstance(row.get("evidence_refs"), list)
        else [],
        "policy": {
            "read_only": True,
            "host_layer_mutates_stack": False,
            "executes_commands": False,
            "action_execution": False,
        },
    }


def working_stack_activation_smoke_complete(
    smoke: Any,
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
) -> bool:
    if not isinstance(smoke, Mapping):
        return False
    rows = smoke.get("rows") if isinstance(smoke.get("rows"), list) else []
    summary = smoke.get("summary") if isinstance(smoke.get("summary"), Mapping) else {}
    packets = (
        smoke.get("stack_organ_use_packets")
        if isinstance(smoke.get("stack_organ_use_packets"), list)
        else []
    )
    packet_by_service = (
        smoke.get("stack_organ_use_packet_by_service")
        if isinstance(smoke.get("stack_organ_use_packet_by_service"), Mapping)
        else {}
    )
    service_ids = [
        str(row.get("service"))
        for row in rows
        if isinstance(row, Mapping) and row.get("service")
    ]
    summary_service_ids = [
        str(item)
        for item in (
            summary.get("service_ids")
            if isinstance(summary.get("service_ids"), list)
            else []
        )
    ]
    expected_services = [
        str(item)
        for item in (
            summary.get("stack_organs_expected_services")
            if isinstance(summary.get("stack_organs_expected_services"), list)
            else []
        )
    ]
    return (
        smoke.get("schema")
        == f"{schema_prefix}_self_awareness_working_stack_activation_smoke_v1"
        and smoke.get("ok") is True
        and bool(smoke.get("run_id"))
        and bool(rows)
        and bool(packets)
        and bool(expected_services)
        and (
            runtime_evidence_contracts.safe_int(
                summary.get("stack_organs_expected"), -1
            )
            == len(expected_services)
        )
        and (runtime_evidence_contracts.safe_int(summary.get("rows"), -1) == len(rows))
        and (
            runtime_evidence_contracts.safe_int(summary.get("rows_ok"), -1) == len(rows)
        )
        and (
            runtime_evidence_contracts.safe_int(
                summary.get("stack_organ_use_packets"), -1
            )
            == len(rows)
        )
        and (
            runtime_evidence_contracts.safe_int(
                summary.get("stack_organ_use_packets_complete"), -1
            )
            == len(rows)
        )
        and (sorted(summary_service_ids) == sorted(service_ids))
        and (len(packets) == len(rows))
        and (set(service_ids) == set(expected_services))
        and (set((str(item) for item in packet_by_service)) == set(service_ids))
        and (not summary.get("stack_organs_without_use_packets"))
        and (summary.get("all_stack_organs_have_use_packets") is True)
        and all(
            (
                stack_organ_use_packet_complete(
                    packet, schema_prefix=schema_prefix, event_issues=event_issues
                )
                for packet in packets
            )
        )
        and (not summary.get("failed_services"))
        and all(
            (
                working_stack_activation_smoke_row_complete(
                    row,
                    schema_prefix=schema_prefix,
                    investigation_node_count=investigation_node_count,
                    event_issues=event_issues,
                )
                for row in rows
            )
        )
        and bool(smoke.get("evidence_refs"))
        and (
            self_awareness_contracts.nested_get(
                smoke, ["policy", "host_layer_mutates_stack"]
            )
            is False
        )
        and (
            self_awareness_contracts.nested_get(smoke, ["policy", "executes_commands"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(smoke, ["policy", "action_execution"])
            is False
        )
        and (
            self_awareness_contracts.nested_get(
                smoke, ["policy", "automatic_remediation"]
            )
            is False
        )
    )


def activation_smoke_needs_refresh(
    smoke: Any,
    activation_entries: list[dict[str, Any]],
    *,
    schema_prefix: str,
    investigation_node_count: int,
    event_issues: Callable[[dict[str, Any]], list[str]],
    expected_services: Iterable[str] | None = None,
) -> bool:
    if not working_stack_activation_smoke_complete(
        smoke,
        schema_prefix=schema_prefix,
        investigation_node_count=investigation_node_count,
        event_issues=event_issues,
    ):
        return True
    rows = (
        smoke.get("rows")
        if isinstance(smoke, Mapping) and isinstance(smoke.get("rows"), list)
        else []
    )
    row_by_service = {
        str(row.get("service")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("service")
    }
    expected_service_set = {
        str(entry.get("service"))
        for entry in activation_entries
        if isinstance(entry, Mapping) and entry.get("service")
    }
    if expected_services is not None:
        expected_service_set = {
            str(service) for service in expected_services if service
        }
    if set(row_by_service) != expected_service_set:
        return True
    entry_by_service = {
        str(entry.get("service")): entry
        for entry in activation_entries
        if isinstance(entry, Mapping) and entry.get("service")
    }
    for service in set(row_by_service) & set(entry_by_service):
        entry = entry_by_service.get(service, {})
        if not isinstance(entry, Mapping) or not entry.get("service"):
            continue
        row = row_by_service.get(str(entry.get("service")), {})
        if str(row.get("machine_usage_status") or "") != str(
            entry.get("machine_usage_status") or ""
        ) or str(row.get("working_stack_link_id") or "") != str(
            entry.get("working_stack_link_id") or ""
        ):
            return True
    return False
