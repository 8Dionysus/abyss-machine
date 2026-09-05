from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping

try:
    from . import storage_reservations
except ImportError:
    import storage_reservations  # type: ignore[no-redef]


UnitStatePort = Callable[[str], dict[str, Any]]
PidAlivePort = Callable[[int], bool]
RunPort = Callable[..., subprocess.CompletedProcess[str]]


def runtime_root(
    environ: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
    path_exists: Callable[[Path], bool] = Path.is_dir,
) -> Path:
    source = os.environ if environ is None else environ
    configured = source.get("XDG_RUNTIME_DIR")
    if configured:
        return Path(configured)
    resolved_uid = os.getuid() if uid is None else int(uid)
    candidate = Path(f"/run/user/{resolved_uid}")
    if path_exists(candidate):
        return candidate
    return Path(tempfile.gettempdir()) / f"abyss-machine-{resolved_uid}"


def reservations_root(
    environ: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
) -> Path:
    return runtime_root(environ, uid=uid) / "abyss-machine" / "resource" / "reservations"


def demand_profiles_path(
    environ: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
) -> Path:
    return runtime_root(environ, uid=uid) / "abyss-machine" / "resource" / "demand-profiles.json"


def admission_lock_path(root: Path) -> Path:
    return root.parent / "admission.lock"


@contextmanager
def admission_lock(root: Path) -> Iterable[None]:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = admission_lock_path(root)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def lease_filename(lease_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(lease_id)).strip("-.") or "lease"
    digest = hashlib.sha256(str(lease_id).encode("utf-8")).hexdigest()[:12]
    return f"{normalized[:80]}-{digest}.json"


def lease_path(root: Path, lease_id: str) -> Path:
    return root / lease_filename(lease_id)


def atomic_write_lease(root: Path, lease: dict[str, Any]) -> Path:
    lease_id = str(lease.get("id") or "")
    if not lease_id:
        raise ValueError("lease id is required")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = lease_path(root, lease_id)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(root))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lease, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination


def atomic_write_json(path: Path, document: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_demand_profiles(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        document = {}
    profiles = document.get("profiles") if isinstance(document, dict) else None
    return {
        "schema": "abyss_machine_resource_demand_profiles_v1",
        "runtime_only": True,
        "profiles": profiles if isinstance(profiles, dict) else {},
    }


def demand_profile(document: Mapping[str, Any], key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    profiles = document.get("profiles") if isinstance(document.get("profiles"), dict) else {}
    profile = profiles.get(key)
    return dict(profile) if isinstance(profile, dict) else None


def update_demand_profiles(
    document: Mapping[str, Any],
    *,
    key: str,
    owner: str,
    kind: str,
    memory_peak_mib: float,
    memory_swap_peak_mib: float,
    observed_at_epoch: float,
    execution_succeeded: bool | None = None,
    execution_returncode: int | None = None,
    requested_demand_mib: float | None = None,
    multiplier: float = 1.25,
    max_entries: int = 64,
    max_samples: int = 16,
) -> dict[str, Any]:
    profiles_source = document.get("profiles") if isinstance(document.get("profiles"), dict) else {}
    profiles = {str(name): dict(value) for name, value in profiles_source.items() if isinstance(value, dict)}
    profile = dict(profiles.get(key) or {})
    old_samples = profile.get("samples") if isinstance(profile.get("samples"), list) else []
    footprint_mib = max(0.0, float(memory_peak_mib)) + max(0.0, float(memory_swap_peak_mib))
    sample = {
        "observed_at_epoch": round(float(observed_at_epoch), 3),
        "memory_peak_mib": round(max(0.0, float(memory_peak_mib)), 3),
        "memory_swap_peak_mib": round(max(0.0, float(memory_swap_peak_mib)), 3),
        "footprint_peak_mib": round(footprint_mib, 3),
    }
    if execution_succeeded is not None:
        sample["execution_succeeded"] = bool(execution_succeeded)
    if execution_returncode is not None:
        sample["execution_returncode"] = int(execution_returncode)
    if requested_demand_mib is not None:
        sample["requested_demand_mib"] = round(max(0.0, float(requested_demand_mib)), 3)
    samples = [dict(item) for item in old_samples if isinstance(item, dict)] + [sample]
    samples = samples[-max(1, min(int(max_samples), 64)):]
    observed_max = max(float(item.get("footprint_peak_mib") or 0.0) for item in samples)
    failed_demand_floor = max(
        (
            float(item.get("requested_demand_mib") or 0.0)
            for item in samples
            if item.get("execution_succeeded") is False
        ),
        default=0.0,
    )
    observed_estimate = observed_max * max(1.0, float(multiplier))
    estimate_source = (
        "failed_execution_request_floor"
        if failed_demand_floor > observed_estimate
        else "runtime_observed_unit_peak"
    )
    profile.update(
        {
            "key": key,
            "owner": owner,
            "kind": kind,
            "updated_at_epoch": round(float(observed_at_epoch), 3),
            "sample_count": len(samples),
            "observed_max_mib": round(observed_max, 3),
            "failed_demand_floor_mib": round(failed_demand_floor, 3),
            "estimate_mib": round(max(observed_estimate, failed_demand_floor), 3),
            "estimate_source": estimate_source,
            "samples": samples,
        }
    )
    profiles[key] = profile
    bounded_entries = max(1, min(int(max_entries), 256))
    if len(profiles) > bounded_entries:
        ordered = sorted(profiles.items(), key=lambda item: float(item[1].get("updated_at_epoch") or 0.0), reverse=True)
        profiles = dict(ordered[:bounded_entries])
    return {
        "schema": "abyss_machine_resource_demand_profiles_v1",
        "runtime_only": True,
        "profiles": profiles,
    }


def record_demand_observation(
    path: Path,
    *,
    key: str,
    owner: str,
    kind: str,
    memory_peak_mib: float,
    memory_swap_peak_mib: float,
    observed_at_epoch: float,
    execution_succeeded: bool | None = None,
    execution_returncode: int | None = None,
    requested_demand_mib: float | None = None,
    multiplier: float = 1.25,
    max_entries: int = 64,
    max_samples: int = 16,
) -> dict[str, Any]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        updated = update_demand_profiles(
            load_demand_profiles(path),
            key=key,
            owner=owner,
            kind=kind,
            memory_peak_mib=memory_peak_mib,
            memory_swap_peak_mib=memory_swap_peak_mib,
            observed_at_epoch=observed_at_epoch,
            execution_succeeded=execution_succeeded,
            execution_returncode=execution_returncode,
            requested_demand_mib=requested_demand_mib,
            multiplier=multiplier,
            max_entries=max_entries,
            max_samples=max_samples,
        )
        atomic_write_json(path, updated)
        profile = demand_profile(updated, key) or {}
        return {"ok": True, "path": str(path), "profile": profile, "runtime_only": True}
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def journal_unit_resource_peaks(
    unit: str,
    *,
    since_epoch: float | None = None,
    run_port: RunPort = subprocess.run,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.:@\\-]+\.(?:service|scope)", str(unit or "")):
        return {"ok": False, "unit": unit, "error": "invalid_unit_identity"}
    try:
        command = ["journalctl", "--user", "--unit", unit]
        if since_epoch is not None:
            command.extend(["--since", f"@{max(0.0, float(since_epoch)):.6f}"])
        command.extend(["--output=json", "--no-pager", "--all", "--lines=128"])
        proc = run_port(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "unit": unit, "error": str(exc)}
    memory_peak = 0
    memory_swap_peak = 0
    matched_records = 0
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        record_unit = str(item.get("USER_UNIT") or item.get("_SYSTEMD_USER_UNIT") or "")
        if record_unit and record_unit != unit:
            continue
        found = False
        for key, current in (("MEMORY_PEAK", "memory"), ("MEMORY_SWAP_PEAK", "swap")):
            try:
                value = max(0, int(item.get(key) or 0))
            except (TypeError, ValueError):
                value = 0
            if value:
                found = True
                if current == "memory":
                    memory_peak = max(memory_peak, value)
                else:
                    memory_swap_peak = max(memory_swap_peak, value)
        if found:
            matched_records += 1
    return {
        "ok": proc.returncode == 0 and bool(memory_peak or memory_swap_peak),
        "source": "journal",
        "unit": unit,
        "memory_peak_bytes": memory_peak,
        "memory_swap_peak_bytes": memory_swap_peak,
        "memory_peak_mib": round(memory_peak / 1024.0 / 1024.0, 3),
        "memory_swap_peak_mib": round(memory_swap_peak / 1024.0 / 1024.0, 3),
        "footprint_peak_mib": round((memory_peak + memory_swap_peak) / 1024.0 / 1024.0, 3),
        "matched_records": matched_records,
        "returncode": proc.returncode,
        "error": proc.stderr.strip() or (None if memory_peak or memory_swap_peak else "resource_peak_not_found"),
    }


_SYSTEMD_SIZE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[KMGTPE]?)(?:i?B)?", re.IGNORECASE)


def _systemd_size_bytes(raw: str) -> int | None:
    match = _SYSTEMD_SIZE_RE.fullmatch(str(raw or "").strip())
    if match is None:
        return None
    exponent = {"": 0, "K": 1, "M": 2, "G": 3, "T": 4, "P": 5, "E": 6}[match.group("unit").upper()]
    return max(0, int(round(float(match.group("value")) * (1024**exponent))))


def _systemd_run_summary_resource_peaks(unit: str, summary: str | None) -> dict[str, Any]:
    size = r"\d+(?:\.\d+)?\s*[KMGTPE]?(?:i?B)?"
    match = re.fullmatch(
        rf"\s*(?P<memory>{size})(?:\s+\(swap:\s*(?P<swap>{size})\))?\s*",
        str(summary or ""),
        re.IGNORECASE,
    )
    memory_peak = _systemd_size_bytes(match.group("memory")) if match else None
    memory_swap_peak = _systemd_size_bytes(match.group("swap") or "0B") if match else None
    valid = memory_peak is not None and memory_swap_peak is not None
    memory_bytes = int(memory_peak or 0)
    swap_bytes = int(memory_swap_peak or 0)
    return {
        "ok": bool(valid and (memory_bytes or swap_bytes)),
        "source": "systemd_run_summary",
        "unit": unit,
        "memory_peak_bytes": memory_bytes,
        "memory_swap_peak_bytes": swap_bytes,
        "memory_peak_mib": round(memory_bytes / 1024.0 / 1024.0, 3),
        "memory_swap_peak_mib": round(swap_bytes / 1024.0 / 1024.0, 3),
        "footprint_peak_mib": round((memory_bytes + swap_bytes) / 1024.0 / 1024.0, 3),
        "raw": summary,
        "error": None if valid and (memory_bytes or swap_bytes) else "systemd_run_summary_peak_invalid",
    }


def remove_lease(root: Path, lease_id: str) -> bool:
    try:
        lease_path(root, lease_id).unlink()
        return True
    except FileNotFoundError:
        return False


def systemd_user_unit_cleanup(
    unit: str | None,
    *,
    run_port: RunPort | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "attempted": False,
        "unit": unit,
        "stop": None,
        "state": None,
        "kill": None,
        "error": None,
    }
    if not unit:
        data["error"] = "missing_unit"
        return data
    if shutil.which("systemctl") is None:
        data["error"] = "systemctl_not_found"
        return data

    runner = run_port or subprocess.run
    data["attempted"] = True
    try:
        stop_proc = runner(
            ["systemctl", "--user", "stop", unit],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        data["stop"] = {
            "returncode": stop_proc.returncode,
            "stdout_tail": stop_proc.stdout[-1000:],
            "stderr_tail": stop_proc.stderr[-1000:],
        }
        state_proc = runner(
            ["systemctl", "--user", "is-active", unit],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        state = state_proc.stdout.strip() or state_proc.stderr.strip()
        data["state"] = {
            "returncode": state_proc.returncode,
            "value": state,
            "stdout_tail": state_proc.stdout[-1000:],
            "stderr_tail": state_proc.stderr[-1000:],
        }
        if state in {"active", "activating", "deactivating"}:
            kill_proc = runner(
                ["systemctl", "--user", "kill", "--kill-whom=all", "--signal=KILL", unit],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False,
            )
            data["kill"] = {
                "returncode": kill_proc.returncode,
                "stdout_tail": kill_proc.stdout[-1000:],
                "stderr_tail": kill_proc.stderr[-1000:],
            }
    except (OSError, subprocess.TimeoutExpired) as exc:
        data["error"] = str(exc)
    return data


def _confirm_systemd_unit_terminal(
    unit: str,
    *,
    unit_state_port: UnitStatePort | None,
    source: str,
) -> dict[str, Any]:
    """Return terminal evidence without treating a timeout as completion."""
    normalized_unit = str(unit or "").strip()
    if not normalized_unit:
        return {
            "confirmed_terminal": False,
            "confirmation": "unit_identity_unavailable",
            "unit": None,
        }
    state_reader = unit_state_port or systemd_user_unit_state
    try:
        state = state_reader(normalized_unit)
    except Exception as exc:  # a failed probe is uncertainty, not completion
        return {
            "confirmed_terminal": False,
            "confirmation": "unit_state_probe_error",
            "unit": normalized_unit,
            "state_error": str(exc)[:500],
        }
    if not isinstance(state, Mapping):
        return {
            "confirmed_terminal": False,
            "confirmation": "unit_state_invalid",
            "unit": normalized_unit,
        }
    active = state.get("active") is True or str(state.get("state") or "") in {
        "active",
        "activating",
        "reloading",
        "deactivating",
    }
    state_name = str(state.get("state") or "").strip().lower()
    terminal_state = state_name in {
        "inactive",
        "failed",
        "dead",
        "exited",
        "missing",
        "not-found",
        "not_found",
        "gone",
    }
    # ``systemd_user_unit_state`` reports ``exists=False`` when its probe
    # itself fails.  A probe error or an unknown state is uncertainty, not
    # evidence that the workload has stopped.
    probe_error = state.get("error") or state.get("state_error")
    confirmed = bool(
        not probe_error
        and not active
        and (
            terminal_state
            or (
                state.get("exists") is False
                and state_name in {"missing", "not-found", "not_found", "gone"}
            )
        )
    )
    return {
        "confirmed_terminal": confirmed,
        "confirmation": source if confirmed else "unit_still_active_or_unknown",
        "unit": normalized_unit,
        "state": dict(state),
    }


def _release_storage_reservation(
    reservation: Mapping[str, Any] | None,
    reservation_root: Path | None,
    completion: Mapping[str, Any],
) -> dict[str, Any]:
    """Release only after terminal evidence; keep active state on uncertainty."""
    if not isinstance(reservation, Mapping):
        return {"requested": False, "ok": True, "decision": "not_requested"}
    reservation_id = str(reservation.get("reservation_id") or "").strip()
    if not reservation_id or reservation_root is None:
        return {
            "requested": True,
            "ok": False,
            "decision": "blocked",
            "error": "storage_reservation_identity_incomplete",
        }
    if completion.get("confirmed_terminal") is not True:
        return {
            "requested": True,
            "ok": True,
            "decision": "deferred_until_terminal",
            "release_pending": True,
            "reservation_id": reservation_id,
            "completion": dict(completion),
        }
    try:
        released = storage_reservations.release_reservation(
            Path(reservation_root),
            reservation_id,
            owner=(str(reservation.get("owner")) if reservation.get("owner") else None),
            execution_identity=(
                str(reservation.get("execution_identity"))
                if reservation.get("execution_identity")
                else None
            ),
        )
    except (OSError, TypeError, ValueError) as exc:
        return {
            "requested": True,
            "ok": False,
            "decision": "blocked",
            "error": "storage_reservation_release_error",
            "detail": str(exc)[:500],
            "reservation_id": reservation_id,
        }
    return {
        "requested": True,
        **released,
        "release_pending": not bool(released.get("ok")),
        "completion": dict(completion),
    }


def execute_systemd_launch(
    *,
    systemd_command: list[str],
    launch_unit: str | None,
    generated_unit: str | None,
    unit_type: str,
    timeout_sec: float,
    lease: Mapping[str, Any] | None,
    reservation_root: Path,
    demand_profile_path: Path,
    demand_key: str | None,
    demand_owner: str | None,
    kind: str,
    observed_peak_multiplier: float,
    profile_max_entries: int,
    profile_max_samples: int,
    parse_output: Callable[[str], dict[str, Any]],
    run_port: RunPort | None = None,
    unit_state_port: UnitStatePort | None = None,
    storage_reservation: Mapping[str, Any] | None = None,
    storage_reservation_root: Path | None = None,
) -> dict[str, Any]:
    runner = run_port or subprocess.run
    launch_started_epoch = time.time()
    started = time.monotonic()
    timeout_value = None if timeout_sec <= 0 else max(0.1, float(timeout_sec))
    if timeout_value is not None and unit_type != "scope":
        timeout_value += 5.0

    result: dict[str, Any]
    lease_released = False
    launch_completed = False
    completion: dict[str, Any] = {
        "confirmed_terminal": False,
        "confirmation": "unconfirmed",
        "unit": launch_unit,
    }
    try:
        proc = runner(
            systemd_command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_value,
            check=False,
        )
        combined = f"{proc.stdout}\n{proc.stderr}"
        launch_completed = True
        systemd_info = parse_output(combined)
        if launch_unit and not systemd_info.get("unit"):
            systemd_info["unit"] = launch_unit
        if generated_unit:
            systemd_info["generated_unit"] = generated_unit
        result = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
            "systemd": systemd_info,
        }
        completion["unit"] = systemd_info.get("unit") or launch_unit
        if unit_type != "scope":
            # The service launch command includes --wait, so a returned
            # subprocess means systemd has observed the unit's terminal
            # result, including a non-zero workload exit status.
            completion.update(
                {
                    "confirmed_terminal": True,
                    "confirmation": "systemd_run_wait",
                }
            )
        else:
            completion = _confirm_systemd_unit_terminal(
                str(completion.get("unit") or ""),
                unit_state_port=unit_state_port,
                source="scope_unit_state_after_run",
            )
    except FileNotFoundError:
        result = {
            "ok": False,
            "returncode": 127,
            "stdout_tail": "",
            "stderr_tail": "systemd-run not found",
            "systemd": {},
        }
        completion = {
            "confirmed_terminal": True,
            "confirmation": "systemd_runner_missing",
            "unit": None,
        }
    except OSError as exc:
        # subprocess.run raises before a systemd unit can be started for
        # invocation errors such as permission or resource failures.  Record
        # the failure as terminal so an acquired accounting lease cannot be
        # stranded when there is no runner process to finish it.
        result = {
            "ok": False,
            "returncode": 126,
            "stdout_tail": "",
            "stderr_tail": str(exc)[:4000],
            "systemd": {},
        }
        completion = {
            "confirmed_terminal": True,
            "confirmation": "systemd_runner_error",
            "unit": None,
            "error": str(exc)[:500],
        }
    except subprocess.TimeoutExpired as exc:
        stdout_tail = (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else ""
        stderr_tail = (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "timeout"
        parsed = parse_output(f"{stdout_tail}\n{stderr_tail}")
        cleanup_unit = parsed.get("unit") or launch_unit
        cleanup = systemd_user_unit_cleanup(cleanup_unit, run_port=runner)
        if cleanup_unit and not parsed.get("unit"):
            parsed["unit"] = cleanup_unit
        if generated_unit:
            parsed["generated_unit"] = generated_unit
        result = {
            "ok": False,
            "returncode": 124,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "systemd": parsed,
            "timeout_cleanup": cleanup,
        }
        completion = _confirm_systemd_unit_terminal(
            str(cleanup_unit or ""),
            unit_state_port=unit_state_port,
            source="timeout_cleanup_unit_state",
        )
    finally:
        if isinstance(lease, Mapping):
            lease_id = str(lease.get("id") or "")
            # The admission lease is the only durable indication that this
            # transient workload may still be consuming the admitted budget.
            # Keep it when terminal state is unknown so the next admission
            # cannot start concurrently with a unit that may still be alive.
            # The reservation accounting path below has the same fail-closed
            # rule, but is a separate storage reservation and must not be
            # conflated with this memory/admission lease.
            if completion.get("confirmed_terminal") is True:
                lease_released = remove_lease(reservation_root, lease_id) or not lease_path(reservation_root, lease_id).exists()

    result["completion"] = completion
    storage_reservation_release = _release_storage_reservation(
        storage_reservation,
        storage_reservation_root,
        completion,
    )
    result["storage_reservation_release"] = storage_reservation_release

    demand_observation: dict[str, Any] | None = None
    if launch_unit and unit_type == "service" and launch_completed:
        peaks = journal_unit_resource_peaks(launch_unit, since_epoch=launch_started_epoch)
        if not peaks.get("ok"):
            systemd_info = result.get("systemd") if isinstance(result.get("systemd"), Mapping) else {}
            summary_peaks = _systemd_run_summary_resource_peaks(
                launch_unit,
                str(systemd_info.get("memory_peak") or ""),
            )
            if summary_peaks.get("ok"):
                summary_peaks["journal_fallback"] = peaks
                peaks = summary_peaks
            else:
                peaks["summary_fallback"] = summary_peaks
        observation: dict[str, Any] = {
            "peaks": peaks,
            "recorded": False,
            "execution_succeeded": result.get("ok") is True,
            "execution_returncode": result.get("returncode"),
            "requested_demand_mib": lease.get("demand_mib") if isinstance(lease, Mapping) else None,
        }
        if peaks.get("ok") and demand_key:
            try:
                recorded = record_demand_observation(
                    demand_profile_path,
                    key=demand_key,
                    owner=str(demand_owner or kind),
                    kind=kind,
                    memory_peak_mib=float(peaks.get("memory_peak_mib") or 0.0),
                    memory_swap_peak_mib=float(peaks.get("memory_swap_peak_mib") or 0.0),
                    observed_at_epoch=time.time(),
                    execution_succeeded=result.get("ok") is True,
                    execution_returncode=int(result.get("returncode") or 0),
                    requested_demand_mib=(
                        float(lease.get("demand_mib"))
                        if isinstance(lease, Mapping) and lease.get("demand_mib") is not None
                        else None
                    ),
                    multiplier=observed_peak_multiplier,
                    max_entries=profile_max_entries,
                    max_samples=profile_max_samples,
                )
                observation.update({"recorded": True, "record": recorded})
            except (OSError, TypeError, ValueError) as exc:
                observation["error"] = str(exc)
        demand_observation = observation

    return {
        "elapsed_sec": round(time.monotonic() - started, 3),
        "execution": result,
        "lease_released": lease_released,
        "demand_observation": demand_observation,
        "completion": completion,
        "storage_reservation_release": storage_reservation_release,
    }


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def systemd_user_unit_state(unit: str) -> dict[str, Any]:
    if not unit:
        return {"exists": False, "active": False, "state": "missing", "memory_current_mib": 0.0}
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "show", unit, "--property=LoadState", "--property=ActiveState", "--property=MemoryCurrent"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exists": False, "active": False, "state": "unknown", "memory_current_mib": 0.0, "error": str(exc)}
    properties: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key] = value
    active_state = properties.get("ActiveState", "unknown")
    load_state = properties.get("LoadState", "not-found")
    raw_memory = properties.get("MemoryCurrent", "0")
    try:
        memory_current_mib = max(0.0, float(raw_memory) / 1024.0 / 1024.0)
    except (TypeError, ValueError):
        memory_current_mib = 0.0
    return {
        "exists": load_state not in {"", "not-found"},
        "active": active_state in {"active", "activating", "reloading"},
        "state": active_state,
        "load_state": load_state,
        "memory_current_mib": round(memory_current_mib, 3),
        "returncode": proc.returncode,
        "error": proc.stderr.strip() or None,
    }


def lease_status(
    lease: dict[str, Any],
    *,
    now_epoch: float,
    pid_alive_port: PidAlivePort = pid_alive,
    unit_state_port: UnitStatePort = systemd_user_unit_state,
) -> dict[str, Any]:
    lease_id = str(lease.get("id") or "")
    lease_kind = str(lease.get("lease_kind") or "startup")
    try:
        launcher_pid = int(lease.get("launcher_pid") or 0)
    except (TypeError, ValueError):
        launcher_pid = 0
    try:
        expires_at = float(lease.get("expires_at_epoch") or 0.0)
    except (TypeError, ValueError):
        expires_at = 0.0
    raw_demand = lease.get("demand_mib")
    demand_mib: float | None
    try:
        demand_mib = None if raw_demand is None else max(0.0, float(raw_demand))
    except (TypeError, ValueError):
        demand_mib = None
    launcher_alive = pid_alive_port(launcher_pid) if launcher_pid > 0 else False
    unit = str(lease.get("unit") or "")
    unit_state = unit_state_port(unit) if unit else {
        "exists": False,
        "active": False,
        "state": "pending",
        "memory_current_mib": 0.0,
    }
    unit_active = bool(unit_state.get("active"))
    expired = expires_at <= 0.0 or now_epoch >= expires_at
    runtime_cold_load = lease_kind == "runtime_cold_load"
    runtime_workload = lease_kind == "runtime_workload"
    runtime_lease = runtime_cold_load or runtime_workload
    runtime_identity_valid = bool(
        lease.get("owner")
        and lease.get("workload_id")
        and lease.get("request_id")
        and lease.get("request_digest")
        and lease.get("release_token_sha256")
    )
    try:
        owner_pid = int(lease.get("owner_pid") or 0)
    except (TypeError, ValueError):
        owner_pid = 0
    owner_alive = pid_alive_port(owner_pid) if owner_pid > 0 else False
    workload_identity_valid = runtime_identity_valid and owner_pid > 0 and bool(lease.get("owner_cgroup"))
    invalid = not lease_id or (not runtime_lease and launcher_pid <= 0) or (
        runtime_cold_load and not runtime_identity_valid
    ) or (runtime_workload and not workload_identity_valid)
    unknown_demand = bool(lease.get("unknown_demand")) or demand_mib is None
    startup_deadline_elapsed = not runtime_lease and expired and (unknown_demand or not unit_active)
    runtime_deadline_elapsed = runtime_cold_load and expired
    workload_deadline_elapsed = runtime_workload and expired
    workload_owner_gone = runtime_workload and not owner_alive
    stale = invalid or runtime_deadline_elapsed or startup_deadline_elapsed or (
        not runtime_lease and not launcher_alive and not unit_active
    ) or workload_deadline_elapsed or workload_owner_gone
    if invalid:
        stale_reason = "invalid_identity"
    elif runtime_deadline_elapsed:
        stale_reason = "runtime_lease_deadline_elapsed"
    elif workload_deadline_elapsed:
        stale_reason = "workload_lease_deadline_elapsed"
    elif workload_owner_gone:
        stale_reason = "workload_owner_gone"
    elif startup_deadline_elapsed:
        stale_reason = "startup_deadline_elapsed"
    elif not runtime_lease and not launcher_alive and not unit_active:
        stale_reason = "launcher_dead_and_unit_inactive"
    else:
        stale_reason = None
    materialized_mib = max(0.0, float(unit_state.get("memory_current_mib") or 0.0))
    outstanding_mib = None if demand_mib is None else max(0.0, demand_mib - materialized_mib)
    return {
        **lease,
        "launcher_alive": launcher_alive,
        "owner_alive": owner_alive if runtime_workload else None,
        "unit_state": unit_state,
        "phase": "cold_load" if runtime_cold_load else ("workload_active" if runtime_workload else ("active_unit" if unit_active else "startup")),
        "expired": expired,
        "stale": stale,
        "stale_reason": stale_reason,
        "demand_mib": demand_mib,
        "materialized_mib": round(materialized_mib, 3),
        "outstanding_mib": None if outstanding_mib is None else round(outstanding_mib, 3),
        "unknown_demand": unknown_demand,
    }


def reservation_snapshot(
    root: Path,
    *,
    cleanup: bool = False,
    cleanup_invalid: bool = True,
    now_epoch: float | None = None,
    pid_alive_port: PidAlivePort = pid_alive,
    unit_state_port: UnitStatePort = systemd_user_unit_state,
) -> dict[str, Any]:
    resolved_now = time.time() if now_epoch is None else float(now_epoch)
    items: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append({"path": str(path), "error": str(exc)})
                if cleanup and cleanup_invalid:
                    try:
                        path.unlink()
                        removed.append({"path": str(path), "reason": "invalid_json"})
                    except OSError:
                        pass
                continue
            if not isinstance(document, dict):
                errors.append({"path": str(path), "error": "lease_not_object"})
                continue
            status = lease_status(
                document,
                now_epoch=resolved_now,
                pid_alive_port=pid_alive_port,
                unit_state_port=unit_state_port,
            )
            status["path"] = str(path)
            if status.get("stale"):
                if cleanup:
                    try:
                        path.unlink()
                        removed.append({"id": status.get("id"), "path": str(path), "reason": status.get("stale_reason")})
                    except OSError as exc:
                        errors.append({"path": str(path), "error": str(exc)})
                continue
            items.append(status)
    outstanding_mib = sum(float(item.get("outstanding_mib") or 0.0) for item in items)
    unknown_count = sum(1 for item in items if item.get("unknown_demand"))
    return {
        "schema": "abyss_machine_resource_reservation_snapshot_v1",
        "ok": not errors,
        "root": str(root),
        "items": items,
        "removed": removed,
        "errors": errors,
        "summary": {
            "active_count": len(items),
            "known_count": len(items) - unknown_count,
            "unknown_count": unknown_count,
            "outstanding_mib": round(outstanding_mib, 3),
            "removed_count": len(removed),
            "error_count": len(errors),
        },
        "policy": {
            "runtime_only": True,
            "materialized_memory_not_double_counted": True,
            "no_process_mutation": True,
        },
    }
