from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from . import typing_nervous_adapters


LatestReaderPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
PathExistsPort = Callable[[Path], bool]
DirectorySizePort = Callable[[Path], int]
FileCounterPort = Callable[[Path, str], int]


def path_exists(path: Path) -> bool:
    return path.exists()


def directory_size_bytes(path: Path) -> int:
    total = 0
    try:
        walker = os.walk(path)
        for current, _, filenames in walker:
            current_path = Path(current)
            for filename in filenames:
                try:
                    total += (current_path / filename).stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def count_files(root: Path, pattern: str) -> int:
    try:
        return sum(1 for path in root.rglob(pattern) if path.is_file())
    except OSError:
        return 0


def capture_status_document(
    *,
    capture_latest_path: Path,
    private_capture_root: Path,
    screenshot_root: Path,
    browser_content_root: Path,
    browser_content_latest_path: Path,
    browser_bidi_url: str,
    browser_tmp_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_reader: LatestReaderPort = typing_nervous_adapters.read_json_document,
    path_exists: PathExistsPort = path_exists,
    directory_size: DirectorySizePort = directory_size_bytes,
    file_counter: FileCounterPort = count_files,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(capture_latest_path)
    browser_content_latest, browser_content_error = latest_reader(browser_content_latest_path)

    screenshot_exists = path_exists(screenshot_root)
    browser_content_exists = path_exists(browser_content_root)
    private_root_exists = path_exists(private_capture_root)
    return {
        "schema": f"{schema_prefix}_nervous_capture_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": latest is not None,
        "latest": latest,
        "latest_error": latest_error,
        "browser_content_latest": browser_content_latest,
        "browser_content_latest_error": browser_content_error,
        "paths": {
            "latest": str(capture_latest_path),
            "private_root": str(private_capture_root),
            "screenshots": str(screenshot_root),
            "browser_content": str(browser_content_root),
            "browser_content_latest": str(browser_content_latest_path),
            "browser_bidi_url": browser_bidi_url,
            "browser_tmp": str(browser_tmp_root),
        },
        "storage": {
            "screenshots_count": file_counter(screenshot_root, "*.png") if screenshot_exists else 0,
            "screenshots_bytes": directory_size(screenshot_root) if screenshot_exists else 0,
            "browser_content_jsonl_files": file_counter(browser_content_root, "*.jsonl") if browser_content_exists else 0,
            "browser_content_bytes": directory_size(browser_content_root) if browser_content_exists else 0,
            "private_root_bytes": directory_size(private_capture_root) if private_root_exists else 0,
        },
        "controls": {
            "pause": "abyss-machine nervous privacy-set pause on --reason TEXT --json",
            "private_mode": "abyss-machine nervous privacy-set private-mode on --reason TEXT --json",
            "disable_source": "abyss-machine nervous source-disable SOURCE --reason TEXT --json",
            "forget": "abyss-machine nervous forget --minutes N --json",
        },
    }
