from __future__ import annotations

from contextlib import contextmanager
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_lock_adapters


def test_file_lock_creates_and_releases_lock_file(tmp_path: Path) -> None:
    lock_path = tmp_path / "dictation.lock"

    with dictation_lock_adapters.dictation_lock(lock_path, timeout_sec=0.1):
        assert lock_path.exists()

    with dictation_lock_adapters.dictation_lock(lock_path, timeout_sec=0.1):
        assert lock_path.exists()


def test_file_lock_times_out_when_another_process_holds_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "dictation.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys, time;"
                "fd=os.open(sys.argv[1], os.O_CREAT|os.O_RDWR, 0o600);"
                "fcntl.flock(fd, fcntl.LOCK_EX);"
                "print('ready', flush=True);"
                "time.sleep(0.35);"
                "fcntl.flock(fd, fcntl.LOCK_UN);"
                "os.close(fd)"
            ),
            str(lock_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "ready"
        with pytest.raises(TimeoutError, match="dictation is busy"):
            with dictation_lock_adapters.dictation_lock(lock_path, timeout_sec=0.05):
                pass
    finally:
        holder.wait(timeout=2.0)
        assert holder.returncode == 0


def test_completion_lock_uses_completion_busy_message(tmp_path: Path) -> None:
    lock_path = tmp_path / "completion.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys, time;"
                "fd=os.open(sys.argv[1], os.O_CREAT|os.O_RDWR, 0o600);"
                "fcntl.flock(fd, fcntl.LOCK_EX);"
                "print('ready', flush=True);"
                "time.sleep(0.35);"
                "fcntl.flock(fd, fcntl.LOCK_UN);"
                "os.close(fd)"
            ),
            str(lock_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "ready"
        with pytest.raises(TimeoutError, match="dictation completion is busy"):
            with dictation_lock_adapters.completion_lock(lock_path, timeout_sec=0.05):
                pass
    finally:
        holder.wait(timeout=2.0)
        assert holder.returncode == 0


def test_cli_dictation_lock_binds_path_and_timeout(monkeypatch, tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime" / "dictation.lock"
    captured: dict[str, object] = {}

    @contextmanager
    def fake_lock(path: Path, timeout_sec: float):
        captured["path"] = path
        captured["timeout_sec"] = timeout_sec
        yield

    monkeypatch.setattr(cli, "dictation_lock_file", lambda: lock_path)
    monkeypatch.setattr(dictation_lock_adapters, "dictation_lock", fake_lock)

    with cli.dictation_lock(timeout_sec=1.5):
        captured["entered"] = True

    assert captured["path"] == lock_path
    assert captured["timeout_sec"] == 1.5
    assert captured["entered"] is True


def test_cli_completion_lock_binds_path_and_timeout(monkeypatch, tmp_path: Path) -> None:
    lock_path = tmp_path / "runtime" / "completion.lock"
    captured: dict[str, object] = {}

    @contextmanager
    def fake_lock(path: Path, timeout_sec: float):
        captured["path"] = path
        captured["timeout_sec"] = timeout_sec
        yield

    monkeypatch.setattr(cli, "dictation_completion_lock_file", lambda: lock_path)
    monkeypatch.setattr(dictation_lock_adapters, "completion_lock", fake_lock)

    with cli.dictation_completion_lock(timeout_sec=2.5):
        captured["entered"] = True

    assert captured["path"] == lock_path
    assert captured["timeout_sec"] == 2.5
    assert captured["entered"] is True
