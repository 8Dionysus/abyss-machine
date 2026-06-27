from __future__ import annotations

import array
import base64
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_semantic import (
    batch_policy,
    body_preview,
    build_command,
    build_status,
    connect_db,
    counts,
    delete_stale_vectors,
    dedupe_results,
    dot,
    embedding_text,
    embedding_input_jsonl,
    embedding_runtime_options,
    embedding_subprocess_command,
    embedding_subprocess_result,
    embedding_window_size,
    existing_hashes,
    existing_vectors_by_hash,
    initialize_db,
    insert_vectors,
    maintain_assess,
    maintain_index_refresh_assess,
    put_meta,
    query_text,
    record_build_run,
    schema_sql,
    search_with_vector,
    source_chunks_query,
    source_rows_to_chunks,
    vector_from_blob,
)


FIXED_NOW = dt.datetime(2026, 6, 25, 12, 0, tzinfo=dt.timezone.utc)


def test_nervous_semantic_schema_is_module_owned_contract() -> None:
    schema = schema_sql()

    assert "CREATE TABLE IF NOT EXISTS vectors" in schema
    assert "CREATE TABLE IF NOT EXISTS build_runs" in schema
    assert "body_sha256 TEXT NOT NULL" in schema
    assert "CREATE INDEX IF NOT EXISTS idx_semantic_vectors_source_id" in schema


def test_semantic_status_tracks_bounded_source_drift_without_marking_stale() -> None:
    status = build_status(
        semantic={
            "enabled": True,
            "backend": "sqlite_float32_sidecar",
            "embedding": {"pooling": "last_token", "padding_side": "left", "device": "CPU", "batch_size": 16},
            "maintain": {"min_delta_chunks": 128, "max_stale_minutes": 90},
        },
        counts={
            "db_exists": True,
            "vectors": 100,
            "meta": {
                "source_index_run_id": "old-run",
                "built_at": "2026-06-25T11:50:00+00:00",
                "pooling": "last_token",
                "padding_side": "left",
            },
        },
        source_counts={"chunks": 120, "meta": {"run_id": "new-run", "built_at": "2026-06-25T11:58:00+00:00"}},
        model_dir="/srv/abyss-machine/runtimes/semantic/model",
        model_exists=True,
        cache_dir="/srv/abyss-machine/cache/ai/openvino/semantic",
        cache_exists=True,
        source_index_db_exists=True,
        semantic_index_db_exists=True,
        paths={
            "db": "/var/lib/abyss-machine/nervous/semantic/index.db",
            "root": "/var/lib/abyss-machine/nervous/semantic",
            "latest": "/var/lib/abyss-machine/nervous/semantic/latest.json",
            "source_index_db": "/var/lib/abyss-machine/nervous/index.db",
        },
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        now=FIXED_NOW,
    )

    assert status["ok"] is True
    assert status["ready"] is True
    assert status["freshness"]["source_index_changed"] is True
    assert status["freshness"]["bounded_source_drift"] is True
    assert status["freshness"]["stale"] is False
    assert "semantic source-index drift is below maintenance thresholds" in status["notices"]


def test_maintain_assess_requires_refresh_for_delta_or_embedding_policy() -> None:
    assessment = maintain_assess(
        {
            "ready": True,
            "freshness": {
                "source_index_run_id": "new",
                "semantic_source_index_run_id": "old",
                "source_chunks": 400,
                "vectors": 100,
                "embedding_config_stale": True,
            },
            "counts": {"meta": {"built_at": "2026-06-25T09:00:00+00:00"}},
            "source_index": {"built_at": "2026-06-25T11:00:00+00:00"},
        },
        min_delta_chunks=128,
        max_stale_minutes=90,
        now=FIXED_NOW,
    )

    assert assessment["needed"] is True
    assert assessment["stale"] is True
    assert assessment["delta_chunks"] == 300
    assert "embedding_config_changed" in assessment["reasons"]
    assert "stale_delta_chunks=300" in assessment["reasons"]
    assert "stale_age_minutes=180.0" in assessment["reasons"]


def test_index_refresh_assessment_is_bounded_status_contract() -> None:
    disabled = maintain_index_refresh_assess({"ready": False, "freshness": {"stale": True}}, enabled=False)
    stale = maintain_index_refresh_assess(
        {
            "ok": True,
            "ready": True,
            "freshness": {"stale": False, "records_lag_stale": True, "records_lag": "9"},
            "counts": {"chunks": 10, "meta": {"run_id": "run-1", "built_at": "2026-06-25T11:00:00+00:00"}},
        },
        enabled=True,
    )

    assert disabled["needed"] is False
    assert disabled["reasons"] == ["refresh_index_first_disabled"]
    assert stale["needed"] is True
    assert stale["records_lag"] == 9
    assert stale["reasons"] == ["source_index_records_lag"]


def test_batch_policy_reduces_implicit_batch_under_load_but_preserves_explicit_batch() -> None:
    memory = {
        "class": "hot",
        "pressure": {
            "summary": {
                "class": "hot",
                "zram_resident_mib": 9000,
                "psi_some_avg10": 3.2,
                "psi_full_avg10": 0.1,
            }
        },
        "game_guard": {"active": True, "platform_present": True, "summary": "fixture"},
        "recommended_new_work": {
            "medium": {
                "unattended_allowed": False,
                "unattended_blocked_reasons": ["fixture_unattended_block"],
            }
        },
    }

    implicit = batch_policy(
        {"embedding": {"batch_size": 16}},
        {"loaded_batch_size": 4, "loaded_batch_zram_resident_mib": 8192},
        None,
        "medium",
        True,
        memory,
    )
    explicit = batch_policy(
        {"embedding": {"batch_size": 16}},
        {"loaded_batch_size": 4, "loaded_batch_zram_resident_mib": 8192},
        12,
        "medium",
        True,
        memory,
    )

    assert implicit["load_detected"] is True
    assert implicit["effective_batch_size"] == 4
    assert implicit["pass_batch_override"] == 4
    assert implicit["load_reasons"] == [
        "game_guard_active",
        "fixture_unattended_block",
        "memory_class_hot",
        "zram_resident_high",
        "memory_psi_active_stalls",
    ]
    assert explicit["effective_batch_size"] == 12
    assert explicit["pass_batch_override"] is None


def test_semantic_build_command_and_search_helpers_are_stable_contracts() -> None:
    command = build_command(max_chunks=64, explicit_batch_size=None, batch_override=4, rebuild=True)
    truncated = embedding_text("Title", "body " * 20, 24)
    preview = body_preview("  one\n\n two\tthree  ", max_chars=80)
    vector = array.array("f", [1.0, 2.0])
    same = vector_from_blob(vector.tobytes())
    rows = [
        {"source_id": "nervous_events", "title": "nervous snapshot 2026-06-25T10:00:00+00:00", "score": 0.4, "chunk_generated_at": "2026-06-25T10:00:00+00:00"},
        {"source_id": "nervous_events", "title": "nervous snapshot 2026-06-25T11:00:00+00:00", "score": 0.9, "chunk_generated_at": "2026-06-25T11:00:00+00:00"},
        {"source_id": "browser_active_tab", "title": "different", "score": 0.6, "chunk_generated_at": "2026-06-25T09:00:00+00:00"},
    ]

    assert command == ["abyss-machine", "nervous", "semantic-build", "--json", "--max-chunks", "64", "--batch-size", "4", "--rebuild"]
    assert truncated.endswith("chars]")
    assert preview == "one two three"
    assert round(dot(same, same), 3) == 5.0
    assert [item["source_id"] for item in dedupe_results(rows, limit=4, dedupe=True)] == ["nervous_events", "browser_active_tab"]
    assert query_text("thermal route").endswith("Query: thermal route")


def test_semantic_embedding_subprocess_contract_is_module_owned() -> None:
    options = embedding_runtime_options(
        {
            "batch_size": 0,
            "max_tokens": 8,
            "pooling": "mean",
            "padding_side": "right",
            "timeout_sec": "12.5",
        }
    )
    input_jsonl = embedding_input_jsonl([{"id": "query", "text": "thermal route"}])
    command = embedding_subprocess_command(
        python="/usr/bin/python",
        input_path="/tmp/in.jsonl",
        output_path="/tmp/out.jsonl",
        model_dir="/srv/abyss-machine/runtimes/model",
        device="CPU",
        cache_dir="/srv/abyss-machine/cache/openvino",
        options=options,
    )
    vector = array.array("f", [1.0, 0.0])
    output_jsonl = json.dumps(
        {
            "id": "query",
            "dim": 2,
            "vector_b64": base64.b64encode(vector.tobytes()).decode("ascii"),
        }
    ) + "\n"
    result = embedding_subprocess_result(
        stdout='diagnostic\n{"ok":true,"items":1,"vectors":1,"dim":2}',
        stderr="runtime warning",
        returncode=0,
        output_jsonl=output_jsonl,
        expected_items=1,
        resource_profile={"kind": "fixture"},
    )
    mismatch = embedding_subprocess_result(
        stdout='{"ok":true,"items":1,"vectors":1,"dim":2}',
        stderr="",
        returncode=0,
        output_jsonl="",
        expected_items=1,
        resource_profile=None,
    )

    assert options["batch_size"] == 16
    assert options["max_tokens"] == 32
    assert options["pooling"] == "mean"
    assert options["padding_side"] == "right"
    assert options["timeout_sec"] == 12.5
    assert input_jsonl == '{"id": "query", "text": "thermal route"}\n'
    assert command[:3] == ["/usr/bin/python", "-c", command[2]]
    assert "OVModelForFeatureExtraction" in command[2]
    assert command[-7:] == ["/srv/abyss-machine/runtimes/model", "CPU", "/srv/abyss-machine/cache/openvino", "16", "32", "mean", "right"]
    assert result["ok"] is True
    assert result["stderr_tail"] == "runtime warning"
    assert result["resource_profile"] == {"kind": "fixture"}
    assert result["vectors"]["query"]["dim"] == 2
    assert result["vectors"]["query"]["blob"] == vector.tobytes()
    assert mismatch["ok"] is False


def test_semantic_source_chunk_and_store_contracts_are_module_owned(tmp_path: Path) -> None:
    sql, params = source_chunks_query(max_chunks=2)
    chunks = source_rows_to_chunks(
        [
            {
                "chunk_id": "chunk-a",
                "doc_id": "doc-a",
                "source_id": "nervous_events",
                "title": "Thermal route",
                "body": "zram pressure and thermal routing",
                "generated_at": "2026-06-25T11:00:00+00:00",
                "privacy_mode": "normal",
                "provenance_json": '{"severity":"info","event_id":"event-a"}',
                "document_generated_at": "2026-06-25T11:00:00+00:00",
                "document_schema": "abyss_machine_nervous_event_v1",
                "capture_trigger": "test",
                "source_path": "/var/lib/abyss-machine/nervous/events.jsonl",
                "source_line": 1,
            }
        ],
        max_input_chars=128,
    )

    assert "FROM chunks" in sql
    assert params == [2]
    assert chunks[0]["body_sha256"]
    assert chunks[0]["body_preview"] == "zram pressure and thermal routing"
    assert chunks[0]["embedding_text"].startswith("Thermal route")
    assert embedding_window_size({"maintain": {"embedding_window_chunks": 99999}}) == 8192

    db_path = tmp_path / "semantic.db"
    conn = connect_db(db_path, create=True)
    initialize_db(conn, version="test-version")
    conn.commit()
    put_meta(
        conn,
        {
            "run_id": "semantic-run-1",
            "source_index_run_id": "source-run-1",
            "built_at": "2026-06-25T11:05:00+00:00",
            "partial": "false",
        },
    )
    conn.commit()
    pending_by_id = {
        "chunk-a": chunks[0],
        "chunk-b": {
            **chunks[0],
            "chunk_id": "chunk-b",
            "doc_id": "doc-b",
            "source_id": "browser_active_tab",
            "title": "Browser note",
            "body_sha256": "hash-b",
            "provenance_json": '{"severity":"warn","event_id":"event-b"}',
        },
    }
    vector_a = array.array("f", [1.0, 0.0])
    vector_b = array.array("f", [0.2, 0.8])
    inserted = insert_vectors(
        conn,
        {
            "chunk-a": {"dim": 2, "blob": vector_a.tobytes()},
            "chunk-b": {"dim": 2, "blob": vector_b.tobytes()},
        },
        pending_by_id,
        "2026-06-25T11:06:00+00:00",
    )
    record_build_run(
        conn,
        run_id="semantic-run-1",
        started_at="2026-06-25T11:06:00+00:00",
        finished_at="2026-06-25T11:07:00+00:00",
        ok=True,
        source_chunks=2,
        pending_chunks=2,
        vectors_indexed=inserted,
        partial=False,
        errors={"provenance": {"source": "test"}},
    )
    conn.commit()

    assert inserted == 2
    assert existing_hashes(conn)["chunk-a"] == chunks[0]["body_sha256"]
    assert existing_vectors_by_hash(conn)[chunks[0]["body_sha256"]]["dim"] == 2
    conn.execute("BEGIN")
    removed = delete_stale_vectors(conn, {"chunk-a"}, partial=False)
    conn.commit()
    conn.close()

    sidecar_counts = counts(db_path)
    assert removed == 1
    assert sidecar_counts["vectors"] == 1
    assert sidecar_counts["build_runs"] == 1
    assert sidecar_counts["meta"]["run_id"] == "semantic-run-1"
    assert sidecar_counts["last_successful_build_run"]["details"]["provenance"]["source"] == "test"


def test_semantic_search_with_vector_filters_and_summarizes_sidecar(tmp_path: Path) -> None:
    db_path = tmp_path / "semantic.db"
    conn = connect_db(db_path, create=True)
    initialize_db(conn, version="test-version")
    put_meta(
        conn,
        {
            "run_id": "semantic-run-2",
            "source_index_run_id": "source-run-2",
            "built_at": "2026-06-25T11:10:00+00:00",
            "partial": "true",
        },
    )
    conn.commit()
    vector_hot = array.array("f", [1.0, 0.0])
    vector_cold = array.array("f", [0.0, 1.0])
    insert_vectors(
        conn,
        {
            "hot": {"dim": 2, "blob": vector_hot.tobytes()},
            "cold": {"dim": 2, "blob": vector_cold.tobytes()},
        },
        {
            "hot": {
                "chunk_id": "hot",
                "doc_id": "doc-hot",
                "source_id": "nervous_events",
                "document_schema": "schema-hot",
                "title": "thermal pressure",
                "body_sha256": "hash-hot",
                "body_preview": "hot route",
                "generated_at": "2026-06-25T11:00:00+00:00",
                "document_generated_at": "2026-06-25T11:00:00+00:00",
                "privacy_mode": "normal",
                "provenance_json": '{"severity":"warn","sensitivity":"machine","event_id":"hot"}',
            },
            "cold": {
                "chunk_id": "cold",
                "doc_id": "doc-cold",
                "source_id": "browser_active_tab",
                "document_schema": "schema-cold",
                "title": "browser context",
                "body_sha256": "hash-cold",
                "body_preview": "cold route",
                "generated_at": "2026-06-25T10:00:00+00:00",
                "document_generated_at": "2026-06-25T10:00:00+00:00",
                "privacy_mode": "normal",
                "provenance_json": '{"severity":"info","sensitivity":"machine","event_id":"cold"}',
            },
        },
        "2026-06-25T11:11:00+00:00",
    )
    conn.close()

    result = search_with_vector(
        db_path=db_path,
        query="thermal",
        query_vector_blob=vector_hot.tobytes(),
        query_vector_result={
            "embedding_status": {"ok": True, "vectors": 1},
            "policy_gate": {"ok": True},
        },
        final_limit=5,
        source="nervous_events",
        severity="warn",
        schema_prefix="abyss_machine",
        version="test-version",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["results"] == 1
    assert result["summary"]["filtered_out"] == 1
    assert result["summary"]["partial"] is True
    assert result["summary"]["semantic_run_id"] == "semantic-run-2"
    assert result["results"][0]["chunk_id"] == "hot"
    assert result["results"][0]["provenance"]["event_id"] == "hot"
