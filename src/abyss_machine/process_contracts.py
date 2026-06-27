from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PROTECTED_CAPABILITY_ROLES = {"persistent_model", "persistent_ai_service", "operator_dictation"}
GAME_TEXT_MATCH_INSPECTION_COMMS = {
    "abyss-machine",
    "awk",
    "bash",
    "cat",
    "codex",
    "cut",
    "fd",
    "find",
    "fish",
    "grep",
    "head",
    "jq",
    "less",
    "pgrep",
    "python",
    "python3",
    "rg",
    "sed",
    "sh",
    "sort",
    "tail",
    "tr",
    "uniq",
    "watch",
    "xargs",
    "zsh",
}
WINDOWS_WINE_UTILITY_COMMS = {
    "conhost.exe",
    "explorer.exe",
    "plugplay.exe",
    "rpcss.exe",
    "services.exe",
    "svchost.exe",
    "wineboot.exe",
    "winedevice.exe",
}
GAME_STRONG_ACTIVE_PATTERNS = [
    r"\bgamescope\b",
    r"\bgamemoderun\b",
    r"\bgamemode-simulate-game\b",
    r"\blutris\b",
    r"\bheroic\b",
    r"\blegendary\b",
    r"\bumu-run\b",
    r"\bsteam_appid=",
    r"\bsteam_app_?[0-9]+\b",
    r"\bsteamapps/common\b",
    r"/steamapps/common/",
    r"/steamapps/compatdata/",
    r"\bdragon\s+age\b",
    r"\bdaorigins(?:\.exe)?\b",
    r"\bdragonage(?:origins)?(?:\.exe)?\b",
]
GAME_WINE_RUNTIME_PATTERNS = [
    r"\bwine(64|server|boot|cfg|preloader)?\b",
    r"/wine-preloader\b",
]
PROCESS_REGEX_MATCH_HEAD_CHARS = 32768
PROCESS_REGEX_MATCH_TAIL_CHARS = 32768
_REGEX_CACHE: dict[str, re.Pattern[str]] = {}
PROCESS_REGEX_CACHE = _REGEX_CACHE


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def text_haystack(*parts: Any) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def text_matches_any(patterns: list[str], text: str) -> bool:
    if not text:
        return False
    match_text = text
    match_limit = PROCESS_REGEX_MATCH_HEAD_CHARS + PROCESS_REGEX_MATCH_TAIL_CHARS
    if len(match_text) > match_limit:
        match_text = f"{match_text[:PROCESS_REGEX_MATCH_HEAD_CHARS]} {match_text[-PROCESS_REGEX_MATCH_TAIL_CHARS:]}"
    for pattern in patterns:
        compiled = _REGEX_CACHE.get(pattern)
        if compiled is None:
            compiled = re.compile(pattern)
            _REGEX_CACHE[pattern] = compiled
        if compiled.search(match_text):
            return True
    return False


def path_text_under_game_root(value: Any, game_roots: list[Any]) -> bool:
    text = str(value or "").lower().replace(" (deleted)", "").rstrip("/")
    if not text:
        return False
    for root in game_roots:
        root_text = str(root).lower().rstrip("/")
        if root_text and (text == root_text or text.startswith(root_text + "/")):
            return True
    return False


def has_strong_game_signal(text: str) -> bool:
    return text_matches_any(GAME_STRONG_ACTIVE_PATTERNS, text)


def has_wine_runtime_signal(text: str) -> bool:
    return text_matches_any(GAME_WINE_RUNTIME_PATTERNS, text)


def capability_role(cmdline: str, comm: str, cwd: str | None = None, exe: str | None = None) -> str:
    text = text_haystack(comm, cmdline, cwd, exe)
    comm_name = str(comm or "").strip().lower()
    if comm_name == "llama-server" or "/llama-server" in text or "/app/llama-server" in text:
        return "persistent_model"
    if comm_name == "ovms" or "openvino_model_server" in text or ("openvino" in text and "model_server" in text):
        return "persistent_model"
    if "uvicorn" in text and ("--port 5001" in text or "--port 5201" in text):
        return "persistent_ai_service"
    if "qwen" in text and "tts" in text and ("uvicorn" in text or "server" in text):
        return "persistent_ai_service"
    if "abyss-dictation" in text:
        return "operator_dictation"
    return "none"


def game_role(
    cmdline: str,
    comm: str,
    cwd: str | None = None,
    exe: str | None = None,
    *,
    game_roots: list[Any] | None = None,
) -> str:
    roots = game_roots or []
    text = text_haystack(comm, cmdline, cwd, exe)
    comm_name = str(comm or "").strip().lower()
    if path_text_under_game_root(cwd, roots) or path_text_under_game_root(exe, roots):
        return "active_game"

    strong_game_signal = has_strong_game_signal(text)
    wine_runtime_signal = has_wine_runtime_signal(text)
    generic_wine_utility = (
        wine_runtime_signal
        and not strong_game_signal
        and (
            comm_name in WINDOWS_WINE_UTILITY_COMMS
            or "/.local/share/bottles/bottles/" in text
            or "/bottles/runners/" in text
        )
    )
    if comm_name not in GAME_TEXT_MATCH_INSPECTION_COMMS and strong_game_signal and not generic_wine_utility:
        if "gamemoded" not in text:
            return "active_game"

    if any(re.search(pattern, text) for pattern in [r"\bgamemoded\b"]):
        return "game_service"

    platform_patterns = [
        r"\bsteam\b",
        r"\bsteamwebhelper\b",
        r"\bsteam-runtime",
        r"\bpressure-vessel\b",
        r"com\.valvesoftware\.steam",
    ]
    if any(re.search(pattern, text) for pattern in platform_patterns):
        return "game_platform"
    return "none"


def workload_hint(
    cmdline: str,
    comm: str,
    cwd: str | None = None,
    exe: str | None = None,
    *,
    game_roots: list[Any] | None = None,
) -> str:
    role = game_role(cmdline, comm, cwd, exe, game_roots=game_roots)
    if role == "active_game":
        return "game"
    if role == "game_platform":
        return "game_platform"
    if role == "game_service":
        return "game_service"
    cap_role = capability_role(cmdline, comm, cwd, exe)
    if cap_role in {"persistent_model", "persistent_ai_service"}:
        return "ai_runtime"
    if cap_role == "operator_dictation":
        return "abyss_machine"
    text = text_haystack(comm, cmdline, cwd, exe)
    if "abyss-machine" in text or "abyss-dictation" in text or "abyss-tts" in text:
        return "abyss_machine"
    if "openvino" in text or "whisper" in text or "qwen" in text or "torch" in text:
        return "ai_runtime"
    if "podman" in text or "conmon" in text or "containers" in text:
        return "container"
    if "chrome" in text or "chromium" in text or "firefox" in text or "playwright" in text:
        return "browser"
    if "code" in text or "codex" in text:
        return "development"
    return "normal"


def game_summary_entry(proc: dict[str, Any], *, game_roots: list[Any] | None = None) -> dict[str, Any]:
    role = proc.get("game_role") or game_role(
        str(proc.get("cmdline") or ""),
        str(proc.get("comm") or ""),
        proc.get("cwd"),
        proc.get("exe"),
        game_roots=game_roots,
    )
    return {
        "pid": proc.get("pid"),
        "ppid": proc.get("ppid"),
        "uid": proc.get("uid"),
        "name": proc.get("name"),
        "comm": proc.get("comm"),
        "workload_hint": proc.get("workload_hint"),
        "game_role": role,
        "vmrss_kib": proc.get("vmrss_kib"),
        "cpu_system_percent": proc.get("cpu_system_percent"),
        "cwd": proc.get("cwd"),
        "exe": proc.get("exe"),
        "cmdline": proc.get("cmdline"),
    }


def game_entries(processes: list[dict[str, Any]], *, top: int = 60, game_roots: list[Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    active_games: list[dict[str, Any]] = []
    platforms: list[dict[str, Any]] = []
    services: list[dict[str, Any]] = []
    for proc in processes:
        role = str(proc.get("game_role") or game_role(
            str(proc.get("cmdline") or ""),
            str(proc.get("comm") or ""),
            proc.get("cwd"),
            proc.get("exe"),
            game_roots=game_roots,
        ))
        entry = game_summary_entry({**proc, "game_role": role}, game_roots=game_roots)
        if role == "active_game":
            active_games.append(entry)
        elif role == "game_platform":
            platforms.append(entry)
        elif role == "game_service":
            services.append(entry)
    key = lambda item: (float(item.get("cpu_system_percent") or 0.0), int(item.get("vmrss_kib") or 0))
    return {
        "active_games": sorted(active_games, key=key, reverse=True)[:top],
        "platforms": sorted(platforms, key=key, reverse=True)[:top],
        "services": sorted(services, key=key, reverse=True)[:top],
    }


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    daily_paths: dict[str, Any],
) -> dict[str, Any]:
    root = Path(str(refs["root"]))
    return {
        "schema": _schema(schema_prefix, "process_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(root),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "index": str(refs["index"]),
        "latest": str(refs["latest"]),
        "snapshots_glob": str(Path(str(refs["snapshot_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "thermal_attribution": {
            "root": str(refs["thermal_attribution_root"]),
            "latest": str(refs["thermal_attribution_latest"]),
            "today": str(daily_paths["thermal_attribution_today"]),
            "daily_glob": str(Path(str(refs["thermal_attribution_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "thermal_plan": {
            "root": str(refs["thermal_plan_root"]),
            "latest": str(refs["thermal_plan_latest"]),
            "today": str(daily_paths["thermal_plan_today"]),
            "daily_glob": str(Path(str(refs["thermal_plan_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "desktop_compositor": {
            "root": str(refs["desktop_compositor_root"]),
            "latest": str(refs["desktop_compositor_latest"]),
            "today": str(daily_paths["desktop_compositor_today"]),
            "daily_glob": str(Path(str(refs["desktop_compositor_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "game_guard": {
            "root": str(refs["game_guard_root"]),
            "latest": str(refs["game_guard_latest"]),
            "today": str(daily_paths["game_guard_today"]),
            "daily_glob": str(Path(str(refs["game_guard_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "containers": {
            "root": str(refs["container_root"]),
            "latest": str(refs["container_latest"]),
            "today": str(daily_paths["container_today"]),
            "daily_glob": str(Path(str(refs["container_root"])) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "service": str(refs["service"]),
        "timer": str(refs["timer"]),
        "commands": {
            "paths": "abyss-machine processes paths --json",
            "latest": "abyss-machine processes latest --json",
            "snapshot": "abyss-machine processes snapshot --json",
            "game_guard": "abyss-machine processes game-guard --json",
            "containers": "abyss-machine processes containers --json",
            "thermal_attribution": "abyss-machine processes thermal-attribution --json",
            "thermal_plan": "abyss-machine processes thermal-plan --json",
            "desktop_compositor": "abyss-machine processes desktop-compositor --json",
        },
        "policy_contract": {
            "read_only_by_default": True,
            "mutates_existing_processes": False,
            "live_collectors_enabled_by_paths": False,
            "repo_mutation": False,
        },
    }


def latest_summary_document(*, path: str, latest: Any, error: Any) -> dict[str, Any]:
    if not isinstance(latest, dict):
        return {"ok": False, "path": path, "error": error or "missing"}
    return {
        "ok": True,
        "path": path,
        "generated_at": latest.get("generated_at"),
        "summary": latest.get("summary"),
    }


def latest_read_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    path: str,
    latest: Any,
    error: Any,
) -> dict[str, Any]:
    if not isinstance(latest, dict):
        return {
            "schema": _schema(schema_prefix, "process_latest_read_v1"),
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "path": path,
            "error": error or "missing",
        }
    data = dict(latest)
    data["read_schema"] = _schema(schema_prefix, "process_latest_read_v1")
    data["ok"] = data.get("ok", True)
    return data


def game_guard_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    entries: dict[str, list[dict[str, Any]]],
    inaccessible: int,
    source: str,
    gamemode: dict[str, Any],
    protected_roots: list[dict[str, Any]],
    latest_path: str,
    daily_glob: str,
) -> dict[str, Any]:
    active = bool(entries["active_games"])
    return {
        "schema": _schema(schema_prefix, "process_game_guard_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "active": active,
        "platform_present": bool(entries["platforms"]),
        "summary": {
            "active_game_processes": len(entries["active_games"]),
            "game_platform_processes": len(entries["platforms"]),
            "game_service_processes": len(entries["services"]),
            "inaccessible_or_exited": inaccessible,
            "gamemode_available": gamemode.get("available"),
            "gamemode_global_active": gamemode.get("global_active"),
            "protected_roots_existing": sum(1 for root in protected_roots if root.get("exists")),
        },
        "capture": {
            "source": source,
            "facts_only": True,
            "interval_sec": 0,
        },
        "active_games": entries["active_games"],
        "platforms": entries["platforms"],
        "services": entries["services"],
        "gamemode": gamemode,
        "protected_roots": protected_roots,
        "routing_policy": {
            "automation": "protect_active_games_by_gating_new_competing_work",
            "do_not_change_existing_game_process_affinity": True,
            "do_not_kill_or_throttle_games": True,
            "do_not_clean_or_write_game_roots": True,
            "steam_client_alone_is_platform_not_active_game": True,
            "when_active": {
                "block_default_heavy_and_sustained_ai_launches": True,
                "block_unattended_medium_or_heavier_launches": True,
                "allow_light_interactive_operator_work": True,
                "operator_force_override_supported": True,
            },
        },
        "commands": {
            "guard": "abyss-machine processes game-guard --json",
            "game_mode_status": "gamemoded -s",
            "run_game_with_gamemode": "gamemoderun COMMAND...",
            "steam_launch_option": "gamemoderun %command%",
        },
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
        "non_claims": [
            "This guard does not prove that no game exists outside accessible /proc data.",
            "Steam client/helper processes alone are platform context and do not mean an active game is running.",
            "Generic Wine/Bottles utility processes alone are not active-game evidence without a strong game signal.",
            "This guard only gates new launches through abyss-machine; it does not mutate running games.",
        ],
    }


def snapshot_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    top: int,
    interval: float,
    system: dict[str, Any],
    processes: list[dict[str, Any]],
    inaccessible: int,
) -> dict[str, Any]:
    top_rss = sorted(processes, key=lambda item: int(item.get("vmrss_kib") or 0), reverse=True)[:top]
    cpu_key = "cpu_system_percent" if interval > 0 else "cpu_time_sec"
    top_cpu = sorted(processes, key=lambda item: float(item.get(cpu_key) or 0.0), reverse=True)[:top]
    top_io_read = sorted(processes, key=lambda item: int(item.get("io", {}).get("read_bytes") or 0), reverse=True)[:top]
    top_io_write = sorted(processes, key=lambda item: int(item.get("io", {}).get("write_bytes") or 0), reverse=True)[:top]
    interesting = [
        item for item in processes
        if item.get("storage_matches")
        or item.get("capability_role") in PROTECTED_CAPABILITY_ROLES
        or item.get("workload_hint") in {"abyss_machine", "ai_runtime", "container", "development", "game", "game_platform", "game_service"}
    ][:top]
    return {
        "schema": _schema(schema_prefix, "process_snapshot_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "paths": paths,
        "capture": {
            "source": "/proc",
            "interval_sec": interval,
            "top_limit": top,
            "facts_only": True,
        },
        "system": system,
        "summary": {
            "processes": len(processes),
            "threads": sum(int(item.get("threads") or 0) for item in processes),
            "inaccessible_or_exited": inaccessible,
            "rss_total_kib": sum(int(item.get("vmrss_kib") or 0) for item in processes),
            "storage_matched_processes": sum(1 for item in processes if item.get("storage_matches")),
            "ai_runtime_processes": sum(1 for item in processes if item.get("workload_hint") == "ai_runtime"),
            "persistent_model_processes": sum(1 for item in processes if item.get("capability_role") == "persistent_model"),
            "persistent_ai_service_processes": sum(1 for item in processes if item.get("capability_role") == "persistent_ai_service"),
            "operator_dictation_processes": sum(1 for item in processes if item.get("capability_role") == "operator_dictation"),
            "protected_capability_processes": sum(1 for item in processes if item.get("capability_role") in PROTECTED_CAPABILITY_ROLES),
            "container_processes": sum(1 for item in processes if item.get("workload_hint") == "container"),
            "development_processes": sum(1 for item in processes if item.get("workload_hint") == "development"),
            "game_processes": sum(1 for item in processes if item.get("workload_hint") == "game"),
            "game_platform_processes": sum(1 for item in processes if item.get("workload_hint") == "game_platform"),
            "game_service_processes": sum(1 for item in processes if item.get("workload_hint") == "game_service"),
        },
        "top": {
            "rss": top_rss,
            "cpu": top_cpu,
            "io_read": top_io_read,
            "io_write": top_io_write,
            "storage_or_workload": interesting,
        },
        "processes": sorted(processes, key=lambda item: int(item.get("pid") or 0)),
        "non_claims": [
            "This is a point-in-time /proc snapshot, not exclusive attribution to a workload.",
            "CPU percent is only included when an interval sample is requested.",
        ],
    }
