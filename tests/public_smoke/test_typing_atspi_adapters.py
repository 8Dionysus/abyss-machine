from __future__ import annotations

from abyss_machine import typing_atspi_adapters


class FakePyAtspi:
    STATE_FOCUSED = "focused"
    STATE_EDITABLE = "editable"
    STATE_SHOWING = "showing"
    STATE_VISIBLE = "visible"
    STATE_SENSITIVE = "sensitive"
    STATE_ENABLED = "enabled"
    STATE_SINGLE_LINE = "single_line"
    STATE_MULTI_LINE = "multi_line"


class FakeState:
    def __init__(self, *flags: str) -> None:
        self.flags = set(flags)

    def contains(self, flag: str) -> bool:
        return flag in self.flags


class FakeText:
    def __init__(self, text: str, caret: int = 0) -> None:
        self.text = text
        self.characterCount = len(text)
        self.caretOffset = caret

    def getText(self, start: int, end: int) -> str:
        return self.text[start:end]


class FakeDocument:
    def __init__(self, attributes: dict[str, str]) -> None:
        self.attributes = dict(attributes)

    def getAttributeValue(self, key: str) -> str:
        return self.attributes.get(key, "")

    def getAttributes(self) -> list[str]:
        return [f"{key}:{value}" for key, value in self.attributes.items()]


class FakeApp:
    def __init__(self, name: str = "firefox", pid: int = 1234) -> None:
        self.name = name
        self.pid = pid
        self.toolkitName = "gtk"
        self.toolkitVersion = "4"
        self.parent = None

    def getRoleName(self) -> str:
        return "application"

    def getApplication(self) -> "FakeApp":
        return self

    def get_process_id(self) -> int:
        return self.pid


class FakeAccessible:
    def __init__(
        self,
        *,
        role: str,
        name: str,
        app: FakeApp,
        parent: object | None = None,
        index: int = 0,
        state: FakeState | None = None,
        text: FakeText | None = None,
        document: FakeDocument | None = None,
        description: str = "",
    ) -> None:
        self.role = role
        self.name = name
        self.app = app
        self.parent = parent
        self.indexInParent = index
        self.state = state or FakeState()
        self.text = text
        self.document = document
        self.description = description

    def getRoleName(self) -> str:
        return self.role

    def getApplication(self) -> FakeApp:
        return self.app

    def getState(self) -> FakeState:
        return self.state

    def queryText(self) -> FakeText:
        if self.text is None:
            raise RuntimeError("text unavailable")
        return self.text

    def queryDocument(self) -> FakeDocument:
        if self.document is None:
            raise RuntimeError("document unavailable")
        return self.document

    def getIndexInParent(self) -> int:
        return self.indexInParent


def test_atspi_runtime_helpers_project_object_payloads_without_live_pyatspi() -> None:
    app = FakeApp()
    frame = FakeAccessible(
        role="frame",
        name="Example Window",
        app=app,
        parent=app,
        index=0,
        document=FakeDocument({
            "DocURL": "https://example.test/page",
            "MimeType": "text/html",
            "Title": "Example",
        }),
    )
    field = FakeAccessible(
        role="entry",
        name="Search",
        app=app,
        parent=frame,
        index=2,
        state=FakeState("focused", "editable", "showing", "visible", "enabled", "single_line"),
        text=FakeText("hello atspi runtime", caret=5),
        description="Search field",
    )

    assert typing_atspi_adapters.atspi_state_flags(field, FakePyAtspi)["editable"] is True
    assert typing_atspi_adapters.atspi_text_payload(field, 5) == ("hello", len("hello atspi runtime"), 5, None)
    assert typing_atspi_adapters.atspi_object_path(field) == "0.0.2"

    attrs = typing_atspi_adapters.atspi_document_attributes(field)
    assert attrs["url"] == "https://example.test/page"
    assert attrs["content_type"] == "text/html"
    assert attrs["document_title"] == "Example"
    assert attrs["atspi_path"] == "0.0.2"
    assert attrs["document_path"] == "0.0"

    context = typing_atspi_adapters.atspi_object_context(field, FakePyAtspi)
    assert context["app"] == "firefox"
    assert context["window_title"] == "Example Window"
    assert context["role"] == "entry"
    assert context["name"] == "Search"
    assert context["states"]["focused"] is True
    assert context["app_process_id"] == 1234


def test_atspi_application_context_uses_bounded_proc_fallback(tmp_path) -> None:
    proc_root = tmp_path / "proc"
    (proc_root / "444").mkdir(parents=True)
    (proc_root / "444" / "comm").write_text("firefox\n", encoding="utf-8")
    app = FakeApp(name="-", pid=444)
    field = FakeAccessible(role="entry", name="Search", app=app)

    context = typing_atspi_adapters.atspi_application_context(field, proc_root=proc_root)

    assert context == {
        "name": "firefox",
        "process_id": 444,
        "toolkit_name": "gtk",
        "toolkit_version": "4",
    }


def test_focused_snapshot_sensitive_candidate_builds_metadata_only_ingest_plan() -> None:
    candidate = {
        "ok": True,
        "app": "browser",
        "window_title": "Login",
        "role": "password text",
        "name": "Password",
        "path": "1/2/3",
        "url": "https://example.test/login",
        "states": {"focused": True, "editable": True},
        "text_role": True,
        "sensitive_context": True,
        "text_read_allowed": False,
        "sensitive_matches": [{"kind": "sensitive_role", "role": "password text"}],
    }

    plan = typing_atspi_adapters.focused_snapshot_ingest_plan(
        candidate,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["action"] == "ingest"
    assert plan["result_status"] == "metadata_only_or_skipped_before_text_read"
    assert plan["ingest"]["source"] == typing_atspi_adapters.FOCUSED_SNAPSHOT_SOURCE
    assert plan["ingest"]["text"] == ""
    assert plan["ingest"]["force_metadata_only_reason"] == "focused_sensitive_context"
    assert plan["ingest"]["metadata"]["atspi"]["text_read"] is False
    assert plan["ingest"]["metadata"]["atspi"]["gate_decision"] == "metadata_only"

    event = {"ok": True, "status": "metadata_only", "event_id": "evt-1"}
    document = typing_atspi_adapters.focused_snapshot_document_from_event(
        plan,
        event,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert document["schema"] == "abyss_machine_typing_focused_snapshot_v1"
    assert document["status"] == "metadata_only_or_skipped_before_text_read"
    assert document["candidate"]["text_read_allowed"] is False
    assert document["policy"]["raw_keylogging"] is False
    assert document["event"] == event


def test_focused_snapshot_non_text_focus_builds_skip_document() -> None:
    plan = typing_atspi_adapters.focused_snapshot_ingest_plan(
        {
            "ok": True,
            "app": "gnome-shell",
            "window_title": "Main stage",
            "role": "window",
            "path": "0/0",
            "states": {"focused": True, "editable": False},
            "text_role": False,
            "sensitive_context": False,
            "text_read_allowed": False,
        },
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["action"] == "store"
    document = plan["document"]
    assert document["status"] == "skipped_non_text_focus"
    assert document["candidate"]["app"] == "gnome-shell"
    assert document["candidate"]["sensitive_matches"] == []
    assert document["policy"]["duplicate_gate"] is True


def test_atspi_text_event_builders_bound_private_browser_context_and_debounce() -> None:
    context_data = {
        "app": "firefox",
        "window_title": "Example",
        "role": "entry",
        "name": "Search",
        "states": {"editable": True, "focused": True, "sensitive": False},
        "app_process_id": 123,
        "app_toolkit_name": "gtk",
        "app_toolkit_version": "4",
    }
    browser_context = {
        "ok": True,
        "url": "https://example.test/private",
        "title": "Private title",
        "basis": "recent_nervous_browser_content_atspi_path",
    }

    sample = typing_atspi_adapters.atspi_text_event_sample_base(
        context_data,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
        event_type="object:text-changed:insert",
        event_detail1=1,
        event_detail2=2,
        event_any_data={"ignored": True},
        url="https://example.test/private",
        document_title="Example",
        content_type="text/html",
        source_atspi_path="0.1.2",
        document_atspi_path="0.1",
        browser_context_inference=browser_context,
        text_role=True,
        sensitive_context=False,
        sensitive_matches=[],
        controlled_sensitive_override={},
        capture_gate={"decision": "allow_text"},
    )
    metadata = typing_atspi_adapters.atspi_text_event_metadata(
        context_data,
        event_type="object:text-changed:insert",
        url="https://example.test/private",
        document_title="Example",
        content_type="text/html",
        source_atspi_path="0.1.2",
        document_atspi_path="0.1",
        gate_decision="allow_text",
        text_read=True,
        caret_offset=3,
        browser_context_inference=browser_context,
    )

    assert sample["source_adapter"] == typing_atspi_adapters.AT_SPI_TEXT_EVENT_SOURCE
    assert sample["browser_context_inference"] == {"ok": True, "basis": "recent_nervous_browser_content_atspi_path"}
    assert metadata["atspi"]["browser_context_inference"] == {"ok": True, "basis": "recent_nervous_browser_content_atspi_path"}
    assert metadata["atspi"]["caret_offset"] == 3
    assert typing_atspi_adapters.atspi_text_event_debounce_status(
        {"sha256": "same", "text_length": 5, "ts": 10.0},
        now_ts=10.2,
        text_hash="same",
        text_length=5,
        min_interval_sec=0.8,
        capture_length_change_updates=True,
    ) == "duplicate_snapshot_skipped"
    assert typing_atspi_adapters.atspi_text_event_debounce_status(
        {"sha256": "old", "text_length": 5, "ts": 10.0},
        now_ts=10.2,
        text_hash="new",
        text_length=5,
        min_interval_sec=0.8,
        capture_length_change_updates=False,
    ) == "debounced"


def test_generic_gui_selftest_document_accepts_safe_route_and_sensitive_metadata_only() -> None:
    plan = typing_atspi_adapters.generic_gui_selftest_plan("2026062700000012345")
    ingest = {
        "ok": True,
        "event_id": "evt-safe",
        "status": "captured",
        "source_adapter": typing_atspi_adapters.AT_SPI_TEXT_EVENT_SOURCE,
        "capture_gate": {"decision": "allow_text", "confidence": "atspi_generic_editable_text_allowed"},
        "text": {"text_length": len(plan["probe_text"]), "text_chars_stored": len(plan["probe_text"])},
        "causal_context": {"recipient": {"kind": "focused_application"}, "where": {}, "task": {}},
    }
    sensitive = {
        "ok": True,
        "event_id": "evt-sensitive",
        "status": "metadata_only",
        "capture_gate": {"decision": "metadata_only", "confidence": "sensitive_context"},
        "text": {"text_length": len(plan["sensitive_text"]), "text_chars_stored": 0, "metadata_only_reason": "capture_gate:metadata_only"},
    }
    event = {
        "event_id": "evt-safe",
        "generated_at": "2026-06-27T00:00:00Z",
        "status": "captured",
        "source_adapter": typing_atspi_adapters.AT_SPI_TEXT_EVENT_SOURCE,
        "capture_gate_decision": "allow_text",
        "capture_gate_confidence": "atspi_generic_editable_text_allowed",
        "text_length": len(plan["probe_text"]),
        "text_chars_stored": len(plan["probe_text"]),
        "text_sha256": plan["probe_hash"],
        "recipient": {"kind": "focused_application"},
    }

    document = typing_atspi_adapters.generic_gui_selftest_document(
        plan=plan,
        ingest=ingest,
        sensitive=sensitive,
        event=event,
        parse_errors=[],
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert document["ok"] is True
    assert document["status"] == "passed"
    assert document["probe"]["text_omitted"] is True
    assert document["sensitive_probe"]["text_chars_stored"] == 0
    assert document["policy"]["raw_keylogging"] is False
