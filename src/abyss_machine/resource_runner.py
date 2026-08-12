from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from time import monotonic
from typing import Any

try:
    from . import resource_adapters
    from . import resource_planning
except ImportError:
    import resource_adapters  # type: ignore[no-redef]
    import resource_planning  # type: ignore[no-redef]


MAX_HANDOFF_BYTES = 16 * 1024 * 1024


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


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
    startup = document.get("startup_admission") if isinstance(document.get("startup_admission"), dict) else {}
    startup["lease_released"] = bool(outcome.get("lease_released"))
    startup["demand_observation"] = outcome.get("demand_observation")
    document["startup_admission"] = startup
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
