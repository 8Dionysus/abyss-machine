from __future__ import annotations

import hashlib
import io
import struct

import pytest

from abyss_machine import cli
from abyss_machine import typing_browser_adapters


def test_firefox_extension_profiles_parse_relative_and_absolute_paths(tmp_path) -> None:
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        "\n".join([
            "[Profile0]",
            "Name=default-release",
            "IsRelative=1",
            "Path=abc.default-release",
            "Default=1",
            "",
            "[Profile1]",
            "Name=work",
            "IsRelative=0",
            "Path=/srv/firefox/work",
            "Default=0",
        ]),
        encoding="utf-8",
    )

    profiles = typing_browser_adapters.firefox_extension_profiles(
        profiles_ini,
        extension_id="fixture@example.test",
    )

    assert profiles == [
        {
            "name": "default-release",
            "path": str(tmp_path / "abc.default-release"),
            "default": True,
            "extensions_json": str(tmp_path / "abc.default-release" / "extensions.json"),
            "sideload_xpi": str(tmp_path / "abc.default-release" / "extensions" / "fixture@example.test.xpi"),
        },
        {
            "name": "work",
            "path": "/srv/firefox/work",
            "default": False,
            "extensions_json": "/srv/firefox/work/extensions.json",
            "sideload_xpi": "/srv/firefox/work/extensions/fixture@example.test.xpi",
        },
    ]


def test_firefox_release_profile_selection_order_is_public_safe(tmp_path) -> None:
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        "\n".join([
            "[Install123]",
            "Default=custom.profile",
            "",
            "[Profile0]",
            "Name=default-release",
            "IsRelative=1",
            "Path=default-release.profile",
            "Default=1",
            "",
            "[Profile1]",
            "Name=custom",
            "IsRelative=1",
            "Path=custom.profile",
            "Default=0",
        ]),
        encoding="utf-8",
    )

    selected = typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    )

    assert selected is not None
    assert selected["name"] == "custom"
    assert selected["selection"] == "install_default"
    assert selected["path"] == str(tmp_path / "custom.profile")


def test_firefox_release_profile_falls_back_to_named_default_then_profile_default(tmp_path) -> None:
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        "\n".join([
            "[Profile0]",
            "Name=default-release",
            "IsRelative=1",
            "Path=release.profile",
            "Default=0",
            "",
            "[Profile1]",
            "Name=other",
            "IsRelative=1",
            "Path=other.profile",
            "Default=1",
        ]),
        encoding="utf-8",
    )

    selected = typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    )
    assert selected is not None
    assert selected["name"] == "default-release"
    assert selected["selection"] == "named_default_release"

    profiles_ini.write_text(
        "\n".join([
            "[Profile0]",
            "Name=plain",
            "IsRelative=1",
            "Path=plain.profile",
            "Default=1",
        ]),
        encoding="utf-8",
    )
    fallback = typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    )
    assert fallback is not None
    assert fallback["name"] == "plain"
    assert fallback["selection"] == "profile_default"


def test_firefox_profiles_missing_file_preserves_empty_behavior(tmp_path) -> None:
    profiles_ini = tmp_path / "missing.ini"

    assert typing_browser_adapters.firefox_extension_profiles(
        profiles_ini,
        extension_id="fixture@example.test",
    ) == []
    assert typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    ) is None


def test_browser_extension_plan_and_status_document_are_public_safe() -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "browser_name": "firefox",
        "title": "Writing",
        "url": "https://example.test/write",
        "text": "synthetic browser text",
        "field": {"safe": True, "kind": "textarea", "type": "textarea"},
    }

    plan = typing_browser_adapters.browser_extension_ingest_plan(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["valid"] is True
    assert plan["source_adapter"] == "browser_extension_explicit"
    assert plan["ingest"]["text"] == "synthetic browser text"
    assert plan["ingest"]["source"] == "browser_extension_explicit"
    assert plan["ingest"]["app"] == "firefox"
    assert "event_kind=committed_text" in plan["ingest"]["context"]
    assert "field_safe=True" in plan["ingest"]["context"]
    assert plan["ingest"]["metadata"]["browser"]["key_events_captured"] is False

    status = typing_browser_adapters.browser_extension_status_document(
        plan,
        {
            "ok": True,
            "event_id": "evt-browser",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"text_length": 22, "text_chars_stored": 22},
            "duplicate": False,
        },
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:02Z",
    )

    assert status["schema"] == "abyss_machine_typing_browser_extension_status_v1"
    assert status["ok"] is True
    assert status["event"]["event_id"] == "evt-browser"
    assert status["event"]["capture_gate_confidence"] == "browser_url_and_field_allowed"
    assert status["policy"]["raw_keylogging"] is False
    assert "text" not in status["event"]


def test_browser_ai_transcript_plan_cleans_text_and_preserves_counterpart_metadata() -> None:
    message = {
        "schema": "abyss_machine_browser_ai_transcript_message_v1",
        "event_kind": "ai_transcript_message",
        "browser_name": "firefox",
        "title": "ChatGPT",
        "url": "https://chatgpt.com/c/fixture",
        "text": "ChatGPT said hello\nShow more",
        "browser": {"transcript_safe": True},
        "ai_transcript": {"safe": True, "message_role": "bubble", "message_index": "3", "partial": False},
    }

    plan = typing_browser_adapters.browser_ai_transcript_ingest_plan(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["valid"] is True
    assert plan["source_adapter"] == "browser_ai_transcript"
    assert plan["ingest"]["text"] == "ChatGPT said hello"
    assert "transcript_safe=True" in plan["ingest"]["context"]
    assert "message_role=assistant" in plan["ingest"]["context"]
    assert plan["text_cleanup"]["removed_line_count"] == 1
    assert plan["transcript_meta"]["message_role"] == "assistant"
    assert plan["transcript_meta"]["page_identity"]["entity_id"] == "ai:openai:chatgpt"

    status = typing_browser_adapters.browser_ai_transcript_status_document(
        plan,
        {
            "ok": True,
            "event_id": "evt-ai",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "source_adapter": "browser_ai_transcript",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_ai_transcript_known_ai_page_allowed"},
            "text": {"text_length": 18, "text_chars_stored": 18, "truncated": False},
            "causal_context": {
                "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
                "where": {"context_anchor": {"kind": "ai_chat"}, "interaction": {"id": "fixture"}},
            },
        },
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:02Z",
    )

    assert status["schema"] == "abyss_machine_typing_browser_ai_transcript_status_v1"
    assert status["event"]["message_role"] == "assistant"
    assert status["event"]["message_index"] == 3
    assert status["event"]["recipient"]["id"] == "ai:openai:chatgpt"
    assert status["policy"]["known_ai_counterpart_required"] is True


def test_browser_selftest_documents_and_native_host_response_envelopes() -> None:
    run_id = typing_browser_adapters.browser_selftest_run_id("fixture-seed")
    safe_message, sensitive_message = typing_browser_adapters.browser_extension_selftest_messages(run_id)
    ai_message, ai_sensitive_message = typing_browser_adapters.browser_ai_transcript_selftest_messages(run_id)

    assert len(run_id) == 12
    assert safe_message["text"].endswith(run_id)
    assert sensitive_message["url"] == "https://example.com/login"
    assert typing_browser_adapters.native_host_message_route(safe_message) == "browser_extension_explicit"
    assert typing_browser_adapters.native_host_message_route(ai_message) == "browser_ai_transcript"
    assert typing_browser_adapters.native_host_message_route(ai_sensitive_message) == "browser_ai_transcript"

    safe = {
        "ok": True,
        "event": {
            "source_adapter": "browser_ai_transcript",
            "status": "captured",
            "capture_gate_decision": "allow_text",
            "recipient": {"id": "ai:google:gemini"},
            "message_role": "assistant",
        },
    }
    sensitive = {"ok": True, "event": {"capture_gate_decision": "metadata_only", "text_chars_stored": 0}}
    selftest = typing_browser_adapters.browser_ai_transcript_selftest_document(
        safe=safe,
        sensitive=sensitive,
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
        test_run_id=run_id,
    )
    response = typing_browser_adapters.native_host_response({"ok": True, "status": "sent", "event": {"event_id": "evt"}, "policy": {"raw_keylogging": False}})
    error = typing_browser_adapters.native_host_error_response(ValueError("boom"))

    assert selftest["ok"] is True
    assert selftest["status"] == "passed"
    assert response == {"ok": True, "status": "sent", "event": {"event_id": "evt"}, "policy": {"raw_keylogging": False}}
    assert error["ok"] is False
    assert error["status"] == "native_host_error"
    assert error["policy"]["automatic_action"] is False


def test_native_host_transport_reads_and_writes_length_prefixed_json() -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "text": "synthetic browser text",
    }
    framed = typing_browser_adapters.native_host_encode_response_frame(message)
    decoded = typing_browser_adapters.native_host_read_message(io.BytesIO(framed))
    empty = typing_browser_adapters.native_host_read_message(io.BytesIO(b""))

    assert decoded == message
    assert empty is None

    out = io.BytesIO()
    typing_browser_adapters.native_host_write_response(out, {"ok": True, "status": "captured", "note": "synthetic"})
    raw = out.getvalue()
    length = struct.unpack("<I", raw[:4])[0]
    assert length == len(raw[4:])
    assert raw[4:] == b'{"ok":true,"status":"captured","note":"synthetic"}'


def test_cli_native_host_transport_binds_to_standard_buffers(monkeypatch) -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "text": "synthetic browser text",
    }
    stdin_buffer = io.BytesIO(typing_browser_adapters.native_host_encode_response_frame(message))
    stdout_buffer = io.BytesIO()

    class FakeStdin:
        buffer = stdin_buffer

    class FakeStdout:
        buffer = stdout_buffer

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())
    monkeypatch.setattr(cli.sys, "stdout", FakeStdout())

    assert cli.typing_browser_native_host_read_message() == message
    cli.typing_browser_native_host_write_response({"ok": True, "status": "captured"})

    raw = stdout_buffer.getvalue()
    assert struct.unpack("<I", raw[:4])[0] == len(raw[4:])
    assert raw[4:] == b'{"ok":true,"status":"captured"}'


def test_native_host_transport_rejects_malformed_frames() -> None:
    with pytest.raises(ValueError, match="header"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(b"\x01\x02"))
    with pytest.raises(ValueError, match="out of range"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 0)))
    with pytest.raises(ValueError, match="out of range"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 1024 * 1024 + 1)))
    with pytest.raises(ValueError, match="truncated"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 5) + b"{}"))
    with pytest.raises(ValueError, match="JSON object"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 2) + b"[]"))


def test_browser_webextension_base_command_selects_path_or_offline_npm(tmp_path) -> None:
    direct_command, direct_info = typing_browser_adapters.browser_webextension_base_command(
        npm_cache=tmp_path / "npm",
        which=lambda name: "/usr/bin/web-ext" if name == "web-ext" else None,
    )
    npm_command, npm_info = typing_browser_adapters.browser_webextension_base_command(
        npm_cache=tmp_path / "npm",
        which=lambda name: "/usr/bin/npm" if name == "npm" else None,
    )
    missing_command, missing_info = typing_browser_adapters.browser_webextension_base_command(
        npm_cache=tmp_path / "npm",
        which=lambda name: None,
    )

    assert direct_command == ["/usr/bin/web-ext"]
    assert direct_info["route"] == "path"
    assert npm_command[:5] == ["/usr/bin/npm", "exec", "--offline", "--yes", "--package"]
    assert npm_info["route"] == "npm_exec_offline"
    assert npm_info["npm_cache"] == str(tmp_path / "npm")
    assert missing_command == []
    assert missing_info["route"] == "missing"


def test_browser_webextension_selftest_reports_missing_runtime_without_probe(tmp_path) -> None:
    called = {"probe": False}

    def forbidden_probe(_text_sha: str, _limit: int):
        called["probe"] = True
        return None, []

    firefox_missing = typing_browser_adapters.browser_webextension_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        extension_root=tmp_path / "extension",
        npm_cache=tmp_path / "npm",
        schema_prefix="abyss_machine",
        version="fixture-version",
        find_probe_event=forbidden_probe,
        which=lambda name: None,
    )
    web_ext_missing = typing_browser_adapters.browser_webextension_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        extension_root=tmp_path / "extension",
        npm_cache=tmp_path / "npm",
        schema_prefix="abyss_machine",
        version="fixture-version",
        find_probe_event=forbidden_probe,
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
    )

    assert firefox_missing["status"] == "firefox_missing"
    assert firefox_missing["source_adapter"] == "browser_extension_explicit"
    assert web_ext_missing["status"] == "web_ext_missing"
    assert web_ext_missing["policy"]["raw_keylogging"] is False
    assert called["probe"] is False


def test_browser_webextension_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    probe_text = f"abyss browser webextension committed text {run_id}"
    probe_hash = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    commands: list[tuple[list[str], float, dict[str, str] | None]] = []
    launched: list[list[str]] = []
    cleanup_tokens: list[str] = []

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return 0

        def communicate(self, timeout=0):
            return "web-ext stdout", "web-ext stderr"

    def fake_which(name: str) -> str | None:
        return {
            "firefox": "/usr/bin/firefox",
            "web-ext": "/usr/bin/web-ext",
        }.get(name)

    def fake_run(cmd: list[str], timeout: float, env: dict[str, str] | None) -> dict[str, object]:
        commands.append((cmd, timeout, env))
        return {"ok": True, "returncode": 0, "stdout": "8.0.0", "stderr": ""}

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_find_probe_event(text_sha256: str, limit: int):
        assert text_sha256 == probe_hash
        assert limit == 520
        return {
            "event_id": "evt-webextension",
            "generated_at": generated_at,
            "status": "captured",
            "source_adapter": "browser_extension_explicit",
            "capture_gate_decision": "allow_text",
            "capture_gate_confidence": "browser_url_and_field_allowed",
            "text_length": len(probe_text),
            "text_chars_stored": len(probe_text),
            "text_sha256": probe_hash,
            "recipient": {"kind": "browser_extension"},
        }, []

    def fake_terminate(token: str) -> list[dict[str, object]]:
        cleanup_tokens.append(token)
        return [{"token": token, "ok": True}]

    data = typing_browser_adapters.browser_webextension_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        extension_root=tmp_path / "extension",
        npm_cache=tmp_path / "npm",
        schema_prefix="abyss_machine",
        version="fixture-version",
        find_probe_event=fake_find_probe_event,
        which=fake_which,
        run_command=fake_run,
        process_factory=fake_process_factory,
        terminate_processes=fake_terminate,
        sleep=lambda _seconds: None,
        deadline_seconds=1.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["probe"] == {
        "text_sha256": probe_hash,
        "text_length": len(probe_text),
        "text_omitted": True,
    }
    assert data["event"]["event_id"] == "evt-webextension"
    assert "text" not in data["event"]
    assert data["policy"]["temporary_firefox_profile"] is True
    assert data["policy"]["release_profile_mutated"] is False
    assert data["policy"]["loopback_http_only"] is True
    assert data["web_ext"]["loader"]["route"] == "path"
    assert data["web_ext"]["version"] == "8.0.0"
    assert data["web_ext"]["cleanup_actions"] == [{"token": str(tmp_path / "tmp"), "ok": True}]
    assert commands[0][0] == ["/usr/bin/web-ext", "--version"]
    assert launched[0][:4] == ["/usr/bin/web-ext", "run", "--source-dir", str(tmp_path / "extension")]
    assert "--firefox-profile" in launched[0]
    assert str(tmp_path / "tmp" / "profile") in launched[0]
    assert cleanup_tokens == [str(tmp_path / "tmp")]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "index.html").exists()


def test_browser_context_selftest_reports_missing_firefox_without_live_probe(tmp_path) -> None:
    called = {"live": False}

    def forbidden_live_capture(**_kwargs: object) -> dict[str, object]:
        called["live"] = True
        return {}

    data = typing_browser_adapters.browser_context_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        events_policy={"max_age_sec": 30},
        focus_window_by_title=lambda *_args, **_kwargs: {},
        focus_metadata_by_url=lambda *_args, **_kwargs: {},
        live_content_capture=forbidden_live_capture,
        context_from_recent_atspi_path=lambda *_args, **_kwargs: {},
        which=lambda name: None,
    )

    assert data["status"] == "firefox_missing"
    assert data["policy"]["raw_keylogging"] is False
    assert called["live"] is False


def test_browser_context_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    launched: list[list[str]] = []
    runtime_env = {
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_APPS": "old",
        "KEEP": "1",
    }

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return 0

        def communicate(self, timeout=0):
            return "opened ?token=secret", "stderr ?client_secret=secret"

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_live_capture(**kwargs: object) -> dict[str, object]:
        assert kwargs == {"write_latest": True}
        url = launched[0][-1]
        return {
            "ok": True,
            "summary": {"captures": 1},
            "captures": [{
                "record": {
                    "captured_at": generated_at,
                    "title": "Abyss Writing Context",
                    "url": {"url": url},
                    "content_type": "text/html",
                    "text_length": 512,
                    "skipped_text": False,
                    "web_context_quality": {"class": "project_context"},
                    "content_quality": {"classification": "usable"},
                },
                "atspi": {
                    "path": "/application/firefox/document",
                    "role": "document",
                    "showing": True,
                    "visible": True,
                    "focused": True,
                },
            }],
        }

    def fake_context_from_path(
        source_path: str,
        document_path: str,
        events_policy: dict[str, object] | None,
        *,
        allow_attention_fallback: bool,
    ) -> dict[str, object]:
        assert source_path == "/application/firefox/document"
        assert document_path == "/application/firefox/document"
        assert events_policy == {"max_age_sec": 30}
        assert allow_attention_fallback is False
        return {
            "ok": True,
            "status": "matched",
            "url": launched[0][-1],
            "title": "Abyss Writing Context",
            "basis": "recent_browser_content",
        }

    data = typing_browser_adapters.browser_context_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        events_policy={"max_age_sec": 30},
        focus_window_by_title=lambda *_args, **_kwargs: {"ok": True, "_private": "hidden", "method": "title"},
        focus_metadata_by_url=lambda *_args, **_kwargs: {"ok": True, "_private": "hidden", "method": "url"},
        live_content_capture=fake_live_capture,
        context_from_recent_atspi_path=fake_context_from_path,
        natural_route_host=lambda: "127.0.0.1",
        url_origin=lambda url: {"origin": "http://127.0.0.1"},
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
        process_factory=fake_process_factory,
        sleep=lambda _seconds: None,
        monotonic=lambda: 100.0,
        env_mapping=runtime_env,
        deadline_seconds=1.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["capture"]["record"]["text_captured"] is True
    assert data["capture"]["record"]["content_quality_class"] == "usable"
    assert data["capture"]["atspi"]["path"] == "/application/firefox/document"
    assert "_private" not in data["capture"]["window_focus_attempt"]
    assert "_private" not in data["capture"]["focus_attempt"]
    assert data["inference"] == {"ok": True, "status": "matched", "basis": "recent_browser_content"}
    assert data["policy"]["temporary_firefox_profile"] is True
    assert data["policy"]["release_profile_mutated"] is False
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stdout_tail"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stderr_tail"]
    assert launched[0][:4] == ["/usr/bin/firefox", "--new-instance", "--profile", str(tmp_path / "tmp" / "profile")]
    assert launched[0][-2:] == ["--new-window", data["url"]]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "index.html").exists()
    assert runtime_env == {
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_APPS": "old",
        "KEEP": "1",
    }


def test_cli_browser_context_selftest_binds_adapter_to_latest_store(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T18:00:00Z")
    monkeypatch.setattr(cli, "TYPING_BROWSER_CONTEXT_SELFTEST_TMP_ROOT", tmp_path / "tmp")
    monkeypatch.setattr(cli, "typing_browser_context_selftest_store", lambda data, write_latest=True: {"stored": data, "write_latest": write_latest})
    monkeypatch.setattr(cli, "typing_policy", lambda write_latest=False: {"policy": True})
    monkeypatch.setattr(cli, "typing_atspi_text_events_policy", lambda policy: {"events_policy": policy})

    def fake_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "abyss_machine_typing_browser_context_selftest_v1", "ok": True}

    monkeypatch.setattr(typing_browser_adapters, "browser_context_selftest_document", fake_document)

    result = cli.typing_browser_context_selftest(write_latest=False)

    assert result["write_latest"] is False
    assert result["stored"]["ok"] is True
    assert captured["generated_at"] == "2026-06-27T18:00:00Z"
    assert captured["tmp_root"] == tmp_path / "tmp"
    assert captured["events_policy"] == {"events_policy": {"policy": True}}
    assert captured["focus_window_by_title"] is cli.typing_atspi_focus_firefox_frame_by_title
    assert captured["focus_metadata_by_url"] is cli.typing_atspi_focus_metadata_by_url
    assert captured["live_content_capture"] is cli.nervous_browser_live_content_capture
    assert captured["context_from_recent_atspi_path"] is cli.typing_browser_context_from_recent_atspi_path
    assert captured["natural_route_host"] is cli.typing_browser_atspi_natural_route_host
    assert captured["process_tail"] is cli.typing_safe_process_tail


def test_cli_browser_extension_ingest_executes_adapter_plan(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T00:00:00Z")
    monkeypatch.setattr(cli, "typing_browser_extension_store", lambda data, write_latest=True: data)

    def fake_ingest(text: str, **kwargs: object) -> dict[str, object]:
        captured["text"] = text
        captured.update(kwargs)
        return {
            "ok": True,
            "event_id": "evt-cli",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"text_length": len(text), "text_chars_stored": len(text)},
            "duplicate": False,
        }

    monkeypatch.setattr(cli, "typing_ingest", fake_ingest)

    result = cli.typing_browser_extension_ingest_message(
        {
            "event_kind": "committed_text",
            "browser_name": "firefox",
            "title": "Writing",
            "url": "https://example.test/write",
            "text": "cli fixture",
            "field": {"safe": True, "kind": "textarea", "type": "textarea"},
        },
        write_latest=False,
    )

    assert captured["text"] == "cli fixture"
    assert captured["source"] == "browser_extension_explicit"
    assert captured["write_latest"] is False
    assert captured["skip_duplicate"] is True
    assert result["schema"] == "abyss_machine_typing_browser_extension_status_v1"
    assert result["event"]["event_id"] == "evt-cli"
