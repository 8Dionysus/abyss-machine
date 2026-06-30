from __future__ import annotations

import grp
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import nervous_synthesis
from . import typing_nervous_adapters


RecordsReaderPort = Callable[[Path], tuple[list[dict[str, Any]], list[dict[str, Any]]]]
LatestReaderPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
LatestJsonWriterPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
LatestHistoryWriterPort = Callable[[dict[str, Any], Path, Path], list[dict[str, Any]]]
PeriodRecordWriterPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
TextWriterPort = Callable[[Path, str, int], dict[str, Any] | None]


def read_records(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return typing_nervous_adapters.load_source_records_from_root(root)


def read_latest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc}"
    if not isinstance(data, dict):
        return None, "document is not a JSON object"
    return data, None


def default_latest_history_writer(data: dict[str, Any], latest_path: Path, daily_root: Path) -> list[dict[str, Any]]:
    return typing_nervous_adapters.write_latest_and_history(data, latest_path, daily_root, mode=0o664)


def write_latest(
    data: dict[str, Any],
    latest_path: Path,
    *,
    writer: LatestJsonWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    error = writer(latest_path, data, 0o664)
    if error:
        data["ok"] = False
        data["write_errors"] = [error]
    return data


def write_latest_history(
    data: dict[str, Any],
    latest_path: Path,
    daily_root: Path,
    *,
    writer: LatestHistoryWriterPort = default_latest_history_writer,
) -> dict[str, Any]:
    errors = writer(data, latest_path, daily_root)
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
    return data


def replace_period_record(
    path: Path,
    data: dict[str, Any],
    mode: int = 0o664,
    *,
    group: str = typing_nervous_adapters.DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    period = data.get("period") if isinstance(data.get("period"), dict) else {}
    scope = str(data.get("scope") or period.get("scope") or "")
    records: list[dict[str, Any]] = []
    tmp_name: str | None = None
    try:
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        return {"path": str(path), "line": line_no, "error": "non-object synthesis JSONL record"}
                    record_period = record.get("period") if isinstance(record.get("period"), dict) else {}
                    same_period = str(record.get("scope") or record_period.get("scope") or "") == scope and record_period == period
                    if not same_period:
                        records.append(record)
        records.append(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o2775)
        except PermissionError:
            pass
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", delete=False) as tmp:
            tmp_name = tmp.name
            for record in records:
                json.dump(record, tmp, sort_keys=False, ensure_ascii=False)
                tmp.write("\n")
        os.chmod(tmp_name, mode)
        try:
            os.chown(tmp_name, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, PermissionError):
            pass
        os.replace(tmp_name, path)
        return None
    except (OSError, ValueError) as exc:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        return {"path": str(path), "error": str(exc)}


def write_text_atomic(
    path: Path,
    text: str,
    mode: int = 0o664,
    *,
    group: str = typing_nervous_adapters.DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    tmp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o2775)
        except PermissionError:
            pass
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(text)
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
        return {"path": str(path), "error": str(exc)}


def paths_document(*, latest_path: Path, hourly_root: Path, daily_root: Path) -> dict[str, str]:
    return nervous_synthesis.paths_document(
        latest_path=str(latest_path),
        hourly_glob=str(hourly_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        daily_jsonl_glob=str(daily_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        daily_markdown_glob=str(daily_root / "YYYY" / "MM" / "YYYY-MM-DD.md"),
    )


def synthesis_records(
    *,
    hourly_root: Path,
    daily_root: Path,
    records_reader: RecordsReaderPort = read_records,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records, errors = records_reader(hourly_root)
    daily_records, daily_errors = records_reader(daily_root)
    return records + daily_records, errors + daily_errors


def build_synthesis(
    *,
    episodes_root: Path,
    events_root: Path,
    latest_path: Path,
    hourly_root: Path,
    daily_root: Path,
    scope: str,
    date_value: str | None,
    hour: int | None,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    latest_writer: LatestJsonWriterPort = typing_nervous_adapters.safe_atomic_write_json,
    period_writer: PeriodRecordWriterPort = replace_period_record,
    text_writer: TextWriterPort = write_text_atomic,
) -> dict[str, Any]:
    episode_items, parse_errors = records_reader(episodes_root)
    event_items, _event_errors = records_reader(events_root)
    data = nervous_synthesis.build_candidate_from_items(
        episode_items=episode_items,
        episode_parse_errors=parse_errors,
        event_items=event_items,
        scope=scope,
        date_value=date_value,
        hour=hour,
        paths=paths_document(latest_path=latest_path, hourly_root=hourly_root, daily_root=daily_root),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        period = data.get("period") if isinstance(data.get("period"), dict) else {}
        write_paths = nervous_synthesis.write_paths(scope, period, hourly_root=hourly_root, daily_root=daily_root)
        errors = [
            error
            for error in (
                latest_writer(latest_path, data, 0o664),
                period_writer(Path(write_paths["period_jsonl"]), data, 0o664),
            )
            if error
        ]
        if "daily_markdown" in write_paths:
            md_error = text_writer(Path(write_paths["daily_markdown"]), nervous_synthesis.markdown(data), 0o664)
            if md_error:
                errors.append(md_error)
        data = nervous_synthesis.with_write_results(data, write_paths=write_paths, write_errors=errors)
    return data


def validate_synthesis(
    *,
    latest_path: Path,
    episodes_latest_path: Path,
    validate_latest_path: Path,
    hourly_root: Path,
    daily_root: Path,
    episodes_root: Path,
    events_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    latest_reader: LatestReaderPort = read_latest,
    latest_writer: LatestJsonWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(latest_path)
    episodes_latest, _episodes_latest_error = latest_reader(episodes_latest_path)
    items, parse_errors = synthesis_records(hourly_root=hourly_root, daily_root=daily_root, records_reader=records_reader)
    episode_items, _episode_errors = records_reader(episodes_root)
    event_items, _event_errors = records_reader(events_root)
    data = nervous_synthesis.validate_records(
        latest=latest,
        latest_error=latest_error,
        episodes_latest=episodes_latest,
        candidate_items=items,
        candidate_parse_errors=parse_errors,
        episode_items=episode_items,
        event_items=event_items,
        latest_path=str(latest_path),
        validate_latest_path=str(validate_latest_path),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest(data, validate_latest_path, writer=latest_writer)
    return data


def build_eval_run(
    *,
    events_validation: dict[str, Any],
    episodes_validation: dict[str, Any],
    index_validation: dict[str, Any],
    recall: dict[str, Any],
    synthesis: dict[str, Any],
    synthesis_validation: dict[str, Any],
    latest_path: Path,
    daily_root: Path,
    recall_latest_path: Path,
    synthesis_latest_path: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    latest_history_writer: LatestHistoryWriterPort = default_latest_history_writer,
) -> dict[str, Any]:
    data = nervous_synthesis.eval_run_document(
        events_validation=events_validation,
        episodes_validation=episodes_validation,
        index_validation=index_validation,
        recall=recall,
        synthesis=synthesis,
        synthesis_validation=synthesis_validation,
        latest_path=str(latest_path),
        daily_glob=str(daily_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        recall_latest_path=str(recall_latest_path),
        synthesis_latest_path=str(synthesis_latest_path),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest_history(data, latest_path, daily_root, writer=latest_history_writer)
    return data


def validate_eval(
    *,
    latest_path: Path,
    validate_latest_path: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest_enabled: bool = True,
    latest_reader: LatestReaderPort = read_latest,
    latest_writer: LatestJsonWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(latest_path)
    data = nervous_synthesis.eval_validate_document(
        latest=latest,
        latest_error=latest_error,
        latest_path=str(latest_path),
        validate_latest_path=str(validate_latest_path),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest_enabled:
        data = write_latest(data, validate_latest_path, writer=latest_writer)
    return data
