#!/usr/bin/env python3
"""Dub an audio clip with Index-Echo-S2ST-2B / Index-Echo-S2ST-9B.

Speech-to-speech translation: feed a Chinese or English clip, get it back
dubbed into English / Spanish / Japanese / Chinese, preserving the source
speaker's voice (ST LM -> Hidden2CV mapper -> CosyVoice3, single package).

Usage:
    # one-time download (~13 GB for 2B, ~26 GB for 9B)
    huggingface-cli download IndexTeam/Index-Echo-S2ST-2B --local-dir ./Index-Echo-S2ST-2B

    python dub.py input.wav --lang en --model-dir ./Index-Echo-S2ST-2B -o dub_en.wav
    python dub.py english.wav --lang zh --model-dir ./Index-Echo-S2ST-2B -o dub_zh.wav

`--lang` is the TARGET language (en/es/ja/zh); the source language is
auto-detected (CJK transcript -> zh source, otherwise en source).

Requirements: Python 3.12+, one CUDA GPU (>=12 GB VRAM for 2B, >=24 GB for 9B),
ffmpeg on PATH, and the pip packages listed in the model repo's README
(torch 2.11, transformers 5.6, librosa, onnxruntime, wetext, kaldifst, ...).

For an HTTP service wrapper or full video dubbing, see ../../video-dub/.
"""

import argparse
import os
import sys

LANGS = ("en", "es", "ja", "zh")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dub audio with Index-Echo-S2ST models")
    ap.add_argument("input", help="input audio (wav/mp3/m4a/flac, <=30s recommended)")
    ap.add_argument("--lang", "-l", required=True, choices=LANGS,
                    help="TARGET language: en/es/ja/zh (source is auto-detected)")
    ap.add_argument("--model-dir", "-m", default=os.environ.get("S2ST_MODEL_DIR", "./Index-Echo-S2ST-2B"),
                    help="local path of the downloaded model package")
    ap.add_argument("-o", "--out", default=None,
                    help="output wav path (default: dub_<lang>.wav in the current directory)")
    args = ap.parse_args()

    model_dir = os.path.abspath(args.model_dir)
    if not os.path.isfile(os.path.join(model_dir, "modeling_dubbing.py")):
        ap.error(f"{model_dir} does not look like an Index-Echo-S2ST package "
                 f"(modeling_dubbing.py missing). Download with:\n"
                 f"  huggingface-cli download IndexTeam/Index-Echo-S2ST-2B --local-dir {args.model_dir}")

    # Resolve the user's input/output paths BEFORE chdir(): we switch into the model
    # directory below, so a relative path would be resolved against the package instead
    # of the caller's working directory (dub.py clip.wav would look for
    # <model_dir>/clip.wav). Same treatment as ../../echo-s2tt/s2tt.py.
    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        ap.error(f"input audio not found: {input_path}")
    out_wav = os.path.abspath(args.out or f"dub_{args.lang}.wav")

    # The package is self-contained: weights + all inference code live inside.
    sys.path.insert(0, model_dir)
    os.chdir(model_dir)  # relative paths inside the package (code/, wetext/, ...)

    from modeling_dubbing import DubbingBridgeModel

    print(f"[dub] loading {model_dir} ...", file=sys.stderr, flush=True)
    model = DubbingBridgeModel.from_pretrained(model_dir)
    print("[dub] model loaded", file=sys.stderr, flush=True)

    wav, sr, info = model.dub(input_path, lang=args.lang, out_wav=out_wav, return_info=True)
    print(f"[dub] source lang : {info['src_lang']}", file=sys.stderr)
    print(f"[dub] transcript  : {info['zh']}", file=sys.stderr)
    print(f"[dub] translation : {info['tgt_raw']}", file=sys.stderr)
    print(f"[dub] saved {out_wav} ({sr} Hz)")


if __name__ == "__main__":
    main()
