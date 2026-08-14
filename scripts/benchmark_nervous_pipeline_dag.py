#!/usr/bin/env python3
"""Compare a real-history nervous session delta with its complete oracle."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import benchmark_nervous_index_dag as index_benchmark  # noqa: E402
from abyss_machine import cli  # noqa: E402
from abyss_machine import nervous_events_adapters  # noqa: E402
from abyss_machine import nervous_index  # noqa: E402
from abyss_machine import nervous_index_adapters  # noqa: E402


def _timed(operation: Callable[[], dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    result = operation()
    return round(time.perf_counter() - started, 6), result


def _jsonl_digest(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    records = 0
    files = nervous_index.jsonl_files(root)
    for file_index, path in enumerate(files):
        relative = path.relative_to(root).as_posix()
        digest.update(f"file:{file_index}:{relative}\n".encode("utf-8"))
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                raw = line.strip()
                if not raw:
                    continue
                record = json.loads(raw)
                digest.update(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8", errors="replace")
                )
                digest.update(b"\n")
                records += 1
    return {
        "sha256": digest.hexdigest(),
        "files": len(files),
        "records": records,
    }


def _last_json_record(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        position = stream.tell()
        buffer = b""
        while position > 0:
            size = min(position, 1024 * 1024)
            position -= size
            stream.seek(position)
            buffer = stream.read(size) + buffer
            lines = [line for line in buffer.splitlines() if line.strip()]
            if lines and (position == 0 or len(lines) >= 2):
                record = json.loads(lines[-1].decode("utf-8", errors="replace"))
                if not isinstance(record, dict):
                    raise ValueError("last fact record is not an object")
                return record
    raise ValueError("fact source is empty")


def _snapshot_facts(source_root: Path, snapshot_root: Path) -> dict[str, Any]:
    source_files = nervous_index.jsonl_files(source_root)
    if not source_files:
        raise ValueError("facts root has no JSONL source partitions")
    total_bytes = 0
    snapshot_entries: list[dict[str, Any]] = []
    for source in source_files:
        relative = source.relative_to(source_root)
        target = snapshot_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        copied = False
        for _attempt in range(2):
            before = nervous_events_adapters.source_file_observation(source)
            shutil.copy2(source, target)
            after = nervous_events_adapters.source_file_observation(source)
            if before == after and target.stat().st_size == int(after["size_bytes"]):
                copied = True
                break
        if not copied:
            raise RuntimeError("fact source changed repeatedly during isolated snapshot")
        target_size = target.stat().st_size
        with target.open("rb") as stream:
            target_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        total_bytes += target_size
        snapshot_entries.append({
            "relative_path": relative.as_posix(),
            "size_bytes": target_size,
            "sha256": target_sha256,
        })
    current = snapshot_root / source_files[-1].relative_to(source_root)
    return {
        "source_files": len(source_files),
        "source_bytes": total_bytes,
        "current_partition": current,
        "current_partition_bytes": current.stat().st_size,
        "snapshot_identity_sha256": nervous_index.stable_json_sha256(snapshot_entries),
    }


def _append_session_fixture(path: Path) -> dict[str, Any]:
    record = copy.deepcopy(_last_json_record(path))
    original_time = nervous_index.parse_time(record.get("generated_at"))
    generated = (
        original_time + dt.timedelta(seconds=1)
        if original_time is not None
        else dt.datetime(2026, 8, 13, 23, 59, 59, tzinfo=dt.UTC)
    )
    record["generated_at"] = generated.isoformat()
    capture = dict(record.get("capture")) if isinstance(record.get("capture"), dict) else {}
    capture.update({
        "trigger": "benchmark_session_delta",
        "manual": True,
        "timer": False,
    })
    record["capture"] = capture
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n"
    needs_separator = False
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() > 0:
            stream.seek(-1, os.SEEK_END)
            needs_separator = stream.read(1) not in {b"\n", b"\r"}
    with path.open("ab") as stream:
        if needs_separator:
            stream.write(b"\n")
        stream.write(encoded)
    return {
        "appended_bytes": len(encoded) + int(needs_separator),
        "generated_at": generated.isoformat(),
    }


def _event_build(
    *,
    facts_root: Path,
    events_root: Path,
    generated_at: str,
    force_full: bool,
    thresholds: dict[str, float],
    deferred_source_ids: set[str],
) -> dict[str, Any]:
    def stateful_builder(
        items: list[dict[str, Any]],
        *,
        initial_state: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        return cli.nervous_events_contracts.events_from_fact_records_with_state(
            items,
            initial_state=initial_state,
            thresholds=thresholds,
            fact_source_id=cli.nervous_fact_source_id,
            deferred_source_ids=deferred_source_ids,
            compact_json_func=cli.nervous_compact_json_for_index,
            schema_prefix=cli.SCHEMA_PREFIX,
            version=cli.VERSION,
        )

    return nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=events_root / "latest.json",
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        derivation_identity=cli.nervous_events_contracts.event_derivation_identity(
            thresholds=thresholds,
            deferred_source_ids=deferred_source_ids,
            schema_prefix=cli.SCHEMA_PREFIX,
            version=cli.VERSION,
        ),
        force_full=force_full,
    )


def _episode_build(
    *,
    events_root: Path,
    episodes_root: Path,
    generated_at: str,
    force_full: bool,
) -> dict[str, Any]:
    return nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=episodes_root / "latest.json",
        episodes_from_events=cli.nervous_episodes_from_events,
        event_records_from_items=lambda items: cli.nervous_events_contracts.event_records_from_items(
            items,
            schema_prefix=cli.SCHEMA_PREFIX,
        ),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        force_full=force_full,
    )


def _index_plan(
    *,
    db_path: Path,
    roots: tuple[Path, Path, Path],
    privacy: dict[str, Any],
    sources: dict[str, Any],
    run_id: str,
    generated_at: str,
    force_full: bool,
    source_delta_attestations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return nervous_index_adapters.build_incremental_document_from_source_roots(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        run_id=run_id,
        started_at=generated_at,
        db_path=db_path,
        config_path=db_path.parent / "index.json",
        privacy=privacy,
        sources=sources,
        source_roots=roots,
        derived_refresh={},
        redact_text=cli.nervous_redact_index_text,
        force_full=force_full,
        source_delta_attestations=source_delta_attestations or [],
    )


def _index_write(
    *,
    plan: dict[str, Any],
    db_path: Path,
    roots: tuple[Path, Path, Path],
    run_id: str,
    generated_at: str,
) -> dict[str, Any]:
    facts_root, events_root, episodes_root = roots
    return nervous_index_adapters.write_build_projection(
        plan["data"],
        db_path=db_path,
        root=db_path.parent,
        schema_path=db_path.parent / "schema.sql",
        schema_sql=nervous_index.nervous_index_schema_sql(),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        group="missing-benchmark-group",
        run_id=run_id,
        started_at=generated_at,
        source_files=plan["source_files"],
        projection=plan["projection"],
        parse_errors=plan["parse_errors"],
        facts_root=facts_root,
        events_root=events_root,
        episodes_root=episodes_root,
        source_state_change_id="benchmark-source-state",
        privacy_state_change_id="benchmark-privacy-state",
        semantic_lock_active=lambda: False,
        now=lambda: generated_at,
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


def _index_stage(
    *,
    db_path: Path,
    roots: tuple[Path, Path, Path],
    privacy: dict[str, Any],
    sources: dict[str, Any],
    run_id: str,
    generated_at: str,
    force_full: bool,
    attestations: list[dict[str, Any]] | None = None,
) -> tuple[float, dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    plan = _index_plan(
        db_path=db_path,
        roots=roots,
        privacy=privacy,
        sources=sources,
        run_id=run_id,
        generated_at=generated_at,
        force_full=force_full,
        source_delta_attestations=attestations,
    )
    result = _index_write(
        plan=plan,
        db_path=db_path,
        roots=roots,
        run_id=run_id,
        generated_at=generated_at,
    )
    duration = round(time.perf_counter() - started, 6)
    execution = plan["data"].get("execution", {})
    projection_delta = execution.get("delta")
    compact = {
        "ok": result.get("ok"),
        "strategy": execution.get("strategy"),
        "source_partitions": execution.get("source_partitions"),
        "source_scan": execution.get("source_scan"),
        "delta": projection_delta,
        "timings_ms": result.get("execution", {}).get("timings_ms"),
        "counts": {
            key: result.get("counts", {}).get(key)
            for key in ("documents", "chunks", "fts_chunks", "db_size_bytes")
        },
    }
    del plan
    gc.collect()
    return duration, result, compact


def _compact_derived(result: dict[str, Any]) -> dict[str, Any]:
    incremental = result.get("incremental") if isinstance(result.get("incremental"), dict) else {}
    fallback_reason_codes = sorted({
        str(reason).split(":", 1)[0]
        for reason in (incremental.get("fallback_reasons") or [])
    })
    return {
        "ok": result.get("ok"),
        "strategy": incremental.get("strategy"),
        "fallback_reason_codes": fallback_reason_codes,
        "summary": result.get("summary"),
        "delta": incremental.get("delta"),
        "source_partitions": incremental.get("source_partitions"),
        "source_scan": incremental.get("source_scan"),
        "timings_ms": incremental.get("timings_ms"),
        "attestations": len(incremental.get("delta_attestations") or []),
    }


def run_pipeline(
    *,
    facts_source_root: Path,
    work_root: Path,
    keep_workdir: bool,
    session_deltas: int = 1,
) -> dict[str, Any]:
    source_identity = index_benchmark._git_source()
    work_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="nervous-pipeline-dag-", dir=work_root))
    try:
        facts_root = run_root / "facts"
        events_root = run_root / "events"
        episodes_root = run_root / "episodes"
        db_path = run_root / "index" / "nervous.db"
        roots = (facts_root, events_root, episodes_root)
        snapshot_started = time.perf_counter()
        source = _snapshot_facts(facts_source_root, facts_root)
        snapshot_sec = round(time.perf_counter() - snapshot_started, 6)
        privacy = cli.nervous_effective_privacy(write_latest=False)
        if bool(privacy.get("global_pause")):
            raise RuntimeError("global_pause is active; benchmark refused")
        sources = cli.nervous_effective_sources(write_latest=False)
        thresholds = cli.nervous_thermal_event_thresholds()
        deferred_source_ids = cli.nervous_deferred_source_ids(sources)
        event_derivation_identity = cli.nervous_events_contracts.event_derivation_identity(
            thresholds=thresholds,
            deferred_source_ids=deferred_source_ids,
            schema_prefix=cli.SCHEMA_PREFIX,
            version=cli.VERSION,
        )
        episode_derivation_identity = cli.nervous_events_contracts.episode_derivation_identity(
            schema_prefix=cli.SCHEMA_PREFIX,
            version=cli.VERSION,
        )
        enabled_sources = nervous_index.enabled_index_source_ids(sources)
        projection_identity = nervous_index.index_projection_identity(
            sources,
            enabled_sources,
            schema_prefix=cli.SCHEMA_PREFIX,
        )

        seed_at = "2026-08-13T23:00:00+00:00"
        seed_started = time.perf_counter()
        events_seed_sec, events_seed = _timed(
            lambda: _event_build(
                facts_root=facts_root,
                events_root=events_root,
                generated_at=seed_at,
                force_full=True,
                thresholds=thresholds,
                deferred_source_ids=deferred_source_ids,
            )
        )
        episodes_seed_sec, episodes_seed = _timed(
            lambda: _episode_build(
                events_root=events_root,
                episodes_root=episodes_root,
                generated_at=seed_at,
                force_full=True,
            )
        )
        index_seed_sec, index_seed, index_seed_compact = _index_stage(
            db_path=db_path,
            roots=roots,
            privacy=privacy,
            sources=sources,
            run_id="pipeline-seed",
            generated_at=seed_at,
            force_full=True,
        )
        seed_total_sec = round(time.perf_counter() - seed_started, 6)
        if not (events_seed.get("ok") and episodes_seed.get("ok") and index_seed.get("ok")):
            raise RuntimeError("full seed failed")
        del index_seed
        gc.collect()

        normalized_session_deltas = max(int(session_deltas), 1)
        delta_sessions: list[dict[str, Any]] = []
        fixtures: list[dict[str, Any]] = []
        final_base = dt.datetime(2026, 8, 13, 23, 30, tzinfo=dt.UTC)
        for sequence in range(1, normalized_session_deltas + 1):
            fixture = _append_session_fixture(source["current_partition"])
            fixtures.append(fixture)
            final_at = (final_base + dt.timedelta(minutes=sequence - 1)).isoformat()
            delta_started = time.perf_counter()
            events_delta_sec, events_delta = _timed(
                lambda: _event_build(
                    facts_root=facts_root,
                    events_root=events_root,
                    generated_at=final_at,
                    force_full=False,
                    thresholds=thresholds,
                    deferred_source_ids=deferred_source_ids,
                )
            )
            episodes_delta_sec, episodes_delta = _timed(
                lambda: _episode_build(
                    events_root=events_root,
                    episodes_root=episodes_root,
                    generated_at=final_at,
                    force_full=False,
                )
            )
            attestations = list(events_delta.get("incremental", {}).get("delta_attestations") or [])
            index_delta_sec, index_delta, index_delta_compact = _index_stage(
                db_path=db_path,
                roots=roots,
                privacy=privacy,
                sources=sources,
                run_id=f"pipeline-delta-{sequence}",
                generated_at=final_at,
                force_full=False,
                attestations=attestations,
            )
            delta_total_sec = round(time.perf_counter() - delta_started, 6)
            if not (events_delta.get("ok") and episodes_delta.get("ok") and index_delta.get("ok")):
                raise RuntimeError("incremental session delta failed")
            delta_sessions.append(
                {
                    "sequence": sequence,
                    "total_sec": delta_total_sec,
                    "events_sec": events_delta_sec,
                    "episodes_sec": episodes_delta_sec,
                    "index_sec": index_delta_sec,
                    "appended_bytes": fixture["appended_bytes"],
                    "events": _compact_derived(events_delta),
                    "episodes": _compact_derived(episodes_delta),
                    "index": index_delta_compact,
                }
            )
            del index_delta
            gc.collect()
        delta_digests = {
            "events": _jsonl_digest(events_root),
            "episodes": _jsonl_digest(episodes_root),
            "index_sha256": index_benchmark._logical_digest(db_path),
        }

        oracle_started = time.perf_counter()
        events_oracle_sec, events_oracle = _timed(
            lambda: _event_build(
                facts_root=facts_root,
                events_root=events_root,
                generated_at=final_at,
                force_full=True,
                thresholds=thresholds,
                deferred_source_ids=deferred_source_ids,
            )
        )
        episodes_oracle_sec, episodes_oracle = _timed(
            lambda: _episode_build(
                events_root=events_root,
                episodes_root=episodes_root,
                generated_at=final_at,
                force_full=True,
            )
        )
        index_oracle_sec, index_oracle, index_oracle_compact = _index_stage(
            db_path=db_path,
            roots=roots,
            privacy=privacy,
            sources=sources,
            run_id="pipeline-oracle",
            generated_at=final_at,
            force_full=True,
        )
        oracle_total_sec = round(time.perf_counter() - oracle_started, 6)
        if not (events_oracle.get("ok") and episodes_oracle.get("ok") and index_oracle.get("ok")):
            raise RuntimeError("forced full oracle failed")
        oracle_digests = {
            "events": _jsonl_digest(events_root),
            "episodes": _jsonl_digest(episodes_root),
            "index_sha256": index_benchmark._logical_digest(db_path),
        }
        del index_oracle
        gc.collect()

        fixed_at = (final_base + dt.timedelta(minutes=normalized_session_deltas + 14)).isoformat()
        fixed_started = time.perf_counter()
        events_fixed_sec, events_fixed = _timed(
            lambda: _event_build(
                facts_root=facts_root,
                events_root=events_root,
                generated_at=fixed_at,
                force_full=False,
                thresholds=thresholds,
                deferred_source_ids=deferred_source_ids,
            )
        )
        episodes_fixed_sec, episodes_fixed = _timed(
            lambda: _episode_build(
                events_root=events_root,
                episodes_root=episodes_root,
                generated_at=fixed_at,
                force_full=False,
            )
        )
        index_fixed_sec, index_fixed, index_fixed_compact = _index_stage(
            db_path=db_path,
            roots=roots,
            privacy=privacy,
            sources=sources,
            run_id="pipeline-fixed-point",
            generated_at=fixed_at,
            force_full=False,
            attestations=list(events_fixed.get("incremental", {}).get("delta_attestations") or []),
        )
        fixed_total_sec = round(time.perf_counter() - fixed_started, 6)
        if not (events_fixed.get("ok") and episodes_fixed.get("ok") and index_fixed.get("ok")):
            raise RuntimeError("fixed-point route failed")
        del index_fixed
        gc.collect()

        parity = {
            "events": delta_digests["events"] == oracle_digests["events"],
            "episodes": delta_digests["episodes"] == oracle_digests["episodes"],
            "index": delta_digests["index_sha256"] == oracle_digests["index_sha256"],
        }
        return {
            "schema": "abyss_machine_nervous_real_session_dag_benchmark_v2",
            "generated_at": cli.now_iso(),
            "source": source_identity,
            "authority": "isolated real-history shadow comparison; never authorizes the owner gate",
            "environment": {
                "python_version": sys.version.split()[0],
                "sqlite_version": sqlite3.sqlite_version,
                "privacy_identity_sha256": nervous_index.stable_json_sha256(privacy),
                "sources_identity_sha256": nervous_index.stable_json_sha256(sources),
                "event_derivation_identity": event_derivation_identity,
                "episode_derivation_identity": episode_derivation_identity,
                "index_projection_identity": projection_identity,
            },
            "fixture": {
                "source_partitions": source["source_files"],
                "source_bytes_before_append": source["source_bytes"],
                "current_partition_bytes_before_append": source["current_partition_bytes"],
                "session_deltas": normalized_session_deltas,
                "appended_bytes": sum(int(item["appended_bytes"]) for item in fixtures),
                "appended_bytes_each": [int(item["appended_bytes"]) for item in fixtures],
                "isolated_snapshot_sec": snapshot_sec,
                "snapshot_identity_sha256": source["snapshot_identity_sha256"],
            },
            "seed": {
                "total_sec": seed_total_sec,
                "events_sec": events_seed_sec,
                "episodes_sec": episodes_seed_sec,
                "index_sec": index_seed_sec,
                "events": _compact_derived(events_seed),
                "episodes": _compact_derived(episodes_seed),
                "index": index_seed_compact,
            },
            "delta": {
                "total_sec": delta_total_sec,
                "events_sec": events_delta_sec,
                "episodes_sec": episodes_delta_sec,
                "index_sec": index_delta_sec,
                "events": _compact_derived(events_delta),
                "episodes": _compact_derived(episodes_delta),
                "index": index_delta_compact,
                "digests": delta_digests,
            },
            "session_deltas": delta_sessions,
            "oracle": {
                "total_sec": oracle_total_sec,
                "events_sec": events_oracle_sec,
                "episodes_sec": episodes_oracle_sec,
                "index_sec": index_oracle_sec,
                "events": _compact_derived(events_oracle),
                "episodes": _compact_derived(episodes_oracle),
                "index": index_oracle_compact,
                "digests": oracle_digests,
            },
            "fixed_point": {
                "total_sec": fixed_total_sec,
                "events_sec": events_fixed_sec,
                "episodes_sec": episodes_fixed_sec,
                "index_sec": index_fixed_sec,
                "events": _compact_derived(events_fixed),
                "episodes": _compact_derived(episodes_fixed),
                "index": index_fixed_compact,
            },
            "comparison": {
                "parity": parity,
                "logical_parity": all(parity.values()),
                "delta_speedup_vs_oracle": round(oracle_total_sec / delta_total_sec, 3),
                "median_session_delta_sec": round(
                    statistics.median(item["total_sec"] for item in delta_sessions),
                    6,
                ),
                "median_session_speedup_vs_oracle": round(
                    oracle_total_sec
                    / statistics.median(item["total_sec"] for item in delta_sessions),
                    3,
                ),
                "fixed_point_speedup_vs_oracle": round(oracle_total_sec / fixed_total_sec, 3),
                "claims_weakened": False,
            },
            "workdir": str(run_root) if keep_workdir else None,
        }
    finally:
        if not keep_workdir:
            shutil.rmtree(run_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare an isolated real-history nervous session delta with the full oracle",
    )
    parser.add_argument("--facts-root", type=Path, required=True)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=cli.ABYSS_MACHINE_TMP_ROOT / "nervous-pipeline-benchmarks",
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--session-deltas", type=int, default=1)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_pipeline(
            facts_source_root=args.facts_root.resolve(),
            work_root=args.work_root.resolve(),
            keep_workdir=bool(args.keep_workdir),
            session_deltas=max(int(args.session_deltas), 1),
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        result = {
            "schema": "abyss_machine_nervous_real_session_dag_benchmark_v2",
            "generated_at": cli.now_iso(),
            "source": index_benchmark._git_source(),
            "ok": False,
            "error_type": type(exc).__name__,
        }
    else:
        result["ok"] = bool(result["comparison"]["logical_parity"])
    index_benchmark._write_json(args.receipt, result)
    if not args.quiet:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
