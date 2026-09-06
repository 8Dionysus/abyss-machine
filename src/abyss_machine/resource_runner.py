from __future__ import annotations

import datetime as dt
import json
import math
import os
from pathlib import Path
import sys
from time import monotonic
from typing import Any

try:
    from . import resource_adapters
    from . import resource_planning
    from . import storage_lifecycle_adapters
except ImportError:
    # The handoff deliberately execs this file by path.  Its package context
    # is therefore absent and sibling modules cannot be imported as bare
    # top-level names when their own imports are relative.  Add the source
    # package parent, then resolve the same package modules used in-process.
    package_parent = str(Path(__file__).resolve().parent.parent)
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)
    from abyss_machine import resource_adapters  # type: ignore[no-redef]
    from abyss_machine import resource_planning  # type: ignore[no-redef]
    from abyss_machine import storage_lifecycle_adapters  # type: ignore[no-redef]


MAX_HANDOFF_BYTES = 16 * 1024 * 1024


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def validate_launch_attestation(execution: dict[str, Any]) -> dict[str, Any]:
    """Validate the private handoff's required monotonic freshness boundary."""
    raw = execution.get("launch_attestation")
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "reason": "launch_attestation_handoff_missing",
            "status": "missing",
        }
    required = raw.get("required")
    if not isinstance(required, bool):
        return {
            "ok": False,
            "reason": "launch_attestation_handoff_malformed",
            "status": "malformed",
        }
    if "deadline_monotonic" not in raw:
        return {
            "ok": False,
            "reason": "launch_attestation_handoff_malformed",
            "status": "malformed",
        }
    deadline = raw.get("deadline_monotonic")
    if required:
        if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
            return {
                "ok": False,
                "reason": "launch_attestation_handoff_malformed",
                "status": "malformed",
            }
        try:
            deadline_value = float(deadline)
        except (OverflowError, TypeError, ValueError):
            return {
                "ok": False,
                "reason": "launch_attestation_handoff_malformed",
                "status": "malformed",
            }
        if not math.isfinite(deadline_value):
            return {
                "ok": False,
                "reason": "launch_attestation_handoff_malformed",
                "status": "malformed",
            }
        checked_at = monotonic()
        if checked_at >= deadline_value:
            return {
                "ok": False,
                "reason": "launch_attestation_expired_before_execute",
                "status": "expired",
                "checked_at_monotonic": checked_at,
                "deadline_monotonic": deadline_value,
            }
        return {
            "ok": True,
            "status": "fresh",
            "checked_at_monotonic": checked_at,
            "deadline_monotonic": deadline_value,
        }
    if deadline is not None:
        return {
            "ok": False,
            "reason": "launch_attestation_handoff_malformed",
            "status": "malformed",
        }
    return {"ok": True, "status": "not_required"}


def preserve_managed_workspace_failure(
    lifecycle: dict[str, Any],
    *,
    reason: str,
    execution_started: bool | None = False,
    execution_status: str | None = None,
    cleanup_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Seal and preserve a delegated workspace after a pre-execute denial."""
    workspace_id = str(lifecycle.get("workspace_id") or "")
    failure = {
        "reason": str(reason),
        "stage": "pre_execute",
        "execution_started": execution_started,
        "execution_status": execution_status or (
            "not_started" if execution_started is False else "unknown"
        ),
        "preserved": True,
        "cleanup_errors": list(cleanup_errors or []),
    }
    try:
        sealed = storage_lifecycle_adapters.seal_registered_workspace(
            Path(str(lifecycle.get("root") or "")),
            workspace_id=workspace_id,
            lease_token=str(lifecycle.get("lease_token") or ""),
            preserved_failure=failure,
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        sealed = {"ok": False, "errors": [str(exc)[:500]]}
    record = sealed.get("record") if isinstance(sealed.get("record"), dict) else {}
    disposition = record.get("disposition") if isinstance(record.get("disposition"), dict) else {}
    return {
        "attempted": True,
        "ok": bool(
            sealed.get("ok") is True
            and record.get("state") == "sealed"
            and disposition.get("decision") == "UNKNOWN"
            and disposition.get("released") is False
        ),
        "workspace_id": workspace_id,
        "path": lifecycle.get("path"),
        "owner": lifecycle.get("owner"),
        "state": record.get("state"),
        "disposition": {
            "decision": disposition.get("decision"),
            "released": disposition.get("released"),
            "failure": disposition.get("failure"),
        },
        "execution_started": execution_started,
        "execution_status": execution_status or (
            "not_started" if execution_started is False else "unknown"
        ),
        "auto_deleted": False,
        "reason": str(reason),
        "cleanup_errors": list(cleanup_errors or []),
        "errors": [str(item) for item in sealed.get("errors", []) if str(item)],
    }


def read_handoff(environ: dict[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if environ is None else environ
    raw_fd = source.pop("ABYSS_RESOURCE_LAUNCH_HANDOFF_FD", "")
    try:
        fd = int(raw_fd)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("missing resource launch handoff fd") from exc
    if fd < 0:
        raise RuntimeError("invalid resource launch handoff fd")

    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = os.read(fd, min(1024 * 1024, MAX_HANDOFF_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_HANDOFF_BYTES:
                raise RuntimeError("resource launch handoff exceeds 16 MiB")
    finally:
        os.close(fd)
    try:
        document = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid resource launch handoff") from exc
    if not isinstance(document, dict):
        raise RuntimeError("resource launch handoff must be an object")
    return document


def finish_document(handoff: dict[str, Any]) -> dict[str, Any]:
    document = handoff.get("document")
    execution = handoff.get("execution")
    if not isinstance(document, dict) or not isinstance(execution, dict):
        raise RuntimeError("resource launch handoff is incomplete")

    attestation = validate_launch_attestation(execution)
    handoff_failure = None if attestation.get("ok") is True else attestation
    if handoff_failure is not None:
        reason = str(handoff_failure.get("reason") or "launch_attestation_handoff_malformed")
        denied_reasons = list(document.get("denied_reasons") or [])
        if reason not in denied_reasons:
            denied_reasons.append(reason)
        document["denied_reasons"] = denied_reasons
        planning = document.get("planning")
        if not isinstance(planning, dict):
            planning = {}
            document["planning"] = planning
        pre_admission = planning.get("pre_admission_dag")
        if not isinstance(pre_admission, dict):
            pre_admission = {}
            planning["pre_admission_dag"] = pre_admission
        pre_admission["handoff_validation"] = {
            "required": True,
            "status": handoff_failure.get("status"),
            "reason": reason,
            "checked_before_execute": True,
            "checked_at_monotonic": handoff_failure.get("checked_at_monotonic"),
            "deadline_monotonic": handoff_failure.get("deadline_monotonic"),
        }
        lease = execution.get("lease") if isinstance(execution.get("lease"), dict) else None
        lease_released = False
        lease_cleanup_error: str | None = None
        if isinstance(lease, dict):
            lease_id = str(lease.get("id") or "")
            reservation_root = Path(str(execution.get("reservation_root") or ""))
            if lease_id:
                try:
                    lease_released = resource_adapters.remove_lease(
                        reservation_root,
                        lease_id,
                    ) or not resource_adapters.lease_path(
                        reservation_root,
                        lease_id,
                    ).exists()
                except (OSError, TypeError, ValueError, RuntimeError) as exc:
                    lease_cleanup_error = str(exc)[:500]
            else:
                lease_cleanup_error = "lease_identity_missing"
        if lease_cleanup_error:
            denied_reasons.append("startup_lease_release_failed")
        storage_reservation = (
            execution.get("storage_reservation")
            if isinstance(execution.get("storage_reservation"), dict)
            else None
        )
        storage_reservation_root = (
            Path(str(execution.get("storage_reservation_root") or ""))
            if execution.get("storage_reservation_root")
            else None
        )
        try:
            storage_release = resource_adapters._release_storage_reservation(
                storage_reservation,
                storage_reservation_root,
                {
                    "confirmed_terminal": True,
                    "confirmation": "launch_attestation_handoff_rejected_before_execute",
                    "unit": str(execution.get("launch_unit") or "") or None,
                },
            )
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            storage_release = {
                "requested": isinstance(storage_reservation, dict),
                "ok": False,
                "decision": "blocked",
                "error": "storage_reservation_release_error",
                "detail": str(exc)[:500],
            }
        if storage_release.get("requested") and storage_release.get("ok") is not True:
            denied_reasons.append("storage_reservation_release_failed")
        pre_admission["handoff_validation"]["cleanup"] = {
            "memory_lease": {
                "attempted": isinstance(lease, dict),
                "released": lease_released,
                "error": lease_cleanup_error,
            },
            "storage_reservation": storage_release,
        }
        outcome = {
            "elapsed_sec": 0.0,
            "execution": None,
            "lease_released": lease_released,
            "demand_observation": None,
            "storage_reservation_release": storage_release,
        }
    else:
        outcome = resource_adapters.execute_systemd_launch(
            systemd_command=[str(item) for item in execution.get("systemd_command", [])],
            launch_unit=str(execution.get("launch_unit") or "") or None,
            generated_unit=str(execution.get("generated_unit") or "") or None,
            unit_type=str(execution.get("unit_type") or "service"),
            timeout_sec=float(execution.get("timeout_sec") or 0.0),
            lease=execution.get("lease") if isinstance(execution.get("lease"), dict) else None,
            reservation_root=Path(str(execution.get("reservation_root") or "")),
            demand_profile_path=Path(str(execution.get("demand_profile_path") or "")),
            demand_key=str(execution.get("demand_key") or "") or None,
            demand_owner=str(execution.get("demand_owner") or "") or None,
            kind=str(execution.get("kind") or "generic"),
            observed_peak_multiplier=float(execution.get("observed_peak_multiplier") or 1.25),
            profile_max_entries=int(execution.get("profile_max_entries") or 64),
            profile_max_samples=int(execution.get("profile_max_samples") or 16),
            parse_output=resource_planning.parse_systemd_run_output,
            command_identity=str(execution.get("command_identity") or "") or None,
            storage_reservation=(
                execution.get("storage_reservation")
                if isinstance(execution.get("storage_reservation"), dict)
                else None
            ),
            storage_reservation_root=(
                Path(str(execution.get("storage_reservation_root") or ""))
                if execution.get("storage_reservation_root")
                else None
            ),
        )

    result = outcome.get("execution") if isinstance(outcome.get("execution"), dict) else None
    document["generated_at"] = now_iso()
    document["elapsed_sec"] = float(outcome.get("elapsed_sec") or 0.0)
    planning = (
        document.get("planning")
        if isinstance(document.get("planning"), dict)
        else {}
    )
    request_started_monotonic = execution.get(
        "request_started_monotonic"
    )
    finished_monotonic = monotonic()
    if (
        isinstance(request_started_monotonic, (int, float))
        and not isinstance(request_started_monotonic, bool)
        and request_started_monotonic > 0
        and request_started_monotonic <= finished_monotonic
    ):
        total_elapsed_sec = (
            finished_monotonic - request_started_monotonic
        )
    else:
        total_elapsed_sec = (
            float(planning.get("elapsed_sec") or 0.0)
            + document["elapsed_sec"]
        )
    document["total_elapsed_sec"] = round(total_elapsed_sec, 3)
    document["execution"] = result
    document["ok"] = not document.get("denied_reasons") and not document.get("blocked_reasons") and bool(result and result.get("ok"))
    storage_release = outcome.get("storage_reservation_release")
    if isinstance(storage_release, dict) and storage_release.get("requested"):
        storage_document = document.get("storage_reservation")
        if not isinstance(storage_document, dict):
            storage_document = {"requested": True}
        storage_document["release"] = storage_release
        storage_document["accounting_complete"] = bool(
            storage_release.get("ok") is True
            and not storage_release.get("release_pending")
        )
        document["storage_reservation"] = storage_document
        if storage_release.get("release_pending") or storage_release.get("ok") is not True:
            document["ok"] = False
    startup = document.get("startup_admission") if isinstance(document.get("startup_admission"), dict) else {}
    startup["lease_released"] = bool(outcome.get("lease_released"))
    startup["demand_observation"] = outcome.get("demand_observation")
    document["startup_admission"] = startup
    lifecycle = execution.get("workspace_lifecycle")
    if isinstance(lifecycle, dict):
        if handoff_failure is not None:
            cleanup = preserve_managed_workspace_failure(
                lifecycle,
                reason=str(handoff_failure.get("reason") or "launch_attestation_handoff_rejected_before_execute"),
            )
            document["managed_workspace_cleanup"] = cleanup
            if not cleanup.get("ok"):
                document["denied_reasons"].append("managed_workspace_failure_cleanup_failed")
        else:
            finalized = storage_lifecycle_adapters.finalize_managed_workspace(
                Path(str(lifecycle.get("root") or "")),
                lifecycle,
                grace_seconds=int(lifecycle.get("grace_seconds") or 0),
            )
            if isinstance(result, dict):
                result["managed_workspace"] = finalized
        request = document.get("request") if isinstance(document.get("request"), dict) else {}
        request["managed_workspace"] = {
            key: value for key, value in lifecycle.items() if key not in {"lease_token", "root"}
        }
        document["request"] = request
    policy = document.get("policy") if isinstance(document.get("policy"), dict) else {}
    policy["long_waiter"] = "lightweight_exec_handoff"
    document["policy"] = policy

    if bool(handoff.get("write_latest")):
        errors: list[str] = []
        for raw_path, payload in (
            (handoff.get("latest_path"), document),
            (handoff.get("index_path"), handoff.get("index_document")),
        ):
            if not raw_path or not isinstance(payload, dict):
                errors.append("missing resource launch write target")
                continue
            try:
                resource_adapters.atomic_write_json(Path(str(raw_path)), payload, mode=0o664)
            except OSError as exc:
                errors.append(str(exc))
        if errors:
            document["ok"] = False
            document["write_errors"] = errors
    return document


def print_document(document: dict[str, Any], *, output_json: bool) -> None:
    if output_json:
        print(json.dumps(document, indent=2, sort_keys=False))
        return
    execution = document.get("execution") if isinstance(document.get("execution"), dict) else {}
    systemd = execution.get("systemd") if isinstance(execution.get("systemd"), dict) else {}
    print(f"resource launch: ok={document.get('ok')} dry_run={document.get('dry_run')}")
    print(f"blocked: {','.join(document.get('blocked_reasons', [])) or 'none'}")
    print(f"denied: {','.join(document.get('denied_reasons', [])) or 'none'}")
    print(f"unit: {systemd.get('unit')} returncode={execution.get('returncode')} memory_peak={systemd.get('memory_peak')}")


def exit_code(document: dict[str, Any], *, success_on_block: bool) -> int:
    if document.get("denied_reasons"):
        return 1
    if document.get("blocked_reasons"):
        return 0 if success_on_block else 2
    return 0 if document.get("ok") else 1


def release_handoff_lease(handoff: dict[str, Any]) -> bool:
    execution = handoff.get("execution")
    if not isinstance(execution, dict):
        return False
    lease = execution.get("lease")
    reservation_root = str(execution.get("reservation_root") or "")
    if not isinstance(lease, dict) or not reservation_root:
        return False
    lease_id = str(lease.get("id") or "")
    if not lease_id:
        return False
    root = Path(reservation_root)
    return resource_adapters.remove_lease(root, lease_id) or not resource_adapters.lease_path(
        root,
        lease_id,
    ).exists()


def main() -> int:
    handoff: dict[str, Any] | None = None
    try:
        handoff = read_handoff()
        document = finish_document(handoff)
    except Exception as exc:
        if handoff is not None:
            release_handoff_lease(handoff)
        print(json.dumps({"ok": False, "error": str(exc), "stage": "resource_launch_lightweight_waiter"}))
        return 1
    output = handoff.get("output") if isinstance(handoff.get("output"), dict) else {}
    print_document(document, output_json=bool(output.get("json")))
    return exit_code(document, success_on_block=bool(output.get("success_on_block")))


if __name__ == "__main__":
    raise SystemExit(main())
