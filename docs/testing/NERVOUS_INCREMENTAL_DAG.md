# Nervous Incremental DAG

## Purpose

The normal typing/nervous refresh route must scale with new evidence, not with
the complete retained history. It must still produce the same event, episode,
document, chunk, FTS, summary, and search claims as the complete rebuild.

The complete rebuild remains an executable oracle. No source policy, privacy
gate, parse error, document, chunk, FTS row, or validation claim is removed to
make the incremental route faster.

## Compared Routes

The lexical benchmark keeps four methods independently runnable:

| Method | Work after one appended record | Role |
| --- | --- | --- |
| `full_rebuild` | parse, project, and replace every source record | serial correctness oracle and rollback |
| `file_partition_delta` | replace every record in each changed file | arbitrary-edit and removal fallback |
| `record_append_delta` | verify the old prefix, then insert only appended records | independent incremental route |
| `record_append_attested` | consume the exact append proof already produced by event derivation, recheck the current stat identity, and read only the tail | selected cross-stage DAG route when its proof matches |
| `fixed_point_noop` | recheck the locked source snapshot and prior run identity without opening a write transaction | selected route when no source or policy vertex changed |

File-partition delta is intentionally retained even when it benchmarks slower
than a full rebuild on a one-file fixture. It is the bounded route for an
arbitrary modification when most other source partitions are unchanged.

## Execution Graph

The normal route is a fixed-point DAG:

1. Event derivation scans source partition metadata. Unchanged partitions
   reuse their exact prior SHA only when device, inode, size, nanosecond mtime,
   and nanosecond ctime all match.
2. A changed fact partition is read and hashed exactly. An append is admitted
   only when the prior byte prefix hashes to the previous manifest identity and
   ends at a complete line boundary.
3. Event derivation applies the saved boundary state to only the new records.
   Stable source timestamps make an unchanged derivation an exact fixed point.
   Its state is reusable only while the exact derivation identity (ABI, output
   version, thermal thresholds, and deferred-source policy) matches. When the
   derived event file remains a literal append of its old bytes, the stage emits
   a second exact append attestation for that output partition. Event storage is
   ordered by normalized-UTC `generated_at` and `event_id`, while semantic
   episode grouping still uses `observed_at`; an older nested observation can
   therefore stay a physical append without changing its meaning.
4. Episode derivation replaces only episode partitions owned by changed event
   partitions. Its manifest records each `(day, category)` owner. If one group
   crosses event-file boundaries, the same invocation automatically executes
   the complete oracle and marks incremental state invalid.
5. The index reuses unchanged manifest entries. For changed fact and derived
   event files it may consume typed event-stage append attestations; it
   independently verifies each proof digest, base SHA/size/line identity,
   current stat identity, and tail length before using it. Episode partition
   replacement remains a bounded file delta because existing episode rows can
   change when new events join a group.
6. The SQLite transaction uses `documents.source_path` and chunk primary-key
   lookups to touch only replaced or appended rows. It inserts and verifies only
   the new FTS rowids, upserts only changed manifest/meta values, preserves
   `chunks.rowid == fts_chunks.rowid`, and commits atomically. A document keeps
   its immutable `record_sha256`; the mutable whole-partition SHA is owned only
   by the source manifest. No query scans all documents or chunks merely to
   prove a 17-document delta.
7. With no changed source, metadata, or policy vertex, the locked fixed-point
   route verifies the stable source snapshot and previous database `run_id`,
   reads bounded counts, and leaves the database byte-for-byte untouched. It
   does not advance `built_at` or manufacture a new database run.

The event attestation is an optimization witness, not a new source of truth.
If it is absent, malformed, stale, or changed, the index reads and hashes the
source itself.

## Fail-Closed Boundaries

Incremental admission falls back to a file or full rebuild when any of these
conditions holds:

- projection policy or projection ABI changed;
- manifest identity, document count, chunk count, or FTS count drifted;
- FTS rowid identity is not established;
- a historical partition changed or disappeared;
- an append prefix does not match its exact prior SHA and line boundary;
- a derived event's normalized generation order would not preserve the literal
  output prefix required by an append attestation;
- event/episode derivation policy, ABI, or output version changed;
- an episode `(day, category)` group is owned by more than one event partition;
- the source partition set or stat identity changes between planning and the
  locked write;
- an event boundary state or episode partition-local proof is missing;
- parsing, derived-file writing, SQLite uniqueness, or FTS identity fails.

Source changes after planning refuse the write without touching the database.
SQLite delta writes use one transaction, so a partial document/chunk/FTS
failure rolls back the entire mutation.

## Operator and Oracle Commands

Normal builds select the strongest admitted incremental route:

```bash
abyss-machine nervous events-build --json
abyss-machine nervous episodes-build --json
abyss-machine nervous index-build --json
```

Each layer retains an explicit complete oracle:

```bash
abyss-machine nervous events-build --full-rebuild --json
abyss-machine nervous episodes-build --full-rebuild --json
abyss-machine nervous index-build --full-rebuild --json
```

An explicit index-only experiment can avoid an unrelated derived refresh with
`index-build --no-refresh-derived`. This is not the normal session route.

## Reproducible Shadow Comparison

Run the public-safe synthetic harness through resource admission:

```bash
abyss-machine resource launch \
  --class medium --kind benchmark --activity background \
  --memory-demand-mib 1536 \
  --demand-key abyss-machine:nervous-index-dag-synthetic-10k \
  --demand-owner abyss-machine \
  --estimate-source bounded-scale-up-from-1k \
  --estimate-confidence medium \
  -- scripts/benchmark_nervous_index_dag.py \
  --records 10000 --body-bytes 256 --repetitions 3 \
  --receipt RECEIPT.json --quiet
```

The harness rotates method order, seeds an independent database per method,
adds the same one-record delta, and hashes the final logical documents, chunks,
FTS rows, and source manifest. It never authorizes the owner gate. Selection is
reported only when every logical digest matches and the best append candidate
is at least 1.1 times faster than the full oracle on that fixture.

The 2026-08-13 bounded runs produced:

| Fixture | Full median | File delta median | Record delta median | Attested record median | Selected speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 -> 1,001 records, 7 repetitions | 0.087 s | 0.102 s | 0.026 s | 0.033 s | 3.35x |
| 10,000 -> 10,001 records, 3 repetitions | 1.141 s | 1.254 s | 0.067 s | 0.024 s | 46.88x |

All compared final logical digests matched. In the exact-current 10,000-record
run, the selected attested path spent 0.024 seconds end-to-end and the
independent prefix-verifying append path spent 0.067 seconds. The
resource-controlled four-method, three-repetition experiment used 24.869
seconds wall time, 23.598 CPU-seconds, 943.6 MiB peak memory, and no swap. Its
receipt SHA-256 is
`ba5b26d88ccc7ebfe75b912cc5840ed670f4e88bb90d6309a37c75cc01e73f9a`.

For the complete real-session pipeline, use an isolated snapshot of local fact
history and keep the receipt outside the repository:

```bash
abyss-machine resource launch \
  --class medium --kind benchmark --activity background \
  --bytes 6442450944 \
  --target /srv/abyss-machine/tmp/nervous-pipeline-benchmarks \
  --memory-demand-mib MEMORY_BUDGET_FROM_PRIOR_RUNS \
  --demand-key abyss-machine:nervous:pipeline-dag-benchmark \
  --demand-owner abyss-machine \
  -- scripts/benchmark_nervous_pipeline_dag.py \
  --facts-root /var/lib/abyss-machine/nervous/facts \
  --work-root /srv/abyss-machine/tmp/nervous-pipeline-benchmarks \
  --receipt RECEIPT.json --session-deltas 3 --quiet
```

This harness copies every fact partition to isolated host-managed temporary
storage while checking that each source observation remains stable. Snapshot
copy time is reported separately. It seeds events, episodes, and SQLite; runs
the requested number of consecutive one-record session deltas on the same
snapshot; compares the final state with a forced full oracle; and measures a
no-change fixed point. Only aggregate counts, timings, resource-safe identities,
and streaming logical digests enter the receipt. Source records and private
source paths do not.

The exact-source 2026-08-13 run covered 39 fact partitions and 1.620 GB before
append, with 45,962 final documents and 207,763 final chunks/FTS rows. Its three
consecutive session deltas took 0.706, 0.511, and 0.515 seconds (0.515-second
median) versus 231.465 seconds for the complete oracle: 449.53x median speedup.
Events, episodes, and the logical SQLite projection all matched their oracle
digests and `claims_weakened` remained false. The unchanged fixed point took
0.048 seconds, including a 0.023-second index stage with `db_write=0` and
`database_touched=false`.

On the real 207,000-row FTS store, targeted SQLite maintenance reduced the
index stage from the earlier 0.55-0.70-second diagnostic range to 0.10-0.14
seconds. Replacement planning fell below 0.23 ms, FTS insertion below 2.74 ms,
and FTS rowid verification below 0.33 ms; commit remained a bounded 9.64-25.96
ms. The default WAL and FTS policies are therefore retained. The complete
resource-controlled evidence run, including seed and oracle, used 9 minutes 12
seconds wall time, 8 minutes 42 seconds CPU time, 9.11 GiB peak memory, and no
swap. That experimental envelope is not the session latency. Receipt SHA-256:
`dac5989cbf1021e3fa35418bacbebfd7916431056a295f401134ada3b0c67811`;
execution source-tree SHA-256:
`c6bccaba9d89ab3052bc7f3e4e3ef180a9342705847a5c77d4e8af3a2db2dde2`.

These measurements are observational and fixture-specific. Correctness comes
from oracle parity and negative controls; latency determines which already
correct route should be preferred.
