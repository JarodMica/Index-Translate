#!/usr/bin/env python3
"""Syllable-controlled translation with Index-Homura-2B / Index-Homura-9B via
any OpenAI-compatible server (vLLM, SGLang, ...).

Homura translates while keeping the output at (approximately) a target
syllable count — useful for dubbing / subtitling where the translation must
fit a fixed time slot.

Usage:
    python syllable_translate.py "我们今天去看电影吧" --syllables 8
    python syllable_translate.py "..." --syllables 12 --target en \
        --model IndexTeam/Index-Homura-2B

Defaults assume:  vllm serve IndexTeam/Index-Homura-9B
"""

import argparse
import os
import sys
from urllib.parse import urlparse

from openai import OpenAI


def make_client(base_url: str, api_key: str) -> OpenAI:
    """OpenAI client; bypass env/system proxies for local servers."""
    host = urlparse(base_url).hostname or ""
    if host in ("127.0.0.1", "localhost", "::1"):
        import httpx
        return OpenAI(base_url=base_url, api_key=api_key,
                      http_client=httpx.Client(trust_env=False))
    return OpenAI(base_url=base_url, api_key=api_key)

# Same code->name table as translate.py (kept self-contained on purpose).
LANG_NAMES = {
    "en": "英语", "zh": "中文", "de": "德语", "fr": "法语", "es": "西班牙语",
    "ja": "日语", "ko": "韩语", "pt": "葡萄牙语", "ru": "俄语", "ar": "阿拉伯语",
    "it": "意大利语", "nl": "荷兰语", "pl": "波兰语", "ro": "罗马尼亚语",
    "sv": "瑞典语", "tr": "土耳其语", "hi": "印地语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ms": "马来语", "fil": "菲律宾语",
}

DEFAULT_MODEL = "IndexTeam/Index-Homura-9B"


def syl_prompt(text: str, target_lang: str, syllables: int) -> str:
    lang_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    return (f"请将以下文本翻译为{lang_name}，译文严格控制在 {syllables} 个音节。"
            f"直接输出翻译结果，不要进行任何解释。\n\n{text}")


def strip_think(text: str) -> str:
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Syllable-controlled translation with Index-Homura models")
    ap.add_argument("text", nargs="?", help="text to translate (stdin if omitted)")
    ap.add_argument("--syllables", "-n", type=int, required=True, help="target syllable count")
    ap.add_argument("--target", "-t", default="en", help="target language code (default: en)")
    ap.add_argument("--model", "-m", default=os.environ.get("INDEX_MODEL", DEFAULT_MODEL))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "EMPTY"))
    ap.add_argument("--max-tokens", type=int, default=0, help="0 = max(512, 3 * len(text))")
    ap.add_argument("--temperature", type=float, default=0.3)
    args = ap.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    text = text.strip()
    if not text:
        ap.error("empty input text")

    max_tokens = args.max_tokens if args.max_tokens > 0 else max(512, len(text) * 3)
    client = make_client(args.base_url, args.api_key)
    resp = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": syl_prompt(text, args.target, args.syllables)}],
        temperature=args.temperature,
        max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    print(strip_think(resp.choices[0].message.content))


if __name__ == "__main__":
    main()
