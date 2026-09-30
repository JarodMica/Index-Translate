"""ffmpeg helpers: audio extraction, muxing, tempo adjustment."""

import json
import os
import subprocess
import tempfile


def run(cmd, **kw):
    proc = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stderr[-2000:]}")
    return proc


def probe_duration(path):
    """Return media duration in seconds."""
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", path,
    ])
    return float(json.loads(out.stdout)["format"]["duration"])


def extract_audio(video_path, out_wav, sr=16000):
    """Extract mono PCM wav from a video (or audio) file."""
    run([
        "ffmpeg", "-y", "-i", video_path, "-vn",
        "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", out_wav,
    ])
    return out_wav


def atempo_chain(ratio):
    """Build an atempo filter string; each atempo factor must be in [0.5, 2.0]."""
    ratio = max(0.25, min(4.0, ratio))
    parts = []
    r = ratio
    while r > 2.0:
        parts.append("atempo=2.0")
        r /= 2.0
    while r < 0.5:
        parts.append("atempo=0.5")
        r /= 0.5
    parts.append(f"atempo={r:.4f}")
    return ",".join(parts)


def speed_to_duration(in_wav, out_wav, ratio, sr):
    """Time-stretch in_wav by ratio (>1 = faster/shorter) and write sr-Hz wav."""
    run([
        "ffmpeg", "-y", "-i", in_wav, "-af", atempo_chain(ratio),
        "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", out_wav,
    ])
    return out_wav


def mux_video_audio(video_path, audio_path, out_path, audio_codec="aac"):
    """Replace the audio track of video_path with audio_path."""
    run([
        "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", audio_codec, "-shortest", out_path,
    ])
    return out_path


def mix_audio(base_wav, over_wav, out_wav, base_vol=1.0, over_vol=1.0, sr=24000):
    """Mix over_wav on top of base_wav (e.g. dubbed voice over instrumental)."""
    run([
        "ffmpeg", "-y", "-i", base_wav, "-i", over_wav,
        "-filter_complex",
        f"[0:a]volume={base_vol}[b];[1:a]volume={over_vol}[o];"
        f"[b][o]amix=inputs=2:duration=longest:normalize=0[mix]",
        "-map", "[mix]", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", out_wav,
    ])
    return out_wav


def extract_segment(in_wav, out_wav, start, end, sr=16000):
    """Cut [start, end) seconds from in_wav."""
    run([
        "ffmpeg", "-y", "-i", in_wav, "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", out_wav,
    ])
    return out_wav
