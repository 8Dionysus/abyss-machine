# Abyss Machine Tools

This directory holds host-owned helper tools for `abyss-machine`.

Tools here support the machine layer only. They must not become project-repo
automation, hidden deployment logic, or a place for work-project artifacts.

## Operating Contract

- Input: operator intent, host-layer source/config, and helper source files.
- Output: thin wrappers, probes, packages, or validation helpers; runtime
  evidence belongs under `/var/lib/abyss-machine`, not in this tree.
- Owner: `/etc/abyss-machine` source contracts and the nearest local
  `AGENTS.md` card.
- Tools: stable `abyss-machine ... --json` commands first; local scripts only
  when they remain auditable wrappers or probes.
- Next route: choose the nearest local card under `ai/`, `nervous/`,
  `typing/`, or `topology/` before touching helper files.
- Verify: run the subsystem validator plus `abyss-machine docs mesh-validate
  --json`.

## Rules

- Prefer stable `abyss-machine ... --json` commands as the primary interface.
- Keep helper scripts thin, auditable, and reversible.
- Keep caches, generated reports, and runtime outputs outside this tools tree.
- Do not write to `/srv/AbyssOS`, `/work`, `/srv/work`, or project repositories
  from tools in this directory.
- Add a local `AGENTS.md` for any subdirectory that carries its own contracts or
  verification scripts.

## Local Cards

- `/srv/abyss-machine/tools/ai/AGENTS.md` before AI helper, reranker, or TTS
  probe work.
- `/srv/abyss-machine/tools/nervous/AGENTS.md` before capture or nervous-system
  helper work.
- `/srv/abyss-machine/tools/typing/AGENTS.md` before typed-text native-host or
  browser extension helper work.
- `/srv/abyss-machine/tools/topology/AGENTS.md` before topology helper work.
