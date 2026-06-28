from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import time
from typing import Iterator


@contextmanager
def file_lock(
    path: Path,
    *,
    timeout_sec: float,
    busy_message: str,
    poll_interval: float,
) -> Iterator[None]:
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.time() + timeout_sec
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    raise TimeoutError(busy_message)
                time.sleep(poll_interval)
        yield
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def dictation_lock(path: Path, timeout_sec: float = 0.25):
    return file_lock(
        path,
        timeout_sec=timeout_sec,
        busy_message="dictation is busy",
        poll_interval=0.025,
    )


def completion_lock(path: Path, timeout_sec: float = 900.0):
    return file_lock(
        path,
        timeout_sec=timeout_sec,
        busy_message="dictation completion is busy",
        poll_interval=0.05,
    )
