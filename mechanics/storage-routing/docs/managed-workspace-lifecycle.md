# Managed workspace lifecycle

`abyss-machine storage lifecycle` is the thin owner boundary for new heavy
workspaces. It does not classify old directories and does not infer value from
names, age, process absence, or storage pressure.

## Contract

Each managed workspace has three durable states:

```text
open -> sealed -> released
```

- `open` carries a capability-bound lease while the launcher owns execution.
- `sealed` binds the exact filesystem fingerprint and physical byte count after
  execution ends.
- `released` exists only after the owner returns `DELETE(plan)` or
  `ARCHIVE(plan)`. `KEEP` and `UNKNOWN` remain sealed and blocked.

The normal entrypoint is one launch, not a cleanup ceremony:

```bash
abyss-machine resource launch \
  --workspace /srv/abyss-machine/tmp/producer/job-id \
  --workspace-owner producer-capability \
  -- COMMAND...
```

The launcher creates an absent workspace, opens its lease, and supplies these
variables to the launched owner:

```text
ABYSS_MANAGED_WORKSPACE_ID
ABYSS_MANAGED_WORKSPACE_PATH
ABYSS_MANAGED_WORKSPACE_DISPOSITION
```

Before exit, the owner may atomically write the disposition path as JSON:

```json
{"decision":"DELETE","plan":{"kind":"delete_workspace"},"owner_evidence_refs":["result:exported"]}
```

For archive, the owner supplies an exact absolute target:

```json
{"decision":"ARCHIVE","plan":{"kind":"archive_workspace","target":"/mounted/vault/path/job-id","required_mount":"/mounted/vault"}}
```

No callback is `UNKNOWN`; it never grants mutation.

## Executor

The launcher seals on process completion. The lightweight reaper inspects only
released registry records and processes at most one object per invocation. It
rechecks the grace deadline, live process and mount references, full seal
fingerprint, and original inode. Delete detaches the exact inode with an atomic
sibling rename before removal. Archive copies to a partial target, verifies the
same content digest, publishes the archive without overwrite, and only then
detaches the local inode. A per-workspace execution journal makes an authorized
detach resumable after interruption. Each applied action writes a byte receipt.

The archive executor requires an exact live mount (default `/abyss` for older
plans), a target beneath it without symlink ancestors, and the same mount
identity before local detach/removal. An absent Vault never creates archive
payloads in the unmounted directory on `/`. A changed source fingerprint blocks
detach; resumed detached archives are content-verified again before removal.

An existing directory may be observed and sealed, but it is not eligible for
automatic disposition because launcher creation was not proven. Old data stays
under the separate candidate/reconciliation route.

## Health

```bash
abyss-machine storage lifecycle status --json
```

The compact readout exposes `active_managed_bytes`,
`sealed_reclaimable_bytes`, and `blocked_bytes`. `unmanaged_bytes` stays unknown
until a bounded owner inventory supplies its coverage; the lifecycle does not
scan all of `/srv` to invent that number.

## Recovery

The event path performs normal sealing. The timer only retries released
dispositions after crashes and never broad-scans subject trees. Disabling the
timer stops mutation without invalidating compact lifecycle records or owner
receipts.
