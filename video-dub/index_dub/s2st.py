"""HTTP client for the Index S2ST inference service.

The service exposes POST /s2st (multipart: file=<wav>, lang=<target>) and
returns JSON: {ok, audio_b64, sr, zh, text, lang, gen_s, hit_eos}.
"""

import base64
import time

import requests

TARGET_LANGS = ("en", "es", "ja", "zh")


class S2STClient:
    def __init__(self, base_url, timeout=600, retries=2):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    def healthz(self):
        r = requests.get(f"{self.base_url}/healthz", timeout=10)
        r.raise_for_status()
        return r.json()

    def dub(self, wav_path, lang, endpoint="/s2st"):
        """Dub one wav segment; returns dict with wav bytes + metadata."""
        assert lang in TARGET_LANGS, f"unsupported lang {lang!r}: {TARGET_LANGS}"
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                with open(wav_path, "rb") as f:
                    r = requests.post(
                        f"{self.base_url}{endpoint}",
                        files={"file": ("seg.wav", f, "audio/wav")},
                        data={"lang": lang},
                        timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                if not data.get("ok"):
                    raise RuntimeError(f"service returned ok=false: {data}")
                data["_wav_bytes"] = base64.b64decode(data.pop("audio_b64"))
                return data
            except Exception as e:  # noqa: BLE001 - retry on any transient error
                last_err = e
                if attempt < self.retries:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"s2st failed after {self.retries + 1} attempts: {last_err}")
