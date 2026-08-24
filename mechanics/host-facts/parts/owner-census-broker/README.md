# Owner Census Broker

This host-facts part defines the source-owned, read-only census seam for a
runtime-supplied process/descriptor target snapshot. The implementation is
`src/abyss_machine/owner_census_broker.py`; the public wire anchors are the
three `schemas/pytest-owner-lifecycle-*.schema.json` files.

The part accepts scope, exact target identities, finite bounds, broker/key
generation, and key/replay providers at runtime. It emits unsigned evidence
or an authenticated `BrokerReceipt` bound to the request digest, target
snapshot, process incarnation, descriptor identities, timestamps, bounds,
completeness, nonce, replay counter, and boot/generation identities.

`complete=false` is the correct result when procfs visibility, credentials,
namespace identity, mount identity, descriptor reads, process currentness,
platform support, or declared bounds are insufficient. Consumers must not
turn an incomplete receipt into an operation grant.

This part has no installed unit, socket, timer, latest file, service, delete
or rename capability, cleanup authority, storage policy, free-space rule, or
capacity-based launch decision. The stack bridge exposes only this source
contract metadata; it does not invent a runtime artifact route.
