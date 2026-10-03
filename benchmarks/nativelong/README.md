---
pretty_name: NAtIveLong Long-Document Translation Benchmark
license: other
license_name: component-specific-upstream-terms
license_link: https://github.com/EleanorJiang/BlonDe/blob/main/TERMS_OF_USE
language: [zh, en]
task_categories: [translation]
size_categories: [n<1K]
tags: [benchmark, evaluation, long-document, literary-translation]
configs:
  - config_name: bwb_metadata
    data_files:
      - split: test
        path: bwb/case-index.jsonl
  - config_name: guofeng_metadata
    data_files:
      - split: test
        path: guofeng/case-index.jsonl
---

# NAtIveLong

NAtIveLong evaluates Chinese-to-English long-document translation at 4K, 8K,
16K, 32K and 64K source-token bands. It defines **84 BWB cases and 84 GuoFeng
cases**, using six held-out books per corpus from the upstream training corpora.
These are project-defined splits, not the upstream official test splits.

## What this release contains

**This public release contains metadata, reconstruction information and evaluation
code. It contains no BWB or GuoFeng source books or reference translations.**

| Corpus | 4K | 8K | 16K | 32K | 64K | Total | Public delivery |
|---|---:|---:|---:|---:|---:|---:|---|
| BWB | 24 | 24 | 12 | 12 | 12 | 84 | Case index, book/chapter mapping, frozen prompt and provenance |
| GuoFeng | 24 | 24 | 12 | 12 | 12 | 84 | Case index, numerical extraction recipe and reconstruction script |

```python
from datasets import load_dataset
bwb = load_dataset("IndexTeam/NAtIveLong", "bwb_metadata", split="test")
guofeng = load_dataset("IndexTeam/NAtIveLong", "guofeng_metadata", split="test")
assert len(bwb) == len(guofeng) == 84
```

The dataset viewer shows case metadata; it does not supply translation inputs.
Do not use references, expected hashes or scoring metadata as model inputs.

## Obtain official data

For BWB, obtain the official Train corpus from the
[BWB download](https://drive.google.com/drive/folders/12K1-DWmpEdqkaR_61aogdywsALDg4z1L)
and follow its [terms](https://github.com/EleanorJiang/BlonDe/blob/main/TERMS_OF_USE).
The released `bwb/chapter-map.jsonl` maps project-ordered chapters to physical
upstream records, and `bwb/case-index.jsonl` provides frozen endpoints and hashes.
This release does not include an automated BWB text reconstruction utility.
See [BWB details](bwb/README.md) for the mapping and scoring input requirements.

For GuoFeng, obtain **V1 Train** through the
[official registration form](https://forms.gle/YqJPkfLgGmACbnbU6), then run:

```bash
python guofeng/reconstruct.py --source raw/train.zh --reference raw/train.en \
  --output reconstructed/guofeng
```

The standard-library script verifies official input hashes and all 168
reconstructed source/reference hashes. The output directory must be new.
See [GuoFeng details](guofeng/README.md). Reconstructed text is local material,
subject to the upstream terms, and is not included in this public dataset.

## Generate and evaluate

The [evaluation guide](evaluation/README.md) documents prediction formats,
installation, fixed scoring models and a two-document synthetic example.
Use the frozen `zh-en-document-v3` prompt and save each final translation with
its `case_id`. Record the inference engine, model revision, reasoning setting,
output limit and finish reason. The 64K band describes Chinese source length;
reserve sufficient output and total-context budget for its English translation.

The primary score is **SEGALE-COMET**, using `summary.json` →
`five_band_macro.value`: an equal-weight mean over the five length bands.
Report BWB and GuoFeng separately, plus scored/total case coverage. Scores are
on a 0–1 scale; chrF2 is auxiliary. Incomplete bands do not produce a valid full
five-band score. Evaluation code includes upstream notices and licenses.

## Limitations and provenance

Length labels use the frozen tokenizer with 5% tolerance. Windows overlap within
books, and these tests have been used in model development and comparison.
GuoFeng reconstruction preserves the existing `undefined` row in two 127-dylr
cases; it does not silently repair the frozen benchmark.

`release_manifest.json` records the source revision and public file hashes.
`SHA256SUMS` checks the delivered files. The original BWB text archive was
intentionally excluded from this public release; BWB's metadata describes the
original frozen data, not newly reselected examples.

## Attribution and terms

- [BWB / BlonDe](https://github.com/EleanorJiang/BlonDe): cite
  [NAACL 2022](https://aclanthology.org/2022.naacl-main.111/) and the applicable
  [ACL 2023 annotations](https://aclanthology.org/2023.acl-long.435/).
- [GuoFeng](https://github.com/longyuewangdcu/GuoFeng-Webnovel): follow the upstream
  non-commercial research and redistribution conditions and citation guidance
  for [WMT 2023](https://aclanthology.org/2023.wmt-1.3/) and
  [WMT 2024](https://aclanthology.org/2024.wmt-1.58/).
- [SEGALE](https://github.com/NVlabs/SEGALE): component notices are in
  `evaluation/NOTICE.md` and the vendored directories.
- Model family: [Index-Translate](https://github.com/bilibili/Index-Translate).

We grant no additional rights in underlying books or translations. The evaluation
code is Apache-2.0 under `evaluation/LICENSE`; upstream corpus terms apply
separately. See [LICENSE.md](LICENSE.md).

## Benchmark collection

Part of the [Index-Translate Benchmarks collection](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7).
