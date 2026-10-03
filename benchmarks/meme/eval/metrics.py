"""Pure aggregation functions for Meme Translation Bench scores."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

SCORES = (0.0, 0.5, 1.0)


def _score_key(score: float) -> str:
    return "0" if score == 0 else "0.5" if score == 0.5 else "1"


def aggregate_group(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    counts = Counter(float(row["score"]) for row in rows)
    total = len(rows)
    covered = sum(row.get("prediction_status") == "present" for row in rows)
    judged = sum(row.get("judge_status") == "success" for row in rows)
    present_scores = [
        float(row["score"]) for row in rows if row.get("prediction_status") == "present"
    ]
    return {
        "total": total,
        "prediction_coverage": covered,
        "prediction_coverage_rate": covered / total if total else 0.0,
        "judged": judged,
        "mean_score": sum(float(row["score"]) for row in rows) / total if total else 0.0,
        "mean_score_present_predictions": (
            sum(present_scores) / len(present_scores) if present_scores else 0.0
        ),
        "score_distribution": {_score_key(score): counts[score] for score in SCORES},
        "nonstandard_judge_responses": sum(
            row.get("parse_status") == "nonstandard_fallback_0" for row in rows
        ),
    }


def compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = aggregate_group(rows)
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        "text_type": defaultdict(list),
    }
    for row in rows:
        grouped["text_type"][str(row["text_type"])].append(row)
    summary["breakdowns"] = {
        dimension: {key: aggregate_group(group_rows) for key, group_rows in sorted(groups.items())}
        for dimension, groups in grouped.items()
    }
    return summary
