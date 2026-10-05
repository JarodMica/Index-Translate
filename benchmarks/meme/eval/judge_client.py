"""OpenAI-compatible Judge client with a durable append-only cache."""

from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from pathlib import Path
from typing import Any

JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 2048


class JudgeRequestError(RuntimeError):
    pass


class _EmptyJudgeResponseError(JudgeRequestError):
    """Raised when a provider returns no usable completion text for a judgement."""


class JudgeClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        prompt_version: str,
        cache_path: Path,
        timeout: float = 360.0,
        max_attempts: int = 6,
    ) -> None:
        if not api_key:
            raise ValueError("JUDGE_API_KEY is required")
        from openai import OpenAI

        self.model = model
        self.base_url = base_url
        self.prompt_version = prompt_version
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        self._load_cache()

    def _key(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                # The provider endpoint is part of the judgement identity: the same
                # prompt answered by a different backend is not the same cached result.
                "base_url": self.base_url,
                "prompt_version": self.prompt_version,
                "temperature": JUDGE_TEMPERATURE,
                "max_tokens": JUDGE_MAX_TOKENS,
                "prompt": prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_cache(self) -> None:
        if not self.cache_path.is_file():
            return
        with self.cache_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    self._cache[record["key"]] = record["response"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    # An interrupted final append must not destroy earlier cache entries.
                    # Skip the damaged line and keep every readable entry around it.
                    continue

    def _cache_put(self, key: str, response: str) -> None:
        with self._lock:
            if key in self._cache:
                return
            self._cache[key] = response
            with self.cache_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"key": key, "response": response}, ensure_ascii=False))
                handle.write("\n")
                handle.flush()

    def complete(self, prompt: str) -> tuple[str, bool]:
        key = self._key(prompt)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached, True

        error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=JUDGE_TEMPERATURE,
                    max_tokens=JUDGE_MAX_TOKENS,
                )
                content = response.choices[0].message.content
                if not isinstance(content, str) or not content.strip():
                    # A content filter (or a reasoning-only reply) yields no judgement.
                    # Never cache it and never score it: retry, then fail loudly.
                    raise _EmptyJudgeResponseError("judge returned an empty response")
                self._cache_put(key, content)
                return content, False
            except Exception as exc:
                error = exc
                status_code = getattr(exc, "status_code", None)
                retryable = status_code == 429 or (
                    isinstance(status_code, int) and 500 <= status_code < 600
                )
                # Connection/transport failures usually have no HTTP status.
                if status_code is None:
                    retryable = True
                if retryable and attempt + 1 < self.max_attempts:
                    time.sleep(min(2 ** (attempt + 1), 60) + random.uniform(0, 1))
                    continue
                break
        raise JudgeRequestError(
            f"Judge request failed after {self.max_attempts} attempts: {error}"
        ) from error

    @property
    def cache_entries(self) -> int:
        return len(self._cache)
