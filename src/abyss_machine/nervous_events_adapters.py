from __future__ import annotations

import datetime as dt
import grp
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import nervous_events
from . import typing_nervous_adapters


RecordsReaderPort = Callable[[Path], tuple[list[dict[str, Any]], list[dict[str, Any]]]]
RecordsWriterPort = Callable[[Path, list[dict[str, Any]]], str | None]
LatestReaderPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
LatestWriterPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
EventsBuilderPort = Callable[[list[dict[str, Any]]], tuple[list[dict[str, Any]], dict[str, Any]]]
EpisodesBuilderPort = Callable[[list[dict[str, Any]]], tuple[list[dict[str, Any]], dict[str, Any]]]


def parse_time(value: Any) -> dt.datetime | None:
    return nervous_events.parse_time(value)


def jsonl_path_for_time(root: Path, value: Any, *, now: dt.datetime | None = None) -> Path:
    parsed = parse_time(value) or now or dt.datetime.now(dt.timezone.utc).astimezone()
    local = parsed.astimezone()
    return root / f"{local.year:04d}" / f"{local.month:02d}" / f"{local.strftime('%Y-%m-%d')}.jsonl"


def jsonl_files(root: Path) -> list[Path]:
    return typing_nervous_adapters.jsonl_files(root)


def read_records(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return typing_nervous_adapters.load_source_records_from_root(root)


def read_latest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return (data if isinstance(data, dict) else None), None if isinstance(data, dict) else "non-object JSON"
    except OSError as exc:
        return None, str(exc)
    except ValueError as exc:
        return None, str(exc)


def write_jsonl_records(path: Path, records: list[dict[str, Any]], *, mode: int = 0o664, group: str = typing_nervous_adapters.DEFAULT_STATE_GROUP) -> str | None:
    tmp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", delete=False) as tmp:
            tmp_name = tmp.name
            for record in records:
                json.dump(record, tmp, ensure_ascii=False, sort_keys=False)
                tmp.write("\n")
        os.chmod(tmp_name, mode)
        try:
            os.chown(tmp_name, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, PermissionError):
            pass
        os.replace(tmp_name, path)
        return None
    except OSError as exc:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        return str(exc)


def write_derived_records(
    root: Path,
    records: list[dict[str, Any]],
    derived_by: str,
    *,
    reader: RecordsReaderPort = typing_nervous_adapters.load_jsonl_records,
    writer: RecordsWriterPort = write_jsonl_records,
    existing_files: Callable[[Path], list[Path]] = jsonl_files,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        path = jsonl_path_for_time(root, record.get("observed_at") or record.get("start_at") or record.get("generated_at"), now=now)
        grouped.setdefault(str(path), []).append(record)
    existing = {str(path) for path in existing_files(root)}
    paths = sorted(existing | set(grouped))
    files: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for path_s in paths:
        path = Path(path_s)
        loaded, parse_errors = reader(path) if path.exists() else ([], [])
        kept = [record for record in loaded if record.get("derived_by") != derived_by]
        generated = sorted(
            grouped.get(path_s, []),
            key=lambda item: (
                item.get("observed_at") or item.get("start_at") or item.get("generated_at") or "",
                item.get("event_id") or item.get("episode_id") or "",
            ),
        )
        merged = kept + generated
        error = writer(path, merged)
        if error:
            errors.append({"path": str(path), "error": error})
        files.append(
            {
                "path": str(path),
                "kept_existing": len(kept),
                "derived_written": len(generated),
                "records_written": len(merged),
                "parse_errors": len(parse_errors),
            }
        )
        errors.extend(parse_errors)
    return {
        "files": files,
        "errors": errors[:20],
        "error_count": len(errors),
    }


def write_latest(data: dict[str, Any], latest_path: Path, *, writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json) -> dict[str, Any]:
    error = writer(latest_path, data, 0o664)
    if error:
        data["ok"] = False
        data["write_errors"] = [error]
    return data


def latest_read_document(
    *,
    latest_path: Path,
    read_schema: str,
    version: str,
    generated_at: str,
    reader: LatestReaderPort = read_latest,
) -> dict[str, Any]:
    data, error = reader(latest_path)
    if data is None:
        return {
            "schema": read_schema,
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "path": str(latest_path),
            "error": error or "missing",
        }
    data = dict(data)
    data["read_schema"] = read_schema
    data["read_at"] = generated_at
    data["ok"] = data.get("ok", True)
    return data


def build_events(
    *,
    facts_root: Path,
    events_root: Path,
    latest_path: Path,
    events_from_fact_records: EventsBuilderPort,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    derived_writer: Callable[..., dict[str, Any]] = write_derived_records,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    items, parse_errors = records_reader(facts_root)
    events, event_summary = events_from_fact_records(items)
    write_report = derived_writer(events_root, events, "nervous_events_build_v1")
    data = nervous_events.events_build_document(
        items=items,
        parse_errors=parse_errors,
        events=events,
        event_summary=event_summary,
        write_report=write_report,
        facts_root=str(facts_root),
        latest_path=str(latest_path),
        daily_glob=str(events_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest(data, latest_path, writer=latest_writer)
    return data


def validate_events(
    *,
    events_root: Path,
    latest_path: Path,
    validate_latest_path: Path,
    allowed_sources: set[str],
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    latest_reader: LatestReaderPort = read_latest,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(latest_path)
    items, parse_errors = records_reader(events_root)
    data = nervous_events.events_validate_document(
        latest=latest,
        latest_error=latest_error,
        items=items,
        parse_errors=parse_errors,
        allowed_sources=allowed_sources,
        latest_path=str(latest_path),
        daily_glob=str(events_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest(data, validate_latest_path, writer=latest_writer)
    return data


def build_episodes(
    *,
    events_root: Path,
    episodes_root: Path,
    latest_path: Path,
    episodes_from_events: EpisodesBuilderPort,
    event_records_from_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    schema_prefix: str,
    version: str,
    generated_at: str,
    events_refresh: dict[str, Any] | None = None,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    derived_writer: Callable[..., dict[str, Any]] = write_derived_records,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    event_items, parse_errors = records_reader(events_root)
    events = event_records_from_items(event_items)
    episodes, episode_summary = episodes_from_events(events)
    write_report = derived_writer(episodes_root, episodes, "nervous_episodes_build_v1")
    data = nervous_events.episodes_build_document(
        event_items=event_items,
        parse_errors=parse_errors,
        events_refresh=events_refresh,
        episodes=episodes,
        episode_summary=episode_summary,
        write_report=write_report,
        events_root=str(events_root),
        latest_path=str(latest_path),
        daily_glob=str(episodes_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest(data, latest_path, writer=latest_writer)
    return data


def validate_episodes(
    *,
    episodes_root: Path,
    latest_path: Path,
    validate_latest_path: Path,
    allowed_sources: set[str],
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    latest_reader: LatestReaderPort = read_latest,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(latest_path)
    items, parse_errors = records_reader(episodes_root)
    data = nervous_events.episodes_validate_document(
        latest=latest,
        latest_error=latest_error,
        items=items,
        parse_errors=parse_errors,
        allowed_sources=allowed_sources,
        latest_path=str(latest_path),
        daily_glob=str(episodes_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest(data, validate_latest_path, writer=latest_writer)
    return data
