from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_notifications_adapters


def test_notifications_enabled_honors_env_override_without_loading_config() -> None:
    def config_document() -> dict[str, object]:
        raise AssertionError("config should not be loaded when env override is present")

    assert dictation_notifications_adapters.notifications_enabled({"ABYSS_DICTATION_NOTIFY": "1"}, config_document) is True
    assert dictation_notifications_adapters.notifications_enabled({"ABYSS_DICTATION_NOTIFY": "off"}, config_document) is False


def test_notifications_enabled_uses_config_desktop_gate() -> None:
    assert (
        dictation_notifications_adapters.notifications_enabled(
            {},
            lambda: {"notifications": {"enabled": True, "desktop": True}},
        )
        is True
    )
    assert (
        dictation_notifications_adapters.notifications_enabled(
            {},
            lambda: {"notifications": {"enabled": True, "desktop": False}},
        )
        is False
    )
    assert dictation_notifications_adapters.notifications_enabled({}, lambda: {"notifications": "bad"}) is False
    assert dictation_notifications_adapters.notifications_enabled({}, lambda: (_ for _ in ()).throw(RuntimeError("bad config"))) is False


def test_notify_builds_command_and_uses_fakeable_spawn() -> None:
    calls: list[list[str]] = []

    sent = dictation_notifications_adapters.notify(
        "Abyss Dictation",
        "Текст распознан",
        4500,
        env={"ABYSS_DICTATION_NOTIFY": "true"},
        config_document=lambda: {},
        command_exists=lambda command: command == "notify-send",
        spawn=calls.append,
    )

    assert sent is True
    assert calls == [
        [
            "notify-send",
            "--app-name=abyss-machine",
            "--expire-time=4500",
            "Abyss Dictation",
            "Текст распознан",
        ]
    ]


def test_notify_skips_disabled_missing_command_and_spawn_errors() -> None:
    calls: list[list[str]] = []

    disabled = dictation_notifications_adapters.notify(
        "Abyss Dictation",
        env={"ABYSS_DICTATION_NOTIFY": "0"},
        config_document=lambda: {},
        command_exists=lambda command: True,
        spawn=calls.append,
    )
    missing = dictation_notifications_adapters.notify(
        "Abyss Dictation",
        env={"ABYSS_DICTATION_NOTIFY": "1"},
        config_document=lambda: {},
        command_exists=lambda command: False,
        spawn=calls.append,
    )
    failed = dictation_notifications_adapters.notify(
        "Abyss Dictation",
        env={"ABYSS_DICTATION_NOTIFY": "1"},
        config_document=lambda: {},
        command_exists=lambda command: True,
        spawn=lambda command: (_ for _ in ()).throw(OSError("no display")),
    )

    assert disabled is False
    assert missing is False
    assert failed is False
    assert calls == []


def test_cli_notification_enabled_binds_live_policy_port(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_enabled(env: object, config_document: object) -> bool:
        captured["env"] = env
        captured["config_document"] = config_document
        return True

    monkeypatch.setattr(dictation_notifications_adapters, "notifications_enabled", fake_enabled)

    assert cli.dictation_notifications_enabled() is True
    assert captured["env"] is cli.os.environ
    assert captured["config_document"] is cli.dictation_config


def test_cli_notify_binds_live_spawn_ports(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_notify(title: str, body: str, expire_ms: int, **kwargs: object) -> bool:
        captured["title"] = title
        captured["body"] = body
        captured["expire_ms"] = expire_ms
        captured.update(kwargs)
        return True

    monkeypatch.setattr(dictation_notifications_adapters, "notify", fake_notify)

    cli.notify("Abyss Dictation", "ready", 1200)

    assert captured["title"] == "Abyss Dictation"
    assert captured["body"] == "ready"
    assert captured["expire_ms"] == 1200
    assert captured["env"] is cli.os.environ
    assert captured["config_document"] is cli.dictation_config
    assert captured["command_exists"] is cli.command_exists
    assert captured["spawn"] is cli.spawn_notification
