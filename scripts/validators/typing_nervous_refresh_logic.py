#!/usr/bin/env python3
from __future__ import annotations

import sys

from _common import REPO_ROOT, fail, ok, require


SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine.typing_nervous_refresh import (  # noqa: E402
    TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
    typing_nervous_deferred_recent_index_safe,
    typing_nervous_index_resource_gated,
    typing_nervous_recent_index_debounce_safe,
)


def main() -> int:
    failures: list[str] = []

    require(
        "indexing_unattended_swap_used_pressure" in TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
        "swap-used pressure must remain an accepted soft resource gate",
        failures,
    )
    require(
        "indexing_unattended_swap_free_below_floor" in TYPING_NERVOUS_INDEX_RESOURCE_GATE_REASONS,
        "swap-free floor must remain an accepted soft resource gate",
        failures,
    )
    require(
        typing_nervous_index_resource_gated(
            {
                "ok": False,
                "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
                "denied_reasons": [],
            }
        ),
        "known soft resource block should be accepted",
        failures,
    )
    require(
        not typing_nervous_index_resource_gated(
            {
                "ok": False,
                "blocked_reasons": ["indexing_unattended_swap_used_pressure"],
                "denied_reasons": ["storage_denied"],
            }
        ),
        "denied resource launch must not be accepted as soft-gated",
        failures,
    )

    bounded = {
        "index_deferred_recent_attempt": True,
        "index_previous_attempt_age_sec": 225,
        "index_min_interval_sec": 900,
        "index_records_lag": 6,
        "index_records_lag_tolerance": 4,
        "global_index_records_lag": 6,
        "global_index_records_lag_tolerance": 4,
    }
    require(
        typing_nervous_deferred_recent_index_safe(bounded),
        "bounded recent-index debounce should be accepted",
        failures,
    )
    unbounded = dict(bounded, index_records_lag=65, global_index_records_lag=65)
    require(
        not typing_nervous_deferred_recent_index_safe(unbounded),
        "unbounded recent-index lag should not be accepted",
        failures,
    )

    common = {
        "index_needed": True,
        "force_index": False,
        "previous_index_launch_attempted": True,
        "previous_index_attempt_age_sec": 725,
        "index_min_interval_sec": 900,
        "index_records_lag_tolerance": 4,
        "index_stale": True,
    }
    require(
        typing_nervous_recent_index_debounce_safe(**common, index_records_lag=6),
        "bounded recent-index debounce should defer safely",
        failures,
    )
    require(
        not typing_nervous_recent_index_debounce_safe(**common, index_records_lag=17),
        "large lag should bypass recent-index debounce",
        failures,
    )

    require(
        cli.typing_nervous_index_resource_gated is typing_nervous_index_resource_gated,
        "CLI must re-export module resource-gate helper",
        failures,
    )
    require(
        cli.typing_nervous_deferred_recent_index_safe is typing_nervous_deferred_recent_index_safe,
        "CLI must re-export module deferred-index helper",
        failures,
    )
    require(
        cli.typing_nervous_recent_index_debounce_safe is typing_nervous_recent_index_debounce_safe,
        "CLI must re-export module recent-index debounce helper",
        failures,
    )

    cli_source = (REPO_ROOT / "src" / "abyss_machine" / "cli.py").read_text(encoding="utf-8")
    for name in (
        "typing_nervous_index_resource_gated",
        "typing_nervous_deferred_recent_index_safe",
        "typing_nervous_recent_index_debounce_safe",
    ):
        require(f"def {name}" not in cli_source, f"CLI must not redefine {name}", failures)

    if failures:
        return fail("typing/nervous refresh logic validation failed", failures)
    return ok("typing/nervous refresh logic validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
