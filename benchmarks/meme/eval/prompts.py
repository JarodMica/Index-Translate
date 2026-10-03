"""Deterministic model and Judge prompts for Meme Translation Bench.

Model messages are built from structured benchmark case fields at runtime;
they are not stored inside the case data.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

MODEL_PROMPT_VERSION = "meme-translation-inference-v1"
JUDGE_PROMPT_VERSION = "meme-translation-judge-v1"

TYPE_NAMES = {
    "bullet": "弹幕",
    "review": "评论",
    "title": "标题",
    "description": "简介",
}
CONTROL_SEPARATOR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")

MODEL_PROMPT = """请将以下中文视频{text_type}翻译成英语。

【视频摘要】
{summary}

【待翻译文本】{text}

【约束要求】
结合原文和视频背景，先判断网络梗、亚文化用语或文化梗在当前语境中的实际含义、语气和功能，再选择合适的跨文化翻译策略。只输出译文，不要有任何额外说明。"""


def require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} must be a non-empty string")
    return value.strip()


def clean_context_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = CONTROL_SEPARATOR_RE.sub("\n", value)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def resolve_text_type(case: dict[str, Any]) -> str:
    text_type = case["text_type"]
    if text_type not in TYPE_NAMES:
        raise ValueError(f"unknown text_type: {text_type!r}")
    return text_type


def build_video_context(case: dict[str, Any]) -> str:
    text = require_text(case.get("original_text"), "original_text")
    title = clean_context_text(case.get("video_title"))
    content = clean_context_text(case.get("video_description"))
    parts: list[str] = []
    if title and title != text:
        parts.append(f"【视频标题】{title}")
    if content and content != text:
        parts.append(f"【视频简介】{content}")
    if not parts:
        return "（无可用视频摘要）"
    return "\n".join(parts)


def build_model_prompt(case: dict[str, Any]) -> str:
    text_type = resolve_text_type(case)
    summary = build_video_context(case)
    return MODEL_PROMPT.format(
        text_type=TYPE_NAMES[text_type],
        summary=summary,
        text=require_text(case.get("original_text"), "original_text"),
    )


def build_model_messages(case: dict[str, Any]) -> list[dict[str, str]]:
    return [{"role": "user", "content": build_model_prompt(case)}]


def format_definition(context: dict[str, Any]) -> str:
    result = require_text(context.get("definition"), "definition")
    examples = context.get("examples", [])
    if examples:
        result += "\n\n例句：\n" + "\n".join(
            f"- {require_text(example.get('original_text'), 'example.original_text')}"
            for example in examples
        )
    return result


def _format_reference_groups(groups: Any) -> list[str]:
    lines: list[str] = []
    for group in groups or []:
        references = group.get("references") or []
        if references:
            lines.append(f"- {group['strategy']}：{' | '.join(references)}")
    return lines


def format_translation_references(context: dict[str, Any]) -> str:
    good = context.get("translation_references") or []
    partial = context.get("translation_references_0.5_score") or []
    bad = context.get("translation_references_0_score") or []
    if not good and not partial and not bad:
        return "（暂无参考翻译）"

    lines = _format_reference_groups(good)
    if partial:
        if lines:
            lines.append("")
        lines.append("以下参考翻译为勉强可用的参考，或是判定为0.5分的译法：")
        lines.extend(_format_reference_groups(partial))
    if bad:
        if lines:
            lines.append("")
        lines.append("以下参考翻译为不可用参考，或是判定为0分的译法：")
        lines.extend(_format_reference_groups(bad))
    return "\n".join(lines)


def build_judge_prompt(
    case: dict[str, Any], context: dict[str, Any], prediction: str
) -> str:
    definition = format_definition(context)
    references = format_translation_references(context)
    return f"""你是一个专业的翻译质量评估专家，需要评估模型对包含网络流行语（梗）的文本的翻译质量。

【评估标准】
- 1分：翻译准确，正确传达了梗的含义和文本的整体意思，译文自然流畅
- 0.5分：翻译基本准确，梗的核心含义传达正确，但在表达方式或流畅度上有所欠缺
- 0分：翻译错误，误解了梗的含义或文本的整体意思

【待评估内容】
原文：
{case['original_text']}

梗：{case['term']}

梗的释义（包含例句）：
{definition}

参考翻译（按翻译策略分类，同一策略下列出的译法均视为正确）：
{references}

模型翻译：
{prediction}

【评估要求】
1. 判断模型翻译是否准确传达了原文含义，特别是梗的含义
2. 参考翻译仅供参考，不要求模型翻译与参考翻译完全一致；语义等价的意译也应视为正确
3. 重点关注：梗的处理是否恰当、整体意思是否准确、译文是否自然
4. 给出评分（0/0.5/1）和详细的评估理由

请按以下格式输出：
评分：[0/0.5/1]
理由：[详细说明评分依据]
"""


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


JUDGE_TEMPLATE_SHA256 = prompt_sha256(
    build_judge_prompt(
        {"original_text": "{original_text}", "term": "{term}"},
        {"definition": "{definition}", "examples": []},
        "{prediction}",
    )
)
