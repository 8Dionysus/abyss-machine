# 0020 Artifact Evidence Cleanup Route

## Status

accepted

## Date

2026-06-12

## Index Tags

- artifacts
- storage-topology
- ai-cache
- vault-restore
- validation-guard

## Current Applicability

As of 2026-06-12, large host-local artifact cleanup is routed through the
`abyss-machine artifacts ...` read-model before archive, offload, quarantine,
or removal decisions. Current source law is in `{{ABYSS_MACHINE_ETC}}/AGENTS.md`,
the generated/local entrypoint is `{{ABYSS_MACHINE_STATE}}/artifacts/AGENTS.md`,
and the implementation lives in `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`.

The second 2026-06-12 increment adds `usage` and `timeline` read-models so the
machine can separate current live refs, live config, source config, docs refs,
historical `.bak`/canary refs, generated latest/history mentions, journal/log
mentions, and vault restore state. Only current live process/service/container
refs or live config can support active-route classification by themselves.
Source config, docs, decisions, `.bak`, and generated history are visible
context but not current-live proof.

## Context

The host had large AI cache/model/runtime surfaces where old mtime, large size,
or a missing live fd could look like enough evidence to clean. That is unsafe:
some artifacts are active service/container routes, some are local-absent but
vault-backed offloads, and some are likely quarantine candidates only after a
controlled workload probe.

The storage lane already says facts first and no automatic deletion. The missing
piece was a more precise artifact-level organ that joins local path state,
process refs, service/container refs, live config refs, historical traces,
vault backup/offload/preserved-deleted state, restore route, classification,
confidence, and a quarantine plan.

## Options Considered

- Keep storage cleanup as size/date buckets only. This is too weak for AI
  artifacts and would invite accidental removal of active runtime surfaces.
- Push all decisions to manual ad hoc shell inspection. This preserves caution
  but loses repeatability, source route, and future system memory.
- Add an artifact evidence organ that is read-only by default and requires
  backup/restore plus workload evidence before future mutation.

## Decision

Create `abyss-machine artifacts` as a facts-only host organ with inventory,
explain/trace, classify, quarantine-plan, and validate commands.

Classification must separate at least:

- `active-route`: active process, service, container, or strong live config
  evidence; do not clean without route-specific test and operator intent.
- `quarantine-first`: no active refs observed, backup state known, but still no
  delete-ok; only a controlled quarantine plus workload probe may follow.
- `archive-candidate`: local path already absent and vault/offload/preserved
  state can restore it if needed.
- `regenerable` or `unknown`: low-confidence states that do not grant delete-ok.

## Rationale

This keeps cleanup pressure useful without flattening it into "old equals
unused." The machine can now know more: which artifacts are live routes, which
are restorable offloads, which are only historical/contextual traces, and which
future action would prove safety. The route also matches the vault strategy:
backup/offload is evidence for reversibility, not permission to delete blindly.

## Consequences

Future storage cleanup can ask the artifact organ first instead of re-running
one-off shell archaeology. Vault restore commands become visible next to the
classification. Validators can assert that dictation OpenVINO stays protected
as an active route and that semantic embedding cache stays bounded as
quarantine-first unless stronger live evidence appears.

The organ adds another generated latest/history surface under
`{{ABYSS_MACHINE_STATE}}/artifacts`. Those read-models must not become source
truth and may be regenerated.

## Boundaries

- No `artifacts` command deletes, moves, stops services, or mutates project
  roots.
- Date, size, mtime, atime, and refs=0 are never sufficient for delete-ok.
- A backup/offload hit proves a restore route, not that local cleanup is safe.
- Context config hits, historical tmp/canary files, and generated classifier
  specs are not strong live-route evidence by themselves.
- Semantic OpenVINO compile-cache safety requires a bounded real rebuild probe
  after quarantine, for example `abyss-machine nervous semantic-build
  --max-chunks 8 --batch-size 1 --rebuild --json`; status, search, and dry-run
  alone are insufficient.
- `abyss-machine` still must not mutate `{{ABYSS_OS_ROOT}}`, `abyss-stack`, work
  roots, game roots, or stack-owned services.

## Review Log

- 2026-06-12: Initial record.
- 2026-06-12: Added real usage/timeline lanes and split live/source/docs/history/generated/backup evidence so non-live references cannot inflate active-route confidence.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/artifacts/AGENTS.md`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_SRV}}/tests/contract/test_artifact_evidence.py`
- `{{ABYSS_MACHINE_STATE}}/artifacts/index.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/inventory/latest.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/trace/latest.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/usage/latest.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/timeline/latest.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/classify/latest.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/quarantine/latest.json`
- `{{ABYSS_MACHINE_STATE}}/artifacts/validate/latest.json`
- `{{ABYSS_BACKUP_ROOT}}/heavy`

## Validation

- `abyss-machine artifacts validate --json`
- `abyss-machine artifacts usage PATH --json`
- `abyss-machine artifacts timeline PATH --json`
- `abyss-machine storage validate --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine test quick --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`

## Follow-up Route

Future cleanup/offload work should start with
`abyss-machine artifacts inventory --scope ai-cache --with-usage --json` or
`abyss-machine artifacts usage PATH --json`, then use `abyss-machine artifacts
quarantine --path PATH --verify-workload NAME --json` for reversible dry-run
planning before any mutation-specific change record.
