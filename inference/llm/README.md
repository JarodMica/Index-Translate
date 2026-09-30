# llm · Text-Translation LLMs (Translate / NativeLong / Homura)

[中文](README_zh.md)

Client scripts, serving presets, fixed prompt templates, and captured cases
for the six text-translation LLMs. All of them speak the OpenAI chat
completions API — serve with vLLM (recommended), SGLang, or any compatible
stack, then point the scripts at it.

Index-NativeLong retains the published `IndexTeam/Index-Nailong-*` model IDs and `nailong-*` serving presets. The Index-Translate models cover 150 languages; use a full language name when a language code is not mapped by the client.

## Serve

```bash
pip install -U vllm     # needs a build with Qwen3.5 support (tested on 0.29)

./serve_vllm.sh translate-9b    # IndexTeam/Index-Translate-9B on :8000
./serve_vllm.sh translate-2b
./serve_vllm.sh nailong-9b      # long-doc, 229376 max positions per shipped config
./serve_vllm.sh nailong-2b      # long-doc, 262144
./serve_vllm.sh homura-9b       # syllable-controlled
./serve_vllm.sh homura-2b
```

Extra arguments are passed through to `vllm serve`, e.g.
`./serve_vllm.sh nailong-9b --tensor-parallel-size 4 --data-parallel-size 2`.

GPU memory (bf16): 2B ≈ 8 GB, 9B ≈ 24 GB, plus KV cache for long contexts.

## Use

```bash
pip install openai httpx

# general translation (Index-Translate)
python translate.py "你好，世界。今天天气不错。" --target en
python translate.py "The quick brown fox..." --source en --target zh \
    --model IndexTeam/Index-Translate-2B

# long-document translation (Index-NativeLong), fixed direction templates
python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
python doc_translate.py paper.txt --direction en-zh --model IndexTeam/Index-Nailong-2B

# syllable-controlled translation (Index-Homura)
python syllable_translate.py "我们今天去看电影吧" --syllables 8 --target en
```

All scripts default to `--base-url http://127.0.0.1:8000/v1` and take
`--base-url/--model` (or `OPENAI_BASE_URL`/`INDEX_MODEL`) to hit any server.

## Prompts and decoding (matched to training)

- **Translate**: single user message
  `请将以下{源}文本翻译为{目标}，直接输出翻译结果，不要进行任何解释。\n\n{text}`
  (source omitted when `auto`); greedy decoding — temperature 0; thinking disabled.
- **NativeLong**: fixed per-direction templates (`prompts/nailong_{zh-en,en-zh,zh-ja,ja-zh}.txt`,
  substitute the single `（在这里放入需要翻译的完整…原文）` marker with the full text);
  greedy decoding — temperature 0, top_p 1, top_k -1, min_p 0, seed 42,
  `stop_token_ids=[248044, 248046]`, thinking disabled, and **no `max_tokens`**
  so the model writes into the remaining window. `doc_translate.py` reproduces
  this profile exactly.
- **Homura**: single user message
  `请将以下文本翻译为{目标}，译文严格控制在 N 个音节。直接输出翻译结果，不要进行任何解释。\n\n{text}`;
  temperature 0.3; thinking disabled. Syllable counts are approximate targets,
  not hard guarantees.

## Cases

`cases/` holds inputs and outputs captured from real runs of these exact
scripts against the released weights (both sizes, several directions) —
regenerate or extend them as a smoke test after your own deployment.
