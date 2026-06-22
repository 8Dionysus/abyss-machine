#!/usr/bin/env python3
"""Host-owned VoXtream2 benchmark for Intel XPU/CPU experiments."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path


ROOT = Path(os.environ.get("ABYSS_MACHINE_ROOT", "/srv/abyss-machine"))
RUNTIME_USER = os.environ.get("ABYSS_USER") or os.environ.get("USER") or Path.home().name or "abyss"
AI_HOME = Path(os.environ.get("ABYSS_AI_HOME", str(ROOT / "runtimes" / "home" / RUNTIME_USER / "abyss-ai")))
OVERLAY = AI_HOME / "voxtream-0.2.3-xpu-overlay"
ASSETS = AI_HOME / "voxtream-0.2.3-assets"
EVAL_ROOT = Path("/var/lib/abyss-machine/ai/tts/evals/experimental")
SYNTH_ROOT = Path("/var/lib/abyss-machine/ai/tts/synth")


def configure_env(device: str, compile_model: bool) -> None:
    os.environ.setdefault("HF_HOME", str(ROOT / "cache/ai/huggingface"))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(ROOT / "cache/ai/huggingface/hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(ROOT / "cache/ai/huggingface/transformers"))
    os.environ.setdefault("TORCH_HOME", str(ROOT / "cache/ai/torch"))
    os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / "cache/ai/xdg"))
    os.environ.setdefault("NLTK_DATA", str(ROOT / "cache/ai/nltk"))
    os.environ.setdefault("TMPDIR", str(ROOT / "tmp"))
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("NO_CUDA_GRAPH", "1")
    os.environ["VOXTREAM_DEVICE"] = device
    if device == "xpu":
        os.environ.setdefault("ONEAPI_DEVICE_SELECTOR", "level_zero:gpu")
        os.environ.setdefault("SYCL_CACHE_PERSISTENT", "1")
        os.environ.setdefault("SYCL_CACHE_DIR", str(ROOT / "cache/ai/sycl"))
        if compile_model:
            os.environ.setdefault("TORCHINDUCTOR_CACHE_DIR", str(ROOT / "cache/ai/torchinductor"))
            os.environ.setdefault("TRITON_CACHE_DIR", str(ROOT / "cache/ai/triton"))
            os.environ.setdefault("TRITON_CODEGEN_INTEL_XPU_BACKEND", "1")
    for path in (
        Path(os.environ["HF_HOME"]),
        Path(os.environ["TORCH_HOME"]),
        Path(os.environ["XDG_CACHE_HOME"]),
        Path(os.environ["NLTK_DATA"]),
        Path(os.environ["TMPDIR"]),
        ROOT / "cache/ai/sycl",
        ROOT / "cache/ai/torchinductor",
        ROOT / "cache/ai/triton",
        EVAL_ROOT,
        SYNTH_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(OVERLAY))


def synth_once(generator, config, prompt: Path, text: str, label: str, stream: bool):
    import numpy as np
    import soundfile as sf
    from voxtream.utils.generator import text_generator

    out = SYNTH_ROOT / f"voxtream2-{label}.wav"
    text_arg = text_generator(text) if stream else text
    frames = []
    gen_times = []
    first_yield_wall = None
    req0 = time.perf_counter()
    for frame, gen_time in generator.generate_stream(prompt_audio_path=prompt, text=text_arg):
        if first_yield_wall is None:
            first_yield_wall = time.perf_counter() - req0
        frames.append(frame)
        gen_times.append(gen_time)
    req1 = time.perf_counter()
    audio = np.concatenate(frames) if frames else np.zeros(0, dtype=np.float32)
    sf.write(out, audio, config.mimi_sr)
    audio_duration = len(audio) / config.mimi_sr if config.mimi_sr else 0.0
    return {
        "label": label,
        "stream": stream,
        "text": text,
        "output_wav": str(out),
        "request_wall_seconds": round(req1 - req0, 6),
        "first_yield_wall_seconds": round(first_yield_wall, 6) if first_yield_wall is not None else None,
        "internal_first_packet_seconds": round(gen_times[0], 6) if gen_times else None,
        "internal_avg_frame_seconds_after_first": round(float(np.mean(gen_times[1:])), 6)
        if len(gen_times) > 1
        else None,
        "internal_rtf_after_first": round((float(np.mean(gen_times[1:])) * 1000) / config.mimi_frame_ms, 6)
        if len(gen_times) > 1
        else None,
        "wall_rtf_request": round((req1 - req0) / audio_duration, 6) if audio_duration else None,
        "audio_duration_seconds": round(audio_duration, 6),
        "frames": len(frames),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=("xpu", "cpu"), default="xpu")
    parser.add_argument("--compile", action="store_true", help="Use torch.compile on supported VoXtream submodules.")
    parser.add_argument("--no-cfg", action="store_true", help="Disable VoXtream CFG for a lower-compute experimental run.")
    parser.add_argument("--stream", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-warmup", action="store_true")
    parser.add_argument("--text", default="This is a measured full streaming interactive speech synthesis test.")
    parser.add_argument("--warmup-text", default="Warm up.")
    parser.add_argument("--prompt", type=Path, default=ASSETS / "assets/audio/english_male.wav")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    configure_env(args.device, args.compile)

    import numpy as np  # noqa: F401 - imported before model load to fail fast if absent.
    from voxtream.config import SpeechGeneratorConfig
    from voxtream.generator import SpeechGenerator
    from voxtream.utils.generator import select_device, set_seed

    set_seed()
    with open(ASSETS / "configs/generator.json") as f:
        config = SpeechGeneratorConfig(**json.load(f))
    with open(ASSETS / "configs/speaking_rate.json") as f:
        spk_rate_config = json.load(f)
    config.cache_prompt = True
    config.apply_vad = False
    config.enhance_prompt = False
    if args.no_cfg:
        config.cfg_gamma = None
        config.cfg_ac_gamma = None

    t0 = time.perf_counter()
    generator = SpeechGenerator(config, spk_rate_config=spk_rate_config, compile=args.compile)
    t1 = time.perf_counter()

    label_base = args.label or (
        f"{args.device}{'-compile' if args.compile else ''}{'-nocfg' if args.no_cfg else ''}"
    )
    results = []
    if not args.skip_warmup:
        results.append(synth_once(generator, config, args.prompt, args.warmup_text, f"{label_base}-warmup", args.stream))
    results.append(synth_once(generator, config, args.prompt, args.text, f"{label_base}-measured", args.stream))

    result = {
        "schema": "abyss_machine_ai_tts_voxtream2_eval_v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "candidate": "voxtream==0.2.3 / VoXtream2",
        "runtime": {
            "python": sys.executable,
            "overlay": str(OVERLAY),
            "assets": str(ASSETS),
        },
        "device": select_device(),
        "torch_device": generator.ctx.device,
        "torch_dtype": str(generator.ctx.dtype),
        "compile": args.compile,
        "cfg_gamma": None if args.no_cfg else config.cfg_gamma,
        "cfg_ac_gamma": None if args.no_cfg else config.cfg_ac_gamma,
        "init_seconds": round(t1 - t0, 6),
        "results": results,
        "ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "decision_hint": {
            "promote_live_fast_interactive": False,
            "reason": "Measured Intel XPU streaming is still slower than real time unless future runtime/compiler changes improve it.",
        },
    }
    out_json = EVAL_ROOT / f"{time.strftime('%Y-%m-%d')}-voxtream2-{label_base}.json"
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
