# Testing Tools

This lane stores helper tools for the host-machine test suite.

## Route

- Tool root: `/srv/abyss-machine/tools/testing`
- Test root: `/srv/abyss-machine/tests/AGENTS.md`

## Rules

- Helpers support tests; they are not standalone source truth.
- Keep helper behavior deterministic and explicit.
- Do not add network, password, or destructive behavior to test helpers unless routed through manual tests.
