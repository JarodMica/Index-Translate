# Prompt Examples

[中文](prompts_zh.md) · [Back to README](../README.md)

*Note: in the following examples, use full language names (e.g. 英语/English). All templates output the translation only, with no extra explanation.*

| Type | Chinese prompt | English prompt |
|---|---|---|
| **Default translation** (Index-Translate) | 请将以下文本翻译为 `{target_lang}`，直接输出翻译结果，不要进行任何解释：<br><br>`{source_text}` | Translate the following text into `{target_lang}`. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **Terminology / constrained translation** (Index-Translate) | 请将以下字幕翻译为 `{target_lang}`。要求：术语在全文中保持一致（如 `{term}` 固定译法），保留原文结构与占位符：<br><br>`{source_text}` | Translate the following subtitles into `{target_lang}`. Requirements: keep terminology consistent across sentences (fixed rendering for `{term}`), preserve structure and placeholders:<br><br>`{source_text}` |
| **Structured data** (Index-Translate) | 将下方 `{format_type}` 数据翻译为 `{target_lang}`：仅翻译面向用户的文本字段，严禁改动结构、键名与占位符：<br><br>`{source_text}` | Translate the following `{format_type}` data into `{target_lang}`: translate only user-facing text fields; never alter the structure, keys, or placeholders:<br><br>`{source_text}` |
| **Syllable-controlled** (Index-Homura) | 请将以下文本翻译为 `{target_lang}`，译文严格控制在 `N` 个音节。直接输出翻译结果，不要进行任何解释：<br><br>`{source_text}` | Translate the following text into `{target_lang}`, strictly within `N` syllables. Output the translation directly, without any explanation:<br><br>`{source_text}` |
| **Long document** (Index-NativeLong) | 直接粘贴完整文档，使用固定方向模板（见 [inference/llm/prompts](../inference/llm/prompts)），一次生成完整译文 | Paste the complete document with the fixed per-direction template (see [inference/llm/prompts](../inference/llm/prompts)); the full translation is produced in one generation |

The Translate client defaults to temperature 0 (greedy decoding), while Homura defaults to temperature 0.3; both disable thinking. NativeLong uses fixed direction templates and greedy decoding. See the [text inference guide](../inference/llm/README.md) for the full settings.
