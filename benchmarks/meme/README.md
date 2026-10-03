---
pretty_name: Meme Translation Bench
license: cc-by-nc-4.0
language:
  - zh
  - en
task_categories:
  - translation
size_categories:
  - 1K<n<10K
tags:
  - evaluation
  - benchmark
  - meme
  - internet-slang
  - cultural-translation
configs:
  - config_name: default
    data_files:
      - split: test
        path: data/test.jsonl
  - config_name: definitions
    data_files:
      - split: test
        path: data/definitions.jsonl
---

# Meme Translation Bench

Meme Translation Bench is an **evaluation benchmark for meme and
culture-specific translation**. Memes are where translation fails hardest: the
meaning that matters is not the literal reading of the words, but the sense a
community assigns to the expression in that context, whether that is a
homophone, a community alias, a euphemism, or an allusion only insiders
recognize. The benchmark contains **3,638 evaluation instances**, covering
**703 meme terms** and **857 disambiguated senses**, with **2,410 usage
examples** and sense-level translation references grouped by strategy and
quality tier.

The benchmark is released as part of the **Index-Translate** model family and is
referred to as **MEME** in the Index-Translate technical report
([PDF](https://github.com/bilibili/Index-Translate/blob/main/docs/Index_Translate_Series_Technical_Report.pdf),
[LaTeX source](https://github.com/bilibili/Index-Translate/tree/main/Index-Translate-tech-report)).
See [Citation](#citation) for how to refer to it.

## Task and motivation

Each instance pairs a meme-bearing text with the meme it contains and the
disambiguated sense being used, together with usage examples and tiered
reference renderings. The task is to translate the full text into the target
language while preserving the meme's context-dependent meaning, tone, and
communicative function. The benchmark targets four recurring difficulties:

- Recognizing nonliteral or newly coined meanings, including homophones,
  abbreviations, and allusions.
- Disambiguating expressions whose meanings vary across communities and contexts.
- Conveying culture-specific concepts to readers without the same background knowledge.
- Preserving pragmatic effects such as irony, humor, stance, and informal style.

The translation model receives the source text and, when available, the video
title and description as context. Sense annotations, usage examples, and
translation references are reserved for evaluation. This release covers Chinese
user-generated video content translated into English.

## Dataset statistics

| Item | Count |
| --- | ---: |
| Evaluation instances | 3,638 |
| Meme terms | 703 |
| Disambiguated senses | 857 |
| Usage examples | 2,410 |
| Terms with multiple annotated senses | 120 (17.1%) |

| Source text type | Value in data | Instances |
| --- | --- | ---: |
| Comments | `review` | 2,162 |
| On-screen comments / danmaku | `bullet` | 881 |
| Video titles | `title` | 527 |
| Video descriptions | `description` | 68 |

Usage examples are supporting sense annotations, not additional evaluation
instances. Counts of senses and examples refer to unique annotations: these
annotations are repeated across rows associated with the same sense.

## Data collection and annotation

Meme-containing texts were collected from Bilibili user-generated content:
comments, on-screen comments, video titles, and video descriptions. The release
contains 3,638 evaluation instances covering 703 meme terms and 857
disambiguated senses, supported by 2,410 sense-level usage examples and
strategy-grouped translation references in three quality tiers.

Sense definitions and text-to-sense assignments were proposed with LLM and
search-assisted workflows, then cross-checked and corrected by two community
experts. For each sense, LLMs proposed translation strategies and candidate
renderings, which three bilingual experts with cross-cultural experience
cross-checked into quality tiers: accurate and natural, imperfect but usable, or
unusable. Each term–sense pair contributes one to three usage examples and one
to six evaluation instances, and the two identifier sets are disjoint.

The release applies anonymization to the collected text: emotes, mentions, links
and other personal or contact details are represented by placeholders rather
than their original form.

## Files and schema

```text
README.md
manifest.json
data/test.jsonl
data/definitions.jsonl
prepare_inputs.py
evaluate.py
eval/
    __init__.py
    prompts.py
    judge_client.py
    score_parser.py
    metrics.py
requirements.txt
```

The dataset ships two views of the same benchmark, exposed as the `default` and
`definitions` configurations:

- `data/test.jsonl` — one evaluation instance per line, self-contained. Sense
  annotations are repeated on every instance that uses them, so `prepare_inputs.py`
  and `evaluate.py` need no second file.
- `data/definitions.jsonl` — one sense per line, 857 rows. The term- and
  sense-level view the benchmark was built on, without the per-instance
  duplication.

`manifest.json` records release statistics, prompt versions, and the SHA-256
checksums of both data files.

| Field | Type | Description |
| --- | --- | --- |
| `sentence_id` | string | Unique evaluation instance identifier; use it to match predictions. |
| `original_text` | string | Full Chinese text to translate. |
| `term` | string | Target meme expression. |
| `term_id` | string | Meme term identifier. |
| `definition_id` | string | Identifier of the sense assigned to this instance. |
| `text_type` | string | `review`, `bullet`, `title`, or `description`. |
| `video_title` | string | Available video title; empty if unavailable. |
| `video_description` | string | Available video description; empty if unavailable. |
| `definition` | string | Chinese explanation of the assigned sense. |
| `examples` | list of objects | Usage examples, each with `sentence_id` and `original_text`. |
| `translation_references` | list of objects | Acceptable sense-level renderings, grouped by strategy. |
| `translation_references_0.5_score` | list of objects | Imperfect but usable sense-level renderings, grouped by strategy. |
| `translation_references_0_score` | list of objects | Unacceptable sense-level renderings, grouped by strategy. |

Each reference group has `strategy` (a Chinese label) and `references` (a list
of candidate English renderings). An empty list means that no references in
that tier were provided. These are **sense-level renderings of the meme**, not
gold translations of the full evaluation sentence. Acceptable translations are
not restricted to the listed candidates.

Source text retains informal spellings, punctuation, and placeholders such as
`<EMOTE-placeholder-0>`; the underlying emote images are not provided.

`data/definitions.jsonl` uses the same annotation fields minus the per-instance
ones:

| Field | Type | Description |
| --- | --- | --- |
| `definition_id` | string | Sense identifier; joins to the `default` configuration. |
| `term` | string | Meme expression. |
| `term_id` | string | Meme term identifier. |
| `definition` | string | Chinese explanation of the sense. |
| `examples` | list of objects | Usage examples for this sense. |
| `translation_references` | list of objects | Acceptable sense-level renderings. |
| `translation_references_0.5_score` | list of objects | Imperfect but usable renderings. |
| `translation_references_0_score` | list of objects | Unacceptable renderings. |

```python
from datasets import load_dataset

senses = load_dataset("IndexTeam/Meme-Translation-Bench", "definitions", split="test")
print(len(senses))  # 857
print(senses[0]["term"], senses[0]["definition"][:40])
```

## Loading the data

Install the optional loading and evaluation dependencies:

```bash
pip install -r requirements.txt
```

Load the published dataset:

```python
from datasets import load_dataset

dataset = load_dataset("IndexTeam/Meme-Translation-Bench", split="test")
print(len(dataset))  # 3638
print(dataset[0]["original_text"])
```

Or load a local copy from the repository root:

```python
from datasets import load_dataset

dataset = load_dataset(
    "json", data_files={"test": "data/test.jsonl"}, split="test"
)
```

## Generating translations

Export the standard model inputs from the repository root:

```bash
python prepare_inputs.py --output outputs/model_inputs.jsonl
```

Each output row contains only `sentence_id` and a chat-format `messages` list.
Send **only `messages`** to the translation model; use `sentence_id` locally to
associate the returned translation with the instance. Do not send the complete
dataset row to the model, since it contains evaluation annotations.

The standard prompt requests English translation only, with no explanations.
It provides the video title and description when available as context, omits
fields identical to the text being translated, and uses an explicit placeholder
when no context is available. Prompt construction is defined in
[`eval/prompts.py`](eval/prompts.py).

Use any inference engine, then save one final translation per instance as JSONL:

```python
import json

# `translations` must align with the ordered rows read from model_inputs.jsonl.
with open("outputs/model_inputs.jsonl", encoding="utf-8") as handle:
    inputs = [json.loads(line) for line in handle]

# Fill this list with your model's final English translations.
translations = [...]  # one string per input
assert len(translations) == len(inputs)
with open("outputs/predictions.jsonl", "w", encoding="utf-8") as handle:
    for row, translation in zip(inputs, translations):
        handle.write(json.dumps({
            "sentence_id": row["sentence_id"],
            "prediction": translation,
        }, ensure_ascii=False) + "\n")
```

Record the model revision, inference engine, decoding parameters, and reasoning
setting with reported results. Predictions should contain final translations
without reasoning traces or other commentary.

## Evaluation protocol

An LLM Judge receives the source text, target meme, assigned definition, usage
examples, tiered translation references, and candidate translation. The Judge
prompt does not include the video context. The annotations ground the judgment
in the intended sense and documented translation choices.

| Score | Interpretation |
| --- | --- |
| 1 | Accurate and natural; conveys the meme and the overall meaning appropriately. |
| 0.5 | Conveys the core meaning but has shortcomings in expression or fluency. |
| 0 | Mistranslates the meme or the overall meaning. |

The primary metric is the instance-weighted mean score over **all 3,638
instances**, on a 0–1 scale. Multiply by 100 to report a percentage. Missing or
empty predictions receive zero and remain in the denominator. Duplicate or
unknown prediction identifiers are rejected. Reference matching is semantic,
not exact string matching.

The default Judge is `gemini-2.5-flash` with temperature `0` and a maximum of
`2048` output tokens, accessed through an OpenAI-compatible endpoint. Configure
an endpoint and credentials for a provider you have access to; no provider
credentials are bundled.

```bash
export JUDGE_API_BASE="https://YOUR_PROVIDER/v1"
export JUDGE_API_KEY="YOUR_API_KEY"

python evaluate.py \
  --predictions outputs/predictions.jsonl \
  --output-dir outputs/evaluation \
  --judge-model gemini-2.5-flash
```

The evaluator writes per-instance scores, aggregate metrics, a reusable response
cache, and a score-parsing audit. The summary includes prediction coverage and
breakdowns by text type. Provider failures abort the run after retries rather
than becoming quality scores. Unparseable Judge responses receive zero and are
listed for review in `score_parse_audit.json`; review these when interpreting
results. Successful cached responses can be reused when rerunning the same
configuration. This public release validates complete numeric score tokens;
invalid values such as `Score: 0.1` cannot be misread as 1. Nonstandard responses
still score zero and appear in the parsing audit.

`--limit N` selects the first N instances for a smoke check and marks the summary
as non-formal. For this mode, provide predictions only for the selected instances.
Subset scores are not full-benchmark results.

## Reported results

Mean score over all 3,638 instances, as published in the Index-Translate
technical report. Index-Translate models were run at temperature `0` with a
`2048`-token output limit and reasoning disabled; the other systems were run
with their own default non-thinking sampling recipes, so they are reproduced
here as recorded sources rather than as a controlled comparison.

| Model | MEME |
| --- | ---: |
| DeepSeek-V4.1-Flash | 0.7424 |
| **Index-Translate-35B-A3B** (preview) | **0.7405** |
| **Index-Translate-9B** | **0.7387** |
| GPT-5.6-Sol | 0.7194 |
| Gemini 3.5 Flash Lite | 0.7034 |
| North-Small-Translate (218B-A25B) | 0.6836 |
| Qwen3.5-35B-A3B | 0.6447 |
| **Index-Translate-2B** | **0.6443** |
| Hy-MT2-30B-A3B | 0.5812 |
| Qwen3.5-9B | 0.5728 |
| Hy-MT2-7B | 0.5139 |
| TranslateGemma-12B-IT | 0.4281 |
| Hy-MT2-1.8B | 0.3643 |
| Qwen3.5-2B | 0.2062 |

The 35B-A3B Index-Translate entry is a preview. Scores obtained with a different
Judge model, provider, or decoding configuration are not comparable to this
table; report the Judge configuration alongside any new numbers.

## Citation

```bibtex
@misc{indextranslate2026memebench,
  title        = {Meme Translation Bench},
  author       = {{Index LLM Team}},
  year         = {2026},
  howpublished = {Hugging Face dataset},
  url          = {https://huggingface.co/datasets/IndexTeam/Meme-Translation-Bench},
  note         = {MEME benchmark of the Index-Translate model family}
}
```

Cite the technical report for the model family, the training recipe, and the
full evaluation suite:

```bibtex
@misc{indextranslate2026,
  title        = {Index-Translate: Controllable Multilingual Translation for
                  Content Production},
  subtitle     = {Text, Speech, Controlled Dubbing, and Long-Document Translation},
  author       = {{Index LLM Team}},
  year         = {2026},
  howpublished = {Technical report},
  url          = {https://github.com/bilibili/Index-Translate}
}
```

## Links

- Technical report: [Index-Translate Technical Report](https://github.com/bilibili/Index-Translate/blob/main/docs/Index_Translate_Series_Technical_Report.pdf)
- Models: [Hugging Face collection](https://huggingface.co/collections/IndexTeam/index-translate-6abab639ab144cac37c4c519) · [ModelScope](https://www.modelscope.cn/organization/IndexTeam)
- Code: [github.com/bilibili/Index-Translate](https://github.com/bilibili/Index-Translate)

## Intended use and limitations

The dataset is intended for evaluating contextual meme translation. Treat its
test instances and evaluation annotations as held-out material when reporting
benchmark results.

Coverage is limited to the sampled communities, expressions, and language pair.
Meme meanings evolve over time, and a finite set of references cannot exhaust
all valid translations. User-generated text can contain profanity, sarcasm, or
offensive expressions; inclusion documents usage and does not endorse the views
expressed. Expert-reviewed annotations may still contain errors.

LLM Judge scores depend on the model, provider, and scoring implementation and
are not a substitute for human review. Report the Judge configuration alongside
scores. This release does not include a separate human-versus-Judge validation
set or raw agreement annotations.

## License

This dataset is released under the **Creative Commons Attribution–NonCommercial
4.0 International (CC BY-NC 4.0)** license. You may share and adapt the dataset
for non-commercial purposes with appropriate attribution. See [LICENSE](LICENSE)
and the [full license text](https://creativecommons.org/licenses/by-nc/4.0/).

## Benchmark collection

Part of the [Index-Translate Benchmarks collection](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7).
