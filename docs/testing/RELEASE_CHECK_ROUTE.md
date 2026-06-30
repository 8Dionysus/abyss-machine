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
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --json
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
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile diagnostic-read --json
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile ai-llm-refresh --allow-runtime-refresh --json
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --runtime-profile storage-refresh --allow-runtime-refresh --json
```

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
