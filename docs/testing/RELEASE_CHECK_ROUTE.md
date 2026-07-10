# Release Check Route

This route proves the public seed stays portable without publishing private host
state. It complements GitHub `Repo Validation`; it does not replace live host
evidence for installed `abyss-machine`.

## Public-Safe Gates

Run from the repository root:

```bash
PYTHONPATH=src python scripts/ci_gate.py --mode source-fast
PYTHONPATH=src python scripts/validators/public_boundary.py
PYTHONPATH=src python scripts/validators/first_run_installed_projection.py
PYTHONPATH=src python scripts/generate_contract_abi_signatures.py --check
PYTHONPATH=src python scripts/generate_scaffold_index.py --check
```

These gates must not read private captures, local indexes, model weights, or
host-only evidence.

## Bootstrap Dry-Runs

```bash
PYTHONPATH=src scripts/abyss-machine-bootstrap doctor --dry-run --json
PYTHONPATH=src scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
```

The dry-runs prove source projection and rendered config shape. They do not
prove current service health on a target host.

## Secret And Path Scans

Use public-boundary validation as the canonical gate, then do a human-readable
scan before publication:

```bash
rg -n 'sk-[A-Za-z0-9]|ghp_[A-Za-z0-9]|BEGIN (RSA|OPENSSH|PRIVATE) KEY|/var/lib/abyss-machine|/srv/abyss-machine|/etc/abyss-machine' \
  README.md docs config-templates env manifests mechanics schemas scripts src systemd tests tools
```

Expected findings must be public route examples, templates, or policy text, not
live payloads or credentials.

## Source/Install/Runtime Parity

When a change touches installed CLI behavior, typing/nervous, host contracts,
or live adapters, add the relevant host-side checks:

```bash
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --summary --json
PYTHONPATH=src python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"
PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json
abyss-machine enter --json
abyss-machine topology --json
abyss-machine doctor --json
abyss-machine doctor machine-report --json --no-thermal-sample
```

For a richer installed-host closeout, use module-owned runtime profiles instead
of hand-maintaining command lists in the validator script:

```bash
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile diagnostic-read --summary --json
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile ai-llm-refresh --allow-runtime-refresh --summary --json
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile storage-refresh --allow-runtime-refresh --summary --json
```

Use the full `--json` document only when investigating the parity route itself.
Closeout reports should use `--summary --json`, which keeps drift counts,
bounded samples, runtime check status, and warning/failure counts while omitting
path details, digest values, raw runtime stderr/stdout, and raw runtime JSON.

If the only live drift after a source landing is installed CLI/package modules
or compact public seed files, close it with the bounded bootstrap route:

```bash
abyss-machine changes preflight --intent "refresh installed abyss-machine code from landed source" --surface /usr/local/bin/abyss-machine --surface /usr/local/libexec/abyss-machine --surface /usr/local/share/abyss-machine --json
scripts/abyss-machine-bootstrap refresh-code --dry-run --json
scripts/abyss-machine-bootstrap refresh-code --apply --json
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --summary --json
```

Use full `install --apply` only when config templates, root creation, or systemd
unit projection must change. `refresh-code` does not render `/etc` or systemd,
and it does not authorize skipping the artifact trust gate for live defaults.
The apply command must include the admitted bundle selector for production/live
roots; `--skip-artifact-trust-gate` remains limited to isolated projection
rehearsals.

For storage apply adapter changes, public CI should rely on fake-port tests and
live-safe `storage cleanup-plan` / `storage apply --dry-run` summaries. Do not
run `storage apply --confirm` as validation unless the operator explicitly
requests that live mutation and the report stays compact.

For storage hook execution adapter changes, public CI should rely on fake-runner
tests for hook payload/env/result mapping plus live-safe `storage hooks --json`
status. Do not run `storage run-hooks ... --enforce` on a live host as
validation unless the operator explicitly requests hook execution; report only a
compact summary and never copy hook payloads or local generated evidence into
the repository.

For storage inventory measurement adapter changes, public CI should rely on
fake-port tests for `du`/fallback size measurement, disk usage, path status, and
home-review scanning plus live-safe compact `storage inventory --json` or
`storage status --json` summaries. Prefer light inventory for closeout; use
`storage inventory --full --json` only when the operator explicitly wants a
broader home-review scan, and never copy generated inventory payloads into the
repository.

For process `/proc` adapter changes, public CI should rely on synthetic proc-root
tests for stat/status/cmdline/io/cgroup/fd parsing, storage/game classification
binding, and CPU interval sampling. Live-host closeout may use compact
`processes snapshot --json` or `processes game-guard --json` summaries, but
should report counts and status only, not raw process command payloads.

For process thermal-attribution/thermal-plan adapter changes, public CI should
rely on synthetic proc-root and fake-port tests for `/proc/*/task/*/stat`
thread deltas, thermal focus CPU projection, candidate confidence, incident
classification, route-port fanout, game-guard new-work adjustment, and
observe-only policy. Live-host closeout may use compact
`processes thermal-attribution --seconds 1 --interval 0.5 --json` and
`processes thermal-plan --seconds 1 --interval 0.5 --json` summaries, but
should report only ok/classification/focus counts/candidate counts/unattended
caps and route policy status, not raw command payloads, window titles, local
paths, generated histories, or full process lists.

For memory read/orchestration adapter changes, public CI should rely on
fake-root and fake-port tests for PSI/vmstat/sysctl/swap/zram/zswap/meminfo,
cgroup memory/swap attribution, process `smaps_rollup`, residency systemd
snapshots, Podman inspect/restart routing, target snapshot assembly, local HTTP
JSON/status probes, cgroup CPU sampling, live lock behavior, and rehydrate
polling. Live-host closeout may use compact `memory status --json`, `memory
pressure --json`, `memory residency --json`, `memory orchestrate plan --json`,
`memory orchestrate idle --candidate ID --json`, and dry-run/confirmed preflight
summaries only when an operator-safe candidate exists; report only
ok/class/status/decision/counts/guard/idle summaries and never raw prompts,
container environment, local model payloads, full process command lines, full
process lists, or live restart execution output.

For process container-health adapter changes, public CI should rely on
fake-runner tests for Podman unavailable/failure/invalid-JSON behavior,
sanitized `podman ps`/`inspect` projection, label allowlisting, attention-reason
classification, and redaction. Live-host closeout may use compact
`processes containers --json` summaries, but should report status/counts only,
not raw container payloads, environment variables, create commands, or mount
contents.

For process desktop-compositor command/proc/AT-SPI adapter changes, public CI
should rely on fake-port tests for `/proc` GNOME Shell sampling, synthetic
`systemctl`/`gdbus`/`busctl`/`gsettings`/`dbus-monitor`/`wmctrl`/`xprop`/`ss`/
`ps` outputs, fake `pyatspi` registry modules, and fake bounded subprocess/
latest-fallback ports. Live-host closeout may use compact
`processes desktop-compositor --json` summaries, but should report only
ok/classification/counts/rates and observe-only policy status, not raw window
titles, process command payloads, local extension paths, or generated desktop
history.

Use a longer timeout for full doctor/machine-report refresh closeout:

```bash
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile diagnostic-refresh --allow-runtime-refresh --runtime-timeout 60 --json
```

For safe repair adapter changes, public CI should rely on fake-port tests and
read-only doctor path/status-shape checks. Runtime profiles whose names end in
`-refresh` intentionally run commands that may refresh live latest/readmodel
state and therefore require `--allow-runtime-refresh`. If `abyss-machine doctor
--repair --safe-only --json --no-thermal-sample` is run on a live host, report
only the compact repair summary and performed action names; do not copy
generated latest files or raw repair payloads into the repository.

For doctor AI/runtime status-probe changes, public CI should rely on fake-port
tests for AI facts, status, capability, TTS profile, policy, storage hygiene,
runtime snapshot, report-latest, workload stats, and timer projection. Live
closeout may use compact `abyss-machine doctor --json --no-thermal-sample` or
the diagnostic parity profiles, but should report only check counts/status and
never raw model inventory, benchmark payloads, local runtime paths beyond route
paths, generated AI latest JSON, or workload records.

For self-awareness resource-preflight or HTTP-status probe adapter changes,
public CI should rely on fake-port tests for env/meminfo/loadavg/cpu threshold
decisions, fail-closed resource-denial behavior, bounded HTTP GET request
binding, truncation, redaction, and error/status projection. Live-host closeout
may use compact `abyss-machine self-awareness status --json` summaries; run
`self-awareness probe` or `self-awareness cycle` only when the slice
intentionally changes orchestration or the operator explicitly accepts live
latest/readmodel refresh. Report status/counts/reasons only, never raw stack
responses, local latest payloads, generated event/fabric stores, browser
captures, or private host evidence.

For self-awareness latest-read adapter changes, public CI should rely on fake
latest-reader tests for spec order, schema selection, cycle latest document
dispatch, and bridge-document load dispatch. Live-host closeout may use compact
`self-awareness status --json` summaries; avoid refreshing probe/cycle
readmodels unless orchestration or concrete write ports changed.

For self-awareness body-closure status document-builder adapter changes, public
CI should rely on synthetic heartbeat, reaction, response, doctor, topology,
stack-bridge, change-index, nervous-brief, and backup documents for watch-source
classification, summary counts, backup blocker projection, and non-mutating
policy. Keep latest reads and backup-plane policy callbacks at the CLI/live
binding edge.

For self-awareness status open-potential/open-requirement row-builder adapter
changes, public CI should rely on synthetic autolink rows, activation dossier
rows, activation-smoke rows, requirements, and stack-closure rows for row
classification, handoff policy, activation-gap route callback binding, and
stack-owner requirement projection. Keep latest reads, status document assembly,
and live probe/cycle orchestration at the CLI/live binding edge.

For self-awareness latest artifact-ref adapter changes, public CI should rely on
fake latest-loader, path-exists, path-hash, and history-path ports for schema
projection, missing artifact behavior, summary passthrough, and hash gating.
Keep concrete filesystem paths and live artifact hash/history binding at the
CLI/live binding edge.

For self-awareness artifact evidence-ref adapter changes, public CI should rely
on fake path-exists, path-stat, and mtime-format ports for public-safe evidence
ref shape, missing-stat behavior, summary passthrough, and freshness/truth
flags. Keep concrete filesystem path/stat binding at the CLI/live binding edge.

For self-awareness freshness-gate adapter changes, public CI should rely on fake
path-exists, parse-time, clock, and artifact-ref ports for age calculation,
fresh/stale/missing status, evidence-ref filtering, and maintenance/details
projection. Keep concrete path, clock, parser, and artifact-ref binding at the
CLI/live binding edge.

For self-awareness cycle artifact-evidence adapter changes, public CI should
rely on fake-port tests for latest-artifact existence/stat/hash/mtime
projection, missing artifact behavior, bridge steps with `requires_ok=false`,
and extra evidence merging. Live-host closeout may use compact
`self-awareness status --json` summaries; avoid running `self-awareness cycle`
unless orchestration itself changed or the operator accepts live latest/readmodel
refresh.

For self-awareness cycle artifact-step manifest changes, public CI should rely
on synthetic tests for step order, command strings, document source grouping,
required-vs-nonblocking step policy, and extra evidence routing. Keep concrete
path constants and live latest document loading at the CLI edge; do not run live
`self-awareness cycle` merely to prove manifest assembly.

For self-awareness probe/cycle document-builder adapter changes, public CI
should rely on synthetic shape tests for resource-denied documents, probe result
documents, movement-smoke summaries, cycle partial/building snapshots, and
cycle stack-handoff/final result snapshots. Keep latest/history writes,
concrete stack paths, and probe/cycle orchestration in separate live-host checks
unless the slice intentionally moves those ports.

For self-awareness cycle readmodel guard changes, public CI should rely on
synthetic tests for open requirement-row classification, issue/guard input
projection, initial chain assembly through supplied completion predicates, and
post-export chain updates. Do not run live `self-awareness cycle` merely to
prove this adapter class; the adapter must be constrained by fake documents and
existing completion predicates while CLI remains responsible for orchestration.

For self-awareness working-stack source-inventory adapter changes, public CI
should rely on fake-root/fake-port tests for stack service-name normalization,
service-selection policy JSON projection, compose service discovery, stack
service-root inventories, bounded model-root tags, and read-error behavior.
Live-host closeout may use compact `self-awareness status --json` or
`self-awareness working-stack --json` summaries only when needed; report counts,
status, and owner-boundary facts, not raw stack paths, model inventories,
generated readmodels, stack response bodies, or private host evidence.

For self-awareness working-stack inventory assembly/readmodel adapter changes,
public CI should rely on synthetic documents and fake ports for container
service extraction, PID-alive projection, supplied container-tool/TTS probes,
AI model-root bridge status, service-selection policy status, evidence refs,
usage-gap classification, and summary counts. Keep concrete stack path
discovery, endpoint URL construction, subprocess/socket runners, AI latest
loading, and latest/history writes at the CLI/live binding edge.

For self-awareness working-stack movement/event assembly adapter changes,
public CI should rely on synthetic inventory documents and synthetic previous
activation-smoke rows for signal/source routing, state-digest comparison,
movement selection, severity, fabric correlation keys, event evidence refs, and
read-only/no-mutation policy. Keep previous latest reads, concrete
working-stack latest paths, and host identity binding at the CLI/live binding
edge; do not run live `self-awareness collect` merely to prove event assembly.

For self-awareness working-stack usage-gap episode adapter changes, public CI
should rely on synthetic working-stack documents and synthetic working-stack
events with supplied latest paths for episode identity, affected nodes,
confidence, working_stack_gap packets, evidence refs, and non-mutating policy.
Keep latest reads, event refresh, episode writes, and probe/cycle execution at
the CLI/live binding edge.

For self-awareness working-stack link-integrity adapter changes, public CI
should rely on synthetic working-stack, events, timeline, spatial graph,
context, episodes, and coverage-gap documents for matrix rows, match/freshness
predicates, usage-gap coverage accounting, evidence refs, and read-only policy.
Keep concrete latest reads and dependency-refresh orchestration at the CLI/live
binding edge. Live-host closeout may use compact `self-awareness status --json`
or `self-awareness working-stack --json` summaries when needed.

For self-awareness autolink predicate adapter changes, public CI should rely on
synthetic autolink documents, working-stack link rows, episodes, and stack
closure dossiers for row-state projection, completion, episode coverage, and
activation-entry coverage predicates. Keep concrete latest reads, refresh
orchestration, and latest/history writes at the CLI/live binding edge.
Live-host closeout may use compact `self-awareness status --json` summaries.

For self-awareness autolink document-builder adapter changes, public CI should
rely on synthetic working-stack, coverage-audit, stack-closure, activation-smoke,
episodes, and previous-autolink documents for organ links, stack-requirement
links, state deltas, synthetic scenarios, evidence refs, summary counts, and
non-mutating policy. Keep stale checks, dependency refresh orchestration,
latest reads, and latest/history writes at the CLI/live binding edge.

For self-awareness activation-smoke predicate adapter changes, public CI should
rely on synthetic stack-organ-use packets, activation-smoke rows, compact rows,
smoke documents, and activation entries for completion, compact projection, and
refresh predicates. Keep actual investigate execution, caller-side replay
invocation, activation latest reads, and activation latest/history writes at
the CLI/live binding edge; the replay engine itself belongs to the replay
orchestration adapter.

For self-awareness activation-entry adapter changes, public CI should rely on
synthetic working-stack organs with supplied latest paths for activation
readiness, runbook, closure, scenario, evidence-ref, and completion predicate
coverage. Keep working-stack latest reads, dossier refresh, probe/cycle
execution, and all stack mutations at the CLI/live binding edge.

For self-awareness activation-dossier document-builder adapter changes, public
CI should rely on synthetic working-stack documents, supplied latest paths, and
supplied artifact refs for activation order, closure/scenario matrices, handoff,
summary, evidence refs, and policy coverage. Keep working-stack latest reads,
artifact hash collection, refresh fallback, and latest/history writes at the
CLI/live binding edge.

For self-awareness activation-gap or stack-requirement handoff route adapter
changes, public CI should rely on synthetic working-stack gap documents,
activation-smoke row summaries, stack closure packets, stack replay summaries,
and fake completion ports for route assembly and completion predicates. Keep
actual investigate execution, caller-side replay invocation, stack latest
reads, and route latest/history writes at the CLI/live binding edge; replay
construction and replay persistence belong to the replay orchestration adapter.

For self-awareness activation synthetic-scenario, closure-acceptance,
activation synthetic-proof, or export-overlay adapter changes, public CI should
rely on synthetic activation entries, verifier command lists, stack source refs,
evidence refs, replay summaries, coverage rows, cycle documents, and export
documents for packet/proof/overlay assembly and completion predicates. Keep
actual proof investigate/replay orchestration, concrete export writes, source
latest reads, and proof latest/history writes at the CLI/live binding edge;
the invoked replay engine remains adapter-owned.

For self-awareness systemd observation adapter changes, public CI should rely
on fake command, unit-state, property, hostname, and event-builder ports for
user/system discovery, static/discovered deduplication, timer/service state
normalization, inactive-service filtering, evidence refs, and explicit
read-only resource projection. Live-host closeout may report only timer/service
counts, categories, event validity, and read-only posture. Never publish unit
payloads, environment values, command output, or private fragment paths, and do
not start, stop, enable, disable, reload, or restart units as validation.

For self-awareness collect-input adapter changes, public CI should prove the
exact latest/live acquisition order with fake ports, required path/schema
selection, supplied working-stack reuse, refresh fallback, stack-provided
execution candidates, bounded Alertmanager routing, and the 15-minute LogQL
window from a fake clock. Live-host closeout may run `self-awareness collect`
and report only schema/status, event and invalid counts, degraded-source names,
scheduler/service counts, and owner-boundary booleans. Do not publish latest
documents, query responses, event bodies, runtime inventories, or private paths.

For self-awareness collect-assembly adapter changes, public CI should use
synthetic input documents and supplied contract ports to prove required path
binding, event/fabric document assembly, duplicate handling, correlation-index
handoff, required-versus-optional degradation, collector summaries, and the
read-only owner boundary without writing latest/history/index state. Live-host
closeout may report only schema/status, event and invalid counts,
degraded-source names, scheduler/service counts, and owner-boundary booleans.
Do not publish assembled events, collector payloads, query responses, or local
paths.

For self-awareness collect-persistence adapter changes, public CI should prove
the exact events-latest, event-history, collect-latest, collect-history, and
index-latest attempt order through fake ports, including continued attempts and
ordered error projection after partial failures. A temp-root test should also
exercise the shared atomic JSON and locked JSONL concrete writer. Live-host
closeout may report only before/after history counts, latest schemas, event
count, and write-error count. History is append-only; recovery from a partial
failure is a bounded retry that may duplicate records already appended, not a
destructive rollback.

For self-awareness replay-orchestration adapter changes, public CI should use a
synthetic investigation/checkpoint chain and fake latest/write ports to prove
thread selection, canonical node order, parent continuity, divergence
reporting, handoff/working-stack/resident/body state preservation, resume and
failure-recovery envelopes, write opt-in, and write-error projection. Existing
host-contract fixtures should continue to exercise the full nine-node chain and
stack-handoff closure-readiness replay. Live-host closeout may report only
schema, checkpoint/divergence counts, replayability booleans, policy booleans,
history-count delta, and write-error count; never publish checkpoint states,
conclusions, evidence bodies, or private paths.

For self-awareness working-stack runtime-probe adapter changes, public CI should
rely on fake-port tests for HTTP JSON/status probe routing, TCP connect
success/failure envelopes, `podman exec` container HTTP probe projection,
expected-status success mapping, subprocess failure redaction, runtime smoke
stdout/stderr hashing, and TTS smoke sidecar/WAV artifact projection without
storing raw text or audio. Live-host closeout may use compact
`self-awareness working-stack --json` summaries only when needed; report
service/probe counts, artifact presence, and statuses, never response bodies,
stack payloads, container stdout/stderr, sidecar text, audio payloads, browser
captures, or local stack secrets.

For typing/nervous changes, prefer bounded JSON status and validation commands:

```bash
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile typing-nervous-refresh --allow-runtime-refresh --json
abyss-machine typing status --json
abyss-machine typing validate --json
abyss-machine nervous status --json
abyss-machine nervous quality-audit --json
```

For nervous source-policy adapter changes, public CI should rely on fake-port
tests for config/default merge reads, latest writes, source-state reads/writes,
and source-enable/source-disable orchestration through lookup/state/write/audit/
clock ports. Live-host closeout should use compact `abyss-machine nervous
sources-list --json`, `abyss-machine nervous source-status SOURCE --json`, and
`abyss-machine nervous capture-status --json` summaries only. Do not run
`source-enable` or `source-disable` as validation unless the operator explicitly
requests that live source-state mutation, and never report raw browser content,
typed text, clipboard material, source-state payloads, or generated private
evidence.

For nervous status readmodel adapter changes, public CI should rely on fake-port
tests for policy/source/privacy projection, latest-document summaries, systemd
unit projection, index-count binding, today counters, process-latest summaries,
and status latest/index write routing. Live-host closeout may use compact
summaries from `abyss-machine nervous status --json` and
`abyss-machine nervous quality-audit --json`; report only
ok/phase/warning/count summaries and never copy generated latest documents,
source-state payloads, browser content, local index contents, or private host
evidence into the repository.

For nervous quality-audit adapter changes, public CI should rely on fake-port
tests for refresh orchestration, validation/status/capture/privacy/source/timer
input collection, browser-latest read handling, redaction smoke projection,
missing-index projection, and quality latest/history write routing. Live-host
closeout may use compact `abyss-machine nervous quality-audit --json`
summaries only: schema, return code, ok/status, fail/warning/check counts, and
bounded refresh/result counts. Do not publish generated quality latest/history
documents, browser-content payloads, redaction sample input, source-state
payloads, or local index contents.

For nervous privacy adapter changes, public CI should rely on fake-port tests
for privacy config/state reads, state write-error projection, audit JSONL append
routing, latest writes, status input assembly, and privacy-set orchestration.
Live-host closeout may use compact `abyss-machine nervous privacy-status --json`
and `abyss-machine nervous quality-audit --json` summaries only: schema, return
code, ok/status, pause/private-mode booleans, and fail/warning/check counts. Do
not publish privacy state documents, audit records, generated latest payloads,
source-state payloads, browser content, or local index contents.

For nervous capture-status adapter changes, public CI should rely on fake-port
tests for capture/browser latest reads, path-existence checks, private-root size
summaries, screenshot PNG counts, browser-content JSONL counts, browser route
path projection, and operator control command projection. Live-host closeout may
use compact `abyss-machine nervous capture-status --json` summaries; report only
ok/latest-error/count/byte totals and never publish generated latest payloads,
browser content, screenshots, private capture roots, or source-state payloads.
Do not run live capture as validation for a readmodel-only capture-status seam.

For nervous event/episode file/write adapter changes, public CI should rely on
fake-root tests for JSONL root reads, derived-record replacement writes, latest
read envelopes, and build/validate latest write routing. Live-host closeout may
use compact `abyss-machine nervous events-build --json`,
`abyss-machine nervous events-validate --json`,
`abyss-machine nervous episodes-build --json`, and
`abyss-machine nervous episodes-validate --json` summaries; report only
ok/schema/count/error summaries and never copy generated event/episode JSONL
records or raw source payloads into the repository.

For nervous lexical index lifecycle adapter changes, public CI should rely on
fake-port tests for source discovery/loading, derived-refresh orchestration,
SQLite write stages, status/freshness, validation fact collection, and vacuum
routing. Live-host closeout should prefer compact
`abyss-machine nervous index-status --json` and
`abyss-machine nervous index-validate --json` summaries. Run a full
`abyss-machine nervous index-build --json` only when the slice intentionally
changes live rebuild behavior or the operator explicitly accepts the host cost;
never copy raw local index rows, source records, browser content, or generated
JSONL payloads into the repository.

For nervous semantic-maintain orchestration adapter changes, public CI should
rely on fake-port tests for source-index pre-refresh assessment, dry-run/launch
resource-gate outcomes, semantic lock refusal, batch-policy memory-plan fan-in,
deferred-build stdout parsing, and maintain latest/history routing. Live-host
closeout should prefer compact `abyss-machine nervous semantic-maintain
--dry-run --json` and `abyss-machine nervous semantic-status --json` summaries.
Run `abyss-machine nervous semantic-maintain --json` or
`abyss-machine nervous semantic-build --json` only when the slice intentionally
changes live rebuild behavior or the operator explicitly accepts the host cost;
never copy raw local vectors, source chunks, model paths beyond route summaries,
embedding text, OpenVINO cache payloads, or generated semantic DB contents into
the repository.

For nervous semantic-build window execution adapter changes, public CI should
rely on fake-port tests for pending/reuse classification, reused-vector insert
routing, embedding-window fallback batch attempts, progressive vector insert,
failed-build receipt recording, command/refusal/source-reload document shaping,
successful-build finalize routing, and compile-cache summary projection.
Live-host closeout should prefer `abyss-machine nervous semantic-status --json`
plus a bounded source dry-run/refusal path when available; run
`abyss-machine nervous semantic-build --max-chunks N --batch-size 1 --device CPU
--rebuild --json` only when the slice intentionally changes live rebuild
behavior or the operator explicitly accepts the host cost. Never copy raw
embedding text, vectors, source chunks, local semantic DB rows, OpenVINO cache
payloads, or generated semantic latest files into the repository.

For nervous semantic-search adapter changes, public CI should rely on fake-port
tests for limit bounding, global-pause refusal, missing-db/no-vector documents,
query-vector policy/error projection, and vector-search dispatch. Live-host
closeout may use compact `abyss-machine nervous semantic-status --json` and
`abyss-machine nervous semantic-search --query TEXT --json` summaries, but
should report only ok/result counts, freshness, and policy-denial status. Never
copy raw search results, snippets, titles, embedding text, vectors, source
chunks, local semantic DB rows, generated latest files, or OpenVINO cache
payloads into the repository.

For nervous semantic-eval adapter changes, public CI should rely on fake-port
tests for probe/check/result document assembly, eval-query embedding fanout,
lexical/semantic search dispatch, policy-denial projection, and eval
latest/history routing. Live-host closeout may use compact
`abyss-machine nervous semantic-status --json` and
`abyss-machine nervous semantic-eval --json` summaries, but should report only
ok/status/check counts/warning counts and never copy raw search results,
embedding text, vectors, source chunks, generated eval latest files, local
semantic DB rows, or OpenVINO cache payloads into the repository.

For nervous rerank-eval adapter changes, public CI should rely on fake-port
tests for fixed eval-query dispatch, force-policy fanout, eval document
assembly through the rerank contract module, and eval latest/history routing.
Live-host closeout may use compact
`abyss-machine nervous rerank-eval --json` and, if useful,
`abyss-machine nervous recall --mode hybrid --query TEXT --json` summaries, but
should report only ok/status/check counts/warning counts/result counts and
policy-denial status. Never copy raw rerank results, snippets, titles, source
payloads, neural debug input/output files, generated latest/history files, local
index rows, semantic DB rows, vectors, model paths beyond route summaries, or
OpenVINO cache payloads into the repository.

Report live-host results separately from public CI. Do not copy the underlying
`/var/lib/abyss-machine`, `/srv/abyss-machine`, browser, typing, transcript,
index, cache, or model-weight contents into the repository.

For nervous clipboard adapter changes, public CI should rely on fake-port tests
for source-policy refusal, Wayland socket readiness, `wl-paste` MIME/text command
results, redacted payload projection, and Wayland backend failure-to-skip
mapping. Live-host closeout may use compact `abyss-machine nervous
source-status clipboard --json`, `abyss-machine nervous sources-list --json`,
and `abyss-machine nervous capture-status --json` summaries only. Do not run
ad hoc clipboard reads as validation, and never report raw clipboard text,
binary payloads, MIME-sensitive content, or generated private source payloads.

For nervous browser-content store adapter changes, public CI should rely on
fake-port and temporary-root tests for local-day JSONL path projection,
record-from-page callback binding, duplicate suppression, append/latest write
routing, and write-error projection. Live-host closeout may use compact
`abyss-machine nervous capture-status --json` and `abyss-machine nervous
source-status browser_active_tab --json` summaries only. Do not force AT-SPI,
BiDi, browser history, or active-tab capture as validation unless that runtime
adapter is the touched surface, and never copy browser text, URLs, generated
browser-content JSONL, latest payloads, or private capture roots into the repo.

For nervous browser-content AT-SPI capture runtime adapter changes, public CI
should rely on fake `Atspi` trees, fake `/proc` roots, fake store callbacks, and
fake latest writers for settings, Firefox env readiness, accessibility-tree
document discovery, text extraction, sensitive-field skips, no-Firefox skip
behavior, import failure behavior, capture result assembly, and latest write
routing. Live-host closeout may use compact source-side
`abyss-machine nervous capture-status --json` and
`abyss-machine nervous source-status browser_active_tab --json` summaries. Do
not report raw browser text, URLs, generated browser-content JSONL, latest
payloads, window titles, or private capture roots.

For nervous browser-content BiDi/WebSocket capture runtime adapter changes,
public CI should rely on fake sockets, fake WebSocket connect ports, fake BiDi
call ports, fake store callbacks, fake summary callbacks, and fake latest
writers for URL parsing, frame JSON encoding/decoding, receive routing,
remote-value decode, context filtering, capture result assembly, redacted error
URL projection, and latest routing. Live-host closeout may use compact
`abyss-machine nervous capture-status --json`,
`abyss-machine nervous source-status browser_active_tab --json`, and a bounded
local BiDi port availability check. Do not force browser launch, do not force
BiDi capture when the port is closed, and never report raw browser text, URLs,
generated browser-content JSONL, latest payloads, window titles, or private
capture roots.

For nervous browser-content browser-history adapter changes, public CI should
rely on synthetic Firefox `places.sqlite` fixtures, fake home/profile roots,
fake temp roots, fake history-row ports, fake content-record callbacks, and
redacted URL/title assertions for profile discovery, copied SQLite recency
queries, cutoff/limit behavior, duplicate URL suppression, temp cleanup,
history fact assembly, and virtual-source summary routing. Live-host closeout
may use compact `abyss-machine nervous source-status browser_active_tab --json`
and `abyss-machine nervous capture-status --json` summaries only. Do not report
raw browser history URLs, query strings, fragments, titles, generated
browser-content JSONL, latest payloads, window titles, or private profile paths.

For nervous retention filesystem/apply adapter changes, public CI should rely on
fake-root/fake-writer tests for route-root scanning, symlink-tail blockers,
protected/latest candidate refusal, dry-run-first confirmed unlink, mutation
receipts, and latest/validate write routing. Live-host closeout may use compact
`abyss-machine nervous retention-plan --json`,
`abyss-machine nervous retention-apply --dry-run --json`, and
`abyss-machine nervous retention-validate --json` summaries only. Do not run
`abyss-machine nervous retention-apply --confirm` as validation unless the operator explicitly
requests that deletion; report only counts/status/errors and never copy private
candidate paths, captures, browser content, or generated retention payloads into
the repository.

## Completion Rule

A release or portability claim is only true when:

- public-safe gates pass on source;
- bootstrap dry-runs prove projection shape;
- generated ABI/scaffold surfaces are current;
- source/install projection checks cover the changed entrypoints;
- the compact source/install/runtime parity summary is either green after
  install or explicitly reported as advisory drift before install;
- relevant host quick checks are either green or explicitly named as skipped;
- residual live adapter debt is named in docs, not hidden behind green tests.
