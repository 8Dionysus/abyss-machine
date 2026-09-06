# Landing Log

- Initial skeleton: package created to route storage and cache work.
- 2026-08-01: Added persistent hard-gated candidate history, owner adapters,
  leases, exact validation, changed-only notifications, and a daily deep timer;
  no automatic subject mutation was added.
- 2026-08-30: Added the separate managed-workspace thin waist for new launcher-
  created objects: lease, exact seal, owner release, bounded revalidation,
  atomic detach/archive, and byte receipts. Existing candidates remain outside
  this automatic executor.
- 2026-09-06: Prepared a capacity-only five-minute user service/timer that
  records the existing cheap capacity feed through the installed generation-
  guarded entrypoint. The source units intentionally do not run monitor,
  inventory, deep refresh, cleanup, or lifecycle work; activation remains
  pending owner review.
