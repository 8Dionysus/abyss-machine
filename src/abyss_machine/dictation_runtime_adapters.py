from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from . import dictation_contracts


PathExists = Callable[[Path], bool]
EnsureDir = Callable[[Path], None]


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def runtime_root(
    env: Mapping[str, str],
    *,
    uid: int,
    path_exists: PathExists = Path.exists,
) -> Path:
    base = env.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base)
    candidate = Path(f"/run/user/{uid}")
    return candidate if path_exists(candidate) else Path("/tmp")


def runtime_dir(
    env: Mapping[str, str],
    *,
    uid: int,
    path_exists: PathExists = Path.exists,
    ensure_dir: EnsureDir = ensure_directory,
) -> Path:
    path = runtime_root(env, uid=uid, path_exists=path_exists) / "abyss-machine" / "dictation"
    ensure_dir(path)
    return path


def server_socket(env: Mapping[str, str], runtime_dir_path: Path) -> Path:
    return Path(env.get("ABYSS_DICTATION_SERVER_SOCKET", str(runtime_dir_path / "server.sock")))


def ydotool_socket(env: Mapping[str, str], *, uid: int) -> Path:
    return Path(env.get("YDOTOOL_SOCKET", f"/run/user/{uid}/.ydotool_socket"))


def max_seconds(env: Mapping[str, str], default: int) -> int:
    return dictation_contracts.max_seconds(env, default)
