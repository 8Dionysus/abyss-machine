"""Bounded capacity observations; forecasts are evidence, never write admission."""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any

MAX_SAMPLES = 168
MAX_STATE_BYTES = 256 * 1024
WINDOW_SECONDS = 7 * 86400
MIN_SPAN_SECONDS = 3 * 3600
SAMPLE_INTERVAL_SECONDS = 1800
FREE_FLOOR_BYTES = 5 * 1024**3


def forecast(samples: list[dict[str, Any]], current: dict[str, Any]) -> dict[str, Any]:
    """Extrapolate capacity on one unchanged filesystem.

    ``net_bytes_per_day`` remains the historical available-endpoint metric.
    When every retained sample includes ``reserved_bytes``, the depletion
    decision and headroom use physical free space (available plus reserved)
    while holding the current reserve policy fixed. Missing historical reserve
    values stay on the legacy basis; they are never treated as zero.
    """
    result = {
        "path": current["path"],
        "filesystem_key": current.get("filesystem_key"),
        "available_to_user_bytes": current.get("available_to_user_bytes"),
        "free_floor_bytes": FREE_FLOOR_BYTES,
        "status": "insufficient_history",
        "net_bytes_per_day": None,
        "net_physical_free_consumed_bytes": None,
        "net_physical_free_consumption_bytes_per_day": None,
        "reserve_shift_bytes": None,
        "physical_free_bytes": None,
        "forecast_basis": "legacy_available_to_user",
        "hours_to_free_floor": None,
        "hours_to_full": None,
        "method": "constant_net_rate_extrapolation_not_deadline",
    }
    if current.get("error"):
        return {**result, "status": "measurement_error", "error": current["error"]}
    now = current["timestamp"]
    by_time = {
        row["timestamp"]: row
        for row in samples
        if row.get("path") == current["path"]
        and row.get("filesystem_key") == current["filesystem_key"]
        and isinstance(row.get("timestamp"), (int, float))
        and 0 <= now - row["timestamp"] <= WINDOW_SECONDS
        and isinstance(row.get("available_to_user_bytes"), int)
        and not row.get("error")
    }
    by_time[now] = current
    rows = [by_time[key] for key in sorted(by_time)][-MAX_SAMPLES:]
    span = now - rows[0]["timestamp"]
    result.update(sample_count=len(rows), window_seconds=span)
    if len(rows) < 4 or span < MIN_SPAN_SECONDS:
        return result
    # Include cleanup in the net rate rather than calling reclaimed bytes growth.
    rate = (rows[0]["available_to_user_bytes"] - current["available_to_user_bytes"]) / span
    result["net_bytes_per_day"] = round(rate * 86400)

    reserve_values = [row.get("reserved_bytes") for row in rows]
    has_reserve_history = all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in reserve_values
    )
    physical_rate = rate
    if has_reserve_history:
        first_physical_free = rows[0]["available_to_user_bytes"] + reserve_values[0]
        current_physical_free = current["available_to_user_bytes"] + reserve_values[-1]
        physical_rate = (first_physical_free - current_physical_free) / span
        result.update(
            forecast_basis="physical_free_fixed_reserve",
            method="constant_physical_free_consumption_fixed_reserve_extrapolation_not_deadline",
            net_physical_free_consumed_bytes=first_physical_free - current_physical_free,
            net_physical_free_consumption_bytes_per_day=round(physical_rate * 86400),
            reserve_shift_bytes=reserve_values[-1] - reserve_values[0],
            physical_free_bytes=current_physical_free,
        )
    else:
        result["forecast_basis"] = "legacy_available_to_user_missing_reserved_bytes"

    if physical_rate <= 0:
        result["status"] = "not_depleting_in_observed_window"
        return result
    available = current["available_to_user_bytes"]
    result.update(
        status="depleting",
        hours_to_free_floor=round(max(0, available - FREE_FLOOR_BYTES) / physical_rate / 3600, 2),
        hours_to_full=round(available / physical_rate / 3600, 2),
    )
    return result


def _measure(path: Path, timestamp: float) -> dict[str, Any]:
    row: dict[str, Any] = {"path": str(path), "timestamp": timestamp}
    try:
        if not path.is_mount():
            raise OSError("expected_capacity_mount_missing")
        st = path.stat()
        capacity = os.statvfs(path)
        total = capacity.f_frsize * capacity.f_blocks
        row.update(
            filesystem_key=f"{st.st_dev}:{capacity.f_fsid}:{total}",
            total_bytes=total,
            available_to_user_bytes=capacity.f_frsize * capacity.f_bavail,
            reserved_bytes=capacity.f_frsize * (capacity.f_bfree - capacity.f_bavail),
        )
    except OSError as exc:
        row["error"] = str(exc)[:300]
    return row


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError("capacity_state_invalid_or_over_budget")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "abyss_machine_capacity_samples_v1":
        raise ValueError("capacity_state_schema_invalid")
    rows = document.get("samples")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("capacity_state_samples_invalid")
    return rows


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".capacity-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"schema": "abyss_machine_capacity_samples_v1", "samples": rows}, handle)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def observe(state_path: Path, *, paths: tuple[Path, ...], write: bool = True) -> dict[str, Any]:
    timestamp = dt.datetime.now(dt.timezone.utc).timestamp()
    current = [_measure(path, timestamp) for path in paths]
    lock = None
    try:
        if write:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            lock = open(state_path.with_suffix(".lock"), "a", encoding="utf-8")
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = _load(state_path)
        forecasts = [forecast(rows, row) for row in current]
        if write and not any(row.get("error") for row in current):
            retained = []
            for row in current:
                if row.get("error"):
                    # Failed acquisition is not a zero-byte measurement.
                    continue
                prior = [
                    old for old in rows
                    if old.get("path") == row["path"]
                    and old.get("filesystem_key") == row["filesystem_key"]
                    and isinstance(old.get("timestamp"), (int, float))
                    and 0 <= timestamp - old["timestamp"] <= WINDOW_SECONDS
                ]
                prior.sort(key=lambda item: item["timestamp"])
                if not prior or timestamp - prior[-1]["timestamp"] >= SAMPLE_INTERVAL_SECONDS:
                    prior.append(row)
                retained.extend(prior[-MAX_SAMPLES:])
            _write(state_path, retained)
        return {
            "ok": not any(row.get("error") for row in current),
            "generated_at": dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat(),
            "roots": forecasts,
            "history_limit_per_root": MAX_SAMPLES,
            "history_window_seconds": WINDOW_SECONDS,
            "minimum_span_seconds": MIN_SPAN_SECONDS,
            "basis": "statvfs_user_available_bytes",
            "automatic_deletion": False,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"ok": False, "status": "history_unavailable", "error": str(exc)[:300], "roots": current}
    finally:
        if lock is not None:
            lock.close()
