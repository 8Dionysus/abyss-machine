# Landing Log

- Initial skeleton: package created to route storage and cache work.
- 2026-08-01: Added persistent hard-gated candidate history, owner adapters,
  leases, exact validation, changed-only notifications, and a daily deep timer;
  no automatic subject mutation was added.
- 2026-08-30: Added the separate managed-workspace thin waist for new launcher-
  created objects: lease, exact seal, owner release, bounded revalidation,
  atomic detach/archive, and byte receipts. Existing candidates remain outside
  this automatic executor.
