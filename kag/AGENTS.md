# AGENTS.md

## Applies to

This card applies to `abyss-machine/kag/` and every nested path until a nearer
card narrows the lane.

## Role

`kag/` is the repository-local KAG provider home for `abyss-machine`. It
exposes source-linked records and generated repository indexes over the public
host source, contracts, manifests, mechanics, and validation surfaces.

## Read before editing

Read the root `AGENTS.md`, this card, `kag/README.md`, `kag/manifest.json`,
`README.md`, `DESIGN.md`, `docs/publication/PUBLICATION_BOUNDARY.md`, and
`manifests/repo_scaffold.manifest.json` before changing provider records.

## Boundaries

Public host-source meaning belongs to `abyss-machine`. Shared KAG schema,
registry, composition, and provider validation belong to `aoa-kag`. Installed
host state, captures, secrets, histories, caches, models, databases, and host
runtime indexes remain under their private machine roots.

## Validation

Use the owner validator named in `manifest.json`, then validate this provider
through the `aoa-kag` local subtree validator.

## Closeout

Report provider records changed, source-return route changed, owner validation,
`aoa-kag` validation, and the affected host or runtime consumer route.
