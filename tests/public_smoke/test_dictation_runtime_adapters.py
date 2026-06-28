from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_runtime_adapters


def test_runtime_adapter_uses_xdg_runtime_dir_and_ensures_dictation_path(tmp_path: Path) -> None:
    ensured: list[Path] = []

    path = dictation_runtime_adapters.runtime_dir(
        {"XDG_RUNTIME_DIR": str(tmp_path / "run")},
        uid=1234,
        path_exists=lambda path: (_ for _ in ()).throw(AssertionError(path)),
        ensure_dir=ensured.append,
    )

    assert path == tmp_path / "run" / "abyss-machine" / "dictation"
    assert ensured == [path]


def test_runtime_adapter_falls_back_to_user_run_dir_or_tmp() -> None:
    user_run = Path("/run/user/1234")

    assert (
        dictation_runtime_adapters.runtime_root(
            {},
            uid=1234,
            path_exists=lambda path: path == user_run,
        )
        == user_run
    )
    assert (
        dictation_runtime_adapters.runtime_root(
            {},
            uid=1234,
            path_exists=lambda path: False,
        )
        == Path("/tmp")
    )


def test_runtime_adapter_resolves_socket_overrides_and_max_seconds(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    assert dictation_runtime_adapters.server_socket({}, runtime) == runtime / "server.sock"
    assert dictation_runtime_adapters.server_socket({"ABYSS_DICTATION_SERVER_SOCKET": "/tmp/custom.sock"}, runtime) == Path("/tmp/custom.sock")
    assert dictation_runtime_adapters.ydotool_socket({}, uid=1234) == Path("/run/user/1234/.ydotool_socket")
    assert dictation_runtime_adapters.ydotool_socket({"YDOTOOL_SOCKET": "/tmp/y.sock"}, uid=1234) == Path("/tmp/y.sock")
    assert dictation_runtime_adapters.max_seconds({"ABYSS_DICTATION_MAX_SECONDS": "9999"}, 180) == 3600
    assert dictation_runtime_adapters.max_seconds({"ABYSS_DICTATION_MAX_SECONDS": "0"}, 180) == 0
    assert dictation_runtime_adapters.max_seconds({"ABYSS_DICTATION_MAX_SECONDS": "bad"}, 180) == 180


def test_cli_dictation_runtime_binds_live_environment(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    runtime = tmp_path / "runtime" / "dictation"

    def fake_runtime_dir(env: object, **kwargs: object) -> Path:
        captured["runtime_env"] = env
        captured["runtime_kwargs"] = kwargs
        return runtime

    def fake_server_socket(env: object, runtime_dir_path: Path) -> Path:
        captured["server_env"] = env
        captured["server_runtime_dir"] = runtime_dir_path
        return runtime_dir_path / "server.sock"

    def fake_ydotool_socket(env: object, **kwargs: object) -> Path:
        captured["ydotool_env"] = env
        captured["ydotool_kwargs"] = kwargs
        return Path("/tmp/ydotool.sock")

    def fake_max_seconds(env: object, default: int) -> int:
        captured["max_env"] = env
        captured["max_default"] = default
        return 222

    monkeypatch.setattr(cli.os, "getuid", lambda: 4321)
    monkeypatch.setattr(dictation_runtime_adapters, "runtime_dir", fake_runtime_dir)
    monkeypatch.setattr(dictation_runtime_adapters, "server_socket", fake_server_socket)
    monkeypatch.setattr(dictation_runtime_adapters, "ydotool_socket", fake_ydotool_socket)
    monkeypatch.setattr(dictation_runtime_adapters, "max_seconds", fake_max_seconds)

    assert cli.dictation_runtime_dir() == runtime
    assert cli.dictation_server_socket() == runtime / "server.sock"
    assert cli.dictation_status_paths().ydotool_socket == Path("/tmp/ydotool.sock")
    assert cli.dictation_max_seconds() == 222

    assert captured["runtime_env"] is os.environ
    assert captured["runtime_kwargs"] == {"uid": 4321}
    assert captured["server_env"] is os.environ
    assert captured["server_runtime_dir"] == runtime
    assert captured["ydotool_env"] is os.environ
    assert captured["ydotool_kwargs"] == {"uid": 4321}
    assert captured["max_env"] is os.environ
    assert captured["max_default"] == cli.DICTATION_DEFAULT_MAX_SECONDS
