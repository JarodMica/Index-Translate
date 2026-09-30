#!/usr/bin/env python3
"""Translate text with Index-Translate-2B / Index-Translate-9B via any
OpenAI-compatible server (vLLM, SGLang, ...).

Usage:
    python translate.py "你好，世界" --target en
    echo "Hello world" | python translate.py --target zh
    python translate.py "..." --target ja --model IndexTeam/Index-Translate-2B

Defaults assume a local server:  vllm serve IndexTeam/Index-Translate-9B
Override with --base-url / --model, or env OPENAI_BASE_URL / INDEX_MODEL.
"""

import argparse
import os
import sys
from urllib.parse import urlparse

from openai import OpenAI


def make_client(base_url: str, api_key: str) -> OpenAI:
    """OpenAI client; bypass env/system proxies for local servers (a system-wide
    proxy would otherwise swallow http://127.0.0.1 traffic)."""
    host = urlparse(base_url).hostname or ""
    if host in ("127.0.0.1", "localhost", "::1"):
        import httpx
        return OpenAI(base_url=base_url, api_key=api_key,
                      http_client=httpx.Client(trust_env=False))
    return OpenAI(base_url=base_url, api_key=api_key)

# Language code -> Chinese name, as used by the training-side prompt builder.
LANG_NAMES = {
    "en": "英语", "zh": "中文", "de": "德语", "fr": "法语", "es": "西班牙语",
    "ja": "日语", "ko": "韩语", "pt": "葡萄牙语", "ru": "俄语", "ar": "阿拉伯语",
    "it": "意大利语", "nl": "荷兰语", "pl": "波兰语", "ro": "罗马尼亚语",
    "sv": "瑞典语", "tr": "土耳其语", "hi": "印地语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ms": "马来语", "fil": "菲律宾语",
    "ukr_Cyrl": "乌克兰语", "fas_Arab": "波斯语", "ces_Latn": "捷克语",
    "ell_Grek": "希腊语", "dan_Latn": "丹麦语", "hun_Latn": "匈牙利语",
    "fin_Latn": "芬兰语", "nob_Latn": "书面挪威语", "slk_Latn": "斯洛伐克语",
    "bul_Cyrl": "保加利亚语",
}

DEFAULT_MODEL = "IndexTeam/Index-Translate-9B"


def trans_prompt(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Same prompt as training: 请将以下{source}文本翻译为{target},直接输出翻译结果。"""
    lang_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    if source_lang and source_lang.lower() not in ("auto", ""):
        src_name = LANG_NAMES.get(source_lang.lower(), source_lang)
        return f"请将以下{src_name}文本翻译为{lang_name}，直接输出翻译结果，不要进行任何解释。\n\n{text}"
    return f"请将以下文本翻译为{lang_name}，直接输出翻译结果，不要进行任何解释。\n\n{text}"


def strip_think(text: str) -> str:
    """Safety net: drop a <think>...</think> block if the model emits one."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Translate text with Index-Translate models")
    ap.add_argument("text", nargs="?", help="text to translate (stdin if omitted)")
    ap.add_argument("--target", "-t", default="en", help="target language code, e.g. en/zh/ja (default: en)")
    ap.add_argument("--source", "-s", default="auto", help="source language code (default: auto)")
    ap.add_argument("--model", "-m", default=os.environ.get("INDEX_MODEL", DEFAULT_MODEL))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "EMPTY"))
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.3)
    args = ap.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    text = text.strip()
    if not text:
        ap.error("empty input text")

    client = make_client(args.base_url, args.api_key)
    resp = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": trans_prompt(text, args.target, args.source)}],
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    print(strip_think(resp.choices[0].message.content))


if __name__ == "__main__":
    main()
