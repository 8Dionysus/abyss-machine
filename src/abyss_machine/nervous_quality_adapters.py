from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from . import nervous_quality
from . import typing_nervous_adapters


MappingPort = Callable[..., Mapping[str, Any]]
LatestReaderPort = Callable[[Path], tuple[Any, str | None]]
LatestJsonWriterPort = Callable[[Path, dict[str, Any], int], Any]
JsonlAppendPort = Callable[[Path, dict[str, Any], int], Any]
TodayPathPort = Callable[[Path], Path]
PathExistsPort = Callable[[Path], bool]


def path_exists(path: Path) -> bool:
    return path.exists()


def _refresh_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": data.get("ok"),
        "summary": data.get("summary"),
        "error": data.get("error"),
    }


def _synthesis_refresh_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    item = _refresh_summary(data)
    item["candidate_id"] = data.get("candidate_id")
    return item


def _index_refresh_summary(data: Mapping[str, Any]) -> dict[str, Any]:
    item = _refresh_summary(data)
    item["derived_refresh"] = data.get("derived_refresh")
    return item


def missing_index_validation_document(index_db_path: Path) -> dict[str, Any]:
    return {
        "ok": False,
        "summary": {"fails": 1, "warnings": 0, "checks": 0},
        "checks": [
            {
                "level": "fail",
                "key": "index_db",
                "message": "nervous search index database missing",
                "details": {"path": str(index_db_path)},
            }
        ],
    }


def run_quality_audit(
    *,
    refresh: bool,
    refresh_index: bool,
    write_latest_enabled: bool,
    deep_index_validate: bool,
    search_index_db_path: Path,
    browser_content_latest_path: Path,
    privacy_state_path: Path,
    quality_latest_path: Path,
    quality_root: Path,
    semantic_maintain_latest_path: Path,
    passive_chronicle_timer: str,
    browser_content_capture_timer: str,
    search_index_timer: str,
    semantic_maintain_timer: str,
    semantic_maintain_service: str,
    commands: Mapping[str, str],
    schema_prefix: str,
    version: str,
    generated_at: str,
    index_build: MappingPort,
    events_build: MappingPort,
    episodes_build: MappingPort,
    synthesis_build: MappingPort,
    eval_run: MappingPort,
    status: MappingPort,
    capture_status: Callable[[], Mapping[str, Any]],
    derived_refresh_status: Callable[[], Mapping[str, Any]],
    privacy_status: MappingPort,
    effective_sources: MappingPort,
    facts_validate: Callable[[], Mapping[str, Any]],
    events_validate: MappingPort,
    episodes_validate: MappingPort,
    synthesis_validate: MappingPort,
    eval_validate: MappingPort,
    retention_validate: MappingPort,
    index_status: MappingPort,
    index_validate: MappingPort,
    bounded_index_validate_from_status: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    latest_reader: LatestReaderPort,
    redaction_smoke: Callable[[str], Mapping[str, Any]],
    systemd_unit: Callable[[str], Mapping[str, Any]],
    latest_writer: LatestJsonWriterPort = typing_nervous_adapters.safe_atomic_write_json,
    jsonl_append: JsonlAppendPort = typing_nervous_adapters.safe_append_jsonl,
    today_path: TodayPathPort = typing_nervous_adapters.daily_jsonl_path,
    path_exists_port: PathExistsPort = path_exists,
) -> dict[str, Any]:
    refresh_results: dict[str, Any] = {}
    if refresh:
        if refresh_index:
            index_refresh = index_build(write_latest=True, refresh_derived=True)
            refresh_results["index_build"] = _index_refresh_summary(index_refresh)
        else:
            events_refresh = events_build(write_latest=True)
            episodes_refresh = episodes_build(write_latest=True, refresh_events=False)
            refresh_results["events_build"] = _refresh_summary(events_refresh)
            refresh_results["episodes_build"] = _refresh_summary(episodes_refresh)
        synthesis_refresh = synthesis_build(scope="daily", write_latest=True)
        eval_refresh = eval_run(write_latest=True)
        refresh_results["synthesis_build"] = _synthesis_refresh_summary(synthesis_refresh)
        refresh_results["eval_run"] = _refresh_summary(eval_refresh)

    status_data = status(write_latest=True)
    capture = capture_status()
    derived = derived_refresh_status()
    privacy = privacy_status(write_latest=True)
    sources = effective_sources(write_latest=True)
    facts_validation = facts_validate()
    events_validation = events_validate(write_latest=True)
    episodes_validation = episodes_validate(write_latest=True)
    synthesis_validation = synthesis_validate(write_latest=True)
    eval_validation = eval_validate(write_latest=True)
    retention_validation = retention_validate(write_latest=True)
    index_status_data = index_status(write_latest=True)
    if deep_index_validate and path_exists_port(search_index_db_path):
        index_validation = index_validate(write_latest=True)
    elif path_exists_port(search_index_db_path):
        index_validation = bounded_index_validate_from_status(index_status_data)
    else:
        index_validation = missing_index_validation_document(search_index_db_path)

    browser_latest, browser_error = latest_reader(browser_content_latest_path)
    redaction = redaction_smoke("password=CorrectHorseBatteryStaple token=" + "gh" + "p_123456789012345678901234")
    redaction_summary = redaction.get("summary") if isinstance(redaction.get("summary"), dict) else {}
    timers = {
        "passive_chronicle": systemd_unit(passive_chronicle_timer),
        "browser_content_capture": systemd_unit(browser_content_capture_timer),
        "search_index": systemd_unit(search_index_timer),
        "semantic_maintain": systemd_unit(semantic_maintain_timer),
    }
    semantic_maintain = {
        "service": systemd_unit(semantic_maintain_service),
        "timer": systemd_unit(semantic_maintain_timer),
        "latest": str(semantic_maintain_latest_path),
    }
    data = nervous_quality.audit_document(
        refresh_requested=refresh,
        refresh_index_requested=refresh_index,
        refresh_results=refresh_results,
        validations={
            "facts": facts_validation,
            "events": events_validation,
            "episodes": episodes_validation,
            "synthesis": synthesis_validation,
            "eval": eval_validation,
            "retention": retention_validation,
            "index": index_validation,
        },
        timers=timers,
        status_data=status_data,
        capture_status=capture,
        derived_refresh_status=derived,
        privacy_status=privacy,
        sources=sources,
        index_status=index_status_data,
        semantic_maintain=semantic_maintain,
        browser_latest=browser_latest if isinstance(browser_latest, dict) else None,
        browser_error=browser_error,
        browser_path=str(browser_content_latest_path),
        redaction_summary=redaction_summary,
        privacy_state_path=str(privacy_state_path),
        index_db_path=str(search_index_db_path),
        latest_path=str(quality_latest_path),
        daily_glob=str(quality_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        commands=commands,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        latest_error = latest_writer(quality_latest_path, data, 0o664)
        daily_error = jsonl_append(today_path(quality_root), data, 0o664)
        errors = [error for error in (latest_error, daily_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data
