# Release Check Route

This route proves the public seed stays portable without publishing private host
state. It complements GitHub `Repo Validation`; it does not replace live host
evidence for installed `abyss-machine`.

## Public-Safe Gates

Run from the repository root:

```bash
PYTHONPATH=src python scripts/release_check.py --sdk-root PATH_TO_PINNED_AOA_SDK --receipt /tmp/abyss-machine-validation.json
PYTHONPATH=src python scripts/validators/public_boundary.py
PYTHONPATH=src python scripts/validators/first_run_installed_projection.py
PYTHONPATH=src python scripts/generate_contract_abi_signatures.py --check
PYTHONPATH=src python scripts/generate_scaffold_index.py --check
```

The release-check default is the full authoritative owner graph. Its exact
clean SDK pin and pytest-xdist pin fail closed, and the graph receipt binds
owner, runner, manifest, inputs, evidence, and sufficiency. Use
`PYTHONPATH=src python scripts/release_check.py --mode serial` for the
independent sequential completeness oracle or emergency rollback.

These gates must not read private captures, local indexes, model weights, or
host-only evidence.

## Live-Adapter Goal Closeout

Architecture ownership, the 20-family completion matrix, and remaining CLI-edge
classification are authoritative in
[LIVE_ADAPTERS.md](../host/LIVE_ADAPTERS.md). `SUBSYSTEM_COMMANDS.md` is a
command-surface overview and `mechanics/README.md` is a route entrypoint; neither
overrides that completion audit.

A completion claim must come after the behavior exists and must combine the
current source audit with existing evidence routes: focused public tests,
`source-fast`, generated ABI/scaffold checks, an isolated first-run installed
projection, relevant non-live host contracts, bootstrap doctor/render dry-runs,
and the canonical host quick lane. A validator must not invent the completion
boundary or convert the presence of concrete CLI IO into adapter debt.

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
ABYSS_MACHINE_TEST_SCHEDULER=serial tools/abyss-machine-test quick --json
abyss-machine enter --json
abyss-machine topology --json
abyss-machine doctor --json
abyss-machine doctor machine-report --json --no-thermal-sample
```

The host-contract wrapper preserves the direct command's exact marker
selection. It admits three-worker xdist scheduling only for `quick` and only
with exact `pytest-xdist==3.8.0`; the environment-prefixed command is the serial
rollback. `enter` is a bounded navigation surface: it may reuse explicitly
labelled owner latest/index documents and points to the full status commands.
It is not a substitute for fresh topology, mode, cooling, or change-ledger
health evidence.

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
fake-port tests for `du`/fallback size measurement, timeout-without-second-walk,
remaining-budget exhaustion without partial counts, disk usage, path status,
and home-review scanning plus live-safe compact `storage inventory --json` or
`storage status --json` summaries. Prefer light inventory for closeout; use
`storage inventory --full --json` only when the operator explicitly wants a
broader home-review scan, and never copy generated inventory payloads into the
repository.

Unix-socket publication tests must use a short isolated runtime directory when
their claim is atomic publication, private mode, or competing-path preservation.
Keep the platform path-length refusal as a separate explicit negative test so a
long checkout or pytest worker temp root cannot silently change which contract
the test exercises.

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

For memory read adapter changes, public CI should rely on fake-root and
fake-port tests for PSI/vmstat/sysctl/swap/zram/zswap/meminfo, cgroup
memory/swap attribution, process `smaps_rollup`, residency systemd snapshots,
and bounded local HTTP JSON/status transport. Live-host closeout may use compact
`memory status --json`, `memory pressure --json`, and `memory residency --json`
summaries; report only ok/class/status/counts and never raw prompts, container
environment, local model payloads, full process command lines, or full process
lists.

`memory plan --json` deliberately collects fresh pressure without the expensive
per-process attribution scan because the admission decision does not consume
those rows. Its receipt labels the omission. Use full `memory pressure --json`
when process or cgroup attribution is the question; the bounded plan must not be
presented as attribution evidence.

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

For self-awareness capabilities orchestration changes, public CI should rely on
synthetic input, contract, and persistence ports for stack/container refresh
order, bounded endpoint order, latest-read routing, the 18-row capability
matrix, ready/degraded gates, no-write behavior, ordered requirements then
capabilities writes, and write-error projection. Live-host closeout may compare
compact source and installed summaries containing only status,
capability/available counts, required-missing IDs, matrix counts, coverage
booleans, history delta, and write-error count. Do not publish raw capability
documents, endpoint bodies, model inventories, or private latest paths.

For self-awareness event-foundation changes, public CI should use synthetic
observation events, explicit clocks, host identity, and investigate/replay
latest paths. It must constrain stable dedupe order, time/service/container/
context/owner/source indexes, checkpoint trace links, bounded run IDs, event
redaction, fabric completeness, and no-mutation policy. Keep concrete event
latest reads and collect refresh at the CLI edge; do not run live collect or
investigation merely to prove these contracts.

For self-awareness status orchestration changes, public CI should rely on
synthetic latest-reader, body-closure, activation-gap-route, and paths ports for
canonical load order, complete/watch/degraded transitions, missing-latest
projection, open-potential/open-requirement counts, and public-safe latest
summaries. Live closeout may compare compact source and installed status using
only top-level/readmodel/body/stack-usage status, missing names,
capability/requirement counts, open service/requirement IDs, and
probe/cycle/validate booleans. The status adapter is read-only and requires no
live refresh merely to prove document assembly.

For self-awareness export orchestration changes, public CI should rely on
synthetic runtime, refresh, contract, and persistence ports for canonical
refresh/read order, artifact existence/schema/stat/hash/history projection,
selective artifact reload, portable manifest/handoff assembly, final-export
persistence disablement, dependency-refresh write intent, persistence routing,
and write-error projection. A complete
synthetic export must cover stack activation, resident replay, host-body,
memory-space, response trace, entity-event-document, completion-route, and
link-integrity gates without reading or writing live host state. Live closeout
may compare source and installed export summaries using only top-level `ok`,
artifact/missing/malformed counts, handoff/open requirement counts, portable
inclusion booleans, history delta, and write-error count. Do not publish raw
artifact maps, hashes, latest documents, local paths, stack payloads, or host
evidence.

For self-awareness export stack-handoff contract changes, public CI should use
already-loaded synthetic requirements, requirement-probe, closure-dossier,
coverage, activation-smoke, and exported-artifact documents plus fake contract
callbacks. It must prove empty satisfied state, open/closed requirement
classification, closure order and dependency projection, coverage impacts,
verifier matrices, current-state digest redaction, activation/use-packet
summaries, artifact-ref whitelisting, and no-execution/no-mutation policy. Live
closeout may compare only schema/status, open/closed/closure/activation/artifact
counts, open requirement IDs, policy booleans, and write-error count.

For self-awareness completion contract-core changes, public CI should rely on
synthetic readiness/path inputs for exact gate and blocker identities,
autolink count-pair completeness, read-only owner-boundary predicates,
deterministic action scores/ranks, fallback evidence refs, resource-gate
projection, stack-requirement and working-stack drilldown completeness,
deduplicated verifier plans, deterministic route order, explicit unassigned
fallback, route coverage/dependency projections, empty-state behavior, and
no-execution policy. Existing host-contract tests must still prove body-watch
and open-stack-potential semantics. Live closeout may compare only compact gate
states, blocker IDs, top action and top drilldown identity/rank/score/class,
missing/fulfilled/verifier counts, route IDs/action/verifier counts,
resource/preflight and no-execution booleans, entity/packet counts,
owner-boundary booleans, and history delta; do not publish raw action
drilldowns, entity maps, packet payloads, or host evidence.

For self-awareness completion graph changes, public CI should use synthetic
latest paths, completion actions, drilldowns, route maps, working-stack organs,
autolinks, and cycle bridge rows. It must constrain action/body/bridge entity
and event identities, document resolution, route bindings, autolink fallback,
empty state, unresolved-document fail-closed behavior, route-packet graph
joins, verifier/evidence deduplication, complete/incomplete/empty packet
states, and no-execution policy. Existing completion-audit host contracts must
preserve exact action/body/bridge/packet counts and top IDs. Live closeout may
compare only compact map/index status, summary counts, route/body/bridge IDs,
unmapped sets, top-packet cardinalities, automation booleans, and write-error
count; do not publish paths, commands, evidence refs, hashes, or raw map/packet
rows.

For self-awareness completion document changes, public CI should use synthetic
core/graph products and already-loaded status, body-closure, coverage,
resource, artifact, and open-row inputs. It must constrain backlog aggregation,
degraded/incomplete/watch/complete transitions, stack-usage versus body-closure
semantics, compact coverage whitelisting, stable field names, and no-execution
policy. Existing completion-audit host contracts must preserve the complete
summary and nested backlog/map/packet surfaces. Live closeout may compare only
final status, compact summary/backlog values, coverage row count/key whitelist,
policy booleans, and write-error count.

For self-awareness completion-audit orchestration changes, public CI should use
fake status/body/latest/preflight/artifact-ref/contract/persistence ports. It
must constrain exact input, artifact, and contract order, body-closure fallback,
write/no-write behavior, partial-write failure projection, and no heavy command
execution. Existing completion-audit host contracts must preserve the full
nested contract. Live closeout may compare only compact final/core/graph
summaries, coverage row count/key whitelist, policy booleans, and write-error
count.

For self-awareness validation-intake adapter changes, public CI should use
synthetic refresh/path/latest/history/writer ports to prove the exact optional
refresh order, cycle-aware root and latest selection, JSON/history check order,
write opt-in, and fail-closed write-error projection. Existing host-contract
fixtures should continue to exercise the complete validation rules. Live-host
closeout may report only schema/status, check/fail/warning counts, whether a
refresh was requested, and write-error count; never publish loaded documents,
history rows, checks with private data, or generated host paths.

For self-awareness validation-contract changes, public CI should prove CLI
binding of named repair/contract ports, preserve the complete non-live
self-awareness host-contract suite, run the installed synthetic self-tests with
live latest/query/refresh/write functions replaced by rejecting fakes, and
compare a compact source/installed validate envelope. Query and failure-matrix
self-test fixtures must execute their real document builders over synthetic
inputs with runtime IO denied. Conditional repairs may refresh machine-owned
readmodels; the contract module itself must not perform concrete filesystem,
systemd, network, subprocess, or persistence IO. Live closeout may report only
schema, status, check/fail/warning counts, and write-error count.

For self-awareness causal readmodel pipeline changes, public CI should use
synthetic runtime, refresh, contract, and latest/history ports for timeline,
spatial graph, context, and episodes. It must constrain event deduplication,
invalid-latest fallback, supplied-readmodel reuse, bounded context assembly,
nested write order, no-write behavior, and CLI concrete binding. Live-host
closeout must compare source and installed schema/ok/status/summary only; never
publish event rows, graph nodes or edges, context bodies, episodes, local
indexes, or machine paths.

For self-awareness causal-overlay changes, public CI should use synthetic
runtime, refresh, contract, path, and config ports for memory-space and
stack-handoff time-space projection. It must constrain supplied-document reuse
without hidden latest reads, bounded retrieval/freshness projection,
non-mutating stack-handoff timeline/graph assembly, owner routing, and CLI
concrete binding. Live-host closeout must compare source and installed schema/
ok/status/summary/policy only; never publish retrieval rows, event contexts,
graph nodes or edges, evidence refs, or machine paths.

For self-awareness query/correlation changes, public CI should use supplied
events, episodes, graph, memory-space, capabilities, stack, and index documents
plus synthetic runtime, refresh, contract, persistence, path, and config ports.
It must constrain no-hidden-read behavior, bounded scoring, query write routing,
context/service joins, SLO and baseline projection, capability fallback, the
runtime-IO-denying query fixture, no-write behavior, and CLI binding. Live-host
closeout must compare source and installed schema/ok/summary/policy only; never
publish result rows, joins,
provenance bodies, evidence refs, queries, or machine paths.

For self-awareness trace-context fallback changes, public CI should use
supplied stack-observability, requirement-probes, probe, context, timeline,
episodes, and capabilities documents plus synthetic runtime, refresh,
contract, persistence, path, and config ports. It must constrain bounded link
projection, no raw-log copying, no false stack closure, capabilities-only
fallback, next-open requirement routing, write/no-write behavior, completion,
and CLI binding. Live-host closeout may compare full source/installed documents
locally by hash, but may report only schema/ok/status, readiness booleans and
counts, and policy; never publish checks, links, samples, endpoints, evidence
refs, or machine paths.

For self-awareness episode-body-trace changes, public CI should use synthetic
episode, event, and context documents plus fake context-latest and time-bucket
ports. It must constrain supplied-context reuse, the single context fallback
read, temporal/spatial/context/host-body projection, deterministic lineage,
completion, no raw-body/context storage, and CLI binding. Live-host closeout
may compare full source/installed documents locally by hash, but may report
only completeness, temporal/spatial/context counts, and policy; never publish
context values, event/episode bodies, evidence refs, or machine paths.

For self-awareness episode-response changes, public CI should use synthetic
episode/event/investigation/replay/context/completion documents plus fake body-
trace, entity-context, activation-route, stack-route, completion, and latest-
loader ports. It must constrain synthetic-probe, activation-gap, stack-handoff,
and movement evidence branches, their exact latest-read routes, the movement
no-read path, response lineage, risk/runbook/approval policy, contract/candidate/
route completion, and CLI binding. Live-host closeout may compare full source/
installed documents locally by hash across present episode kinds, but may
report only kind counts, lineage/completion booleans, and policy; never publish
contract bodies, risks, runbooks, events, episodes, evidence refs, or paths.

For self-awareness alert-pipeline changes, public CI should use synthetic
events, context, episode classes, investigation/replay documents, response
contracts, completion predicates, refresh callbacks, and latest/history
writers. It must constrain ordinary alert, working-stack usage-gap, selected
organ-movement, stack-handoff, and synthetic-probe-marker branches; deterministic
dedupe; conditional context/episode refresh; response/body-trace depth; no-write
and write-error behavior; owner gating; and CLI binding. Live-host closeout may
compare the full source/installed alert document locally by hash, but may report
only candidate/depth/body-trace counts and policy; never publish events,
episodes, candidates, response bodies, evidence refs, or machine paths.

For self-awareness brief-pipeline changes, public CI should use synthetic
timeline/spatial/context/episode/alert/capability/probe/latest documents plus
fake refresh, memory-freshness, coverage-impact, completion, clock, and
latest/history ports. It must constrain stack-requirement priority and closed-
row filtering, closure/coverage/verifier projection, refresh order, referenced
claims, health/degradation summaries, no-write and write-error behavior,
no-mutation policy, and CLI binding. Live-host closeout must capture one input
snapshot before full source/installed hash comparison because container probes,
network errors, and freshness timestamps may change between calls; report only
brief/action-map summary counts and policy, never claims, blockers, runbooks,
evidence refs, endpoints, or paths.

For self-awareness resident-worker contract changes, public CI should use six
synthetic status/monitor/digest/micro/eval/candidate documents. It must
constrain stack-owned serving projection, monitor timers, bounded model/thermal
metadata, candidate/eval summaries, completion, action-execution denial,
non-authoritative output policy, and CLI binding. Live closeout must compare a
single fixed six-document source/installed snapshot and may report only
ok/completion/status and policy; never publish model paths, endpoints, metrics,
candidates, or eval bodies.

For self-awareness resident-cognitive contract changes, public CI should use
synthetic completion-audit/context/episode/investigation/replay/export inputs
plus fake latest, replay/export refresh, body-trace, worker-completion, and
route-issue ports. It must constrain supplied-vs-latest reads, route context,
bounded tools/hypotheses/contradictions, packet and checkpoint preservation,
stack-handoff closure-readiness ordering, dependencies, coverage impacts and
evidence refs, cycle refresh/no-refresh behavior, no-mutation policy, and CLI
binding. Live
closeout must compare fixed input snapshots and may report only completion
booleans and overlay state; never publish cognitive packets, claims, evidence,
endpoints, or paths.

For self-awareness activation-smoke pipeline changes, public CI should use
synthetic dossier/inventory/episode/previous-smoke documents plus fake latest,
refresh, clock, host identity, PID, movement-row, completion, and persistence
ports. It must constrain supplied/fallback reads, episode refresh, per-organ
coverage, summaries, no-write/write-error behavior, no-mutation policy, and CLI
binding. Live closeout must compare a fixed latest snapshot and may report only
ok/completion/row/use-packet counts and policy; never publish organ packets,
events, evidence refs, runtime identity, or paths.

For self-awareness stack-closure pipeline changes, public CI should use
synthetic capabilities/requirements/probes/activation refresh callbacks,
contract builders, ordered artifact-ref callbacks, and latest/history writers.
It must constrain probe and enriched-requirements write order, explicit-input
behavior, dossier dependency and acceptance assembly, nine artifact-ref order,
no-write behavior, and CLI binding. Live closeout may compare only schema/ok/
status/summary for requirement-probes and stack-closure-dossier; never publish
current-state bodies, checks, artifact refs, runbooks, or host paths.

For self-awareness stack-probe runtime changes, public CI should use fake HTTP,
socket, clock, path metadata, JSON loader, daily-history, and secret-pattern
ports. It must constrain bounded OpenAPI/name projection, TCP timing/error
projection, capability artifact metadata without body reads, Grafana URL and
credential redaction, external-evidence size/policy rejection, and CLI concrete
binding. Live closeout may compare capability IDs/ok/status and aggregate
summary plus external-evidence status/summary only; never publish HTTP bodies,
datasource rows, database or graph data, external evidence rows, or host paths.

For self-awareness failure-matrix changes, public CI should use fake ordered
latest reads, capabilities refresh, clock, and latest/history writer ports. It
must constrain read order, missing-capabilities fallback, current/absent/closed
requirement rows, hermetic required-row fixture completeness, malformed
detection, write opt-in, no automatic remediation, and CLI binding. Live
closeout may compare schema/
ok/status/summary/policy only; never publish failure rows, current-state bodies,
evidence refs, or host paths.

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
and concrete host/path binding at the CLI/live binding edge. Probe and cycle
engines are adapter-owned.

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
cycle stack-handoff/final result snapshots. Probe and cycle orchestration plus
their latest/history writes belong to their adapters; keep concrete host/path
binding in separate live-host checks unless the slice intentionally moves those
ports.

For self-awareness cycle readmodel guard changes, public CI should rely on
synthetic tests for open requirement-row classification, issue/guard input
projection, initial chain assembly through supplied completion predicates, and
post-export chain updates. Do not run live `self-awareness cycle` merely to
prove this adapter class; the adapter must be constrained by fake documents and
existing completion predicates. The cycle orchestration adapter binds these
builders through explicit runtime, refresh, contract, and persistence ports.

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
Keep latest reads, event refresh, episode writes, probe caller binding, and
cycle caller binding at the CLI/live binding edge.

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
activation-entry coverage predicates. Concrete paths and live callbacks remain
at the CLI binding edge; refresh order and latest/history write intent belong to
the typed autolink orchestration port. Live-host closeout may use compact
`self-awareness status --json` summaries.

For self-awareness autolink document-builder adapter changes, public CI should
rely on synthetic working-stack, coverage-audit, stack-closure, activation-smoke,
episodes, and previous-autolink documents for organ links, stack-requirement
links, state deltas, synthetic scenarios, evidence refs, summary counts, and
non-mutating policy. For orchestration changes, add fake-port scenarios for
supplied-input reuse, stale working-stack and link-integrity refresh order,
activation/episode refresh, no-write behavior, and persistence errors. Keep
concrete paths and live callback binding at the CLI edge; do not run live stack
probes merely to prove the public state machine.

For self-awareness activation contract changes, public CI should rely on
synthetic stack organs, activation entries, episodes, stack-organ-use packets,
activation-smoke rows, compact rows, and smoke documents for signal routing,
state digests, movement selection, episode identity, packet assembly,
completion, compact projection, and refresh behavior. Keep activation caller
orchestration, caller-side investigate/replay invocation, activation latest
reads, and activation latest/history writes in the activation-smoke pipeline;
the invoked investigate and replay engines belong to their orchestration
adapters. Live closeout uses a fixed latest snapshot and reports only compact
completion/count/policy facts.

For self-awareness lineage contract changes, public CI should use synthetic
chain keys, artifact refs, cycle steps, traceparents, events, replay/response/
export summaries, and fake filesystem ports. Cover complete and broken e2e
proofs, cycle-required top-level completion, machine-owned path enforcement,
and no-mutation policy. Keep concrete latest artifact metadata and path hashing
at the CLI runtime binding edge. Live closeout may evaluate a fixed snapshot and
report only row/artifact/missing-chain/completion counts and policy.

For self-awareness coverage pipeline changes, public CI should use synthetic
capabilities, requirements, probes, cycle chains, stack-closure dossiers,
working-stack organs, activation rows, artifact refs, and fake runtime/refresh/
contract ports. Cover stack-owned blockers, capability-covered absent
requirements, objective/covered/blocked planes, linkage integrity, write/no-
write behavior, closure-acceptance identity/owner/policy, summary-plane
consistency, malformed impact rejection, and no-mutation policy. Live closeout
must use one fixed latest snapshot and report only status,
row/plane/blocker counts, completion, and policy. A valid working-stack
inventory with no service-bearing organs is a stable negative control: there
are no dependent link rows to refresh, so coverage audit must not launch the
working-stack dependent refresh chain merely because an empty link readmodel is
stale.

For self-awareness requirement contract changes, public CI should use
synthetic requirement, capability, external-closure, readiness, and action-map
documents plus fake latest/clock/write/refresh ports. Cover alternate endpoint
configuration, acceptance/compatibility/negative controls, all supported
stack-owner probe families, stale probe rejection, write/no-write behavior,
secret redaction, and the no-stack-mutation policy. Keep concrete endpoint
selection, latest paths, secret scanner, clock, capabilities refresh, brief
action-map binding, and latest/history persistence at the CLI edge. Live
closeout must compare one fixed requirements/probes snapshot and report only
schema, status, open/closed counts, readiness counts, and policy.

For self-awareness cognitive contract changes, public CI should use synthetic
freshness gates, trace fallback, capability details, resource/mode snapshots,
bounded contexts, and working-stack usage-gap episodes plus fake completion
ports. Cover bounded projections, stale/resource-denied memory handoff,
multimodal non-promotion, review-only LLM escalation, governance readiness,
failure recovery, gap handoff completeness, and no-mutation policy. Keep live
latest reads, capabilities refresh, investigation execution, and persistence
in their existing orchestration owners. Live closeout may compare one fixed
capabilities/context/episode snapshot and report only schemas, completion,
bounded counts, readiness status, and policy.

For self-awareness entity-context contract changes, public CI should use
synthetic entity/event/document maps, completion route-packet indexes,
episodes, source events, body traces, and a fake latest loader. Cover malformed
and unresolved references, expected-count mismatches, supplied-vs-fallback
completion audit, bounded response selections, automation stop-lines, and
no-mutation policy. Keep map/index construction, live latest paths, response
orchestration, probes, cycles, and persistence with their existing owners.
Live closeout may evaluate a fixed completion-audit snapshot and report only
issue counts, selected entity/event/document/route counts, completion, and
policy.

For self-awareness cycle-proof contract changes, public CI should use
synthetic machine-bridge latest paths, fake artifact-ref/stat ports, fixed cycle
and probe ids, cycle-chain rows, step artifacts, failed steps, and missing-chain
lists. Cover all thirteen bridge surfaces, absent/schema/hash/machine-path
failure, mtime projection, from-zero obligations, no-execution policy, and
completion predicates. Keep probe/investigate/replay/export execution, cycle
ordering, latest writes, and persistence in cycle orchestration. Live closeout
may evaluate a fixed bridge/latest snapshot and report only row/obligation/
step counts, failed ids, completion, and policy.

For self-awareness activation-entry adapter changes, public CI should rely on
synthetic working-stack organs with supplied latest paths for activation
readiness, runbook, closure, scenario, evidence-ref, and completion predicate
coverage. Keep working-stack latest reads, dossier refresh, probe caller
binding, cycle caller binding, and all stack mutations at the CLI/live binding
edge.

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
caller-side investigate/replay invocation, stack latest reads, and route
latest/history writes at the CLI/live binding edge; investigation construction
and persistence belong to the investigation orchestration adapter, while
replay construction and persistence belong to the replay orchestration adapter.

For self-awareness activation synthetic-scenario, closure-acceptance,
activation synthetic-proof, or export-overlay adapter changes, public CI should
rely on synthetic activation entries, verifier command lists, stack source refs,
evidence refs, replay summaries, coverage rows, cycle documents, and export
documents for packet/proof/overlay assembly and completion predicates. Keep
proof-level investigate/replay caller orchestration, concrete export writes,
source latest reads, and proof latest/history writes at the CLI/live binding
edge; both invoked engines remain adapter-owned.

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

For self-awareness probe-orchestration adapter changes, public CI should use
synthetic runtime, refresh, contract, and persistence ports to prove resource
preflight fails closed before HTTP/refresh work, traced request headers,
synthetic request/context/alert/movement event order, controlled movement
episode selection, the complete 35-step chain, investigation/replay handoff,
validation after the first persistence stage, the second validation-enriched
persistence stage, no-write behavior, and write-error projection. Existing
host-contract fixtures should remain green for probe/cycle integration. Live
closeout may report only status, passed/total and failed chain keys,
movement-smoke and lineage counts, validation counts, non-mutating policy,
history-count delta, and write-error count; never publish responses, event
bodies, readmodels, checkpoint states, or private paths. A write-enabled probe
intentionally appends twice, once before validation and once after validation;
partial retry can append duplicates and is not destructively rolled back.

For self-awareness cycle-orchestration adapter changes, public CI should use
synthetic runtime, refresh, contract, filesystem, latest-reader, and
persistence ports to prove resource denial before probe, one probe invocation,
the intentional two investigate/replay passes around activation smoke, initial
chain/bridge/issue assembly, latest and bridge load dispatch, 34 initial plus
two final artifact steps, the pre-export `building` write, autolink/export
ordering, from-zero/e2e/lineage proofs, final write, no-write behavior, and
write-error projection. Existing host-contract probe/cycle fixtures should
remain green. Live closeout may report only cycle status, step/chain/proof
counts, failed step and missing-chain keys, replay/body/lineage booleans,
automatic/mutating route counts, history delta, and write-error count; never
publish artifact digests, readmodels, probe payloads, checkpoint states, or
private paths. A write-enabled cycle intentionally appends a `building` row and
a final row; retry after partial failure may duplicate rows and is not
destructively rolled back.

For self-awareness investigation-orchestration adapter changes, public CI
should use synthetic input, contract, checkpoint, module-availability, and
writer ports to prove mandatory refresh/read ordering, context and
completion-route fallback refresh, explicit/query/latest episode selection,
the canonical nine-node parent-linked graph, evidence validation, read-only
handoff policy, candidate-only conclusion, write opt-in, and ordered
write-error projection. Existing host-contract fixtures should continue to
exercise working-stack gaps, stack-handoff closure readiness, and the complete
investigate/replay loop. Live-host closeout may report only schema,
selected-episode identity, checkpoint/node and validation-failure counts,
completeness booleans, policy booleans, history-count delta, and write-error
count; never publish checkpoint states, conclusions, evidence bodies, resident
payloads, or private paths. A failed final write leaves the complete in-memory
document available with `ok=false`; retry may replace latest and may append a
duplicate history row after a partial failure.

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
abyss-machine typing status --compact --json
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
read envelopes, append-state boundary continuity, partition-local episode
replacement, fixed-point no-write behavior, source-snapshot race refusal, and
full-oracle parity. Live-host closeout may
use compact `abyss-machine nervous events-build --json`,
`abyss-machine nervous events-validate --json`,
`abyss-machine nervous episodes-build --json`, and
`abyss-machine nervous episodes-validate --json` summaries; report only
ok/schema/count/error summaries and never copy generated event/episode JSONL
records or raw source payloads into the repository.

For nervous lexical index lifecycle adapter changes, public CI should rely on
fake-port tests for source discovery/loading, derived-refresh orchestration,
SQLite write stages, status/freshness, validation fact collection, and vacuum
routing. Incremental changes must also prove full/file/append route selection,
logical document/chunk/FTS/search parity with the forced full oracle, manifest
and FTS drift fallback, attestation rejection, source-snapshot race refusal,
and atomic rollback after a partial mutation. Live-host closeout should prefer compact
`abyss-machine nervous index-status --json` and
`abyss-machine nervous index-validate --json` summaries. Run
`abyss-machine nervous index-build --full-rebuild --json` only when the slice intentionally
changes live rebuild behavior or the operator explicitly accepts the host cost;
never copy raw local index rows, source records, browser content, or generated
JSONL payloads into the repository.

Synthetic method comparisons use
`scripts/benchmark_nervous_index_dag.py` through `abyss-machine resource
launch`. Its receipts may publish fixture sizes, timings, resource peaks, and
logical digests, but not source rows or private host paths. Benchmark timing is
selection evidence only; the owner gate remains bound to correctness and
negative-control tests.

The real-session shadow uses `scripts/benchmark_nervous_pipeline_dag.py`. It
must run from a resource-admitted, isolated full snapshot of local fact history
and compare delta, forced oracle, and fixed point in one invocation. Only
aggregate receipt fields may leave the host. Logical parity across events,
episodes, and index is mandatory; a speedup with any digest mismatch is a
failed experiment, not an optimization result.

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
