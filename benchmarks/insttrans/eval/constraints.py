"""Rule-based checkers for the five hard constraints.

Ported unchanged from the internal scorer so published scores stay comparable.
Each checker returns ``{"is_valid": bool, ...}`` with diagnostic detail.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .syllable import cal_syllable_count

HARD_CONSTRAINT_IDS = frozenset({
    "format_preserve", "layout_break", "term_compliance",
    "syllable_order", "social_preserve",
})
SOFT_CONSTRAINT_IDS = frozenset({
    "style_consistency", "context_disambiguate", "coref_resolution",
    "term_cross_sentence", "academic_format_preserve",
})


# ======================== Constraint text parsing ========================

def parse_term_targets(constraint_lines: list[str]) -> list[str]:
    """Target-side renderings from a `专名/术语对照: X→Y、...` line."""
    target_terms = []
    for line in constraint_lines:
        if "术语对照" not in line and "专名" not in line:
            continue
        match = re.search(r"(?:专名/?)?术语对照[:：]\s*(.*)", line)
        if not match:
            continue
        for pair in re.split(r"[、,，]", match.group(1)):
            if "→" in pair:
                target = pair.split("→", 1)[1].strip()
                if target:
                    target_terms.append(target)
    return target_terms


def parse_layout_features(constraint_lines: list[str]) -> list[str]:
    features = []
    for line in constraint_lines:
        if "布局" not in line and "排版" not in line:
            continue
        if "换行" in line:
            features.append("newlines")
        if "缩进" in line:
            features.append("indent")
        if "表格" in line:
            features.append("table_align")
    return features if features else ["newlines", "indent"]


def parse_social_elements(constraint_lines: list[str]) -> list[str]:
    elements = []
    for line in constraint_lines:
        if "社交元素" not in line:
            continue
        for sep in (":", "："):
            if sep in line:
                raw = line.split(sep, 1)[1].strip()
                elements.extend(p.strip() for p in re.split(r"[、,，]", raw) if p.strip())
                break
    return elements


def collect_soft_constraint_descs(
    constraint_ids: list[str], constraint_lines: list[str]
) -> dict[str, str]:
    """Map each soft constraint id to the prompt line stating it."""
    keyword_map = {
        "style_consistency": ["语体", "风格"],
        "context_disambiguate": ["歧义", "消歧"],
        "coref_resolution": ["指代", "代词"],
        "term_cross_sentence": ["跨句", "全文统一"],
        "academic_format_preserve": ["学术", "LaTeX", "学术格式"],
    }
    soft_descs: dict[str, str] = {}
    for cid in constraint_ids:
        if cid not in SOFT_CONSTRAINT_IDS:
            continue
        for line in constraint_lines:
            if any(kw in line for kw in keyword_map.get(cid, [])):
                soft_descs[cid] = line
                break
        soft_descs.setdefault(cid, cid)
    return soft_descs


# ======================== Rule-based checkers ========================

def _build_term_pattern(term: str) -> str:
    escaped = re.escape(term)
    # CJK has no word boundaries; \b would never match against them.
    if any(("一" <= ch <= "鿿") or ("぀" <= ch <= "ヿ") for ch in term):
        return escaped
    return rf"(?<!\w){escaped}(?!\w)"


def check_glossary(target_text: str, required_terms: list[str]) -> dict[str, Any]:
    missing = [t for t in required_terms
               if not re.search(_build_term_pattern(t), target_text)]
    return {"is_valid": not missing, "missing_terms": missing}


def check_json_preserved(source_text: str, target_text: str) -> dict[str, Any]:
    def extract_keys(text: str) -> tuple[bool, list[str]]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return False, []
        keys: list[str] = []

        def walk(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current = f"{path}.{key}" if path else key
                    keys.append(current)
                    walk(value, current)
            elif isinstance(obj, list):
                for index, element in enumerate(obj):
                    walk(element, f"{path}[{index}]")

        walk(parsed)
        return True, keys

    src_valid, src_keys = extract_keys(source_text)
    tgt_valid, tgt_keys = extract_keys(target_text)
    if not src_valid:
        return {"is_valid": False, "issues": ["源文不是有效JSON"]}
    if not tgt_valid:
        return {"is_valid": False, "issues": ["译文不是有效JSON"]}

    issues = []
    missing = set(src_keys) - set(tgt_keys)
    extra = set(tgt_keys) - set(src_keys)
    if missing:
        issues.append(f"缺失key: {missing}")
    if extra:
        issues.append(f"多余key: {extra}")
    return {"is_valid": not issues, "issues": issues}


def _extract_visible_text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _chinese_ratio(text: str) -> float:
    text = re.sub(r"\s+", "", text)
    if not text:
        return 0.0
    return sum(1 for ch in text if "一" <= ch <= "鿿") / len(text)


def check_html_preserved(
    source_text: str, target_text: str,
    src_lang: str | None = None, tgt_lang: str | None = None,
) -> dict[str, Any]:
    tag_pattern = re.compile(r"</?[a-z][a-z0-9]*\b[^>]*>", re.IGNORECASE)
    src_tag_types = [re.sub(r"\s+.*?>", ">", t) for t in tag_pattern.findall(source_text)]
    tgt_tag_types = [re.sub(r"\s+.*?>", ">", t) for t in tag_pattern.findall(target_text)]

    issues = []
    if src_tag_types != tgt_tag_types:
        issues.append(f"标签不一致: 源文{len(src_tag_types)}个, 译文{len(tgt_tag_types)}个")

    if src_lang == "zh" and tgt_lang not in ("ja", "zh"):
        tgt_visible = _extract_visible_text(target_text)
        if tgt_visible and _extract_visible_text(source_text):
            ratio = _chinese_ratio(tgt_visible)
            if ratio > 0.01:
                issues.append(f"译文中残留中文（占比{ratio:.1%}）")

    return {"is_valid": not issues, "issues": issues}


def check_markdown_preserved(source_text: str, target_text: str) -> dict[str, Any]:
    md_patterns = [
        (r"^#{1,6}\s", "标题"), (r"\*\*[^*]+\*\*", "粗体"),
        (r"\*[^*]+\*", "斜体"), (r"`[^`]+`", "行内代码"),
        (r"```[\s\S]*?```", "代码块"), (r"^[-*+]\s", "列表项"),
        (r"^\d+\.\s", "有序列表"), (r"\[.*?\]\(.*?\)", "链接"),
        (r"!\[.*?\]\(.*?\)", "图片"), (r"^>\s", "引用"),
        (r"\|.*\|", "表格"),
    ]
    issues = []
    for pattern, name in md_patterns:
        if re.search(pattern, source_text, re.MULTILINE) and not re.search(
            pattern, target_text, re.MULTILINE
        ):
            issues.append(f"丢失{name}标记")
    return {"is_valid": not issues, "issues": issues}


def check_placeholder_preserved(source_text: str, target_text: str) -> dict[str, Any]:
    patterns = [
        r"\{[a-zA-Z_][a-zA-Z0-9_]*\}",
        r"%[dsf]",
        r"\$\d+",
        r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}",
    ]
    issues = []
    for pattern in patterns:
        missing = set(re.findall(pattern, source_text)) - set(re.findall(pattern, target_text))
        if missing:
            issues.append(f"丢失占位符: {missing}")
    return {"is_valid": not issues, "issues": issues}


def check_format_preserve(
    source_text: str, target_text: str,
    src_lang: str | None = None, tgt_lang: str | None = None,
) -> dict[str, Any]:
    """Dispatch to whichever format checkers the source text actually triggers."""
    results: dict[str, Any] = {}
    issues: list[str] = []
    stripped = source_text.strip()

    if stripped[:1] in ("{", "["):
        try:
            json.loads(stripped)
            is_json = True
        except json.JSONDecodeError:
            is_json = False
        if is_json:
            sub = check_json_preserved(stripped, target_text.strip())
            results["json"] = sub
            if not sub["is_valid"]:
                issues.extend(sub.get("issues", []))

    if re.search(r"</?[a-z][a-z0-9]*\b[^>]*>", source_text, re.IGNORECASE):
        sub = check_html_preserved(source_text, target_text, src_lang=src_lang, tgt_lang=tgt_lang)
        results["html"] = sub
        if not sub["is_valid"]:
            issues.extend(sub.get("issues", []))

    if re.search(r"^#{1,6}\s|\*\*|`|^[-*+]\s|^>\s|\[.*?\]\(.*?\)", source_text, re.MULTILINE):
        sub = check_markdown_preserved(source_text, target_text)
        results["markdown"] = sub
        if not sub["is_valid"]:
            issues.extend(sub.get("issues", []))

    if re.search(
        r"\{[a-zA-Z_][a-zA-Z0-9_]*\}|%[dsf]|\$\d+|\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}", source_text
    ):
        sub = check_placeholder_preserved(source_text, target_text)
        results["placeholder"] = sub
        if not sub["is_valid"]:
            issues.extend(sub.get("issues", []))

    return {"is_valid": not issues, "issues": issues, "sub_results": results}


def check_layout_preserved(
    source_text: str, target_text: str, layout_features: list[str] | None = None
) -> dict[str, Any]:
    layout_features = layout_features or ["newlines", "indent"]
    issues = []

    if "newlines" in layout_features:
        src_nl, tgt_nl = source_text.count("\n"), target_text.count("\n")
        if src_nl != tgt_nl:
            issues.append(f"换行数不一致: 源文{src_nl}, 译文{tgt_nl}")

    if "indent" in layout_features:
        src_indent = len(source_text) - len(source_text.lstrip())
        tgt_indent = len(target_text) - len(target_text.lstrip())
        if (src_indent > 0) != (tgt_indent > 0):
            issues.append("缩进风格不一致")

    if "table_align" in layout_features:
        src_has = any("|" in l and l.count("|") >= 2 for l in source_text.splitlines())
        tgt_has = any("|" in l and l.count("|") >= 2 for l in target_text.splitlines())
        if src_has and not tgt_has:
            issues.append("源文含表格对齐结构但译文丢失")

    return {"is_valid": not issues, "issues": issues}


def check_social_preserve(target_text: str, elements: list[str]) -> dict[str, Any]:
    if not elements:
        return {"is_valid": True, "note": "no elements to check"}
    missing = [e for e in elements if e not in target_text]
    return {"is_valid": not missing, "missing_elements": missing}


def check_syllable_order(
    prediction: str, durations: list[float], tgt_lang: str
) -> dict[str, Any]:
    """Rank-correlate per-sentence duration against translated syllable count.

    Passes at concordance >= 0.9. Pairs with equal durations, and pairs with equal
    syllable counts, are not counted as inversions.
    """
    if not durations or not prediction:
        return {"is_valid": True, "note": "no duration data"}

    try:
        output = json.loads(prediction)
    except (json.JSONDecodeError, TypeError):
        return {"is_valid": False, "note": "output is not valid JSON"}
    if not isinstance(output, dict):
        return {"is_valid": False, "note": "output is not a JSON object"}

    syllables = [
        cal_syllable_count(output.get(str(i), ""), tgt_lang)
        for i in range(1, len(durations) + 1)
    ]
    if len(syllables) < 2:
        return {"is_valid": True, "note": "too few sentences"}

    inversions = total_pairs = 0
    for i in range(len(durations)):
        for j in range(i + 1, len(durations)):
            if durations[i] == durations[j]:
                continue
            total_pairs += 1
            if syllables[i] == syllables[j]:
                continue
            if (durations[i] > durations[j]) != (syllables[i] > syllables[j]):
                inversions += 1

    if total_pairs == 0:
        return {"is_valid": True, "note": "all durations equal"}

    concordance = 1.0 - inversions / total_pairs
    return {
        "is_valid": concordance >= 0.9,
        "concordance": round(concordance, 3),
        "inversions": inversions,
        "total_pairs": total_pairs,
    }


def check_hard_constraints(row: dict[str, Any], prediction: str) -> dict[str, Any]:
    """Run every hard checker this instance is annotated for."""
    if not prediction:
        return {}

    source_text = row["source_text"]
    constraint_lines = row["constraints"]
    results: dict[str, Any] = {}

    for cid in row["constraint_ids"]:
        if cid not in HARD_CONSTRAINT_IDS:
            continue
        if cid == "format_preserve":
            results[cid] = check_format_preserve(
                source_text, prediction,
                src_lang=row["source_lang"], tgt_lang=row["target_lang"],
            )
        elif cid == "layout_break":
            results[cid] = check_layout_preserved(
                source_text, prediction, parse_layout_features(constraint_lines))
        elif cid == "term_compliance":
            terms = parse_term_targets(constraint_lines)
            results[cid] = (check_glossary(prediction, terms) if terms
                            else {"is_valid": True, "note": "no terms to check"})
        elif cid == "syllable_order":
            results[cid] = check_syllable_order(
                prediction, row.get("duration_s", []), row["target_lang"])
        elif cid == "social_preserve":
            results[cid] = check_social_preserve(
                prediction, parse_social_elements(constraint_lines))

    return results
