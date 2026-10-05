# Index-Dub Demo Web App

[中文详细教程](README_zh.md)

A self-contained demo site for video dubbing: **upload a video → watch it get
dubbed live → play the result with bilingual (source + translation)
subtitles**. Every finished video becomes a case in the showcase; old cases
are never removed.

## Features

- 📤 Drag & drop or file-picker upload
- 🌐 Language selection: **source** (auto-detect / 中文 / English) + **target** (zh / en / es / ja), aligned with the official S2ST service (zh → en/es/ja, en → zh/es/ja); picking a source filters the target dropdown to supported directions
- 📊 Live progress: extract → vocal separation → segmentation → per-segment dubbing (x/y) → assembly → muxing
- 🎬 Result playback: dubbed video + bilingual cue list that scrolls and highlights with playback; click a cue to seek; spacebar toggles play/pause
- 🗂 Case library: every result is auto-registered; history persists across restarts
- 🔊 Segments whose source language equals the target (e.g. English lines in a zh→en job) keep the original voice and are badged 原声

## Architecture

```
browser ──HTTP──> demo/app.py (FastAPI) ──HTTP──> S2ST inference service
                  · SPA + Range-aware video       · self-hosted (deploy/serve_s2st.py)
                  · upload / jobs / progress API  · or any existing /s2st endpoint
                  · pipeline worker threads
```

The app does **not** bundle model weights — inference goes through the S2ST
HTTP service.

## Setup

```bash
cd <repo>/video-dub                      # the paths below are relative to video-dub/
pip install -r requirements.txt          # pipeline deps (video-dub/requirements.txt)
pip install -r demo/requirements.txt     # web app deps (video-dub/demo/requirements.txt)
ffmpeg -version                          # ffmpeg must be on PATH
```

### The S2ST service: use an existing one, or self-host

```bash
# self-host on a GPU machine (2B ≈ 8 GB VRAM bf16, 9B ≈ 22 GB; int4 packages ~6.6/10.6 GB)
python deploy/serve_s2st.py --model-dir /path/to/dubbing_2b_fulldir_cv3 --port 8094
curl http://127.0.0.1:8094/healthz

# or tunnel to a remote one
ssh -N -L 8094:127.0.0.1:8094 <gpu-host>
```

## Run

```bash
python3 demo/app.py --s2st-url http://127.0.0.1:8094 --port 8080
# open http://127.0.0.1:8080/
```

| Flag | Default | Notes |
|---|---|---|
| `--s2st-url` | env `S2ST_URL`, else `http://127.0.0.1:8094` | S2ST service base URL |
| `--port` | 8080 | web port |
| `--host` | 127.0.0.1 | use `0.0.0.0` to share on LAN |

## Usage

1. Drop a video onto the upload zone (or click to pick a file)
2. Choose the **source language** (default 自动识别 — the model auto-detects zh/en) and the **target language**; once a source is picked, the target dropdown only offers officially supported directions (zh → en/es/ja, en → zh/es/ja) and same-language pairs are rejected server-side with 400
3. Options: **vocal separation** (recommended when the video has BGM; demucs
   downloads ~80 MB of models on first run) and **parallel requests** (default 4)
4. Hit **开始配音** — the progress bar shows the current step and per-segment
   progress (x/y)
5. When done, the new case opens automatically: play the dubbed video with
   bilingual subtitles, click any cue to jump

Per-segment failures never abort the run — the slot keeps the original voice
(and is badged 原声 in the cue list).

## Data layout

```
demo/
├── app.py              # FastAPI server: upload/progress APIs + static + Range
├── index.html          # single-page frontend
├── case_registry.py    # case manifest (cases/manifest.json + cases/<id>.json)
├── add_case.py         # register existing dub_video.py outputs from the CLI
├── uploads/            # uploaded originals (runtime)
├── results/<job_id>/   # per-job mp4 + srt + bilingual.srt + segments.json
└── cases/              # showcase data
```

`uploads/`, `results/`, `cases/` are runtime data (gitignored); deleting them
resets the demo.

## Importing existing dub_video.py outputs

```bash
cd demo
python3 add_case.py ../out/slzz.en.segments.json slzz.en.mp4 \
    "My video (zh → en dub)" "Index S2ST 9B · 8:16 · 88 segments" \
    --tab "My video (9B)"
```

## HTTP API

| Method | Path | Description |
|---|---|---|
| GET | `/api/langs` | languages: `targets`, `sources`, `directions` |
| GET | `/api/cases` · `/api/cases/<id>` | showcase data |
| POST | `/api/dub` | multipart upload: `file`, `lang`, `src_lang` (empty = auto), `separate`, `workers` → `{job_id}`; unsupported directions get 400 |
| GET | `/api/jobs` · `/api/jobs/<id>` | job list / live progress |
| GET | `/api/healthz` | web + S2ST service health |

## Troubleshooting

- **Video plays but the seek bar doesn't** — serve via `app.py` (it supports
  HTTP Range); `python -m http.server` does not
- **Job fails immediately** — check the S2ST URL: `curl <url>/healthz`
- **demucs SSL error on macOS** — `export SSL_CERT_FILE=$(python3 -m certifi)`
- **Slow on long videos** — the reference service is single-concurrency;
  wall time ≈ segments × per-segment latency / workers. 2B is 3–5× faster
  than 9B
