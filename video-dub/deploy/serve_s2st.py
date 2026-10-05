#!/usr/bin/env python3
"""Standalone S2ST inference service for the index-dub workflow.

Wraps the official DubbingBridgeModel export package (ST LM + Hidden2CV
mapper + CosyVoice3 in one directory) behind the same HTTP API the client
expects:

    GET  /healthz          -> {"ok": true, "langs": [...]}
    POST /s2st             multipart: file=<audio>, lang=<en|es|ja|zh>
                           -> {"ok", "audio_b64", "sr", "zh", "text", ...}
    POST /s2tt             same input, text translation only

Usage:
    python serve_s2st.py --model-dir /path/to/dubbing_fulldir_cv3 \
        --port 8094 --device cuda:0

Single GPU, single concurrency (a global lock serializes requests).
"""

import argparse
import base64
import os
import subprocess
import sys
import tempfile
import threading
import traceback

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

LANGS = ("en", "es", "ja", "zh")
S2ST_MAX_S = 10.5   # S2ST generation is capped; longer audio is rejected
S2TT_MAX_S = 60.0
MAX_UPLOAD_BYTES = 100 * 1024 * 1024   # reject bigger uploads before buffering


class PayloadTooLarge(Exception):
    """Upload over MAX_UPLOAD_BYTES; surfaced as HTTP 413."""


def to_wav16k(raw: bytes, suffix: str) -> str:
    suffix = suffix if suffix and len(suffix) <= 8 else ".bin"
    fd, src = tempfile.mkstemp(prefix="s2s_in_", suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    out = src + ".16k.wav"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                        "-ac", "1", "-ar", "16000", out],
                       capture_output=True, text=True)
    os.unlink(src)
    if r.returncode != 0:
        raise RuntimeError("audio decode failed: " + (r.stderr or "")[-200:])
    return out


def wav_duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def build_app(model_dir, device=None):
    if device:
        # the flag must win over an inherited CUDA_VISIBLE_DEVICES (setdefault
        # would silently ignore --device); warn when it overrides a different one
        prev = os.environ.get("CUDA_VISIBLE_DEVICES")
        if prev is not None and prev != str(device):
            print(f"[serve_s2st] --device {device} overrides the existing "
                  f"CUDA_VISIBLE_DEVICES={prev}", flush=True)
        os.environ["CUDA_VISIBLE_DEVICES"] = str(device)
    sys.path.insert(0, model_dir)

    from fastapi import FastAPI, UploadFile, Form
    from fastapi.responses import JSONResponse

    from modeling_dubbing import DubbingBridgeModel

    print(f"[serve_s2st] loading model from {model_dir} ...", flush=True)
    model = DubbingBridgeModel.from_pretrained(model_dir)
    print("[serve_s2st] model loaded", flush=True)

    lock = threading.Lock()
    app = FastAPI(title="index-dub-s2st")

    @app.middleware("http")
    async def reject_oversized(request, call_next):
        # pre-check the declared body size: the multipart parser would otherwise
        # spool the whole upload to disk before any handler runs
        declared = request.headers.get("content-length")
        if declared:
            try:
                too_big = int(declared) > MAX_UPLOAD_BYTES
            except ValueError:
                too_big = False
            if too_big:
                return JSONResponse(
                    {"ok": False, "error": f"upload exceeds "
                     f"{MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit"}, 413)
        return await call_next(request)

    async def read_audio(file: UploadFile):
        raw = await file.read()
        if not raw:
            raise RuntimeError("empty file")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise PayloadTooLarge(
                f"file too large (>{MAX_UPLOAD_BYTES // (1024 * 1024)}MB)")
        src = to_wav16k(raw, os.path.splitext(file.filename or "")[1])
        return src, wav_duration(src)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "langs": list(LANGS)}

    @app.post("/s2tt")
    async def s2tt(file: UploadFile, lang: str = Form("en")):
        if lang not in LANGS:
            return JSONResponse({"ok": False, "error": f"lang must be one of {LANGS}"}, 400)
        src = None
        try:
            src, d = await read_audio(file)
            if d > S2TT_MAX_S:
                return JSONResponse(
                    {"ok": False, "error": f"audio {d:.1f}s exceeds {S2TT_MAX_S:.0f}s limit"}, 400)
            with lock:
                ext = model._pipe.extract(src, lang=lang)
            return {"ok": True, "zh": ext["zh"], "text": ext["tgt_raw"],
                    "lang": lang, "dur": round(d, 2)}
        except AssertionError as e:
            return JSONResponse({"ok": False, "error": f"nothing translated: {e}"}, 422)
        except PayloadTooLarge as e:
            return JSONResponse({"ok": False, "error": str(e)}, 413)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return JSONResponse({"ok": False, "error": str(e)[-400:]}, 500)
        finally:
            if src and os.path.exists(src):
                os.unlink(src)

    @app.post("/s2st")
    async def s2st(file: UploadFile, lang: str = Form("en")):
        if lang not in LANGS:
            return JSONResponse({"ok": False, "error": f"lang must be one of {LANGS}"}, 400)
        src = out = None
        try:
            src, d = await read_audio(file)
            if d > S2ST_MAX_S:
                return JSONResponse(
                    {"ok": False, "error": f"audio {d:.1f}s exceeds {S2ST_MAX_S:.0f}s limit"}, 400)
            fd, out = tempfile.mkstemp(prefix="s2s_out_", suffix=".wav")
            os.close(fd)
            with lock:
                w, sr, info = model.dub(src, lang=lang, out_wav=out, return_info=True)
            with open(out, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            return {"ok": True, "audio_b64": audio_b64, "sr": sr,
                    "zh": info.get("zh", ""), "text": info.get("tgt_raw", ""),
                    "lang": lang, "gen_s": info.get("gen_s"),
                    "hit_eos": info.get("hit_eos")}
        except AssertionError as e:
            return JSONResponse({"ok": False, "error": f"nothing translated: {e}"}, 422)
        except PayloadTooLarge as e:
            return JSONResponse({"ok": False, "error": str(e)}, 413)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return JSONResponse({"ok": False, "error": str(e)[-400:]}, 500)
        finally:
            for p in (src, out):
                if p and os.path.exists(p):
                    os.unlink(p)

    return app


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", required=True,
                    help="path to the DubbingBridgeModel export directory")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8094)
    ap.add_argument("--device", default=None,
                    help="GPU index for CUDA_VISIBLE_DEVICES, e.g. 0 "
                         "(overrides an inherited CUDA_VISIBLE_DEVICES)")
    args = ap.parse_args()

    import uvicorn
    app = build_app(args.model_dir, device=args.device)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
