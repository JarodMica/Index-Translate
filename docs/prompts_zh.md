# 提示词示例

[English](prompts.md) · [返回 README](../README_zh.md)

*注：以下示例中源/目标语言请使用完整语言名（如 英语/English）。所有模板只输出译文，不带额外解释。*

| 类型 | 中文提示词 | 英文提示词 |
|---|---|---|
| **默认翻译**（Index-Translate） | 请将以下文本翻译为 `{目标语言}`，直接输出翻译结果，不要进行任何解释：<br><br>`{源文本}` | Translate the following text into `{target_lang}`. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **术语/约束翻译**（Index-Translate） | 请将以下字幕翻译为 `{目标语言}`。要求：术语在全文中保持一致（如 `{术语}` 固定译法），保留原文结构与占位符：<br><br>`{源文本}` | Translate the following subtitles into `{target_lang}`. Requirements: keep terminology consistent across sentences (fixed rendering for `{term}`), preserve structure and placeholders:<br><br>`{source_text}` |
| **结构化数据**（Index-Translate） | 将下方 `{格式}` 数据翻译为 `{目标语言}`：仅翻译面向用户的文本字段，严禁改动结构、键名与占位符：<br><br>`{源文本}` | Translate the following `{format_type}` data into `{target_lang}`: translate only user-facing text fields; never alter the structure, keys, or placeholders:<br><br>`{source_text}` |
| **音节受控**（Index-Homura） | 请将以下文本翻译为 `{目标语言}`，译文严格控制在 `N` 个音节。直接输出翻译结果，不要进行任何解释：<br><br>`{源文本}` | Translate the following text into `{target_lang}`, strictly within `N` syllables. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **长文档**（Index-NativeLong） | 直接粘贴完整文档，使用固定方向模板（见 [inference/llm/prompts](../inference/llm/prompts)），一次生成完整译文 | Paste the complete document with the fixed per-direction template (see [inference/llm/prompts](../inference/llm/prompts)); the full translation is produced in one generation |

Translate 与 Homura 的客户端默认 temperature 为 0.3，并关闭思考；NativeLong 使用固定方向模板和贪心解码。完整配置见[文本推理文档](../inference/llm/README_zh.md)。
