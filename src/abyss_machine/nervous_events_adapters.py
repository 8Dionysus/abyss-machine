from __future__ import annotations

import datetime as dt
import grp
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import nervous_events
from . import nervous_index
from . import typing_nervous_adapters


RecordsReaderPort = Callable[[Path], tuple[list[dict[str, Any]], list[dict[str, Any]]]]
RecordsWriterPort = Callable[[Path, list[dict[str, Any]]], str | None]
LatestReaderPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
LatestWriterPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
EventsBuilderPort = Callable[[list[dict[str, Any]]], tuple[list[dict[str, Any]], dict[str, Any]]]
StatefulEventsBuilderPort = Callable[..., tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]]
EpisodesBuilderPort = Callable[[list[dict[str, Any]]], tuple[list[dict[str, Any]], dict[str, Any]]]
RefusedResultPort = Callable[..., dict[str, Any]]
EventsRefreshPort = Callable[..., dict[str, Any]]


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


def source_file_observation(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {
        "device": int(stat.st_dev),
        "inode": int(stat.st_ino),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "ctime_ns": int(stat.st_ctime_ns),
    }


def exact_source_identity(
    path: Path,
    raw: bytes,
    observation: dict[str, int],
) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "line_count": len(raw.splitlines()),
        "observation": observation,
    }


def stable_source_bytes(
    path: Path,
    *,
    source_bytes_reader: Callable[[Path], bytes] = lambda source: source.read_bytes(),
    observation_reader: Callable[[Path], dict[str, int]] = source_file_observation,
) -> tuple[bytes, dict[str, int]] | None:
    try:
        for _attempt in range(2):
            before = observation_reader(path)
            raw = source_bytes_reader(path)
            after = observation_reader(path)
            if before == after and int(after.get("size_bytes", -1)) == len(raw):
                return raw, after
    except OSError:
        return None
    return None


def derived_record_storage_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    if item.get("event_id"):
        generated_at = parse_time(item.get("generated_at") or item.get("observed_at"))
        return (
            (
                generated_at.astimezone(dt.timezone.utc).isoformat()
                if generated_at is not None
                else str(item.get("generated_at") or item.get("observed_at") or "")
            ),
            str(item.get("event_id") or ""),
        )
    return (
        str(item.get("start_at") or item.get("observed_at") or item.get("generated_at") or ""),
        str(item.get("episode_id") or ""),
    )


def source_snapshot_error(
    root: Path,
    expected: dict[str, dict[str, int]],
    *,
    source_files_reader: Callable[[Path], list[Path]] = jsonl_files,
    observation_reader: Callable[[Path], dict[str, int]] = source_file_observation,
) -> str | None:
    try:
        current_files = source_files_reader(root)
    except OSError as exc:
        return f"source snapshot rescan failed: {exc}"
    if [str(path) for path in current_files] != sorted(expected):
        return "source partition set changed after derivation planning"
    for path in current_files:
        try:
            current = observation_reader(path)
        except OSError as exc:
            return f"source snapshot observation failed for {path}: {exc}"
        if current != expected.get(str(path)):
            return f"source partition changed after derivation planning: {path}"
    return None


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
        generated = sorted(grouped.get(path_s, []), key=derived_record_storage_sort_key)
        merged = kept + generated
        unchanged = bool(path.exists() and merged == loaded and not parse_errors)
        error = None if unchanged else writer(path, merged)
        if error:
            errors.append({"path": str(path), "error": error})
        files.append(
            {
                "path": str(path),
                "kept_existing": len(kept),
                "derived_written": len(generated),
                "records_written": len(merged),
                "parse_errors": len(parse_errors),
                "status": "unchanged" if unchanged else ("write_failed" if error else "written"),
            }
        )
        errors.extend(parse_errors)
    return {
        "files": files,
        "errors": errors[:20],
        "error_count": len(errors),
    }


def append_derived_records(
    root: Path,
    records: list[dict[str, Any]],
    derived_by: str,
    *,
    reader: RecordsReaderPort = typing_nervous_adapters.load_jsonl_records,
    writer: RecordsWriterPort = write_jsonl_records,
    source_bytes_reader: Callable[[Path], bytes] = lambda path: path.read_bytes(),
    source_observation_reader: Callable[[Path], dict[str, int]] = source_file_observation,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        path = jsonl_path_for_time(
            root,
            record.get("observed_at") or record.get("start_at") or record.get("generated_at"),
            now=now,
        )
        grouped.setdefault(str(path), []).append(record)
    files: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    delta_attestations: list[dict[str, Any]] = []
    for path_s, generated_items in sorted(grouped.items()):
        path = Path(path_s)
        base_snapshot = (
            stable_source_bytes(
                path,
                source_bytes_reader=source_bytes_reader,
                observation_reader=source_observation_reader,
            )
            if path.exists()
            else None
        )
        loaded, parse_errors = reader(path) if path.exists() else ([], [])
        if parse_errors:
            errors.extend(parse_errors)
            files.append(
                {
                    "path": path_s,
                    "status": "refused_existing_parse_errors",
                    "derived_added": 0,
                    "derived_updated": 0,
                    "records_written": len(loaded),
                    "parse_errors": len(parse_errors),
                }
            )
            continue
        foreign = [record for record in loaded if record.get("derived_by") != derived_by]
        existing_derived = {
            str(record.get("event_id") or record.get("episode_id") or nervous_index.stable_json_sha256(record)): record
            for record in loaded
            if record.get("derived_by") == derived_by
        }
        added = 0
        updated = 0
        for record in generated_items:
            identity = str(record.get("event_id") or record.get("episode_id") or nervous_index.stable_json_sha256(record))
            previous = existing_derived.get(identity)
            if previous is None:
                added += 1
            elif previous != record:
                updated += 1
            existing_derived[identity] = record
        generated = sorted(existing_derived.values(), key=derived_record_storage_sort_key)
        merged = foreign + generated
        unchanged = bool(path.exists() and merged == loaded)
        error = None if unchanged else writer(path, merged)
        if error:
            errors.append({"path": path_s, "error": error})
        elif not unchanged and base_snapshot is not None:
            current_snapshot = stable_source_bytes(
                path,
                source_bytes_reader=source_bytes_reader,
                observation_reader=source_observation_reader,
            )
            if current_snapshot is not None:
                base_raw, base_observation = base_snapshot
                current_raw, current_observation = current_snapshot
                if (
                    len(current_raw) > len(base_raw)
                    and current_raw[: len(base_raw)] == base_raw
                    and (not base_raw or base_raw.endswith((b"\n", b"\r")))
                ):
                    base_identity = exact_source_identity(path, base_raw, base_observation)
                    current_identity = exact_source_identity(path, current_raw, current_observation)
                    delta_attestations.append(
                        nervous_events.source_delta_attestation(
                            path=path_s,
                            basis="append_only",
                            base={
                                "sha256": base_identity["sha256"],
                                "size_bytes": base_identity["size_bytes"],
                                "line_count": base_identity["line_count"],
                            },
                            current=current_identity,
                        )
                    )
        files.append(
            {
                "path": path_s,
                "status": "unchanged" if unchanged else ("write_failed" if error else "written"),
                "derived_added": added,
                "derived_updated": updated,
                "records_written": len(merged),
                "parse_errors": 0,
            }
        )
    return {
        "files": files,
        "errors": errors[:20],
        "error_count": len(errors),
        "derived_added": sum(int(item.get("derived_added") or 0) for item in files),
        "derived_updated": sum(int(item.get("derived_updated") or 0) for item in files),
        "delta_attestations": delta_attestations,
    }


def replace_derived_partitions(
    root: Path,
    records: list[dict[str, Any]],
    derived_by: str,
    partition_paths: list[Path] | tuple[Path, ...],
    *,
    reader: RecordsReaderPort = typing_nervous_adapters.load_jsonl_records,
    writer: RecordsWriterPort = write_jsonl_records,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    partitions = sorted({Path(path) for path in partition_paths}, key=str)
    return write_derived_records(
        root,
        records,
        derived_by,
        reader=reader,
        writer=writer,
        existing_files=lambda _root: partitions,
        now=now,
    )


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


def build_events_incremental(
    *,
    facts_root: Path,
    events_root: Path,
    latest_path: Path,
    events_from_fact_records_with_state: StatefulEventsBuilderPort,
    schema_prefix: str,
    version: str,
    generated_at: str,
    derivation_identity: str | None = None,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    source_files_reader: Callable[[Path], list[Path]] = jsonl_files,
    source_bytes_reader: Callable[[Path], bytes] = lambda path: path.read_bytes(),
    source_observation_reader: Callable[[Path], dict[str, int]] = source_file_observation,
    source_snapshot_validator: Callable[..., str | None] = source_snapshot_error,
    previous_latest_reader: LatestReaderPort = read_latest,
    full_derived_writer: Callable[..., dict[str, Any]] = write_derived_records,
    append_derived_writer: Callable[..., dict[str, Any]] = append_derived_records,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
    monotonic: Callable[[], float] = time.monotonic,
    force_full: bool = False,
) -> dict[str, Any]:
    started = monotonic()
    current_derivation_identity = derivation_identity or nervous_events.event_derivation_identity(
        thresholds=nervous_events.thermal_event_thresholds(),
        deferred_source_ids=set(),
        schema_prefix=schema_prefix,
        version=version,
    )
    previous_latest, previous_latest_error = previous_latest_reader(latest_path)
    previous_data = previous_latest if isinstance(previous_latest, dict) else {}
    previous_incremental = (
        previous_data.get("incremental")
        if isinstance(previous_data.get("incremental"), dict)
        else {}
    )
    previous_sources_raw = previous_incremental.get("source_files")
    previous_sources = previous_sources_raw if isinstance(previous_sources_raw, list) else []
    previous_by_path = {
        str(item.get("path")): item
        for item in previous_sources
        if isinstance(item, dict) and item.get("path")
    }
    previous_paths = [str(item.get("path")) for item in previous_sources if isinstance(item, dict) and item.get("path")]
    source_files = source_files_reader(facts_root)
    current_paths = [str(path) for path in source_files]
    fallback_reasons: list[str] = []
    if previous_latest_error or previous_data.get("ok") is not True:
        fallback_reasons.append("previous_successful_build_missing")
    if previous_incremental.get("valid") is not True:
        fallback_reasons.append("previous_incremental_state_invalid")
    if previous_incremental.get("abi") != nervous_events.EVENT_DERIVATION_INCREMENTAL_ABI:
        fallback_reasons.append("incremental_abi_mismatch")
    if previous_incremental.get("derivation_identity") != current_derivation_identity:
        fallback_reasons.append("derivation_identity_mismatch")
    if not isinstance(previous_incremental.get("final_state"), dict):
        fallback_reasons.append("previous_boundary_state_missing")
    if current_paths[: len(previous_paths)] != previous_paths:
        fallback_reasons.append("source_partition_history_changed")
    if force_full:
        fallback_reasons.append("full_rebuild_forced")

    scan_started = monotonic()
    identities: list[dict[str, Any]] = []
    source_observations: dict[str, dict[str, int]] = {}
    raw_by_path: dict[str, bytes] = {}
    content_bytes_hashed = 0
    content_bytes_reused = 0
    observation_reuse_allowed = not fallback_reasons
    for path in source_files:
        path_text = str(path)
        try:
            observation = source_observation_reader(path)
        except OSError as exc:
            fallback_reasons.append(f"source_observation_failed:{path_text}:{exc}")
            continue
        source_observations[path_text] = observation
        previous = previous_by_path.get(path_text) if isinstance(previous_by_path.get(path_text), dict) else {}
        if (
            observation_reuse_allowed
            and previous
            and previous.get("observation") == observation
            and int(previous.get("size_bytes") or 0) == int(observation.get("size_bytes", -1))
            and str(previous.get("sha256") or "")
        ):
            identities.append(dict(previous))
            content_bytes_reused += int(previous.get("size_bytes") or 0)
            continue
        try:
            raw: bytes | None = None
            for _attempt in range(2):
                before = source_observation_reader(path)
                candidate = source_bytes_reader(path)
                after = source_observation_reader(path)
                if before == after and int(after.get("size_bytes", -1)) == len(candidate):
                    raw = candidate
                    observation = after
                    break
            if raw is None:
                raise OSError("source changed repeatedly while being read")
        except OSError as exc:
            fallback_reasons.append(f"source_read_failed:{path_text}:{exc}")
            continue
        source_observations[path_text] = observation
        raw_by_path[path_text] = raw
        content_bytes_hashed += len(raw)
        identities.append(
            {
                "path": path_text,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "line_count": len(raw.splitlines()),
                "observation": observation,
            }
        )
    identity_by_path = {str(item["path"]): item for item in identities}
    if len(identities) != len(source_files):
        fallback_reasons.append("source_identity_incomplete")

    tail_specs: list[tuple[Path, bytes, int]] = []
    delta_attestations: list[dict[str, Any]] = []
    if not fallback_reasons and previous_paths:
        for path_text in previous_paths[:-1]:
            previous = previous_by_path[path_text]
            current = identity_by_path.get(path_text, {})
            if str(current.get("sha256") or "") != str(previous.get("sha256") or ""):
                fallback_reasons.append(f"historical_partition_changed:{path_text}")
        last_path_text = previous_paths[-1]
        previous_last = previous_by_path[last_path_text]
        current_last = identity_by_path.get(last_path_text, {})
        if not fallback_reasons and current_last:
            if str(current_last.get("sha256") or "") != str(previous_last.get("sha256") or ""):
                raw = raw_by_path[last_path_text]
                previous_size = int(previous_last.get("size_bytes") or 0)
                previous_hash = str(previous_last.get("sha256") or "")
                if (
                    previous_size < 0
                    or len(raw) <= previous_size
                    or hashlib.sha256(raw[:previous_size]).hexdigest() != previous_hash
                    or (previous_size > 0 and raw[:previous_size][-1:] != b"\n")
                ):
                    fallback_reasons.append(f"last_partition_not_append_only:{last_path_text}")
                else:
                    tail_specs.append(
                        (
                            Path(last_path_text),
                            raw[previous_size:],
                            int(previous_last.get("line_count") or 0),
                        )
                    )
                    delta_attestations.append(
                        nervous_events.source_delta_attestation(
                            path=last_path_text,
                            basis="append_only",
                            base={
                                "sha256": str(previous_last.get("sha256") or ""),
                                "size_bytes": int(previous_last.get("size_bytes") or 0),
                                "line_count": int(previous_last.get("line_count") or 0),
                            },
                            current=current_last,
                        )
                    )
    if not fallback_reasons:
        for path_text in current_paths[len(previous_paths):]:
            raw = raw_by_path[path_text]
            tail_specs.append((Path(path_text), raw, 0))
            delta_attestations.append(
                nervous_events.source_delta_attestation(
                    path=path_text,
                    basis="new_partition",
                    base=None,
                    current=identity_by_path[path_text],
                )
            )
    scan_finished = monotonic()

    parse_started = monotonic()
    strategy = "append_state_delta" if not fallback_reasons else "full_rebuild"
    if strategy == "append_state_delta":
        items: list[dict[str, Any]] = []
        parse_errors: list[dict[str, Any]] = []
        for path, raw, line_offset in tail_specs:
            identity = identity_by_path[str(path)]
            parsed, errors = nervous_index.parse_jsonl_records_with_metadata(
                path,
                raw.decode("utf-8", errors="replace"),
                source_sha256=str(identity["sha256"]),
                line_offset=line_offset,
            )
            items.extend(parsed)
            parse_errors.extend(errors)
        items = nervous_index.sort_source_records(items)
        parse_finished = monotonic()
        derive_started = monotonic()
        events, delta_summary, final_state = events_from_fact_records_with_state(
            items,
            initial_state=previous_incremental.get("final_state"),
        )
        derive_finished = monotonic()
        write_started = monotonic()
        snapshot_failure = source_snapshot_validator(facts_root, source_observations)
        if snapshot_failure is None:
            write_report = append_derived_writer(events_root, events, "nervous_events_build_v1")
        else:
            write_report = {
                "files": [],
                "errors": [{"error": snapshot_failure}],
                "error_count": 1,
                "derived_added": 0,
                "derived_updated": 0,
            }
        write_finished = monotonic()
        event_summary = nervous_events.merge_event_summaries(
            previous_data.get("summary") if isinstance(previous_data.get("summary"), dict) else {},
            delta_summary,
        )
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
        data["source"]["records_seen"] = int(event_summary.get("input_snapshots") or 0)
        if not events:
            data["latest_event"] = previous_data.get("latest_event")
        delta_admission_ok = bool(
            not parse_errors
            and int(write_report.get("error_count") or 0) == 0
            and int(write_report.get("derived_added") or 0) == len(events)
            and int(write_report.get("derived_updated") or 0) == 0
        )
        if not delta_admission_ok:
            data["ok"] = False
            data["incremental_error"] = "append-state delta admission failed; full rebuild required"
    else:
        items, parse_errors = records_reader(facts_root)
        parse_finished = monotonic()
        derive_started = monotonic()
        events, event_summary, final_state = events_from_fact_records_with_state(items, initial_state=None)
        derive_finished = monotonic()
        write_started = monotonic()
        snapshot_failure = source_snapshot_validator(facts_root, source_observations)
        if snapshot_failure is None:
            write_report = full_derived_writer(events_root, events, "nervous_events_build_v1")
        else:
            write_report = {
                "files": [],
                "errors": [{"error": snapshot_failure}],
                "error_count": 1,
            }
        write_finished = monotonic()
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
        delta_admission_ok = False

    if snapshot_failure is not None:
        data["refused"] = True
        data["decision"] = "source_snapshot_changed"
        data["error"] = snapshot_failure

    state_valid = bool(data.get("ok") and not parse_errors)
    data["incremental"] = {
        "abi": nervous_events.EVENT_DERIVATION_INCREMENTAL_ABI,
        "derivation_identity": current_derivation_identity,
        "valid": state_valid,
        "strategy": strategy,
        "fallback_reasons": fallback_reasons,
        "base_generated_at": previous_data.get("generated_at") if strategy == "append_state_delta" else None,
        "source_files": identities,
        "final_state": final_state if state_valid else None,
        "delta": {
            "source_records": len(items) if strategy == "append_state_delta" else None,
            "events": len(events) if strategy == "append_state_delta" else None,
            "admitted": delta_admission_ok if strategy == "append_state_delta" else None,
        },
        "delta_attestations": (
            [
                *delta_attestations,
                *(
                    write_report.get("delta_attestations")
                    if isinstance(write_report.get("delta_attestations"), list)
                    else []
                ),
            ]
            if strategy == "append_state_delta" and delta_admission_ok
            else []
        ),
        "timings_ms": {
            "source_scan_and_hash": round((scan_finished - scan_started) * 1000.0, 3),
            "source_parse": round((parse_finished - parse_started) * 1000.0, 3),
            "derive": round((derive_finished - derive_started) * 1000.0, 3),
            "write": round((write_finished - write_started) * 1000.0, 3),
            "total_before_latest_write": round((write_finished - started) * 1000.0, 3),
        },
        "source_scan": {
            "partitions_reused_by_observation": sum(
                1 for item in identities if str(item.get("path")) not in raw_by_path
            ),
            "content_bytes_reused": content_bytes_reused,
            "content_bytes_hashed": content_bytes_hashed,
            "observation_fields": ["device", "inode", "size_bytes", "mtime_ns", "ctime_ns"],
        },
    }
    if write_latest_enabled:
        data = write_latest(data, latest_path, writer=latest_writer)
    return data


def run_events_build(
    *,
    privacy: dict[str, Any] | None,
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
    refused_result_builder: RefusedResultPort = nervous_events.events_build_refused_result,
    events_from_fact_records_with_state: StatefulEventsBuilderPort | None = None,
    derivation_identity: str | None = None,
    force_full: bool = False,
) -> dict[str, Any]:
    if isinstance(privacy, dict) and bool(privacy.get("global_pause")):
        data = refused_result_builder(
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )
        if write_latest_enabled:
            data = write_latest(data, latest_path, writer=latest_writer)
        return data
    if events_from_fact_records_with_state is not None:
        return build_events_incremental(
            facts_root=facts_root,
            events_root=events_root,
            latest_path=latest_path,
            events_from_fact_records_with_state=events_from_fact_records_with_state,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
            derivation_identity=derivation_identity,
            write_latest_enabled=write_latest_enabled,
            latest_writer=latest_writer,
            force_full=force_full,
        )
    return build_events(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records=events_from_fact_records,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        write_latest_enabled=write_latest_enabled,
        records_reader=records_reader,
        derived_writer=derived_writer,
        latest_writer=latest_writer,
    )


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


def build_episodes_incremental(
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
    source_files_reader: Callable[[Path], list[Path]] = jsonl_files,
    source_bytes_reader: Callable[[Path], bytes] = lambda path: path.read_bytes(),
    source_observation_reader: Callable[[Path], dict[str, int]] = source_file_observation,
    source_snapshot_validator: Callable[..., str | None] = source_snapshot_error,
    previous_latest_reader: LatestReaderPort = read_latest,
    full_derived_writer: Callable[..., dict[str, Any]] = write_derived_records,
    partition_derived_writer: Callable[..., dict[str, Any]] = replace_derived_partitions,
    episode_records_reader: RecordsReaderPort = read_records,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
    monotonic: Callable[[], float] = time.monotonic,
    force_full: bool = False,
) -> dict[str, Any]:
    started = monotonic()
    current_derivation_identity = nervous_events.episode_derivation_identity(
        schema_prefix=schema_prefix,
        version=version,
    )
    previous_latest, previous_error = previous_latest_reader(latest_path)
    previous_data = previous_latest if isinstance(previous_latest, dict) else {}
    previous_incremental = (
        previous_data.get("incremental")
        if isinstance(previous_data.get("incremental"), dict)
        else {}
    )
    previous_entries_raw = previous_incremental.get("source_files")
    previous_entries_list = previous_entries_raw if isinstance(previous_entries_raw, list) else []
    previous_entries = {
        str(item.get("path")): item
        for item in previous_entries_list
        if isinstance(item, dict) and item.get("path")
    }

    def manifest_identity(entries: dict[str, dict[str, Any]]) -> str:
        return nervous_index.stable_json_sha256({
            "abi": nervous_events.EPISODE_DERIVATION_INCREMENTAL_ABI,
            "source_files": [entries[path] for path in sorted(entries)],
        })

    fallback_reasons: list[str] = []
    if previous_error or previous_data.get("ok") is not True:
        fallback_reasons.append("previous_successful_build_missing")
    if previous_incremental.get("valid") is not True:
        fallback_reasons.append("previous_incremental_state_invalid")
    if previous_incremental.get("abi") != nervous_events.EPISODE_DERIVATION_INCREMENTAL_ABI:
        fallback_reasons.append("incremental_abi_mismatch")
    if previous_incremental.get("derivation_identity") != current_derivation_identity:
        fallback_reasons.append("derivation_identity_mismatch")
    if (
        previous_entries
        and previous_incremental.get("source_manifest_identity")
        != manifest_identity(previous_entries)
    ):
        fallback_reasons.append("source_manifest_identity_mismatch")
    if force_full:
        fallback_reasons.append("full_rebuild_forced")
    incremental = not fallback_reasons

    scan_started = monotonic()
    source_files = source_files_reader(events_root)
    current_paths = [str(path) for path in source_files]
    current_path_set = set(current_paths)
    source_observations: dict[str, dict[str, int]] = {}
    identities: dict[str, dict[str, Any]] = {}
    raw_by_path: dict[str, bytes] = {}
    unchanged_paths: list[str] = []
    metadata_refreshed_paths: list[str] = []
    changed_paths: list[str] = []
    source_errors: list[dict[str, Any]] = []
    content_bytes_reused = 0
    content_bytes_hashed = 0
    for path in source_files:
        path_text = str(path)
        previous = previous_entries.get(path_text) if isinstance(previous_entries.get(path_text), dict) else {}
        try:
            observation = source_observation_reader(path)
        except OSError as exc:
            source_errors.append({"path": path_text, "error": str(exc)})
            continue
        source_observations[path_text] = observation
        if (
            incremental
            and previous
            and previous.get("observation") == observation
            and int(previous.get("size_bytes") or 0) == int(observation.get("size_bytes", -1))
            and str(previous.get("sha256") or "")
        ):
            identities[path_text] = {
                "path": path_text,
                "sha256": str(previous.get("sha256") or ""),
                "size_bytes": int(previous.get("size_bytes") or 0),
                "line_count": int(previous.get("line_count") or 0),
                "observation": observation,
            }
            unchanged_paths.append(path_text)
            content_bytes_reused += int(previous.get("size_bytes") or 0)
            continue
        try:
            raw: bytes | None = None
            for _attempt in range(2):
                before = source_observation_reader(path)
                candidate = source_bytes_reader(path)
                after = source_observation_reader(path)
                if before == after and int(after.get("size_bytes", -1)) == len(candidate):
                    raw = candidate
                    observation = after
                    break
            if raw is None:
                raise OSError("source changed repeatedly while being read")
        except OSError as exc:
            source_errors.append({"path": path_text, "error": str(exc)})
            continue
        source_observations[path_text] = observation
        identity = {
            "path": path_text,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
            "line_count": len(raw.splitlines()),
            "observation": observation,
        }
        identities[path_text] = identity
        content_bytes_hashed += len(raw)
        if (
            incremental
            and previous
            and str(previous.get("sha256") or "") == identity["sha256"]
            and int(previous.get("size_bytes") or 0) == identity["size_bytes"]
            and int(previous.get("line_count") or 0) == identity["line_count"]
        ):
            unchanged_paths.append(path_text)
            metadata_refreshed_paths.append(path_text)
        else:
            changed_paths.append(path_text)
            raw_by_path[path_text] = raw
    removed_paths = sorted(set(previous_entries) - current_path_set) if incremental else []
    if source_errors or len(identities) != len(source_files):
        incremental = False
        fallback_reasons.append("source_snapshot_incomplete")
    scan_finished = monotonic()

    parse_started = monotonic()
    all_items: list[dict[str, Any]] = []
    all_parse_errors: list[dict[str, Any]] = []
    source_entries: dict[str, dict[str, Any]] = {}
    generated_episodes: list[dict[str, Any]] = []
    partition_local = True

    def episode_paths(episodes: list[dict[str, Any]]) -> list[str]:
        return sorted({
            str(
                jsonl_path_for_time(
                    episodes_root,
                    episode.get("start_at") or episode.get("generated_at"),
                )
            )
            for episode in episodes
        })

    def episode_groups(episodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {"day": day, "category": category}
            for day, category in sorted({
                (
                    str(episode.get("day") or ""),
                    str(episode.get("category") or "misc"),
                )
                for episode in episodes
            })
        ]

    parse_paths = changed_paths if incremental else current_paths
    if not incremental:
        for path_text in current_paths:
            if path_text in raw_by_path:
                continue
            try:
                raw_by_path[path_text] = source_bytes_reader(Path(path_text))
            except OSError as exc:
                source_errors.append({"path": path_text, "error": str(exc)})
    for path_text in parse_paths:
        raw = raw_by_path.get(path_text)
        if raw is None:
            continue
        parsed, errors = nervous_index.parse_jsonl_records_with_metadata(
            path_text,
            raw.decode("utf-8", errors="replace"),
            source_sha256=str(identities.get(path_text, {}).get("sha256") or ""),
        )
        all_items.extend(parsed)
        all_parse_errors.extend(errors)
        events = event_records_from_items(parsed)
        local_episodes, local_summary = episodes_from_events(events)
        generated_episodes.extend(local_episodes)
        source_entries[path_text] = {
            **identities[path_text],
            "summary": local_summary,
            "parse_error_count": len(errors),
            "parse_errors": errors[:20],
            "episode_paths": episode_paths(local_episodes),
            "episode_groups": episode_groups(local_episodes),
        }
    all_items = nervous_index.sort_source_records(all_items)
    parse_finished = monotonic()

    derive_started = monotonic()
    if incremental:
        for path in unchanged_paths:
            source_entries[path] = dict(previous_entries[path])
            if path in metadata_refreshed_paths:
                source_entries[path]["observation"] = identities[path]["observation"]
        group_owners: dict[tuple[str, str], list[str]] = {}
        for path, entry in source_entries.items():
            groups = entry.get("episode_groups") if isinstance(entry.get("episode_groups"), list) else []
            for group in groups:
                if not isinstance(group, dict):
                    continue
                key = (
                    str(group.get("day") or ""),
                    str(group.get("category") or "misc"),
                )
                group_owners.setdefault(key, []).append(path)
        locality_conflicts = {
            key: sorted(set(paths))
            for key, paths in group_owners.items()
            if len(set(paths)) > 1
        }
        if locality_conflicts:
            fallback = build_episodes_incremental(
                events_root=events_root,
                episodes_root=episodes_root,
                latest_path=latest_path,
                episodes_from_events=episodes_from_events,
                event_records_from_items=event_records_from_items,
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
                events_refresh=events_refresh,
                write_latest_enabled=False,
                source_files_reader=source_files_reader,
                source_bytes_reader=source_bytes_reader,
                source_observation_reader=source_observation_reader,
                source_snapshot_validator=source_snapshot_validator,
                previous_latest_reader=previous_latest_reader,
                full_derived_writer=full_derived_writer,
                partition_derived_writer=partition_derived_writer,
                episode_records_reader=episode_records_reader,
                latest_writer=latest_writer,
                monotonic=monotonic,
                force_full=True,
            )
            fallback_incremental = (
                fallback.get("incremental")
                if isinstance(fallback.get("incremental"), dict)
                else {}
            )
            fallback_incremental["fallback_reasons"] = [
                *(
                    fallback_incremental.get("fallback_reasons")
                    if isinstance(fallback_incremental.get("fallback_reasons"), list)
                    else []
                ),
                "episode_group_ownership_conflict",
            ]
            fallback_timings = (
                fallback_incremental.get("timings_ms")
                if isinstance(fallback_incremental.get("timings_ms"), dict)
                else {}
            )
            fallback_incremental["timings_ms"] = {
                **fallback_timings,
                "total_before_latest_write": round((monotonic() - started) * 1000.0, 3),
            }
            fallback["incremental"] = fallback_incremental
            if write_latest_enabled:
                fallback = write_latest(fallback, latest_path, writer=latest_writer)
            return fallback
        aggregate_summary = nervous_events.merge_episode_summaries([
            entry.get("summary") if isinstance(entry.get("summary"), dict) else {}
            for entry in source_entries.values()
        ])
        old_episode_paths = {
            str(episode_path)
            for path in [*changed_paths, *removed_paths]
            for episode_path in (
                previous_entries.get(path, {}).get("episode_paths")
                if isinstance(previous_entries.get(path, {}).get("episode_paths"), list)
                else []
            )
        }
        new_episode_paths = set(episode_paths(generated_episodes))
        partitions_to_replace = sorted(old_episode_paths | new_episode_paths)
        strategy = "file_partition_delta"
    else:
        events = event_records_from_items(all_items)
        oracle_episodes, oracle_summary = episodes_from_events(events)
        local_sorted = sorted(
            generated_episodes,
            key=lambda item: (item.get("start_at") or "", item.get("episode_id") or ""),
        )
        partition_local = local_sorted == oracle_episodes
        generated_episodes = oracle_episodes
        aggregate_summary = oracle_summary
        partitions_to_replace = []
        strategy = "full_rebuild"
    derive_finished = monotonic()

    snapshot_failure = source_snapshot_validator(events_root, source_observations)
    if source_errors:
        snapshot_failure = "event source snapshot could not be read consistently"
    if incremental and not partition_local:
        snapshot_failure = "episode partition locality changed; full rebuild required"
    write_started = monotonic()
    if snapshot_failure is not None:
        write_report = {
            "files": [],
            "errors": [{"error": snapshot_failure}, *source_errors[:19]],
            "error_count": 1 + len(source_errors),
        }
    elif incremental:
        write_report = partition_derived_writer(
            episodes_root,
            generated_episodes,
            "nervous_episodes_build_v1",
            [Path(path) for path in partitions_to_replace],
        )
    else:
        write_report = full_derived_writer(
            episodes_root,
            generated_episodes,
            "nervous_episodes_build_v1",
        )
    write_finished = monotonic()

    data = nervous_events.episodes_build_document(
        event_items=all_items,
        parse_errors=all_parse_errors,
        events_refresh=events_refresh,
        episodes=generated_episodes,
        episode_summary=aggregate_summary,
        write_report=write_report,
        events_root=str(events_root),
        latest_path=str(latest_path),
        daily_glob=str(episodes_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    data["source"]["records_seen"] = int(aggregate_summary.get("input_events") or 0)
    total_parse_errors = sum(
        int(entry.get("parse_error_count") or 0)
        for entry in source_entries.values()
    )
    data["source"]["parse_errors"] = total_parse_errors
    if total_parse_errors:
        data["ok"] = False
    if snapshot_failure is not None:
        data["ok"] = False
        data["refused"] = True
        data["decision"] = "source_snapshot_changed"
        data["error"] = snapshot_failure
    elif incremental and partitions_to_replace:
        current_items, current_errors = episode_records_reader(episodes_root)
        current_episodes = [
            item["record"]
            for item in current_items
            if isinstance(item.get("record"), dict)
            and item["record"].get("schema") == f"{schema_prefix}_nervous_episode_v1"
        ]
        current_episodes.sort(
            key=lambda item: (item.get("start_at") or "", item.get("episode_id") or "")
        )
        data["latest_episode"] = nervous_events.episode_latest_projection(
            current_episodes[-1] if current_episodes else None
        )
        if current_errors:
            data["ok"] = False
            data["post_write_errors"] = current_errors[:20]
    elif incremental:
        data["latest_episode"] = previous_data.get("latest_episode")

    state_valid = bool(data.get("ok") and partition_local and not total_parse_errors)
    data["incremental"] = {
        "abi": nervous_events.EPISODE_DERIVATION_INCREMENTAL_ABI,
        "derivation_identity": current_derivation_identity,
        "valid": state_valid,
        "strategy": strategy,
        "fallback_reasons": fallback_reasons,
        "source_files": [source_entries[path] for path in sorted(source_entries)],
        "source_manifest_identity": manifest_identity(source_entries),
        "partition_local": partition_local,
        "source_partitions": {
            "total": len(source_files),
            "changed": len(changed_paths) if strategy == "file_partition_delta" else len(source_files),
            "unchanged": len(unchanged_paths) if strategy == "file_partition_delta" else 0,
            "removed": len(removed_paths),
            "metadata_refreshed": len(metadata_refreshed_paths),
            "episode_partitions_replaced": len(partitions_to_replace),
        },
        "delta": {
            "source_events": len(all_items) if strategy == "file_partition_delta" else None,
            "episodes": len(generated_episodes) if strategy == "file_partition_delta" else None,
        },
        "source_scan": {
            "partitions_reused_by_observation": len(unchanged_paths) - len(metadata_refreshed_paths),
            "content_bytes_reused": content_bytes_reused,
            "content_bytes_hashed": content_bytes_hashed,
            "observation_fields": ["device", "inode", "size_bytes", "mtime_ns", "ctime_ns"],
        },
        "timings_ms": {
            "source_scan": round((scan_finished - scan_started) * 1000.0, 3),
            "source_parse": round((parse_finished - parse_started) * 1000.0, 3),
            "derive": round((derive_finished - derive_started) * 1000.0, 3),
            "write": round((write_finished - write_started) * 1000.0, 3),
            "total_before_latest_write": round((write_finished - started) * 1000.0, 3),
        },
    }
    if write_latest_enabled:
        data = write_latest(data, latest_path, writer=latest_writer)
    return data


def run_episodes_build(
    *,
    privacy: dict[str, Any] | None,
    events_root: Path,
    episodes_root: Path,
    latest_path: Path,
    episodes_from_events: EpisodesBuilderPort,
    event_records_from_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    schema_prefix: str,
    version: str,
    generated_at: str,
    events_builder: EventsRefreshPort,
    refresh_events: bool = True,
    write_latest_enabled: bool = True,
    records_reader: RecordsReaderPort = read_records,
    derived_writer: Callable[..., dict[str, Any]] = write_derived_records,
    latest_writer: LatestWriterPort = typing_nervous_adapters.safe_atomic_write_json,
    refused_result_builder: RefusedResultPort = nervous_events.episodes_build_refused_result,
    incremental_enabled: bool = False,
    force_full: bool = False,
) -> dict[str, Any]:
    if isinstance(privacy, dict) and bool(privacy.get("global_pause")):
        data = refused_result_builder(
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )
        if write_latest_enabled:
            data = write_latest(data, latest_path, writer=latest_writer)
        return data
    events_refresh = events_builder(write_latest=True) if refresh_events else None
    if incremental_enabled:
        return build_episodes_incremental(
            events_root=events_root,
            episodes_root=episodes_root,
            latest_path=latest_path,
            episodes_from_events=episodes_from_events,
            event_records_from_items=event_records_from_items,
            events_refresh=events_refresh,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
            write_latest_enabled=write_latest_enabled,
            latest_writer=latest_writer,
            force_full=force_full,
        )
    return build_episodes(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=episodes_from_events,
        event_records_from_items=event_records_from_items,
        events_refresh=events_refresh,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        write_latest_enabled=write_latest_enabled,
        records_reader=records_reader,
        derived_writer=derived_writer,
        latest_writer=latest_writer,
    )


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
