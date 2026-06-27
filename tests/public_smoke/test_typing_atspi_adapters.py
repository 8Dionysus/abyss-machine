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

    def setCaretOffset(self, offset: int) -> None:
        self.caretOffset = offset


class FakeEditableText:
    def __init__(self, text: FakeText) -> None:
        self.text = text

    def insertText(self, offset: int, insert_text: str, length: int) -> bool:
        payload = insert_text[:length]
        self.text.text = self.text.text[:offset] + payload + self.text.text[offset:]
        self.text.characterCount = len(self.text.text)
        self.text.caretOffset = offset + len(payload)
        return True

    def setTextContents(self, text: str) -> bool:
        self.text.text = text
        self.text.characterCount = len(text)
        self.text.caretOffset = len(text)
        return True


class FakeDocument:
    def __init__(self, attributes: dict[str, str]) -> None:
        self.attributes = dict(attributes)

    def getAttributeValue(self, key: str) -> str:
        return self.attributes.get(key, "")

    def getAttributes(self) -> list[str]:
        return [f"{key}:{value}" for key, value in self.attributes.items()]


class FakeComponent:
    def __init__(self, obj: "FakeAccessible") -> None:
        self.obj = obj

    def grabFocus(self) -> bool:
        self.obj.state.flags.add("focused")
        return True


class FakeAction:
    nActions = 1

    def __init__(self, obj: "FakeAccessible") -> None:
        self.obj = obj

    def getName(self, index: int) -> str:
        return "focus" if index == 0 else ""

    def doAction(self, index: int) -> bool:
        if index == 0:
            self.obj.state.flags.add("focused")
            return True
        return False


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
        children: list["FakeAccessible"] | None = None,
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
        self.children = list(children or [])
        for child_index, child in enumerate(self.children):
            child.parent = self
            child.indexInParent = child_index

    def getRoleName(self) -> str:
        return self.role

    def __iter__(self):
        return iter(self.children)

    def getApplication(self) -> FakeApp:
        return self.app

    def getState(self) -> FakeState:
        return self.state

    def queryText(self) -> FakeText:
        if self.text is None:
            raise RuntimeError("text unavailable")
        return self.text

    def queryEditableText(self) -> FakeEditableText:
        if self.text is None:
            raise RuntimeError("editable text unavailable")
        return FakeEditableText(self.text)

    def queryDocument(self) -> FakeDocument:
        if self.document is None:
            raise RuntimeError("document unavailable")
        return self.document

    def queryComponent(self) -> FakeComponent:
        return FakeComponent(self)

    def queryAction(self) -> FakeAction:
        return FakeAction(self)

    def getIndexInParent(self) -> int:
        return self.indexInParent


class FakeAtspiEvent:
    def __init__(self, event_type: str, source: object) -> None:
        self.type = event_type
        self.source = source
        self.detail1 = 1
        self.detail2 = 2
        self.any_data = {"kind": "fake"}


class FakeRegistry:
    def __init__(self, events: list[FakeAtspiEvent], desktop: object | None = None) -> None:
        self.events = events
        self.desktop = desktop
        self.listeners: list[tuple[object, str]] = []
        self.stop_calls = 0
        self.started = False

    def getDesktop(self, index: int) -> object:
        if self.desktop is None:
            raise RuntimeError("desktop unavailable")
        return self.desktop

    def registerEventListener(self, callback: object, event_type: str) -> None:
        self.listeners.append((callback, event_type))

    def start(self) -> None:
        self.started = True
        for event in self.events:
            for callback, event_type in list(self.listeners):
                if event_type == event.type:
                    callback(event)  # type: ignore[misc]

    def stop(self) -> None:
        self.stop_calls += 1


class FakeGiAtspi:
    class Role:
        ENTRY = "entry"
        TEXT = "text"
        PARAGRAPH = "paragraph"
        DOCUMENT_WEB = "document web"
        DOCUMENT_FRAME = "document frame"
        DOCUMENT_TEXT = "document text"
        DOCUMENT_EMAIL = "document email"

    class StateType:
        FOCUSED = "focused"
        EDITABLE = "editable"
        SHOWING = "showing"
        VISIBLE = "visible"
        SENSITIVE = "sensitive"
        ENABLED = "enabled"
        ACTIVE = "active"

    desktop: object | None = None

    @classmethod
    def get_desktop(cls, index: int) -> object:
        if cls.desktop is None:
            raise RuntimeError("desktop unavailable")
        return cls.desktop

    class Accessible:
        @staticmethod
        def get_role(node: "FakeGiNode") -> str:
            return node.role

        @staticmethod
        def get_role_name(node: "FakeGiNode") -> str:
            return node.role_name

        @staticmethod
        def get_name(node: "FakeGiNode") -> str:
            return node.name

        @staticmethod
        def get_child_count(node: "FakeGiNode") -> int:
            return len(node.children)

        @staticmethod
        def get_child_at_index(node: "FakeGiNode", index: int) -> "FakeGiNode":
            return node.children[index]

        @staticmethod
        def get_text_iface(node: "FakeGiNode") -> "FakeGiText | None":
            return node.text

        @staticmethod
        def get_editable_text_iface(node: "FakeGiNode") -> "FakeGiEditableText | None":
            return FakeGiEditableText(node.text) if node.text is not None else None

        @staticmethod
        def get_component_iface(node: "FakeGiNode") -> "FakeGiComponent":
            return FakeGiComponent(node)

        @staticmethod
        def get_action_iface(node: "FakeGiNode") -> "FakeGiAction | None":
            return FakeGiAction(node) if node.action_names else None

        @staticmethod
        def get_document_attribute_value(node: "FakeGiNode", key: str) -> str:
            return node.document_attributes.get(key, "")

    class Text:
        @staticmethod
        def get_character_count(text: "FakeGiText") -> int:
            return len(text.value)

        @staticmethod
        def get_caret_offset(text: "FakeGiText") -> int:
            return text.caret

        @staticmethod
        def get_text(text: "FakeGiText", start: int, end: int) -> str:
            return text.value[start:end]

        @staticmethod
        def set_caret_offset(text: "FakeGiText", offset: int) -> bool:
            text.caret = offset
            return True

    class EditableText:
        @staticmethod
        def insert_text(editable: "FakeGiEditableText", offset: int, insert_text: str, length: int) -> bool:
            return editable.insert_text(offset, insert_text, length)

        @staticmethod
        def set_text_contents(editable: "FakeGiEditableText", text: str) -> bool:
            return editable.set_text_contents(text)

    class Component:
        @staticmethod
        def grab_focus(component: "FakeGiComponent") -> bool:
            return component.grab_focus()

    class Action:
        @staticmethod
        def get_n_actions(action: "FakeGiAction") -> int:
            return len(action.node.action_names)

        @staticmethod
        def get_action_name(action: "FakeGiAction", index: int) -> str:
            return action.node.action_names[index]

        @staticmethod
        def do_action(action: "FakeGiAction", index: int) -> bool:
            return action.do_action(index)


class FakeGiStateSet:
    def __init__(self, flags: set[str]) -> None:
        self.flags = flags

    def contains(self, flag: str) -> bool:
        return flag in self.flags


class FakeGiText:
    def __init__(self, value: str, caret: int = 0) -> None:
        self.value = value
        self.caret = caret


class FakeGiEditableText:
    def __init__(self, text: FakeGiText | None) -> None:
        if text is None:
            raise RuntimeError("editable text unavailable")
        self.text = text

    def insert_text(self, offset: int, insert_text: str, length: int) -> bool:
        payload = insert_text[:length]
        self.text.value = self.text.value[:offset] + payload + self.text.value[offset:]
        self.text.caret = offset + len(payload)
        return True

    def set_text_contents(self, text: str) -> bool:
        self.text.value = text
        self.text.caret = len(text)
        return True


class FakeGiComponent:
    def __init__(self, node: "FakeGiNode") -> None:
        self.node = node

    def grab_focus(self) -> bool:
        self.node.states.add("focused")
        return True


class FakeGiAction:
    def __init__(self, node: "FakeGiNode") -> None:
        self.node = node

    def do_action(self, index: int) -> bool:
        name = self.node.action_names[index].lower()
        self.node.actions_done.append(name)
        if name == "focus":
            self.node.states.add("focused")
        if name == "activate":
            self.node.states.add("active")
        return True


class FakeGiNode:
    def __init__(
        self,
        *,
        role: str,
        role_name: str | None = None,
        name: str = "",
        states: set[str] | None = None,
        text: FakeGiText | None = None,
        document_attributes: dict[str, str] | None = None,
        action_names: list[str] | None = None,
        children: list["FakeGiNode"] | None = None,
    ) -> None:
        self.role = role
        self.role_name = role_name or role
        self.name = name
        self.states = set(states or set())
        self.text = text
        self.document_attributes = dict(document_attributes or {})
        self.action_names = list(action_names or [])
        self.actions_done: list[str] = []
        self.children = list(children or [])

    def get_state_set(self) -> FakeGiStateSet:
        return FakeGiStateSet(self.states)


class FakeTimer:
    def __init__(self, seconds: float, callback: object) -> None:
        self.seconds = seconds
        self.callback = callback
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


class FakeClock:
    def __init__(self) -> None:
        self.ticks = 0

    def now_iso(self) -> str:
        self.ticks += 1
        return f"2026-06-27T00:00:{self.ticks:02d}Z"

    def monotonic(self) -> float:
        self.ticks += 1
        return float(self.ticks) / 10.0


def test_atspi_listener_runtime_registers_events_and_routes_samples_without_live_pyatspi() -> None:
    field = object()
    registry = FakeRegistry([
        FakeAtspiEvent("object:text-changed:insert", field),
        FakeAtspiEvent("object:text-changed:insert", field),
    ])
    pyatspi_module = type("FakePyAtspiModule", (), {"Registry": registry})()
    clock = FakeClock()
    compact_calls: list[tuple[dict[str, object] | None, str, str | None]] = []
    stored: list[tuple[str, bool, int]] = []
    handled: list[str] = []

    def handle_event(event: object, pyatspi: object, last_by_context: dict[str, dict[str, object]], write_latest: bool) -> dict[str, object]:
        assert pyatspi is pyatspi_module
        assert write_latest is True
        handled.append(event.type)  # type: ignore[attr-defined]
        last_by_context["fake"] = {"event_id": "evt-1"}
        return {
            "generated_at": clock.now_iso(),
            "status": "captured",
            "typing_event": {"event_id": "evt-1", "status": "captured"},
        }

    def store_latest_history(data: dict[str, object], write_latest: bool) -> dict[str, object]:
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        stored.append((str(data.get("status")), write_latest, int(summary.get("events_seen") or 0)))
        return data

    def append_compact_history(
        data: dict[str, object],
        sample: dict[str, object] | None,
        listener_status: str,
        error: str | None,
    ) -> dict[str, object] | None:
        compact_calls.append((sample, listener_status, error))
        return None

    data = typing_atspi_adapters.run_atspi_text_events_listener(
        schema_prefix="abyss_machine",
        version="test",
        generated_at=clock.now_iso(),
        events_policy={"event_types": ["object:text-changed:insert"], "max_events_per_run": 1},
        seconds=1.0,
        forever=False,
        write_latest=True,
        handle_event=handle_event,
        store_latest_history=store_latest_history,
        write_latest_only=lambda data: [],
        append_compact_history=append_compact_history,
        pyatspi_module=pyatspi_module,
        now_iso=clock.now_iso,
        monotonic=clock.monotonic,
        timer_factory=FakeTimer,
    )

    assert registry.listeners and registry.listeners[0][1] == "object:text-changed:insert"
    assert registry.started is True
    assert registry.stop_calls == 1
    assert handled == ["object:text-changed:insert"]
    assert data["ok"] is True
    assert data["status"] == "sample_complete"
    assert data["summary"]["events_seen"] == 1
    assert data["summary"]["captured"] == 1
    assert data["last_typing_event_id"] == "evt-1"
    assert compact_calls[0][1] == "running"
    assert stored[-1][0] == "sample_complete"


def test_atspi_listener_runtime_reports_missing_pyatspi_through_store_callback() -> None:
    stored: list[dict[str, object]] = []

    def store_latest_history(data: dict[str, object], write_latest: bool) -> dict[str, object]:
        stored.append(dict(data))
        return data

    data = typing_atspi_adapters.run_atspi_text_events_listener(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
        events_policy={},
        seconds=1.0,
        forever=False,
        write_latest=True,
        handle_event=lambda event, pyatspi, last_by_context, write_latest: {},
        store_latest_history=store_latest_history,
        write_latest_only=lambda data: [],
        append_compact_history=lambda data, sample, listener_status, error: None,
        load_pyatspi=lambda: (None, "pyatspi_unavailable: missing fake module"),
    )

    assert data["ok"] is False
    assert data["status"] == "pyatspi_unavailable"
    assert data["error"] == "pyatspi_unavailable: missing fake module"
    assert stored and stored[-1]["status"] == "pyatspi_unavailable"


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


def test_atspi_focused_candidate_walk_routes_tree_through_builder_without_live_pyatspi() -> None:
    app = FakeApp()
    field = FakeAccessible(
        role="entry",
        name="Search",
        app=app,
        state=FakeState("focused", "editable", "showing", "visible", "enabled"),
        text=FakeText("focused text", caret=7),
        document=FakeDocument({"DocURL": "https://example.test/write", "Title": "Write"}),
    )
    frame = FakeAccessible(role="frame", name="Example Window", app=app, children=[field])
    app_node = FakeAccessible(role="application", name="firefox", app=app, children=[frame])
    desktop = FakeAccessible(role="desktop", name="desktop", app=app, children=[app_node])
    registry = FakeRegistry([], desktop)
    pyatspi_module = type("FakePyAtspiModule", (FakePyAtspi,), {"Registry": registry})()
    snapshots: list[dict[str, object]] = []

    def build_candidate(obj: object, pyatspi: object, snapshot: dict[str, object]) -> dict[str, object]:
        assert obj is field
        assert pyatspi is pyatspi_module
        snapshots.append(snapshot)
        text, text_length, caret, text_error = typing_atspi_adapters.atspi_text_payload(obj, 120)
        return {
            "ok": text_error is None,
            "text_role": True,
            "sensitive_context": False,
            "path": snapshot["path"],
            "role": snapshot["role"],
            "app": snapshot["app"],
            "window_title": snapshot["window_title"],
            "text": text,
            "text_length": text_length,
            "caret_offset": caret,
        }

    data = typing_atspi_adapters.atspi_focused_candidate_walk(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-27T00:00:00Z",
        max_nodes=20,
        max_depth=8,
        timeout_sec=1.0,
        build_candidate=build_candidate,
        pyatspi_module=pyatspi_module,
        monotonic=lambda: 0.0,
    )

    assert "error" not in data
    assert data["nodes_seen"] >= 3
    assert data["candidates"][0]["text"] == "focused text"
    assert data["candidates"][0]["path"] == "0/0/0"
    assert snapshots[0]["document_attrs"]["url"] == "https://example.test/write"
    assert snapshots[0]["window_title"] == "Example Window"


def test_atspi_focus_metadata_by_path_resolves_path_and_focuses_without_live_pyatspi() -> None:
    app = FakeApp()
    field = FakeAccessible(
        role="entry",
        name="Search",
        app=app,
        state=FakeState("editable", "showing", "visible", "enabled"),
        document=FakeDocument({"DocURL": "https://example.test/write", "Title": "Write"}),
    )
    frame = FakeAccessible(role="frame", name="Example Window", app=app, children=[field])
    app_node = FakeAccessible(role="application", name="firefox", app=app, children=[frame])
    desktop = FakeAccessible(role="desktop", name="desktop", app=app, children=[app_node])
    registry = FakeRegistry([], desktop)
    pyatspi_module = type("FakePyAtspiModule", (FakePyAtspi,), {"Registry": registry})()

    data = typing_atspi_adapters.atspi_focus_metadata_by_path(
        "0.0.0",
        "https://example.test/write",
        pyatspi_module=pyatspi_module,
        sleep=lambda seconds: None,
    )

    assert data["ok"] is True
    assert data["status"] == "focused"
    assert data["matched"]["role"] == "entry"
    assert data["matched"]["url"] == "https://example.test/write"
    assert data["matched"]["states_after"]["focused"] is True
    assert data["matched"]["text_read"] is False


def test_atspi_focus_text_by_path_matches_hash_and_focuses_without_live_pyatspi() -> None:
    app = FakeApp()
    text = FakeText("safe browser text", caret=17)
    field = FakeAccessible(
        role="entry",
        name="Search",
        app=app,
        state=FakeState("editable", "showing", "visible", "enabled"),
        text=text,
        document=FakeDocument({"DocURL": "https://example.test/write", "Title": "Write"}),
    )
    frame = FakeAccessible(role="frame", name="Example Window", app=app, children=[field])
    app_node = FakeAccessible(role="application", name="firefox", app=app, children=[frame])
    desktop = FakeAccessible(role="desktop", name="desktop", app=app, children=[app_node])
    registry = FakeRegistry([], desktop)
    pyatspi_module = type("FakePyAtspiModule", (FakePyAtspi,), {"Registry": registry})()

    data = typing_atspi_adapters.atspi_focus_text_by_path(
        "0.0.0",
        "https://example.test/write",
        typing_atspi_adapters.text_sha256("safe browser text"),
        pyatspi_module=pyatspi_module,
        sleep=lambda seconds: None,
    )

    assert data["ok"] is True
    assert data["status"] == "focused"
    assert data["matched"]["expected_text_match"] is True
    assert data["matched"]["text_sha256"] == typing_atspi_adapters.text_sha256("safe browser text")
    assert data["matched"]["focus"]["states_after"]["focused"] is True


def test_atspi_insert_text_by_path_mutates_expected_text_without_live_pyatspi() -> None:
    app = FakeApp()
    text = FakeText("safe browser text", caret=len("safe browser text"))
    field = FakeAccessible(
        role="entry",
        name="Search",
        app=app,
        state=FakeState("editable", "showing", "visible", "enabled"),
        text=text,
        document=FakeDocument({"DocURL": "https://example.test/write", "Title": "Write"}),
    )
    frame = FakeAccessible(role="frame", name="Example Window", app=app, children=[field])
    app_node = FakeAccessible(role="application", name="firefox", app=app, children=[frame])
    desktop = FakeAccessible(role="desktop", name="desktop", app=app, children=[app_node])
    registry = FakeRegistry([], desktop)
    pyatspi_module = type("FakePyAtspiModule", (FakePyAtspi,), {"Registry": registry})()

    data = typing_atspi_adapters.atspi_insert_text_by_path(
        "0.0.0",
        "https://example.test/write",
        typing_atspi_adapters.text_sha256("safe browser text"),
        " plus insert",
        pyatspi_module=pyatspi_module,
        sleep=lambda seconds: None,
    )

    expected_after = "safe browser text plus insert"
    assert data["ok"] is True
    assert data["status"] == "inserted"
    assert data["method"] == "atspi_editable_text_insert"
    assert data["matched"]["insert_ok"] is True
    assert data["matched"]["after_expected_match"] is True
    assert data["matched"]["after_text_sha256"] == typing_atspi_adapters.text_sha256(expected_after)
    assert text.text == expected_after


def test_atspi_insert_text_by_url_mutates_expected_firefox_document_without_live_gi() -> None:
    text = FakeGiText("safe browser text", caret=len("safe browser text"))
    field = FakeGiNode(
        role=FakeGiAtspi.Role.ENTRY,
        name="Search",
        states={"editable", "showing", "visible", "enabled"},
        text=text,
    )
    document = FakeGiNode(
        role=FakeGiAtspi.Role.DOCUMENT_FRAME,
        name="Example",
        states={"showing", "visible"},
        document_attributes={
            "DocURL": "https://example.test/write",
            "Title": "Write",
            "MimeType": "text/html",
        },
        children=[field],
    )
    app = FakeGiNode(role="application", name="firefox", children=[document])
    desktop = FakeGiNode(role="desktop", name="desktop", children=[app])
    FakeGiAtspi.desktop = desktop

    data = typing_atspi_adapters.atspi_insert_text_by_url(
        "https://example.test/write",
        typing_atspi_adapters.text_sha256("safe browser text"),
        " plus insert",
        atspi_module=FakeGiAtspi,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: None,
    )

    expected_after = "safe browser text plus insert"
    assert data["ok"] is True
    assert data["status"] == "inserted"
    assert data["method"] == "atspi_editable_text_insert"
    assert data["matched"]["path"] == "0.0.0"
    assert data["matched"]["document_path"] == "0.0"
    assert data["matched"]["field_focus"]["component_grab_focus"] is True
    assert data["matched"]["after_expected_match"] is True
    assert data["matched"]["after_text_sha256"] == typing_atspi_adapters.text_sha256(expected_after)
    assert text.value == expected_after
    assert "focused" in field.states


def test_atspi_insert_text_by_url_refuses_unexpected_current_text_without_live_gi() -> None:
    text = FakeGiText("different browser text", caret=len("different browser text"))
    field = FakeGiNode(
        role=FakeGiAtspi.Role.ENTRY,
        name="Search",
        states={"editable", "showing", "visible", "enabled"},
        text=text,
    )
    document = FakeGiNode(
        role=FakeGiAtspi.Role.DOCUMENT_FRAME,
        name="Example",
        states={"showing", "visible"},
        document_attributes={"DocURL": "https://example.test/write", "Title": "Write"},
        children=[field],
    )
    app = FakeGiNode(role="application", name="firefox", children=[document])
    desktop = FakeGiNode(role="desktop", name="desktop", children=[app])
    FakeGiAtspi.desktop = desktop

    data = typing_atspi_adapters.atspi_insert_text_by_url(
        "https://example.test/write",
        typing_atspi_adapters.text_sha256("safe browser text"),
        " plus insert",
        atspi_module=FakeGiAtspi,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: None,
    )

    assert data["ok"] is False
    assert data["status"] == "matched_unexpected_current_text"
    assert data["matched"]["expected_current_text_match"] is False
    assert text.value == "different browser text"


def test_atspi_focus_firefox_frame_by_title_focuses_matching_window_without_live_gi() -> None:
    frame = FakeGiNode(
        role="frame",
        role_name="frame",
        name="Abyss focused browser safe input probe - Mozilla Firefox",
        states={"showing", "visible"},
        action_names=["focus", "activate"],
    )
    other_frame = FakeGiNode(
        role="frame",
        role_name="frame",
        name="Other Firefox Window",
        states={"showing", "visible"},
    )
    app = FakeGiNode(role="application", name="firefox", children=[other_frame, frame])
    desktop = FakeGiNode(role="desktop", name="desktop", children=[app])
    FakeGiAtspi.desktop = desktop

    data = typing_atspi_adapters.atspi_focus_firefox_frame_by_title(
        "Abyss focused browser safe input probe",
        atspi_module=FakeGiAtspi,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: None,
    )

    assert data["ok"] is True
    assert data["status"] == "focused"
    assert data["policy"]["window_focus_only"] is True
    assert data["matched"]["child_index"] == 1
    assert data["matched"]["title_match"] is True
    assert data["matched"]["states_before"]["focused"] is False
    assert data["matched"]["focus"]["component_grab_focus"] is True
    assert data["matched"]["focus"]["actions"] == [
        {"name": "focus", "ok": True},
        {"name": "activate", "ok": True},
    ]
    assert data["matched"]["focus"]["states_after"]["focused"] is True
    assert data["matched"]["focus"]["states_after"]["active"] is True
    assert frame.actions_done == ["focus", "activate"]


def test_atspi_focus_firefox_frame_by_title_reports_unavailable_without_live_gi() -> None:
    data = typing_atspi_adapters.atspi_focus_firefox_frame_by_title(
        "Abyss focused browser safe input probe",
        load_atspi=lambda: (None, "AT-SPI import failed: missing fake module"),
    )

    assert data["ok"] is False
    assert data["status"] == "atspi_unavailable"
    assert data["error"] == "AT-SPI import failed: missing fake module"
    assert data["attempts"] == []


def test_atspi_focus_metadata_by_url_walks_document_targets_without_live_pyatspi() -> None:
    app = FakeApp()
    field = FakeAccessible(
        role="entry",
        name="Search",
        app=app,
        state=FakeState("editable", "showing", "visible", "enabled"),
    )
    frame = FakeAccessible(
        role="document frame",
        name="Example",
        app=app,
        document=FakeDocument({"DocURL": "https://example.test/write", "Title": "Write"}),
        children=[field],
    )
    app_node = FakeAccessible(role="application", name="firefox", app=app, children=[frame])
    desktop = FakeAccessible(role="desktop", name="desktop", app=app, children=[app_node])
    registry = FakeRegistry([], desktop)
    pyatspi_module = type("FakePyAtspiModule", (FakePyAtspi,), {"Registry": registry})()

    data = typing_atspi_adapters.atspi_focus_metadata_by_url(
        "https://example.test/write",
        timeout_sec=1.0,
        pyatspi_module=pyatspi_module,
        monotonic=lambda: 0.0,
        sleep=lambda seconds: None,
    )

    assert data["ok"] is True
    assert data["status"] == "focused"
    assert data["matched"]["url"] == "https://example.test/write"
    assert data["matched"]["text_read"] is False
    assert data["matched"]["states_after"]["focused"] is True


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
