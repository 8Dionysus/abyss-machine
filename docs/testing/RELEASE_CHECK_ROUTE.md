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
