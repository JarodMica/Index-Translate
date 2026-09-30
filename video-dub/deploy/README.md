# Self-hosting the S2ST inference service

`serve_s2st.py` wraps the official DubbingBridgeModel export package
(ST LM + Hidden2CV mapper + CosyVoice3 in one directory) as the HTTP service
that `dub_video.py` expects. A single GPU is enough.

## Export package layout (9B example, ~22 GB VRAM in bf16)

```
dubbing_9b_fulldir_cv3/
├── modeling_dubbing.py     # DubbingBridgeModel entry point
├── stlm_ckpt/              # speech-translation LM (EXP-53)
├── stlm_llm/  stlm_omni/   # LLM backbone + omni encoder
├── bridge/                 # Hidden2CV mapper (~26M)
├── cosyvoice3/             # vocoder (CosyVoice3)
└── samples/                # self-check samples
```

## Environment

- GPU: one card with ≥ 24 GB (9B needs ~22 GB; the 2B package needs less)
- Dependencies per the export package README (reference pins:
  `torch 2.11.0+cu129`, `transformers 5.6.0`), plus `fastapi uvicorn` and `ffmpeg`

## Run

```bash
python serve_s2st.py --model-dir /path/to/dubbing_9b_fulldir_cv3 \
    --port 8094 --device 0
```

Then point the client at it:

```bash
python dub_video.py input.mp4 --lang en --s2st-url http://<host>:8094
```

## Notes

- `/s2st` rejects audio longer than ~**10.5 s** — the client default
  `--max-seg 9.5` leaves headroom; if you raise it, raise `S2ST_MAX_S` too
- `/s2tt` (text only) accepts up to 60 s
- The service is single-concurrency (global inference lock). For throughput,
  run multiple instances behind a load balancer
