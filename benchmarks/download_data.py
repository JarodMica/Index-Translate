#!/usr/bin/env python3
"""Fetch pinned public benchmark data and verify the complete frozen release.

Data files (`release['data_files']`) are hard verified: size and SHA256 must match
the pinned release byte for byte. The remaining entries in `release['files']` mirror
sources that already live in this repository, so they are only advisories: a Windows
checkout with `core.autocrlf=true` rewrites their line endings (compared
LF-normalised here) and the repository legitimately keeps editing them after the
release snapshot was cut. Mirror drift is printed as a warning; data drift aborts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def verify_data_file(path, spec):
    """Data files are pinned byte for byte: git never rewrites their contents."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing {spec['path']}; run download_data.py first")
    if path.stat().st_size != spec['size'] or sha256_bytes(path.read_bytes()) != spec['sha256']:
        raise ValueError(f"Size/SHA256 mismatch: {path}. Existing files are never overwritten.")


def verify_mirror_file(path, spec):
    """Report whether a checkout copy of a released source file matches its pinned digest.

    Line endings are normalised to LF before hashing so that a CRLF checkout is not
    mistaken for drift. Returns True only on an exact (normalised) match; anything
    else is reported on stderr and never aborts the data download.
    """
    if not path.is_file():
        print(
            f"Warning: mirror file {path} missing from the checkout; it comes from this "
            "repository, not from the dataset download.",
            file=sys.stderr,
        )
        return False
    data = path.read_bytes().replace(b'\r\n', b'\n')
    if len(data) != spec['size'] or sha256_bytes(data) != spec['sha256']:
        print(
            f"Warning: mirror file {path} differs from the released {spec['path']} "
            "(LF-normalised size/SHA256 mismatch); the local copy is kept.",
            file=sys.stderr,
        )
        return False
    return True


def prepare(name, release, verify_only=False):
    destination = ROOT / name
    specs = {f['path']: f for f in release['files']}
    data_files = release['data_files']
    missing = []
    # Check existing files before downloading; preserve local edits on mismatch.
    for relative in data_files:
        target = destination / relative
        if target.exists():
            verify_data_file(target, specs[relative])
        else:
            missing.append(relative)
    # Mirror files are never downloaded, so check them before paying for any network
    # transfer: drift in the checkout must be visible before the data is fetched.
    mirrors = [p for p in specs if p not in data_files]
    mirrors_verified = sum(verify_mirror_file(destination / p, specs[p]) for p in mirrors)
    if missing and not verify_only:
        from huggingface_hub import snapshot_download
        snapshot = Path(snapshot_download(
            repo_id=release['repo_id'], repo_type='dataset',
            revision=release['revision'], allow_patterns=missing,
        ))
        # Validate the whole download before writing any destination files.
        for relative in missing:
            verify_data_file(snapshot / relative, specs[relative])
        for relative in missing:
            target = destination / relative
            if target.exists():
                verify_data_file(target, specs[relative])
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshot / relative, target)
    for relative in data_files:
        verify_data_file(destination / relative, specs[relative])
    print(
        f"{name}: verified {len(data_files)} data files and "
        f"{mirrors_verified}/{len(mirrors)} mirror files at {release['revision']}"
    )


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
