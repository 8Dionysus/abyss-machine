#!/usr/bin/env python3
"""Compare full, file-partition, and record-append nervous index routes."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine import nervous_events  # noqa: E402
from abyss_machine import nervous_index  # noqa: E402
from abyss_machine import nervous_index_adapters  # noqa: E402


METHODS = (
    "full_rebuild",
    "file_partition_delta",
    "record_append_delta",
    "record_append_attested",
)
EXECUTION_SOURCE_PATHS = {
    "pyproject.toml",
    "scripts/benchmark_nervous_index_dag.py",
    "scripts/benchmark_nervous_pipeline_dag.py",
    "scripts/benchmark_nervous_sqlite_delta.py",
}


def _git_source() -> dict[str, Any]:
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
    inventory = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=False,
        capture_output=True,
    )
    source_entries: list[dict[str, str]] = []
    if inventory.returncode == 0:
        for raw_path in inventory.stdout.split(b"\0"):
            if not raw_path:
                continue
            path_text = raw_path.decode("utf-8", errors="surrogateescape")
            if not (
                path_text.startswith("src/")
                or path_text in EXECUTION_SOURCE_PATHS
            ):
                continue
            path = REPO_ROOT / path_text
            if path.is_file():
                source_entries.append({
                    "path": path_text,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
    source_tree_sha256 = hashlib.sha256(
        json.dumps(
            source_entries,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="replace")
    ).hexdigest()
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": bool(status.stdout) if status.returncode == 0 else None,
        "source_scope": "execution-code-v1:src-plus-benchmark-entrypoints",
        "source_file_count": len(source_entries),
        "source_tree_sha256": source_tree_sha256,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _event(index: int, body_bytes: int) -> dict[str, Any]:
    observed_at = (
        dt.datetime(2026, 8, 13, 12, 0, tzinfo=dt.UTC)
        + dt.timedelta(seconds=index)
    ).isoformat()
    body = f"event-{index:08d} " + ("x" * max(0, body_bytes - 15))
    return {
        "schema": "abyss_machine_nervous_event_v1",
        "raw_private_content": False,
        "source_ids": ["abyss_machine_facts"],
        "event_id": f"event-{index:08d}",
        "observed_at": observed_at,
        "generated_at": observed_at,
        "event_type": "benchmark.synthetic",
        "category": "validation",
        "severity": "info",
        "sensitivity": "machine_metadata",
        "title": body,
        "summary": body,
    }


def _append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _sources() -> dict[str, Any]:
    return {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
        "state": {"last_change_id": "benchmark-source-policy-v1"},
    }


def _plan(
    *,
    db_path: Path,
    roots: tuple[Path, Path, Path],
    run_id: str,
    at: str,
    force_full: bool,
    allow_append_delta: bool,
    source_delta_attestations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return nervous_index_adapters.build_incremental_document_from_source_roots(
        schema_prefix="abyss_machine",
        version="benchmark",
        generated_at=at,
        run_id=run_id,
        started_at=at,
        db_path=db_path,
        config_path=db_path.parent / "index.json",
        privacy={"global_pause": False, "private_mode": False},
        sources=_sources(),
        source_roots=roots,
        derived_refresh={},
        redact_text=lambda text: (text, 0),
        force_full=force_full,
        allow_append_delta=allow_append_delta,
        source_delta_attestations=source_delta_attestations or [],
    )


def _write(
    *,
    plan: dict[str, Any],
    db_path: Path,
    roots: tuple[Path, Path, Path],
    run_id: str,
    at: str,
) -> dict[str, Any]:
    facts_root, events_root, episodes_root = roots
    return nervous_index_adapters.write_build_projection(
        plan["data"],
        db_path=db_path,
        root=db_path.parent,
        schema_path=db_path.parent / "schema.sql",
        schema_sql=nervous_index.nervous_index_schema_sql(),
        schema_prefix="abyss_machine",
        version="benchmark",
        group="missing-benchmark-group",
        run_id=run_id,
        started_at=at,
        source_files=plan["source_files"],
        projection=plan["projection"],
        parse_errors=plan["parse_errors"],
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        source_state_change_id="benchmark-source-policy-v1",
        privacy_state_change_id="benchmark-privacy-v1",
        semantic_lock_active=lambda: False,
        now=lambda: at,
        counts_reader=lambda: nervous_index.counts(db_path),
        manifest_entries=plan["manifest_entries"],
        projection_identity=plan["projection_identity"],
        changed_source_paths=plan["changed_source_paths"],
        replace_source_paths=plan["replace_source_paths"],
        append_source_paths=plan["append_source_paths"],
        source_observations=plan["source_observations"],
        write_mode=plan["write_mode"],
        base_run_id=plan["base_run_id"],
    )


def _logical_digest(db_path: Path) -> str:
    conn = nervous_index.connect_db(db_path, create=False)
    digest = hashlib.sha256()
    try:
        statements = (
            """
            SELECT doc_id, source_path, source_line, source_sha256, record_sha256,
                   schema, generated_at, capture_trigger, global_pause, private_mode,
                   heartbeat, source_ids_json, title, body
            FROM documents ORDER BY doc_id
            """,
            """
            SELECT chunk_id, doc_id, chunk_index, source_id, title, body,
                   generated_at, privacy_mode, provenance_json
            FROM chunks ORDER BY chunk_id
            """,
            "SELECT chunk_id, doc_id, source_id, title, body FROM fts_chunks ORDER BY chunk_id",
            """
            SELECT source_path, source_sha256, source_size_bytes, source_line_count,
                   projection_identity, summary_json, parse_errors_json, skipped_records_json
            FROM source_manifest ORDER BY source_path
            """,
        )
        for index, statement in enumerate(statements):
            digest.update(f"table:{index}\n".encode("ascii"))
            for row in conn.execute(statement):
                digest.update(
                    json.dumps(
                        tuple(row),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ).encode("utf-8", errors="replace")
                )
                digest.update(b"\n")
    finally:
        conn.close()
    return digest.hexdigest()


def _method_flags(method: str) -> tuple[bool, bool, str, bool]:
    if method == "full_rebuild":
        return True, True, "full_rebuild", False
    if method == "file_partition_delta":
        return False, False, "file_partition_delta", False
    if method == "record_append_delta":
        return False, True, "record_append_delta", False
    if method == "record_append_attested":
        return False, True, "record_append_delta", True
    raise ValueError(f"unknown benchmark method: {method}")


def _summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = [float(sample["total_sec"]) for sample in samples]
    plan = [float(sample["plan_sec"]) for sample in samples]
    write = [float(sample["write_sec"]) for sample in samples]
    return {
        "samples": samples,
        "median_total_sec": round(statistics.median(total), 6),
        "min_total_sec": round(min(total), 6),
        "max_total_sec": round(max(total), 6),
        "median_plan_sec": round(statistics.median(plan), 6),
        "median_write_sec": round(statistics.median(write), 6),
    }


def run_benchmark(
    *,
    work_root: Path,
    records: int,
    body_bytes: int,
    repetitions: int,
    keep_workdir: bool,
    minimum_speedup: float,
) -> dict[str, Any]:
    source_identity = _git_source()
    work_root.mkdir(parents=True, exist_ok=True)
    benchmark_root = Path(tempfile.mkdtemp(prefix="nervous-index-dag-", dir=work_root))
    samples: dict[str, list[dict[str, Any]]] = {method: [] for method in METHODS}
    parity_failures: list[dict[str, Any]] = []
    try:
        for repetition in range(repetitions):
            trial_root = benchmark_root / f"trial-{repetition + 1}"
            facts_root = trial_root / "facts"
            events_root = trial_root / "events"
            episodes_root = trial_root / "episodes"
            roots = (facts_root, events_root, episodes_root)
            source_path = events_root / "2026" / "08" / "2026-08-13.jsonl"
            _append_jsonl(
                source_path,
                (_event(index, body_bytes) for index in range(records)),
            )
            db_paths = {
                method: trial_root / "indexes" / method / "nervous.db"
                for method in METHODS
            }
            seed_at = "2026-08-13T13:00:00+00:00"
            seed_plans: dict[str, dict[str, Any]] = {}
            for method, db_path in db_paths.items():
                seed = _plan(
                    db_path=db_path,
                    roots=roots,
                    run_id=f"seed-{repetition}-{method}",
                    at=seed_at,
                    force_full=True,
                    allow_append_delta=True,
                )
                seed_plans[method] = seed
                seeded = _write(
                    plan=seed,
                    db_path=db_path,
                    roots=roots,
                    run_id=f"seed-{repetition}-{method}",
                    at=seed_at,
                )
                if seeded.get("ok") is not True:
                    raise RuntimeError(f"seed failed for {method}: {seeded.get('error')}")

            _append_jsonl(source_path, [_event(records, body_bytes)])
            current_raw = source_path.read_bytes()
            current_observation = nervous_index_adapters.source_file_observation(source_path)
            attested_seed = seed_plans["record_append_attested"]["manifest_entries"][str(source_path)]
            append_attestation = nervous_events.source_delta_attestation(
                path=str(source_path),
                basis="append_only",
                base={
                    "sha256": attested_seed["source_sha256"],
                    "size_bytes": attested_seed["source_size_bytes"],
                    "line_count": attested_seed["source_line_count"],
                },
                current={
                    "path": str(source_path),
                    "sha256": hashlib.sha256(current_raw).hexdigest(),
                    "size_bytes": len(current_raw),
                    "line_count": len(current_raw.splitlines()),
                    "observation": current_observation,
                },
            )
            method_order = list(METHODS[repetition % len(METHODS):]) + list(
                METHODS[: repetition % len(METHODS)]
            )
            final_at = "2026-08-13T14:00:00+00:00"
            digests: dict[str, str] = {}
            for method in method_order:
                force_full, allow_append_delta, expected_strategy, use_attestation = _method_flags(method)
                db_path = db_paths[method]
                started = time.perf_counter()
                plan_started = time.perf_counter()
                plan = _plan(
                    db_path=db_path,
                    roots=roots,
                    run_id=f"final-{repetition}-{method}",
                    at=final_at,
                    force_full=force_full,
                    allow_append_delta=allow_append_delta,
                    source_delta_attestations=[append_attestation] if use_attestation else [],
                )
                plan_finished = time.perf_counter()
                result = _write(
                    plan=plan,
                    db_path=db_path,
                    roots=roots,
                    run_id=f"final-{repetition}-{method}",
                    at=final_at,
                )
                finished = time.perf_counter()
                strategy = plan.get("data", {}).get("execution", {}).get("strategy")
                if result.get("ok") is not True or strategy != expected_strategy:
                    raise RuntimeError(
                        f"{method} failed or selected {strategy!r}: {result.get('error')}"
                    )
                digests[method] = _logical_digest(db_path)
                result_counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
                samples[method].append({
                    "repetition": repetition + 1,
                    "order": method_order.index(method) + 1,
                    "strategy": strategy,
                    "plan_sec": round(plan_finished - plan_started, 6),
                    "write_sec": round(finished - plan_finished, 6),
                    "total_sec": round(finished - started, 6),
                    "delta": plan["data"]["execution"].get("delta"),
                    "timings_ms": result.get("execution", {}).get("timings_ms"),
                    "counts": {
                        "documents": result_counts.get("documents"),
                        "chunks": result_counts.get("chunks"),
                        "fts_chunks": result_counts.get("fts_chunks"),
                        "db_size_bytes": result_counts.get("db_size_bytes"),
                    },
                    "logical_digest": digests[method],
                })
            if len(set(digests.values())) != 1:
                parity_failures.append({"repetition": repetition + 1, "digests": digests})

        methods = {method: _summarize(samples[method]) for method in METHODS}
        full_median = float(methods["full_rebuild"]["median_total_sec"])
        for method in METHODS:
            median = float(methods[method]["median_total_sec"])
            methods[method]["speedup_vs_full"] = (
                round(full_median / median, 3) if median > 0 else None
            )
        append_candidates = ("record_append_delta", "record_append_attested")
        selected_candidate = min(
            append_candidates,
            key=lambda method: float(methods[method]["median_total_sec"]),
        )
        selected_speedup = float(methods[selected_candidate]["speedup_vs_full"] or 0.0)
        selection_allowed = bool(
            not parity_failures
            and selected_speedup >= float(minimum_speedup)
        )
        return {
            "schema": "abyss_machine_nervous_index_dag_benchmark_v1",
            "generated_at": cli.now_iso(),
            "source": source_identity,
            "authority": "shadow comparison only; the full rebuild remains the correctness oracle",
            "fixture": {
                "records_before_append": records,
                "records_after_append": records + 1,
                "body_bytes": body_bytes,
                "repetitions": repetitions,
            },
            "methods": methods,
            "comparison": {
                "oracle": "full_rebuild",
                "selected_candidate": selected_candidate,
                "selected_speedup_vs_full": selected_speedup,
                "minimum_speedup": float(minimum_speedup),
                "logical_parity": not parity_failures,
                "parity_failures": parity_failures,
                "claims_weakened": False,
                "selection_allowed": selection_allowed,
            },
            "workdir": str(benchmark_root) if keep_workdir else None,
        }
    finally:
        if not keep_workdir:
            shutil.rmtree(benchmark_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare nervous index DAG methods against the full rebuild oracle",
    )
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--body-bytes", type=int, default=256)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--minimum-speedup", type=float, default=1.1)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=cli.ABYSS_MACHINE_TMP_ROOT / "nervous-index-benchmarks",
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    records = max(1, min(int(args.records), 1_000_000))
    body_bytes = max(16, min(int(args.body_bytes), 8192))
    repetitions = max(1, min(int(args.repetitions), 20))
    minimum_speedup = max(1.0, min(float(args.minimum_speedup), 1000.0))
    try:
        result = run_benchmark(
            work_root=args.work_root.resolve(),
            records=records,
            body_bytes=body_bytes,
            repetitions=repetitions,
            keep_workdir=bool(args.keep_workdir),
            minimum_speedup=minimum_speedup,
        )
    except (OSError, RuntimeError, sqlite3.Error, ValueError) as exc:
        result = {
            "schema": "abyss_machine_nervous_index_dag_benchmark_v1",
            "generated_at": cli.now_iso(),
            "source": _git_source(),
            "ok": False,
            "error": str(exc),
        }
    else:
        result["ok"] = bool(result["comparison"]["logical_parity"])
    if args.receipt is not None:
        _write_json(args.receipt, result)
    if not args.quiet:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
