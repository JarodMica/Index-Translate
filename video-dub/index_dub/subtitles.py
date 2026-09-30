"""SRT subtitle export from segment timestamps + translations."""


def _fmt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path, spans, texts):
    with open(path, "w", encoding="utf-8") as f:
        for i, ((s, e), text) in enumerate(zip(spans, texts), 1):
            f.write(f"{i}\n{_fmt(s)} --> {_fmt(e)}\n{text.strip()}\n\n")


def write_bilingual_srt(path, spans, sources, translations):
    """Write a bilingual SRT: original line on top (dim), translation below (highlighted)."""
    with open(path, "w", encoding="utf-8") as f:
        for i, ((s, e), src, tgt) in enumerate(zip(spans, sources, translations), 1):
            src_line = (src or "").strip() or "(no source transcription)"
            tgt_line = (tgt or "").strip()
            f.write(f"{i}\n{_fmt(s)} --> {_fmt(e)}\n{src_line}\n{tgt_line}\n\n")
