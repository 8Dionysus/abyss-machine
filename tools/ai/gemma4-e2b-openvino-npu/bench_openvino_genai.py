#!/usr/bin/env python3
"""Benchmark OpenVINO GenAI Gemma 4 runs with reproducible JSON output."""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


for name, value in {
    "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "6",
    "MKL_NUM_THREADS": "6",
    "OPENBLAS_NUM_THREADS": "6",
    "NUMEXPR_NUM_THREADS": "6",
}.items():
    os.environ.setdefault(name, value)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mean_std_pair(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "mean") and hasattr(value, "std"):
        return {"mean": float(value.mean), "std": float(value.std)}
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return {"mean": float(value[0]), "std": float(value[1])}
    return repr(value)


def perf_metrics_to_dict(metrics: Any) -> dict[str, Any]:
    if metrics is None:
        return {}
    out: dict[str, Any] = {}
    getters = {
        "load_time_ms": "get_load_time",
        "num_generated_tokens": "get_num_generated_tokens",
        "num_input_tokens": "get_num_input_tokens",
        "ttft_ms": "get_ttft",
        "tpot_ms_per_token": "get_tpot",
        "ipot_ms_per_token": "get_ipot",
        "throughput_tokens_per_sec": "get_throughput",
        "inference_duration_ms": "get_inference_duration",
        "generate_duration_ms": "get_generate_duration",
        "tokenization_duration_ms": "get_tokenization_duration",
        "detokenization_duration_ms": "get_detokenization_duration",
        "chat_template_duration_ms": "get_chat_template_duration",
        "sampling_duration_ms": "get_sampling_duration",
    }
    for key, getter in getters.items():
        try:
            value = getattr(metrics, getter)()
            if key in ("load_time_ms", "num_generated_tokens", "num_input_tokens"):
                out[key] = value
            else:
                out[key] = mean_std_pair(value)
        except Exception as exc:
            out[key] = {"error": repr(exc)}
    raw = getattr(metrics, "raw_metrics", None)
    if raw is not None:
        raw_out: dict[str, Any] = {}
        for name in (
            "m_times_to_first_token",
            "m_new_token_times",
            "generate_durations",
            "m_durations",
            "token_infer_durations",
            "inference_durations",
            "tokenization_durations",
            "detokenization_durations",
            "chat_template_durations",
        ):
            try:
                value = getattr(raw, name)
                raw_out[name] = list(value)
            except Exception:
                pass
        out["raw"] = raw_out
    return out


def tensor_tokens(tokenized: Any) -> int:
    shape = getattr(getattr(tokenized, "input_ids"), "shape")
    return int(list(shape)[-1])


def count_tokens(tokenizer: Any, text: str) -> int:
    return tensor_tokens(tokenizer.encode(text))


def make_prompt(tokenizer: Any, target_tokens: int) -> tuple[str, int]:
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

    base_tokens = count_tokens(tokenizer, base + question)
    unit_tokens = max(1, count_tokens(tokenizer, unit))
    repeats = max(1, int((target_tokens - base_tokens) / unit_tokens))

    def build(n: int) -> tuple[str, int]:
        prompt = base + (unit * n) + question
        return prompt, count_tokens(tokenizer, prompt)

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


def generation_config(ovg: Any, max_new_tokens: int, min_new_tokens: int, ignore_eos: bool) -> Any:
    cfg = ovg.GenerationConfig()
    cfg.max_new_tokens = int(max_new_tokens)
    cfg.min_new_tokens = int(min_new_tokens)
    cfg.do_sample = False
    cfg.num_beams = 1
    cfg.repetition_penalty = 1.03
    cfg.apply_chat_template = True
    cfg.ignore_eos = bool(ignore_eos)
    return cfg


def pipeline_properties(args: argparse.Namespace) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if args.cache_dir:
        props["CACHE_DIR"] = str(args.cache_dir)
    if args.device.upper().startswith("NPU"):
        props["MAX_PROMPT_LEN"] = int(args.max_prompt_len or args.prompt_tokens)
        props["MIN_RESPONSE_LEN"] = int(args.min_response_len or max(2, args.max_new_tokens))
        if args.best_perf:
            props["GENERATE_HINT"] = "BEST_PERF"
            os.environ.setdefault("NPUW_LLM_GENERATE_HINT", "BEST_PERF")
    if args.device.upper().startswith("CPU"):
        props["PERFORMANCE_HINT"] = "LATENCY"
        props["INFERENCE_NUM_THREADS"] = int(args.threads)
    if args.device.upper().startswith("GPU"):
        props["PERFORMANCE_HINT"] = "LATENCY"
        props["NUM_STREAMS"] = "1"
    return props


def load_pipeline(ovg: Any, args: argparse.Namespace, props: dict[str, Any]) -> tuple[Any, dict[str, Any], str]:
    cls = ovg.VLMPipeline if args.pipeline == "vlm" else ovg.LLMPipeline
    attempts = [
        ("full", props),
        ("cache_only", {"CACHE_DIR": props["CACHE_DIR"]} if "CACHE_DIR" in props else {}),
        ("none", {}),
    ]
    errors: list[dict[str, str]] = []
    for mode, candidate in attempts:
        try:
            return cls(str(args.model_dir), args.device, **candidate), candidate, mode
        except Exception as exc:
            errors.append({"mode": mode, "error": repr(exc)})
    raise RuntimeError(f"pipeline load failed: {errors}")


def run_generate(pipe: Any, prompt: str, cfg: Any, streamer: Any | None) -> Any:
    attempts = []
    if streamer is not None:
        attempts.append((prompt, cfg, streamer))
    attempts.append((prompt, cfg))
    last_error: Exception | None = None
    for call_args in attempts:
        try:
            return pipe.generate(*call_args)
        except TypeError as exc:
            last_error = exc
            try:
                return pipe.generate(prompt, generation_config=cfg)
            except TypeError as inner:
                last_error = inner
    if last_error:
        raise last_error
    raise RuntimeError("generate did not run")


def output_text(output: Any) -> str:
    if isinstance(output, str):
        return output
    texts = getattr(output, "texts", None)
    if texts:
        try:
            return "\n".join(str(item) for item in texts)
        except Exception:
            pass
    return str(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--device", default="NPU")
    parser.add_argument("--pipeline", choices=("vlm", "llm"), default="vlm")
    parser.add_argument("--mode", choices=("cold", "warm-cache", "resident"), default="warm-cache")
    parser.add_argument("--prompt-tokens", type=int, required=True)
    parser.add_argument("--max-new-tokens", type=int, required=True)
    parser.add_argument("--min-new-tokens", type=int, default=2)
    parser.add_argument("--max-prompt-len", type=int)
    parser.add_argument("--min-response-len", type=int)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--ignore-eos", action="store_true")
    parser.add_argument("--best-perf", action="store_true")
    parser.add_argument("--clear-cache-dir", action="store_true")
    parser.add_argument("--stream", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema": "abyss_machine_gemma4_e2b_openvino_genai_bench_v1",
        "started_at": now_iso(),
        "ok": False,
        "model_dir": str(args.model_dir),
        "cache_dir": str(args.cache_dir),
        "device": args.device,
        "pipeline": args.pipeline,
        "mode": args.mode,
        "prompt_target_tokens": args.prompt_tokens,
        "max_new_tokens": args.max_new_tokens,
        "min_new_tokens": args.min_new_tokens,
        "repeats": args.repeats,
        "python": sys.version,
        "platform": platform.platform(),
    }
    try:
        import openvino as ov
        import openvino_genai as ovg

        result["openvino_version"] = getattr(ov, "__version__", None)
        result["openvino_genai_version"] = getattr(ovg, "__version__", None)
        if args.clear_cache_dir and args.cache_dir.exists():
            shutil.rmtree(args.cache_dir)
        args.cache_dir.mkdir(parents=True, exist_ok=True)

        tok_start = time.perf_counter()
        tokenizer = ovg.Tokenizer(str(args.model_dir))
        prompt, actual_tokens = make_prompt(tokenizer, args.prompt_tokens)
        result["tokenizer_seconds"] = time.perf_counter() - tok_start
        result["prompt_actual_tokens"] = actual_tokens
        result["prompt_chars"] = len(prompt)

        props = pipeline_properties(args)
        load_start = time.perf_counter()
        pipe, used_props, property_mode = load_pipeline(ovg, args, props)
        result["load_seconds"] = time.perf_counter() - load_start
        result["pipeline_properties"] = used_props
        result["pipeline_property_mode"] = property_mode

        cfg = generation_config(ovg, args.max_new_tokens, args.min_new_tokens, args.ignore_eos)
        runs = []
        for index in range(args.repeats):
            chunks: list[str] = []
            first_chunk_at: float | None = None
            streamer = None
            if args.stream:
                def callback(text: str) -> Any:
                    nonlocal first_chunk_at
                    if first_chunk_at is None:
                        first_chunk_at = time.perf_counter()
                    chunks.append(text)
                    return ovg.StreamingStatus.RUNNING

                streamer = ovg.TextStreamer(tokenizer, callback)

            gen_start = time.perf_counter()
            output = run_generate(pipe, prompt, cfg, streamer)
            gen_end = time.perf_counter()
            text = output_text(output)
            metrics = perf_metrics_to_dict(getattr(output, "perf_metrics", None))
            runs.append(
                {
                    "index": index,
                    "generate_seconds": gen_end - gen_start,
                    "stream_ttft_seconds": None if first_chunk_at is None else first_chunk_at - gen_start,
                    "stream_chunks": len(chunks),
                    "output_chars": len(text),
                    "output_preview": text[:700],
                    "perf_metrics": metrics,
                }
            )
        result["runs"] = runs
        result["cache_dir_size_bytes"] = sum(p.stat().st_size for p in args.cache_dir.rglob("*") if p.is_file())
        result["ok"] = True
        return_code = 0
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
