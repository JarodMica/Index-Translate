#!/usr/bin/env python3
"""Join document generations with SEGALE/COMET scores and optional groups."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


STANDARD_METADATA_FIELDS = (
    "schema_version",
    "benchmark_version",
    "track_id",
    "split",
    "corpus_id",
    "work_id",
    "official_directory_group",
    "length_band",
    "target_source_tokens",
    "window_family_id",
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def mean(values) -> float | None:
    present = [value for value in values if isinstance(value, (int, float))]
    return statistics.fmean(present) if present else None


def group_summary(rows: list[dict]) -> dict:
    statuses = Counter(row["generation"]["status"] for row in rows)
    scored_cases = sum(row["generation"]["status"] == "ok" for row in rows)
    successful = [row for row in rows if row['generation']['status'] == 'ok']
    caps = [row['generation']['cap_hit'] for row in successful
            if isinstance(row['generation'].get('cap_hit'), bool)]
    empties = [row['diagnostics']['empty_output'] for row in successful
               if isinstance(row['diagnostics'].get('empty_output'), bool)]
    finishes = Counter(row['generation']['finish_reason'] for row in successful
                       if isinstance(row['generation'].get('finish_reason'), str))
    diagnostic_fields = ('null_source_char_ratio', 'null_hypothesis_char_ratio',
                         'exact_duplicate_sentence_ratio')
    return {
        "cases": len(rows),
        "scored_cases": scored_cases,
        "failed_cases": len(rows) - scored_cases,
        "generation_status_counts": dict(sorted(statuses.items())),
        "segale_comet": mean(row.get("segale_comet") for row in rows),
        "aligned_only_comet": mean(row.get("aligned_only_comet") for row in rows),
        "na_ratio": mean(row.get("na_ratio") for row in rows),
        "hypothesis_reference_char_ratio": mean(
            row.get("hypothesis_reference_char_ratio") for row in rows
        ),
        "diagnostics": {
            "case_mean": {key: mean(row['diagnostics'].get(key) for row in rows)
                          for key in diagnostic_fields},
            "observed_cases": {key: sum(row['diagnostics'].get(key) is not None for row in rows)
                               for key in diagnostic_fields},
            "under_translation_nulls": sum(row.get('under_translation_nulls') or 0 for row in rows),
            "over_translation_nulls": sum(row.get('over_translation_nulls') or 0 for row in rows),
            "null_count_observed_cases": sum(row.get('under_translation_nulls') is not None
                                             and row.get('over_translation_nulls') is not None for row in rows),
            "cap_observed_cases": len(caps),
            "cap_hit_cases": sum(caps),
            "cap_hit_ratio": mean(caps),
            "empty_output_observed_cases": len(empties),
            "empty_output_cases": sum(empties),
            "empty_output_ratio": mean(empties),
            "finish_reason_counts": dict(sorted(finishes.items())),
        },
    }


def case_metadata(case: dict) -> dict:
    metadata = case.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError(f"Case {case.get('case_id')} metadata must be an object")
    result = dict(metadata)
    for key in STANDARD_METADATA_FIELDS:
        if key in case:
            result[key] = case[key]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--generations", type=Path, required=True)
    parser.add_argument("--comet-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--system-key", required=True)
    parser.add_argument("--group-by", action="append", default=[])
    parser.add_argument("--chrf-dir", type=Path)
    args = parser.parse_args()

    cases = read_jsonl(args.cases)
    generations = read_jsonl(args.generations)
    comet = json.loads(args.comet_summary.read_text(encoding="utf-8"))
    cases_by_id = {row["case_id"]: row for row in cases}
    generations_by_id = {row["case_id"]: row for row in generations}
    scores_by_id = {row["case_id"]: row for row in comet["cases"]}
    if len(cases_by_id) != len(cases) or len(generations_by_id) != len(generations):
        raise ValueError("Duplicate case_id")
    expected = set(cases_by_id)
    unexpected_generations = set(generations_by_id) - expected
    if unexpected_generations:
        raise ValueError(f"Generation contains unknown cases: {sorted(unexpected_generations)}")
    expected_scores = {
        case_id
        for case_id, generation in generations_by_id.items()
        if generation.get("status", "ok") == "ok"
    }
    if set(scores_by_id) != expected_scores:
        raise ValueError("Score coverage differs from successful generations")

    rows = []
    statuses = Counter()
    for case in cases:
        case_id = case["case_id"]
        generation = generations_by_id.get(case_id)
        status = "missing" if generation is None else generation.get("status", "ok")
        if not isinstance(status, str) or not status:
            raise ValueError(f"Generation {case_id} has an invalid status")
        score = scores_by_id.get(case_id, {})
        statuses[status] += 1
        rows.append(
            {
                "case_id": case_id,
                "metadata": case_metadata(case),
                "generation": {
                    key: (generation or {}).get(key)
                    for key in (
                        "status",
                        "finish_reason",
                        "input_tokens",
                        "output_tokens",
                        "cap_hit",
                        "model_revision",
                        "generation_config_sha256",
                        "output_sha256",
                    )
                } | {"status": status},
                "segale_comet": score.get("comet"),
                "aligned_only_comet": score.get("comet_aligned_only"),
                "na_ratio": score.get("na_ratio"),
                "hypothesis_reference_char_ratio": score.get(
                    "hypothesis_reference_char_ratio"
                ),
                "under_translation_nulls": score.get("under_translation_nulls"),
                "over_translation_nulls": score.get("over_translation_nulls"),
                "position_buckets": score.get("position_buckets"),
                "diagnostics": {
                    **score.get('diagnostics', {}),
                    "exact_duplicate_sentence_ratio": score.get('exact_duplicate_sentence_ratio'),
                    "empty_output": (not generation['mt'].strip())
                    if generation and isinstance(generation.get('mt'), str) else None,
                },
            }
        )

    grouped = {}
    for field in args.group_by:
        buckets = defaultdict(list)
        for row in rows:
            value = row["metadata"].get(field)
            if isinstance(value, (dict, list)):
                raise ValueError(f"Grouping field {field} must be a scalar")
            label = "__missing__" if value is None else str(value)
            buckets[label].append(row)
        grouped[field] = {
            label: group_summary(bucket) for label, bucket in sorted(buckets.items())
        }

    scored_case_count = statuses["ok"]
    result = {
        "schema_version": "document-segale-summary-v1",
        "suite_id": args.suite_id,
        "system_key": args.system_key,
        "case_count": len(rows),
        "scored_case_count": scored_case_count,
        "failed_case_count": len(rows) - scored_case_count,
        "generation_status_counts": dict(sorted(statuses.items())),
        "scored": group_summary(rows),
        "group_by": args.group_by,
        "groups": grouped,
        "cases": rows,
    }
    if args.chrf_dir:
        from score_document_chrf import aggregate, sha_file
        completed = json.loads((args.chrf_dir / "COMPLETED.json").read_text())
        artifact_path = args.chrf_dir / "artifact-manifest.json"
        if completed["artifact_manifest_sha256"] != sha_file(artifact_path):
            raise ValueError("chrF2 artifact manifest hash mismatch")
        artifacts = json.loads(artifact_path.read_text())
        for name in ("summary.json", "cases.jsonl"):
            if artifacts[name] != sha_file(args.chrf_dir / name):
                raise ValueError("chrF2 artifact hash mismatch")
        auxiliary = json.loads((args.chrf_dir / "summary.json").read_text())
        chrf_rows = read_jsonl(args.chrf_dir / "cases.jsonl")
        if auxiliary["suite_id"] != args.suite_id or auxiliary["system_key"] != args.system_key:
            raise ValueError("chrF2 run identity mismatch")
        for name, path in (("cases", args.cases), ("generations", args.generations)):
            if auxiliary["inputs"][name]["sha256"] != sha_file(path):
                raise ValueError("chrF2 input hash mismatch")
        if [r["case_id"] for r in chrf_rows] != [r["case_id"] for r in rows]:
            raise ValueError("chrF2 case coverage/order mismatch")
        for row, extra in zip(rows, chrf_rows, strict=True):
            if row["generation"]["status"] != extra["generation_status"]:
                raise ValueError("chrF2 generation status mismatch")
            row["auxiliary_metrics"] = {"chrf2": extra}
        result["auxiliary_metrics"] = {"chrf2": {
            "metric": auxiliary["metric"], "aggregate": aggregate(chrf_rows),
            "artifact": "chrf2/summary.json",
        }}
        for field, buckets in grouped.items():
            for label, bucket in buckets.items():
                subset = [r for r in chrf_rows
                          if ("__missing__" if r["metadata"].get(field) is None
                              else str(r["metadata"][field])) == label]
                bucket["auxiliary_metrics"] = {"chrf2": aggregate(subset)}

    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Summarized {len(rows)} document cases")


if __name__ == "__main__":
    main()
