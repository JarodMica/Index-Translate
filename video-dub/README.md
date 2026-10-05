# video-dub · Video Translation & Dubbing

[中文](README_zh.md)

Feed in an mp4, get back the same video dubbed into another language — powered by the **Index S2ST (speech-to-speech translation) models**:

```
mp4 → extract audio → vocal separation (demucs) → VAD segmentation (timestamps)
    → per-segment S2ST dubbing → timeline alignment → dubbed mp4
```

Because S2ST models can't take long inputs, speech is split into short
utterances (≤9.5 s by default) with timestamps; each segment is dubbed by the
inference service and placed back onto the original timeline (lightly
time-stretched to fit), with optional SRT subtitles and a per-segment JSON
manifest.

## Requirements

- Python 3.9+, `ffmpeg` on PATH
- `pip install -r requirements.txt`
  - `demucs` for vocal separation (on by default; downloads ~80 MB of models on first run, `--no-separate` to disable)
  - `silero-vad`/`torch` for accurate segmentation; without them the pipeline falls back to ffmpeg silencedetect
- A reachable S2ST inference service (see [deploy/](deploy/))

## Quick start

```bash
# Dub input.mp4 into English (vocal separation + BGM kept under the dub)
python dub_video.py input.mp4 --lang en --s2st-url http://127.0.0.1:8094

# Clean voice-over footage can skip separation; also export subtitles
python dub_video.py input.mp4 --lang en --no-separate --srt

# Japanese output, custom segment cap, more parallel requests
python dub_video.py input.mp4 --lang ja --max-seg 10 --workers 8
```

Outputs:

- `<input>.<lang>.mp4` — the dubbed video
- `<input>.<lang>.srt` — (`--srt`) translated subtitles on the original timeline
- `<input>.<lang>.segments.json` — per-segment timestamps + translations

Target languages: `en / es / ja / zh` (source auto-detected: Chinese/English).

## How it works

| Step | Module | Notes |
|---|---|---|
| Audio extraction | `index_dub/media.py` | ffmpeg → 16 kHz mono wav |
| Vocal separation | `index_dub/separate.py` | on by default, demucs two-stem; the instrumental is mixed back under the dub. `--no-separate` skips it, `--no-bgm` drops the music |
| Segmentation | `index_dub/segment.py` | silero-vad speech spans, short gaps merged, over-long spans re-split at their quietest point; all with timestamps |
| Dubbing | `index_dub/s2st.py` | `POST {url}/s2st` (multipart: `file`=wav, `lang`=target) → `audio_b64` (24 kHz wav) + source/translated text; `--workers N` parallel requests |
| Timeline assembly | `index_dub/timeline.py` | each dub goes back into its original slot: stretched to fit the slot in both directions (`--max-stretch` cap, so a short dub is slowed down to fill the time), silence elsewhere |
| Muxing | `index_dub/media.py` | ffmpeg audio-track replacement, video stream copied (no re-encode) |

## Inference service

The workflow talks to an HTTP service (`--s2st-url` or env `S2ST_URL`):

```
GET  /healthz   -> {"ok": true, "langs": ["en","es","ja","zh"]}
POST /s2st      multipart: file=<wav>, lang=<en|es|ja|zh>
                -> {"ok": true, "audio_b64": "<24kHz wav base64>",
                    "sr": 24000, "zh": "<source>", "text": "<translation>", ...}
POST /s2tt      same input, text translation only
```

To self-host the service offline, see [deploy/](deploy/) — it wraps the
official DubbingBridgeModel export package (single GPU, ~22 GB VRAM for 9B).

## Known limits

- Source language auto-detection supports Chinese/English only
- Fast speech + long translations may be time-stretched up to `--max-stretch` (default 1.5×), hard-truncated to the slot beyond that
- The stretch goes both ways: a dub shorter than its slot is **slowed down** (up to the same `--max-stretch` cap) so it still fills the original timing — very short utterances can therefore sound dragged out
- Best with a single speaker; overlapping speakers / heavy BGM rely on vocal separation (on by default)

## License

Apache 2.0 (see repo root LICENSE).
