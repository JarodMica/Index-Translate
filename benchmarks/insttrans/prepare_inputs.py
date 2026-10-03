#!/usr/bin/env python3
"""Export model inputs without exposing the reference translation to the model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.prompts import build_model_messages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-file", type=Path,
                        default=Path(__file__).resolve().parent / "data/test.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.data_file.resolve():
        parser.error("--output must differ from --data-file")

    # split("\n"), not splitlines(): source text contains raw U+2028, which is
    # legal inside a JSON string but is a line break to splitlines().
    rows = [json.loads(line) for line
            in args.data_file.read_text(encoding="utf-8").split("\n") if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({
                "case_id": row["case_id"],
                "messages": build_model_messages(row),
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} model inputs to {args.output}")


if __name__ == "__main__":
    main()
