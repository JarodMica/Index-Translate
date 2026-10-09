"""Serialized standard inference shared by the clip and live interfaces."""
import gc
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

import numpy as np
import soundfile as sf
import torch
from download import MODELS

LANGUAGES = ("en", "es", "ja", "zh")
SESSION_CACHES = ("tts_speech_token_dict", "llm_end_dict", "hift_cache_dict")


class Engine:
    def __init__(self, root: Path, size: str, model_dir: Path | None = None):
        self.root = root
        self.size = size
        self.custom_model = model_dir is not None
        self.model_dir = (model_dir or root / "models" / MODELS[size][0].split("/")[-1]).resolve()
        self.outputs = root / "outputs" / "demos"
        self.model = None
        self.lock = threading.Lock()

    def download(self):
        if self.custom_model:
            if not (self.model_dir / "modeling_dubbing.py").is_file():
                raise ValueError("The selected folder is not an Index-Echo S2ST package")
            return
        from huggingface_hub import snapshot_download
        repo, revision = MODELS[self.size]
        snapshot_download(repo, revision=revision, local_dir=self.model_dir,
                          ignore_patterns=["_legacy/*", "__pycache__/*", "**/__pycache__/*"], max_workers=4)

    def sample(self, source):
        if source not in ("en", "zh"):
            raise ValueError("Choose an English or Chinese sample")
        with self.lock:
            self.download()
        return str(self.model_dir / "samples" / f"input_{source}.wav")

    def _load(self):
        if self.model is not None:
            return self.model
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable. Install with uv sync --extra cu130 and check your NVIDIA driver.")
        free = torch.cuda.mem_get_info()[0]
        if shutil.which("nvidia-smi"):
            reading = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], text=True, timeout=10)
            free = min(free, int(reading.splitlines()[0]) * 1024**2)
        minimum = 10 if self.size == "2b" else 24
        if free < minimum * 1024**3:
            raise RuntimeError(f"Only {free / 1024**3:.1f} GiB GPU memory is free. Free roughly {minimum} GiB before loading {self.size}.")
        self.download()
        os.environ["DUBBING_HOME"] = str(self.model_dir)
        sys.path.insert(0, str(self.model_dir))
        from modeling_dubbing import DubbingBridgeModel
        self.model = DubbingBridgeModel.from_pretrained(str(self.model_dir), device="cuda")
        return self.model

    def prepare(self):
        with self.lock:
            self._load()
        return f"{self.size.upper()} model ready."

    def unload(self):
        with self.lock:
            self.model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        return "Model unloaded."

    def _synthesize(self, pipe, extracted):
        acoustic = pipe.cv.model
        for attempt, seed in enumerate((42, 43, 44), 1):
            snapshots = {name: set(getattr(acoustic, name)) for name in SESSION_CACHES}
            try:
                wave, info = pipe.synth(extracted, out_wav=None, seed=seed)
                if wave.shape[-1] / pipe.sample_rate < .1:
                    raise RuntimeError("Collapsed speech output")
                if not torch.isfinite(wave).all().item():
                    raise RuntimeError("Synthesis returned non-finite audio")
                return wave, info, attempt, seed
            except RuntimeError as error:
                with acoustic.lock:
                    for name in SESSION_CACHES:
                        cache = getattr(acoustic, name)
                        for key in set(cache) - snapshots[name]:
                            cache.pop(key, None)
                known_short = (str(error) == "Collapsed speech output" or
                               ("Calculated padded input size per channel" in str(error) and
                                "Kernel size can't be greater than actual input size" in str(error)))
                if not known_short:
                    raise
                logging.warning("Short speech output on seed %s (attempt %s/3)", seed, attempt)
        raise RuntimeError("Speech synthesis failed on three attempts. Try a longer phrase.")

    def translate(self, audio, target):
        if not audio:
            raise ValueError("Record or upload English or Chinese audio first")
        if target not in LANGUAGES:
            raise ValueError("Unsupported target language")
        input_info = sf.info(audio)
        if not 0 < input_info.duration <= 30:
            raise ValueError("Use a clip between 0 and 30 seconds long")
        with self.lock:
            started = time.perf_counter()
            model = self._load()
            load_seconds = time.perf_counter() - started
            began = time.perf_counter()
            extracted = model._pipe.extract(str(audio), lang=target)
            wave, details, attempts, seed = self._synthesize(model._pipe, extracted)
            samples = wave.detach().cpu().numpy().T
            if not np.isfinite(samples).all():
                raise RuntimeError("Synthesis returned non-finite audio")
            self.outputs.mkdir(parents=True, exist_ok=True)
            output = self.outputs / f"{target}-{uuid.uuid4().hex}.wav"
            sf.write(output, samples, model.sample_rate, subtype="PCM_16")
            elapsed = time.perf_counter() - began
            summary = dict(model=self.size, runtime="standard", source_language=details.get("src_lang"),
                           source_transcript=details.get("zh"), translation=details.get("tgt_raw"),
                           speech_frontend_text=details.get("tgt_cv"), input_seconds=input_info.duration,
                           output_seconds=len(samples) / model.sample_rate, sample_rate=model.sample_rate,
                           load_seconds=round(load_seconds, 3), inference_seconds=round(elapsed, 3),
                           rtf=round(elapsed / input_info.duration, 3), synthesis_attempts=attempts,
                           synthesis_seed=seed)
            output.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(output), summary
