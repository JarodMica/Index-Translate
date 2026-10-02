#!/usr/bin/env python3
"""Translate text with Index-Translate-2B / Index-Translate-9B / Index-Translate-35B
via any OpenAI-compatible server (vLLM, SGLang, ...).

Supports standard translation as well as instruction following with hard and soft constraints:
  - Hard constraints: format preservation (JSON, CSV, markdown, code, placeholders),
    terminology / glossary enforcement.
  - Soft constraints: tone/register (formal, casual, viral social media),
    domain context and word-sense disambiguation.

Usage:
    # Standard translation
    python translate.py "你好，世界" --target en

    # Hard constraint: Terminology / Glossary enforcement
    python translate.py "碳纤维的好处就是它抗裂缝。" --target en \
        --glossary "碳纤维:carbon fiber, 抗裂缝:crack resistance"

    # Hard constraint: Structured data preservation (JSON, CSV, etc.)
    python translate.py '{"title": "用户协议", "version": "1.0.0"}' --target en \
        --instruction "仅翻译键值内容，严格保留合法 JSON 语法格式与键名"

    # Soft constraint: Style and tone adjustment
    python translate.py "今天下午的会议临时取消了，改天我们再碰一下商量。" --target en \
        --instruction "调整为严谨、正式、礼貌的商务公文风格"

    # Soft constraint: Domain context and disambiguation
    python translate.py "The plant is operating at full capacity after the spring upgrade." --target zh \
        --instruction "语境为工业制造与重工厂房领域，准确消歧专有名词"

    # Reading from stdin:
    echo "Hello world" | python translate.py --target zh

Defaults assume a local server:  vllm serve IndexTeam/Index-Translate-9B
Override with --base-url / --model, or env OPENAI_BASE_URL / INDEX_MODEL.
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


def parse_glossary(glossary_input: str) -> str:
    """Parse glossary input from a JSON file, a JSON string, or comma-separated pairs.
    Returns a standardized string like 'term1 -> target1, term2 -> target2'."""
    if not glossary_input:
        return ""
    glossary_input = glossary_input.strip()

    # Case 1: Existing JSON file
    if os.path.isfile(glossary_input):
        try:
            with open(glossary_input, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return ", ".join(f"{k} -> {v}" for k, v in data.items())
        except Exception as e:
            sys.stderr.write(f"Warning: failed to read glossary file {glossary_input}: {e}\n")

    # Case 2: JSON string format: {"term": "target"}
    if glossary_input.startswith("{") and glossary_input.endswith("}"):
        try:
            data = json.loads(glossary_input)
            if isinstance(data, dict):
                return ", ".join(f"{k} -> {v}" for k, v in data.items())
        except Exception:
            pass

    # Case 3: Delimited pairs, e.g. "term:trans, term2:trans2" or "term->trans"
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


def trans_prompt(text: str, target_lang: str, source_lang: str = "auto",
                 instruction: str = "", glossary: str = "") -> str:
    """Construct prompt matching the model's instruction-following training format.
    
    Hard constraints (e.g. glossary mappings, format preservation) and soft constraints
    (e.g. tone, style, domain disambiguation) are incorporated cleanly into the prompt.
    """
    lang_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    if source_lang and source_lang.lower() not in ("auto", ""):
        src_name = LANG_NAMES.get(source_lang.lower(), source_lang)
        prefix = f"请将以下{src_name}文本翻译为{lang_name}"
    else:
        prefix = f"请将以下文本翻译为{lang_name}"

    requirements = []
    if instruction:
        inst_clean = instruction.strip().rstrip("。")
        requirements.append(inst_clean)
    if glossary:
        formatted_g = parse_glossary(glossary)
        if formatted_g:
            requirements.append(f"严格遵守术语映射表【{formatted_g}】，严禁使用其他译名")

    if requirements:
        req_str = "。要求：" + "，".join(requirements) + "。"
        return f"{prefix}{req_str}直接输出翻译结果，不要进行任何解释。\n\n{text}"
    return f"{prefix}，直接输出翻译结果，不要进行任何解释。\n\n{text}"


def strip_think(text: str) -> str:
    """Safety net: drop a <think>...</think> block if the model emits one."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Translate text with Index-Translate models (with instruction following support)")
    ap.add_argument("text", nargs="?", help="text to translate (stdin if omitted)")
    ap.add_argument("--target", "-t", default="en", help="target language code, e.g. en/zh/ja (default: en)")
    ap.add_argument("--source", "-s", default="auto", help="source language code (default: auto)")
    ap.add_argument("--instruction", "-i", default="",
                    help="task instruction or constraint (e.g. style, format preservation, domain context)")
    ap.add_argument("--glossary", "-g", default="",
                    help="terminology glossary mapping: 'k:v, k2:v2' or JSON file path")
    ap.add_argument("--raw-prompt", action="store_true",
                    help="send input text directly as raw prompt without template wrapping")
    ap.add_argument("--model", "-m", default=os.environ.get("INDEX_MODEL", DEFAULT_MODEL))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "EMPTY"))
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    text = text.strip()
    if not text:
        ap.error("empty input text")

    if args.raw_prompt:
        prompt_content = text
    else:
        prompt_content = trans_prompt(
            text=text,
            target_lang=args.target,
            source_lang=args.source,
            instruction=args.instruction,
            glossary=args.glossary,
        )

    client = make_client(args.base_url, args.api_key)
    resp = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": prompt_content}],
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    print(strip_think(resp.choices[0].message.content))


if __name__ == "__main__":
    main()
