# Reproduce SEGALE-COMET evaluation

This directory contains the code needed to score the released Chinese-to-English tests: SEGALE alignment code, VecAlign, input adapters, COMET aggregation and document chrF2. It runs locally on CPU or one CUDA GPU.

Original SEGALE repository: **https://github.com/NVlabs/SEGALE**

Paper: https://aclanthology.org/2025.emnlp-main.1645/

VecAlign: https://github.com/shuoyangd/vecalign (upstream: https://github.com/thompsonb/vecalign)

Versions and modifications are recorded in [NOTICE.md](NOTICE.md) and [provenance.json](provenance.json). Code licenses are included; they do not cover the datasets' book text.

## 1. Install

Use **Python 3.11** in a dedicated environment. VecAlign needs a C compiler (`build-essential` on Ubuntu, or Xcode Command Line Tools on macOS).

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r evaluation/requirements.txt
python -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
python evaluation/setup_vecalign.py
```

The pinned PyTorch version supports CPU and compatible CUDA installations. The example uses CPU; choose `--device cuda` for longer tests on a CUDA GPU. Scores may differ slightly with GPU batching and dependency versions.

## 2. Download the models once

```bash
python evaluation/download_models.py
```

The script runs `hf download` with exact revisions from [models.json](models.json): BAAI/bge-m3, Unbabel/wmt22-comet-da, and the XLM-R tokenizer/config required by COMET. Approximately 4.6 GB of weights are downloaded into the standard Hugging Face cache. Set `HF_HOME` before downloading and scoring if you need a different cache location. Existing matching files are reused. No model weights are committed to this repository.

Scoring uses those cached snapshots with network access disabled. Downloading the XLM-R config/tokenizer is necessary even though the COMET checkpoint already contains encoder weights.

## 3. Run the short example

```bash
python evaluation/run.py --example --output runs/example --device cpu
```

The example contains two original, short Chinese passages, English references, and handwritten demonstration predictions. One prediction omits a sentence. These are interface examples, not benchmark cases or actual model outputs. The example's length label is `example`, so its five-band benchmark aggregate is deliberately `null`.

Read `runs/example/summary.json`. The run also retains:

| Output | Contents |
|---|---|
| `generations.jsonl` | Predictions with preserved text, hashes and available metadata |
| `adapter/` | SEGALE input and case-ID mapping |
| `adapter/system/aligned_spacy_system.jsonl` | Actual source/reference/prediction alignment |
| `comet/` | Window scores, per-document results and diagnostics |
| `chrf2/` | Full-document chrF2 scores |
| `summary.json` | Per-case results, length groups, coverage and five-band macro |

The recorded CPU example result is [example/expected.json](example/expected.json). Its scores are a numerical reference; hardware or library differences can affect the last digits.

## GLM API example

This optional example obtains translations from the **official domestic GLM API**, then passes them to the same evaluator. Complete installation and model download above first. The API helper uses only the Python standard library and makes two short requests for the original example passages.

Endpoint: `https://open.bigmodel.cn/api/paas/v4/chat/completions`; model: `glm-5.3-flash`. The example uses these settings: streaming with usage, temperature 1, top-p 0.95, low reasoning effort, and thinking enabled. The short example reserves 4,096 output tokens, including thinking. Only the final translation is saved as `mt`; references are used by the local scorer, never sent to the API.

From the repository root, enter your key without displaying it, obtain predictions, and score them:

```bash
export BIGMODEL_API_KEY="$(python -c 'import getpass; print(getpass.getpass("GLM API key: "))')"
python evaluation/glm_api_example.py \
  --example --output runs/glm-example/generations.jsonl
python evaluation/run.py \
  --data-root evaluation/example \
  --generations runs/glm-example/generations.jsonl \
  --output runs/glm-example/score --device cpu
```

Read `runs/glm-example/score/summary.json`: `cases` contains the two SEGALE-COMET scores and `scored.segale_comet` their mean. These short examples have no benchmark length bands, so `five_band_macro.value` is `null`. The API outputs are new model translations; the handwritten `example/expected.json` is not their expected result.

The live check on 2026-09-30 completed both official API calls and CPU scoring: 2/2 cases scored, with a case mean of **0.920040**. This verifies the example workflow; new API calls can produce different translations and scores.

To evaluate one real BWB case, extract the archive and use its frozen request:

```bash
tar -xzf bwb/bwb-4k-64k.tar.gz
python evaluation/glm_api_example.py \
  --requests bwb-4k-64k/requests.jsonl \
  --case-id bwb-a3-main-45-start-4k --max-tokens 131072 \
  --output runs/glm-bwb-one/generations.jsonl
python evaluation/run.py \
  --data-root bwb-4k-64k \
  --generations runs/glm-bwb-one/generations.jsonl \
  --output runs/glm-bwb-one/score --device cuda
```

For GuoFeng, use the reconstructed `requests.jsonl` and its case IDs. Omitting `--case-id` sends every request in that file, sequentially. This command sets a 131,072-token output ceiling; check the [context and output limits](../README.md#prediction-input-and-budgets) for the model you use. A single BWB case has 1/84 coverage and no five-band score; scoring a full dataset requires predictions for that dataset.

Use new output files for new runs. The helper preserves token usage, response ID, returned model name, settings and finish reason in each prediction, without saving the key. It stops on an API error, interrupted stream or explicit filter and records that case as non-success; it does not retry automatically. Outputs ending with `length` retain their translation and are scored with `cap_hit=true`.

## 4. Score BWB or reconstructed GuoFeng

Supply saved translations from your model or API in the format below. Check the [input and output budgets](../README.md#prediction-input-and-budgets) before obtaining them. This entrypoint reads predictions and computes scores; it does not call an inference service.

Extract the included BWB archive first:

```bash
tar -xzf bwb/bwb-4k-64k.tar.gz
python evaluation/run.py \
  --data-root bwb-4k-64k \
  --generations predictions/bwb.jsonl \
  --output runs/bwb --device cuda
```

For GuoFeng, follow its README to reconstruct the data, then run:

```bash
python evaluation/run.py \
  --data-root reconstructed/guofeng \
  --generations predictions/guofeng.jsonl \
  --output runs/guofeng --device cuda
```

Each prediction is one UTF-8 JSONL record. The minimum fields are:

```json
{"case_id":"bwb-a3-main-45-start-4k","mt":"Your complete English translation."}
```

Use the exact case IDs from that dataset. For an API response, put its final English translation text in `mt`, rather than the response envelope or reasoning text. `finish_reason`, `input_tokens`, `output_tokens`, `cap_hit`, `model_revision`, `generation_config_sha256` and `output_sha256` are accepted when available. Missing metadata is recorded as unknown (`null`); a missing text hash is computed. Supplied hashes are checked. Predictions are not trimmed, deduplicated or otherwise cleaned.

Missing predictions and explicit non-success records such as `{"case_id":"...","status":"not_admissible"}` are reported separately. They do not receive fabricated zero scores. An empty successful translation is rejected by the SEGALE adapter. Use a new output directory for each run.

`--batch-size` defaults to 8 and `--case-workers` to 1; both can be set explicitly. This portable entrypoint provides CPU/single-GPU evaluation. For multiple GPUs, run disjoint case subsets externally and aggregate per-case results, rather than averaging unequal shard means.

## 5. Read the results

**SEGALE-COMET is the primary metric.** For each dataset, report `five_band_macro.value` from `summary.json`, which weights the five length groups equally. It uses a 0–1 scale; multiply by 100 to report on a 0–100 scale.

| Field in `summary.json` | Meaning |
|---|---|
| `five_band_macro.value` | Primary benchmark score: equal mean of the five band means |
| `five_band_macro.band_means` | SEGALE-COMET for each length band |
| `five_band_macro.coverage` | Scored and total cases for each band |
| `scored.segale_comet` | Mean over individual scored cases, with different weights because bands contain different numbers of cases |
| `scored.diagnostics.cap_hit_cases` / `cap_observed_cases` | Outputs reaching their limit / outputs with known limit status |

Report coverage with the score. A missing entire band produces `null`; partial coverage within a band can still produce a mean and must be disclosed. Unknown limit status does not mean that no output was truncated. BWB and GuoFeng have separate scores. Full-document chrF2 is an auxiliary metric, and a normal finish or high score alone does not establish complete translation.

## Metric settings

- Alignment: spaCy `en_core_web_sm==3.8.0`, public BGE-M3, embedding limit 512 tokens, `max_size=8`, seeded VecAlign adaptive search with `online-stop`.
- Main metric: reference-based `Unbabel/wmt22-comet-da`; null model alignments receive 0, canonical missing-reference units are excluded from scoring.
- Auxiliary metric: full-document chrF2 from SacreBLEU 2.6.0, already on a 0–100 scale.

BWB and GuoFeng are scored and reported separately. This profile uses spaCy and public BGE-M3, not the SEGALE paper's Ersatz/fine-tuned embedding configuration. Saved scores describe the specified profile.
