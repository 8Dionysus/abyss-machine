# Boundaries

## Public Repository Boundary

This repository may contain:

- source code and helper tools
- public-safe config templates
- systemd unit skeletons
- schemas, route docs, tests, and validators
- examples that contain no secrets or private captures

It must not contain:

- real secrets, tokens, password files, or vault contents
- generated `/var/lib/abyss-machine` evidence
- mutable `/srv/abyss-machine` caches, runtimes, storage, backups, or temp data
- raw typed text, browser captures, screenshots, transcripts, or private indexes
- rendered private host configs from a real machine

## Owner Boundary

`abyss-machine` owns host-machine evidence and routing. `abyss-stack` owns the
runtime substrate and consumes machine facts read-only unless a route explicitly
authorizes a host-layer change.

Sibling AoA repositories own their doctrine, source records, proofs, memory
surfaces, and playbooks. This repo may expose host context to them; it does not
replace their source truth.

## Installation Boundary

Bootstrap may render `/etc/abyss-machine`, install CLI entrypoints, and create
empty local roots when explicitly applied. Dry-run output must remain safe and
reviewable.
