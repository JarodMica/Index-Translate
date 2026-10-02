# llm · Text-Translation LLMs (Translate / NativeLong / Homura)

[中文](README_zh.md)

Client scripts, serving presets, fixed prompt templates, and captured cases
for the Translate, NativeLong, and Homura families. All of them speak the OpenAI chat
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

# 1. General translation (Index-Translate)
python translate.py "你好，世界。今天天气不错。" --target en
python translate.py "The quick brown fox..." --source en --target zh \
    --model IndexTeam/Index-Translate-2B

# 2. Hard constraint: Terminology / Glossary enforcement
python translate.py "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" --target en \
    --glossary "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# 3. Hard constraint: Structured data & format preservation (JSON, CSV, placeholders)
python translate.py '{"user_id": 1024, "message": "您的订单已支付完成。"}' --target en \
    --instruction "仅翻译 message 字段，严格保留合法 JSON 语法格式与键名"

# 4. Soft constraint: Style and tone adjustment
python translate.py "今天下午的会议临时取消了，改天我们再碰一下商量。" --target en \
    --instruction "调整为严谨、正式、礼貌的商务公文风格"

# 5. Soft constraint: Domain context and word-sense disambiguation
python translate.py "The plant is operating at full capacity after the spring upgrade." --target zh \
    --instruction "语境为工业制造与重工厂房领域，准确消歧专有名词"

# 6. Syllable-controlled translation with optional terminology (Index-Homura)
python syllable_translate.py "我们今天去看电影吧" --syllables 7 --target en \
    --glossary "电影:cinema"

# 7. Long-document translation (Index-NativeLong), fixed direction templates
python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
python doc_translate.py paper.txt --direction en-zh --model IndexTeam/Index-Nailong-2B
```

All scripts default to `--base-url http://127.0.0.1:8000/v1` and take
`--base-url/--model` (or `OPENAI_BASE_URL`/`INDEX_MODEL`) to hit any server.

---

## Instruction Following & Constrained Translation

Index-Translate optimizes translation quality jointly with instruction following via Rubric-as-Reward (RaR) and GRPO, formulated as:
$$R_{\mathrm{inst}} = g_{\mathrm{lang}} \cdot g_{\mathrm{hard}} \cdot \bigl(q_{\mathrm{qual}} + q_{\mathrm{soft}}\bigr)$$

Evaluated extensively on **instTrans** and **IFMTBench**, the models support two main classes of constraints:

### 1. Hard Constraints ($g_{\mathrm{hard}}$ Binary Gate)
Hard checks must pass with 100% fidelity; any failure zeros out the gate:
- **Terminology / Glossary Enforcement**: Adhere strictly to user-specified term mappings. Pass mappings directly via `--glossary "term:translation"` or provide a JSON file path.
- **Structure & Format Preservation**: In structured documents (JSON, CSV, Markdown tables, HTML), preserve keys, delimiters, tags, numbers, and boolean values intact while translating user-facing text.
- **Placeholders & Code Protection**: In software localization, preserve `{variable}`, `%s`, `[1]`, URLs, and markup unchanged.

### 2. Soft Constraints ($q_{\mathrm{soft}}$ Graded Score)
Soft constraints assess stylistic nuance, pragmatic intent, and contextual appropriateness:
- **Style & Register (Tone)**: Fluidly adjust between Formal/Business, Casual/Colloquial, Social Media (Viral / Gen-Z), and Literary styles.
- **Domain Context Disambiguation**: For polysemous words (e.g., Plant, Spring, Cell, Crane), specifying domain context (industrial, botanical, maritime, computing) ensures the correct industry-standard translation.
- **Coreference Resolution & Cross-Sentence Consistency**: Accurately resolve pronouns and maintain consistent perspective across multiple sentences or subtitle segments.

### 3. Syllable Control with Terminology Enforcement (Homura)
**Index-Homura** not only respects strict target syllable budgets (e.g. `--syllables 7`), but **also supports terminology glossaries** (`--glossary`). The model dynamically adjusts syntactic structure and function words to ensure required terms are included while matching the exact rhythm budget.

---

## Prompts

Decoding and serving defaults are collected in the [shared settings table](../../README.md#default-inference-settings). The prompts below match the task-specific training format.

- **Translate (Standard)**:
  ```
  请将以下{源}文本翻译为{目标}，直接输出翻译结果，不要进行任何解释。

  {text}
  ```
  (source omitted when `auto`).

- **Translate (Constrained with Instructions & Glossary)**:
  ```
  请将以下{源}文本翻译为{目标}。要求：{instruction}。严格遵守术语映射表【{glossary}】，严禁使用其他译名。直接输出翻译结果，不要进行任何解释。

  {text}
  ```

- **Homura (Syllable Control + Optional Glossary)**:
  ```
  请将以下文本翻译为{目标}，译文严格控制在 N 个音节。要求：严格遵守术语映射表【{glossary}】。直接输出翻译结果，不要进行任何解释。

  {text}
  ```

- **NativeLong**:
  Fixed per-direction templates (`prompts/nailong_{zh-en,en-zh,zh-ja,ja-zh}.txt`,
  substitute the single `（在这里放入需要翻译的完整…原文）` marker with the full text).

---

## Cases

- [`cases/translate_cases.jsonl`](cases/translate_cases.jsonl): baseline multilingual short-text evaluation cases.
- [`cases/instruction_cases.jsonl`](cases/instruction_cases.jsonl): recorded real runs covering CSV/JSON format preservation, glossary constraints, formal vs. casual styles, domain disambiguation, and Homura syllable + glossary co-adaptation.
- [`cases/doc_cases.jsonl`](cases/doc_cases.jsonl): native long-document translation cases.
- [`cases/syllable_cases.jsonl`](cases/syllable_cases.jsonl): Homura syllable-controlled cases.
