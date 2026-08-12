# Resource Thermal Admission Comparison

## Question

Which thermal evidence belongs on the synchronous `resource launch` critical
path without weakening the existing temperature, CPU-route, game-guard, mode,
memory, storage, or atomic startup-reservation gates?

The full process thermal plan is intentionally broader than that question. It
waits for `/proc` CPU attribution and inspects the desktop/compositor so an
operator can investigate heat. Neither result changes the CPU route or the
resource admission verdict.

## Compared Methods

Run from the source checkout:

```bash
python scripts/benchmark_resource_thermal_admission.py \
  --class medium --latency balanced --repetitions 1
```

Three live comparisons on 2026-08-12 produced:

| Method | Observed wall-time range | Disposition | Evidence boundary |
| --- | ---: | --- | --- |
| direct emergency sensor | 0.001-0.006 s | retained for runtime cold-load admission | direct CPU hwmon emergency only |
| direct CPU thermal map | 0.018-0.036 s | retained as a required input | current package/core class and safe/avoid CPU sets |
| request-specific thermal admission | 0.573-0.745 s | selected for `resource launch` | fresh thermal map plus the exact requested CPU route |
| full process thermal plan | 10.033-11.252 s | retained as an operator diagnostic | admission evidence plus process attribution and desktop/compositor context |

The selected method was 15.105-17.524 times faster than the full diagnostic in
those comparisons. The emergency-only method was not selected for `resource launch`:
it cannot prove per-core avoidance, routed-heavy policy, or the route for the
requested workload class. Reusing only a latest document was also rejected as
the primary proof because another request can replace it and its sensor state
can be stale.

## Claim and Evidence Split

The synchronous launch graph now requires these fresh nodes in two waves:

- wave 1, parallel: direct CPU thermal map, mode plan, game guard, and the
  request-specific storage write preflight when a write is declared;
- wave 2: request-specific thermal admission, derived from that exact thermal
  map and mode plan.

They run in parallel outside the startup lock. The thermal receipt carries the
full CPU-route document into the final plan, so a concurrent writer cannot
silently substitute a different latest route. A missing thermal map, failed
route, workload-class, latency, or force identity mismatch, or malformed route
payload makes the attestation fail closed. The final lock still owns the fresh
memory/PSI check, reservation recheck, sufficiency decision, and atomic lease
creation.

The following evidence remains available but is no longer a prerequisite for
starting unrelated work:

- repeated `/proc` thread CPU attribution;
- desktop/compositor inspection;
- the assembled all-workload thermal diagnostic.

No diagnostic was removed. `abyss-machine processes thermal-plan --json`,
`thermal-attribution`, and `desktop-compositor` retain their existing commands
and evidence shapes.

## End-to-End Source Proof

The triggering real source launch spent 10.362 seconds in planning: 10.090
seconds in the monolithic thermal node, 0.299 seconds in storage proof, and
0.249 seconds holding the final admission lock.

Three runs of the selected graph, with the same medium benchmark request, 1.1 GB
target proof, and `/usr/bin/true` execution, measured:

| Receipt field | Candidate range |
| --- | ---: |
| planning | 0.623-0.813 s |
| complete two-wave pre-admission round | 0.513-0.703 s |
| wave-2 request-specific thermal projection | 0.059-0.076 s |
| final admission lock | 0.080-0.106 s |
| total inside resource route | 0.800-1.014 s |
| cold Python process included | 1.84-2.09 s |

All three executions returned `allow`, had no blocked or denied reasons, matched
the attested and final route timestamp, class, cpuset, thread limit, and gate
decisions, and completed the transient command with
return code zero. These are live-host observations, not universal performance
ceilings; the contract tests prove the graph and fail-closed behavior without
depending on timing.

## Negative Controls

The deterministic test route covers:

- thermal attribution and desktop/compositor callbacks must not run during the
  fast admission collection;
- supplied thermal and storage receipts must not be recomputed in the final
  plan;
- the independent nodes run outside the atomic startup lock;
- unavailable thermal-map evidence blocks the plan;
- a route for a different workload class, latency, or force identity blocks
  the plan;
- the final plan consumes the exact route embedded in the thermal receipt;
- aged receipts refresh outside the lock before a lease can be created.

Timing remains observational. Safety and completeness are established by the
claim/evidence contracts and negative controls, not by a latency threshold.
