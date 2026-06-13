# Test Topology

Public tests must run without a configured private host. Host-contract tests may
model local behavior through fixtures, but should keep live/manual/long checks
behind markers.

Tests should prove that generated planes are ignored, templates render from the
source roots, and opt-in organs stay disabled until selected.
