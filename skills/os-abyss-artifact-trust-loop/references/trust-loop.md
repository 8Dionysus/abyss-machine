# Route one artifact to one consumer verdict

## Establish the exact request

Record the smallest useful identity:

- artifact path, manifest, bundle, registry record, digest, or class;
- source owner and exact source ref when known;
- consumer intent such as `agent`, `installer`, `runtime`, `update_client`, or
  `release_consumer`;
- requested phase and effects;
- whether installed host state, a supplied isolated registry, or source-only
  policy is the observation target.

Do not broaden a question about one artifact into whole-OS coverage. Do not
turn an audit into production or promotion.

## Resolve the owner route without loading the whole trust plane

Use the owner read models as the compact index. Do not start by loading the
complete artifact policy, bundle README, all producer route refs, or every
artifact command.

1. Use `requirements` for class, controls, owner, trust-root posture, matching
   bundle refs, and compact producer data.
2. Read only the matching `manifests/artifact_bundles/*.bundle.json` when the
   task needs its producer or consumer command.
3. Before `prepare`, read the artifact owner repository's `AGENTS.md` and only
   the route refs that apply to the selected class and requested effect. A
   generic producer profile may list refs for several classes; do not load all
   of them.
4. Read a targeted policy fragment only when the read model leaves one
   material field unresolved. Never print the complete policy into context.

The policy is an OS read model over owner routes. It does not transfer source,
build, release, or proof authority to `abyss-machine`.

## Inspect

Run the smallest current owner read set. From the source checkout use
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m abyss_machine.cli`; from an
installed owner use `abyss-machine`.

Some commands named as read models persist generated latest/history/index
files. They are observational in authority but not necessarily zero-write at
the filesystem. When live generated-state writes are not authorized, bind all
four owner roots to one task-local directory:

```text
ABYSS_MACHINE_STATE_ROOT=TMP/state
ABYSS_MACHINE_ROOT=TMP/srv
ABYSS_MACHINE_RUN_ROOT=TMP/run
ABYSS_MACHINE_ETC_ROOT=TMP/etc
```

Remove that task-local state at closeout. Do not use
`ABYSS_MACHINE_SRV_ROOT`; the owner variable is `ABYSS_MACHINE_ROOT`.

Run these commands sequentially when they share owner state. Their latest and
index writes make them incompatible parallel DAG nodes.

Choose by phase rather than running the whole list:

```text
artifacts requirements --artifact-class CLASS --json
artifacts producer-profiles --artifact-class CLASS --json
artifacts affected --registry-dir REGISTRY --artifact-class CLASS --source-repo OWNER --source-ref REF --json
artifacts registry-latest --registry-dir REGISTRY --artifact-class CLASS --consumer-intent INTENT --json
artifacts trust-gate --registry-dir REGISTRY --artifact-class CLASS --consumer-intent INTENT --json
```

For `admit` with an already known class and explicit registry, begin with
`registry-latest`, extract the selected record and subject digest, then run one
fully bound `trust-gate`. Run `requirements` only if controls or policy posture
are not already available. Run `producer-profiles` only for `prepare` or an
explicit producer audit. Run `affected` only when current-source drift or
changed paths are part of the question; an exact gate already bound to a
supplied source ref does not need ceremonial `affected`.

The command ABI above is sufficient for this phase. Do not search CLI source,
read registry files directly, call `--help`, or inspect implementation merely
to reconfirm a valid bounded result. If a required output field is absent,
report it as unknown or skipped; do not expand into implementation archaeology.

Add `--require-command-resolution` to `producer-profiles` only when the relevant
owner checkout roots are available. Pass `--workspace-root` or
`--owner-repo-root OWNER=PATH` when the default workspace does not contain the
owner. Command resolution proves references exist; it does not execute owner
validators.

Pass the same explicit `--registry-dir` to `affected`, `registry-latest`,
`trust-gate`, coverage, and validation commands whenever they support it. Do
not let one phase silently fall back to a different default registry.

Use `affected` only with the changed paths and source constraints material to
the request. Use `trust-coverage`, `scenarios`, and `validate` for an explicit
plane-wide audit or when the selected class/read model reports a wider
dependency; they are not mandatory ceremony for every artifact.

Never print complete requirements, producer-profile, registry record, affected
matrix, or gate documents into model context. Use `jq` or a bounded
programmatic projection to retain:

- top-level `ok`, schema, policy/version, errors, and write errors;
- class, owner, required/deferred controls, selected producer commands, and
  matching bundle refs;
- selected record id, subject digest, lifecycle, source owner/ref, trust-root
  mode, verification and controls;
- exact verdict, blockers, warnings, manual review, and only the inspected
  identity claims needed by the request.

Do not hide `ok=false` or write errors merely because the desired fields were
present.

For identity-bound consumption, also pass every supplied constraint supported
by the command: `--subject-digest`, `--record-id`, `--source-repo`,
`--source-ref`, `--access-policy`, and `--trust-root-mode`. A gate that did not
bind a requested identity is not the requested gate.

### MCP fidelity gate

The optional `abyss_machine_surface` MCP can inspect allowlisted artifact
surfaces such as requirements, producer profiles, affected, coverage,
registry-latest, trust-gate, scenarios, and validate.

Before accepting an MCP result:

1. require the wrapper to report `ok=true` and parsed payload;
2. require `payload_ok=true` for an owner command whose payload has an `ok`
   field;
3. inspect the reported command and confirm it actually includes every
   requested identity constraint;
4. compare policy version, source context, latest identity, and freshness with
   the target of the question.

If any check fails, preserve the MCP result as degraded access-plane evidence
and run the exact source-owned CLI command. Do not combine a stale MCP
requirements result with a newer CLI gate into a single green claim.

## Prepare owner evidence

Run this phase only when the request authorizes the corresponding effect.

1. Select the matching owner bundle manifest or producer profile.
2. Follow its current `consumer_command`, producer commands, and owner route;
   do not reconstruct a signing or release sequence from memory.
3. Build or refresh only the named artifact and sidecars.
4. Verify the bundle and required controls.
5. Run the owner-local validators that establish the producer claim.
6. Promote evidence or change lifecycle only when that registry effect is part
   of the request and the supplied evidence refs are durable and truthful.

A build result is not verification. Verification is not promotion. Promotion
is not latest selection. Latest selection is not consumer admission.

Never use MCP for this phase. Never invent trust-root evidence, replace a dirty
source ref with a clean one, or describe local-development credentials as
public-release trust.

## Admit the exact consumer

Run `registry-latest` and `trust-gate` sequentially after the last
evidence-changing effect. Bind the selected record and subject digest plus the
requested source, access policy, trust-root mode, and consumer intent.

Interpret outcomes literally:

- `allow`: the exact checked consumer may proceed within the reported claim
  limits;
- `warn`: admission may be permitted by policy, but every warning remains live
  in the handoff and closeout;
- `deny`: stop consumption and return blockers;
- `manual_review_required`: stop automated consumption and name the missing
  human or owner decision;
- `unknown` or no registry record: fail closed.

Build the result claim limit from the checked identity and phase boundary:
the verdict applies only to the selected consumer, registry record, subject,
source constraints, access policy, and trust-root posture; the gate does not
build, independently verify, promote, consume, publish, or authorize a later
effect. A missing claim-limit field in CLI JSON does not justify reading the
implementation.

For public media, preserve C2PA credential/trust-list limitations. For update
or installer consumers, preserve TUF, trust-root evidence, lifecycle, subject
store, and freeze/rollback requirements. For OCI consumption, preserve
digest-pinned subject and required referrer constraints.

## Audit and close out

An audit may inspect `requirements`, `producer-profiles`, `affected`,
`trust-coverage --durable-only`, `scenarios`, and `validate`, but it must
separate:

- source policy from installed policy;
- durable registry evidence from manual or temporary evidence;
- producer validation from consumer admission;
- local integrity from public-release trust;
- missing evidence from stale evidence and accepted lag.

Return compact fields from the contract. Do not dump full registry records,
private host paths, credentials, raw evidence, or unrelated artifact classes.
Delete task-local bundles, registries, prompts, rubrics, and DAG notes after the
manual trial or task no longer needs them.
