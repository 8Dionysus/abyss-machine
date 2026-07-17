# abyss-machine Local KAG Provider

`kag/` exposes portable records and repository indexes for the public
`abyss-machine` source checkout.

## Operating Card

| Field | Route |
| --- | --- |
| role | local KAG provider for host source, contracts, manifests, mechanics, and validation surfaces |
| records | `nodes/`, `edges/`, `indexes/`, `projections/`, `receipts/` |
| manifest | `manifest.json` |
| source route | `README.md`, `DESIGN.md`, `manifests/`, `mechanics/`, and `schemas/` |
| consumer route | `aoa-kag` registry/composition, `abyss-stack`, MCP resources |
| owner return | `README.md` |

## Record Classes

| Class | Current record |
| --- | --- |
| node | public host source and contract routes |
| edge | host source routes to its contract surface |
| index | content-addressed manifest plus bounded repository knowledge shards |
| projection | MCP-readable source-return packet |
| receipt | validation receipt for the current owner route |

Git holds public source records and the portable manifest/shard family. Exact
legacy JSON views are assembled on demand; installed host evidence, runtime
indexes, and other materializations remain outside the repository.
