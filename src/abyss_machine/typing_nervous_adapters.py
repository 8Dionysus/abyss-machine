from __future__ import annotations

import datetime as dt
import collections
import fcntl
import grp
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from . import nervous_index
from . import typing_capture_contracts


DEFAULT_STATE_GROUP = "wheel"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_datetime(value: dt.datetime | None = None) -> dt.datetime:
    current = value or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return current.astimezone(dt.timezone.utc)


def daily_jsonl_path(root: Path, when: dt.datetime | None = None) -> Path:
    current = when or dt.datetime.now(dt.timezone.utc).astimezone()
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc).astimezone()
    else:
        current = current.astimezone()
    return root / f"{current.year:04d}" / f"{current.month:02d}" / f"{current.strftime('%Y-%m-%d')}.jsonl"


def read_json_document(path: Path) -> tuple[dict[str, Any] | None, str | None]:
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


def jsonl_files(root: Path) -> list[Path]:
    return nervous_index.jsonl_files(root)


def load_jsonl_records(path: Path | str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return nervous_index.load_jsonl_records(path)


def load_jsonl_records_with_metadata(path: Path | str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return nervous_index.load_jsonl_records_with_metadata(path)


def load_source_records_from_root(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return nervous_index.load_source_records_from_root(root)


def read_recent_jsonl_records(root: Path, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for path in sorted(jsonl_files(root), reverse=True):
        parsed, parse_errors = load_jsonl_records(path)
        errors.extend(parse_errors)
        for record in reversed(parsed):
            records.append(record)
            if len(records) >= limit:
                return records, errors
    return records, errors


def read_recent_jsonl_records_for_source(
    root: Path,
    source_adapter: str,
    *,
    limit: int,
    max_scan_records: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    target = str(source_adapter or "")
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    scanned = 0
    files_scanned = 0
    for path in sorted(jsonl_files(root), reverse=True):
        parsed, parse_errors = load_jsonl_records(path)
        files_scanned += 1
        errors.extend(parse_errors)
        for record in reversed(parsed):
            scanned += 1
            if isinstance(record, dict) and record.get("source_adapter") == target:
                records.append(record)
                if len(records) >= limit:
                    return records, errors, {
                        "source_adapter": target,
                        "limit": limit,
                        "max_scan_records": max_scan_records,
                        "scanned_records": scanned,
                        "files_scanned": files_scanned,
                        "exhausted": False,
                    }
            if scanned >= max_scan_records:
                return records, errors, {
                    "source_adapter": target,
                    "limit": limit,
                    "max_scan_records": max_scan_records,
                    "scanned_records": scanned,
                    "files_scanned": files_scanned,
                    "exhausted": True,
                }
    return records, errors, {
        "source_adapter": target,
        "limit": limit,
        "max_scan_records": max_scan_records,
        "scanned_records": scanned,
        "files_scanned": files_scanned,
        "exhausted": False,
    }


def codex_session_id_from_path(path: Path) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path.name, re.I)
    return match.group(1) if match else path.stem[:120]


def codex_session_tail_files(
    sessions_root: Path,
    *,
    limit: int = 4,
    state: Mapping[str, Any] | None = None,
    now: dt.datetime | None = None,
) -> list[Path]:
    root = sessions_root
    if not root.exists():
        return []

    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    files = [path for path in root.rglob("*.jsonl") if path.is_file()]
    files.sort(key=mtime, reverse=True)
    requested = max(1, min(_safe_int(limit, 1), 16))
    max_selected = max(requested, min(16, requested * 2))
    selected: list[Path] = []
    selected_text: set[str] = set()

    def add(path: Path) -> None:
        text = str(path)
        if text in selected_text:
            return
        selected.append(path)
        selected_text.add(text)

    for path in files[:requested]:
        add(path)

    state_files = state.get("files") if isinstance(state, Mapping) and isinstance(state.get("files"), Mapping) else {}
    if state_files:
        root_resolved = root.resolve()
        state_candidates: list[tuple[dt.datetime, Path]] = []
        current = _utc_datetime(now)
        for path_text, item in state_files.items():
            if not isinstance(item, Mapping):
                continue
            path = Path(str(path_text))
            try:
                resolved = path.resolve()
                resolved.relative_to(root_resolved)
            except (OSError, ValueError):
                continue
            if not path.is_file() or path.suffix != ".jsonl":
                continue
            timestamp = (
                typing_capture_contracts.typing_parse_iso(item.get("last_user_timestamp"))
                or typing_capture_contracts.typing_parse_iso(item.get("updated_at"))
            )
            if timestamp is None:
                continue
            age_sec = (current - timestamp).total_seconds()
            if age_sec > 24 * 3600:
                continue
            state_candidates.append((timestamp, path))
        state_candidates.sort(key=lambda item: item[0], reverse=True)
        for _, path in state_candidates:
            if len(selected) >= max_selected:
                break
            add(path)

    return selected


def codex_session_tail_candidate_lines(
    path: Path,
    since_line: int,
    initial_tail_lines: int,
    recovery_tail_lines: int,
    recovery_scan: bool = False,
) -> tuple[list[tuple[int, str]], int, list[dict[str, Any]], str]:
    errors: list[dict[str, Any]] = []
    candidates: list[tuple[int, str]] = []
    tail_limit = max(20, _safe_int(recovery_tail_lines if recovery_scan else initial_tail_lines or 12000, 12000))
    tail: collections.deque[tuple[int, str]] = collections.deque(maxlen=tail_limit)
    line_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_count, line in enumerate(handle, 1):
                if since_line > 0 and not recovery_scan:
                    if line_count > since_line:
                        candidates.append((line_count, line))
                else:
                    tail.append((line_count, line))
    except OSError as exc:
        errors.append({"path": str(path), "error": str(exc)})
    if since_line <= 0 or recovery_scan:
        candidates = list(tail)
    scan_mode = "recovery_tail" if recovery_scan else ("incremental" if since_line > 0 else "initial_tail")
    return candidates, line_count, errors, scan_mode


def codex_session_tail_incremental_lines(
    path: Path,
    since_line: int,
    since_byte: int,
) -> tuple[list[tuple[int, str]], int, int, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    candidates: list[tuple[int, str]] = []
    line_count = since_line
    byte_offset = since_byte
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, since_byte))
            for raw_line in handle:
                line_count += 1
                candidates.append((line_count, raw_line.decode("utf-8", errors="replace")))
            byte_offset = handle.tell()
    except OSError as exc:
        errors.append({"path": str(path), "error": str(exc)})
    return candidates, line_count, byte_offset, errors


def codex_session_tail_path_candidates(
    path: Path,
    previous: Mapping[str, Any] | None,
    *,
    initial_tail_lines: int,
    recovery_tail_lines: int,
    recovery_scan: bool = False,
) -> tuple[list[tuple[int, str]], dict[str, Any], list[dict[str, Any]]]:
    path_text = str(path)
    previous_data = previous if isinstance(previous, Mapping) else {}
    since_line = _safe_int(previous_data.get("line_count"), 0)
    previous_size = _safe_int(previous_data.get("file_size"), -1)
    previous_mtime_ns = _safe_int(previous_data.get("mtime_ns"), -1)
    previous_byte_offset = _safe_int(previous_data.get("byte_offset"), 0)
    try:
        path_stat = path.stat()
        file_size = int(path_stat.st_size)
        mtime_ns = int(path_stat.st_mtime_ns)
    except OSError as exc:
        error = {"path": path_text, "error": str(exc)}
        return [], {
            "path": path_text,
            "line_count": since_line,
            "since_line": since_line,
            "scan_mode": "stat_failed",
            "candidate_lines": 0,
            "error": str(exc),
        }, [error]

    if (
        since_line > 0
        and not recovery_scan
        and previous_size == file_size
        and previous_mtime_ns == mtime_ns
    ):
        candidate_lines: list[tuple[int, str]] = []
        line_count = since_line
        byte_offset = previous_byte_offset or file_size
        read_errors: list[dict[str, Any]] = []
        scan_mode = "unchanged"
    elif (
        since_line > 0
        and not recovery_scan
        and previous_byte_offset > 0
        and previous_byte_offset <= file_size
    ):
        candidate_lines, line_count, byte_offset, read_errors = codex_session_tail_incremental_lines(
            path,
            since_line,
            previous_byte_offset,
        )
        scan_mode = "incremental_bytes"
    else:
        candidate_lines, line_count, read_errors, scan_mode = codex_session_tail_candidate_lines(
            path,
            since_line,
            initial_tail_lines,
            recovery_tail_lines,
            recovery_scan=recovery_scan,
        )
        byte_offset = file_size

    return candidate_lines, {
        "path": path_text,
        "line_count": line_count,
        "since_line": since_line,
        "scan_mode": scan_mode,
        "file_size": file_size,
        "mtime_ns": mtime_ns,
        "byte_offset": byte_offset,
        "candidate_lines": len(candidate_lines),
    }, read_errors


def read_latest_document(
    path: Path,
    read_schema: str,
    *,
    version: str,
    now: Callable[[], str],
    default_existing_ok: bool | None = True,
) -> dict[str, Any]:
    data, error = read_json_document(path)
    read_at = now()
    if data is None:
        return {
            "schema": read_schema,
            "version": version,
            "generated_at": read_at,
            "ok": False,
            "path": str(path),
            "error": error or "missing",
        }
    data["read_schema"] = read_schema
    data["read_at"] = read_at
    if default_existing_ok is not None:
        data["ok"] = data.get("ok", default_existing_ok)
    return data


def ensure_state_history_dir(path: Path, *, group: str = DEFAULT_STATE_GROUP) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o2775)
    except PermissionError:
        pass
    try:
        os.chown(path, -1, grp.getgrnam(group).gr_gid)
    except (KeyError, PermissionError):
        pass


def atomic_write_json(path: Path, data: dict[str, Any], mode: int = 0o644, *, group: str = DEFAULT_STATE_GROUP) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    ) as tmp:
        json.dump(data, tmp, indent=2, sort_keys=False)
        tmp.write("\n")
        tmp_name = tmp.name

    os.chmod(tmp_name, mode)
    try:
        os.chown(tmp_name, -1, grp.getgrnam(group).gr_gid)
    except (KeyError, PermissionError):
        pass
    os.replace(tmp_name, path)


def safe_atomic_write_json(
    path: Path,
    data: dict[str, Any],
    mode: int = 0o664,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    try:
        atomic_write_json(path, data, mode, group=group)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def safe_append_jsonl(
    path: Path,
    data: dict[str, Any],
    mode: int = 0o664,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    try:
        ensure_state_history_dir(path.parent, group=group)
        payload = (json.dumps(data, sort_keys=False) + "\n").encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        fd = os.open(path, flags, mode)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("short append write")
                view = view[written:]
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
        try:
            os.chmod(path, mode)
        except PermissionError:
            pass
        try:
            os.chown(path, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, PermissionError):
            pass
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def write_latest_and_history(
    data: dict[str, Any],
    latest_path: Path,
    history_root: Path,
    *,
    mode: int = 0o664,
    when: dt.datetime | None = None,
    group: str = DEFAULT_STATE_GROUP,
) -> list[dict[str, Any]]:
    return [
        error
        for error in (
            safe_atomic_write_json(latest_path, data, mode, group=group),
            safe_append_jsonl(daily_jsonl_path(history_root, when), data, mode, group=group),
        )
        if error
    ]


def store_latest_history_and_index(
    data: dict[str, Any],
    *,
    write_latest: bool,
    latest_path: Path,
    history_root: Path,
    index_path: Path | None = None,
    index_document: dict[str, Any] | None = None,
    mode: int = 0o664,
    when: dt.datetime | None = None,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any]:
    if not write_latest:
        return data
    errors = write_latest_and_history(data, latest_path, history_root, mode=mode, when=when, group=group)
    if index_path is not None and index_document is not None:
        index_error = safe_atomic_write_json(index_path, index_document, mode, group=group)
        if index_error:
            errors.append(index_error)
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
    return data
