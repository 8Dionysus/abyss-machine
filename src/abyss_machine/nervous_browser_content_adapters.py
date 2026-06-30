from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Callable

from . import nervous_sources
from . import typing_nervous_adapters


ParseTimePort = Callable[[Any], dt.datetime | None]
NowPort = Callable[[], dt.datetime]
NowIsoPort = Callable[[], str]
AppendJsonlPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
WriteJsonPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]


def browser_content_jsonl_path(
    root: Path,
    value: Any | None = None,
    *,
    parse_time: ParseTimePort,
    now: NowPort,
) -> Path:
    parsed = parse_time(value) or now()
    local = parsed.astimezone()
    return root / f"{local.year:04d}" / f"{local.month:02d}" / f"{local.strftime('%Y-%m-%d')}.jsonl"


def browser_content_dedupe_key(record: dict[str, Any]) -> str:
    return nervous_sources.browser_content_dedupe_key(record)


def read_recent_jsonl_lines(path: Path, max_lines: int = 240, max_bytes: int = 2 * 1024 * 1024) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            payload = handle.read()
    except OSError:
        return []
    if start > 0:
        payload = payload.split(b"\n", 1)[-1]
    return payload.decode("utf-8", errors="replace").splitlines()[-max_lines:]


def browser_content_recent_duplicate(path: Path, record: dict[str, Any], max_lines: int = 240) -> dict[str, Any] | None:
    if not path.exists():
        return None
    key = browser_content_dedupe_key(record)
    if not key.strip("|"):
        return None
    lines = read_recent_jsonl_lines(path, max_lines=max_lines)
    for offset, line in enumerate(reversed(lines), start=1):
        try:
            previous = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(previous, dict):
            continue
        if browser_content_dedupe_key(previous) == key:
            return {
                "duplicate": True,
                "matched_recent_line_from_end": offset,
                "matched_generated_at": previous.get("generated_at"),
                "matched_captured_at": previous.get("captured_at"),
            }
    return None


def browser_content_record_from_page(
    page: dict[str, Any],
    capture_source: str,
    *,
    context_id: str | None = None,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    max_text_chars: int,
    uid: int,
    gid: int,
) -> dict[str, Any]:
    return nervous_sources.browser_content_record_from_page(
        page,
        capture_source,
        context_id=context_id,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        captured_at=str(page.get("captured_at") or now_iso()),
        source_read_at=now_iso(),
        max_text_chars=max_text_chars,
        uid=uid,
        gid=gid,
    )


def default_append_jsonl(path: Path, data: dict[str, Any], mode: int = 0o664) -> dict[str, Any] | None:
    return typing_nervous_adapters.safe_append_jsonl(path, data, mode)


def default_write_json(path: Path, data: dict[str, Any], mode: int = 0o664) -> dict[str, Any] | None:
    return typing_nervous_adapters.safe_atomic_write_json(path, data, mode)


def browser_content_store(
    page: dict[str, Any],
    capture_source: str,
    *,
    content_root: Path,
    latest_path: Path,
    context_id: str | None = None,
    write_latest: bool = True,
    schema_prefix: str,
    version: str,
    parse_time: ParseTimePort,
    now: NowPort,
    now_iso: NowIsoPort,
    max_text_chars: int,
    uid: int,
    gid: int,
    append_jsonl: AppendJsonlPort = default_append_jsonl,
    write_json: WriteJsonPort = default_write_json,
) -> dict[str, Any]:
    record = browser_content_record_from_page(
        page,
        capture_source,
        context_id=context_id,
        schema_prefix=schema_prefix,
        version=version,
        now_iso=now_iso,
        max_text_chars=max_text_chars,
        uid=uid,
        gid=gid,
    )
    path = browser_content_jsonl_path(content_root, record.get("captured_at"), parse_time=parse_time, now=now)
    duplicate = browser_content_recent_duplicate(path, record)
    error = None if duplicate else append_jsonl(path, record, 0o664)
    data = {
        "schema": f"{schema_prefix}_nervous_browser_content_ingest_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": error is None,
        "path": str(path),
        "source_id": "browser_active_tab",
        "capture_source": capture_source,
        "dedupe": duplicate or {"duplicate": False},
        "record": {
            "captured_at": record.get("captured_at"),
            "title": record.get("title"),
            "url": record.get("url"),
            "text_length": record.get("text_length"),
            "clean_text_length": record.get("clean_text_length"),
            "content_quality": record.get("content_quality"),
            "web_context_quality": record.get("web_context_quality"),
            "page_identity": record.get("page_identity"),
            "atspi_context": record.get("atspi_context"),
            "skipped_text": record.get("skipped_text"),
            "skipped_reason": record.get("skipped_reason"),
            "redaction": record.get("redaction"),
        },
    }
    if error:
        data["write_errors"] = [error]
    if write_latest:
        latest_error = write_json(latest_path, data, 0o664)
        if latest_error:
            data.setdefault("write_errors", []).append(latest_error)
            data["ok"] = False
    return data
