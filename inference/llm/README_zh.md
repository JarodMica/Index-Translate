# llm · 文本翻译大模型（Translate / NativeLong / Homura）

[English](README.md)

Translate、NativeLong、Homura 三个家族的客户端脚本、部署预设、固定 prompt 模板和实测用例。
它们都走 OpenAI chat completions 协议——用 vLLM（推荐）、SGLang 或任何兼容栈起服务，然后把脚本指过去即可。

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

# 1. 通用基础翻译（Index-Translate）
python translate.py "你好，世界。今天天气不错。" --target en
python translate.py "The quick brown fox..." --source en --target zh \
    --model IndexTeam/Index-Translate-2B

# 2. 指令遵循：硬约束（术语指定 / 字典干预）
python translate.py "王平仲采用了更加昂贵的碳纤维材料。碳纤维的好处就是它抗裂缝。" --target en \
    --glossary "碳纤维:carbon fiber, 抗裂缝:crack resistance"

# 3. 指令遵循：硬约束（格式保留 / JSON、CSV、变量保护）
python translate.py '{"user_id": 1024, "message": "您的订单已支付完成。"}' --target en \
    --instruction "仅翻译 message 字段，严格保留合法 JSON 语法格式与键名"

# 4. 指令遵循：软约束（文风与语气控制）
python translate.py "今天下午的会议临时取消了，改天我们再碰一下商量。" --target en \
    --instruction "调整为严谨、正式、礼貌的商务公文风格"

# 5. 指令遵循：软约束（领域与语境多义词消歧）
python translate.py "The plant is operating at full capacity after the spring upgrade." --target zh \
    --instruction "语境为工业制造与重工厂房领域，准确消歧专有名词"

# 6. 音节受控翻译（Index-Homura，支持结合术语约束）
python syllable_translate.py "我们今天去看电影吧" --syllables 7 --target en \
    --glossary "电影:cinema"

# 7. 长文档翻译（Index-NativeLong，固定方向模板）
python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
python doc_translate.py paper.txt --direction en-zh --model IndexTeam/Index-Nailong-2B
```

脚本默认 `--base-url http://127.0.0.1:8000/v1`，可用 `--base-url/--model`（或环境变量 `OPENAI_BASE_URL`/`INDEX_MODEL`）指向任意服务器。

---

## 指令遵循与约束翻译（Instruction Following）

Index-Translate 在训练中通过 Rubric-as-Reward (RaR) 和 GRPO 联合优化翻译质量与指令遵循能力，其奖励函数为：
$$R_{\mathrm{inst}} = g_{\mathrm{lang}} \cdot g_{\mathrm{hard}} \cdot \bigl(q_{\mathrm{qual}} + q_{\mathrm{soft}}\bigr)$$

评测涵盖 **instTrans** 与 **IFMTBench**，支持以下两大类约束：

### 1. 硬约束（Hard Constraints, $g_{\mathrm{hard}}$ 门控）
硬约束为二进制指标（0 或 1），任何一项违背直接视为不合规：
- **术语强约束（Terminology / Glossary）**：严格按照给定的映射表输出目标译名。可直接通过 `--glossary "源词:目标词"` 传入，或传入 JSON 字典文件路径。
- **结构与格式保护（Format Preservation）**：在翻译 JSON、CSV、Markdown 表格、HTML 时，严格保护键名、标签、分隔符、数字、布尔值，仅翻译面向用户的文本内容。
- **变量与占位符保护（Placeholders / Code）**：在系统提示、文案本地化中，严格保留 `{user_name}`、`%s`、`[1]`、URL 链接等变量不被破坏。

### 2. 软约束（Soft Constraints, $q_{\mathrm{soft}}$ 连续评分）
软约束关注语义贴合度、行文自然度与语境适配：
- **文体风格与语气（Style & Tone）**：正式商务（Formal）、日常随性口语（Casual）、海外社交网络网感（Viral / Gen-Z）、文学典雅（Literary）等风格自由切换。
- **领域语境消歧（Context Disambiguation）**：输入多义词（如 Plant、Spring、Cell、Crane）时，通过指令声明领域（工业制造 / 温室农业 / 港口工程 / 软件架构），模型能精准选取行业地道译法。
- **共指消解与跨句一致性（Coreference & Consistency）**：在多句篇章或字幕对话中保持代词指代（他/她/它）与角色称呼前后呼应。

### 3. 音节控制与术语协同（Homura Syllable Control with Glossary）
配音与字幕专用模型 **Index-Homura** 不仅支持目标音节数控制（如 `--syllables 7`），**同样支持术语强约束**（`--glossary`）。模型能在紧凑的音节预算下，动态调度虚词与句式，既保证指定术语 100% 出现，又精准贴合目标音节预算。

---

## Prompt 规范

解码与部署默认值统一见[默认设置总表](../../README_zh.md#默认推理参数)。下面的提示词采用对应任务的训练格式：

- **Translate（基础翻译）**：
  ```
  请将以下{源}文本翻译为{目标}，直接输出翻译结果，不要进行任何解释。

  {text}
  ```
  （`auto` 时省略源语种）。

- **Translate（带约束指令与术语）**：
  ```
  请将以下{源}文本翻译为{目标}。要求：{任务指令}。严格遵守术语映射表【{术语 -> 译名}】，严禁使用其他译名。直接输出翻译结果，不要进行任何解释。

  {text}
  ```

- **Homura（音节受控 + 可选术语）**：
  ```
  请将以下文本翻译为{目标}，译文严格控制在 N 个音节。要求：严格遵守术语映射表【{术语 -> 译名}】。直接输出翻译结果，不要进行任何解释。

  {text}
  ```

- **NativeLong（长文档）**：
  固定方向模板（`prompts/nailong_{zh-en,en-zh,zh-ja,ja-zh}.txt`，把唯一的 `（在这里放入需要翻译的完整…原文）` 占位符替换为全文）。

---

## 用例

- [`cases/translate_cases.jsonl`](cases/translate_cases.jsonl)：基础多语言短文本评测用例。
- [`cases/instruction_cases.jsonl`](cases/instruction_cases.jsonl)：收录 CSV/JSON 格式保护、术语表强约束、正式/随性文风对比、领域多义词消歧、音节+术语协同等真实运行样本。
- [`cases/doc_cases.jsonl`](cases/doc_cases.jsonl)：长文档真实输入输出。
- [`cases/syllable_cases.jsonl`](cases/syllable_cases.jsonl)：音节控制基准用例。
