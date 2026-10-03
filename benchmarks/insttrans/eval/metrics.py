"""Score parsing and aggregation.

The headline metric is IF_Score: ``product(hard_pass) x mean(soft_scores)``. A
single failed hard constraint zeroes the instance; soft constraints average into
a 0-1 multiplier. Instances with no soft constraints use a multiplier of 1.0, so
they score 1.0 or 0.0.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

SCORES = (0.0, 0.5, 1.0)


def parse_quality_score(response: str) -> float | None:
    """Parse a 0 / 0.5 / 1 quality verdict. Returns None if unparseable."""
    text = (response or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if not re.fullmatch(r"(?:0(?:\.0+)?|0\.50*|1(?:\.0+)?)", text):
        return None
    return float(text)


def parse_soft_constraint_scores(
    response: str, constraint_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Parse the soft-constraint Judge's JSON verdict, keyed by constraint id."""
    unscored = {cid: {"score": None} for cid in constraint_ids}
    if not response:
        return unscored

    data = None
    try:
        data = json.loads(response.strip())
    except json.JSONDecodeError:
        # The Judge sometimes wraps the object in prose or a code fence.
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    if not isinstance(data, dict):
        return unscored

    results: dict[str, dict[str, Any]] = {}
    for cid in constraint_ids:
        entry = data.get(cid)
        if isinstance(entry, dict):
            try:
                score = float(entry.get("score"))
            except (TypeError, ValueError):
                score = None
            if score in (0, 0.5, 1):
                results[cid] = {"score": score, "note": entry.get("note", "")}
                continue
        results[cid] = {"score": None}
    return results


def compute_if_score(
    hard_results: dict[str, Any], soft_results: dict[str, Any]
) -> float:
    hard_pass = 1.0
    for result in hard_results.values():
        if not result.get("is_valid", True):
            hard_pass = 0.0
            break
    soft_values = [r["score"] for r in soft_results.values() if r.get("score") is not None]
    soft_mean = sum(soft_values) / len(soft_values) if soft_values else 1.0
    return hard_pass * soft_mean


def _score_key(score: float) -> str:
    return "0" if score == 0 else "0.5" if score == 0.5 else "1"


def aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    covered = sum(row["prediction_status"] == "present" for row in rows)
    if_scores = [float(row["if_score"]) for row in rows]
    quality = [row["quality_score"] for row in rows if row["quality_score"] is not None]
    return {
        "total": total,
        "prediction_coverage": covered,
        "prediction_coverage_rate": covered / total if total else 0.0,
        "if_score": sum(if_scores) / total if total else 0.0,
        "translation_quality": sum(quality) / len(quality) if quality else None,
        "quality_scored": len(quality),
        "quality_distribution": {
            _score_key(s): sum(1 for q in quality if q == s) for s in SCORES
        },
    }


def aggregate_constraints(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-constraint pass rate (hard) or mean score (soft)."""
    hard: dict[str, Counter] = defaultdict(Counter)
    soft: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        for cid, result in row["hard_constraint_results"].items():
            hard[cid]["total"] += 1
            if result.get("is_valid", True):
                hard[cid]["pass"] += 1
        for cid, result in row["soft_constraint_results"].items():
            if result.get("score") is not None:
                soft[cid].append(float(result["score"]))

    out: dict[str, Any] = {}
    for cid, counts in sorted(hard.items()):
        total = counts["total"]
        out[cid] = {
            "type": "hard",
            "total": total,
            "pass": counts["pass"],
            "pass_rate": counts["pass"] / total if total else None,
        }
    for cid, scores in sorted(soft.items()):
        out[cid] = {
            "type": "soft",
            "total": len(scores),
            "mean_score": sum(scores) / len(scores) if scores else None,
            "score_distribution": {
                _score_key(s): sum(1 for v in scores if v == s) for s in SCORES
            },
        }
    return out


def compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = aggregate_group(rows)
    summary["by_constraint"] = aggregate_constraints(rows)

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        "scenario": defaultdict(list),
        "domain": defaultdict(list),
        "language_pair": defaultdict(list),
    }
    for row in rows:
        grouped["scenario"][row["scenario"]].append(row)
        grouped["domain"][row["domain"]].append(row)
        grouped["language_pair"][f"{row['source_lang']}-{row['target_lang']}"].append(row)

    summary["breakdowns"] = {
        dimension: {key: aggregate_group(group) for key, group in sorted(groups.items())}
        for dimension, groups in grouped.items()
    }
    return summary
