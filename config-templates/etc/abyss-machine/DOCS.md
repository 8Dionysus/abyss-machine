# Abyss Machine Documentation Contract

This document defines how host-layer documentation stays useful without turning
into a second source tree or a stale command dump.

## Source Hierarchy

When documentation conflicts, prefer this order:

1. Source contracts in `{{ABYSS_MACHINE_ETC}}`, especially `DOCS.md`,
   `DESIGN.md`, `DESIGN.AGENTS.md`, `ROADMAP.md`, `CHANGELOG.md`,
   `decisions/`, `TOPOLOGY.md`, `STACK-BRIDGE.md`, policy JSON, and config
   JSON.
2. Local large-root design in `{{ABYSS_MACHINE_SRV}}/DESIGN.md` when work is
   specifically about `{{ABYSS_MACHINE_SRV}}` data, runtime, storage, tool, or
   design-artifact routing.
3. Owner-local `AGENTS.md` files for the exact subsystem or root being changed.
4. Generated compact indexes and latest facts under `{{ABYSS_MACHINE_STATE}}`.
5. Append-only JSONL history under `{{ABYSS_MACHINE_STATE}}`.
6. Runtime state under `/run` or large/cache state under `{{ABYSS_MACHINE_SRV}}`.

Generated facts accelerate orientation, but they do not replace source
contracts. Project repositories remain read-only from this host layer unless an
explicit owner route says otherwise.

## Document Roles

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md` is the first agent orientation document. It
  should point to the right routes and policies, not duplicate every command.
- `{{ABYSS_MACHINE_ETC}}/DESIGN.md` is the host-machine system-form contract.
- `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md` is the agent-facing mesh and card-form
  contract.
- `{{ABYSS_MACHINE_ETC}}/ROADMAP.md` is the host-wide direction and future-trigger
  surface. It is not a task list or change history.
- `{{ABYSS_MACHINE_ETC}}/decisions/` explains durable rationale for structural,
  route-law, validation, bridge, topology, and source-boundary choices. Current
  source surfaces define what.
- `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json` is the generated
  compact index of decision records for quick access to what changed when and
  why. It is not source truth.
- `{{ABYSS_MACHINE_ETC}}/CHANGELOG.md` is a sparse curated milestone surface.
  Exact host mutation history lives in `{{ABYSS_MACHINE_STATE}}/changes/`.
- `{{ABYSS_MACHINE_ETC}}/agents-mesh.json` is the source config for local
  `AGENTS.md` coverage and marker validation.
- `{{ABYSS_MACHINE_ETC}}/commands.md` is the operator command catalog. Put command
  lists here instead of copying them into `AGENTS.md` or README files.
- `{{ABYSS_MACHINE_ETC}}/MAPS.md` and `{{ABYSS_MACHINE_ETC}}/maps-policy.json` are
  the source contract and policy for the generated machine atlas.
- `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md` is the root/surface/topology contract.
- `{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md` is the read-only host-to-stack handoff
  contract.
- `{{ABYSS_MACHINE_SRV}}/DESIGN.md` is the local large-root design contract for
  cache, runtime, storage, temporary, tool, hook, and design-artifact routing.
- `/usr/local/share/abyss-machine/README.md` is only a short installed pointer
  to the authoritative `{{ABYSS_MACHINE_ETC}}` documents.
- `{{ABYSS_MACHINE_STATE}}/*/AGENTS.md` and `index.json` are subsystem
  entrypoints generated or maintained for quick orientation.
- `{{ABYSS_MACHINE_STATE}}/maps/` is a generated atlas of route signals across
  time, subsystems, causal chains, freshness, resources, risk, and handoffs.
- `abyss-machine-maps-refresh.timer` is the bounded user-scope refresh route
  for that atlas; it updates generated indexes and does not execute responses or
  memory/proof/KAG handoffs.
- `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json` is a generated compact
  mirror of the source cards. It is not source truth.

## Do Not Duplicate

- Do not maintain parallel command catalogs in README files, generated facts, or
  subsystem notes.
- Do not paste large JSON outputs into Markdown. Link the latest JSON path and
  the command that refreshes it.
- Do not turn generated `latest.json` files into prose source truth.
- Do not turn `ROADMAP.md` into a task backlog or a recap of every closed
  change.
- Do not turn `CHANGELOG.md` into the host change ledger.
- Do not let decision records override current source contracts.
- Do not hand-edit the generated decision index; rebuild it from source records.
- Do not document future claims as current readiness. Use explicit labels such
  as `candidate`, `facts-only`, `review`, or `operator-required`.

## Update Rules

Update documentation in the same change as behavior when:

- a CLI command, argument, schema, policy path, or root role changes;
- a subsystem gets a new `AGENTS.md`, `index.json`, timer, or validation route;
- a bridge field becomes stable enough for future agents to rely on;
- a generated surface is intentionally retired or renamed.
- host-wide direction or future triggers move, in which case update
  `ROADMAP.md`;
- durable rationale is needed for a structural, source-boundary, route-law,
  validation, bridge, or topology choice, in which case add a decision record;
- a curated milestone contour changes, in which case update `CHANGELOG.md`.
- a decision record changes, in which case rebuild the generated decision index.

After documentation changes, run:

```bash
abyss-machine docs audit --json
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine topology validate --json
abyss-machine graph validate --json
abyss-machine stack-bridge validate --json
```

Use `abyss-machine docs audit --strict --json` when closing a documentation
cleanup pass and all warnings are expected to be resolved.

## Generated Evidence

The documentation audit writes:

```text
{{ABYSS_MACHINE_STATE}}/docs/latest.json
{{ABYSS_MACHINE_STATE}}/docs/index.json
{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json
{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/latest.json
{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json
{{ABYSS_MACHINE_STATE}}/docs/audit/YYYY/MM/YYYY-MM-DD.jsonl
```

These are evidence and drift signals. They are not a replacement for this
contract or for the source documents above.
