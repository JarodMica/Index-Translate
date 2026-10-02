#!/usr/bin/env python3
"""Syllable-controlled translation with Index-Homura-2B / Index-Homura-9B via
any OpenAI-compatible server (vLLM, SGLang, ...).

Homura translates while keeping the output at (approximately) a target
syllable count — useful for dubbing / subtitling where the translation must
fit a fixed time slot. It also supports terminology / glossary enforcement
alongside syllable constraints.

Usage:
    # Standard syllable-controlled translation
    python syllable_translate.py "我们今天去看电影吧" --syllables 8

    # Syllable control + Terminology glossary enforcement
    python syllable_translate.py "我们今天去看电影吧" --syllables 7 --target en \
        --glossary "电影:cinema"

    # With 2B model
    python syllable_translate.py "..." --syllables 12 --target en \
        --model IndexTeam/Index-Homura-2B

Defaults assume:  vllm serve IndexTeam/Index-Homura-9B
"""

import argparse
import json
import os
import sys
from urllib.parse import urlparse

from openai import OpenAI


def make_client(base_url: str, api_key: str) -> OpenAI:
    """OpenAI client; handle proxies properly for local or internal servers."""
    import httpx
    host = urlparse(base_url).hostname or ""
    proxy = os.environ.get("OPENAI_PROXY") or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")

    if host in ("127.0.0.1", "localhost", "::1"):
        return OpenAI(base_url=base_url, api_key=api_key,
                      http_client=httpx.Client(trust_env=False))
    if proxy:
        return OpenAI(base_url=base_url, api_key=api_key,
                      http_client=httpx.Client(proxy=proxy, trust_env=False))
    return OpenAI(base_url=base_url, api_key=api_key)

# Same lowercase code->name table as translate.py (kept self-contained on purpose).
LANG_NAMES = {
    "en": "英语", "zh": "中文", "de": "德语", "fr": "法语", "es": "西班牙语",
    "ja": "日语", "ko": "韩语", "pt": "葡萄牙语", "ru": "俄语", "ar": "阿拉伯语",
    "it": "意大利语", "nl": "荷兰语", "pl": "波兰语", "ro": "罗马尼亚语",
    "sv": "瑞典语", "tr": "土耳其语", "hi": "印地语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ms": "马来语", "fil": "菲律宾语",
    "ukr_cyrl": "乌克兰语", "fas_arab": "波斯语", "ces_latn": "捷克语",
    "ell_grek": "希腊语", "dan_latn": "丹麦语", "hun_latn": "匈牙利语",
    "fin_latn": "芬兰语", "nob_latn": "书面挪威语", "slk_latn": "斯洛伐克语",
    "bul_cyrl": "保加利亚语",
}

DEFAULT_MODEL = "IndexTeam/Index-Homura-9B"


def parse_glossary(glossary_input: str) -> str:
    """Parse glossary input from a JSON file, a JSON string, or comma-separated pairs."""
    if not glossary_input:
        return ""
    glossary_input = glossary_input.strip()

    if os.path.isfile(glossary_input):
        try:
            with open(glossary_input, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return ", ".join(f"{k} -> {v}" for k, v in data.items())
        except Exception as e:
            sys.stderr.write(f"Warning: failed to read glossary file {glossary_input}: {e}\n")

    if glossary_input.startswith("{") and glossary_input.endswith("}"):
        try:
            data = json.loads(glossary_input)
            if isinstance(data, dict):
                return ", ".join(f"{k} -> {v}" for k, v in data.items())
        except Exception:
            pass

    pairs = []
    for item in glossary_input.replace("，", ",").split(","):
        item = item.strip()
        if not item:
            continue
        if "->" in item:
            k, v = item.split("->", 1)
            pairs.append(f"{k.strip()} -> {v.strip()}")
        elif ":" in item:
            k, v = item.split(":", 1)
            pairs.append(f"{k.strip()} -> {v.strip()}")
        elif "：" in item:
            k, v = item.split("：", 1)
            pairs.append(f"{k.strip()} -> {v.strip()}")
        else:
            pairs.append(item)
    return ", ".join(pairs)


def syl_prompt(text: str, target_lang: str, syllables: int, glossary: str = "") -> str:
    lang_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    base = f"请将以下文本翻译为{lang_name}，译文严格控制在 {syllables} 个音节。"
    if glossary:
        formatted_g = parse_glossary(glossary)
        if formatted_g:
            return f"{base}要求：严格遵守术语映射表【{formatted_g}】。直接输出翻译结果，不要进行任何解释。\n\n{text}"
    return f"{base}直接输出翻译结果，不要进行任何解释。\n\n{text}"


def strip_think(text: str) -> str:
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Syllable-controlled translation with Index-Homura models (with glossary support)")
    ap.add_argument("text", nargs="?", help="text to translate (stdin if omitted)")
    ap.add_argument("--syllables", "-n", type=int, required=True, help="target syllable count")
    ap.add_argument("--target", "-t", default="en", help="target language code (default: en)")
    ap.add_argument("--glossary", "-g", default="",
                    help="terminology glossary mapping: 'k:v, k2:v2' or JSON file path")
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
        messages=[{"role": "user", "content": syl_prompt(text, args.target, args.syllables, args.glossary)}],
        temperature=args.temperature,
        max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    print(strip_think(resp.choices[0].message.content))


if __name__ == "__main__":
    main()
