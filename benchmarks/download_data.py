#!/usr/bin/env python3
"""Fetch pinned public benchmark data and verify the complete frozen release."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def verify_file(path, spec):
    if not path.is_file():
        raise FileNotFoundError(f"Missing {spec['path']}; run download_data.py first")
    if path.stat().st_size != spec['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError(f"Size/SHA256 mismatch: {path}. Existing files are never overwritten.")


def prepare(name, release, verify_only=False):
    destination = ROOT / name
    specs = {f['path']: f for f in release['files']}
    missing = []
    # Check existing files before downloading; preserve local edits on mismatch.
    for relative in release['data_files']:
        target = destination / relative
        if target.exists():
            verify_file(target, specs[relative])
        else:
            missing.append(relative)
    if missing and not verify_only:
        from huggingface_hub import snapshot_download
        snapshot = Path(snapshot_download(
            repo_id=release['repo_id'], repo_type='dataset',
            revision=release['revision'], allow_patterns=missing,
        ))
        # Validate the whole download before writing any destination files.
        for relative in missing:
            verify_file(snapshot / relative, specs[relative])
        for relative in missing:
            target = destination / relative
            if target.exists():
                verify_file(target, specs[relative])
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshot / relative, target)
    for relative, spec in specs.items():
        verify_file(destination / relative, spec)
    print(f"{name}: verified {len(specs)} files at {release['revision']}")


def main():
    releases = json.loads((ROOT / 'releases.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('benchmark', choices=['all', *releases])
    parser.add_argument('--verify-only', action='store_true', help='Verify locally; no network requests')
    args = parser.parse_args()
    for name in releases if args.benchmark == 'all' else [args.benchmark]:
        prepare(name, releases[name], args.verify_only)


if __name__ == '__main__':
    main()
