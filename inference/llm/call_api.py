#!/usr/bin/env python3
"""Index-Translate Free Public API Invocation Script.

Directly call the free public Index-Translate API on https://index-translate.bilibili.com/v1.

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

    # 7. Start local OpenAI-compatible bridge proxy (e.g. for Immersive Translate / 沉浸式翻译)
    python call_api.py --serve
"""

import argparse
import http.server
import json
import os
import sys
import time
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


def run_proxy_server(port: int = 8080, api_base: str = DEFAULT_API_BASE):
    """Run lightweight OpenAI-compatible local proxy server for browser extensions like Immersive Translate."""

    class ProxyHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {args[0]} {args[1]}\n")

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Max-Age", "86400")
            self.end_headers()

        def do_GET(self):
            if self.path in ("/v1/models", "/models"):
                body = json.dumps({
                    "object": "list",
                    "data": [
                        {"id": "Index-Translate-35B-A3B", "object": "model"},
                        {"id": "Index-Translate-2B", "object": "model"},
                        {"id": "Index-Translate-9B", "object": "model"},
                    ],
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Index-Translate Proxy Ready\n")

        def do_POST(self):
            if not (self.path.endswith("/chat/completions") or self.path.endswith("/completions")):
                self.send_response(404)
                self.end_headers()
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Ensure enable_thinking=False is sent by default to prevent CoT reasoning from replacing translation text
            try:
                payload = json.loads(body.decode("utf-8"))
                if "chat_template_kwargs" not in payload or not isinstance(payload.get("chat_template_kwargs"), dict):
                    payload["chat_template_kwargs"] = {}
                if "enable_thinking" not in payload["chat_template_kwargs"]:
                    payload["chat_template_kwargs"]["enable_thinking"] = False
                body = json.dumps(payload).encode("utf-8")
            except Exception:
                pass

            upstream_url = f"{api_base.rstrip('/')}/chat/completions"
            req = urllib.request.Request(
                upstream_url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Index-Translate-Client/1.0",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    self.send_response(resp.status)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    for k, v in resp.headers.items():
                        if k.lower() in ("content-type", "cache-control"):
                            self.send_header(k, v)
                    self.end_headers()

                    while True:
                        chunk = resp.read(1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except urllib.error.HTTPError as e:
                err_data = e.read()
                self.send_response(e.code)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err_data)
            except Exception as e:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), ProxyHandler)
    print("=" * 60)
    print(f"Index-Translate Local Proxy started on http://127.0.0.1:{port}/v1")
    print(f"Upstream API: {api_base}")
    print()
    print("沉浸式翻译 (Immersive Translate) 配置指南:")
    print("  1. 翻译服务选择: 自定义 (OpenAI 兼容)")
    print(f"  2. 接口地址 (API URL): http://127.0.0.1:{port}/v1")
    print("  3. 模型 (Model): Index-Translate-35B-A3B")
    print("  4. API Key: 随意填写 (如 index)")
    print("=" * 60, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping proxy...")
        server.server_close()


def main():
    ap = argparse.ArgumentParser(description="Call Index-Translate Free Public API")
    ap.add_argument("text", nargs="?", help="Text to translate (reads stdin if omitted)")
    ap.add_argument("--target", "-t", default="en", help="Target language code, e.g. en/zh/ja (default: en)")
    ap.add_argument("--source", "-s", default="auto", help="Source language code (default: auto)")
    ap.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Model identifier (default: {DEFAULT_MODEL})")
    ap.add_argument("--instruction", "-i", default="", help="Instruction or formatting constraint")
    ap.add_argument("--glossary", "-g", default="", help="Glossary pairs, e.g. 'term1:target1, term2:target2'")
    ap.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API Base URL (default: {DEFAULT_API_BASE})")
    ap.add_argument("--max-tokens", type=int, default=1024, help="Max tokens to generate (default: 1024)")
    ap.add_argument("--stream", action="store_true", help="Stream translation tokens (SSE)")
    ap.add_argument(
        "--serve",
        "--proxy",
        nargs="?",
        const=8080,
        type=int,
        default=None,
        dest="serve_port",
        help="Start local OpenAI-compatible bridge proxy (default port: 8080) for tools like Immersive Translate",
    )

    args = ap.parse_args()

    if args.serve_port is not None:
        run_proxy_server(port=args.serve_port, api_base=args.api_base)
        return

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
