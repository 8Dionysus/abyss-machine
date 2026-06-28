from __future__ import annotations

from typing import Any, Callable, Mapping

from . import dictation_contracts


ConfigDocument = Callable[[], dict[str, Any]]
CommandExists = Callable[[str], bool]
Spawn = Callable[[list[str]], None]


def notifications_enabled(env: Mapping[str, str], config_document: ConfigDocument) -> bool:
    raw = env.get("ABYSS_DICTATION_NOTIFY")
    if raw is not None:
        return raw.lower() not in {"0", "false", "no", "off"}
    try:
        settings = config_document().get("notifications", {})
    except Exception:
        return False
    if not isinstance(settings, dict):
        return False
    return dictation_contracts.bool_value(settings.get("enabled"), False) and dictation_contracts.bool_value(settings.get("desktop"), False)


def notify_send_command(title: str, body: str = "", expire_ms: int = 2500) -> list[str]:
    command = ["notify-send", "--app-name=abyss-machine", f"--expire-time={int(expire_ms)}", title]
    if body:
        command.append(body)
    return command


def notify(
    title: str,
    body: str = "",
    expire_ms: int = 2500,
    *,
    env: Mapping[str, str],
    config_document: ConfigDocument,
    command_exists: CommandExists,
    spawn: Spawn,
) -> bool:
    if not notifications_enabled(env, config_document):
        return False
    if not command_exists("notify-send"):
        return False
    try:
        spawn(notify_send_command(title, body, expire_ms))
    except OSError:
        return False
    return True
