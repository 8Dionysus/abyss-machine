from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
SRC_ROOT = ROOT / "src"
for path in (SCRIPTS_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import benchmark_nervous_sqlite_delta as benchmark
from abyss_machine import nervous_index


def test_sqlite_delta_strategy_benchmark_preserves_rows_and_hides_source_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "private-index" / "nervous.db"
    source_path = str(tmp_path / "private-episodes" / "2026-08-13.jsonl")
    conn = nervous_index.connect_db(db_path, create=True)
    nervous_index.initialize_db(conn, version="test")
    conn.execute(
        """
        INSERT INTO documents (
          doc_id, source_path, source_line, source_sha256, record_sha256, schema,
          generated_at, capture_trigger, global_pause, private_mode, heartbeat,
          source_ids_json, title, body, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "doc-episode",
            source_path,
            1,
            None,
            "record-episode",
            "abyss_machine_nervous_episode_v1",
            "2026-08-13T12:00:00+00:00",
            "derived_episode",
            0,
            0,
            0,
            json.dumps(["nervous_episodes"]),
            "episode title",
            "episode body for fts",
            "2026-08-13T12:01:00+00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO chunks (
          chunk_id, doc_id, chunk_index, source_id, title, body,
          generated_at, privacy_mode, provenance_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "chunk-episode",
            "doc-episode",
            0,
            "nervous_episodes",
            "episode title",
            "episode body for fts",
            "2026-08-13T12:00:00+00:00",
            "normal",
            "{}",
        ),
    )
    conn.execute(
        """
        INSERT INTO fts_chunks(rowid, chunk_id, doc_id, source_id, title, body)
        SELECT rowid, chunk_id, doc_id, source_id, title, body FROM chunks
        """
    )
    conn.execute(
        """
        INSERT INTO source_manifest (
          source_path, source_sha256, source_size_bytes, source_line_count,
          source_observation_json, projection_identity, summary_json,
          parse_errors_json, skipped_records_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (source_path, "partition-sha", 100, 1, "{}", "projection", "{}", "[]", "[]", "now"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(benchmark, "_copy_database", lambda source, target: shutil.copy2(source, target))
    result = benchmark.run_benchmark(
        db_path=db_path,
        lock_path=tmp_path / "index.lock",
        work_root=tmp_path / "work",
        repetitions=1,
    )

    assert result["ok"] is True
    assert result["comparison"]["logical_parity"] is True
    assert result["comparison"]["claims_weakened"] is False
    assert result["comparison"]["selected_candidate"] in benchmark.METHODS
    assert result["source_code"]["source_scope"] == "execution-code-v1:src-plus-benchmark-entrypoints"
    assert all(
        sample["parity"] is True
        for method in result["methods"].values()
        for sample in method["samples"]
    )
    assert str(tmp_path) not in json.dumps(result, ensure_ascii=False)
