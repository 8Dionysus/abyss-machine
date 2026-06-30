from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_browser_content_adapters as adapters


def parse_time(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    return dt.datetime.fromisoformat(str(value))


def test_browser_content_jsonl_path_uses_local_day_projection(tmp_path: Path) -> None:
    path = adapters.browser_content_jsonl_path(
        tmp_path,
        "2026-06-30T12:40:00+00:00",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )

    assert path == tmp_path / "2026" / "06" / "2026-06-30.jsonl"


def test_browser_content_store_appends_record_and_writes_latest(tmp_path: Path) -> None:
    now_values = iter([
        "2026-06-30T12:40:00+00:00",
        "2026-06-30T12:40:01+00:00",
        "2026-06-30T12:40:02+00:00",
        "2026-06-30T12:40:03+00:00",
    ])
    appends: list[tuple[Path, dict[str, Any], int]] = []
    writes: list[tuple[Path, dict[str, Any], int]] = []

    def append_jsonl(path: Path, data: dict[str, Any], mode: int):
        appends.append((path, data, mode))
        return None

    def write_json(path: Path, data: dict[str, Any], mode: int):
        writes.append((path, data, mode))
        return None

    data = adapters.browser_content_store(
        {"url": "https://example.test/docs", "title": "Docs", "text": "Useful browser text"},
        "fixture_atspi",
        content_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        context_id="ctx",
        schema_prefix="abyss_machine",
        version="test",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 6, 30, 12, 40, tzinfo=dt.timezone.utc),
        now_iso=lambda: next(now_values),
        max_text_chars=200,
        uid=1000,
        gid=1000,
        append_jsonl=append_jsonl,
        write_json=write_json,
    )

    assert data["ok"] is True
    assert data["schema"] == "abyss_machine_nervous_browser_content_ingest_v1"
    assert data["dedupe"] == {"duplicate": False}
    assert data["record"]["title"] == "Docs"
    assert data["record"]["text_length"] == len("Useful browser text")
    assert appends[0][0] == tmp_path / "browser-content" / "2026" / "06" / "2026-06-30.jsonl"
    assert appends[0][2] == 0o664
    assert writes[0][0] == tmp_path / "latest.json"
    assert writes[0][1] is data
    assert writes[0][2] == 0o664


def test_browser_content_store_suppresses_recent_duplicate_append(tmp_path: Path) -> None:
    root = tmp_path / "browser-content"
    path = root / "2026" / "06" / "2026-06-30.jsonl"
    path.parent.mkdir(parents=True)
    page = {
        "url": "https://example.test/docs",
        "title": "Docs",
        "text": "Duplicate browser text",
        "captured_at": "2026-06-30T12:41:00+00:00",
    }
    previous = adapters.browser_content_record_from_page(
        page,
        "fixture_atspi",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T12:41:00+00:00",
        max_text_chars=200,
        uid=1000,
        gid=1000,
    )
    path.write_text(json.dumps(previous) + "\n", encoding="utf-8")

    data = adapters.browser_content_store(
        page,
        "fixture_atspi",
        content_root=root,
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 6, 30, 12, 41, tzinfo=dt.timezone.utc),
        now_iso=lambda: "2026-06-30T12:41:01+00:00",
        max_text_chars=200,
        uid=1000,
        gid=1000,
        append_jsonl=lambda *_args: (_ for _ in ()).throw(AssertionError("duplicate should not append")),
        write_json=lambda *_args: None,
    )

    assert data["ok"] is True
    assert data["dedupe"]["duplicate"] is True
    assert data["dedupe"]["matched_recent_line_from_end"] == 1


def test_browser_content_store_reports_latest_write_error(tmp_path: Path) -> None:
    data = adapters.browser_content_store(
        {"url": "https://example.test/docs", "title": "Docs", "text": "Text"},
        "fixture_atspi",
        content_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        parse_time=parse_time,
        now=lambda: dt.datetime(2026, 6, 30, 12, 42, tzinfo=dt.timezone.utc),
        now_iso=lambda: "2026-06-30T12:42:00+00:00",
        max_text_chars=200,
        uid=1000,
        gid=1000,
        append_jsonl=lambda *_args: None,
        write_json=lambda path, _data, _mode: {"path": str(path), "error": "readonly"},
    )

    assert data["ok"] is False
    assert data["write_errors"] == [{"path": str(tmp_path / "latest.json"), "error": "readonly"}]


def test_cli_browser_content_store_binds_adapter_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_store(*args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return {"ok": True, "capture_source": args[1]}

    monkeypatch.setattr(cli.nervous_browser_content_adapters, "browser_content_store", fake_store)

    data = cli.nervous_browser_content_store({"title": "Docs"}, "fixture", context_id="ctx-cli", write_latest=False)

    assert data == {"ok": True, "capture_source": "fixture"}
    assert captured["content_root"] == cli.NERVOUS_BROWSER_CONTENT_ROOT
    assert captured["latest_path"] == cli.NERVOUS_BROWSER_CONTENT_LATEST_PATH
    assert captured["context_id"] == "ctx-cli"
    assert captured["write_latest"] is False
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["parse_time"] is cli.parse_time
    assert captured["now_iso"] is cli.now_iso
    assert captured["append_jsonl"] is cli.safe_append_jsonl
    assert captured["write_json"] is cli.safe_atomic_write_json


def test_firefox_history_db_paths_finds_profile_places(tmp_path: Path) -> None:
    first = tmp_path / ".mozilla" / "firefox" / "one.default" / "places.sqlite"
    second = tmp_path / ".mozilla" / "firefox" / "two.default" / "places.sqlite"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"sqlite")
    second.write_bytes(b"sqlite")

    assert adapters.firefox_history_db_paths(tmp_path) == [first, second]


def test_read_browser_history_rows_uses_temp_copy_recent_cutoff_and_cleanup(tmp_path: Path) -> None:
    db_path = tmp_path / "profile" / "places.sqlite"
    tmp_root = tmp_path / "tmp"
    db_path.parent.mkdir()
    now = dt.datetime(2026, 6, 30, 12, 0, tzinfo=dt.timezone.utc)
    recent = dt.datetime(2026, 6, 30, 11, 30, tzinfo=dt.timezone.utc)
    old = dt.datetime(2026, 6, 30, 1, 30, tzinfo=dt.timezone.utc)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
        conn.execute("CREATE TABLE moz_historyvisits (place_id INTEGER, visit_date INTEGER)")
        conn.execute("INSERT INTO moz_places (id, url, title) VALUES (1, 'https://example.test/docs?token=secret#frag', 'Docs')")
        conn.execute("INSERT INTO moz_places (id, url, title) VALUES (2, 'https://example.test/old', 'Old')")
        conn.execute("INSERT INTO moz_historyvisits (place_id, visit_date) VALUES (1, ?)", (int(recent.timestamp() * 1_000_000),))
        conn.execute("INSERT INTO moz_historyvisits (place_id, visit_date) VALUES (2, ?)", (int(old.timestamp() * 1_000_000),))

    rows, error = adapters.read_browser_history_rows(
        db_path,
        "firefox",
        tmp_root=tmp_root,
        now_epoch=now.timestamp,
    )

    assert error is None
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.test/docs?token=secret#frag"
    assert rows[0]["title"] == "Docs"
    assert int(dt.datetime.fromisoformat(rows[0]["visited_at"]).timestamp()) == int(recent.timestamp())
    assert not list(tmp_root.glob("*.sqlite"))


def test_browser_recent_history_fact_assembles_redacted_entries_and_content_callback(tmp_path: Path) -> None:
    first = tmp_path / ".mozilla" / "firefox" / "one.default" / "places.sqlite"
    second = tmp_path / ".mozilla" / "firefox" / "two.default" / "places.sqlite"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"")
    second.write_bytes(b"")
    calls: list[tuple[Path, str]] = []

    def read_rows(path: Path, browser: str) -> tuple[list[dict[str, Any]], str | None]:
        calls.append((path, browser))
        if path == first:
            return [
                {
                    "url": "https://example.test/docs?token=secret#frag",
                    "title": "Docs",
                    "visited_at": "2026-06-30T11:30:00+00:00",
                },
                {
                    "url": "https://example.test/docs?token=secret#frag",
                    "title": "Duplicate",
                    "visited_at": "2026-06-30T11:31:00+00:00",
                },
            ], None
        return [], "locked"

    data, skip = adapters.browser_recent_history_fact(
        home=tmp_path,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T12:00:00+00:00",
        uid=1000,
        gid=1000,
        live_capture={"ok": True, "skipped": False},
        coverage="recent_history_plus_fixture_capture",
        content_recent_records=lambda hours, limit: ([{"captured_at": "2026-06-30T11:59:00+00:00"}], []),
        read_history_rows=read_rows,
    )

    assert skip is None
    assert data["ok"] is True
    assert data["summary"]["entries"] == 1
    assert data["summary"]["content_entries"] == 1
    assert data["summary"]["profiles_seen"] == 2
    assert data["summary"]["errors"] == 1
    assert data["entries"][0]["profile"] == "one.default"
    assert data["entries"][0]["title"] == "Docs"
    assert data["entries"][0]["url"]["url"] == "https://example.test/docs"
    assert data["entries"][0]["url"]["query_present"] is True
    assert data["entries"][0]["url"]["fragment_present"] is True
    assert data["errors"][0]["profile"].endswith("two.default")
    assert data["source"]["virtual"] is True
    assert calls == [(first, "firefox"), (second, "firefox")]


def test_cli_browser_recent_history_fact_binds_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_fact(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "name": "browser_recent_history"}, None

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli, "nervous_browser_live_content_capture", lambda write_latest: {"ok": True, "write_latest": write_latest})
    monkeypatch.setattr(cli.nervous_browser_content_adapters, "browser_recent_history_fact", fake_fact)

    data, skip = cli.nervous_browser_recent_history_fact(
        {"safe_now": {"browser_active_tab": {"enabled": True, "allowed": True}}},
        trigger="manual",
    )

    assert skip is None
    assert data == {"ok": True, "name": "browser_recent_history"}
    assert captured["home"] == tmp_path
    assert captured["tmp_root"] == cli.NERVOUS_BROWSER_TMP_ROOT
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["now_iso"] is cli.now_iso
    assert captured["live_capture"] == {"ok": True, "write_latest": True}
    assert captured["coverage"] == "recent_history_plus_live_browser_content_capture"
    assert captured["read_history_rows"] is cli.nervous_read_browser_history_rows
    assert callable(captured["content_recent_records"])


class FakeStateSet:
    def __init__(self, states: set[str]):
        self.states = states

    def contains(self, state: str) -> bool:
        return state in self.states


class FakeNode:
    def __init__(
        self,
        *,
        role: int,
        role_name: str,
        name: str,
        text: str = "",
        attrs: dict[str, str] | None = None,
        states: set[str] | None = None,
        children: list["FakeNode"] | None = None,
    ) -> None:
        self.role = role
        self.role_name = role_name
        self.name = name
        self.text = text
        self.attrs = attrs or {}
        self.states = states or set()
        self.children = children or []

    def get_state_set(self) -> FakeStateSet:
        return FakeStateSet(self.states)


class FakeRole:
    ENTRY = 1
    PASSWORD_TEXT = 2
    COMBO_BOX = 3
    TOGGLE_BUTTON = 4
    PUSH_BUTTON = 5
    BUTTON = 6
    DOCUMENT_WEB = 7
    DOCUMENT_FRAME = 8
    DOCUMENT_TEXT = 9
    DOCUMENT_EMAIL = 10
    APPLICATION = 11


class FakeStateType:
    SHOWING = "showing"
    VISIBLE = "visible"
    FOCUSED = "focused"


class FakeAccessible:
    @staticmethod
    def get_text_iface(node: FakeNode) -> FakeNode | None:
        return node if node.text else None

    @staticmethod
    def get_role(node: FakeNode) -> int:
        return node.role

    @staticmethod
    def get_role_name(node: FakeNode) -> str:
        return node.role_name

    @staticmethod
    def get_name(node: FakeNode) -> str:
        return node.name

    @staticmethod
    def get_child_count(node: FakeNode) -> int:
        return len(node.children)

    @staticmethod
    def get_child_at_index(node: FakeNode, index: int) -> FakeNode:
        return node.children[index]

    @staticmethod
    def get_document_attribute_value(node: FakeNode, key: str) -> str | None:
        return node.attrs.get(key)


class FakeText:
    @staticmethod
    def get_character_count(node: FakeNode) -> int:
        return len(node.text)

    @staticmethod
    def get_text(node: FakeNode, start: int, end: int) -> str:
        return node.text[start:end]


class FakeAtspi:
    Role = FakeRole
    StateType = FakeStateType
    Accessible = FakeAccessible
    Text = FakeText

    def __init__(self, desktop: FakeNode):
        self.desktop = desktop

    def get_desktop(self, _index: int) -> FakeNode:
        return self.desktop


def test_atspi_collect_document_text_skips_sensitive_entry_text() -> None:
    document = FakeNode(
        role=FakeRole.DOCUMENT_WEB,
        role_name="document web",
        name="Docs",
        text="Visible documentation text",
        children=[
            FakeNode(
                role=FakeRole.PASSWORD_TEXT,
                role_name="password text",
                name="Password",
                text="super-secret",
            )
        ],
    )

    text, meta = adapters.atspi_collect_document_text(
        FakeAtspi,
        document,
        max_chars=400,
        max_nodes=20,
        max_children=20,
    )

    assert text == "Visible documentation text"
    assert "super-secret" not in text
    assert meta["sensitive_fields_seen"] is True
    assert meta["chunks"] == 1


def test_firefox_runtime_env_status_reads_fake_proc_root(tmp_path: Path) -> None:
    proc = tmp_path / "1234"
    proc.mkdir()
    (proc / "comm").write_text("firefox\n", encoding="utf-8")
    (proc / "cmdline").write_bytes(b"/usr/bin/firefox\0")
    (proc / "environ").write_bytes(b"GNOME_ACCESSIBILITY=1\0NO_AT_BRIDGE=0\0GTK_MODULES=gail:atk-bridge\0")

    status = adapters.firefox_runtime_env_status(proc_root=tmp_path, home_path=tmp_path / "home")

    assert status["running"] is True
    assert status["env_ready"] is True
    assert status["processes"][0]["pid"] == 1234
    assert status["processes"][0]["missing_required_env"] == []
    assert status["environment_d"].endswith(".config/environment.d/70-abyss-firefox-accessibility.conf")


def test_browser_accessibility_capture_uses_fake_atspi_and_store(tmp_path: Path) -> None:
    document = FakeNode(
        role=FakeRole.DOCUMENT_WEB,
        role_name="document web",
        name="Project Docs",
        text="Project notes from accessible browser document",
        attrs={"DocURL": "https://example.test/project", "MimeType": "text/html", "Title": "Project Docs"},
        states={"showing", "visible", "focused"},
    )
    firefox = FakeNode(
        role=FakeRole.APPLICATION,
        role_name="application",
        name="Firefox",
        children=[document],
    )
    terminal = FakeNode(role=FakeRole.APPLICATION, role_name="application", name="Terminal")
    desktop = FakeNode(
        role=FakeRole.APPLICATION,
        role_name="desktop",
        name="desktop",
        children=[terminal, firefox],
    )
    stored_pages: list[tuple[dict[str, Any], str, str | None, bool]] = []

    def store_page(page: dict[str, Any], capture_source: str, *, context_id: str | None, write_latest: bool) -> dict[str, Any]:
        stored_pages.append((page, capture_source, context_id, write_latest))
        return {
            "ok": True,
            "path": str(tmp_path / "browser.jsonl"),
            "dedupe": {"duplicate": False},
            "record": {
                "title": page["title"],
                "url": page["url"],
                "skipped_text": False,
                "web_context_quality": {"class": "project"},
            },
        }

    data = adapters.browser_accessibility_capture(
        settings={
            "max_apps": 4,
            "max_documents_per_app": 4,
            "max_scan_nodes": 40,
            "max_text_nodes": 40,
            "max_children": 20,
            "max_text_chars": 1000,
        },
        storage_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T13:00:00+00:00",
        store_page=store_page,
        write_latest=False,
        atspi_loader=lambda: FakeAtspi(desktop),
        runtime_status=lambda: {"running": True, "env_ready": True},
        web_context_summary=lambda captures: {"captures": len(captures), "class": "project"},
    )

    assert data["ok"] is True
    assert data["summary"]["apps_seen"] == 1
    assert data["summary"]["documents_seen"] == 1
    assert data["summary"]["captures"] == 1
    assert data["summary"]["text_records"] == 1
    assert data["summary"]["web_context_quality"] == {"captures": 1, "class": "project"}
    assert stored_pages[0][1] == "firefox_accessibility_tree"
    assert stored_pages[0][2] == "atspi:0:0.0"
    assert stored_pages[0][3] is False
    assert stored_pages[0][0]["text"] == "Project notes from accessible browser document"
    assert stored_pages[0][0]["atspi"]["focused"] is True


def test_browser_accessibility_capture_reports_import_failure_and_latest_write(tmp_path: Path) -> None:
    writes: list[tuple[Path, dict[str, Any], int]] = []

    def fail_loader() -> Any:
        raise RuntimeError("missing gi")

    def write_json(path: Path, data: dict[str, Any], mode: int):
        writes.append((path, data, mode))
        return None

    data = adapters.browser_accessibility_capture(
        settings={
            "max_apps": 1,
            "max_documents_per_app": 1,
            "max_scan_nodes": 500,
            "max_text_nodes": 500,
            "max_children": 20,
            "max_text_chars": 1000,
        },
        storage_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T13:01:00+00:00",
        store_page=lambda *_args, **_kwargs: {"ok": True},
        write_latest=True,
        write_json=write_json,
        atspi_loader=fail_loader,
        runtime_status=lambda: {"running": False, "env_ready": False},
    )

    assert data["ok"] is False
    assert data["error"] == "AT-SPI import failed: missing gi"
    assert data["summary"]["errors"] == 1
    assert writes == [(tmp_path / "latest.json", data, 0o664)]


def test_browser_accessibility_capture_skips_when_firefox_is_absent(tmp_path: Path) -> None:
    desktop = FakeNode(
        role=FakeRole.APPLICATION,
        role_name="desktop",
        name="desktop",
        children=[FakeNode(role=FakeRole.APPLICATION, role_name="application", name="Terminal")],
    )

    data = adapters.browser_accessibility_capture(
        settings={
            "max_apps": 1,
            "max_documents_per_app": 1,
            "max_scan_nodes": 500,
            "max_text_nodes": 500,
            "max_children": 20,
            "max_text_chars": 1000,
        },
        storage_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T13:02:00+00:00",
        store_page=lambda *_args, **_kwargs: {"ok": True},
        write_latest=False,
        atspi_loader=lambda: FakeAtspi(desktop),
        runtime_status=lambda: {"running": False, "env_ready": False},
    )

    assert data["ok"] is True
    assert data["skipped"] is True
    assert data["skip_reason"] == "firefox_not_running"
    assert data["summary"]["apps_seen"] == 0


def test_cli_browser_accessibility_capture_binds_adapter_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_capture(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "capture_source": "firefox_accessibility_tree"}

    monkeypatch.setattr(cli.nervous_browser_content_adapters, "browser_accessibility_capture", fake_capture)
    monkeypatch.setattr(cli, "nervous_browser_accessibility_capture_settings", lambda: {"max_apps": 1})

    data = cli.nervous_browser_accessibility_capture(write_latest=False)

    assert data == {"ok": True, "capture_source": "firefox_accessibility_tree"}
    assert captured["settings"] == {"max_apps": 1}
    assert captured["storage_root"] == cli.NERVOUS_BROWSER_CONTENT_ROOT
    assert captured["latest_path"] == cli.NERVOUS_BROWSER_CONTENT_LATEST_PATH
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["now_iso"] is cli.now_iso
    assert captured["store_page"] is cli.nervous_browser_content_store
    assert captured["write_latest"] is False
    assert captured["write_json"] is cli.safe_atomic_write_json
    assert captured["runtime_status"] is cli.nervous_firefox_runtime_env_status
    assert captured["web_context_summary"] is cli.nervous_browser_capture_web_context_summary


class FakeSocket:
    def __init__(self, recv_payload: bytes = b"") -> None:
        self.recv_payload = bytearray(recv_payload)
        self.sent = bytearray()
        self.closed = False

    def recv(self, size: int) -> bytes:
        if not self.recv_payload:
            return b""
        chunk = self.recv_payload[:size]
        del self.recv_payload[:size]
        return bytes(chunk)

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def close(self) -> None:
        self.closed = True


def test_websocket_helpers_frame_json_with_deterministic_mask() -> None:
    sock = FakeSocket()

    adapters.websocket_send_json(sock, {"id": 1, "method": "ping"}, mask_bytes=b"\x01\x02\x03\x04")

    raw = bytes(sock.sent)
    assert raw[:2] == b"\x81\x98"
    assert raw[2:6] == b"\x01\x02\x03\x04"
    unmasked = bytes(byte ^ raw[2 + index % 4] for index, byte in enumerate(raw[6:]))
    assert json.loads(unmasked.decode("utf-8")) == {"id": 1, "method": "ping"}


def test_websocket_recv_json_decodes_unmasked_server_frame() -> None:
    payload = json.dumps({"id": 2, "result": {"ok": True}}, separators=(",", ":")).encode("utf-8")
    sock = FakeSocket(b"\x81" + bytes([len(payload)]) + payload)

    assert adapters.websocket_recv_json(sock) == {"id": 2, "result": {"ok": True}}


def test_bidi_decode_value_handles_nested_remote_values() -> None:
    value = {
        "type": "object",
        "value": [
            ["title", {"type": "string", "value": "Docs"}],
            ["count", {"type": "number", "value": 3}],
            ["items", {"type": "array", "value": [{"type": "string", "value": "a"}]}],
            [{"type": "string", "value": "dynamic"}, {"type": "boolean", "value": True}],
        ],
    }

    assert adapters.bidi_decode_value(value) == {
        "title": "Docs",
        "count": 3,
        "items": ["a"],
        "dynamic": True,
    }


def test_browser_bidi_capture_uses_fake_bidi_and_store(tmp_path: Path) -> None:
    sock = FakeSocket()
    calls: list[tuple[int, str, dict[str, Any]]] = []
    stored_pages: list[tuple[dict[str, Any], str, str | None, bool]] = []

    def call_bidi(_sock: FakeSocket, request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((request_id, method, params))
        if method == "session.new":
            return {
                "result": {
                    "capabilities": {
                        "browserName": "firefox",
                        "browserVersion": "130",
                        "platformName": "linux",
                    }
                }
            }
        if method == "browsingContext.getTree":
            return {
                "result": {
                    "contexts": [
                        {"context": "skip", "url": "about:blank"},
                        {"context": "ctx-1", "url": "https://example.test/docs"},
                        {"context": "child", "parent": "ctx-1", "url": "https://example.test/frame"},
                    ]
                }
            }
        if method == "script.evaluate":
            assert params["target"] == {"context": "ctx-1"}
            assert params["expression"] == "return-page"
            return {
                "result": {
                    "type": "success",
                    "result": {
                        "type": "object",
                        "value": [
                            ["url", {"type": "string", "value": "https://example.test/docs"}],
                            ["title", {"type": "string", "value": "Docs"}],
                            ["text", {"type": "string", "value": "Useful page text"}],
                            ["captured_at", {"type": "string", "value": "2026-06-30T14:00:00+00:00"}],
                            ["has_sensitive_fields", {"type": "boolean", "value": False}],
                        ],
                    },
                }
            }
        if method == "session.end":
            return {"result": {}}
        raise AssertionError(method)

    def store_page(page: dict[str, Any], capture_source: str, *, context_id: str | None, write_latest: bool) -> dict[str, Any]:
        stored_pages.append((page, capture_source, context_id, write_latest))
        return {
            "ok": True,
            "path": str(tmp_path / "browser-content.jsonl"),
            "dedupe": {"duplicate": False},
            "record": {
                "title": page.get("title"),
                "url": {"url": page.get("url"), "raw_omitted": True},
                "skipped_text": False,
                "web_context_quality": {"class": "docs"},
            },
        }

    data = adapters.browser_bidi_capture(
        bidi_url="ws://127.0.0.1:9222/session",
        storage_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T14:00:00+00:00",
        store_page=store_page,
        write_latest=False,
        connect_websocket=lambda url, timeout: sock,
        call_bidi=call_bidi,
        web_context_summary=lambda captures: {"captures": len(captures), "class": "docs"},
        capture_script="return-page",
    )

    assert data["ok"] is True
    assert data["session"] == {"browserName": "firefox", "browserVersion": "130", "platformName": "linux"}
    assert data["contexts_seen"] == 2
    assert data["summary"]["captures"] == 1
    assert data["summary"]["errors"] == 0
    assert data["summary"]["web_context_quality"] == {"captures": 1, "class": "docs"}
    assert stored_pages == [(
        {
            "url": "https://example.test/docs",
            "title": "Docs",
            "text": "Useful page text",
            "captured_at": "2026-06-30T14:00:00+00:00",
            "has_sensitive_fields": False,
        },
        "firefox_webdriver_bidi",
        "ctx-1",
        False,
    )]
    assert calls[-1][1] == "session.end"
    assert sock.closed is True


def test_browser_bidi_capture_redacts_script_errors_and_writes_latest(tmp_path: Path) -> None:
    writes: list[tuple[Path, dict[str, Any], int]] = []

    def call_bidi(_sock: FakeSocket, _request_id: int, method: str, _params: dict[str, Any]) -> dict[str, Any]:
        if method == "session.new":
            return {"result": {"capabilities": {}}}
        if method == "browsingContext.getTree":
            return {"result": {"contexts": [{"context": "ctx", "url": "https://example.test/login?token=secret#frag"}]}}
        if method == "script.evaluate":
            return {"result": {"type": "exception"}}
        if method == "session.end":
            return {"result": {}}
        raise AssertionError(method)

    def write_json(path: Path, data: dict[str, Any], mode: int):
        writes.append((path, data, mode))
        return None

    data = adapters.browser_bidi_capture(
        bidi_url="ws://127.0.0.1:9222/session",
        storage_root=tmp_path / "browser-content",
        latest_path=tmp_path / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-30T14:01:00+00:00",
        store_page=lambda *_args, **_kwargs: {"ok": True},
        write_latest=True,
        write_json=write_json,
        connect_websocket=lambda _url, timeout: FakeSocket(),
        call_bidi=call_bidi,
    )

    assert data["ok"] is False
    assert data["summary"]["contexts_seen"] == 1
    assert data["summary"]["errors"] == 1
    assert data["errors"][0]["url"]["url"] == "https://example.test/login"
    assert data["errors"][0]["url"]["query_present"] is True
    assert data["errors"][0]["url"]["fragment_present"] is True
    assert writes == [(tmp_path / "latest.json", data, 0o664)]


def test_cli_browser_bidi_capture_binds_adapter_ports(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_capture(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "capture_source": "firefox_webdriver_bidi"}

    monkeypatch.setattr(cli.nervous_browser_content_adapters, "browser_bidi_capture", fake_capture)

    data = cli.nervous_browser_content_capture(bidi_url="ws://example.test:9222/session", write_latest=False)

    assert data == {"ok": True, "capture_source": "firefox_webdriver_bidi"}
    assert captured["bidi_url"] == "ws://example.test:9222/session"
    assert captured["storage_root"] == cli.NERVOUS_BROWSER_CONTENT_ROOT
    assert captured["latest_path"] == cli.NERVOUS_BROWSER_CONTENT_LATEST_PATH
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["now_iso"] is cli.now_iso
    assert captured["store_page"] is cli.nervous_browser_content_store
    assert captured["write_latest"] is False
    assert captured["write_json"] is cli.safe_atomic_write_json
    assert captured["connect_websocket"] is cli.nervous_ws_connect
    assert captured["call_bidi"] is cli.nervous_bidi_call
    assert captured["web_context_summary"] is cli.nervous_browser_capture_web_context_summary
    assert captured["capture_script"] == cli.NERVOUS_BROWSER_CAPTURE_SCRIPT
