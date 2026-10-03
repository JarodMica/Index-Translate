#!/usr/bin/env python3
"""Export original model messages and case IDs, excluding labels and metadata."""
import argparse
import json
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-file',type=Path,default=Path(__file__).parent/'sandglass_bench.jsonl')
    ap.add_argument('--output',type=Path,required=True)
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.data_file.open(encoding='utf-8') as source,args.output.open('w',encoding='utf-8') as output:
        for line in source:
            if line.strip():
                row=json.loads(line)
                output.write(json.dumps(dict(case_id=row['case_id'],messages=row['prompt']),ensure_ascii=False)+'\n')
if __name__ == '__main__':
    main()
