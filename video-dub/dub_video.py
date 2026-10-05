#!/usr/bin/env python3
"""Dub a video into another language with the Index S2ST service.

Pipeline: mp4 -> extract audio -> [optional vocal separation] -> VAD
segmentation (with timestamps) -> per-segment S2ST dubbing -> timeline
assembly -> mux back into the video.

Example:
    python dub_video.py input.mp4 --lang en --s2st-url http://127.0.0.1:8094
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

import soundfile as sf

from index_dub import media, segment, separate, s2st, subtitles, timeline


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="input video (mp4) or audio file")
    ap.add_argument("-l", "--lang", required=True, choices=s2st.TARGET_LANGS,
                    help="target language (source is auto-detected: zh/en)")
    ap.add_argument("-o", "--output", help="output mp4 (default: <input>.<lang>.mp4)")
    ap.add_argument("--s2st-url", default=os.environ.get("S2ST_URL",
                                                         "http://127.0.0.1:8094"),
                    help="base URL of the S2ST service (env S2ST_URL)")
    ap.add_argument("--endpoint", default="/s2st",
                    help="service endpoint (/s2st for audio out, /s2tt for text only)")
    ap.add_argument("--max-seg", type=float, default=9.5,
                    help="max segment duration in seconds (default: 9.5; the "
                         "reference service rejects audio longer than ~10.5s)")
    ap.add_argument("--max-stretch", type=float, default=1.5,
                    help="max time-stretch factor to fit a dub into its slot")
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel S2ST requests (server may still serialize "
                         "GPU inference; parallelism hides network latency)")
    ap.add_argument("--vad", default="auto", choices=["auto", "silero", "ffmpeg"],
                    help="segmentation backend")
    ap.add_argument("--separate", dest="separate", action="store_true",
                    default=True,
                    help="separate vocals with demucs first and keep the "
                         "instrumental under the dub (default: on)")
    ap.add_argument("--no-separate", dest="separate", action="store_false",
                    help="skip vocal separation (faster; fine for clean speech)")
    ap.add_argument("--no-bgm", action="store_true",
                    help="with --separate: drop the instrumental instead of mixing it back")
    ap.add_argument("--srt", action="store_true",
                    help="also export translated subtitles as <output>.srt "
                         "(and <output>.bilingual.srt when source text is available)")
    ap.add_argument("--speech-wav",
                    help="reuse an existing 16kHz speech wav and skip audio "
                         "extraction + vocal separation (e.g. vocals16k.wav "
                         "from an earlier --keep-temp run)")
    ap.add_argument("--instr-wav",
                    help="instrumental wav mixed back under the dub "
                         "(only meaningful with --speech-wav)")
    ap.add_argument("--keep-temp", action="store_true",
                    help="keep the temp working directory")
    args = ap.parse_args()

    if args.max_seg <= 0:
        # <= 0 would make the segmenter split forever trying to fit a slot
        ap.error(f"--max-seg must be greater than 0 seconds (got {args.max_seg})")

    out_mp4 = args.output or os.path.splitext(args.input)[0] + f".{args.lang}.mp4"
    tmp = tempfile.mkdtemp(prefix="index_dub_")
    print(f"[1/6] workdir: {tmp}")

    try:
        # 1+2. extract audio and separate vocals (or reuse a previous run's stems)
        if args.speech_wav:
            speech_wav, instr_wav = args.speech_wav, args.instr_wav
            total_dur = media.probe_duration(args.input)
            print(f"[1-2/6] reusing speech track: {speech_wav}")
            print(f"      duration: {total_dur:.1f}s")
        else:
            # 1. extract audio (16k mono for VAD + S2ST input)
            full_wav = os.path.join(tmp, "audio16k.wav")
            media.extract_audio(args.input, full_wav, sr=16000)
            total_dur = media.probe_duration(args.input)
            print(f"      duration: {total_dur:.1f}s")

            # 2. vocal separation (default on; gracefully degrade if demucs missing)
            speech_wav, instr_wav = full_wav, None
            if args.separate:
                try:
                    print("[2/6] separating vocals (demucs) ...")
                    vocals, instr = separate.separate_vocals(full_wav, os.path.join(tmp, "demucs"))
                    speech_wav = os.path.join(tmp, "vocals16k.wav")
                    media.run(["ffmpeg", "-y", "-i", vocals, "-ac", "1", "-ar", "16000",
                               "-c:a", "pcm_s16le", speech_wav])
                    if not args.no_bgm:
                        instr_wav = instr
                except RuntimeError as e:
                    print(f"[2/6] vocal separation unavailable ({e}); using raw audio")
            else:
                print("[2/6] vocal separation disabled (--no-separate)")

        # 3. segmentation with timestamps
        spans = segment.segment_audio(speech_wav, backend=args.vad, max_dur=args.max_seg)
        if not spans:
            sys.exit("[3/6] no speech detected, nothing to dub")
        print(f"[3/6] {len(spans)} segments: " +
              ", ".join(f"{s:.1f}-{e:.1f}" for s, e in spans[:8]) +
              (" ..." if len(spans) > 8 else ""))

        # 4. per-segment S2ST dubbing
        client = s2st.S2STClient(args.s2st_url)
        print(f"[4/6] dubbing via {args.s2st_url}{args.endpoint} (lang={args.lang})")
        print(f"      service healthz: {client.healthz()}")
        seg_dir = os.path.join(tmp, "segs")
        os.makedirs(seg_dir, exist_ok=True)
        dub_wavs, translations, sources = [None] * len(spans), [None] * len(spans), [None] * len(spans)
        failed_segs = []

        def dub_one(i, s, e):
            seg_in = os.path.join(seg_dir, f"in_{i:04d}.wav")
            media.extract_segment(speech_wav, seg_in, s, e)
            try:
                r = client.dub(seg_in, args.lang, endpoint=args.endpoint)
            except RuntimeError as err:
                print(f"      [{i + 1}/{len(spans)}] {s:.1f}-{e:.1f}s FAILED, "
                      f"keeping original audio: {err}", flush=True)
                dub_wavs[i] = seg_in  # fall back to the original voice
                translations[i] = ""
                sources[i] = ""
                failed_segs.append(i)
                return
            wav_bytes = r.get("_wav_bytes")
            if wav_bytes is None:
                # text-only endpoint (/s2tt): no audio came back; keep the original
                # voice in the slot but still record the translation (for --srt).
                dub_wavs[i] = seg_in
                translations[i] = r.get("text", "")
                sources[i] = r.get("zh", "")
                print(f"      [{i + 1}/{len(spans)}] {s:.1f}-{e:.1f}s "
                      f"text-only response, original audio kept | "
                      f"{str(r.get('zh', ''))[:40]} -> {str(r.get('text', ''))[:40]}",
                      flush=True)
                return
            seg_out = os.path.join(seg_dir, f"out_{i:04d}.wav")
            with open(seg_out, "wb") as f:
                f.write(wav_bytes)
            dub_wavs[i] = seg_out
            translations[i] = r.get("text", "")
            sources[i] = r.get("zh", "")
            print(f"      [{i + 1}/{len(spans)}] {s:.1f}-{e:.1f}s "
                  f"gen={r.get('gen_s', '?')}s | {str(r.get('zh', ''))[:40]} -> "
                  f"{str(r.get('text', ''))[:40]}", flush=True)

        if args.workers <= 1:
            for i, (s, e) in enumerate(spans):
                dub_one(i, s, e)
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futs = [pool.submit(dub_one, i, s, e)
                        for i, (s, e) in enumerate(spans)]
                for f in futs:  # surface unexpected bugs; per-seg failures are caught inside
                    f.result()
        if failed_segs:
            print(f"      {len(failed_segs)}/{len(spans)} segments failed and fell back to original voice")

        # 5. timeline assembly
        print("[5/6] assembling dubbed timeline ...")
        track, sr = timeline.build_track(spans, dub_wavs, total_dur, tmp,
                                         sr=24000, max_stretch=args.max_stretch)
        dub_track = os.path.join(tmp, "dub_track.wav")
        sf.write(dub_track, track, sr, subtype="PCM_16")
        if instr_wav:
            mixed = os.path.join(tmp, "final_track.wav")
            media.mix_audio(instr_wav, dub_track, mixed, base_vol=0.9, over_vol=1.0, sr=sr)
            dub_track = mixed

        # 6. mux
        media.mux_video_audio(args.input, dub_track, out_mp4)
        print(f"[6/6] wrote {out_mp4}")

        if args.srt:
            ok = [(sp, src, t) for sp, src, t in zip(spans, sources, translations) if t]
            srt_path = os.path.splitext(out_mp4)[0] + ".srt"
            subtitles.write_srt(srt_path, [sp for sp, _, _ in ok],
                                [t for _, _, t in ok])
            print(f"      wrote {srt_path}")
            if any(src for _, src, _ in ok):
                bilingual_srt = os.path.splitext(out_mp4)[0] + ".bilingual.srt"
                subtitles.write_bilingual_srt(bilingual_srt, [sp for sp, _, _ in ok],
                                              [src for _, src, _ in ok],
                                              [t for _, _, t in ok])
                print(f"      wrote {bilingual_srt}")

        manifest = os.path.join(os.path.dirname(out_mp4) or ".",
                                os.path.splitext(os.path.basename(out_mp4))[0] + ".segments.json")
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump([{"start": s, "end": e, "src": src, "text": t}
                       for (s, e), src, t in zip(spans, sources, translations)],
                      f, ensure_ascii=False, indent=1)
        print(f"      wrote {manifest}")
    finally:
        # every exit path (early sys.exit, exception, success) cleans up;
        # --keep-temp still keeps the workdir for re-runs with --speech-wav
        if args.keep_temp:
            print(f"      temp kept at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
