# Schemas

These JSON Schemas are v1 anchors for public contract shape. They intentionally
start permissive and will tighten as bootstrap reports and policy files settle.

- `local-provenance-packet.schema.json` anchors the private host evidence packet
  shape; it does not make live `/var/lib/abyss-machine` evidence public.
- The C18 and C19 active-organ schemas are strict security-boundary contracts,
  not permissive telemetry drafts. They expose only sanitized references and
  host admission and cannot carry raw host data, launch execution, project
  mutation, stack mutation, memory semantics, or broader effect authority.
- `active-organ-host-erasure-owner-extension-v0.schema.json` is the strict ER6
  reference-lab boundary. It carries a managed-root class and
  content-minimized physical/recovery evidence without disclosing host paths,
  and it forbids project/stack mutation, live execution, and global completion.
