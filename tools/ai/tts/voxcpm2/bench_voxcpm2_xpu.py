#!/usr/bin/env python3
"""Host-layer VoxCPM2 benchmark/profiler.

This script is intentionally outside abyss-stack. It validates and profiles the
host-owned VoxCPM2 runtime and writes generated artifacts to abyss-machine paths.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf
import torch


MODEL_DIR = Path("/srv/abyss-machine/cache/ai/tts/voxcpm2/openbmb-VoxCPM2")
OUT_ROOT = Path("/var/lib/abyss-machine/ai/tts")

ENV_KEYS = [
    "ABYSS_PREFER_IPV4",
    "HF_HOME",
    "HUGGINGFACE_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "TORCH_HOME",
    "TORCHINDUCTOR_CACHE_DIR",
    "XDG_CACHE_HOME",
    "TMPDIR",
    "ONEAPI_DEVICE_SELECTOR",
    "ZE_AFFINITY_MASK",
    "SYCL_CACHE_PERSISTENT",
    "SYCL_UR_USE_LEVEL_ZERO_V2",
    "SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def sync_xpu() -> None:
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        torch.xpu.synchronize()


def maxrss_kib() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def xpu_memory() -> dict[str, int] | None:
    if not (hasattr(torch, "xpu") and torch.xpu.is_available()):
        return None
    out: dict[str, int] = {}
    for name in (
        "memory_allocated",
        "max_memory_allocated",
        "memory_reserved",
        "max_memory_reserved",
    ):
        fn = getattr(torch.xpu, name, None)
        if fn is not None:
            try:
                out[name] = int(fn())
            except Exception:
                pass
    return out


def torch_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "xpu_available": bool(hasattr(torch, "xpu") and torch.xpu.is_available()),
    }
    if info["xpu_available"]:
        info["xpu_count"] = int(torch.xpu.device_count())
        info["xpu_device_name"] = torch.xpu.get_device_name(0)
        try:
            props = torch.xpu.get_device_properties(0)
            info["xpu_properties"] = {
                "name": getattr(props, "name", None),
                "platform_name": getattr(props, "platform_name", None),
                "device_id": getattr(props, "device_id", None),
                "driver_version": getattr(props, "driver_version", None),
                "total_memory": getattr(props, "total_memory", None),
                "max_compute_units": getattr(props, "max_compute_units", None),
                "gpu_eu_count": getattr(props, "gpu_eu_count", None),
                "has_fp16": getattr(props, "has_fp16", None),
                "has_fp64": getattr(props, "has_fp64", None),
            }
        except Exception as exc:
            info["xpu_properties_error"] = repr(exc)
    return info


class StageTimer:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"count": 0, "total_sec": 0.0, "max_sec": 0.0}
        )

    def record(self, label: str, elapsed: float) -> None:
        row = self.rows[label]
        row["count"] = int(row["count"]) + 1
        row["total_sec"] = float(row["total_sec"]) + elapsed
        row["max_sec"] = max(float(row["max_sec"]), elapsed)

    def wrap(self, label: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            sync_xpu()
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            sync_xpu()
            self.record(label, time.perf_counter() - start)
            return result

        return wrapped

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for label, row in sorted(self.rows.items()):
            count = int(row["count"])
            total = float(row["total_sec"])
            out[label] = {
                "count": count,
                "total_sec": round(total, 6),
                "mean_sec": round(total / count, 6) if count else None,
                "max_sec": round(float(row["max_sec"]), 6),
            }
        return out


def patch_stage_timers(tts_model: Any) -> StageTimer:
    timer = StageTimer()

    def wrap_module(label: str, module: Any) -> None:
        if module is None or not hasattr(module, "forward"):
            return
        module.forward = timer.wrap(label, module.forward)

    def wrap_attr(label: str, obj: Any, attr: str) -> None:
        if obj is None or not hasattr(obj, attr):
            return
        setattr(obj, attr, timer.wrap(label, getattr(obj, attr)))

    wrap_module("feat_encoder.forward", getattr(tts_model, "feat_encoder", None))
    wrap_module("enc_to_lm_proj.forward", getattr(tts_model, "enc_to_lm_proj", None))
    wrap_module("base_lm.forward", getattr(tts_model, "base_lm", None))
    wrap_attr("base_lm.forward_step", getattr(tts_model, "base_lm", None), "forward_step")
    wrap_module("residual_lm.forward", getattr(tts_model, "residual_lm", None))
    wrap_attr("residual_lm.forward_step", getattr(tts_model, "residual_lm", None), "forward_step")
    wrap_module("fusion_concat_proj.forward", getattr(tts_model, "fusion_concat_proj", None))
    wrap_module("lm_to_dit_proj.forward", getattr(tts_model, "lm_to_dit_proj", None))
    wrap_module("res_to_dit_proj.forward", getattr(tts_model, "res_to_dit_proj", None))
    wrap_module("feat_decoder.forward", getattr(tts_model, "feat_decoder", None))
    wrap_module("audio_vae.decode.forward", getattr(getattr(tts_model, "audio_vae", None), "decoder", None))
    wrap_attr("audio_vae.decode", getattr(tts_model, "audio_vae", None), "decode")
    wrap_module("stop_proj.forward", getattr(tts_model, "stop_proj", None))
    wrap_module("stop_head.forward", getattr(tts_model, "stop_head", None))
    return timer


def compile_selected_xpu(tts_model: Any) -> list[dict[str, str]]:
    compiled: list[dict[str, str]] = []
    targets = [
        ("base_lm.forward_step", getattr(tts_model, "base_lm", None), "forward_step"),
        ("residual_lm.forward_step", getattr(tts_model, "residual_lm", None), "forward_step"),
        ("feat_encoder", tts_model, "feat_encoder"),
        ("feat_decoder.estimator", getattr(tts_model, "feat_decoder", None), "estimator"),
    ]
    for label, obj, attr in targets:
        if obj is None or not hasattr(obj, attr):
            compiled.append({"target": label, "status": "missing"})
            continue
        try:
            setattr(
                obj,
                attr,
                torch.compile(getattr(obj, attr), mode="reduce-overhead", fullgraph=True),
            )
            compiled.append({"target": label, "status": "compiled"})
        except Exception as exc:
            compiled.append({"target": label, "status": "failed", "error": repr(exc)})
    return compiled


def save_wav(out_dir: Path, label: str, kind: str, wav: np.ndarray, sample_rate: int) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{label}-{kind}.wav"
    sf.write(path, wav, sample_rate)
    return str(path)


def run_streaming(model: Any, args: argparse.Namespace, sample_rate: int, out_dir: Path) -> dict[str, Any]:
    chunks: list[np.ndarray] = []
    chunk_rows: list[dict[str, Any]] = []
    start = time.perf_counter()
    first_chunk_sec: float | None = None
    try:
        for idx, chunk in enumerate(
            model.generate_streaming(
                text=args.text,
                cfg_value=args.cfg_value,
                inference_timesteps=args.steps,
                min_len=args.min_len,
                max_len=args.max_len,
                normalize=False,
                denoise=False,
                retry_badcase=False,
            )
        ):
            sync_xpu()
            elapsed = time.perf_counter() - start
            if first_chunk_sec is None:
                first_chunk_sec = elapsed
            arr = np.asarray(chunk, dtype=np.float32).reshape(-1)
            chunks.append(arr)
            chunk_rows.append(
                {
                    "index": idx,
                    "wall_sec": round(elapsed, 6),
                    "samples": int(arr.shape[0]),
                    "audio_sec": round(float(arr.shape[0]) / sample_rate, 6),
                }
            )
            if args.max_chunks and idx + 1 >= args.max_chunks:
                break
    except Exception as exc:
        return {
            "kind": "streaming",
            "ok": False,
            "error": repr(exc),
            "first_chunk_sec": first_chunk_sec,
            "wall_sec": round(time.perf_counter() - start, 6),
        }

    wall = time.perf_counter() - start
    wav = np.concatenate(chunks) if chunks else np.zeros((0,), dtype=np.float32)
    audio_sec = float(wav.shape[0]) / sample_rate if sample_rate else 0.0
    return {
        "kind": "streaming",
        "ok": True,
        "first_chunk_sec": round(first_chunk_sec, 6) if first_chunk_sec is not None else None,
        "wall_sec": round(wall, 6),
        "audio_sec": round(audio_sec, 6),
        "rtf": round(wall / audio_sec, 6) if audio_sec else None,
        "chunks": chunk_rows,
        "wav": save_wav(out_dir, args.label, "streaming", wav, sample_rate),
    }


def run_full(model: Any, args: argparse.Namespace, sample_rate: int, out_dir: Path) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        wav = model.generate(
            text=args.text,
            cfg_value=args.cfg_value,
            inference_timesteps=args.steps,
            min_len=args.min_len,
            max_len=args.max_len,
            normalize=False,
            denoise=False,
            retry_badcase=False,
        )
        sync_xpu()
    except Exception as exc:
        return {"kind": "full", "ok": False, "error": repr(exc), "wall_sec": round(time.perf_counter() - start, 6)}
    wall = time.perf_counter() - start
    arr = np.asarray(wav, dtype=np.float32).reshape(-1)
    audio_sec = float(arr.shape[0]) / sample_rate if sample_rate else 0.0
    return {
        "kind": "full",
        "ok": True,
        "wall_sec": round(wall, 6),
        "audio_sec": round(audio_sec, 6),
        "rtf": round(wall / audio_sec, 6) if audio_sec else None,
        "samples": int(arr.shape[0]),
        "wav": save_wav(out_dir, args.label, "full", arr, sample_rate),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(MODEL_DIR))
    parser.add_argument("--label", default="voxcpm2-xpu")
    parser.add_argument("--text", default="Привет. Это короткий тест синтеза речи.")
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--cfg-value", type=float, default=2.0)
    parser.add_argument("--min-len", type=int, default=2)
    parser.add_argument("--max-len", type=int, default=4096)
    parser.add_argument("--mode", choices=["streaming", "full", "both"], default="streaming")
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--profile-stages", action="store_true")
    parser.add_argument("--compile-xpu", action="store_true")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--out-dir", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        print(f"model dir not found: {model_dir}", file=sys.stderr)
        return 2

    from voxcpm import VoxCPM

    out_dir = Path(args.out_dir) if args.out_dir else OUT_ROOT / "synth" / time.strftime("%Y/%m/%Y-%m-%d")

    started = time.perf_counter()
    model = VoxCPM.from_pretrained(
        str(model_dir),
        load_denoiser=False,
        optimize=False,
        local_files_only=True,
    )
    sync_xpu()
    load_sec = time.perf_counter() - started
    tts_model = model.tts_model
    sample_rate = int(tts_model.sample_rate)

    stage_timer: StageTimer | None = patch_stage_timers(tts_model) if args.profile_stages else None
    compile_status = compile_selected_xpu(tts_model) if args.compile_xpu else []

    run_rows = []
    if args.mode in ("streaming", "both"):
        run_rows.append(run_streaming(model, args, sample_rate, out_dir))
    if args.mode in ("full", "both"):
        run_rows.append(run_full(model, args, sample_rate, out_dir))

    result = {
        "schema": "abyss_machine_ai_tts_voxcpm2_bench_v1",
        "generated_at": now_iso(),
        "label": args.label,
        "model_dir": str(model_dir),
        "text": args.text,
        "settings": {
            "steps": args.steps,
            "cfg_value": args.cfg_value,
            "min_len": args.min_len,
            "max_len": args.max_len,
            "mode": args.mode,
            "profile_stages": args.profile_stages,
            "compile_xpu": args.compile_xpu,
        },
        "environment": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
        "torch": torch_info(),
        "model": {
            "device": str(getattr(tts_model, "device", "")),
            "dtype": str(getattr(getattr(tts_model, "config", None), "dtype", "")),
            "sample_rate": sample_rate,
            "patch_size": int(getattr(tts_model, "patch_size", 0)),
            "chunk_size": int(getattr(tts_model, "chunk_size", 0)),
            "decode_chunk_size": int(getattr(tts_model, "_decode_chunk_size", 0)),
        },
        "load_sec": round(load_sec, 6),
        "compile_status": compile_status,
        "runs": run_rows,
        "stage_timings": stage_timer.to_json() if stage_timer else {},
        "maxrss_kib": maxrss_kib(),
        "xpu_memory": xpu_memory(),
        "ok": all(row.get("ok") for row in run_rows),
    }

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
