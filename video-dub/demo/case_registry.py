"""Shared case registry for the demo web app.

A "case" is one dubbed video: its segments data lives at cases/<id>.json and
the manifest at cases/manifest.json. Registering is idempotent per id and
never removes other cases.

Writes go through a process-wide lock plus a temp-file + ``os.replace`` swap,
so concurrent pipeline threads (and the reader endpoints) can never observe a
half-written manifest or lose each other's cases.
"""
import json
import os
import tempfile
import threading

_LOCK = threading.RLock()


def _cases_dir(demo_dir):
    d = os.path.join(demo_dir, "cases")
    os.makedirs(d, exist_ok=True)
    return d


def _write_json(path, obj):
    """Atomically replace ``path`` with ``obj`` serialized as JSON."""
    d = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def register_case(demo_dir, case_id, meta, segments, tab=None):
    """Write cases/<case_id>.json and add it to the manifest.

    meta: {"video": "<path relative to demo dir>", "title": ..., "meta": ...}
    segments: [{"start", "end", "src", "text", "kept"?}]
    Returns the number of registered cases.
    """
    cdir = _cases_dir(demo_dir)
    manifest_path = os.path.join(cdir, "manifest.json")
    # the whole read-modify-write of the manifest is serialized: two jobs
    # finishing at the same time must not overwrite each other's entry
    with _LOCK:
        _write_json(os.path.join(cdir, f"{case_id}.json"),
                    {"meta": meta, "segments": segments})

        cases = []
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    cases = json.load(f)
            except Exception:
                cases = []
        if not isinstance(cases, list):
            cases = []
        cases = [c for c in cases if c.get("id") != case_id]
        cases.append({"id": case_id, "tab": tab or meta.get("title", case_id)})
        _write_json(manifest_path, cases)
        return len(cases)


def list_cases(demo_dir):
    manifest_path = os.path.join(_cases_dir(demo_dir), "manifest.json")
    if not os.path.exists(manifest_path):
        return []
    try:
        with _LOCK:  # keep readers off a manifest mid-swap (Windows os.replace)
            with open(manifest_path, encoding="utf-8") as f:
                cases = json.load(f)
    except Exception:
        return []
    return cases if isinstance(cases, list) else []


def load_case(demo_dir, case_id):
    if "/" in case_id or ".." in case_id or "\\" in case_id:
        return None
    path = os.path.join(_cases_dir(demo_dir), f"{case_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with _LOCK:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None
