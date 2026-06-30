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

Report live-host results separately from public CI. Do not copy the underlying
`/var/lib/abyss-machine`, `/srv/abyss-machine`, browser, typing, transcript,
index, cache, or model-weight contents into the repository.

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
