# AoA session raw-block storage runner

The optional `aoa-session-memory-storage` profile provides a 30-minute user
timer for the owner-owned `raw-block-storage-compact` route.  The unit invokes
the installed `abyss-machine` launcher, which selects the pinned
`aoa_session_memory_portable_bundle` subject.  It never falls back to the live
`.aoa/scripts/aoa_session_memory.py` file.

The subject-store root in the rendered config is the host's writable storage
candidate (`{{ABYSS_MACHINE_SRV}}/storage/artifacts/subjects`).  The runner
passes that root to the trust-gate subprocess through the existing
`ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT(S)` override.  After the gate, the
selected registry record's `artifact_subject_store.path` is authoritative for
the bundle directory; a missing, unverified, or structurally mismatched path
blocks the run.  This lets storage admission reroute the materialized subject
store without moving the authoritative registry.

The rendered config is
`{{ABYSS_MACHINE_ETC}}/aoa-session-memory-storage.json`.  It is disabled by
default and must carry the exact promoted registry `record_id` before an
operator enables it.  The bundle class, subject digest, source ref, runtime
consumer intent, and `public_release` trust root are fixed in the public
template; a trust-gate mismatch stops before the Vault or owner command.

Each enabled run performs these bounded steps:

1. Admit the exact bundle with `abyss-machine artifacts trust-gate` for the
   `runtime` consumer.
2. Run `abyss-backup timer-preflight sessions`; an absent Vault defers without
   invoking the owner.
3. Obtain the existing medium/indexing memory lease through `abyss-machine
   resource launch`.  The protected owner path does not support a host byte
   reservation, so the outcome states
   `reservation_not_supported_for_owner_path` and passes neither `--bytes` nor
   `--target`.
4. Run `raw-block-storage-compact all --scheduled` with the owner limits:
   four sessions, 32 index entries, 1 GiB plaintext, sealed blocks from an
   open tail allowed, and owner ref/generation/staging guards intact.

Lock contention retries after 5, 15, and 30 seconds, with a 15-minute total
deadline.  Each resource launch receives the remaining deadline minus a
15-second post-timeout stop/probe reserve.  Its inner resource timeout leaves
another 45 seconds for policy planning, lease admission, and the resource
adapter's systemd wait margin; when those reserves are exhausted the runner
defers before starting another unit.  Every attempt has a unique transient
unit name.  If the outer wait expires, the runner issues a bounded stop and
terminal-state probe and records the unit as pending when systemd cannot prove
termination; it never retries an unresolved unit.  The owner runs through a
child wrapper inside the same resource lease, which drains stdout and stderr
concurrently, stops the child as soon as either stream crosses its cap, and
emits a summary below the resource adapter's 4 KiB tail.
The runner records only compact status, counters, cursor outcome,
and audit summaries under
`{{ABYSS_MACHINE_STATE}}/storage/aoa-session-memory-raw-block-compact/latest.json`;
it does not copy child stdout or raw session content into the host receipt.
`skipped_lock_held`, resource admission blocks, and an unmounted Vault are
reported as deferred and remain eligible for the next timer tick.

The initial enabled mode is `"mode": "pilot"` and invokes `--apply` without
`--confirm-remove-plain`, so compressed sidecars and ref audits can be checked
while plaintext remains.  Set `"mode": "reclaim"`,
`"reclaim_plain": true`, `"pilot_verified": true`, and a durable
`pilot_evidence_ref` only after the owner pilot's digest, restore, and old
reader checks have been accepted.  The runner then adds
`--confirm-remove-plain`; all owner transaction and last-good safeguards still
apply.

The service and timer are rendered by bootstrap but are not enabled by the
`linux-systemd-core` profile.  The explicit opt-in is
`--profile aoa-session-memory-storage`.  Disabling the config is the safe
rollback for the bridge; a code rollback uses the normal bootstrap immutable
generation rollback while preserving the prior installed generation.
