"""Shared case registry for the demo web app.

A "case" is one dubbed video: its segments data lives at cases/<id>.json and
the manifest at cases/manifest.json. Registering is idempotent per id and
never removes other cases.
"""
import json
import os


def _cases_dir(demo_dir):
    d = os.path.join(demo_dir, "cases")
    os.makedirs(d, exist_ok=True)
    return d


def register_case(demo_dir, case_id, meta, segments, tab=None):
    """Write cases/<case_id>.json and add it to the manifest.

    meta: {"video": "<path relative to demo dir>", "title": ..., "meta": ...}
    segments: [{"start", "end", "src", "text", "kept"?}]
    Returns the number of registered cases.
    """
    cdir = _cases_dir(demo_dir)
    with open(os.path.join(cdir, f"{case_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "segments": segments}, f, ensure_ascii=False, indent=1)

    manifest_path = os.path.join(cdir, "manifest.json")
    cases = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                cases = json.load(f)
        except Exception:
            cases = []
    cases = [c for c in cases if c.get("id") != case_id]
    cases.append({"id": case_id, "tab": tab or meta.get("title", case_id)})
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=1)
    return len(cases)


def list_cases(demo_dir):
    manifest_path = os.path.join(_cases_dir(demo_dir), "manifest.json")
    if not os.path.exists(manifest_path):
        return []
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def load_case(demo_dir, case_id):
    if "/" in case_id or ".." in case_id:
        return None
    path = os.path.join(_cases_dir(demo_dir), f"{case_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
