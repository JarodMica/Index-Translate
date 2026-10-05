---
pretty_name: Sandglass Syllable-Controlled Translation Benchmark
license: mit
language: [zh, en, ja, es, ar]
task_categories: [translation]
size_categories: [1K<n<10K]
tags: [benchmark, evaluation, syllable-control, constrained-translation]
configs:
  - config_name: default
    data_files:
      - split: test
        path: sandglass_bench.jsonl
---

# Sandglass: Syllable-Controlled Translation Benchmark

Sandglass is a benchmark for evaluating syllable-controlled translation quality and controllability. It tests whether models can translate Chinese video subtitles into target languages while adhering to precise syllable count constraints.

## Overview

- **3,600 test cases**: 300 real video subtitles × 4 languages × 3 length targets
- **Languages**: English (en), Japanese (ja), Spanish (es), Arabic (ar)
- **Length targets**: short (0.75×), natural (1.0×), long (1.25×) relative to duration-based anchor
- **Evaluation**: Syllable accuracy + LLM-judged translation quality

## Quick Start

```bash
pip install -r requirements.txt
hf download IndexTeam/Sandglass-Bench --repo-type dataset --local-dir ./Sandglass-Bench
cd Sandglass-Bench
python prepare_inputs.py --output outputs/model_inputs.jsonl
```

Send each row's `messages` to your translation system. Save JSONL predictions
as `{"case_id": "...", "prediction": "final translation"}`; do not send
labels or metadata to the model. Preserve the exact prompts and record the
model revision and decoding settings.

```bash
export JUDGE_API_BASE="https://YOUR_PROVIDER/v1"
export JUDGE_API_KEY="YOUR_API_KEY"
python evaluate.py --predictions outputs/predictions.jsonl --output-dir outputs/evaluation
# Offline syllable-only checks (not full benchmark scores):
python evaluate.py --predictions outputs/predictions.jsonl --output-dir outputs/syllables --skip-judge
```

The evaluator accepts saved predictions from any inference engine. It does not
load a GPU model or bundle provider credentials. The default Judge is
`gemini-2.5-flash`; its request parameters are recorded in the summary, with the
endpoint reduced to scheme+host (embedded credentials, path and query are never
written out).

## Data Format

`sandglass_bench.jsonl` contains 3,600 lines, each with:

```json
{
  "case_id": "uuid:en:natural",
  "prompt": [{"role": "user", "content": "请将下面这句中文视频字幕翻译成英语，译文控制为 12 个音节。\n..."}],
  "label": "reference translation (en only)",
  "metadata": {
    "uuid": "unique-id",
    "fenqu": "category (二次元/影视/旅游出行/游戏/知识)",
    "duration": 1.9,
    "target_language": "en",
    "target_syllables": 12,
    "target_kind": "natural",
    "source": "Chinese subtitle text",
    "summary": "video summary",
    "up_context": "previous subtitle",
    "down_context": "next subtitle"
  }
}
```

## Evaluation Metrics

### Syllable Accuracy
- **mean|dev|**: Mean absolute relative deviation from target
- **±1**: Percentage within 1 syllable of target
- **dev≤5%/10%/20%**: Percentage within relative deviation thresholds
- **syllable_reward**: Continuous score (1.0 for ±1 or dev≤5%, linearly decaying from 5% to 50%, 0.0 for dev≥50%)

### Translation Quality
- **quality**: LLM judge score (0/0.5/1), evaluates translation correctness without reference
- Judge is informed of duration constraint and tolerates reasonable compression/expansion

### Controllability
- **slope**: Regression slope of (target, output) syllables for same sentence across 3 length targets (ideal: 1.0)
- **q_gap_short/long**: Quality difference between natural and short/long targets

### Final Score
```
score = (syllable_reward + quality) / 2
```

## Syllable Calculation

The benchmark uses `syllable_calculation.py` (v3), which supports 22 languages with:
- **Reliability**: `syllable_calculation.py`'s `RELIABILITY` map rates all 22 languages `high` (2026-08-04 espeak-ng IPA validation; `medium`/`low` are empty). ja/ar are exempt from that baseline and are validated by production RL instead.
- **Method**: Language-specific rules (pyphen dictionaries, script-based counting, vowel heuristics)
- **Number expansion**: Digits converted to words before counting

```python
from syllable_calculation import cal_syllable_count

count = cal_syllable_count("Hello world", lang='en')  # 3
count = cal_syllable_count("こんにちは", lang='ja')   # 5
```

## Target Syllable Calculation

Targets are duration-based, independent of Chinese character count:

```
anchor_syllables = duration_seconds × speech_rate
```

Speech rates (syllables/second):
- English: 6.19
- Japanese: 7.84
- Spanish: 7.82
- Arabic: 8.4

Three targets per sentence:
- **short**: round(anchor × 0.75), -1 if collides with natural
- **natural**: round(anchor × 1.0)
- **long**: round(anchor × 1.25), +1 if collides with natural

## Benchmark Statistics

| Dimension | Value |
|---|---|
| Total items | 3,600 |
| Source sentences | 300 (5 categories × 60) |
| Videos | 83 |
| Languages | 4 (en/ja/es/ar) |
| Length targets | 3 (short/natural/long) |
| Subtitle duration | 0.84-7.0s (median 2.3s) |
| Chinese chars | 10-40 (median 13) |
| Target syllables (natural) | en: 14, ja: 18, es: 18, ar: 19 (median) |

## Results Format

`<output-dir>/scores.jsonl` contains per-item results (field names as written by `evaluate.py`):

```json
{
  "case_id": "uuid:en:natural",
  "uuid": "...",
  "target_language": "en",
  "target_kind": "natural",
  "target_syllables": 12,
  "prediction": "If we go by the technological hierarchy of the Ultraman world",
  "hyp_syllables": 13,
  "abs_diff": 1,
  "dev": 0.0833,
  "signed_dev": 0.0833,
  "syllable_reward": 1.0,
  "hit_pm1": 1,
  "hit_strict5": 0,
  "hit_10": 1,
  "hit_20": 1,
  "quality": 1.0,
  "score": 1.0
}
```

## Evaluation protocol and release changes

All 3,600 rows remain in the denominator. Missing or empty predictions score
zero; duplicate and unknown case IDs are rejected. Judge provider failures or
unparseable responses abort the run instead of becoming translation scores.
`--skip-judge` and `--limit` runs are explicitly marked non-formal. Only final
translations should be supplied, without reasoning traces or wrapper text.

The published data retains every source prompt, label and scoring field. Only
`metadata.file_name` (video provenance filename) was removed; a stable composite
`case_id` was added. The original syllable-counting modules are unchanged.

This release replaces the source script's GPU generation and positional cache
with an engine-independent prediction interface and cache keyed by the complete
Judge prompt and request configuration. Strict 0/0.5/1 parsing prevents responses
such as `0.1` from silently becoming 1. Subset scores are not full-benchmark
results, and scores under a different Judge or generation recipe are not
assumed comparable to the historical results below.

Controllability slope is calculated for each source/language over its three
length targets, then averaged over groups. Quality gaps are the mean paired
short-minus-natural and long-minus-natural quality scores. Per-language and
per-length-target metrics, coverage, exact data hash, and Judge parameters are
saved to `summary.json`.

## Citation

If you use this benchmark, please cite:

```bibtex
@misc{cui2026homuratamingsandglasstimeconstrained,
      title={HOMURA: Taming the Sand-Glass for Time-Constrained LLM Translation via Reinforcement Learning},
      author={Ziang Cui and Mengran Yu and Chenyu Shi and Yingxuan Shi and Tianjiao Li},
      year={2026},
      eprint={2601.10187},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2601.10187},
}
```

## License

The benchmark data and evaluation code are released under MIT License. The syllable calculation module includes dependencies (pyphen, fugashi, num2words) with their own licenses.

## Leaderboard

### Top Models

| Model | Type | Quality | mean\|dev\| | ±1 | dev≤5% | Slope |
|---|---|---|---|---|---|---|
| **index-homura** | Ours (9B RL) | 0.786 | 0.069 | 74.4% | 50.0% | 0.968 |
| gpt-5.6-sol | External API | 0.872 | 0.322 | 42.5% | 28.9% | 0.891 |
| Hy-MT2-7B | External OSS | 0.856 | 0.317 | 18.1% | 8.8% | 0.195 |
| DeepSeek-v4-flash | External API | 0.874 | 0.337 | 16.6% | 7.5% | 0.153 |
| Hy-MT2-30B-A3B | External OSS | 0.755 | 0.274 | 21.0% | 10.6% | 0.340 |
| Qwen3.5-9B | External OSS | 0.718 | 0.325 | 15.6% | 6.8% | 0.430 |
| Qwen3.5-35B-A3B | External OSS | 0.786 | 0.346 | 13.3% | 5.8% | 0.249 |
| Hunyuan-MT-7B | External OSS | 0.719 | 1.058 | 12.3% | 7.4% | 0.031 |
| Hy-MT2-1.8B | External OSS | 0.590 | 0.708 | 14.6% | 7.9% | 0.222 |
| Qwen3.5-2B | External OSS | 0.492 | 0.515 | 12.5% | 4.5% | 0.036 |


## Benchmark collection

Part of the [Index-Translate Benchmarks collection](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7).
