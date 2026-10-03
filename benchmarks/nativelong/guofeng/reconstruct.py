#!/usr/bin/env python3
"""Reconstruct frozen GuoFeng cases from user-supplied official V1 Train files."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_rows(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_rows(path, rows):
    with path.open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')


def write_checksums(root):
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (root / 'SHA256SUMS').write_text(''.join(
        f'{digest(p)}  {p.relative_to(root).as_posix()}\n' for p in files
    ), encoding='utf-8')


def reconstruct(recipe, source, reference, output):
    manifest = json.loads((recipe / 'manifest.json').read_text(encoding='utf-8'))
    for side, path in [('source', source), ('reference', reference)]:
        if digest(path) != manifest['upstream'][side + '_sha256']:
            raise ValueError(f'Official {side} file hash differs from the frozen input')
    if output.exists():
        raise FileExistsError(output)
    unit_specs = read_rows(recipe / 'units.jsonl')
    by_row = {r['corpus_row']: r for r in unit_specs}
    values = {}
    for side, path in [('source', source), ('reference', reference)]:
        with path.open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if line_number not in by_row:
                    continue
                raw = line.rstrip('\r\n')
                spans = by_row[line_number][side + '_keep_spans']
                if any(a < 0 or b < a or b > len(raw) for a, b in spans):
                    raise ValueError(f'Invalid character span at row {line_number}')
                values.setdefault(line_number, {})[side] = ''.join(raw[a:b] for a, b in spans)
    if values.keys() != by_row.keys():
        raise ValueError('Missing official input rows')
    by_work = {}
    for spec in unit_specs:
        work = spec['document_id'].split(':', 1)[0]
        by_work.setdefault(work, {})[spec['canonical_alignment_unit_index']] = spec
    cases, requests, references, alignments = [], [], [], []
    prompt = (recipe / 'prompt.txt').read_text(encoding='utf-8')
    for case in read_rows(recipe / 'case-index.jsonl'):
        m = case['metadata']
        selected = [by_work[case['work_id']][i] for i in range(
            m['start_alignment_unit'], m['end_alignment_unit_exclusive'])]
        for side in ['source', 'reference']:
            case[side] = '\n'.join(values[s['corpus_row']][side] for s in selected)
            actual = hashlib.sha256(case[side].encode()).hexdigest()
            if actual != case[side + '_sha256']:
                raise ValueError(f'Frozen text mismatch: {case["case_id"]} {side}')
        cases.append(case)
        requests.append({'case_id': case['case_id'],
                         'messages': [{'role': 'user', 'content': prompt + '\n\n' + case['source']}],
                         'metadata': {k: case[k] for k in [
                             'track_id', 'split', 'work_id', 'length_band', 'source_sha256']}})
        references.append({k: case[k] for k in ['case_id', 'reference', 'reference_sha256']})
        for index, spec in enumerate(selected):
            row = {k: v for k, v in spec.items() if not k.endswith('_keep_spans')}
            row.update(case_id=case['case_id'], alignment_unit_index=index,
                       **values[spec['corpus_row']])
            alignments.append(row)
    output.mkdir(parents=True)
    (output / 'segale').mkdir()
    for name, rows in [('cases.jsonl', cases), ('requests.jsonl', requests),
                       ('references.jsonl', references), ('segale/alignment-units.jsonl', alignments)]:
        write_rows(output / name, rows)
    (output / 'segale/document-boundaries.jsonl').write_bytes(
        (recipe / 'document-boundaries.jsonl').read_bytes())
    (output / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_checksums(output)
    return {'case_count': len(cases), 'matched_source_and_reference_hashes': len(cases) * 2}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--source', type=Path, required=True, help='Official V1 Train train.zh')
    parser.add_argument('--reference', type=Path, required=True, help='Official V1 Train train.en')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    print(json.dumps(reconstruct(args.recipe, args.source, args.reference, args.output)))
