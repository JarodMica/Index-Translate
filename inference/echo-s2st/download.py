#!/usr/bin/env python3
"""Download a pinned official Index-Echo speech-to-speech package."""
import argparse
from pathlib import Path

MODELS = {
    "2b": ("IndexTeam/Index-Echo-S2ST-2B", "0a1a87d26cf0bade2b637c29f0b629e855d14044"),
    "9b": ("IndexTeam/Index-Echo-S2ST-9B", "62ccfab70a41a4959e82548ff40b07667413db5c"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=MODELS, default="2b")
    parser.add_argument("--model-dir", type=Path, help="Destination; defaults to models/<package name>")
    args = parser.parse_args()
    repo, revision = MODELS[args.size]
    destination = args.model_dir or Path("models") / repo.split("/")[-1]
    from huggingface_hub import snapshot_download
    snapshot_download(repo, revision=revision, local_dir=destination,
                      ignore_patterns=["_legacy/*", "__pycache__/*", "**/__pycache__/*"], max_workers=4)
    print(f"Model ready: {destination.resolve()}")


if __name__ == "__main__":
    main()
