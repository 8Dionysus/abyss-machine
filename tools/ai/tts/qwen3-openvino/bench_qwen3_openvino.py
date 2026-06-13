#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import importlib.util
import json
import os
import re
import resource
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import openvino as ov
import soundfile as sf
from transformers import AutoTokenizer


DEFAULT_SOURCE_ROOT = Path("/srv/abyss-machine/cache/ai/tts/qwen3-openvino-src")
DEFAULT_MODEL_DIR = Path(
    "/srv/abyss-machine/cache/ai/tts/qwen3-openvino/customvoice-1p7b-int8-cpfp16-ov"
)
DEFAULT_CACHE_DIR = Path("/srv/abyss-machine/cache/ai/openvino/qwen3-tts")
DEFAULT_SYNTH_DIR = Path("/var/lib/abyss-machine/ai/tts/synth")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")


def _load_ov_infer(source_root: Path) -> Any:
    src = source_root / "src"
    module_path = src / "openvino" / "ov_infer.py"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    spec = importlib.util.spec_from_file_location("abyss_qwen3_ov_infer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load ov_infer from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class StageDevices:
    text: str
    codec: str
    cp_codec: str
    decoder: str
    talker: str
    cp: str

    @classmethod
    def from_spec(cls, spec: str, default: str) -> "StageDevices":
        values = {
            "text": default,
            "codec": default,
            "cp_codec": default,
            "decoder": default,
            "talker": default,
            "cp": default,
        }
        normalized = spec.strip()
        if normalized:
            for part in normalized.split(","):
                key, sep, value = part.partition("=")
                if not sep:
                    raise ValueError(f"Invalid stage placement entry: {part!r}")
                key = key.strip()
                value = value.strip()
                if key not in values:
                    raise ValueError(f"Unknown stage name: {key!r}")
                if not value:
                    raise ValueError(f"Empty device for stage: {key!r}")
                values[key] = value
        return cls(**values)

    def as_dict(self) -> dict[str, str]:
        return {
            "text": self.text,
            "codec": self.codec,
            "cp_codec": self.cp_codec,
            "decoder": self.decoder,
            "talker": self.talker,
            "cp": self.cp,
        }


def _compile_config(device: str, *, cp_f32: bool = False) -> dict[str, Any]:
    config: dict[str, Any] = {"PERFORMANCE_HINT": "LATENCY"}
    if cp_f32:
        config["INFERENCE_PRECISION_HINT"] = "f32"
    if device.upper().startswith("CPU"):
        threads = os.getenv("ABYSS_QWEN3_OV_CPU_THREADS", "").strip()
        if threads:
            config["INFERENCE_NUM_THREADS"] = int(threads)
    return config


class StagePlacedOVQwen3TTS:
    def __init__(self, ov_infer: Any, *, cache_dir: Path | None, stage_devices: StageDevices, cp_f32: bool):
        self._impl = ov_infer.OVQwen3TTS()
        self._ov_infer = ov_infer
        self._cache_dir = cache_dir
        self._stage_devices = stage_devices
        self._cp_f32 = cp_f32

    def load_model(self, ov_dir: Path, model_type: Any) -> None:
        impl = self._impl
        if impl.loaded:
            impl._release_models()

        p = Path(ov_dir)
        core = ov.Core()
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            core.set_property({"CACHE_DIR": str(self._cache_dir)})

        impl.tokenizer = AutoTokenizer.from_pretrained(str(p), trust_remote_code=True)
        impl._mrope_cos, impl._mrope_sin = self._ov_infer.H.precompute_mrope(
            self._ov_infer.TALKER_MAX_POS,
            self._ov_infer.HEAD_DIM,
            self._ov_infer.TALKER_ROPE_THETA,
        )
        impl._cp_cos, impl._cp_sin = self._ov_infer.H.precompute_standard_rope(
            self._ov_infer.CP_MAX_POS,
            self._ov_infer.CP_HEAD_DIM,
        )

        d = self._stage_devices
        impl._text_model_c = core.compile_model(
            str(p / "text_model.xml"), d.text, _compile_config(d.text)
        )
        impl._codec_emb_c = core.compile_model(
            str(p / "codec_embedding.xml"), d.codec, _compile_config(d.codec)
        )
        impl._cp_codec_emb_c = core.compile_model(
            str(p / "cp_codec_embedding.xml"), d.cp_codec, _compile_config(d.cp_codec)
        )
        impl._decoder_c = core.compile_model(
            str(p / "speech_tokenizer" / "speech_decoder.xml"),
            d.decoder,
            _compile_config(d.decoder),
        )
        impl._decoder_input_name = impl._decoder_c.input(0).get_any_name()

        talker_c = core.compile_model(str(p / "talker.xml"), d.talker, _compile_config(d.talker))
        impl._talker_req = talker_c.create_infer_request()
        cp_c = core.compile_model(
            str(p / "code_predictor.xml"),
            d.cp,
            _compile_config(d.cp, cp_f32=self._cp_f32),
        )
        impl._cp_req = cp_c.create_infer_request()

        impl._speaker_enc_c = None
        impl._speech_enc_c = None
        impl._model_type = model_type
        impl._loaded = True
        print(f"[engine] loaded from {p} stage_devices={d.as_dict()} model_type={model_type.value}")

    def generate(self, request: Any) -> tuple[np.ndarray, int]:
        return self._impl.generate(request)

    async def unload_model(self) -> None:
        await self._impl.unload_model()


def _parse_perf_lines(output: str) -> dict[str, float | str]:
    metrics: dict[str, float | str] = {}
    for line in output.splitlines():
        if not line.startswith("[perf]"):
            continue
        match = re.match(r"^\[perf\]\s+([^:]+):\s+(.+)$", line)
        if not match:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", match.group(1).strip().lower()).strip("_")
        value = match.group(2).strip()
        seconds = re.search(r"([0-9]+(?:\.[0-9]+)?)s", value)
        if seconds:
            metrics[f"{key}_s"] = float(seconds.group(1))
        else:
            metrics[key] = value
    return metrics


def _build_request(ov_infer: Any, args: argparse.Namespace) -> Any:
    language = ov_infer.Language(args.language) if args.language != "auto" else None
    sampling = ov_infer.SamplingParams(
        max_new_tokens=args.max_new_tokens,
        do_sample=not args.no_sample,
        top_k=args.top_k,
        top_p=args.top_p,
        temperature=args.temperature,
        repetition_penalty=args.repetition_penalty,
        subtalker_do_sample=not args.no_sample,
        subtalker_top_k=args.subtalker_top_k,
        subtalker_top_p=args.subtalker_top_p,
        subtalker_temperature=args.subtalker_temperature,
    )
    return ov_infer.CustomVoiceRequest(
        text=args.text,
        speaker=ov_infer.Speaker(args.speaker),
        language=language,
        instruct=args.instruct or None,
        sampling=sampling,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Qwen3-TTS OpenVINO stage placement.")
    parser.add_argument("--label", default="qwen3-openvino")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--ov-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--cache-key",
        default="",
        help="Stable OpenVINO cache leaf. Defaults to model/stage placement, not benchmark label.",
    )
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--default-device", default="CPU")
    parser.add_argument(
        "--stage-devices",
        default="",
        help="Comma list: text=CPU,codec=CPU,cp_codec=CPU,decoder=CPU,talker=CPU,cp=CPU",
    )
    parser.add_argument("--cp-f32", action="store_true")
    parser.add_argument("--text", required=True)
    parser.add_argument("--language", default="russian")
    parser.add_argument("--speaker", default="ryan")
    parser.add_argument("--instruct", default="")
    parser.add_argument("--max-new-tokens", type=int, default=24)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    parser.add_argument("--subtalker-temperature", type=float, default=0.9)
    parser.add_argument("--subtalker-top-k", type=int, default=50)
    parser.add_argument("--subtalker-top-p", type=float, default=1.0)
    parser.add_argument("--no-sample", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    np.random.seed(args.seed)
    ov_infer = _load_ov_infer(args.source_root)
    stage_devices = StageDevices.from_spec(args.stage_devices, args.default_device)
    if args.no_cache:
        cache_dir = None
    else:
        cache_key = args.cache_key.strip()
        if not cache_key:
            stage_key = "-".join(f"{key}-{value}" for key, value in stage_devices.as_dict().items())
            cache_key = f"{args.ov_dir.name}-{stage_key}"
        cache_dir = args.cache_dir / _slug(cache_key)
    output = args.output or DEFAULT_SYNTH_DIR / f"{args.label}.wav"
    output.parent.mkdir(parents=True, exist_ok=True)

    engine = StagePlacedOVQwen3TTS(
        ov_infer,
        cache_dir=cache_dir,
        stage_devices=stage_devices,
        cp_f32=args.cp_f32,
    )
    request = _build_request(ov_infer, args)

    stdout = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(stdout):
        load_start = time.perf_counter()
        engine.load_model(args.ov_dir, ov_infer.ModelType.CUSTOM_VOICE)
        load_s = time.perf_counter() - load_start
        synth_start = time.perf_counter()
        wav, sr = engine.generate(request)
        synth_s = time.perf_counter() - synth_start
        asyncio.run(engine.unload_model())
    total_s = time.perf_counter() - t0
    log = stdout.getvalue()
    print(log, end="")

    sf.write(output, wav, sr)
    audio_s = float(len(wav) / sr) if sr else 0.0
    payload: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "ok": True,
        "paths": {
            "source_root": str(args.source_root),
            "ov_dir": str(args.ov_dir),
            "cache_dir": str(cache_dir) if cache_dir is not None else None,
            "output_wav": str(output),
        },
        "versions": {
            "openvino": ov.__version__,
        },
        "stage_devices": stage_devices.as_dict(),
        "sampling": {
            "max_new_tokens": args.max_new_tokens,
            "temperature": args.temperature,
            "top_k": args.top_k,
            "top_p": args.top_p,
            "repetition_penalty": args.repetition_penalty,
            "subtalker_temperature": args.subtalker_temperature,
            "subtalker_top_k": args.subtalker_top_k,
            "subtalker_top_p": args.subtalker_top_p,
            "do_sample": not args.no_sample,
        },
        "timings": {
            "load_s": load_s,
            "synth_s": synth_s,
            "total_s": total_s,
            "audio_s": audio_s,
            "rtf": (synth_s / audio_s) if audio_s > 0 else None,
            "parsed_perf": _parse_perf_lines(log),
        },
        "resource": {
            "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "stdout": log,
    }

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "[bench] "
        f"label={args.label} load={load_s:.3f}s synth={synth_s:.3f}s "
        f"audio={audio_s:.3f}s rtf={payload['timings']['rtf']:.3f}"
    )
    print(f"[bench] wav={output}")
    if args.json_out is not None:
        print(f"[bench] json={args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
