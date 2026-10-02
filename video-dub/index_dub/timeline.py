"""Assemble dubbed segments back onto the original timeline."""

import os

import numpy as np
import soundfile as sf

from . import media


def _fit_segment(dub_wav, slot_dur, workdir, idx, sr, max_stretch=1.5):
    """Time-stretch a dubbed segment to fit its slot; returns samples at sr.

    ratio = dub_dur / slot_dur (>1 means the dub is too long and is sped up;
    <1 means the dub is shorter and is slowed down to stretch and fill the slot).
    The stretch factor is clamped to [1.0 / max_stretch, max_stretch].
    Any segment still exceeding its slot after maximum acceleration is
    truncated; silence naturally follows if a segment cannot stretch enough.
    """
    y, y_sr = sf.read(dub_wav)
    if y.ndim > 1:
        y = y.mean(axis=1)
    dub_dur = len(y) / y_sr
    ratio = dub_dur / max(slot_dur, 1e-3)
    cur = dub_wav
    if abs(ratio - 1.0) > 0.05:
        stretch = min(max(ratio, 1.0 / max_stretch), max_stretch)
        cur = os.path.join(workdir, f"fit_{idx:04d}.wav")
        media.speed_to_duration(dub_wav, cur, stretch, sr)
    if sf.info(cur).samplerate != sr:
        out = os.path.join(workdir, f"rs_{idx:04d}.wav")
        media.run(["ffmpeg", "-y", "-i", cur, "-ac", "1", "-ar", str(sr),
                   "-c:a", "pcm_s16le", out])
        cur = out
    y, _ = sf.read(cur)
    if y.ndim > 1:
        y = y.mean(axis=1)
    return y


def build_track(spans, dub_wavs, total_dur, workdir, sr=24000, max_stretch=1.5):
    """Place each dubbed wav at its original span; returns (samples, sr)."""
    n = int(total_dur * sr)
    track = np.zeros(n, dtype=np.float32)
    for i, ((s, e), wav) in enumerate(zip(spans, dub_wavs)):
        if wav is None:  # segment failed to dub; slot stays silent/instrumental
            continue
        y = _fit_segment(wav, e - s, workdir, i, sr, max_stretch)
        start_i = int(s * sr)
        cap = n - start_i  # never run past the end of the video
        if i + 1 < len(spans):  # never bleed into the next segment
            cap = min(cap, int(spans[i + 1][0] * sr) - start_i)
        if cap <= 0:
            continue
        y = y[:cap]
        track[start_i:start_i + len(y)] += y.astype(np.float32)
    peak = np.abs(track).max()
    if peak > 0.99:  # avoid clipping after adds
        track *= 0.99 / peak
    return track, sr
