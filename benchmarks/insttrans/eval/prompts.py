"""Model input construction and Judge prompts.

The model prompt is the dataset's own ``prompt`` field, sent verbatim: it already
carries the task instruction, the source text and the numbered constraints, so
rewriting it here would change what the benchmark measures.
"""

from __future__ import annotations

from typing import Any

MODEL_PROMPT_VERSION = "insttrans-inference-v1"
QUALITY_JUDGE_PROMPT_VERSION = "insttrans-quality-judge-v1"
SOFT_CONSTRAINT_JUDGE_PROMPT_VERSION = "insttrans-soft-constraint-judge-v1"

LANGUAGE_NAMES = {
    "ar": "阿拉伯语", "de": "德语", "en": "英语", "es": "西班牙语",
    "fil": "菲律宾语", "fr": "法语", "hi": "印地语", "id": "印尼语",
    "it": "意大利语", "ja": "日语", "ko": "韩语", "ms": "马来语",
    "nl": "荷兰语", "pl": "波兰语", "pt": "葡萄牙语", "ro": "罗马尼亚语",
    "ru": "俄语", "sv": "瑞典语", "th": "泰语", "tr": "土耳其语",
    "vi": "越南语", "zh": "中文",
}


def build_model_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    """Chat messages for the system under test. Sends `prompt` unchanged."""
    return [{"role": "user", "content": row["prompt"]}]


def _lang_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def build_quality_prompt(row: dict[str, Any], prediction: str) -> str:
    """Translation-quality Judge prompt (0 / 0.5 / 1).

    `web_html` instances get a variant that tells the Judge to score only the
    visible text, because their source embeds HTML/JSON markup.
    """
    src_name = _lang_name(row["source_lang"])
    tgt_name = _lang_name(row["target_lang"])
    source_text = row["source_text"]
    reference = row["reference"]

    if row.get("scenario") == "web_html":
        return f"""你是精通{src_name}和{tgt_name}的网页文本翻译质量评估专家。请仅从翻译准确性和流畅度角度评估以下<待评估译文>。
注意：源文中包含HTML/JSON标签，这些标签是文本的一部分，评估时只关注可见文本的翻译质量。

# 评估维度

## 翻译准确性
<严重错误>:
- 可见文本的核心语义发生变化、漏译或严重误译。
- 添加了原文中不存在的内容。

<轻度错误>:
- 专有名词翻译不准确。
- 部分表达语义有偏移。

## 译文流畅度
<严重错误>:
- 可见文本不通顺，无法正常阅读理解。

<轻度错误>:
- 用词不够自然，有翻译腔。
- 语法有轻微瑕疵但不影响理解。

# 评分标准
评分时请考虑文本长度：短文本（1-3句）和长文本（10句以上）应使用相同的质量密度标准，即关注错误占比而非错误绝对数量。
1分: 翻译准确自然，无严重错误。轻度错误占比极低（不超过总句数的10%）。
0.5分: 无严重错误，轻度错误占比适中（约10%-30%的句子有轻度错误），整体可读。
0分: 有严重错误；或轻度错误占比过高（超过30%的句子有轻度错误），严重影响整体质量。

# 评估材料

<源文>:
{source_text}

<参考译文>:
{reference}

<待评估译文>:
{prediction}

请将你的打分写在<输出>中，直接输出[0/0.5/1]中的数字，不要输出任何其他内容。
<输出>:"""

    return f"""你是精通{src_name}和{tgt_name}的翻译质量评估专家。请仅从翻译准确性和流畅度角度评估以下<待评估译文>，不评估格式、约束等方面。

# 评估维度

## 翻译准确性
<严重错误>:
- 核心语义发生变化，原文意思被曲解。
- 重要内容漏译或严重误译。
- 添加了原文中不存在的内容。

<轻度错误>:
- 专有名词翻译不准确。
- 部分表达语义有偏移。

## 译文流畅度
<严重错误>:
- 译文不通顺，无法正常阅读理解。
- 出现目标语言中不自然的表达方式。

<轻度错误>:
- 用词不够自然，有翻译腔。
- 语法有轻微瑕疵但不影响理解。

# 评分标准
评分时请考虑文本长度：短文本（1-3句）和长文本（10句以上）应使用相同的质量密度标准，即关注错误占比而非错误绝对数量。
1分: 翻译准确自然，无严重错误，轻度错误极少。
0.5分: 只有轻度错误，或仅有少量严重错误（不超过总句数的10%），整体可读。
0分: 有大量严重错误（超过总句数的10%），严重影响整体质量。

# 评估材料

<源文>:
{source_text}

<参考译文>:
{reference}

<待评估译文>:
{prediction}

请将你的打分写在<输出>中，直接输出[0/0.5/1]中的数字，不要输出任何其他内容。
<输出>:"""


SOFT_CONSTRAINT_JUDGE_TEMPLATE = """请评估译文对每条约束的满足程度。

【源文】
{source_text}

【译文】
{target_text}

【约束列表】
{constraint_list}

评分标准（每条约束三档）：
- 1：完全满足
- 0.5：部分满足（有小瑕疵但不影响理解）
- 0：未满足或严重偏离

如果译文中存在大段内容不断重复（同一句话或片段连续出现3次及以上），所有约束直接判0分。

请输出JSON，以约束ID为key：
{{
    "constraint_id": {{
      "score": 0或0.5或1,
      "note": "简短说明"
    }}
}}

只输出JSON，不要输出任何其他内容。"""


def build_soft_constraint_prompt(
    row: dict[str, Any], prediction: str, soft_descs: dict[str, str]
) -> str:
    constraint_list = "\n".join(f"[{cid}] {desc}" for cid, desc in soft_descs.items())
    return SOFT_CONSTRAINT_JUDGE_TEMPLATE.format(
        source_text=row["source_text"],
        target_text=prediction,
        constraint_list=constraint_list,
    )
