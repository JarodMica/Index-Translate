# llm · 文本翻译大模型（Translate / NativeLong / Homura）

[English](README.md)

六个文本翻译 LLM 的客户端脚本、部署预设、固定 prompt 模板和实测用例。
它们都走 OpenAI chat completions 协议——用 vLLM（推荐）、SGLang 或任何
兼容栈起服务，然后把脚本指过去即可。

Index-NativeLong 沿用已发布的 `IndexTeam/Index-Nailong-*` 模型 ID 与 `nailong-*` 部署预设。Index-Translate 文本模型覆盖 150 种语言；客户端未映射的语言代码请改用完整语言名称。

## 起服务

```bash
pip install -U vllm     # 需要带 Qwen3.5 支持的版本（实测 0.29）

./serve_vllm.sh translate-9b    # IndexTeam/Index-Translate-9B，端口 :8000
./serve_vllm.sh translate-2b
./serve_vllm.sh nailong-9b      # 长文档，随包 config 上限 229376
./serve_vllm.sh nailong-2b      # 长文档，262144
./serve_vllm.sh homura-9b       # 音节控制
./serve_vllm.sh homura-2b
```

多余参数透传给 `vllm serve`，例如
`./serve_vllm.sh nailong-9b --tensor-parallel-size 4 --data-parallel-size 2`。

显存参考（bf16）：2B ≈ 8 GB，9B ≈ 24 GB，长上下文另需 KV cache。

## 调用

```bash
pip install openai httpx

# 通用翻译（Index-Translate）
python translate.py "你好，世界。今天天气不错。" --target en
python translate.py "The quick brown fox..." --source en --target zh \
    --model IndexTeam/Index-Translate-2B

# 长文档翻译（Index-NativeLong），固定方向模板
python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
python doc_translate.py paper.txt --direction en-zh --model IndexTeam/Index-Nailong-2B

# 音节控制翻译（Index-Homura）
python syllable_translate.py "我们今天去看电影吧" --syllables 8 --target en
```

脚本默认 `--base-url http://127.0.0.1:8000/v1`，可用 `--base-url/--model`
（或环境变量 `OPENAI_BASE_URL`/`INDEX_MODEL`）指向任意服务器。

## Prompt 与采样口径（与训练严格一致）

- **Translate**：单条 user 消息
  `请将以下{源}文本翻译为{目标}，直接输出翻译结果，不要进行任何解释。\n\n{text}`
  （`auto` 时省略源语种）；贪心解码——temperature 0；关闭思考。
- **NativeLong**：固定方向模板（`prompts/nailong_{zh-en,en-zh,zh-ja,ja-zh}.txt`，
  把唯一的 `（在这里放入需要翻译的完整…原文）` 占位符替换为全文）；
  greedy——temperature 0、top_p 1、top_k -1、min_p 0、seed 42、
  `stop_token_ids=[248044, 248046]`、关闭思考，且**不传 `max_tokens`**，
  让模型写满剩余窗口。`doc_translate.py` 完整复现了这套口径。
- **Homura**：单条 user 消息
  `请将以下文本翻译为{目标}，译文严格控制在 N 个音节。直接输出翻译结果，不要进行任何解释。\n\n{text}`；
  temperature 0.3；关闭思考。音节数是近似目标而非硬约束。

## 用例

`cases/` 收录了这些脚本对发布权重真实运行的输入输出（两个尺寸、多个方向），
自己部署后也可以照着重放一遍当冒烟测试。
