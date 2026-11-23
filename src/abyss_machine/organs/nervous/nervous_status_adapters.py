from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping


LatestReaderPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
PathExistsPort = Callable[[Path], bool]
LineCounterPort = Callable[[Path], int | None]
SystemdUnitPort = Callable[[str], dict[str, Any]]
IndexCountsPort = Callable[[], dict[str, Any]]
ProcessLatestPort = Callable[[], dict[str, Any]]
NowIsoPort = Callable[[], str]
WriteJsonPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
IndexDocumentPort = Callable[[dict[str, Any]], dict[str, Any]]


def _nested_get(data: Mapping[str, Any], path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _enabled_sources(sources: Mapping[str, Any], group_name: str) -> list[str]:
    group = sources.get(group_name)
    if not isinstance(group, Mapping):
        return []
    return [
        str(name)
        for name, item in group.items()
        if isinstance(item, Mapping)
        and bool(item.get("enabled"))
        and bool(item.get("allowed", True))
    ]


def _deferred_source_ids(sources: Mapping[str, Any]) -> list[str]:
    group = sources.get("deferred_until_privacy_controls")
    return list(group.keys()) if isinstance(group, Mapping) else []


def _latest_section(
    *,
    latest_path: Path,
    latest_data: dict[str, Any] | None,
    latest_error: str | None,
    path_exists: PathExistsPort,
    fields: Mapping[str, list[str] | str],
) -> dict[str, Any]:
    section: dict[str, Any] = {
        "latest": str(latest_path),
        "latest_exists": path_exists(latest_path),
        "latest_error": latest_error,
        "ok": latest_data.get("ok") if isinstance(latest_data, dict) else None,
    }
    for output_key, source_path in fields.items():
        if not isinstance(latest_data, dict):
            section[output_key] = None
        elif isinstance(source_path, list):
            section[output_key] = _nested_get(latest_data, source_path)
        else:
            section[output_key] = latest_data.get(source_path)
    return section


def status_document_from_ports(
    *,
    paths: Mapping[str, Any],
    policy: Mapping[str, Any],
    sources: Mapping[str, Any],
    privacy: Mapping[str, Any],
    status_paths: Mapping[str, Path],
    unit_names: Mapping[str, str],
    index_counts: IndexCountsPort,
    latest_reader: LatestReaderPort,
    path_exists: PathExistsPort,
    line_counter: LineCounterPort,
    systemd_unit: SystemdUnitPort,
    process_latest: ProcessLatestPort,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    if not path_exists(status_paths["design"]):
        warnings.append("design artifact missing")
    if not path_exists(status_paths["agents"]):
        warnings.append("agent entrypoint missing")
    for key in ("policy_config", "sources_config", "privacy_config"):
        path = status_paths[key]
        if not path_exists(path):
            warnings.append(f"config missing: {path}")

    activation = policy.get("activation") if isinstance(policy.get("activation"), Mapping) else {}
    if policy.get("active_daemon") or activation.get("watcher_enabled"):
        warnings.append("policy claims active daemon; verify service before capture")

    enabled_sources = _enabled_sources(sources, "safe_now")
    enabled_private_sources = _enabled_sources(sources, "deferred_until_privacy_controls")

    events_latest, events_latest_error = latest_reader(status_paths["events_latest"])
    episodes_latest, episodes_latest_error = latest_reader(status_paths["episodes_latest"])
    retrieval_latest, retrieval_latest_error = latest_reader(status_paths["retrieval_latest"])
    synthesis_latest, synthesis_latest_error = latest_reader(status_paths["synthesis_latest"])
    eval_latest, eval_latest_error = latest_reader(status_paths["evals_latest"])
    retention_latest, retention_latest_error = latest_reader(status_paths["retention_latest"])
    capture_latest, capture_latest_error = latest_reader(status_paths["capture_latest"])
    browser_content_latest, browser_content_latest_error = latest_reader(status_paths["browser_content_latest"])

    counts = index_counts()
    browser_content_capture = {
        "service": systemd_unit(unit_names["browser_content_capture_service"]),
        "timer": systemd_unit(unit_names["browser_content_capture_timer"]),
        "scope": "user",
        "latest": str(status_paths["browser_content_latest"]),
        "latest_exists": path_exists(status_paths["browser_content_latest"]),
        "latest_error": browser_content_latest_error,
        "ok": browser_content_latest.get("ok") if isinstance(browser_content_latest, dict) else None,
        "summary": browser_content_latest.get("summary") if isinstance(browser_content_latest, dict) else None,
        "error": browser_content_latest.get("error") if isinstance(browser_content_latest, dict) else None,
        "raw_storage_root": str(status_paths["browser_content_root"]),
        "idle_behavior": "timer tick exits cleanly without capture while Firefox is closed",
    }
    local_index = {
        "service": systemd_unit(unit_names["search_index_service"]),
        "timer": systemd_unit(unit_names["search_index_timer"]),
        "scope": "user",
        "db": str(status_paths["search_index_db"]),
        "latest": str(status_paths["search_index_latest"]),
        "db_exists": path_exists(status_paths["search_index_db"]),
        "documents": counts.get("documents"),
        "chunks": counts.get("chunks"),
    }

    return {
        "schema": f"{schema_prefix}_nervous_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not any(item.startswith("design artifact") or item.startswith("agent entrypoint") for item in warnings),
        "status": "ready-for-local-chronicle",
        "phase": "stage-9-passive-local-private-capture",
        "warnings": warnings,
        "paths": dict(paths),
        "policy": {
            "path": str(status_paths["policy_config"]),
            "exists": path_exists(status_paths["policy_config"]),
            "mode": policy.get("mode"),
            "active_daemon": bool(policy.get("active_daemon")),
            "activation": activation,
            "load_error": policy.get("_load_error"),
        },
        "sources": {
            "path": str(status_paths["sources_config"]),
            "exists": path_exists(status_paths["sources_config"]),
            "mode": sources.get("mode"),
            "enabled_safe_sources": enabled_sources,
            "enabled_private_connector_sources": enabled_private_sources,
            "state_path": str(status_paths["sources_state"]),
            "state": sources.get("state", {}),
            "deferred": _deferred_source_ids(sources),
            "load_error": sources.get("_load_error"),
        },
        "privacy": {
            "path": str(status_paths["privacy_config"]),
            "exists": path_exists(status_paths["privacy_config"]),
            "mode": privacy.get("mode"),
            "global_pause": bool(privacy.get("global_pause")),
            "private_mode": bool(privacy.get("private_mode")),
            "state_path": str(status_paths["privacy_state"]),
            "state": privacy.get("state", {}),
            "load_error": privacy.get("_load_error"),
        },
        "daemon": {
            "service": systemd_unit(unit_names["daemon_service"]),
            "timer": systemd_unit(unit_names["daemon_timer"]),
            "scope": "user",
        },
        "passive_chronicle": {
            "service": systemd_unit(unit_names["passive_chronicle_service"]),
            "timer": systemd_unit(unit_names["passive_chronicle_timer"]),
            "scope": "user",
            "latest_facts": str(status_paths["facts_latest"]),
        },
        "browser_content_capture": browser_content_capture,
        "local_index": local_index,
        "capture": {
            "latest": str(status_paths["capture_latest"]),
            "latest_exists": path_exists(status_paths["capture_latest"]),
            "latest_error": capture_latest_error,
            "ok": capture_latest.get("ok") if isinstance(capture_latest, dict) else None,
            "summary": capture_latest.get("summary") if isinstance(capture_latest, dict) else None,
            "sources": capture_latest.get("sources") if isinstance(capture_latest, dict) else None,
            "private_artifact_root": str(status_paths["private_capture_root"]),
            "screenshots_root": str(status_paths["screenshot_root"]),
            "browser_content_root": str(status_paths["browser_content_root"]),
            "browser_content_latest": str(status_paths["browser_content_latest"]),
        },
        "derived_events": _latest_section(
            latest_path=status_paths["events_latest"],
            latest_data=events_latest,
            latest_error=events_latest_error,
            path_exists=path_exists,
            fields={"events": ["summary", "events"], "by_category": ["summary", "by_category"]},
        ),
        "derived_episodes": _latest_section(
            latest_path=status_paths["episodes_latest"],
            latest_data=episodes_latest,
            latest_error=episodes_latest_error,
            path_exists=path_exists,
            fields={"episodes": ["summary", "episodes"], "by_category": ["summary", "by_category"]},
        ),
        "retrieval": _latest_section(
            latest_path=status_paths["retrieval_latest"],
            latest_data=retrieval_latest,
            latest_error=retrieval_latest_error,
            path_exists=path_exists,
            fields={"pack_id": "pack_id", "evidence_items": ["summary", "evidence_items"]},
        ),
        "synthesis": _latest_section(
            latest_path=status_paths["synthesis_latest"],
            latest_data=synthesis_latest,
            latest_error=synthesis_latest_error,
            path_exists=path_exists,
            fields={"candidate_id": "candidate_id", "scope": "scope", "summary": "summary"},
        ),
        "evals": _latest_section(
            latest_path=status_paths["evals_latest"],
            latest_data=eval_latest,
            latest_error=eval_latest_error,
            path_exists=path_exists,
            fields={"summary": "summary"},
        ),
        "retention": _latest_section(
            latest_path=status_paths["retention_latest"],
            latest_data=retention_latest,
            latest_error=retention_latest_error,
            path_exists=path_exists,
            fields={"summary": "summary"},
        ),
        "existing_bridges": {
            "storage_latest": {
                "path": str(status_paths["storage_latest"]),
                "exists": path_exists(status_paths["storage_latest"]),
            },
            "process_latest": process_latest(),
            "observability_latest": {
                "path": str(status_paths["observability_latest"]),
                "exists": path_exists(status_paths["observability_latest"]),
            },
            "ai_capabilities_latest": {
                "path": str(status_paths["ai_capabilities_latest"]),
                "exists": path_exists(status_paths["ai_capabilities_latest"]),
            },
        },
        "today": {
            "events_path": paths["events"]["today"],
            "events": line_counter(Path(paths["events"]["today"])),
            "facts_path": paths["facts"]["today"],
            "facts": line_counter(Path(paths["facts"]["today"])),
            "facts_latest": str(status_paths["facts_latest"]),
            "episodes_path": paths["episodes"]["today"],
            "episodes": line_counter(Path(paths["episodes"]["today"])),
            "retrieval_path": paths["retrieval"]["today"],
            "retrieval": line_counter(Path(paths["retrieval"]["today"])),
            "evals_path": paths["evals"]["today"],
            "evals": line_counter(Path(paths["evals"]["today"])),
            "retention_path": paths["retention"]["today"],
            "retention": line_counter(Path(paths["retention"]["today"])),
        },
        "non_claims": [
            "No watcher or daemon is installed by this command.",
            "Broad local capture is passive timer-based; no always-on watcher daemon is installed.",
            "Terminal capture does not attach to existing stdout/stderr streams.",
            "Browser capture uses recent local history metadata plus Firefox AT-SPI document text during normal browsing; RemoteAgent is diagnostic-only.",
            "AoA repositories remain reference material under reformation.",
        ],
    }


def write_status_outputs(
    data: dict[str, Any],
    *,
    latest_path: Path,
    index_path: Path,
    index_document: IndexDocumentPort,
    writer: WriteJsonPort,
    mode: int = 0o664,
) -> dict[str, Any]:
    latest_error = writer(latest_path, data, mode)
    index_error = writer(index_path, index_document(data), mode)
    errors = [error for error in (latest_error, index_error) if error]
    if errors:
        data = dict(data)
        data["write_errors"] = errors
    return data
