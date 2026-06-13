#!/usr/bin/env python3
"""Benchmark the resident llama.cpp HTTP endpoint with the same prompt gates."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def get_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    with request.urlopen(base_url.rstrip("/") + path, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def count_tokens(base_url: str, text: str, timeout: float) -> int:
    response = post_json(base_url, "/tokenize", {"content": text}, timeout)
    return len(response.get("tokens") or [])


def make_prompt(base_url: str, target_tokens: int, timeout: float) -> tuple[str, int]:
    base = (
        "You are benchmarking a local inference backend. Use only the evidence blocks. "
        "Answer the final task in one short paragraph.\n\n"
    )
    unit = (
        "Evidence block: model=Gemma4 E2B; backend candidates include llama.cpp Vulkan+CPU "
        "and OpenVINO GenAI on CPU, GPU, and NPU; decision criteria are TTFT, tokens per "
        "second, cache warmup, lazy-load cost, resident memory, stability, thermal behavior, "
        "and practical context length on this exact machine.\n"
    )
    question = "\nFinal task: state whether this backend looks practical and name one risk.\n"

    base_tokens = count_tokens(base_url, base + question, timeout)
    unit_tokens = max(1, count_tokens(base_url, unit, timeout))
    repeats = max(1, int((target_tokens - base_tokens) / unit_tokens))

    def build(n: int) -> tuple[str, int]:
        prompt = base + (unit * n) + question
        return prompt, count_tokens(base_url, prompt, timeout)

    prompt, actual = build(repeats)
    for _ in range(10):
        if actual < target_tokens * 0.97:
            repeats += max(1, repeats // 8)
        elif actual > target_tokens * 1.05 and repeats > 1:
            repeats = max(1, int(repeats * target_tokens / actual))
        else:
            break
        prompt, actual = build(repeats)
    return prompt, actual


def stream_completion(base_url: str, prompt: str, max_new_tokens: int, timeout: float) -> dict[str, Any]:
    payload = {
        "prompt": prompt,
        "n_predict": int(max_new_tokens),
        "temperature": 0,
        "stream": True,
        "cache_prompt": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        base_url.rstrip("/") + "/completion",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_chunk_at = None
    chunks: list[str] = []
    final_payload = None
    with request.urlopen(req, timeout=timeout) as response:
        while True:
            line = response.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text.startswith("data:"):
                continue
            raw = text[5:].strip()
            if raw == "[DONE]":
                break
            item = json.loads(raw)
            final_payload = item
            content = item.get("content") or ""
            if content and first_chunk_at is None:
                first_chunk_at = time.perf_counter()
            chunks.append(content)
            if item.get("stop"):
                break
    ended = time.perf_counter()
    return {
        "generate_seconds": ended - started,
        "stream_ttft_seconds": None if first_chunk_at is None else first_chunk_at - started,
        "output_text": "".join(chunks),
        "chunks": len(chunks),
        "final_payload": final_payload,
    }


def nonstream_completion(base_url: str, prompt: str, max_new_tokens: int, timeout: float) -> dict[str, Any]:
    payload = {
        "prompt": prompt,
        "n_predict": int(max_new_tokens),
        "temperature": 0,
        "stream": False,
        "cache_prompt": False,
    }
    started = time.perf_counter()
    item = post_json(base_url, "/completion", payload, timeout)
    ended = time.perf_counter()
    return {
        "generate_seconds": ended - started,
        "output_text": item.get("content") or "",
        "final_payload": item,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:11435")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--prompt-tokens", type=int, required=True)
    parser.add_argument("--max-new-tokens", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--no-stream", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema": "abyss_machine_gemma4_e2b_llama_cpp_http_bench_v1",
        "started_at": now_iso(),
        "ok": False,
        "base_url": args.base_url,
        "prompt_target_tokens": args.prompt_tokens,
        "max_new_tokens": args.max_new_tokens,
        "python": sys.version,
        "platform": platform.platform(),
    }
    try:
        result["health"] = get_json(args.base_url, "/health", min(args.timeout, 10))
        result["models"] = get_json(args.base_url, "/v1/models", min(args.timeout, 10))
        prompt, actual_tokens = make_prompt(args.base_url, args.prompt_tokens, min(args.timeout, 30))
        result["prompt_actual_tokens"] = actual_tokens
        result["prompt_chars"] = len(prompt)
        if args.no_stream:
            run = nonstream_completion(args.base_url, prompt, args.max_new_tokens, args.timeout)
        else:
            run = stream_completion(args.base_url, prompt, args.max_new_tokens, args.timeout)
        run["output_preview"] = run.pop("output_text")[:700]
        result["run"] = run
        result["ok"] = True
        return_code = 0
    except (TimeoutError, error.URLError, error.HTTPError) as exc:
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
        return_code = 2
    except Exception as exc:
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
        return_code = 2
    finally:
        result["total_seconds"] = time.perf_counter() - started
        result["ru_maxrss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result["finished_at"] = now_iso()
        args.output_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
