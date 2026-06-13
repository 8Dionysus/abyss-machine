#!/usr/bin/env python3
"""Bounded Qwen3.6 prefill matrix runner for abyss-machine."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


WRAPPER = Path("/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server")
DEFAULT_OUTPUT = Path("/var/lib/abyss-machine/ai/llm/evals/qwen36/prefill-matrix/qwen36-prefill-matrix.jsonl")
PROMPTS = {
    8192: Path("/srv/abyss-machine/tmp/qwen36-tests/prompt-8k-ordinary.txt"),
    16384: Path("/srv/abyss-machine/tmp/qwen36-tests/prompt-16k-ordinary.txt"),
    32768: Path("/srv/abyss-machine/tmp/qwen36-tests/prompt-32k-ordinary.txt"),
}


def now() -> str:
    return datetime.now().astimezone().isoformat()


def run(cmd: list[str], *, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    elapsed = round(time.monotonic() - started, 3)
    parsed: Any
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "elapsed_seconds": elapsed,
        "json": parsed,
        "stdout_tail": proc.stdout[-4000:] if parsed is None else None,
        "stderr_tail": proc.stderr[-4000:],
    }


def snapshot() -> dict[str, Any]:
    out: dict[str, Any] = {"generated_at": now()}
    free = subprocess.run(["free", "-b"], text=True, capture_output=True, timeout=5)
    out["free_b"] = free.stdout.strip()
    pressure = subprocess.run(["cat", "/proc/pressure/memory"], text=True, capture_output=True, timeout=5)
    out["memory_pressure"] = pressure.stdout.strip()
    sensors = subprocess.run(["sensors"], text=True, capture_output=True, timeout=5)
    temps = []
    for line in sensors.stdout.splitlines():
        match = re.match(r"^[^:]+:\s*\+([0-9]+(?:\.[0-9]+)?)°C", line)
        if match:
            temps.append(float(match.group(1)))
    out["max_temp_c"] = max(temps) if temps else None
    return out


def parse_case(raw: str) -> dict[str, Any]:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) not in {4, 5}:
        raise argparse.ArgumentTypeError("case must be label,ctx,batch,ubatch[,threads_batch]")
    label, ctx, batch, ubatch = parts[:4]
    if not label:
        raise argparse.ArgumentTypeError("case label is required")
    return {
        "label": label,
        "ctx": int(ctx),
        "batch": int(batch),
        "ubatch": int(ubatch),
        "threads_batch": int(parts[4]) if len(parts) == 5 else 6,
    }


def summarize_completion(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    response = data.get("response") if isinstance(data.get("response"), dict) else {}
    timings = response.get("timings") if isinstance(response.get("timings"), dict) else {}
    result = {
        "ok": data.get("ok"),
        "elapsed_seconds": data.get("elapsed_seconds"),
        "evidence": data.get("evidence"),
        "unit": data.get("unit"),
        "status": data.get("status"),
        "restore_slot": data.get("restore_slot"),
        "save_slot": data.get("save_slot"),
        "response": {
            "id_slot": response.get("id_slot"),
            "stop_type": response.get("stop_type"),
            "content_chars": len(str(response.get("content") or "")),
            "timings": timings,
            "tokens_cached": response.get("tokens_cached"),
            "tokens_evaluated": response.get("tokens_evaluated"),
            "tokens_predicted": response.get("tokens_predicted"),
            "truncated": response.get("truncated"),
        },
    }
    return result


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def run_case(args: argparse.Namespace, case: dict[str, Any]) -> dict[str, Any]:
    ctx = int(case["ctx"])
    prompt = Path(args.prompt or PROMPTS[ctx])
    label = str(case["label"])
    record: dict[str, Any] = {
        "schema": "abyss_machine_qwen36_prefill_matrix_case_v1",
        "generated_at": now(),
        "profile": args.profile,
        "runtime_id": args.runtime_id,
        "case": case,
        "prompt_file": str(prompt),
        "samples": {"before_stop": snapshot()},
    }
    if record["samples"]["before_stop"].get("max_temp_c") and record["samples"]["before_stop"]["max_temp_c"] >= args.hard_temp_c:
        record["ok"] = False
        record["skipped"] = "hard_temp_guard_before_case"
        return record

    record["stop_before"] = run([str(WRAPPER), "stop", "--profile", args.profile, "--ctx", str(ctx), "--runtime-id", args.runtime_id, "--json"], timeout=60)
    record["samples"]["after_stop"] = snapshot()
    start_cmd = [
        str(WRAPPER),
        "start",
        "--profile",
        args.profile,
        "--ctx",
        str(ctx),
        "--runtime-id",
        args.runtime_id,
        "--batch",
        str(case["batch"]),
        "--ubatch",
        str(case["ubatch"]),
        "--threads-batch",
        str(case["threads_batch"]),
        "--health-timeout",
        str(args.health_timeout),
        "--json",
    ]
    record["start"] = run(start_cmd, timeout=args.health_timeout + 60)
    record["samples"]["after_start"] = snapshot()
    if record["start"]["returncode"] != 0:
        record["ok"] = False
        return record

    request_cmd = [
        str(WRAPPER),
        "request",
        "--profile",
        args.profile,
        "--ctx",
        str(ctx),
        "--runtime-id",
        args.runtime_id,
        "--prompt-file",
        str(prompt),
        "--slot-id",
        str(args.slot_id),
        "--n-predict",
        str(args.n_predict),
        "--write-evidence",
        "--evidence-label",
        f"matrix-{label}",
        "--request-timeout",
        str(args.request_timeout),
        "--json",
    ]
    record["request_raw"] = run(request_cmd, timeout=args.request_timeout + 60)
    record["request"] = summarize_completion(record["request_raw"].get("json"))
    record["request_raw"].pop("json", None)
    record["samples"]["after_request"] = snapshot()
    record["ok"] = record["request_raw"]["returncode"] == 0 and bool(record["request"] and record["request"].get("ok"))
    if not args.keep_last:
        record["stop_after"] = run([str(WRAPPER), "stop", "--profile", args.profile, "--ctx", str(ctx), "--runtime-id", args.runtime_id, "--json"], timeout=60)
        record["samples"]["after_final_stop"] = snapshot()
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Qwen3.6 prefill matrix.")
    parser.add_argument("--profile", default="ordinary", choices=["ordinary", "heretic"])
    parser.add_argument("--runtime-id", default="b9060", choices=["b9060", "05ff59c", "22cadc1"])
    parser.add_argument("--case", action="append", type=parse_case, required=True, help="label,ctx,batch,ubatch[,threads_batch]")
    parser.add_argument("--prompt", default=None, help="Override prompt file for all cases.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--slot-id", type=int, default=0)
    parser.add_argument("--n-predict", type=int, default=1)
    parser.add_argument("--health-timeout", type=float, default=180.0)
    parser.add_argument("--request-timeout", type=float, default=1200.0)
    parser.add_argument("--hard-temp-c", type=float, default=109.0)
    parser.add_argument("--keep-last", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    ok = True
    for case in args.case:
        record = run_case(args, case)
        write_jsonl(output, record)
        req = record.get("request") or {}
        timings = ((req.get("response") or {}).get("timings") or {}) if isinstance(req, dict) else {}
        print(json.dumps({
            "label": case["label"],
            "ok": record.get("ok"),
            "ctx": case["ctx"],
            "batch": case["batch"],
            "ubatch": case["ubatch"],
            "prompt_per_second": timings.get("prompt_per_second"),
            "prompt_ms": timings.get("prompt_ms"),
            "output": str(output),
        }, ensure_ascii=False), flush=True)
        ok = ok and bool(record.get("ok"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
