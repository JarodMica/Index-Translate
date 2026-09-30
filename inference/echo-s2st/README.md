# echo-s2st · Speech-to-Speech Dubbing

[中文](README_zh.md)

[Index-Echo-S2ST-2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) and
[Index-Echo-S2ST-9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B) dub
a Chinese or English clip into English / Spanish / Japanese / Chinese while
preserving the source speaker's voice (ST LM → Hidden2CV mapper → CosyVoice3,
all in one self-contained package).

## Quick start

```bash
# download the package (~13 GB for 2B, ~26 GB for 9B)
huggingface-cli download IndexTeam/Index-Echo-S2ST-2B --local-dir ./Index-Echo-S2ST-2B

# install deps (see the model repo's README for the full pinned list)
pip install torch==2.11.0 torchaudio transformers==5.6.0 librosa onnxruntime \
    wetext kaldifst conformer hydra-core HyperPyYAML soundfile safetensors

# dub a Chinese clip into English
python dub.py input_zh.wav --lang en -o dub_en.wav

# English source works too — source language is auto-detected
python dub.py input_en.wav --lang zh -o dub_zh.wav
```

`--lang` is always the **target** language (`en/es/ja/zh`); supported
directions: zh→en/es/ja and en→zh/es/ja.

`dub.py` prints the transcript and translation to stderr and writes the
dubbed wav. For the underlying `DubbingBridgeModel` Python API (batch use,
`return_info`, retries), see the model repo README. Each model package also
ships its own `samples/` (input clips + reference dubs) and a
`verify_export.py` self-check.

## Notes

- One CUDA GPU: ≥12 GB VRAM (2B), ≥24 GB (9B); ffmpeg on PATH.
- Keep input clips short (≤30 s per sentence; the model is tuned for
  utterance-level dubbing). For long videos use the full pipeline in
  [`../../video-dub/`](../../video-dub/) — it handles separation, VAD
  segmentation, and timeline alignment, and `video-dub/deploy/serve_s2st.py`
  wraps the same package as an HTTP service.
- ~1% of short English-source sentences can hit a synthesis failure in the
  vocoder side — just retry (the sampler has jitter even at a fixed seed).
