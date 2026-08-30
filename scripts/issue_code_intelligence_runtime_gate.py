#!/usr/bin/env python3
"""Issue a signed machine-evidence gate from admitted live provider facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine.code_intelligence_gate import issue_runtime_gate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-dir", required=True)
    parser.add_argument("--runtime-root", default="/srv/abyss-machine/runtimes/code-intelligence")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--stack-provider-source", required=True)
    parser.add_argument("--stack-provider-config", required=True)
    parser.add_argument("--private-key", required=True, help="pre-provisioned root-owned Ed25519 PEM key")
    parser.add_argument("--trust-anchor", default="/etc/abyss-machine/trust/code-intelligence-gate-ed25519.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = issue_runtime_gate(
            registry_dir=args.registry_dir,
            runtime_root=args.runtime_root,
            source_root=args.source_root,
            stack_provider_source=args.stack_provider_source,
            stack_provider_config=args.stack_provider_config,
            private_key_path=args.private_key,
            trust_anchor_path=args.trust_anchor,
            output_path=args.output,
        )
    except Exception as exc:
        result = {
            "schema": "abyss_machine_code_intelligence_runtime_gate_issue_v1",
            "status": "blocked",
            "error_type": type(exc).__name__,
            "reason": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") == "issued" else 1


if __name__ == "__main__":
    raise SystemExit(main())
