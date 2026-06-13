# Abyss Machine Commands

## Health

```bash
abyss-machine doctor
abyss-machine doctor --json
abyss-machine doctor --repair --safe-only --json
abyss-machine doctor report --markdown
abyss-machine doctor machine-report --json
abyss-machine doctor machine-report --markdown
abyss-machine doctor validate --json
abyss-machine status --json
abyss-machine bridge --json
abyss-machine docs audit --json
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine test quick --json
abyss-machine test full --json
abyss-machine test live --json
abyss-machine test long --json
abyss-machine test manual --json
abyss-machine storage status --json
abyss-machine memory status --json
abyss-machine memory plan --json
abyss-machine memory orchestrate plan --json
abyss-machine memory orchestrate idle --candidate ID --json
abyss-machine memory orchestrate confirm --candidate ID --operator NAME --reason TEXT --acknowledge-protected --dry-run --json
abyss-machine memory orchestrate apply --candidate ID --dry-run --json
abyss-machine memory orchestrate apply --candidate ID --confirm --json
abyss-machine memory orchestrate apply --candidate ID --confirm --execute-live --acknowledge-live-restart --operator NAME --reason TEXT --json
abyss-machine resource status --json
abyss-machine resource orchestrator --json
abyss-machine resource plan --class heavy --kind ai --json
abyss-machine self-awareness status --json
abyss-machine self-awareness requirements --json
abyss-machine self-awareness requirement-probes --json
abyss-machine self-awareness stack-closure-dossier --json
abyss-machine self-awareness failure-matrix --json
abyss-machine self-awareness probe --json
abyss-machine self-awareness cycle --json
abyss-machine self-awareness validate --json
abyss-machine heartbeats pulse --json
abyss-machine heartbeats validate --json
abyss-machine reactions --json
abyss-machine reactions validate --json
abyss-machine responses --json
abyss-machine responses validate --json
abyss-machine processes snapshot --json
abyss-machine processes game-guard --json
abyss-machine processes thermal-attribution --seconds 3 --interval 0.5 --json
abyss-machine processes thermal-plan --seconds 3 --interval 0.5 --json
abyss-machine processes desktop-compositor --seconds 3 --interval 0.5 --json
abyss-machine nervous status --json
abyss-machine nervous quality-audit --json
abyss-machine nervous rerank-eval --json
```

## Machine Entry And Topology

```bash
abyss-machine enter --json
abyss-machine docs paths --json
abyss-machine docs audit --json
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine topology --json
abyss-machine topology paths --json
abyss-machine topology validate --json
abyss-machine topology validate --strict --json
abyss-machine topology audit --json
abyss-machine graph --json
abyss-machine graph query --node ai --json
abyss-machine graph validate --json
abyss-machine maps --json
abyss-machine maps paths --json
abyss-machine maps policy --json
abyss-machine maps build --json
abyss-machine maps query --axis by-freshness --query semantic --json
abyss-machine maps packet --axis by-eval-packet --reader-profile proof-context --json
abyss-machine maps validate --json
abyss-machine rag --json
abyss-machine rag paths --json
abyss-machine rag policy --json
abyss-machine rag refresh --query TEXT --json
abyss-machine rag trace --query TEXT --json
abyss-machine rag latest --json
abyss-machine rag eval --json
abyss-machine rag validate --json
abyss-machine doctor paths --json
abyss-machine doctor machine-report --json
abyss-machine doctor validate --json
abyss-machine stack-bridge --json
abyss-machine stack-bridge paths --json
abyss-machine stack-bridge export --json
abyss-machine stack-bridge latest --json
abyss-machine stack-bridge validate --json
abyss-machine stack-bridge observability --json
abyss-machine self-awareness paths --json
abyss-machine self-awareness status --json
abyss-machine self-awareness capabilities --json
abyss-machine self-awareness requirements --json
abyss-machine self-awareness requirement-probes --json
abyss-machine self-awareness stack-closure-dossier --json
abyss-machine self-awareness collect --json
abyss-machine self-awareness query --query TEXT --json
abyss-machine self-awareness correlate --json
abyss-machine self-awareness timeline --json
abyss-machine self-awareness spatial-graph --json
abyss-machine self-awareness context --json
abyss-machine self-awareness episodes --json
abyss-machine self-awareness alerts --json
abyss-machine self-awareness investigate --query TEXT --json
abyss-machine self-awareness replay --json
abyss-machine self-awareness brief --json
abyss-machine self-awareness failure-matrix --json
abyss-machine self-awareness probe --json
abyss-machine self-awareness cycle --json
abyss-machine self-awareness export --json
abyss-machine self-awareness validate --json
abyss-machine modes --json
abyss-machine mode paths --json
abyss-machine mode policy --json
abyss-machine mode plan --json
abyss-machine mode validate --json
abyss-machine changes paths --json
abyss-machine changes status --json
abyss-machine changes index --json
abyss-machine changes latest --json
abyss-machine changes preflight --intent TEXT --surface SURFACE --json
abyss-machine changes record --id ID --title TITLE --intent TEXT --surface SURFACE --json
abyss-machine changes close --id ID --decision-review existing --decision-ref DECISION --note "validated and complete" --json
abyss-machine storage validate --json
abyss-machine memory validate --json
abyss-machine resource validate --json
abyss-machine heartbeats pulse --json
abyss-machine heartbeats paths --json
abyss-machine heartbeats validate --json
abyss-machine reactions --json
abyss-machine reactions paths --json
abyss-machine reactions validate --json
abyss-machine responses --json
abyss-machine responses paths --json
abyss-machine responses validate --json
abyss-machine ai validate --json
abyss-machine cooling validate --json
abyss-machine mode validate --json
abyss-machine processes validate --json
abyss-machine nervous validate --json
abyss-machine dictation validate --json
```

Persistent paths:

```bash
{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md
{{ABYSS_MACHINE_ETC}}/DOCS.md
{{ABYSS_MACHINE_ETC}}/DESIGN.md
{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md
{{ABYSS_MACHINE_ETC}}/ROADMAP.md
{{ABYSS_MACHINE_ETC}}/CHANGELOG.md
{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md
{{ABYSS_MACHINE_ETC}}/decisions/README.md
{{ABYSS_MACHINE_ETC}}/decisions/TEMPLATE.md
{{ABYSS_MACHINE_ETC}}/agents-mesh.json
{{ABYSS_MACHINE_SRV}}/DESIGN.md
{{ABYSS_MACHINE_SRV}}/design/AGENTS.md
{{ABYSS_MACHINE_STATE}}/topology/AGENTS.md
{{ABYSS_MACHINE_STATE}}/topology/latest.json
{{ABYSS_MACHINE_STATE}}/topology/index.json
{{ABYSS_MACHINE_STATE}}/topology/validate/latest.json
{{ABYSS_MACHINE_STATE}}/topology/audit/latest.json
{{ABYSS_MACHINE_STATE}}/changes/AGENTS.md
{{ABYSS_MACHINE_STATE}}/changes/index.json
{{ABYSS_MACHINE_STATE}}/changes/latest.json
{{ABYSS_MACHINE_STATE}}/changes/preflight/latest.json
{{ABYSS_MACHINE_STATE}}/changes/active/CHANGE_ID/
{{ABYSS_MACHINE_STATE}}/changes/closed/CHANGE_ID/
{{ABYSS_MACHINE_STATE}}/changes/history/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/graph/latest.json
{{ABYSS_MACHINE_STATE}}/graph/index.json
{{ABYSS_MACHINE_STATE}}/graph/validate/latest.json
{{ABYSS_MACHINE_ETC}}/MAPS.md
{{ABYSS_MACHINE_ETC}}/maps-policy.json
{{ABYSS_MACHINE_STATE}}/maps/START.md
{{ABYSS_MACHINE_STATE}}/maps/latest.json
{{ABYSS_MACHINE_STATE}}/maps/index.json
{{ABYSS_MACHINE_STATE}}/maps/validate/latest.json
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-context-refresh.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-context-refresh.timer
{{ABYSS_MACHINE_STATE}}/rag/AGENTS.md
{{ABYSS_MACHINE_STATE}}/rag/latest.json
{{ABYSS_MACHINE_STATE}}/rag/index.json
{{ABYSS_MACHINE_STATE}}/rag/traces/latest.json
{{ABYSS_MACHINE_STATE}}/rag/evals/latest.json
{{ABYSS_MACHINE_STATE}}/rag/refresh/latest.json
{{ABYSS_MACHINE_STATE}}/rag/validate/latest.json
{{ABYSS_MACHINE_STATE}}/doctor/AGENTS.md
{{ABYSS_MACHINE_STATE}}/doctor/latest.json
{{ABYSS_MACHINE_STATE}}/doctor/reports/latest.md
{{ABYSS_MACHINE_STATE}}/doctor/machine-report/latest.json
{{ABYSS_MACHINE_STATE}}/doctor/machine-report/latest.md
{{ABYSS_MACHINE_STATE}}/doctor/validate/latest.json
{{ABYSS_MACHINE_STATE}}/doctor/operator-required/etc/doctor-policy.json
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-doctor.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-doctor.timer
{{ABYSS_MACHINE_ETC}}/stack-bridge.json
{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md
{{ABYSS_MACHINE_ETC}}/SELF-AWARENESS.md
{{ABYSS_MACHINE_STATE}}/stack-bridge/AGENTS.md
{{ABYSS_MACHINE_STATE}}/stack-bridge/latest.json
{{ABYSS_MACHINE_STATE}}/stack-bridge/validate/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/AGENTS.md
{{ABYSS_MACHINE_STATE}}/self-awareness/index.json
{{ABYSS_MACHINE_STATE}}/self-awareness/capabilities/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/requirements/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/requirement-probes/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/failure-matrix/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/events/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/collect/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/query/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/correlation/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/timeline/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/spatial-graph/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/context/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/episodes/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/alerts/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/investigate/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/replay/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/brief/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/probe/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/cycle/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/export/latest.json
{{ABYSS_MACHINE_STATE}}/self-awareness/validate/latest.json
{{ABYSS_MACHINE_STATE}}/docs/latest.json
{{ABYSS_MACHINE_STATE}}/docs/index.json
{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json
{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/latest.json
{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json
{{ABYSS_MACHINE_STATE}}/docs/audit/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_ETC}}/mode-policy.json
{{ABYSS_MACHINE_STATE}}/mode/AGENTS.md
{{ABYSS_MACHINE_STATE}}/mode/index.json
{{ABYSS_MACHINE_STATE}}/mode/latest.json
{{ABYSS_MACHINE_STATE}}/mode/plans/latest.json
{{ABYSS_MACHINE_STATE}}/mode/validate/latest.json
{{ABYSS_MACHINE_ETC}}/memory-policy.json
{{ABYSS_MACHINE_STATE}}/memory/AGENTS.md
{{ABYSS_MACHINE_STATE}}/memory/index.json
{{ABYSS_MACHINE_STATE}}/memory/latest.json
{{ABYSS_MACHINE_STATE}}/memory/pressure/latest.json
{{ABYSS_MACHINE_STATE}}/memory/processes/latest.json
{{ABYSS_MACHINE_STATE}}/memory/plan/latest.json
{{ABYSS_MACHINE_STATE}}/memory/validate/latest.json
{{ABYSS_MACHINE_ETC}}/resource-policy.json
{{ABYSS_MACHINE_STATE}}/resource/AGENTS.md
{{ABYSS_MACHINE_STATE}}/resource/index.json
{{ABYSS_MACHINE_STATE}}/resource/latest.json
{{ABYSS_MACHINE_STATE}}/resource/plans/latest.json
{{ABYSS_MACHINE_STATE}}/resource/runs/latest.json
{{ABYSS_MACHINE_STATE}}/resource/orchestrator/latest.json
{{ABYSS_MACHINE_STATE}}/resource/validate/latest.json
{{ABYSS_MACHINE_STATE}}/heartbeats/AGENTS.md
{{ABYSS_MACHINE_STATE}}/heartbeats/latest.json
{{ABYSS_MACHINE_STATE}}/heartbeats/validate/latest.json
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-heartbeat.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-heartbeat.timer
{{ABYSS_MACHINE_STATE}}/reactions/AGENTS.md
{{ABYSS_MACHINE_STATE}}/reactions/latest.json
{{ABYSS_MACHINE_STATE}}/reactions/validate/latest.json
{{ABYSS_MACHINE_STATE}}/responses/AGENTS.md
{{ABYSS_MACHINE_STATE}}/responses/latest.json
{{ABYSS_MACHINE_STATE}}/responses/validate/latest.json
```

Current policy:

```bash
machine entry: use `abyss-machine enter --json` before broad host-layer work
topology source: {{ABYSS_MACHINE_ETC}}/TOPOLOGY.md
topology facts: {{ABYSS_MACHINE_STATE}}/topology/latest.json and index.json
topology validation: `abyss-machine topology validate --json`
topology audit: `abyss-machine topology audit --json`, timer `abyss-topology-audit.timer`
machine graph: `abyss-machine graph --json`, generated from bridge/topology/subsystem indexes
machine maps: `abyss-machine maps --json`, generated route atlas across time, subsystems, causal chains, freshness, resource state, privacy risk, and RAG/eval/memo/KAG boundary context; `abyss-machine maps packet --reader-profile PROFILE --json` emits bounded agent reader-profile context packets; entries and packets are route signals, not source truth, destinations, or permission to act
machine context refresh: `abyss-machine rag refresh --query TEXT --json`, user timer `abyss-machine-context-refresh.timer`, rebuilds maps, validates maps, writes RAG trace/eval, and validates RAG every 15 minutes as generated context only
machine RAG trace: `abyss-machine rag trace --query TEXT --json`, read-only loop from maps context packet to bounded evidence summaries, deterministic answer trace, and local trace eval; writes generated state under `{{ABYSS_MACHINE_STATE}}/rag/`; it does not execute actions, produce proof verdicts, write reviewed memory, publish KAG truth, or deliver evidence into AoA organs
machine doctor: `abyss-machine doctor --json`, `abyss-machine doctor --repair --safe-only --json`, `abyss-machine doctor report --markdown`, and `abyss-machine doctor machine-report --json`; oneshot user timer, not a resident daemon
stack bridge: `abyss-machine stack-bridge --json`, read-only host-to-stack handoff bundle for future abyss-stack consumers
stack bridge validation: `abyss-machine stack-bridge validate --json`
documentation contract: {{ABYSS_MACHINE_ETC}}/DOCS.md
documentation direction: {{ABYSS_MACHINE_ETC}}/ROADMAP.md, host-wide direction and future triggers only
decision rationale: {{ABYSS_MACHINE_ETC}}/decisions, durable why for structural host choices; current source surfaces define what
decision index: `abyss-machine docs decisions-index --json`, writes {{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json for fast access to what changed when and why
curated changelog: {{ABYSS_MACHINE_ETC}}/CHANGELOG.md, sparse milestone contour; exact history stays in {{ABYSS_MACHINE_STATE}}/changes
documentation audit: `abyss-machine docs audit --json`, writes {{ABYSS_MACHINE_STATE}}/docs/latest.json and index.json
static bridge sync: `{{ABYSS_MACHINE_ETC}}/bridge.json` and `{{ABYSS_MACHINE_ETC}}/stack-bridge.json` are synchronized with the dynamic Resource Orchestrator v2 and Nervous Quality Audit routes; verify future drift with `abyss-machine stack-bridge sync-static --dry-run --json` before treating a new dynamic route as present in static manifests. Use `pkexec abyss-machine stack-bridge sync-static --json` for future privileged static syncs.
stack bridge shape note: dynamic reads (`stack-bridge export/latest`) expose named bridge payloads under `bridges.*`; root-owned `{{ABYSS_MACHINE_ETC}}/stack-bridge.json` keeps the static compatibility shape and, after sync, should contain `resource_bridge.orchestrator_latest`, top-level `nervous_quality_bridge`, `self_awareness_bridge.commands.requirements`, `self_awareness_bridge.commands.failure_matrix`, `self_awareness_bridge.commands.cycle`, and `artifacts.resource.orchestrator` / `artifacts.nervous.quality` / `artifacts.self_awareness.requirements` / `artifacts.self_awareness.failure_matrix` / `artifacts.self_awareness.cycle`.
work mode plan: `abyss-machine mode plan --json`, maps GNOME-selected mode to power, cooling, thermal/memory gates, storage/process context, and launch policy
work mode validation: `abyss-machine mode validate --json`
memory pressure plan: `abyss-machine memory plan --json`
memory headroom advisor: `abyss-machine memory headroom --json`
memory validation: `abyss-machine memory validate --json`
resource plan: `abyss-machine resource plan --class CLASS --kind KIND --json`, unified host pre-launch decision
resource orchestrator: `abyss-machine resource orchestrator --json`, broad read-only matrix audit for future agents and stack bridges
resource launch: `abyss-machine resource launch --class CLASS --kind KIND -- COMMAND`, starts new work through user systemd-run only; add `--no-thermal-sample` for dry-run/diagnostic paths that should consume the latest thermal plan instead of taking a fresh sample; add `--success-on-block` only for scheduled unattended ticks that should skip cleanly on soft gates
resource validation: `abyss-machine resource validate --json`
OS Abyss heartbeats: `abyss-machine heartbeats pulse --json`, recurring compact pulse over current machine evidence and reaction candidates; writes heartbeat facts only and keeps `automatic_action=false`
reaction candidates: `abyss-machine reactions --json`, non-executing evidence-to-action-candidate read model over nervous, doctor, resource, and selected systemd facts; candidates are suggestions only and keep `automatic=false`
response routes: `abyss-machine responses --json`, owner-gated route read model over reaction candidates; response routes preserve suggested commands and approval gates but keep `automatic_response=false`
change ledger: {{ABYSS_MACHINE_STATE}}/changes
mutation gate: `abyss-machine changes preflight --intent TEXT --surface SURFACE --json`
subsystem validators: `abyss-machine storage|memory|resource|ai|cooling|mode|processes|nervous|typing|dictation|rag validate --json`
test lanes: `abyss-machine test quick --json`, `abyss-machine test full --json`, and read-only `abyss-machine test live --json`; `long` and `manual` are excluded from unattended use
machine-owned writes: {{ABYSS_MACHINE_ETC}}, {{ABYSS_MACHINE_STATE}}, {{ABYSS_MACHINE_SRV}}
project roots: read-only by default from the host layer
forbidden machine-owned storage roots: /work, /srv/work
large caches/runtimes: {{ABYSS_MACHINE_SRV}}, not limited root filesystem
```

## Abyss Nervous System

```bash
abyss-machine nervous status --json
abyss-machine nervous paths --json
abyss-machine nervous policy --json
abyss-machine nervous sources --json
abyss-machine nervous privacy --json
abyss-machine nervous privacy-status --json
abyss-machine nervous privacy-set pause on --reason "..."
abyss-machine nervous privacy-set pause off --reason "..."
abyss-machine nervous privacy-set private-mode on --reason "..."
abyss-machine nervous sources-list --json
abyss-machine nervous source-status abyss_machine_facts --json
abyss-machine nervous source-disable systemd_metadata --reason "..."
abyss-machine nervous source-enable systemd_metadata --reason "..."
abyss-machine nervous snapshot --json
abyss-machine nervous capture-status --json
abyss-machine nervous browser-content-capture --json
abyss-machine nervous validate --json
abyss-machine nervous forget --minutes 15 --dry-run --json
abyss-machine nervous redact-test --text "token=..." --json
abyss-machine nervous redact-file --path /explicit/path --dry-run --json
abyss-machine nervous baseline --json
abyss-machine nervous events-build --json
abyss-machine nervous events-latest --json
abyss-machine nervous events-validate --json
abyss-machine nervous episodes-build --json
abyss-machine nervous episodes-latest --json
abyss-machine nervous episodes-validate --json
abyss-machine nervous index-status --json
abyss-machine nervous index-build --json
abyss-machine nervous index-validate --json
abyss-machine nervous semantic-status --json
abyss-machine nervous semantic-maintain --json
abyss-machine nervous semantic-build --max-chunks 64 --json
abyss-machine nervous semantic-search --query thermal --json
abyss-machine nervous semantic-eval --json
abyss-machine nervous search --query thermal --json
abyss-machine nervous search --query thermal --source nervous_events --json
abyss-machine nervous search --query episode --schema abyss_machine_nervous_episode_v1 --json
abyss-machine nervous rerank --query thermal --json
abyss-machine nervous rerank-eval --json
abyss-machine nervous recall --query thermal --json
abyss-machine nervous recall --mode hybrid --query thermal --json
abyss-machine nervous brief --scope now --json
abyss-machine nervous synthesis-build --scope daily --json
abyss-machine nervous synthesis-latest --json
abyss-machine nervous synthesis-validate --json
abyss-machine nervous eval-run --json
abyss-machine nervous eval-latest --json
abyss-machine nervous eval-validate --json
abyss-machine nervous retention-plan --json
abyss-machine nervous retention-apply --dry-run --json
abyss-machine nervous retention-validate --json
abyss-machine nervous quality-audit --json
abyss-machine nervous quality-audit --refresh --json
abyss-machine nervous quality-audit --refresh --refresh-index --json
abyss-machine nervous search --query thermal --order ranked --no-dedupe --json
abyss-machine nervous index-vacuum --json
abyss-machine nervous latest --json
```

## Reaction Candidates

```bash
abyss-machine reactions --json
abyss-machine reactions paths --json
abyss-machine reactions validate --json
```

This layer converts current machine evidence into routed reaction candidates. It does not execute suggested commands, clear systemd state, mutate project roots, or bypass nervous privacy policy.

## OS Abyss Responses

```bash
abyss-machine responses --json
abyss-machine responses paths --json
abyss-machine responses validate --json
```

This layer converts reaction candidates into owner-gated response routes. `responses` is the route subsystem name; `response_route` is one gated route from one reaction candidate. It does not execute suggested commands, clear systemd state, mutate project roots, or bypass nervous privacy policy.

## OS Abyss Heartbeats

```bash
abyss-machine heartbeats pulse --json
abyss-machine heartbeats paths --json
abyss-machine heartbeats validate --json
systemctl --user status abyss-machine-heartbeat.timer --no-pager
```

This layer writes the recurring OS Abyss heartbeat pulse. `heartbeats` is the recurring subsystem name; `heartbeat_pulse` is one durable pulse. It does not execute reaction candidates, clear systemd state, mutate project roots, or bypass nervous privacy policy.

Persistent paths:

```bash
{{ABYSS_MACHINE_SRV}}/design/abyss-nervous-system-design.md
{{ABYSS_MACHINE_SRV}}/AGENTS.md
{{ABYSS_MACHINE_STATE}}/nervous/AGENTS.md
{{ABYSS_MACHINE_STATE}}/nervous/index.json
{{ABYSS_MACHINE_STATE}}/nervous/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/policy/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/sources/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/privacy/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/privacy/state.json
{{ABYSS_MACHINE_STATE}}/nervous/privacy/audit/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/sources/state.json
{{ABYSS_MACHINE_STATE}}/nervous/checks/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/checks/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/indexes/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/capture/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/facts/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/facts/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/events/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/events/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/episodes/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/episodes/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/retrieval/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/retrieval/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/retrieval/rerank/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/retrieval/rerank/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/evals/rerank/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/evals/rerank/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/brief/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/brief/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/synthesis/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/synthesis/daily/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/synthesis/daily/YYYY/MM/YYYY-MM-DD.md
{{ABYSS_MACHINE_STATE}}/nervous/evals/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/evals/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/retention/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/retention/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/quality/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/quality/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/nervous/indexes/semantic/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/indexes/semantic/maintain/latest.json
{{ABYSS_MACHINE_STATE}}/nervous/indexes/semantic/maintain/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_ETC}}/typing-policy.json
{{ABYSS_MACHINE_STATE}}/typing/AGENTS.md
{{ABYSS_MACHINE_STATE}}/typing/index.json
{{ABYSS_MACHINE_STATE}}/typing/events/latest.json
{{ABYSS_MACHINE_STATE}}/typing/events/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/typing/validate/latest.json
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-passive-chronicle.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-passive-chronicle.timer
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-passive-chronicle.service.d/50-derived-refresh.conf
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-derived-refresh.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-browser-content-capture.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-browser-content-capture.timer
{{ABYSS_USER_HOME}}/.local/bin/abyss-nervous-browser-content-capture-tick
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-index-build.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-index-build.timer
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-semantic-maintain.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-nervous-semantic-maintain.timer
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-process-snapshot.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-process-snapshot.timer
{{ABYSS_MACHINE_ETC}}/nervous/policy.json
{{ABYSS_MACHINE_ETC}}/nervous/sources.json
{{ABYSS_MACHINE_ETC}}/nervous/privacy.json
{{ABYSS_MACHINE_ETC}}/nervous/index.json
{{ABYSS_MACHINE_SRV}}/storage/nervous/indexes/sqlite/nervous.db
{{ABYSS_MACHINE_SRV}}/storage/nervous/indexes/sqlite/schema.sql
{{ABYSS_MACHINE_SRV}}/storage/nervous/captures
{{ABYSS_MACHINE_SRV}}/storage/nervous/captures/screenshots/YYYY/MM
{{ABYSS_MACHINE_SRV}}/storage/nervous/captures/browser-content/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_USER_HOME}}/.local/bin/firefox
{{ABYSS_USER_HOME}}/.local/share/applications/org.mozilla.firefox.desktop
{{ABYSS_MACHINE_SRV}}/tools/nervous/browser-capture/firefox-bidi-launch
{{ABYSS_MACHINE_SRV}}/tmp/nervous/browser-history
{{ABYSS_MACHINE_SRV}}/cache/nervous
{{ABYSS_MACHINE_SRV}}/runtimes/nervous
{{ABYSS_MACHINE_SRV}}/storage/nervous
{{ABYSS_MACHINE_SRV}}/tools/nervous
```

Current policy:

```bash
status: stage-9-passive-local-private-capture
active daemon: disabled
automatic actions: disabled
enabled sources: abyss-machine facts, filesystem metadata, git status, podman metadata, systemd metadata, manual notes, browser history/open-tab content, terminal activity, clipboard, screenshots, dictation transcript autolog, typed text autolog
manual snapshot: reads enabled passive fact sources with connector-specific redaction/provenance
automatic passive chronicle: user timer every 15 minutes, facts-only, stdout suppressed, trigger=timer, no daemon
automatic derived refresh: passive chronicle `OnSuccess` starts `abyss-nervous-derived-refresh.service`; it runs `quality-audit --refresh` first and then resource-gated `index-build`
deterministic events: `events-build` derives event records from passive fact snapshots only
deterministic episodes: `episodes-build` groups derived event records into day/category episodes only
automatic local index: user timer every 45 minutes, full rebuild from passive facts plus derived events and episodes, stdout suppressed
local index DB: {{ABYSS_MACHINE_SRV}}/storage/nervous/indexes/sqlite/nervous.db
local index latest state: {{ABYSS_MACHINE_STATE}}/nervous/indexes/latest.json
local capture latest state: {{ABYSS_MACHINE_STATE}}/nervous/capture/latest.json
local-private artifact root: {{ABYSS_MACHINE_SRV}}/storage/nervous/captures
browser capture: recent local Firefox history with URL query/fragment stripped; Firefox document text through AT-SPI during normal browsing; WebDriver BiDi is diagnostic-only
normal browser launch: `{{ABYSS_USER_HOME}}/.local/bin/firefox` sets GNOME_ACCESSIBILITY=1 NO_AT_BRIDGE=0 GTK_MODULES=gail:atk-bridge and then execs `/usr/bin/firefox`; it must not add --remote-debugging-port
browser privacy: no cookies, no localStorage, no form values; login/password-like page bodies are skipped and text is redacted before indexing
browser content quality: browser-content records preserve raw local-private text but also write `content_quality` and optional `clean_text`; downstream jobs should prefer cleaned usable records and avoid `noise`/`skipped` records
terminal capture: shell history and process metadata only; no attachment to existing stdout/stderr streams
clipboard capture: text is redacted, length-limited, hashed; binary content is not captured; passive timer clipboard reads are enabled through `wl-paste`; known GNOME Shell log noise is recorded as backend quality instead of silently disabling collection
dictation capture: reads existing transcript journal and does not open the microphone itself
typed-text capture: reads explicit committed-text events from `abyss-machine typing ingest`; no raw keylogger, no password-field capture, sensitive contexts are metadata-only
screenshot capture: timer/manual/test snapshots must be invisible to the operator; on normal GNOME desktop they use the allowlisted `org.gnome.Screenshot` DBus-owner route into GNOME Shell with `flash=false`, and on wlroots desktops they may use silent `grim` when supported; during active game or fullscreen X11/Xwayland game contexts they skip GNOME Shell screenshot backends, first try non-focus X11/Xwayland window capture, then `grim`, then skip with evidence instead of minimizing the game; `gnome-screenshot` is operator-visible/noisy and requires explicit diagnostic opt-in with `ABYSS_NERVOUS_ALLOW_NOISY_SCREENSHOT=1`; direct GNOME Shell DBus screenshot is disabled by default because denied calls also produce GNOME Shell log noise and requires explicit `ABYSS_NERVOUS_ALLOW_SHELL_SCREENSHOT_DBUS=1`; `ABYSS_NERVOUS_ALLOW_INTERACTIVE_SCREENSHOT=1` is manual diagnostics only because portal UI can steal focus
local search: `abyss-machine nervous search --query TEXT --json`
local search default: latest-first and deduped; use `--source`, `--schema`, `--since`, `--until`, `--severity`, `--sensitivity`, or `--order ranked --no-dedupe` for focused bridge/debug reads
semantic search: `abyss-machine nervous semantic-build --json` builds an on-demand OpenVINO embedding sidecar under `{{ABYSS_MACHINE_SRV}}/storage/nervous/indexes/semantic`; `semantic-search` reads it, and `semantic-eval` checks known noisy probes. No resident embedding service is enabled.
semantic maintenance: `abyss-machine nervous semantic-maintain --json` checks source-index freshness first, refreshes stale deterministic SQLite/FTS through resource gates, re-assesses semantic drift, and launches full incremental `semantic-build` through `resource launch` only when thresholds are crossed. Under active game/background memory pressure it blocks cleanly or uses a smaller embedding batch instead of forcing new pressure. The user timer `abyss-nervous-semantic-maintain.timer` runs this bounded maintainer every 90 minutes with a 3600s resource timeout and a 65min service envelope; it is not a resident embedding service.
hybrid rerank: `abyss-machine nervous rerank --query TEXT --json` merges local FTS and the optional semantic sidecar; scores expose lexical rank, semantic score, query overlap, recency, severity, and contextual source-prior
recall: `abyss-machine nervous recall --query TEXT --json` writes an evidence pack with freshness and provenance, not new facts
hybrid recall: `abyss-machine nervous recall --mode hybrid --query TEXT --json` writes an evidence pack using rerank output, including source mix, freshness, and semantic run ID
agent brief: `abyss-machine nervous brief --scope now --json` is the preferred quick entrypoint for future agents; it reports readiness, gaps, latest episodes, quality, resource/memory/storage context, and next safe actions
synthesis: `abyss-machine nervous synthesis-build --scope daily --json` writes deterministic candidate JSON and daily markdown; no model call and no repo write
eval gate: `abyss-machine nervous eval-run --json` checks events, episodes, index, recall, synthesis, and synthesis validation
quality audit: `abyss-machine nervous quality-audit --json` is the all-in-one evidence gate before relying on local memory; `--refresh` rebuilds deterministic derived layers, `--refresh-index` also rebuilds SQLite/FTS, and the audit verifies the passive chronicle to derived-refresh service handoff
retention: `abyss-machine nervous retention-plan --json` and `retention-apply --dry-run --json`; retention does not delete facts
index freshness: `index-status` and `index-validate` report latest fact/event/episode timestamps vs index built_at
index validation: `abyss-machine nervous index-validate --json` checks FTS5, storage route, symlink tails, schema, source policy, and derived layer indexing
validation: `abyss-machine nervous validate --json` checks fact/event/episode schemas, source provenance, source hashes, counters, and source policy
privacy state: `{{ABYSS_MACHINE_STATE}}/nervous/privacy/state.json`; changes append audit JSONL
pause behavior: snapshot writes only audit heartbeat and does not update facts/latest.json
index pause behavior: events-build, episodes-build, recall, synthesis-build, eval-run, retention-plan writes, retention-apply, index build/search/vacuum refuse while global pause is active
private behavior: snapshot writes minimal heartbeat with no detailed facts
source overrides: `{{ABYSS_MACHINE_STATE}}/nervous/sources/state.json`; use `source-disable SOURCE` for per-connector stop without pausing all capture
source-index behavior: disabled source classes are filtered before insert; rebuild after source policy changes
forget behavior: atomic JSONL rewrite plus audit record; use --dry-run first
forget-index behavior: rebuild derived events, derived episodes, and local index after real forget operations
redaction: connector-specific redaction before snapshot/index writes; dry-run helpers remain available
private connector sources: browser active tab/history, terminal stdout/stderr class metadata, clipboard, screenshots, audio transcript autolog, typed text autolog
AoA repositories: source material under reformation, read-only until stable import contracts exist
abyss-stack repositories: do not mutate from host layer
large machine-owned data: {{ABYSS_MACHINE_SRV}}, not /work and not the limited root filesystem
```

## AI Host

```bash
abyss-machine ai status
abyss-machine ai status --json
abyss-machine ai paths --json
abyss-machine ai devices --json
abyss-machine ai models --json
abyss-machine ai llm paths --json
abyss-machine ai llm registry --json
abyss-machine ai llm latest --json
abyss-machine ai llm validate --json
abyss-machine ai llm resident paths --json
abyss-machine ai llm resident status --json
abyss-machine ai llm resident preflight --json
abyss-machine ai llm resident monitor --json
abyss-machine ai llm resident policy --request-class job --json
abyss-machine ai llm resident digest --json
abyss-machine ai llm resident job dictation_quality --json
abyss-machine ai llm resident job query_expansion --json
abyss-machine ai llm resident job multimodal_edge_lane --json
abyss-machine ai llm resident micro --json
abyss-machine ai llm resident jobs latest --json
abyss-machine ai llm resident jobs status --json
abyss-machine ai llm resident jobs run --json
abyss-machine ai llm resident jobs-validate --json
abyss-machine ai llm resident candidates --json
abyss-machine ai llm resident candidates-validate --json
abyss-machine ai llm resident evals --json
abyss-machine ai llm resident evals-validate --json
abyss-machine ai llm resident audit --json
abyss-machine ai llm resident smoke --json
abyss-machine ai llm resident validate --json
abyss-machine ai llm workhorse paths --json
abyss-machine ai llm workhorse preflight --json
abyss-machine ai llm workhorse pack --json
abyss-machine ai llm workhorse review --json
abyss-machine ai llm workhorse review --run-model --json
abyss-machine ai llm workhorse validate --json
abyss-machine ai llm workhorse self-test --json
abyss-machine ai tts inventory --json
abyss-machine ai tts profiles --json
abyss-machine ai tts voices --json
abyss-machine ai tts compare --json
abyss-machine ai tts compare --run --json
abyss-machine ai tts server status --json
abyss-machine ai tts server run --profile quality-compact
abyss-machine ai tts server stop --json
abyss-machine ai tts eval --profile quality --json
abyss-machine ai tts eval --profile quality-compact --json
abyss-machine ai tts eval --profile npu-fast-experimental --json
abyss-machine ai tts eval --profile gpu-fast-experimental --json
abyss-machine ai tts eval --profile cpu-fast-experimental --json
abyss-machine ai tts synth --profile quality --text "Привет" --json
abyss-machine ai tts synth --profile quality-compact --text "Привет" --json
abyss-machine ai benchmark --quick --json
abyss-machine ai benchmark --quick --devices CPU,GPU,NPU --json
abyss-machine ai benchmark --real --json
abyss-machine ai eval --quick --json
abyss-machine ai eval --suite stt --json
abyss-machine ai eval --suite embeddings --json
abyss-machine ai eval --suite text --json
abyss-machine ai capabilities --json
abyss-machine ai policy --json
abyss-machine ai cpu topology --json
abyss-machine ai cpu thermal-map --json
abyss-machine ai cpu route --class medium --json
abyss-machine ai cpu route --class heavy --json
abyss-machine ai cpu launch --class heavy --dry-run -- COMMAND
abyss-machine ai cpu test --profile lp-e --seconds 1 --json
abyss-machine ai cpu test --profile e-cores --seconds 1 --json
abyss-machine ai storage --json
abyss-machine ai storage clean-caches --stack-local-openvino --json
abyss-machine ai runtime --json
abyss-machine ai report --json
abyss-machine ai workload --json
abyss-machine ai workload taxonomy --json
abyss-machine ai workload stats --json
abyss-machine ai workload refresh --json
abyss-machine ai config get --json
```

Persistent paths:

```bash
{{ABYSS_MACHINE_STATE}}/ai/AGENTS.md
{{ABYSS_MACHINE_STATE}}/ai/index.json
{{ABYSS_MACHINE_STATE}}/ai/devices/latest.json
{{ABYSS_MACHINE_STATE}}/ai/models/latest.json
{{ABYSS_MACHINE_STATE}}/ai/llm/AGENTS.md
{{ABYSS_MACHINE_STATE}}/ai/llm/registry/latest.json
{{ABYSS_MACHINE_STATE}}/ai/llm/registry/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/llm/validate/latest.json
{{ABYSS_MACHINE_STATE}}/ai/llm/resident/gemma4.spark/audit/latest.json
{{ABYSS_MACHINE_STATE}}/ai/llm/resident/gemma4.spark/candidates/latest.json
{{ABYSS_MACHINE_STATE}}/ai/llm/resident/gemma4.spark/candidates/validate/latest.json
{{ABYSS_MACHINE_SRV}}/runtimes/llama.cpp
{{ABYSS_MACHINE_SRV}}/cache/ai/gemma4
{{ABYSS_MACHINE_STATE}}/ai/tts/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/inventory/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/profiles/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/evals/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/evals/latest_success.json
{{ABYSS_MACHINE_STATE}}/ai/tts/evals/latest_success_by_profile.json
{{ABYSS_MACHINE_STATE}}/ai/tts/evals/success/
{{ABYSS_MACHINE_STATE}}/ai/tts/evals/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/tts/compare/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/compare/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/tts/server/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/research/latest.json
{{ABYSS_MACHINE_STATE}}/ai/tts/research/
{{ABYSS_MACHINE_STATE}}/ai/tts/evals/experimental/
{{ABYSS_MACHINE_STATE}}/ai/tts/runtime-patches/
{{ABYSS_MACHINE_STATE}}/ai/tts/synth/YYYY/MM/YYYY-MM-DD/
{{ABYSS_MACHINE_SRV}}/tools/ai/tts/voxcpm2/bench_voxcpm2_xpu.py
{{ABYSS_MACHINE_STATE}}/ai/benchmarks/latest.json
{{ABYSS_MACHINE_STATE}}/ai/benchmarks/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/evals/latest.json
{{ABYSS_MACHINE_STATE}}/ai/evals/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/capabilities/latest.json
{{ABYSS_MACHINE_STATE}}/ai/policy/latest.json
{{ABYSS_MACHINE_STATE}}/ai/cpu/AGENTS.md
{{ABYSS_MACHINE_STATE}}/ai/cpu/topology/latest.json
{{ABYSS_MACHINE_STATE}}/ai/cpu/thermal-map/latest.json
{{ABYSS_MACHINE_STATE}}/ai/cpu/route/latest.json
{{ABYSS_MACHINE_STATE}}/ai/cpu/tests/latest.json
{{ABYSS_MACHINE_STATE}}/ai/cpu/tests/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/storage/latest.json
{{ABYSS_MACHINE_STATE}}/ai/runtime/latest.json
{{ABYSS_MACHINE_STATE}}/ai/reports/latest.json
{{ABYSS_MACHINE_STATE}}/ai/workloads/latest.json
{{ABYSS_MACHINE_STATE}}/ai/workloads/taxonomy.json
{{ABYSS_MACHINE_STATE}}/ai/workloads/stats/latest.json
{{ABYSS_MACHINE_STATE}}/ai/workloads/runs/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/ai/workloads/refresh/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_ETC}}/ai/config.json
{{ABYSS_MACHINE_ETC}}/storage-policy.json
{{ABYSS_MACHINE_ETC}}/storage-policy.env
{{ABYSS_MACHINE_SRV}}/cache/ai/openvino
{{ABYSS_MACHINE_SRV}}/cache/ai/tts
{{ABYSS_MACHINE_SRV}}/cache/ai/tts/qwen3-openvino
{{ABYSS_MACHINE_SRV}}/cache
{{ABYSS_MACHINE_SRV}}/cache/ai/tts/qwen3-openvino
{{ABYSS_MACHINE_SRV}}/runtimes
{{ABYSS_MACHINE_SRV}}/storage
```

Current policy:

```bash
read-only model roots: {{ABYSS_OS_ROOT}}/abyss-stack/Models, {{ABYSS_USER_HOME}}/src/abyss-stack/Models
quick benchmark only: synthetic OpenVINO compile/infer smoke, not a real LLM/STT throughput test
real host eval: bounded executable evidence, not an abyss-stack runtime promotion verdict
LLM backend: llama.cpp under {{ABYSS_MACHINE_SRV}}/runtimes/llama.cpp; model caches under {{ABYSS_MACHINE_SRV}}/cache/ai/<family>
LLM profiles: gemma4.spark=Gemma 4 E2B resident-small-brain candidate, gemma4.workhorse=Gemma 4 E4B on-demand workhorse candidate
LLM registry: executable host evidence only; future abyss-stack routing must run stack-owned machine-fit, warmup, and quality gates
LLM resident candidate: gemma4.spark runs through user systemd service/timers, writes status/monitor/policy/digest/micro/jobs evidence under {{ABYSS_MACHINE_STATE}}/ai/llm/resident/gemma4.spark, and may skip starts when gates block new resident work
LLM resident policy: `abyss-machine ai llm resident policy --request-class job|jobs|foreground|digest|sustained --json` is the thin-laptop adaptive route; it records allow/degraded/fallback over cooling status, CPU route, memory pressure, game guard, and thermal-throttle delta without changing fans, governors, or stack routing; transient temperature spikes route compact degraded E2B work instead of default fallback, tier-1 request_class=job probes may run degraded under active game guard only with low PSI, enough available memory, and sub-hot thermal evidence, while jobs batches, sustained/absolute heat, broad heat plus throttle storm, higher-tier game-guarded work, or real memory PSI stalls still fallback
LLM resident micro-loop: `abyss-machine ai llm resident micro --json` rotates one compact job per frequent timer tick so E2B keeps producing useful, reviewable artifacts without running the full background batch each time
LLM resident candidates: `abyss-machine ai llm resident candidates --json` aggregates E2B collect/select lane artifacts into derived recall, rank, model-input, review, risk, heartbeat, short-document, and selected handoff queues with `action_execution=false`; each candidate carries `selection_score`, `selection_tier`, `selection_lane`, and `selection_reasons`; selected queues are lane-balanced before heartbeat, E4B review, nervous/search, or future stack handoff, and `candidates-validate` gates that read-model
LLM resident evals: `abyss-machine ai llm resident evals --json` replays current E2B jobs/candidate artifacts into a heartbeat scorecard for schema, semantic grounding, utility, recency, safety, runtime health, per-lane quality trend, fixture-candidate mining, and score-only readiness recommendation without starting a jobs batch, rewriting fixtures, auto-promoting readiness, or running model generation; `evals-validate` makes that scorecard available to audit and heartbeats
LLM resident heartbeat breath: `abyss-machine heartbeats pulse --json` exposes E2B as `e2b_breath`, joining candidate delta, quality score, degraded-current/historical reason, staleness, and review-needed counts without running resident jobs, model generation, candidate execution, or stack promotion
LLM workhorse harness: `abyss-machine ai llm workhorse pack|review|validate --json` wraps Gemma 4 E4B as a non-resident reviewer over E2B `e4b_review_pack_v2`; default review is deterministic/no-model, `--run-model` is explicit and profile-gated, the pack orders by E2B selection score/tier/lane before raw utility, preserves source IDs/excerpts, uncertainty notes, rejected/hollow candidate surfaces, and runtime degradation context, and the harness rejects hollow safety cards, missing source IDs, missing keep/drop/escalate judgements, nested partial JSON, service mutation, stack mutation, and direct action execution
LLM resident audit: `abyss-machine ai llm resident audit --json` is the preferred E2B repair/readiness lane; it checks endpoint health, stack/host service posture, timers, preflight, validate, jobs-validate, evals-validate, policy probes, source freshness, job/micro history, and a tiny generation probe without starting or stopping services
LLM resident source freshness: dictation job inputs default to a 48h freshness window and browser-content inputs default to a 12h freshness window; override with `ABYSS_GEMMA4_SPARK_DICTATION_MAX_AGE_SEC` or `ABYSS_GEMMA4_SPARK_BROWSER_MAX_AGE_SEC`; stale archive rows stay preserved but jobs should write `idle`/audit warnings instead of treating old rows as current operator context
LLM resident browser quality: browser-content records may include `content_quality` and `clean_text`; E2B browser reading ranks/dedupes cleaned usable pages and avoids skipped/noise captures such as player controls, browser-internal pages, and low-signal streaming/catalog pages
LLM resident jobs: candidate calibration artifacts for dictation quality, work blocks, intent candidates, safe operator-input context from the typing process readmodel, command grammar, browser reading, thermal/performance, storage classification, daily brief, query expansion, rerank-lite, source quality, resident quality eval, action-card compilation, bounded hints, risk sentinel, and short document classification; the candidate read-model aggregates the collect/select lanes for review/search/model-input handoff; experimental multimodal/edge endpoint lanes are prepared contracts only, not live runtimes; jobs use resident policy per job and do not execute user intent
OpenVINO compile cache: {{ABYSS_MACHINE_SRV}}/cache/ai/openvino, never stack model roots
TTS cache and generated audio: {{ABYSS_MACHINE_SRV}}/cache/ai/tts and {{ABYSS_MACHINE_STATE}}/ai/tts, never stack model roots
TTS profiles: quality=Qwen3-TTS 1.7B OpenVINO GPU fp16, quality-compact=Qwen3-TTS 1.7B OpenVINO GPU INT8+code-predictor-fp16 lower-memory path, npu-fast-experimental=BabelVox/Qwen3-TTS 0.6B NPU experiment, fallback=Piper CPU placeholder
TTS compare: default reads latest successful per-profile evidence without model execution; use --run only for explicit fresh heavy evals
TTS warm server: abyss-tts-server.service is enabled as a user service and policy-gated by abyss-machine ai policy; default warm profile is quality-compact
Dictation warm server: abyss-dictation-server.service is enabled and protected as operator input; do not disable it for memory relief without explicit operator approval and an immediate rollback path
workload stats: append-only measured eval/benchmark facts; absent metrics mean unmeasured
workload refresh: automatic probe-only refresh, policy-gated, never real eval
heavy eval: policy-gated; use --force only for explicit operator-controlled validation
CPU topology: roles are inferred from cpu_capacity/max frequency because topology/core_type is unavailable on this kernel
CPU thermal route: medium work may still be operator-allowed during a single-core hotspot, but routed away from hot cores with bounded threads; unattended route permission follows the thermal cap
CPU heavy policy: `ai policy` distinguishes `can_run_heavy` unrestricted heavy from `can_run_routed_heavy` CPU-only routed heavy
CPU heavy route: single/narrow core hotspots may allow operator-controlled heavy CPU work through `abyss-machine ai cpu route --class heavy --json`; broad core heat, package hot/critical, battery discharge, or missing telemetry still defer heavy starts
CPU route application: callers must apply returned taskset/env/OpenVINO hints; route commands do not change governors, fans, or abyss-stack state
VoxCPM2 XPU profiler: use {{ABYSS_MACHINE_SRV}}/tools/ai/tts/voxcpm2/bench_voxcpm2_xpu.py with all caches rooted under {{ABYSS_MACHINE_SRV}}; do not run while abyss-machine ai policy is hot or another heavy workload is active
```

## Storage Routing

```bash
cat {{ABYSS_MACHINE_ETC}}/storage-policy.json
cat {{ABYSS_MACHINE_ETC}}/storage-policy.env
abyss-machine storage policy --json
abyss-machine storage paths --json
abyss-machine storage status --json
abyss-machine storage status --full --json
abyss-machine storage inventory --json
abyss-machine storage inventory --full --json
abyss-machine storage pressure --json
abyss-machine storage pressure --refresh-inventory --json
abyss-machine storage cleanup-plan --json
abyss-machine storage cleanup-plan --refresh-inventory --json
abyss-machine storage monitor --json
abyss-machine storage write-preflight --kind model-cache --bytes 10000000000 --target {{ABYSS_USER_HOME}}/.cache/example --json
abyss-machine storage write-preflight --kind model-cache --bytes 10000000000 --target {{ABYSS_MACHINE_SRV}}/cache/ai/example --json
abyss-machine storage apply --action-id ID --dry-run --json
abyss-machine storage hooks --json
abyss-machine storage podman-preflight --json
abyss-machine storage podman-preflight --require-stopped --json
abyss-machine storage run-hooks pre_large_write --json
abyss-machine storage run-hooks post_large_write --json
abyss-machine memory paths --json
abyss-machine memory policy --json
abyss-machine memory status --json
abyss-machine memory pressure --json
abyss-machine memory processes --json
abyss-machine memory plan --json
abyss-machine memory headroom --json
abyss-machine memory residency --json
abyss-machine memory hotpath-probe --json
abyss-machine memory orchestrate plan --json
abyss-machine memory orchestrate idle --candidate ID --json
abyss-machine memory orchestrate confirm --candidate ID --operator NAME --reason TEXT --acknowledge-protected --dry-run --json
abyss-machine memory orchestrate apply --candidate ID --dry-run --json
abyss-machine memory orchestrate apply --candidate ID --confirm --json
abyss-machine memory orchestrate apply --candidate ID --confirm --execute-live --acknowledge-live-restart --operator NAME --reason TEXT --json
abyss-machine memory validate --json
abyss-machine resource paths --json
abyss-machine resource status --json
abyss-machine resource policy --json
abyss-machine resource orchestrator --json
abyss-machine resource orchestrator --refresh-nervous --json
abyss-machine resource plan --class heavy --kind ai --json
abyss-machine resource plan --class heavy --kind ai --unattended --json
abyss-machine resource launch --class light --kind generic --dry-run --json -- /bin/true
abyss-machine resource launch --class medium --kind indexing --unattended --dry-run --no-thermal-sample --json -- /bin/true
abyss-machine resource launch --class medium --kind indexing --unattended --success-on-block --json -- /bin/true
abyss-machine resource launch --class light --kind generic --timeout 5 --json -- /bin/true
abyss-machine resource validate --json
abyss-machine heartbeats pulse --json
abyss-machine heartbeats paths --json
abyss-machine heartbeats validate --json
abyss-machine reactions --json
abyss-machine reactions paths --json
abyss-machine reactions validate --json
abyss-machine responses --json
abyss-machine responses paths --json
abyss-machine responses validate --json
abyss-machine processes paths --json
abyss-machine processes latest --json
abyss-machine processes snapshot --json
abyss-machine processes snapshot --interval 0.5 --json
abyss-machine processes game-guard --json
abyss-machine processes containers --json
abyss-machine processes thermal-attribution --seconds 3 --interval 0.5 --json
abyss-machine processes thermal-plan --seconds 3 --interval 0.5 --json
abyss-machine processes desktop-compositor --seconds 3 --interval 0.5 --json
systemctl --user status abyss-process-snapshot.timer --no-pager
systemctl --user status abyss-storage-monitor.timer --no-pager
df -hT / /srv
du -xhd1 {{ABYSS_USER_HOME}}/.local {{ABYSS_USER_HOME}}/.cache /var/cache /var/tmp /var/log 2>/dev/null | sort -h | tail -60
podman system df
podman ps
{{ABYSS_MACHINE_SRV}}/storage/migrate-podman-rootless.sh
```

Current policy:

```bash
small stable configs/manifests/state: keep on /
large generated caches/runtimes/artifacts: route to {{ABYSS_MACHINE_SRV}}
host cache root: {{ABYSS_MACHINE_SRV}}/cache
host runtime root: {{ABYSS_MACHINE_SRV}}/runtimes
host storage root: {{ABYSS_MACHINE_SRV}}/storage
host tmp root: {{ABYSS_MACHINE_SRV}}/tmp
host storage evidence: {{ABYSS_MACHINE_STATE}}/storage/latest.json
storage inventory latest: {{ABYSS_MACHINE_STATE}}/storage/inventory/latest.json
storage inventory history: {{ABYSS_MACHINE_STATE}}/storage/inventory/YYYY/MM/YYYY-MM-DD.jsonl
storage pressure latest: {{ABYSS_MACHINE_STATE}}/storage/pressure/latest.json
storage pressure history: {{ABYSS_MACHINE_STATE}}/storage/pressure/YYYY/MM/YYYY-MM-DD.jsonl
storage cleanup plan latest: {{ABYSS_MACHINE_STATE}}/storage/cleanup-plan/latest.json
storage cleanup plan history: {{ABYSS_MACHINE_STATE}}/storage/cleanup-plan/YYYY/MM/YYYY-MM-DD.jsonl
storage monitor latest: {{ABYSS_MACHINE_STATE}}/storage/monitor/latest.json
storage monitor history: {{ABYSS_MACHINE_STATE}}/storage/monitor/YYYY/MM/YYYY-MM-DD.jsonl
storage monitor timer: abyss-storage-monitor.timer, user scope, hourly, low CPU/IO priority, stdout suppressed
storage write preflight latest: {{ABYSS_MACHINE_STATE}}/storage/write-preflight/latest.json
storage write preflight history: {{ABYSS_MACHINE_STATE}}/storage/write-preflight/YYYY/MM/YYYY-MM-DD.jsonl
storage apply latest: {{ABYSS_MACHINE_STATE}}/storage/apply/latest.json
storage apply history: {{ABYSS_MACHINE_STATE}}/storage/apply/YYYY/MM/YYYY-MM-DD.jsonl
process snapshots: {{ABYSS_MACHINE_STATE}}/processes/latest.json and {{ABYSS_MACHINE_STATE}}/processes/snapshots/YYYY/MM/YYYY-MM-DD.jsonl
process game guard: {{ABYSS_MACHINE_STATE}}/processes/game-guard/latest.json and {{ABYSS_MACHINE_STATE}}/processes/game-guard/YYYY/MM/YYYY-MM-DD.jsonl
process container health: {{ABYSS_MACHINE_STATE}}/processes/containers/latest.json and {{ABYSS_MACHINE_STATE}}/processes/containers/YYYY/MM/YYYY-MM-DD.jsonl
process thermal attribution: {{ABYSS_MACHINE_STATE}}/processes/thermal-attribution/latest.json and {{ABYSS_MACHINE_STATE}}/processes/thermal-attribution/YYYY/MM/YYYY-MM-DD.jsonl
process thermal plan: {{ABYSS_MACHINE_STATE}}/processes/thermal-plan/latest.json and {{ABYSS_MACHINE_STATE}}/processes/thermal-plan/YYYY/MM/YYYY-MM-DD.jsonl
process desktop compositor: {{ABYSS_MACHINE_STATE}}/processes/desktop-compositor/latest.json and {{ABYSS_MACHINE_STATE}}/processes/desktop-compositor/YYYY/MM/YYYY-MM-DD.jsonl
process snapshot timer: abyss-process-snapshot.timer, user scope, 30min, low CPU/IO priority, stdout suppressed
game guard route: abyss-machine processes game-guard --json; active games block default heavy/sustained ai cpu launch work and unattended medium-or-heavier launch wrappers without mutating existing game processes
container health route: abyss-machine processes containers --json; exposes rootless Podman state, restart counts, health and compose service labels without env, create-command or mount contents
thermal attribution route: abyss-machine processes thermal-attribution --seconds 3 --interval 0.5 --json; combines hot/avoid CPUs from ai cpu thermal-map with per-thread /proc CPU deltas, incident summary, and CPU distribution; confidence ceiling is high but still candidate evidence
thermal orchestration plan: abyss-machine processes thermal-plan --seconds 3 --interval 0.5 --json; plan routes new work only and does not kill, throttle, or re-affinitize existing user processes
desktop compositor route: abyss-machine processes desktop-compositor --seconds 3 --interval 0.5 --json; links GNOME Shell CPU, fd/pidfd/dmabuf stability, high-refresh display state, animations, GNOME Shell Introspect signal churn, read-only AT-SPI panel metric-label churn, AT-SPI application/window context, GNOME extension preference snapshot, Vitals settings evidence, X11 top-level windows, Wayland socket peers, GUI/process CPU candidates, screencast/remote state, and StatusNotifier context without lowering display quality, toggling extensions, changing panel preferences, closing/minimizing apps, or disabling capture
thermal incident 2026-05-06: abyss-dictation-hotkey was found burning about one full P-core on hot CPU0; listener patched to close dead input fds and service restarted; follow-up showed no hot focus CPUs
memory status latest: {{ABYSS_MACHINE_STATE}}/memory/latest.json
memory pressure latest: {{ABYSS_MACHINE_STATE}}/memory/pressure/latest.json and {{ABYSS_MACHINE_STATE}}/memory/pressure/YYYY/MM/YYYY-MM-DD.jsonl
memory process attribution: {{ABYSS_MACHINE_STATE}}/memory/processes/latest.json and {{ABYSS_MACHINE_STATE}}/memory/processes/YYYY/MM/YYYY-MM-DD.jsonl
memory launch plan: {{ABYSS_MACHINE_STATE}}/memory/plan/latest.json and {{ABYSS_MACHINE_STATE}}/memory/plan/YYYY/MM/YYYY-MM-DD.jsonl
memory headroom advisor: {{ABYSS_MACHINE_STATE}}/memory/headroom/latest.json and {{ABYSS_MACHINE_STATE}}/memory/headroom/YYYY/MM/YYYY-MM-DD.jsonl
memory residency advisor: {{ABYSS_MACHINE_STATE}}/memory/residency/latest.json and {{ABYSS_MACHINE_STATE}}/memory/residency/YYYY/MM/YYYY-MM-DD.jsonl
memory hot-path probe: {{ABYSS_MACHINE_STATE}}/memory/hotpath/latest.json and {{ABYSS_MACHINE_STATE}}/memory/hotpath/YYYY/MM/YYYY-MM-DD.jsonl
memory orchestrate plan: {{ABYSS_MACHINE_STATE}}/memory/orchestrate/latest.json and {{ABYSS_MACHINE_STATE}}/memory/orchestrate/YYYY/MM/YYYY-MM-DD.jsonl
memory orchestrate idle gate: {{ABYSS_MACHINE_STATE}}/memory/orchestrate/idle/latest.json and {{ABYSS_MACHINE_STATE}}/memory/orchestrate/idle/YYYY/MM/YYYY-MM-DD.jsonl
memory orchestrate confirmation contract: {{ABYSS_MACHINE_STATE}}/memory/orchestrate/confirm/latest.json and {{ABYSS_MACHINE_STATE}}/memory/orchestrate/confirm/YYYY/MM/YYYY-MM-DD.jsonl
memory orchestrate apply dry-run: {{ABYSS_MACHINE_STATE}}/memory/orchestrate/apply/latest.json and {{ABYSS_MACHINE_STATE}}/memory/orchestrate/apply/YYYY/MM/YYYY-MM-DD.jsonl
memory orchestrate confirmed executor preflight: {{ABYSS_MACHINE_STATE}}/memory/orchestrate/executor/latest.json and {{ABYSS_MACHINE_STATE}}/memory/orchestrate/executor/YYYY/MM/YYYY-MM-DD.jsonl
memory orchestrate live executor: {{ABYSS_MACHINE_STATE}}/memory/orchestrate/live/latest.json and {{ABYSS_MACHINE_STATE}}/memory/orchestrate/live/YYYY/MM/YYYY-MM-DD.jsonl
machine report contour: {{ABYSS_MACHINE_STATE}}/doctor/machine-report/latest.json and latest.md; `abyss-machine doctor machine-report --json` joins doctor status, memory residency, zram ratio/headroom, PSI, protected TTS/dictation/resident LLM cgroup state, AI thermal policy, nervous readiness, and semantic maintenance state without stopping, restarting, disabling, throttling, re-affinitizing, or capping live services
memory pressure route: abyss-machine memory pressure --json; combines meminfo, PSI, zram/zswap/sysctl/cgroup facts, zram resident/ratio telemetry, process PSS/RSS attribution, and cgroup swap counters; zram-only high swap is capped at hot when MemAvailable is healthy and PSI stalls are absent; resident model RSS/PSS/swap is routing evidence, not a stop/on-demand recommendation
memory orchestration route: abyss-machine memory plan --json; gates new medium/heavy/sustained work only and does not kill, swap, reconfigure zram, enable oomd, tune sysctl, throttle, re-affinitize, stop, or demote existing processes, persistent models, warm AI services, or stack processes
memory orchestrate plan route: abyss-machine memory orchestrate plan --json; non-mutating RAM/zram/cgroup attribution and managed dehydration/rehydration candidate ranking; separates physical zram pool from direct RAM consumers and never restarts, stops, disables, throttles, re-affinitizes, caps, swapoffs, drops caches, or tunes live services/kernel policy; apply support is separate through dry-run inspection, confirmed preflight, and a hard-interlocked podman-managed-model or registered rerank-api live executor
memory orchestrate idle route: abyss-machine memory orchestrate idle --candidate ID --json; read-only resident-model idle gate using llama.cpp health/slots plus cgroup CPU sampling when available, registered rerank-api health with `active_requests=0`, and OVMS live/ready plus `/v1/config` available-model status; treats active slot processing/next-token as busy and ignores stale `n_remain` alone after `is_processing=false`; does not generate tokens, stop, restart, throttle, re-affinitize, cap, or tune services
memory orchestrate confirmation route: abyss-machine memory orchestrate confirm --candidate ID --operator NAME --reason TEXT --acknowledge-protected --dry-run --json; records a dry-run protected-capability confirmation contract with operator, reason, expiry, required before/after probes, rollback/rehydrate proof, and explicit non-grant policy; it is not effective authorization for live mutation
memory orchestrate apply dry-run route: abyss-machine memory orchestrate apply --candidate ID --dry-run --json; selects a fresh plan candidate, snapshots target cgroup/systemd/podman state, emits guard/health/executor steps, and refuses confirmed mutation until idle detection, one-heavy-at-a-time serialization, explicit operator confirmation, before/after evidence, and hot-path verification exist
memory orchestrate confirmed executor preflight route: abyss-machine memory orchestrate apply --candidate ID --confirm --json; non-mutating preflight skeleton that rechecks confirmation freshness, target identity, idle-now, current health signal, PSI, serialization lock, and future executor command, then blocks at invocation-level live_executor_stage_disabled without restarting, stopping, disabling, throttling, re-affinitizing, capping, swapoff, cache drop, sysctl tuning, or zram reconfiguration
memory orchestrate live executor route: abyss-machine memory orchestrate apply --candidate ID --confirm --execute-live --acknowledge-live-restart --operator NAME --reason TEXT --json; hard-interlocked managed-model-only live restart/rehydrate route; supports podman managed-model containers and registered rerank-api idle unload/recycle, requires current confirmation contract, immediate idle/health/identity rechecks, explicit live acknowledgement, one-live lock, selected-container `podman restart` or rerank `POST /admin/unload?exit_process=true`, after-health readiness, PID/container proof, and memory delta evidence; never targets TTS, dictation, browsers, games, editors, generic work containers, sysctl, zram, swapoff, cache drop, throttling, re-affinity, cgroup caps, or service disablement
memory headroom route: abyss-machine memory headroom --json; explains zram swap headroom bottlenecks, policy shortfall to relief thresholds, protected/non-protected top swap attribution by cgroup/systemd unit, and safe next-action routes without mutating live processes or kernel/zram policy
memory residency route: abyss-machine memory residency --json; inspects protected resident service cgroups for TTS, dictation, and resident LLM, including MemoryLow/High/SwapMax, cgroup swap, sampled PSS/swap, memory events/stat, PSI, zram ratio/headroom, latest canonical hot-path probe evidence, and runtime-only pilot candidates; facts-only and does not apply cgroup properties, restart, stop, disable, throttle, re-affinitize, or cap live services; `measure_hot_path_latency` distinguishes missing/stale/failed/fresh_ok/fresh_watch probe evidence before persistent cgroup policy
memory hot-path route: abyss-machine memory hotpath-probe --json; runs synthetic TTS->STT latency probes and optional resident LLM micro tick, records before/after zram/PSI/protected-service cgroup state, and does not record microphone audio, stop/restart services, cap swap, throttle, re-affinitize, or apply cgroup properties
memory launch integration: abyss-machine ai cpu launch consumes memory plan alongside game guard and thermal route; use --force only for explicit operator override
resource status latest: {{ABYSS_MACHINE_STATE}}/resource/latest.json
resource plan latest: {{ABYSS_MACHINE_STATE}}/resource/plans/latest.json and {{ABYSS_MACHINE_STATE}}/resource/plans/YYYY/MM/YYYY-MM-DD.jsonl
resource launch latest: {{ABYSS_MACHINE_STATE}}/resource/runs/latest.json and {{ABYSS_MACHINE_STATE}}/resource/runs/YYYY/MM/YYYY-MM-DD.jsonl
resource orchestrator latest: {{ABYSS_MACHINE_STATE}}/resource/orchestrator/latest.json and {{ABYSS_MACHINE_STATE}}/resource/orchestrator/YYYY/MM/YYYY-MM-DD.jsonl
OS Abyss heartbeat latest: {{ABYSS_MACHINE_STATE}}/heartbeats/latest.json and {{ABYSS_MACHINE_STATE}}/heartbeats/YYYY/MM/YYYY-MM-DD.jsonl
OS Abyss heartbeat route: abyss-machine heartbeats pulse --json; recurring compact pulse over current nervous, doctor, resource, E2B breath, reaction, response-route, and change-ledger evidence; non-executing and `automatic_action=false`
reaction candidates latest: {{ABYSS_MACHINE_STATE}}/reactions/latest.json and {{ABYSS_MACHINE_STATE}}/reactions/YYYY/MM/YYYY-MM-DD.jsonl
reaction candidates route: abyss-machine reactions --json; converts current nervous, doctor, resource, and selected systemd evidence into operator-review candidates with reason, severity, command suggestion, and evidence pointers; non-executing and `automatic=false`
response routes latest: {{ABYSS_MACHINE_STATE}}/responses/latest.json and {{ABYSS_MACHINE_STATE}}/responses/YYYY/MM/YYYY-MM-DD.jsonl
response routes route: abyss-machine responses --json; converts reaction candidates into owner-gated response routes with command profile and approval requirement; non-executing and `automatic_response=false`
resource route: abyss-machine resource plan --class CLASS --kind KIND --json; combines mode, memory, storage, game guard, process thermal plan, and ai cpu route
resource orchestrator route: abyss-machine resource orchestrator --json; broad read-only route matrix and prerequisite audit for future agents and stack bridges
resource launch route: abyss-machine resource launch --class CLASS --kind KIND -- COMMAND; applies AllowedCPUs, CPUWeight, IOWeight, and soft MemoryHigh through user systemd-run to new processes only; use --no-thermal-sample for quick dry-run checks that should rely on the latest process thermal plan; use --success-on-block for unattended timers that should report a clean skip when overrideable gates block
resource limits rule: MemoryHigh is soft; MemoryMax and CPUQuota are not set by default; existing user/game/work/stack/persistent-model/warm-AI processes are never killed, throttled, re-affinitized, migrated, stopped, or demoted by this route
hooks: {{ABYSS_MACHINE_ETC}}/hooks.d and {{ABYSS_MACHINE_SRV}}/hooks.d
hook stages: pre_large_write, post_large_write, pre_runtime_create, post_runtime_create, pre_cache_cleanup, post_cache_cleanup, pre_podman_migration, post_podman_migration, process_snapshot
symlink tails: do not leave them for machine-owned caches/runtimes; update configs and wrappers to direct {{ABYSS_MACHINE_SRV}} paths
work root: do not use /work for machine-owned caches, runtimes, model artifacts, storage logs, or process snapshots
protected srv roots: {{ABYSS_OS_ROOT}}, /srv/GAMES, /srv/games, /srv/work, /work, abyss-stack roots, and unknown /srv/* are denied for machine-owned write/cleanup automation
Podman graphroot: already directly routed to {{ABYSS_MACHINE_SRV}}/storage{{ABYSS_USER_HOME}}/containers/storage through ~/.config/containers/storage.conf
Podman preflight: abyss-machine storage podman-preflight --json writes {{ABYSS_MACHINE_STATE}}/storage/podman-migration-preflight/latest.json without container env/create-command secrets
work-aware Podman rule: read /srv/work/rios-de-color/AGENTS.md and /srv/work/rios-de-color/local-mirror/AGENTS.md read-only before stopping or reviewing rios-audit-mariadb, socraticode-qdrant, or socraticode-ollama
Podman migration method: direct rootless storage.conf graphroot only; no symlink route; helper exits cleanly if already routed
storage inventory mode: light is safe for hourly monitoring; full is manual deep review and may measure large home/project/runtime trees
classification rule: rebuildable_cache/redownloadable_heavy are cleanup candidates only under storage pressure; project_source/work/agent-state/current-runtime/current-AI are keep/manual-review
storage pressure rule: `abyss-machine storage pressure --json` classifies `/` and `/srv`, ranks pressure valves, and never deletes anything
cleanup-plan rule: `abyss-machine storage cleanup-plan --json` runs process guard by default and produces operator steps only; it does not execute cleanup
storage monitor rule: `abyss-machine storage monitor --json` refreshes light inventory, pressure, cleanup-plan and status; it is the recurring first-read route and does not run full inventory
write preflight rule: `abyss-machine storage write-preflight --kind KIND --bytes BYTES --target PATH --json` must run before large generated writes; it returns allow/reroute/cleanup_first/deny and never creates files
apply rule: `abyss-machine storage apply --action-id ID --dry-run --json` is the first apply step; actual apply requires `--confirm`, re-runs guard/hooks, and only executes allowlisted actions
active-process guard: if cleanup-plan marks a path `blocked_active_process`, treat it as busy and do not clean it until the process exits or the operator explicitly accepts the consequence
```

## Observability

```bash
abyss-machine observability status
abyss-machine observability status --json
abyss-machine observability paths --json
abyss-machine observability latest --json
abyss-machine observability collect --json
systemctl status abyss-observability-collect.timer
systemctl status abyss-observability-collect.service
```

Persistent paths:

```bash
{{ABYSS_MACHINE_STATE}}/observability/AGENTS.md
{{ABYSS_MACHINE_STATE}}/observability/index.json
{{ABYSS_MACHINE_STATE}}/observability/thermal-battery/latest.json
{{ABYSS_MACHINE_STATE}}/observability/thermal-battery/samples/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/observability/thermal-battery/events/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/observability/thermal-battery/summaries/YYYY/MM/YYYY-MM-DD.json
{{ABYSS_MACHINE_STATE}}/observability/hotfixes/
{{ABYSS_MACHINE_ETC}}/observability/config.json
```

Current policy:

```bash
collector: {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine-observe
collector version: 0.1.1
sensor source: sysfs_hwmon, not sensors -j
blocked source: acpi_fan fan1_input because this BIOS emits VFAN/FANL ACPI errors when it is read; re-tested after BIOS RJCN31WW on 2026-05-07, still blocked
fan/control writes: forbidden in observability; use abyss-machine cooling routes
deep thermal source audit: abyss-machine cooling thermal-audit --seconds 10 --interval 2 --json
```

## Typing

```bash
abyss-machine typing status --json
abyss-machine typing paths --json
abyss-machine typing policy --json
printf %s "committed text" | abyss-machine typing ingest --stdin --source manual_cli_stdin --json
abyss-machine typing latest --json
abyss-machine typing tail --lines 20 --json
abyss-machine typing causal-context --lines 20 --json
abyss-machine typing capture-gate --source SOURCE --json
abyss-machine typing privacy-selftest --json
abyss-machine typing coverage --json
abyss-machine typing process --json
abyss-machine typing nervous-refresh --json
abyss-machine typing focused-snapshot --json
abyss-machine typing atspi-text-events --seconds 5 --json
abyss-machine typing saved-text-scan --json
abyss-machine typing saved-text-scan --prime-state --json
abyss-machine typing zsh-hook-status --json
abyss-machine typing zsh-hook-selftest --json
abyss-machine typing codex-hook-status --json
abyss-machine typing codex-hook-selftest --json
abyss-machine typing codex-prompt-hook
abyss-machine typing codex-session-tail --json
abyss-machine typing codex-session-tail --files 8 --interval 1 --forever
abyss-machine typing editor-extension-selftest --json
abyss-machine typing editor-callback-selftest --json
abyss-machine typing browser-extension-status --json
abyss-machine typing browser-extension-selftest --json
abyss-machine typing browser-webextension-selftest --json
abyss-machine typing browser-atspi-selftest --json
abyss-machine typing focused-browser-selftest --json
abyss-machine typing browser-privacy-selftest --json
abyss-machine typing end-to-end --json
abyss-machine typing redact-test --text "token=..." --json
abyss-machine typing validate --json
```

This layer records safe committed-text events for the nervous system. It is not
a raw keylogger, does not capture password fields, stores redacted text only, and
stores metadata only for login/auth/payment/secret-like contexts.
`focused-snapshot` reads the focused editable accessibility node as an app-state
snapshot, never as raw key events. Under current policy it is a safe text-route
fallback: it reads focused accessibility text only after capture-gate allows a
safe browser URL or a generic focused editable text role, while
login/private/sensitive/unknown contexts remain metadata-only or skipped.
`atspi-text-events` is the live committed accessibility text-change listener:
it runs capture-gate before reading text, allows safe generic editable text
roles outside excluded apps, keeps browser/login/private surfaces metadata-only
or skipped unless the browser URL is safe, and is still not a raw keyboard hook.
`browser-extension-status` checks the explicit Firefox extension/native-host
route. Browser text is allowed only when the page URL and field contract are
safe; login/auth/payment/messenger/password-like fields stay metadata-only or
are skipped before persistence.
`browser-webextension-selftest` opens a temporary Firefox profile, dev-loads the
local WebExtension, serves a loopback safe page, and proves the real
content-script/native-host route without mutating release Firefox profiles.
`saved-text-scan` reads recently saved text files from configured project/work
roots as committed editor evidence; secret-like paths are denied before file
read, file size is bounded, and accepted text still goes through typing redaction.
`zsh-hook-status` and `zsh-hook-selftest` verify the live shell-command adapter:
`zsh_preexec` records submitted commands only, never keystrokes or terminal
output, and the hook skips obvious secret-manager/key material routes before
ingest.
`codex-hook-status` and `codex-hook-selftest` verify the native Codex
`UserPromptSubmit` adapter: it records the submitted prompt immediately at hook
time, not by later transcript processing and not by raw keystroke capture.
Coverage distinguishes `codex-hook-selftest` probes from live prompt evidence:
selftest proves adapter readiness, but a recent non-selftest `UserPromptSubmit`
event is required before Codex-session input is counted as directly covered.
Codex project trust is part of native hook readiness: `{{ABYSS_USER_HOME}}` must stay
`trusted` in `{{ABYSS_USER_HOME}}/.codex/config.toml` for `UserPromptSubmit` hooks to
fire in this workspace.
`codex-session-tail` is the near-live fallback over Codex raw JSONL user-message
records: `event_msg.user_message` and `response_item` message records with
`role=user` / `input_text`. It reads committed submitted prompts only, still
passes capture-gate and redaction, and is counted as fallback coverage when
native `UserPromptSubmit` is not observed.
Codex raw user-message capture normalizes known non-operator envelopes:
`# Context from my IDE setup` records are reduced to the `My request for Codex`
body, and `<goal_context>` continuation blocks are not persisted as typed text.
The session-tail fallback runs as a persistent user service at roughly
one-second cadence. The old timer can remain installed as a dormant fallback;
the live service is the preferred recurring route.
`status` and `validate` expose the latest `codex-session-tail` heartbeat, age,
service/timer recurrence, event counts, raw user candidate counts, parse errors,
and policy shape so near-live Codex fallback silence is visible without waiting
for later session processing.
`editor_extension_explicit` is provided by the local VS Code extension
`abyss-machine.typing-intake`: it sends inserted committed document text only
for allowed file roots, denies secret-looking paths before invoking the CLI,
and never reads terminal output, browser forms, or raw keyboard events.
`editor-extension-selftest` proves the explicit editor ingest, capture-gate, and
causal-context route without claiming that a live VS Code UI callback fired from
a user keystroke.
`editor-callback-selftest` opens a disposable VS Code window and applies a safe
document edit through the extension host; success proves the live
`onDidChangeTextDocument` callback path into typed-input ingest without reading
raw keys, terminal output, or browser forms.
`status` and `validate` expose editor-extension proof freshness: activation
status, direct ingest selftest age, live callback selftest age, and policy
shape, so editor route drift is visible without reading editor buffers.
`browser-atspi-selftest` proves the Firefox AT-SPI fallback on a temporary
loopback page; it is not proof that the unsigned Firefox WebExtension is active.
`focused-browser-selftest` proves the focused safe-browser fallback on a
temporary Firefox loopback textarea: `atspi_focused_text_snapshot` must resolve
a safe URL, pass capture-gate, and ingest the controlled text without touching
release Firefox profiles or password fields.
`browser-privacy-selftest` proves the negative browser route on a temporary
Firefox loopback `/login.html` page: live AT-SPI and focused-browser fallback
events must stay metadata-only before text read and must not persist the
controlled visible text.
For normal Firefox AT-SPI events, a missing document URL can be inferred from a
fresh nervous browser-content accessibility capture by AT-SPI document path.
That inference uses only sanitized no-query/no-fragment URL context and does
not promote login/private/skipped browser captures to text capture.
Browser recency is explicit in `coverage` and `status`: the readmodel reports
release-profile WebExtension events, controlled temporary-profile/selftest
proofs, AT-SPI browser fallback events, latest ages, and whether the current
browser route is live, controlled-proof fresh, stale, or missing.
`end-to-end` is the passwordless proof route for the full typing chain: it runs
safe adapter selftests, checks coverage/capture-gate/causal-context, refreshes
the local nervous snapshot and FTS index by default, and writes a single proof
artifact without widening capture.
`nervous-refresh` is the recurring typing freshness tick: it updates the process
readmodel, refreshes nervous facts only when typed events are not represented
there yet, rebuilds local FTS only when freshness checks require it, and then
rebuilds nervous synthesis when a typing-driven index refresh completed.
`status` and `validate` expose the latest `nervous-refresh` heartbeat, timer
state, age, and freshness decision so typed-input processing silence is visible
without widening capture.
They also expose the latest `focused-snapshot` heartbeat, timer state, age, and
safe-route/capture-gate summary so focused-browser fallback silence is
distinguished from normal absence of a focused editable field.
They also expose the latest `saved-text-scan` heartbeat, timer state, age,
candidate/event counts, skip count, and state errors so saved-file intake
silence is distinguishable from a healthy scan with no changed files.
`saved-text-scan` keeps a separate low-signal artifact filter for generated or
reference corpora such as `legacy/artifacts` and runtime-kernel example/schema
trees. Those paths are skipped as selection noise, not treated as secrets; the
secret/password deny list remains a separate hard privacy gate.
Every accepted event carries `causal_context`: input source, destination
surface, recipient route, observable task/project binding, and a context anchor
when no project root is proven. This is read-only context evidence; it stores no
extra text and does not infer final intent or authorize action.
`capture-gate` is the offline local routing layer in front of text storage:
unknown sources and browser/login/auth/payment surfaces are metadata-only,
private messenger/password-manager contexts are hard skipped, and text is stored
only for high-confidence committed-text adapters, configured project/work
surfaces, safe browser URL fields, or proven generic editable text roles. It has
no network access, no subprocess execution, no automatic action, and no
authority to promote unknown surfaces to text capture.
`privacy-selftest` runs non-persisting synthetic probes for secret-like command
text, login URLs, messenger URLs, password contexts, and denied paths; expected
results are metadata-only or skipped, with no typed event written by the test.
`coverage` is the read-only quality surface for the typing layer: it reports
recent adapter distribution, capture-gate decisions, dominant sources, and
known blind spots without widening collection or authorizing raw keylogging.
Coverage keeps live committed-input lanes separate from the saved-file fallback:
`live_input_records` and `live_observed_adapters` show editor/browser/Codex/
shell/AT-SPI intake even when repository file snapshots dominate total records.
It also exposes `browser_input_recency`, which keeps browser freshness separate
from global record counts so browser silence is visible even when Codex or
saved-text events dominate the recent window.
`covered_with_fallbacks` means all effective safe routes are proven, but at
least one preferred route is not fully active; currently this is used when the
release Firefox WebExtension is not registered while temporary-profile
WebExtension proof and/or the AT-SPI browser fallback still cover browser input.
For `browser-atspi-selftest`, the final captured safe committed-text event is
the authoritative proof; the earlier base-text observation is diagnostic
readiness evidence and may be absent without invalidating a captured final
event.
`browser-atspi-selftest --release-profile` runs the same safe loopback probe in
the configured Firefox release profile, proving the release-profile browser
fallback without relying on the unsigned WebExtension route. It may touch normal
Firefox profile runtime state, but still uses only a local safe URL, AT-SPI
committed text events, and capture-gate filtering.
`process` is the derived typing readmodel: it sorts already-stored committed
events into causal lanes by surface, recipient, task binding, project, and
context anchor. URL origins, operator-home paths, and application surfaces can
bind non-project input without being promoted to project claims; missing anchors
remain quality gaps. The readmodel stores no extra text, widens no capture, and
authorizes no action.
`status` also reports GNOME toolkit accessibility and typed-text nervous
processing: whether `typed_text_autolog` is represented in nervous facts and the
local FTS index.

Persistent paths:

```bash
{{ABYSS_MACHINE_ETC}}/typing-policy.json
{{ABYSS_MACHINE_STATE}}/typing/AGENTS.md
{{ABYSS_MACHINE_STATE}}/typing/index.json
{{ABYSS_MACHINE_STATE}}/typing/events/latest.json
{{ABYSS_MACHINE_STATE}}/typing/events/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/typing/capture-gate/latest.json
{{ABYSS_MACHINE_STATE}}/typing/coverage/latest.json
{{ABYSS_MACHINE_STATE}}/typing/process/latest.json
{{ABYSS_MACHINE_STATE}}/typing/focused-snapshot/latest.json
{{ABYSS_MACHINE_STATE}}/typing/atspi-text-events/latest.json
{{ABYSS_MACHINE_STATE}}/typing/validate/latest.json
{{ABYSS_MACHINE_STATE}}/typing/saved-text/latest.json
{{ABYSS_MACHINE_STATE}}/typing/saved-text/state.json
{{ABYSS_MACHINE_STATE}}/typing/zsh-hook/status/latest.json
{{ABYSS_MACHINE_STATE}}/typing/zsh-hook/selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/codex-hook/events/latest.json
{{ABYSS_MACHINE_STATE}}/typing/codex-hook/status/latest.json
{{ABYSS_MACHINE_STATE}}/typing/codex-hook/selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/editor-extension/latest.json
{{ABYSS_MACHINE_STATE}}/typing/editor-extension/selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/editor-extension/callback-selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/browser-webextension-selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/browser-atspi-selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/focused-browser-selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/browser-privacy-selftest/latest.json
{{ABYSS_MACHINE_STATE}}/typing/end-to-end/latest.json
{{ABYSS_USER_HOME}}/.config/zsh/abyss-typing.zsh
{{ABYSS_USER_HOME}}/.codex/hooks.json
{{ABYSS_USER_HOME}}/.vscode/extensions/abyss-machine.typing-intake-0.1.0
{{ABYSS_USER_HOME}}/.local/bin/abyss-machine-typing-focused-snapshot-tick
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-typing-focused-snapshot.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-typing-focused-snapshot.timer
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-typing-atspi-text-events.service
{{ABYSS_USER_HOME}}/.local/bin/abyss-machine-typing-saved-text-scan-tick
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-typing-saved-text-scan.service
{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-typing-saved-text-scan.timer
```

## Dictation

```bash
abyss-machine dictation status
abyss-machine dictation status --json
abyss-machine dictation journal paths --json
abyss-machine dictation journal latest --json
abyss-machine dictation journal tail --lines 20
abyss-machine dictation audio-doctor
abyss-machine dictation audio-doctor --json
abyss-machine dictation calibrate-mic --seconds 8 --json
abyss-machine dictation calibrate-mic --from-recent --apply --json
abyss-machine dictation config get --json
abyss-machine dictation config set default_profile auto
abyss-machine dictation config set profile_policy.long_min_sec 45
abyss-machine dictation config set 'command_intent.trigger_phrases' '["команда"]'
abyss-machine dictation profile list --json
abyss-machine dictation profile get long --json
abyss-machine dictation replacements list --json
abyss-machine dictation replacements test "между agents.amd и следующим словом" --json
abyss-machine dictation intent test "Команда, веди запись" --json
abyss-machine dictation start --profile auto
abyss-machine dictation stop
abyss-machine dictation toggle --profile auto --json
abyss-machine dictation transcribe /path/to/audio.wav --profile quality --json
abyss-machine dictation complete-stopped --recording-json /run/user/1000/abyss-machine/dictation/completed/STATE.json --json
```

Useful environment toggles:

```bash
ABYSS_DICTATION_AUDIO_PREPROCESS=0
ABYSS_DICTATION_VAD_SEGMENTS=0
ABYSS_DICTATION_ADAPTIVE_DECODING=0
ABYSS_DICTATION_SMART_PUNCTUATION=0
ABYSS_DICTATION_TEXT_FIXES=0
ABYSS_DICTATION_TARGET_RMS_DBFS=-24
ABYSS_DICTATION_VAD_MIN_SECONDS=16
ABYSS_DICTATION_VAD_MIN_PAUSE_SECONDS=0.65
ABYSS_DICTATION_VAD_TARGET_SEGMENT_SECONDS=14
ABYSS_DICTATION_VAD_MIN_SEGMENT_SECONDS=5
ABYSS_DICTATION_PUNCTUATION_STYLE=soft
ABYSS_DICTATION_CLIPBOARD_PROVIDER=foreground
ABYSS_DICTATION_CLIPBOARD_SETTLE_SECONDS=0.12
ABYSS_DICTATION_YDOTOOL_KEY_DELAY_MS=45
```

Persistent settings live in:

```bash
{{ABYSS_MACHINE_ETC}}/dictation/config.json
{{ABYSS_MACHINE_ETC}}/dictation/replacements.json
{{ABYSS_MACHINE_STATE}}/dictation/AGENTS.md
{{ABYSS_MACHINE_STATE}}/dictation/transcripts/latest.json
{{ABYSS_MACHINE_STATE}}/dictation/transcripts/jsonl/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/dictation/transcripts/readable/YYYY/MM/YYYY-MM-DD.md
```

Priority is:

```bash
built-in defaults -> {{ABYSS_MACHINE_ETC}}/dictation/config.json -> environment overrides
```

Service control:

```bash
systemctl --user status abyss-dictation-server.service
systemctl --user restart abyss-dictation-server.service
systemctl status abyss-dictation-hotkey.service
systemctl status input-remapper.service
```

GNOME Wayland usually rejects direct `wtype` insertion, so the practical insert path is foreground `wl-copy` plus `ydotool`. Daemon `wl-copy` timed out under the hotkey/runuser path on 2026-05-07 and must not be used as the default. For `Copilot+RightAlt`, the listener waits for both keys to be released before stopping; do not reintroduce early finish-on-first-release behavior. Hold-to-dictate uses direct hotkey-side stop plus background `complete-stopped`, so the listener can accept the next recording while the previous phrase is still transcribing/inserting.

## Work Modes

```bash
abyss-machine mode list
abyss-machine mode status --json
abyss-machine mode paths --json
abyss-machine mode policy --json
abyss-machine mode plan --json
abyss-machine mode validate --json
abyss-machine mode set ai --json
abyss-machine mode set previous --json
abyss-machine mode reconcile --json
```

Persistent paths:

```bash
{{ABYSS_MACHINE_ETC}}/mode-policy.json
{{ABYSS_MACHINE_STATE}}/mode/AGENTS.md
{{ABYSS_MACHINE_STATE}}/mode/index.json
{{ABYSS_MACHINE_STATE}}/mode/latest.json
{{ABYSS_MACHINE_STATE}}/mode/plans/latest.json
{{ABYSS_MACHINE_STATE}}/mode/plans/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/mode/validate/latest.json
```

Current policy:

```bash
GNOME panel power-saver -> Abyss saver: target power-saver, quiet cooling, probe/light unattended work only
GNOME panel balanced -> Abyss balanced on AC: target balanced, standard cooling unless thermal policy escalates, medium unattended work when cool enough
GNOME panel performance -> Abyss performance on AC: target performance, fan_mode=4 performance cooling, heavy unattended work only when thermal policy allows
active GameMode/external boost: preserve a stronger `performance` profile while GameMode or `processes game-guard` reports an active game/operator workload; expose it as `external_power_profile_guard`, not generic drift/degraded mode
battery discharging: effective mode is saver even if selected mode is balanced/performance/ai; selected mode is preserved for AC restore
ai overlay: selected through `abyss-machine mode set ai`; it maps to performance hardware targets but remains a host overlay, not a fourth GNOME panel profile
thermal hot/critical: preserve the selected power profile on AC when possible, apply emergency cooling target, and gate new unattended work by class cap (`hot` <= `light`, `critical` <= `probe`); do not kill already running operator tasks
routes: callers should use `abyss-machine mode plan --json`, `abyss-machine processes game-guard --json`, `abyss-machine processes thermal-plan --json`, `abyss-machine ai policy --json`, and `abyss-machine ai cpu route --class CLASS --json` before launching heavy local AI or agent work; use `abyss-machine ai cpu launch --class CLASS -- COMMAND...` when the host layer should apply taskset/env hints to a new process
automation: abyss-power-profile-auto.timer runs mode reconcile every 30s and applies the current mode/cooling plan
```

## Cooling

```bash
abyss-machine cooling status
abyss-machine cooling status --json
abyss-machine cooling paths --json
abyss-machine cooling recommend --json
abyss-machine cooling apply --profile auto --json
abyss-machine cooling thermal-audit --seconds 10 --interval 2 --json
abyss-machine cooling fan-validate --levels 50 --seconds 8 --interval 2 --json
abyss-machine cooling fan-series --level 50 --repeats 3 --seconds 8 --interval 2 --cooldown 5 --state-label current_hot --json
abyss-machine cooling tfn1-write --level 50 --seconds 3 --json
pkexec abyss-machine cooling apply --profile auto --json
pkexec abyss-machine cooling apply --profile emergency --json
pkexec abyss-machine cooling fan-validate --levels 50 --seconds 8 --interval 2 --json
pkexec abyss-machine cooling fan-series --level 50 --repeats 3 --seconds 8 --interval 2 --cooldown 5 --state-label current_hot --json
pkexec abyss-machine cooling tfn1-write --level 50 --seconds 3 --json
systemctl status abyss-power-profile-auto.timer
systemctl status abyss-power-profile-auto.service
```

Persistent paths:

```bash
{{ABYSS_MACHINE_ETC}}/cooling/config.json
{{ABYSS_MACHINE_STATE}}/cooling/AGENTS.md
{{ABYSS_MACHINE_STATE}}/cooling/index.json
{{ABYSS_MACHINE_STATE}}/cooling/latest.json
{{ABYSS_MACHINE_STATE}}/cooling/actions/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/cooling/thermal-audit/latest.json
{{ABYSS_MACHINE_STATE}}/cooling/thermal-audit/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/cooling/fan-validate/latest.json
{{ABYSS_MACHINE_STATE}}/cooling/fan-validate/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/cooling/fan-series/latest.json
{{ABYSS_MACHINE_STATE}}/cooling/fan-series/YYYY/MM/YYYY-MM-DD.jsonl
{{ABYSS_MACHINE_STATE}}/cooling/thermal-fan-v2-plan.md
```

Current policy:

```bash
cooling backend: platform_profile + Lenovo VPC2004 fan_mode
documented Lenovo fan modes: 0 super silent, 1 standard, 2 dust cleaning, 4 efficient thermal dissipation
observed firmware-default fan mode readback on this machine: 16, but writing 16 returned Invalid argument on 2026-05-06; do not use 16 as an auto-policy write target
acpi TFN1 candidate: INTC1063:00 exposes fan performance states and fine_grain_control=1; guarded writes of 50 succeeded, one short validation observed 105C->98C, but cur_state/RPM feedback is unavailable; repeated fan-series on 2026-05-06 wrote 50 successfully with kernel-ok, but possible cooling effect was only 1/3 in current_hot and 1/3 in current_warm, so it is manual-only and not automated
thermal audit route: abyss-machine cooling thermal-audit --seconds N --interval M --json; separates coretemp, firmware zones, component sensors, and cpu_hotspot distribution
fan validation route: abyss-machine cooling fan-validate --levels 50 --seconds N --interval M --json; manual/root only, refuses zero/off writes and lower-than-max levels while hot/critical
fan series route: abyss-machine cooling fan-series --level 50 --repeats N --seconds S --interval I --cooldown C --state-label LABEL --json; manual/root repeated evidence route for TFN1 automation gate
manual TFN1 route: abyss-machine cooling tfn1-write --level 50 --seconds N --json; refuses zero/off writes and checks kernel fan errors after the write
hotspot routing: cooling status includes temperature.summary.cpu_hotspot in abyss-machine 0.8.18+; conservative max remains a fan/power safety signal, but CPU work routing should avoid hot mapped cores instead of stopping all CPU use because one core is hot
do not read/write: PNP0C0B FAN0..FAN4 cooling_device cur_state; FAN0 test failed with missing ACPI method _SB.PC00.LPCB.UPFS
do not write/read rpm: VFAN / PNP0C0B:05; VFAN/FANL telemetry path is broken, including after BIOS RJCN31WW validation on 2026-05-07
abyss-machine 0.8.14 cooling status: skips TFN1/FAN0..FAN4/VFAN cur_state reads to avoid triggering broken ACPI paths
lm_sensors note: do not install an acpi_fan ignore rule; it hides fan1 but breaks sensors -j by producing invalid JSON
performance: platform_profile=performance and fan_mode=4
emergency: preserve selected platform profile and apply fan_mode=4
balanced: selected platform profile and writable fan_mode=1 standard
saver: selected platform profile and writable fan_mode=0 super silent
automation: abyss-power-profile-auto.timer runs mode reconcile every 30s and applies cooling auto-policy
emergency hysteresis: once fan_mode=4 is active, auto-policy keeps emergency until at or below recovery_temperature_c; after a thermal-origin emergency or hold-threshold event it also holds fan_mode=4 for min_emergency_hold_seconds to avoid 4->1->4 oscillation without self-extending on repeated timer reconciles
rpm source: do not read acpi_fan fan*_input; this BIOS emits ACPI VFAN/FANL errors
raw EC/PWM writes: forbidden unless a future proven backend explicitly replaces this contract
```

## Snapshots

```bash
abyss-machine snapshots
abyss-machine snapshots --json
snapper -c root list
```

## Notes

- Keep host-layer integration stable and JSON-first.
- Do not write into `~/src/abyss-stack` from this host layer.
- Prefer `abyss-machine` commands over direct implementation details when another agent or `abyss-stack` needs host data.
