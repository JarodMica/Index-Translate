#!/usr/bin/env python3
"""Register an already-dubbed video as a case on the demo page (CLI).

Usage (from the demo directory):
  python3 add_case.py <segments.json> <video.mp4> <title> <meta> [--tab LABEL] [--en-trans en_trans.json]

en_trans.json (optional): {index: {"src_en": ...}} for segments that kept
their original audio (rendered with a 原声 badge).
"""
import argparse
import json
import os

from case_registry import register_case

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("segments_json")
    ap.add_argument("video", help="video path; use a path relative to the demo "
                                "dir (e.g. results/<id>/xxx.en.mp4) or a bare "
                                "filename for a file at the demo root")
    ap.add_argument("title")
    ap.add_argument("meta")
    ap.add_argument("--tab", help="tab label (default: title)")
    ap.add_argument("--en-trans", help="json of {index: {src_en}} for kept-original segments")
    args = ap.parse_args()

    en_trans = {}
    if args.en_trans:
        with open(args.en_trans, encoding="utf-8") as f:
            en_trans = {int(k): v for k, v in json.load(f).items()}

    with open(args.segments_json, encoding="utf-8") as f:
        segs = json.load(f)

    segments = []
    for i, s in enumerate(segs):
        entry = {"start": s["start"], "end": s["end"],
                 "src": s.get("src", ""), "text": s.get("text", "")}
        if not entry["text"].strip() and en_trans.get(i, {}).get("src_en"):
            entry = {"start": s["start"], "end": s["end"],
                     "src": en_trans[i]["src_en"], "text": en_trans[i]["src_en"],
                     "kept": True}
        segments.append(entry)

    video_rel = os.path.relpath(args.video, DEMO_DIR) if os.path.isabs(args.video) else args.video
    case_id = os.path.splitext(os.path.basename(args.video))[0]
    n = register_case(DEMO_DIR, case_id,
                      {"video": video_rel, "title": args.title, "meta": args.meta},
                      segments, tab=args.tab)
    kept = sum(1 for s in segments if s.get("kept"))
    print(f"registered case {case_id!r}: {len(segments)} segments ({kept} kept-original); "
          f"manifest now has {n} case(s)")


if __name__ == "__main__":
    main()
