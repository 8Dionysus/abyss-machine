#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--json" ]]; then
  exec abyss-machine topology validate --json
fi

tmp="$(mktemp)"
cleanup() {
  rm -f "$tmp"
}
trap cleanup EXIT

if ! abyss-machine topology validate --json >"$tmp"; then
  cat "$tmp"
  exit 1
fi

python3 - "$tmp" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
summary = data.get("summary", {})
print(
    "topology validate: "
    f"{summary.get('status')} "
    f"({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)"
)
for check in data.get("checks", []):
    if check.get("level") != "ok":
        print(f"{check.get('level'):4} {check.get('key'):40} {check.get('message')}")
sys.exit(0 if summary.get("fails") == 0 else 1)
PY
