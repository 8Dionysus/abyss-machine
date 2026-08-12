#!/usr/bin/env python3
"""Compare live thermal evidence methods used around resource admission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine import resource_admission_server  # noqa: E402


def git_source() -> dict[str, Any]:
    head = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "root": str(REPO_ROOT),
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": bool(status.stdout) if status.returncode == 0 else None,
    }


def timed_samples(
    repetitions: int,
    operation: Callable[[], dict[str, Any]],
) -> tuple[list[float], dict[str, Any]]:
    samples: list[float] = []
    document: dict[str, Any] = {}
    for _ in range(repetitions):
        started = time.perf_counter()
        document = operation()
        samples.append(round(time.perf_counter() - started, 6))
    return samples, document


def method_result(
    *,
    method: str,
    role: str,
    disposition: str,
    reason: str,
    samples: list[float],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "method": method,
        "role": role,
        "disposition": disposition,
        "reason": reason,
        "samples_sec": samples,
        "median_sec": round(statistics.median(samples), 6),
        "min_sec": round(min(samples), 6),
        "max_sec": round(max(samples), 6),
        "evidence": evidence,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare live thermal evidence methods without changing policy",
    )
    parser.add_argument(
        "--class",
        dest="workload_class",
        choices=("probe", "light", "medium", "heavy", "sustained"),
        default="medium",
    )
    parser.add_argument(
        "--latency",
        choices=("low", "balanced", "interactive"),
        default="balanced",
    )
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args(argv)
    repetitions = max(1, min(int(args.repetitions), 10))

    emergency_samples, emergency = timed_samples(
        repetitions,
        resource_admission_server.fresh_thermal_safety,
    )
    map_samples, thermal_map = timed_samples(
        repetitions,
        lambda: cli.ai_cpu_thermal_map(write_latest=False),
    )
    admission_samples, admission = timed_samples(
        repetitions,
        lambda: cli.resource_thermal_admission_attestation(
            workload_class=args.workload_class,
            latency=args.latency,
            write_latest=False,
        ),
    )
    full_samples, full = timed_samples(
        repetitions,
        lambda: cli.process_thermal_plan(
            seconds=2.0,
            interval=0.5,
            top=20,
            write_latest=False,
        ),
    )

    methods = [
        method_result(
            method="direct_emergency_sensor",
            role="runtime emergency gate",
            disposition="retain_for_runtime_cold_load",
            reason=(
                "Fast and authoritative for emergency temperature, but does "
                "not prove request-specific CPU routing."
            ),
            samples=emergency_samples,
            evidence={
                "available": emergency.get("available"),
                "emergency": emergency.get("emergency"),
                "source": emergency.get("source"),
                "temperature_c_max": emergency.get("temperature_c_max"),
            },
        ),
        method_result(
            method="direct_cpu_thermal_map",
            role="fresh sensor and safe-CPU projection",
            disposition="retain_as_required_input",
            reason=(
                "Provides current package/core state and avoid sets, but not "
                "the decision for the requested workload class."
            ),
            samples=map_samples,
            evidence={
                "ok": thermal_map.get("ok"),
                "class": thermal_map.get("class"),
                "summary": thermal_map.get("summary"),
            },
        ),
        method_result(
            method="request_specific_thermal_admission",
            role="resource launch gate",
            disposition="selected",
            reason=(
                "Combines a fresh direct thermal map with the exact requested "
                "CPU route and fails closed when either proof is unavailable."
            ),
            samples=admission_samples,
            evidence={
                "ok": admission.get("ok"),
                "schema": admission.get("schema"),
                "thermal_class": (
                    admission.get("thermal", {}).get("class")
                    if isinstance(admission.get("thermal"), dict)
                    else None
                ),
                "recommendation": (
                    admission.get("recommended_new_work", {}).get(
                        args.workload_class
                    )
                    if isinstance(admission.get("recommended_new_work"), dict)
                    else None
                ),
                "evidence_errors": admission.get("evidence_errors"),
            },
        ),
        method_result(
            method="full_process_thermal_plan",
            role="operator diagnosis and attribution",
            disposition="retain_outside_launch_critical_path",
            reason=(
                "Preserves process attribution and desktop/compositor context; "
                "those diagnostic claims do not affect launch admission."
            ),
            samples=full_samples,
            evidence={
                "ok": full.get("ok"),
                "schema": full.get("schema"),
                "thermal_class": (
                    full.get("thermal", {}).get("class")
                    if isinstance(full.get("thermal"), dict)
                    else None
                ),
                "recommendation": (
                    full.get("recommended_new_work", {}).get(
                        args.workload_class
                    )
                    if isinstance(full.get("recommended_new_work"), dict)
                    else None
                ),
                "attribution_present": isinstance(full.get("attribution"), dict),
                "desktop_compositor_present": isinstance(
                    full.get("desktop_compositor"), dict
                ),
            },
        ),
    ]
    selected = next(
        item for item in methods if item["disposition"] == "selected"
    )
    diagnostic = next(
        item for item in methods if item["method"] == "full_process_thermal_plan"
    )
    speedup = (
        float(diagnostic["median_sec"]) / float(selected["median_sec"])
        if float(selected["median_sec"]) > 0
        else None
    )
    result = {
        "schema": "abyss_machine_resource_thermal_method_comparison_v1",
        "generated_at": cli.now_iso(),
        "source": git_source(),
        "request": {
            "class": args.workload_class,
            "latency": args.latency,
            "repetitions": repetitions,
        },
        "methods": methods,
        "comparison": {
            "selected": selected["method"],
            "diagnostic_retained": diagnostic["method"],
            "median_speedup_over_full_plan": (
                round(speedup, 3) if speedup is not None else None
            ),
            "claims_weakened": False,
            "safety_basis": [
                "fresh direct thermal map remains required",
                "the exact requested CPU route remains required",
                "missing or mismatched gate evidence fails closed",
                "process attribution and desktop context remain callable diagnostics",
            ],
        },
    }
    print(json.dumps(result, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
