from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import struct
import time
import warnings
from pathlib import Path
from typing import Any, Callable

from . import nervous_sources
from . import typing_nervous_adapters


ParseTimePort = Callable[[Any], dt.datetime | None]
NowPort = Callable[[], dt.datetime]
NowIsoPort = Callable[[], str]
AppendJsonlPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
WriteJsonPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
EnvIntPort = Callable[[str, int, int, int], int]
AtspiLoaderPort = Callable[[], Any]
StorePagePort = Callable[..., dict[str, Any]]
WebContextSummaryPort = Callable[[list[dict[str, Any]]], dict[str, Any]]
WebSocketConnectPort = Callable[..., Any]
BidiCallPort = Callable[[Any, int, str, dict[str, Any]], dict[str, Any]]
BrowserHistoryRowsPort = Callable[[Path, str], tuple[list[dict[str, Any]], str | None]]
BrowserContentRecentRecordsPort = Callable[[float, int], tuple[list[dict[str, Any]], list[dict[str, Any]]]]


BROWSER_CONTENT_CAPTURE_SCRIPT = r"""
(() => {
  const maxChars = 120000;
  const reasons = [];
  const sensitiveSelectors = [
    'input[type="password"]',
    'input[autocomplete*="password" i]',
    'input[name*="password" i]',
    'input[id*="password" i]',
    'input[name*="passwd" i]',
    'input[name*="token" i]',
    'input[name*="secret" i]',
    'input[name*="otp" i]',
    'input[name*="2fa" i]',
    'input[name*="mfa" i]',
    'textarea[name*="secret" i]',
    'textarea[name*="token" i]'
  ];
  const hasSensitiveFields = !!document.querySelector(sensitiveSelectors.join(','));
  if (hasSensitiveFields) {
    reasons.push('sensitive_form_field');
  }
  const url = String(location.href || '');
  const title = String(document.title || '');
  const sensitiveLocation = /\b(login|sign[\s_-]?in|auth|oauth|password|passwd|2fa|mfa|otp|checkout|billing|bank|token)\b/i.test(`${url} ${title}`);
  if (sensitiveLocation) {
    reasons.push('url_or_title_sensitive');
  }
  function normalizeText(value) {
    return String(value || '')
      .replace(/\r/g, '\n')
      .replace(/[ \t\f\v]+/g, ' ')
      .replace(/ *\n */g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }
  let text = '';
  if (!hasSensitiveFields && !sensitiveLocation) {
    const source = document.body || document.documentElement;
    if (source) {
      const root = source.cloneNode(true);
      root.querySelectorAll('script,style,noscript,svg,canvas,template,input,textarea,select,button,[contenteditable="true"],[role="textbox"],[aria-multiline="true"]').forEach((node) => node.remove());
      text = normalizeText(root.innerText || root.textContent || '');
    }
  }
  return {
    schema: 'abyss_browser_page_capture_v1',
    captured_at: new Date().toISOString(),
    url,
    title,
    lang: document.documentElement ? String(document.documentElement.lang || '') : '',
    content_type: String(document.contentType || ''),
    visibility_state: String(document.visibilityState || ''),
    has_sensitive_fields: hasSensitiveFields,
    sensitive_reason: reasons,
    text: text.slice(0, maxChars),
    text_length: text.length,
    text_truncated: text.length > maxChars,
    form_values_captured: false,
    cookies_captured: false,
    local_storage_captured: false
  };
})()
"""


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


def firefox_history_db_paths(home: Path, *, max_profiles: int = 12) -> list[Path]:
    return sorted((home / ".mozilla" / "firefox").glob("*/places.sqlite"))[:max_profiles]


def read_browser_history_rows(
    db_path: Path,
    browser: str,
    *,
    tmp_root: Path,
    now_epoch: Callable[[], float] = time.time,
    copy_file: Callable[[Path, Path], Any] = shutil.copy2,
    connect_sqlite: Callable[[str], Any] = sqlite3.connect,
    lookback_hours: float = 6.0,
    limit: int = 40,
) -> tuple[list[dict[str, Any]], str | None]:
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_root / f"{hashlib.sha256(str(db_path).encode()).hexdigest()[:16]}.sqlite"
    conn: Any | None = None
    try:
        copy_file(db_path, tmp_path)
        conn = connect_sqlite(str(tmp_path))
        conn.row_factory = sqlite3.Row
        rows: list[dict[str, Any]] = []
        if browser == "firefox":
            since_us = int((now_epoch() - lookback_hours * 3600) * 1_000_000)
            query = """
                SELECT p.url AS url, p.title AS title, max(v.visit_date) AS visit_date
                FROM moz_places p JOIN moz_historyvisits v ON v.place_id = p.id
                WHERE v.visit_date >= ?
                GROUP BY p.id
                ORDER BY visit_date DESC
                LIMIT ?
            """
            for row in conn.execute(query, (since_us, limit)):
                visit_time = dt.datetime.fromtimestamp(int(row["visit_date"]) / 1_000_000, dt.timezone.utc).astimezone()
                rows.append({
                    "url": row["url"],
                    "title": row["title"],
                    "visited_at": visit_time.isoformat(timespec="seconds"),
                })
        return rows, None
    except (OSError, sqlite3.Error, ValueError) as exc:
        return [], str(exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            tmp_path.unlink()
        except OSError:
            pass


def browser_recent_history_fact(
    *,
    home: Path,
    tmp_root: Path,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    uid: int,
    gid: int,
    live_capture: dict[str, Any],
    coverage: str,
    content_recent_records: BrowserContentRecentRecordsPort,
    read_history_rows: BrowserHistoryRowsPort | None = None,
    max_profiles: int = 12,
    max_entries: int = 50,
    history_lookback_hours: float = 6.0,
    content_hours: float = 6.0,
    content_limit: int = 20,
) -> tuple[dict[str, Any], None]:
    source_id = "browser_active_tab"
    generated_at = now_iso()
    profiles = firefox_history_db_paths(home, max_profiles=max_profiles)
    history_reader = read_history_rows or (
        lambda db_path, browser: read_browser_history_rows(
            db_path,
            browser,
            tmp_root=tmp_root,
            lookback_hours=history_lookback_hours,
        )
    )
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for db_path in profiles:
        rows, error = history_reader(db_path, "firefox")
        if error:
            errors.append({"profile": str(db_path.parent), "error": error})
            continue
        for row in rows:
            key = str(row.get("url") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            title_payload = nervous_sources.text_payload(
                str(row.get("title") or ""),
                max_chars=600,
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            )
            entries.append({
                "browser": "firefox",
                "profile": db_path.parent.name,
                "visited_at": row.get("visited_at"),
                "title": title_payload["text"],
                "title_sha256": title_payload["text_sha256"],
                "url": _url_payload(
                    str(row.get("url") or ""),
                    schema_prefix=schema_prefix,
                    version=version,
                    generated_at=generated_at,
                ),
            })
            if len(entries) >= max_entries:
                break
        if len(entries) >= max_entries:
            break
    content_entries, content_errors = content_recent_records(content_hours, content_limit)
    payload = {
        "entries": entries,
        "content_entries": content_entries,
        "errors": errors,
        "content_errors": content_errors,
        "coverage": coverage,
        "live_capture": live_capture,
    }
    return {
        "name": "browser_recent_history",
        "source_id": source_id,
        "ok": True,
        "observed_at": generated_at,
        "sensitivity": "local_private_redacted",
        "coverage": coverage,
        "summary": {
            "entries": len(entries),
            "content_entries": len(content_entries),
            "live_capture_ok": bool(live_capture.get("ok")),
            "live_capture_skipped": bool(live_capture.get("skipped")),
            "live_capture_skip_reason": live_capture.get("skip_reason"),
            "live_capture_error": live_capture.get("error"),
            "profiles_seen": len(profiles),
            "errors": len(errors) + len(content_errors),
            "query_fragment_stripped": True,
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
        },
        "entries": entries,
        "content_entries": content_entries,
        "errors": errors[:12],
        "content_errors": content_errors[:12],
        "source": nervous_sources.virtual_source(source_id, payload, read_at=generated_at, uid=uid, gid=gid),
    }, None


def browser_accessibility_capture_settings(
    *,
    env_int: EnvIntPort,
    max_apps_default: int,
    max_documents_per_app_default: int,
    max_scan_nodes_default: int,
    max_text_nodes_default: int,
    max_children_default: int,
    max_text_chars_default: int,
) -> dict[str, int]:
    return {
        "max_apps": env_int("ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_APPS", max_apps_default, 1, 16),
        "max_documents_per_app": env_int(
            "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_DOCUMENTS_PER_APP",
            max_documents_per_app_default,
            1,
            64,
        ),
        "max_scan_nodes": env_int(
            "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_SCAN_MAX_NODES",
            max_scan_nodes_default,
            500,
            24_000,
        ),
        "max_text_nodes": env_int(
            "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_TEXT_MAX_NODES",
            max_text_nodes_default,
            500,
            20_000,
        ),
        "max_children": env_int(
            "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_CHILDREN",
            max_children_default,
            20,
            220,
        ),
        "max_text_chars": env_int(
            "ABYSS_MACHINE_NERVOUS_BROWSER_CONTENT_MAX_CHARS",
            max_text_chars_default,
            1_000,
            max_text_chars_default,
        ),
    }


def atspi_state_contains(node: Any, state: Any) -> bool:
    try:
        state_set = node.get_state_set()
        return bool(state_set and state_set.contains(state))
    except Exception:
        return False


def atspi_node_text(Atspi: Any, node: Any, max_chars: int = 8000) -> str:
    try:
        text_iface = Atspi.Accessible.get_text_iface(node)
        if not text_iface:
            return ""
        count = int(Atspi.Text.get_character_count(text_iface) or 0)
        if count <= 0:
            return ""
        return nervous_sources.browser_text_clean(str(Atspi.Text.get_text(text_iface, 0, min(count, max_chars)) or ""))
    except Exception:
        return ""


def atspi_collect_document_text(
    Atspi: Any,
    document: Any,
    max_chars: int,
    max_nodes: int,
    max_children: int,
    max_depth: int = 18,
) -> tuple[str, dict[str, Any]]:
    skip_roles = {
        Atspi.Role.ENTRY,
        Atspi.Role.PASSWORD_TEXT,
        Atspi.Role.COMBO_BOX,
        Atspi.Role.TOGGLE_BUTTON,
        Atspi.Role.PUSH_BUTTON,
        Atspi.Role.BUTTON,
    }
    sensitive_roles = {Atspi.Role.PASSWORD_TEXT}
    chunks: list[str] = []
    seen_chunks: set[str] = set()
    sensitive = False
    nodes_seen = 0
    truncated = False
    stack: list[tuple[Any, int]] = [(document, 0)]
    while stack and nodes_seen < max_nodes:
        node, depth = stack.pop()
        nodes_seen += 1
        try:
            role = Atspi.Accessible.get_role(node)
            role_name = str(Atspi.Accessible.get_role_name(node) or "")
            name = str(Atspi.Accessible.get_name(node) or "")
            child_count = int(Atspi.Accessible.get_child_count(node) or 0)
        except Exception:
            continue
        low = f"{role_name} {name}".lower()
        if role in sensitive_roles or (
            role in skip_roles and re.search(r"\b(password|passwd|token|secret|otp|2fa|mfa)\b", low)
        ):
            sensitive = True
        if role not in skip_roles:
            text = atspi_node_text(Atspi, node, max_chars=16000)
            if text and not re.fullmatch(r"[\ufffc\s]+", text):
                normalized = nervous_sources.browser_text_clean(text)
                if normalized and normalized not in seen_chunks:
                    chunks.append(normalized)
                    seen_chunks.add(normalized)
        if sum(len(item) + 1 for item in chunks) >= max_chars:
            truncated = True
            break
        if depth < max_depth:
            for index in range(min(child_count, max_children) - 1, -1, -1):
                try:
                    stack.append((Atspi.Accessible.get_child_at_index(node, index), depth + 1))
                except Exception:
                    continue
    text = nervous_sources.browser_text_clean("\n".join(chunks))
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    return text, {
        "nodes_seen": nodes_seen,
        "max_nodes": max_nodes,
        "sensitive_fields_seen": sensitive,
        "truncated": truncated,
        "chunks": len(chunks),
    }


def atspi_document_attributes(Atspi: Any, document: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for target_key, atspi_key in (
        ("url", "DocURL"),
        ("content_type", "MimeType"),
        ("title", "Title"),
    ):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                value = Atspi.Accessible.get_document_attribute_value(document, atspi_key)
        except Exception:
            value = None
        if value:
            values[target_key] = str(value)
    return values


def atspi_firefox_documents(
    Atspi: Any,
    app: Any,
    max_nodes: int,
    max_children: int,
    max_depth: int = 16,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    roles = {
        Atspi.Role.DOCUMENT_WEB,
        Atspi.Role.DOCUMENT_FRAME,
        Atspi.Role.DOCUMENT_TEXT,
        Atspi.Role.DOCUMENT_EMAIL,
    }
    stack: list[tuple[Any, int, str]] = [(app, 0, "0")]
    nodes_seen = 0
    while stack and nodes_seen < max_nodes:
        node, depth, path = stack.pop()
        nodes_seen += 1
        try:
            role = Atspi.Accessible.get_role(node)
            role_name = str(Atspi.Accessible.get_role_name(node) or "")
            name = str(Atspi.Accessible.get_name(node) or "")
            child_count = int(Atspi.Accessible.get_child_count(node) or 0)
        except Exception:
            continue
        if role in roles:
            documents.append({
                "node": node,
                "path": path,
                "role": role_name,
                "name": name,
                "showing": atspi_state_contains(node, Atspi.StateType.SHOWING),
                "visible": atspi_state_contains(node, Atspi.StateType.VISIBLE),
                "focused": atspi_state_contains(node, Atspi.StateType.FOCUSED),
            })
        if depth < max_depth:
            for index in range(min(child_count, max_children) - 1, -1, -1):
                try:
                    stack.append((Atspi.Accessible.get_child_at_index(node, index), depth + 1, f"{path}.{index}"))
                except Exception:
                    continue
    return documents


def atspi_document_priority(document: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        1 if document.get("focused") else 0,
        1 if document.get("showing") else 0,
        1 if document.get("visible") else 0,
        -len(str(document.get("path") or "")),
    )


def firefox_runtime_env_status(
    *,
    proc_root: Path = Path("/proc"),
    home_path: Path | None = None,
) -> dict[str, Any]:
    required = {
        "GNOME_ACCESSIBILITY": "1",
        "NO_AT_BRIDGE": "0",
    }
    optional = {
        "GTK_MODULES": "gail:atk-bridge",
    }
    processes: list[dict[str, Any]] = []
    try:
        proc_entries = list(proc_root.iterdir())
    except OSError:
        proc_entries = []
    for proc in proc_entries:
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        try:
            comm = (proc / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            comm = ""
        try:
            raw_cmdline = (proc / "cmdline").read_bytes()
        except OSError:
            raw_cmdline = b""
        cmdline = [part.decode("utf-8", errors="replace") for part in raw_cmdline.split(b"\0") if part]
        argv0 = cmdline[0] if cmdline else ""
        argv0_base = Path(argv0).name if argv0 else ""
        if comm not in {"firefox", "crashhelper"} and argv0_base not in {"firefox", "crashhelper"}:
            continue
        env: dict[str, str] = {}
        try:
            raw_env = (proc / "environ").read_bytes()
            for part in raw_env.split(b"\0"):
                if not part or b"=" not in part:
                    continue
                key, value = part.split(b"=", 1)
                key_s = key.decode("utf-8", errors="replace")
                if key_s in set(required) | set(optional):
                    env[key_s] = value.decode("utf-8", errors="replace")
        except OSError:
            pass
        missing = [key for key, value in required.items() if env.get(key) != value]
        optional_missing = [key for key, value in optional.items() if env.get(key) != value]
        processes.append({
            "pid": pid,
            "comm": comm,
            "argv0": argv0,
            "env_ready": not missing,
            "missing_required_env": missing,
            "missing_optional_env": optional_missing,
        })
    home = home_path or Path.home()
    return {
        "running": bool(processes),
        "processes": sorted(processes, key=lambda item: int(item.get("pid") or 0)),
        "env_ready": any(bool(item.get("env_ready")) for item in processes),
        "required_env": required,
        "optional_env": optional,
        "environment_d": str(home / ".config/environment.d/70-abyss-firefox-accessibility.conf"),
    }


def default_atspi_loader() -> Any:
    import gi  # type: ignore

    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi  # type: ignore

    return Atspi


def _empty_capture_summary(*, errors: int = 0) -> dict[str, Any]:
    return {
        "apps_seen": 0,
        "documents_seen": 0,
        "captures": 0,
        "errors": errors,
        "skipped_text": 0,
        "text_records": 0,
    }


def browser_accessibility_capture(
    *,
    settings: dict[str, int],
    storage_root: Path,
    latest_path: Path,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    store_page: StorePagePort,
    write_latest: bool = True,
    write_json: WriteJsonPort = default_write_json,
    atspi_loader: AtspiLoaderPort = default_atspi_loader,
    runtime_status: Callable[[], dict[str, Any]] = firefox_runtime_env_status,
    web_context_summary: WebContextSummaryPort = nervous_sources.browser_capture_web_context_summary,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_nervous_browser_content_capture_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": False,
        "source_id": "browser_active_tab",
        "capture_source": "firefox_accessibility_tree",
        "storage_root": str(storage_root),
        "captures": [],
        "errors": [],
        "requirements": {
            "toolkit_accessibility": "org.gnome.desktop.interface toolkit-accessibility=true",
            "firefox_env": "GNOME_ACCESSIBILITY=1 NO_AT_BRIDGE=0 GTK_MODULES=gail:atk-bridge",
            "remote_agent_required": False,
        },
        "capture_settings": dict(settings),
    }
    data["firefox_runtime"] = runtime_status()
    try:
        Atspi = atspi_loader()
    except Exception as exc:
        data["error"] = f"AT-SPI import failed: {exc}"
        data["summary"] = _empty_capture_summary(errors=1)
        if write_latest:
            error = write_json(latest_path, data, 0o664)
            if error:
                data.setdefault("write_errors", []).append(error)
        return data
    try:
        desktop = Atspi.get_desktop(0)
        app_count = int(Atspi.Accessible.get_child_count(desktop) or 0)
        firefox_apps: list[Any] = []
        for index in range(app_count):
            try:
                app = Atspi.Accessible.get_child_at_index(desktop, index)
                name = str(Atspi.Accessible.get_name(app) or "")
            except Exception:
                continue
            if "firefox" in name.lower():
                firefox_apps.append(app)
        documents_seen = 0
        for app_index, app in enumerate(firefox_apps[: settings["max_apps"]]):
            documents = atspi_firefox_documents(
                Atspi,
                app,
                max_nodes=settings["max_scan_nodes"],
                max_children=settings["max_children"],
            )
            documents = sorted(documents, key=atspi_document_priority, reverse=True)
            for document in documents[: settings["max_documents_per_app"]]:
                documents_seen += 1
                node = document["node"]
                attrs = atspi_document_attributes(Atspi, node)
                title = attrs.get("title") or document.get("name") or ""
                if not title or str(title).strip().lower() in {"new tab", "blank page"}:
                    continue
                text, meta = atspi_collect_document_text(
                    Atspi,
                    node,
                    max_chars=settings["max_text_chars"],
                    max_nodes=settings["max_text_nodes"],
                    max_children=settings["max_children"],
                )
                page = {
                    "schema": "abyss_browser_page_capture_v1",
                    "captured_at": now_iso(),
                    "url": attrs.get("url") or "",
                    "title": title,
                    "content_type": attrs.get("content_type") or "text/html",
                    "visibility_state": "visible" if document.get("showing") or document.get("visible") else "unknown",
                    "has_sensitive_fields": bool(meta.get("sensitive_fields_seen")),
                    "sensitive_reason": ["sensitive_form_field"] if meta.get("sensitive_fields_seen") else [],
                    "text": text,
                    "text_length": len(text),
                    "text_truncated": bool(meta.get("truncated")),
                    "form_values_captured": False,
                    "cookies_captured": False,
                    "local_storage_captured": False,
                    "atspi": {
                        "role": document.get("role"),
                        "path": document.get("path"),
                        "showing": document.get("showing"),
                        "visible": document.get("visible"),
                        "focused": document.get("focused"),
                        "nodes_seen": meta.get("nodes_seen"),
                        "chunks": meta.get("chunks"),
                    },
                }
                context = f"atspi:{app_index}:{document.get('path')}"
                stored = store_page(page, "firefox_accessibility_tree", context_id=context, write_latest=False)
                data["captures"].append({
                    "context": context,
                    "ok": stored.get("ok"),
                    "path": stored.get("path"),
                    "dedupe": stored.get("dedupe"),
                    "record": stored.get("record"),
                    "atspi": page["atspi"],
                    "write_errors": stored.get("write_errors"),
                })
        data["ok"] = bool(data["captures"]) and not any(not item.get("ok") for item in data["captures"])
        data["summary"] = {
            "apps_seen": len(firefox_apps),
            "documents_seen": documents_seen,
            "captures": len(data["captures"]),
            "errors": len(data["errors"]),
            "skipped_text": sum(1 for item in data["captures"] if _nested_get(item, ["record", "skipped_text"])),
            "text_records": sum(1 for item in data["captures"] if not _nested_get(item, ["record", "skipped_text"])),
            "web_context_quality": web_context_summary(data["captures"]),
        }
        if not firefox_apps:
            data["ok"] = True
            data["skipped"] = True
            runtime = data.get("firefox_runtime") if isinstance(data.get("firefox_runtime"), dict) else {}
            if bool(runtime.get("running")) and not bool(runtime.get("env_ready")):
                data["skip_reason"] = "firefox_running_without_atspi_environment_restart_required"
            elif bool(runtime.get("running")):
                data["skip_reason"] = "firefox_running_but_not_exposed_via_atspi"
            else:
                data["skip_reason"] = "firefox_not_running"
    except Exception as exc:
        data["error"] = str(exc)[:500]
        data["summary"] = _empty_capture_summary(errors=1)
    if write_latest:
        error = write_json(latest_path, data, 0o664)
        if error:
            data.setdefault("write_errors", []).append(error)
            data["ok"] = False
    return data


def websocket_url_parts(url: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"ws://([^/:]+)(?::(\d+))?(/.*)?", str(url or ""))
    if not match:
        raise ValueError("only ws://host[:port]/path Firefox BiDi URLs are supported")
    host = match.group(1)
    port = int(match.group(2) or 80)
    path = match.group(3) or "/session"
    return host, port, path


def websocket_read_exact(sock: Any, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise OSError("websocket closed")
        data += chunk
    return data


def websocket_send_frame(
    sock: Any,
    opcode: int,
    payload: bytes,
    *,
    mask_bytes: bytes | None = None,
) -> None:
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.extend([0x80 | 126])
        header.extend(struct.pack("!H", length))
    else:
        header.extend([0x80 | 127])
        header.extend(struct.pack("!Q", length))
    mask = mask_bytes if mask_bytes is not None else os.urandom(4)
    if len(mask) != 4:
        raise ValueError("websocket mask must be exactly 4 bytes")
    header.extend(mask)
    sock.sendall(bytes(header) + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload)))


def websocket_send_json(sock: Any, payload: dict[str, Any], *, mask_bytes: bytes | None = None) -> None:
    websocket_send_frame(
        sock,
        0x1,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        mask_bytes=mask_bytes,
    )


def websocket_recv_json(sock: Any) -> dict[str, Any]:
    parts: list[bytes] = []
    while True:
        first, second = websocket_read_exact(sock, 2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", websocket_read_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", websocket_read_exact(sock, 8))[0]
        mask = websocket_read_exact(sock, 4) if masked else b""
        payload = websocket_read_exact(sock, length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        if opcode == 0x8:
            raise OSError("websocket close frame received")
        if opcode == 0x9:
            websocket_send_frame(sock, 0xA, payload)
            continue
        if opcode in {0x1, 0x0}:
            parts.append(payload)
        if fin:
            return json.loads(b"".join(parts).decode("utf-8", errors="replace"))


def websocket_connect(url: str, timeout: float = 1.5) -> socket.socket:
    host, port, path = websocket_url_parts(url)
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode("ascii"))
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
        if len(response) > 16384:
            raise OSError("oversized websocket handshake")
    status_line = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    if " 101 " not in status_line:
        body = response.split(b"\r\n\r\n", 1)[-1].decode("utf-8", errors="replace")
        raise OSError(f"websocket handshake failed: {status_line} {body[:200]}")
    return sock


def bidi_call(sock: Any, request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    websocket_send_json(sock, {"id": request_id, "method": method, "params": params})
    while True:
        message = websocket_recv_json(sock)
        if message.get("id") == request_id:
            if message.get("type") == "error":
                raise OSError(f"{method} failed: {message.get('error')} {message.get('message')}")
            return message


def bidi_decode_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    value_type = value.get("type")
    if value_type in {"string", "number", "boolean", "bigint"}:
        return value.get("value")
    if value_type in {"null", "undefined"}:
        return None
    if value_type == "array":
        return [bidi_decode_value(item) for item in value.get("value") or []]
    if value_type == "object":
        decoded: dict[str, Any] = {}
        for pair in value.get("value") or []:
            if not isinstance(pair, list) or len(pair) != 2:
                continue
            key = pair[0]
            if isinstance(key, dict):
                key = bidi_decode_value(key)
            decoded[str(key)] = bidi_decode_value(pair[1])
        return decoded
    return value.get("value")


def bidi_contexts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        contexts.append(item)
        children = item.get("children")
        if isinstance(children, list):
            contexts.extend(bidi_contexts([child for child in children if isinstance(child, dict)]))
    return contexts


def browser_bidi_capture(
    *,
    bidi_url: str,
    storage_root: Path,
    latest_path: Path,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    store_page: StorePagePort,
    write_latest: bool = True,
    write_json: WriteJsonPort = default_write_json,
    connect_websocket: WebSocketConnectPort = websocket_connect,
    call_bidi: BidiCallPort = bidi_call,
    web_context_summary: WebContextSummaryPort = nervous_sources.browser_capture_web_context_summary,
    capture_script: str = BROWSER_CONTENT_CAPTURE_SCRIPT,
    max_contexts: int = 24,
    timeout: float = 1.5,
) -> dict[str, Any]:
    generated_at = now_iso()
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_nervous_browser_content_capture_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "bidi_url": bidi_url,
        "source_id": "browser_active_tab",
        "capture_source": "firefox_webdriver_bidi",
        "storage_root": str(storage_root),
        "captures": [],
        "errors": [],
    }
    sock: Any | None = None
    try:
        sock = connect_websocket(bidi_url, timeout=timeout)
        request_id = 1
        session = call_bidi(sock, request_id, "session.new", {"capabilities": {}})
        request_id += 1
        data["session"] = {
            "browserName": _nested_get(session, ["result", "capabilities", "browserName"]),
            "browserVersion": _nested_get(session, ["result", "capabilities", "browserVersion"]),
            "platformName": _nested_get(session, ["result", "capabilities", "platformName"]),
        }
        tree = call_bidi(sock, request_id, "browsingContext.getTree", {})
        request_id += 1
        contexts = bidi_contexts(_nested_get(tree, ["result", "contexts"]) or [])
        top_contexts = [item for item in contexts if not item.get("parent")]
        data["contexts_seen"] = len(top_contexts)
        for context in top_contexts[:max_contexts]:
            context_id = str(context.get("context") or "")
            context_url = str(context.get("url") or "")
            if not context_id or context_url.startswith(("about:", "chrome:", "moz-extension:", "resource:")):
                continue
            try:
                result = call_bidi(sock, request_id, "script.evaluate", {
                    "expression": capture_script,
                    "target": {"context": context_id},
                    "awaitPromise": True,
                    "resultOwnership": "none",
                    "serializationOptions": {"maxObjectDepth": 4, "maxDomDepth": 0, "includeShadowTree": "none"},
                })
                request_id += 1
                script_result = result.get("result") if isinstance(result.get("result"), dict) else {}
                if script_result.get("type") != "success":
                    data["errors"].append({
                        "context": context_id,
                        "url": _url_payload(context_url, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
                        "error": "script evaluation did not return success",
                    })
                    continue
                page = bidi_decode_value(script_result.get("result"))
                if not isinstance(page, dict):
                    data["errors"].append({
                        "context": context_id,
                        "url": _url_payload(context_url, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
                        "error": "script result was not an object",
                    })
                    continue
                stored = store_page(page, "firefox_webdriver_bidi", context_id=context_id, write_latest=False)
                data["captures"].append({
                    "context": context_id,
                    "ok": stored.get("ok"),
                    "path": stored.get("path"),
                    "dedupe": stored.get("dedupe"),
                    "record": stored.get("record"),
                    "write_errors": stored.get("write_errors"),
                })
            except Exception as exc:
                request_id += 1
                data["errors"].append({
                    "context": context_id,
                    "url": _url_payload(context_url, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
                    "error": str(exc)[:400],
                })
        try:
            call_bidi(sock, request_id, "session.end", {})
        except Exception:
            pass
        data["ok"] = bool(data["captures"]) and not any(not item.get("ok") for item in data["captures"])
        data["summary"] = {
            "contexts_seen": data.get("contexts_seen", 0),
            "captures": len(data["captures"]),
            "errors": len(data["errors"]),
            "skipped_text": sum(1 for item in data["captures"] if _nested_get(item, ["record", "skipped_text"])),
            "text_records": sum(1 for item in data["captures"] if not _nested_get(item, ["record", "skipped_text"])),
            "web_context_quality": web_context_summary(data["captures"]),
        }
    except Exception as exc:
        data["error"] = str(exc)[:500]
        data["summary"] = {
            "contexts_seen": 0,
            "captures": 0,
            "errors": 1,
            "skipped_text": 0,
            "text_records": 0,
        }
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
    if write_latest:
        error = write_json(latest_path, data, 0o664)
        if error:
            data.setdefault("write_errors", []).append(error)
            data["ok"] = False
    return data


def _url_payload(url: str, *, schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return nervous_sources.url_payload(
        url,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def _nested_get(data: Any, keys: list[str]) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
