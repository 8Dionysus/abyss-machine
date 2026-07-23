---
name: os-abyss-artifact-trust-loop
description: "Route an OS Abyss artifact through owner classification, required controls, producer evidence, drift, durable registry selection, and fail-closed consumer admission. Use before building, releasing, updating, installing, publishing, or consuming an Abyss bundle, package, container, model/runtime, generated read model, portable export, browser extension, or public media artifact; also use to diagnose stale provenance, SBOM, signatures, C2PA, TUF, OCI, source-ref, registry-latest, or trust-gate evidence. Do not use for ordinary source edits or tests with no artifact boundary, generic supply-chain explanations, raw session retrieval, or source-authority disputes."
---

# OS Abyss Artifact Trust Loop

Carry one artifact from an owner-owned source or candidate to an honestly
classified consumer verdict without creating a second trust authority.

The skill is the callable procedure. `abyss-machine` owns artifact policy,
registry and gates; producer repositories own their artifacts and producer
commands; MCP is only a bounded read plane.

## Applicability preflight

Use the bundle when the requested result depends on at least one of:

- artifact class, bundle manifest, producer profile, sidecar, provenance, SBOM,
  signature, C2PA, TUF, OCI, SCITT, subject digest, source ref, registry record,
  drift, trust coverage, or a consumer gate;
- whether an OS Abyss agent, installer, runtime, updater, release consumer, or
  publisher may consume a concrete artifact;
- preparing or refreshing evidence through a named owner producer route.

Return `not_applicable` before resolving the owner for an ordinary code change,
test, Git operation, generic security explanation, raw `.aoa` session lookup,
or authority-map question that does not cross an artifact boundary.

If the request mentions a possible artifact but supplies neither a concrete
artifact/class nor enough context to classify it, select `inspect` and preserve
the class as `unknown`; do not silently choose the nearest class.

## Return to the owner source

Use the skill directory reported by the host as the initial bundle root.

1. If it is `<owner-root>/skills/os-abyss-artifact-trust-loop/`, require the
   adjacent owner root to be the `abyss-machine` source checkout and use it.
2. Otherwise read only `.aoa-skill-source.json` beside this `SKILL.md`.
3. Require `schema_version` to be `aoa_skill_source_receipt_v1` or
   `aoa_skill_source_receipt_v2`,
   `name=os-abyss-artifact-trust-loop`, `owner_repo=abyss-machine`,
   `source_path=skills/os-abyss-artifact-trust-loop`, and `version=0.1.1`.
   For v2 also require non-empty `digest`, `source_fingerprint`,
   `source_fingerprint_scope`, and `prompt_description_sha256`. When
   `capability_graph_hash` is present, require it to be a non-empty string and
   preserve it.
4. Follow the exact `owner_root` and `source_path` from the receipt. Require
   the owner contract to repeat the same identity, version, and admitted
   lifecycle.
5. Stop as `blocked_owner_source` when the receipt or canonical package is
   missing, ambiguous, or version-stale. Do not search sibling repositories
   for a plausible copy.

Report the receipt schema and v2 identity dimensions when present. The receipt
locates and identifies source; it does not prove current policy, evidence,
runtime parity, or consumer admission.

## Start

From the canonical owner bundle:

1. Read [references/contract.yaml](references/contract.yaml).
2. Select the smallest phase set needed by the request:
   `inspect`, `prepare`, `admit`, or `audit`.
3. Name the artifact or candidate, consumer intent, expected source owner/ref,
   requested effects, and whether current installed evidence is required.
4. Read [references/trust-loop.md](references/trust-loop.md) and execute only
   the selected phases.

Do not preload unrelated owner docs, every artifact command, or sibling
repositories. Let the selected artifact class and its producer profile narrow
the route.

## Owner and effect boundary

- `abyss-machine` owns artifact-class policy, durable registry meaning,
  trust-root posture, drift/read models, and fail-closed admission.
- The artifact's source repository owns build inputs, producer behavior,
  release meaning, and owner validators. A central matrix, generated graph, MCP
  result, or this skill cannot replace that owner.
- MCP may inspect allowlisted read models. It may not build, sign, promote,
  repair, mutate the registry, change trust roots, publish, or run arbitrary
  commands.
- MCP observation and `admit` are read-only. Some source-CLI read models also
  refresh generated latest/history state; when live writes are not requested,
  bind them to isolated temporary owner roots and remove that state afterward.
  `prepare` and any registry or publication effect run only when the request
  authorizes that effect and the owner route names it.
- Never infer that a successful build or verification authorizes promotion or
  consumption. Re-run the exact consumer gate after the evidence changes.

## Task-local composition

Build only the edges required for this artifact:

```text
source owner and concrete artifact
  -> artifact class and required controls
  -> owner producer profile
  -> build or refresh evidence when authorized
  -> verify and durable registry selection
  -> exact consumer trust-gate verdict
  -> consume, stop, or hand off
```

The graph ends at the requested consumer decision. It is not a persistent
workflow, a new artifact authority, or permission to complete a release.

## Stop

Return one bounded result containing:

- selected phases, artifact identity/class, consumer intent, owner and source
  ref;
- policy/source surface used and any MCP/CLI fidelity or freshness difference;
- required, present, verified, missing, stale, or deferred controls;
- producer route and actual effects;
- registry/latest identity and exact gate verdict;
- blockers, warnings, manual review, skipped checks, next owner, and claim
  limit.

Preserve `allow`, `warn`, `deny`, `manual_review_required`, and `unknown` as
different outcomes. Stop after one artifact and one consumer decision.
