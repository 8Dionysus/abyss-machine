"""Bounded filesystem allocation health and independent emergency delivery.

Signals only: never balances, deletes, or stops workloads.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

GIB = 1024**3
MIB = 1024**2


def btrfs_allocation(root: Path) -> dict:
    """Read kernel accounting, including reservations absent from statvfs."""
    def number(path: Path) -> int:
        value = int(path.read_text().strip())
        if value < 0:
            raise ValueError("negative_btrfs_counter")
        return value

    allocation = root / "allocation"
    meta = allocation / "metadata"
    total = number(meta / "total_bytes")
    used = number(meta / "bytes_used")
    committed = sum(number(meta / key) for key in (
        "bytes_reserved", "bytes_pinned", "bytes_may_use", "bytes_readonly"))
    chunk = number(meta / "chunk_size")
    physical = sum(number(allocation / kind / "disk_total")
                   for kind in ("data", "metadata", "system"))
    devices = list((root / "devices").iterdir())
    if not devices or not total or not chunk:
        raise ValueError("incomplete_btrfs_accounting")
    device_bytes = sum(number(device / "size") * 512 for device in devices)
    unallocated = max(0, device_bytes - physical)
    headroom = max(0, total - used - committed)
    # Allocation headroom is an upper bound on multi-device/profile feasibility.
    tight = unallocated < max(2 * GIB, 2 * chunk)
    status = "ok"
    if tight and headroom < max(256 * MIB, total // 20):
        status = "critical"
    elif tight and (headroom < chunk or used * 100 >= total * 70):
        status = "warning"
    return {
        "status": status, "filesystem": "btrfs", "device_count": len(devices),
        "device_bytes": device_bytes, "allocated_device_bytes": physical,
        "unallocated_device_bytes": unallocated, "metadata_total_bytes": total,
        "metadata_used_bytes": used, "metadata_reserved_and_pending_bytes": committed,
        "metadata_headroom_bytes": headroom, "metadata_chunk_bytes": chunk,
        "reason": "btrfs_allocation_headroom_low" if status != "ok" else None,
        "automatic_remediation": False,
    }


def measure(path: Path) -> dict:
    try:
        result = subprocess.run(
            ["findmnt", "--json", "--output", "FSTYPE,UUID", "--target", str(path)],
            capture_output=True, text=True, timeout=2, check=True,
        )
        fs = json.loads(result.stdout)["filesystems"][0]
        if fs["fstype"] != "btrfs":
            return {"status": "not_applicable", "filesystem": fs["fstype"]}
        uuid = fs.get("uuid", "")
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", uuid):
            raise ValueError("btrfs_uuid_unavailable")
        return btrfs_allocation(Path("/sys/fs/btrfs") / uuid)
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
        return {"status": "unknown", "reason": "filesystem_health_unavailable", "error": str(exc)[:200]}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".health-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish(document: dict, *, runtime_root: Path, emergency_root: Path,
            notify: bool = True) -> dict:
    """Deliver before normal stdout/state writes; retain the last incident."""
    issues = []
    for row in document.get("roots", []):
        health = row.get("filesystem_health", {})
        if health.get("status") in {"critical", "warning", "unknown"}:
            issues.append({"path": row.get("path"), **health})
    if not document.get("ok"):
        write_failed = document.get("errno") in {errno.ENOSPC, errno.EDQUOT, errno.EROFS}
        issues.append({"status": "critical" if write_failed else "warning",
                       "reason": "capacity_state_write_failed" if write_failed else "capacity_observation_failed",
                       "errno": document.get("errno"), "error": document.get("error")})
    level = "critical" if any(x["status"] == "critical" for x in issues) else "warning" if issues else "ok"
    event = {"schema": "abyss_machine_storage_health_v1", "timestamp": time.time(),
             "severity": level, "issues": issues, "automatic_remediation": False}
    failures = []
    try:
        atomic_json(runtime_root / "latest.json", event)
    except OSError as exc:
        failures.append({"channel": "runtime", "errno": exc.errno})
    if issues:
        # Journal/desktop and each storage sink are independent of each other.
        print("ABYSS_STORAGE_HEALTH " + json.dumps(event, ensure_ascii=False), file=sys.stderr)
        key = [(x.get("path"), x.get("reason"), x["status"]) for x in issues]
        def due(path: Path) -> bool:
            try:
                previous = json.loads(path.read_text())
                old_key = [(x.get("path"), x.get("reason"), x["status"]) for x in previous.get("issues", [])]
                return key != old_key or event["timestamp"] - previous.get("timestamp", 0) >= 900
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                return True

        # Each sink throttles only its own successful delivery. A failed sink is
        # retried on the next observation, even if another sink succeeded.
        for channel, target in (("runtime", runtime_root), ("independent_disk", emergency_root)):
            try:
                if due(target / "last-alert.json"):
                    atomic_json(target / "last-alert.json", event)
            except OSError as exc:
                failures.append({"channel": channel, "errno": exc.errno})
        if notify and due(runtime_root / "desktop-delivered.json"):
            if any(x["reason"] == "capacity_state_write_failed" for x in issues):
                title = "Не удаётся сохранить данные"
                body = "Не удалось записать состояние контроля диска. Файловая система сообщает об отказе записи."
            elif any(x["reason"] == "btrfs_allocation_headroom_low" for x in issues):
                title = "Недостаточно резерва файловой системы"
                body = "Под угрозой сохранение данных на разделе /."
            else:
                title = "Не удалось проверить состояние диска"
                body = "Контроль диска завершился с ошибкой. Сведения о возможности сохранения данных могут быть неполными."
            try:
                subprocess.run(["notify-send", "--app-name=abyss-machine", "--urgency=critical",
                                title, body], capture_output=True, timeout=2, check=True)
                atomic_json(runtime_root / "desktop-delivered.json", event)
            except (OSError, subprocess.SubprocessError) as exc:
                failures.append({"channel": "desktop", "error": str(exc)[:150]})
    return {"severity": level, "issues": issues, "delivery_errors": failures,
            "runtime_path": str(runtime_root / "latest.json"),
            "last_alert_path": str(emergency_root / "last-alert.json")}
