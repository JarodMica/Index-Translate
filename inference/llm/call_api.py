#!/usr/bin/env python3
"""Index-Translate Free Public API Invocation Script.

Directly call the free public Index-Translate-35B / 9B / 2B API on https://index-translate.bilibili.com/v1
Fully OpenAI-compatible endpoints with streaming SSE and instruction-following support.

Usage:
    # 1. Quick translation (defaults to 35B model, translating to English)
    python call_api.py "技术赋能创作，让交流跨越语言的界限。"

    # 2. Specify target language and model
    python call_api.py "Hello, world!" -t zh -m Index-Translate-35B-A3B

    # 3. Stream output (SSE)
    python call_api.py "今天天气真好，我们去公园散步吧。" -t ja --stream

    # 4. Instruction following / constrained translation (instTrans)
    python call_api.py '{"title": "用户协议", "version": "1.0.0"}' -t en \
        --instruction "严格保留合法 JSON 语法格式，仅翻译 value 文本"

    # 5. Terminology / glossary constraint
    python call_api.py "碳纤维的好处就是它抗裂缝。" -t en \
        --glossary "碳纤维:carbon fiber, 抗裂缝:crack resistance"

    # 6. Read from stdin
    cat document.txt | python call_api.py -t en
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_API_BASE = "https://index-translate.bilibili.com/v1"
DEFAULT_MODEL = "Index-Translate-35B-A3B"

LANG_NAMES = {
    "en": "英语", "zh": "中文", "de": "德语", "fr": "法语", "es": "西班牙语",
    "ja": "日语", "ko": "韩语", "pt": "葡萄牙语", "ru": "俄语", "ar": "阿拉伯语",
    "it": "意大利语", "nl": "荷兰语", "pl": "波兰语", "ro": "罗马尼亚语",
    "sv": "瑞典语", "tr": "土耳其语", "hi": "印地语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ms": "马来语", "fil": "菲律宾语",
}


def build_prompt(
    text: str,
    target_lang: str,
    source_lang: str = "auto",
    instruction: str = "",
    glossary: str = "",
) -> str:
    """Build standardized translation prompt matching Index-Translate instTrans template."""
    tgt_name = LANG_NAMES.get(target_lang.lower(), target_lang)
    src_name = LANG_NAMES.get(source_lang.lower(), "") if source_lang and source_lang != "auto" else ""

    constraints = []
    if instruction:
        constraints.append(f"【指令要求】{instruction.strip()}")

    if glossary:
        pairs = []
        for pair in glossary.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                pairs.append(f"{k.strip()}→{v.strip()}")
        if pairs:
            constraints.append(f"【术语干预】必须按照术语表翻译：{', '.join(pairs)}")

    if constraints:
        header = f"请将以下{src_name + ' ' if src_name else ''}文本翻译为{tgt_name}。"
        req_lines = [f"{i+1}. {c}" for i, c in enumerate(constraints)]
        return (
            f"{header}\n\n"
            f"【源文】\n{text.strip()}\n\n"
            f"【约束要求】\n{chr(10).join(req_lines)}\n\n"
            f"只输出译文，不要有任何额外说明。"
        )

    if src_name:
        return f"请将以下{src_name}文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。\n\n{text.strip()}"
    return f"请将以下文本翻译为{tgt_name}，直接输出翻译结果，不要进行任何解释。\n\n{text.strip()}"


def strip_think(text: str) -> str:
    """Strip CoT thought blocks if present."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip().removeprefix("<think>").strip()


def call_completion(
    api_base: str,
    model: str,
    prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    stream: bool = False,
):
    url = f"{api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Index-Translate-Client/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if stream:
                for line in resp:
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    body = line[6:]
                    if body == "[DONE]":
                        break
                    try:
                        chunk = json.loads(body)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            sys.stdout.write(content)
                            sys.stdout.flush()
                    except json.JSONDecodeError:
                        continue
                print()
            else:
                res = json.loads(resp.read().decode("utf-8"))
                content = res["choices"][0]["message"]["content"]
                print(strip_think(content))

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"API Error ({e.code}): {err_msg}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Request failed: {e}\n")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Call Index-Translate Public API")
    ap.add_argument("text", nargs="?", help="Text to translate (reads stdin if omitted)")
    ap.add_argument("--target", "-t", default="en", help="Target language code, e.g. en/zh/ja (default: en)")
    ap.add_argument("--source", "-s", default="auto", help="Source language code (default: auto)")
    ap.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Model identifier (default: {DEFAULT_MODEL})")
    ap.add_argument("--instruction", "-i", default="", help="Instruction or formatting constraint")
    ap.add_argument("--glossary", "-g", default="", help="Glossary pairs, e.g. 'term1:target1, term2:target2'")
    ap.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API Base URL (default: {DEFAULT_API_BASE})")
    ap.add_argument("--max-tokens", type=int, default=1024, help="Max tokens to generate (default: 1024)")
    ap.add_argument("--stream", action="store_true", help="Stream translation tokens (SSE)")

    args = ap.parse_args()
    text = args.text if args.text is not None else sys.stdin.read()
    text = text.strip()
    if not text:
        ap.error("Empty input text")

    prompt = build_prompt(
        text=text,
        target_lang=args.target,
        source_lang=args.source,
        instruction=args.instruction,
        glossary=args.glossary,
    )

    call_completion(
        api_base=args.api_base,
        model=args.model,
        prompt=prompt,
        max_tokens=args.max_tokens,
        stream=args.stream,
    )


if __name__ == "__main__":
    main()
