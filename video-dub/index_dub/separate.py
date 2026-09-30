"""Optional vocal separation (demucs).

Isolates vocals from background music/noise so the S2ST model only sees
speech, and returns the instrumental stem so it can be mixed back under the
dubbed voice. Requires: pip install demucs
"""

import os
import shutil
import subprocess


def separate_vocals(in_wav, workdir, model="htdemucs", device=None):
    """Run demucs two-stem separation.

    Returns (vocals_wav, instrumental_wav) paths.
    """
    if shutil.which("demucs") is None:
        raise RuntimeError(
            "demucs not found (pip install demucs); "
            "pass --no-separate to skip vocal separation")
    cmd = ["demucs", "--two-stems", "vocals", "-n", model, "-o", workdir]
    if device:
        cmd += ["-d", device]
    cmd.append(in_wav)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"demucs failed (exit {e.returncode}): "
            f"{(e.stderr or e.stdout or '').strip()[-500:]}") from e
    stem = os.path.join(workdir, model,
                        os.path.splitext(os.path.basename(in_wav))[0])
    vocals = os.path.join(stem, "vocals.wav")
    instr = os.path.join(stem, "no_vocals.wav")
    if not os.path.exists(vocals):
        raise RuntimeError(f"demucs output missing: {vocals}")
    return vocals, instr
