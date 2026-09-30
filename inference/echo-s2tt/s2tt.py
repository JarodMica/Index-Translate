#!/usr/bin/env python3
"""Speech/video -> timestamped bilingual subtitles with Index-Echo-S2TT-2B/9B.

The model packages are self-contained (weights + infer.py inside). This
script is a convenience wrapper: it downloads a package from Hugging Face
if needed, then runs its infer.py.

Usage:
    python s2tt.py input.mp4 --lang en                      # -> out/input.srt
    python s2tt.py talk.wav --lang ja --size 9b -o out_dir

Requires: Python 3.12+, one CUDA GPU (~10 GB VRAM for 2B), ffmpeg on PATH,
and the pip packages from the model repo's requirements.txt
(torch 2.11, transformers>=5.6, librosa, soundfile, silero-vad).
"""

import argparse
import os
import subprocess
import sys

HF_REPOS = {"2b": "IndexTeam/Index-Echo-S2TT-2B", "9b": "IndexTeam/Index-Echo-S2TT-9B"}
LANGS = ("en", "ja", "es")


def ensure_model(size: str, model_dir: str | None) -> str:
    if model_dir:
        return os.path.abspath(model_dir)
    repo = HF_REPOS[size]
    local = os.path.abspath(f"./{repo.split('/')[-1]}")
    if not os.path.isfile(os.path.join(local, "infer.py")):
        print(f"[s2tt] downloading {repo} -> {local} ...", file=sys.stderr, flush=True)
        from huggingface_hub import snapshot_download
        snapshot_download(repo, local_dir=local)
    return local


def main() -> None:
    ap = argparse.ArgumentParser(description="Speech-to-text translation (subtitles) with Index-Echo-S2TT")
    ap.add_argument("input", help="audio/video file (wav/mp3/m4a/mp4, zh source)")
    ap.add_argument("--lang", "-l", default="en", choices=LANGS, help="target language (default: en)")
    ap.add_argument("--size", "-s", default="2b", choices=list(HF_REPOS), help="model size (default: 2b)")
    ap.add_argument("--model-dir", "-m", help="use an already-downloaded package instead of ./Index-Echo-*")
    ap.add_argument("-o", "--out", default="out", help="output directory (default: ./out)")
    ap.add_argument("--device", default=None, help="e.g. cuda:0")
    ap.add_argument("--glossary", default=None, help="'name1:translation1,name2:translation2'")
    args, extra = ap.parse_known_args()

    model_dir = ensure_model(args.size, args.model_dir)
    infer = os.path.join(model_dir, "infer.py")
    if not os.path.isfile(infer):
        ap.error(f"{model_dir} has no infer.py — not an Index-Echo-S2TT package?")

    cmd = [sys.executable, infer, os.path.abspath(args.input),
           "--target-lang", args.lang, "--out", os.path.abspath(args.out)]
    if args.device:
        cmd += ["--device", args.device]
    if args.glossary:
        cmd += ["--glossary", args.glossary]
    cmd += extra  # pass through any advanced infer.py flags (--max-win, --ctx-k, ...)

    print("[s2tt] running:", " ".join(cmd), file=sys.stderr, flush=True)
    raise SystemExit(subprocess.run(cmd, cwd=model_dir).returncode)


if __name__ == "__main__":
    main()
