# echo-s2tt · Speech-to-Text Translation (Subtitles)

[中文](README_zh.md)

[Index-Echo-S2TT-2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) and
[Index-Echo-S2TT-9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B) turn
Chinese audio/video into bilingual, timestamped subtitles (zh → en/ja/es).
The packages are self-contained: weights plus `infer.py` (VAD windowing,
sliding context for terminology consistency, optional glossary).

## Quick start

```bash
pip install torch==2.11.0 transformers==5.6.0 safetensors librosa soundfile silero-vad
# system: ffmpeg on PATH

# simplest: the wrapper downloads the 2B package on first run
python s2tt.py input.mp4 --lang en            # writes out/input.srt
python s2tt.py talk.wav --lang ja --size 9b   # use the 9B package

# or work with a package directly
huggingface-cli download IndexTeam/Index-Echo-S2TT-2B --local-dir ./Index-Echo-S2TT-2B
python Index-Echo-S2TT-2B/infer.py input.mp4 --out out_dir --target-lang en
```

Output: `<out>/<name>.srt` (two lines per cue: Chinese transcript + target
translation) and `<out>/<name>.windows.jsonl` (per-window raw output).

Useful flags (pass through `s2tt.py`, or use with `infer.py` directly):

- `--glossary "原名1:译名1,原名2:译名2"` — pin terminology per window
- `--max-win 60` — VAD window cap in seconds
- `--ctx-k 5` — how many previous windows feed the `[Context]` slot
- `--device cuda:1` — pick the GPU

## Notes

- ~10 GB VRAM (2B, bf16); roughly 1.4–1.7× realtime on an A100, one file per
  GPU (run several files on several GPUs).
- Source language is Chinese; targets are English / Japanese / Spanish.
