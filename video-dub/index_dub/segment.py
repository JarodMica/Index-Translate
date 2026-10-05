"""Speech segmentation with timestamps.

Primary backend: silero-vad (pip install silero-vad). Fallback: ffmpeg
silencedetect. Segments are capped at ``max_dur`` seconds because the S2ST
model cannot take long inputs; over-long speech runs are split at their
quietest internal point.
"""

import re
import subprocess

import numpy as np


def _energy_quietest_split(y, sr, t0, t1, min_cut=2.0):
    """Find the quietest timestamp inside (t0+min_cut, t1-min_cut)."""
    i0, i1 = int((t0 + min_cut) * sr), int((t1 - min_cut) * sr)
    if i1 <= i0:
        return (t0 + t1) / 2
    win = int(0.1 * sr)  # 100ms rms window
    seg = y[i0:i1]
    n = len(seg) // win
    if n == 0:
        return (t0 + t1) / 2
    e = np.sqrt((seg[: n * win].reshape(n, win) ** 2).mean(axis=1))
    return t0 + min_cut + (int(e.argmin()) + 0.5) * win / sr


def _enforce_max_dur(spans, y, sr, max_dur):
    """Recursively split spans longer than max_dur at quiet internal points."""
    if max_dur <= 0:
        raise ValueError(f"max_dur must be > 0 seconds, got {max_dur} "
                         "(splitting would never terminate)")
    out = []
    stack = list(spans)
    while stack:
        s, e = stack.pop()
        if e - s <= max_dur:
            out.append((s, e))
            continue
        cut = _energy_quietest_split(y, sr, s, e)
        stack.append((cut, e))
        stack.append((s, cut))
    out.sort()
    return out


def _merge_short_gaps(spans, max_gap, max_dur):
    """Merge adjacent spans separated by short gaps (keeps sentences whole)."""
    merged = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= max_gap and e - merged[-1][0] <= max_dur:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def segment_silero(wav_path, max_dur=12.0, min_silence_ms=500,
                   min_speech_ms=250, merge_gap=0.35, pad=0.05):
    """Return [(start, end), ...] speech spans in seconds using silero-vad."""
    import soundfile as sf
    import torch
    from silero_vad import load_silero_vad, get_speech_timestamps

    # load with soundfile instead of silero's read_audio so we don't depend
    # on torchaudio/torchcodec for plain 16k mono wav input
    data, sr = sf.read(wav_path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        raise ValueError(f"expected 16kHz mono wav, got sr={sr}")
    wav = torch.from_numpy(data)
    model = load_silero_vad()
    ts = get_speech_timestamps(
        wav, model, sampling_rate=16000,
        min_speech_duration_ms=min_speech_ms,
        min_silence_duration_ms=min_silence_ms,
    )
    y = data
    total = len(y) / 16000
    spans = [(max(0.0, t["start"] / 16000 - pad), min(total, t["end"] / 16000 + pad))
             for t in ts]
    spans = _merge_short_gaps(spans, merge_gap, max_dur)
    spans = _enforce_max_dur(spans, y, 16000, max_dur)
    return [(round(s, 3), round(e, 3)) for s, e in spans if e - s >= 0.2]


def segment_ffmpeg(wav_path, max_dur=12.0, silence_thresh="-35dB",
                   min_silence=0.5, pad=0.05):
    """Fallback VAD using ffmpeg silencedetect (no extra dependencies)."""
    import soundfile as sf

    proc = subprocess.run(
        ["ffmpeg", "-i", wav_path, "-af",
         f"silencedetect=noise={silence_thresh}:d={min_silence}",
         "-f", "null", "-"],
        capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    y, sr = sf.read(wav_path)
    if y.ndim > 1:
        y = y.mean(axis=1)
    total = len(y) / sr
    # speech = complement of silence
    spans, cursor = [], 0.0
    for ss, se in zip(starts, ends):
        if ss > cursor + 0.2:
            spans.append((cursor, ss))
        cursor = max(cursor, se)
    if total > cursor + 0.2:
        spans.append((cursor, total))
    spans = [(max(0.0, s - pad), min(total, e + pad)) for s, e in spans]
    spans = _merge_short_gaps(spans, 0.35, max_dur)
    spans = _enforce_max_dur(spans, y, sr, max_dur)
    return [(round(s, 3), round(e, 3)) for s, e in spans if e - s >= 0.2]


def segment_audio(wav_path, backend="auto", **kw):
    """Segment audio; backend = 'silero' | 'ffmpeg' | 'auto'."""
    max_dur = kw.get("max_dur")
    if max_dur is not None and max_dur <= 0:
        # reject early: a non-positive cap cannot be satisfied by splitting
        raise ValueError(f"max_dur must be > 0 seconds, got {max_dur}")
    if backend in ("auto", "silero"):
        try:
            return segment_silero(wav_path, **kw)
        except ImportError:
            if backend == "silero":
                raise
            print("[segment] silero-vad not installed, falling back to ffmpeg")
    return segment_ffmpeg(wav_path, **kw)
