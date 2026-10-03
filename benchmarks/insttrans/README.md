---
pretty_name: Instruction-Following Translation Bench
license: cc-by-nc-4.0
language:
  - zh
  - en
  - ja
  - ko
  - ar
  - de
  - es
  - fil
  - fr
  - hi
  - id
  - it
  - ms
  - nl
  - pl
  - pt
  - ro
  - ru
  - sv
  - th
  - tr
  - vi
task_categories:
  - translation
size_categories:
  - 1K<n<10K
tags:
  - evaluation
  - benchmark
  - instruction-following
  - constrained-translation
  - subtitle
  - terminology
configs:
  - config_name: default
    data_files:
      - split: test
        path: data/test.jsonl
---

# Instruction-Following Translation Bench

Instruction-Following Translation Bench measures whether a translation system can
**obey explicit production constraints while translating**. Real content pipelines
rarely want a free translation: a subtitle line has to fit the time it is on
screen, a glossary term has to come out exactly as the glossary says, a JSON
payload has to come back with its keys intact, and a hashtag has to survive
untranslated so it still links. A system that translates beautifully but breaks
the structure around the text cannot be shipped.

The benchmark contains **3,000 evaluation instances** across **10 constraint
types**, **10 content domains** and **61 language pairs**, built from Bilibili
production content: subtitles, comments, on-screen comments, posts, novels,
columns, books, web text and academic papers.

The benchmark is released as part of the **Index-Translate** model family and is
referred to as **InstTrans** in the Index-Translate technical report.
See [Citation](#citation) for how to refer to it.

## Task and motivation

Each instance gives the model a source text plus a numbered list of constraints,
and asks for a translation that satisfies all of them. Constraints are not
suggestions: the scoring treats five of them as gates, so a single structural
break zeroes the instance no matter how good the prose is.

The benchmark separates two things that are usually conflated:

- **Instruction following** — did the output keep the JSON keys, hit the glossary,
  preserve the hashtag, respect the syllable budget, keep the line breaks?
- **Translation quality** — is the translation itself accurate and fluent?

Both are reported. A system can score well on quality and badly on
instruction following, and that gap is the thing this benchmark exists to expose.

## Constraint types

Ten constraint types, split by how they are scored. **Hard** constraints are
checked by deterministic rules and act as gates. **Soft** constraints are scored
0 / 0.5 / 1 by an LLM Judge and average into a multiplier.

| Constraint | Type | Instances | What it requires |
| --- | --- | ---: | --- |
| `format_preserve` | hard | 2,098 | Keep JSON / HTML / Markdown / placeholder structure intact |
| `syllable_order` | hard | 601 | Shorter on-screen durations get fewer syllables in the translation |
| `term_compliance` | hard | 502 | Render each glossary term exactly as specified |
| `social_preserve` | hard | 316 | Leave hashtags, `@mentions` and emote codes untranslated |
| `layout_break` | hard | 266 | Preserve line breaks, indentation and table alignment |
| `style_consistency` | soft | 633 | Hold the requested register (casual / neutral / formal) |
| `term_cross_sentence` | soft | 508 | Use one rendering of a term throughout the document |
| `academic_format_preserve` | soft | 412 | Leave LaTeX and citation markers untranslated |
| `context_disambiguate` | soft | 42 | Resolve a stated ambiguity the way the instruction says |
| `coref_resolution` | soft | 24 | Keep pronoun reference consistent with the stated antecedent |

Instances carry 1–5 constraints each: 1,307 have one, 1,138 two, 426 three, 104
four, and 25 five. The 5,402 constraint annotations over 3,000 instances mean the
average instance is scored on 1.8 constraints at once, which is where systems
tend to fail — satisfying a glossary while also preserving JSON is harder than
either alone.

### The syllable constraint

`syllable_order` is the least obvious of the ten, and it is the one subtitle
production actually needs. Each subtitle instance ships `duration_s`, the
on-screen duration of every line. The requirement is not an absolute syllable
count but the **ordering**: if line 6 is on screen longer than line 2, its
translation should not be shorter in syllables.

Scoring is pairwise. For every pair of lines with different durations, the pair is
an inversion if the duration ordering and the syllable-count ordering disagree.
Concordance is `1 - inversions / comparable_pairs`, and the constraint passes at
**concordance >= 0.9**. Pairs with equal syllable counts are not inversions, and
pairs with equal durations are not comparable. Syllable counting is
language-specific (see [`eval/syllable.py`](eval/syllable.py)) and handles
numbers, acronyms and mixed scripts.

## Dataset statistics

| Item | Count |
| --- | ---: |
| Evaluation instances | 3,000 |
| Constraint types | 10 |
| Constraint annotations | 5,402 |
| Language pairs | 61 |
| Target languages | 22 |
| Content domains | 10 |

| Domain | Value in `domain` | Instances |
| --- | --- | ---: |
| Bilibili posts | `B站动态` | 320 |
| Novels | `小说` | 303 |
| OGV subtitles | `ogv字幕` | 302 |
| On-screen comments | `弹幕` | 302 |
| Comments | `评论` | 300 |
| Columns | `专栏文章` | 300 |
| Academic papers | `学术论文` | 299 |
| UGC subtitles | `UGC字幕` | 299 |
| Books | `书籍` | 293 |
| Web text | `网页文本` | 282 |

The dominant direction is Chinese into 21 other languages (2,419 instances), plus
313 English-source instances and 14–15 instances from each of 19 other source
languages. `zh` is also the most common target (296 instances), from the
English-source and other-source material.

Domains do not carry every constraint. On-screen comments, comments and posts only
ever carry `format_preserve`, `social_preserve` and `term_compliance`;
`syllable_order` appears only on subtitles, since only subtitles have durations;
`academic_format_preserve` concentrates in papers. This is a property of the
content, not a sampling gap — a hashtag constraint on an academic paper would be
artificial.

## Files and schema

```text
README.md
manifest.json
LICENSE
requirements.txt
data/test.jsonl
prepare_inputs.py
evaluate.py
eval/
    __init__.py
    constraints.py
    prompts.py
    judge_client.py
    metrics.py
    syllable.py
```

`manifest.json` records release statistics, prompt versions, the redaction policy
and the SHA-256 checksum of the data file.

| Field | Type | Description |
| --- | --- | --- |
| `case_id` | string | Unique instance identifier; use it to match predictions. |
| `prompt` | string | The complete instruction sent to the model, including source text and constraints. |
| `reference` | string | Reference translation satisfying the constraints. Used by the quality Judge, never sent to the model. |
| `source_lang` | string | Source language code. |
| `target_lang` | string | Target language code. |
| `source_text` | string | Source text alone, extracted from `prompt`. Convenience field for rule checking. |
| `constraints` | list of strings | The numbered constraint lines, verbatim from `prompt`. Aligned 1:1 with `constraint_ids`. |
| `constraint_ids` | list of strings | Machine-readable constraint types for this instance. |
| `scenario` | string | Coarse content grouping (7 values). |
| `domain` | string | Fine content grouping (10 values); several domains share one scenario. |
| `duration_s` | list of floats | Per-line on-screen duration in seconds. Present on the 601 subtitle instances with `syllable_order`. |
| `batch_size` | integer | Number of sentences in a multi-sentence instance. Present when applicable. |
| `style` | object | Requested register, e.g. `{"formality": "casual"}`. Present when the instance specifies one. |

`prompt` is the single source of truth for what the model sees. `source_text` and
`constraints` are derived from it with the same extraction the scorer uses, so
they cannot drift apart.

Source text retains its original informal spelling, punctuation, emote codes and
`@mentions`; the `social_preserve` constraint depends on those surviving
translation, so they are not masked. Provenance identifiers (video and post IDs,
internal file paths) and authorship fields were removed from the release;
`manifest.json` records exactly which.

Contact details that can reach a person or a group chat — phone numbers, email
addresses, QQ group numbers and WeChat IDs, mostly appearing in promotional spam
inside user-generated text — are replaced by bare uppercase tokens
(`PHONE_REDACTED`, `EMAIL_REDACTED`, `QQ_GROUP_REDACTED`, `WECHAT_ID_REDACTED`)
in `prompt`, `reference` and `source_text`. This touches 15 of the 3,000
instances. No constraint scores contact details, and the masks were chosen to
contain no regex-special characters so they cannot be mistaken for an HTML tag, a
placeholder or a Markdown link by the format checkers; scoring the references
gives the same IF_Score before and after masking, with zero per-constraint
verdict changes. URLs and `@mentions` are kept, since `format_preserve` and
`social_preserve` score them.

## Loading the data

```bash
pip install -r requirements.txt
```

```python
from datasets import load_dataset

dataset = load_dataset(
    "IndexTeam/InstTrans-Bench", split="test"
)
print(len(dataset))            # 3000
print(dataset[0]["prompt"])
print(dataset[0]["constraint_ids"])
```

## Generating translations

Export the standard model inputs from the repository root:

```bash
python prepare_inputs.py --output outputs/model_inputs.jsonl
```

Each output row contains only `case_id` and a chat-format `messages` list. Send
**only `messages`** to the model; use `case_id` locally to associate the returned
translation with the instance. Do not send the complete dataset row, since it
contains the reference translation.

Use any inference engine, then save one translation per instance as JSONL:

```python
import json

with open("outputs/model_inputs.jsonl", encoding="utf-8") as handle:
    inputs = [json.loads(line) for line in handle]

translations = [...]  # one string per input, aligned with the rows above
assert len(translations) == len(inputs)
with open("outputs/predictions.jsonl", "w", encoding="utf-8") as handle:
    for row, translation in zip(inputs, translations):
        handle.write(json.dumps({
            "case_id": row["case_id"],
            "prediction": translation,
        }, ensure_ascii=False) + "\n")
```

Predictions should be final translations without reasoning traces or commentary.
Many instances require the output to be a JSON object with the source's keys, so
any wrapper text around it will fail `format_preserve` on its own. Record the
model revision, inference engine, decoding parameters and reasoning setting with
reported results.

## Evaluation protocol

Scoring has two independent dimensions.

**IF_Score** is the headline metric, on a 0–1 scale:

```
IF_Score = product(hard_constraint_passed) x mean(soft_constraint_scores)
```

Every hard constraint is a gate: one failure sets the product to 0 and the
instance scores 0 regardless of the soft scores. Soft constraints are scored
0 / 0.5 / 1 by the Judge and averaged. An instance with no soft constraints uses a
multiplier of 1.0, so it scores either 1.0 or 0.0.

**Translation quality** is scored separately by an LLM Judge that sees the source,
the reference and the candidate, and is told to ignore format and constraints
entirely. It is reported alongside IF_Score, not folded into it.

| Score | Quality interpretation |
| --- | --- |
| 1 | Accurate and natural; no serious errors, minimal minor ones. |
| 0.5 | Minor errors only, or few serious ones (under 10% of sentences); readable overall. |
| 0 | Many serious errors (over 10% of sentences); quality badly affected. |

Hard constraints are checked by deterministic rules in
[`eval/constraints.py`](eval/constraints.py), so that part of the score is
reproducible without a Judge at all:

```bash
python evaluate.py \
  --predictions outputs/predictions.jsonl \
  --output-dir outputs/evaluation \
  --skip-judge
```

The full run needs a Judge. The default is `gpt-5.6-sol`. Configure an endpoint
and credentials for a provider you have access to; none are bundled.

```bash
export JUDGE_API_BASE="https://YOUR_PROVIDER/v1"
export JUDGE_API_KEY="YOUR_API_KEY"

python evaluate.py \
  --predictions outputs/predictions.jsonl \
  --output-dir outputs/evaluation \
  --judge-model gpt-5.6-sol
```

The client picks a request shape from the model name. A reasoning model
(`gpt-5*`, `gpt-6*`, `o1`/`o3`/`o4`) goes to `/responses` with a 4,096-token
output budget and reasoning effort `none`; every other model goes to
`/chat/completions` at temperature `0` with a 2,048-token limit. Reasoning is
disabled so the Judge scores rather than deliberates, and the response cache keys
on the endpoint and its parameters, so switching Judge models never serves a
verdict produced under a different configuration.

If your provider serves a reasoning model on `/chat/completions` instead, pass a
model name outside those prefixes, or adjust `uses_responses_endpoint` in
[`eval/judge_client.py`](eval/judge_client.py).

The evaluator writes per-instance scores (`scores.jsonl`), aggregate metrics
(`summary.json`) and a reusable response cache. The summary breaks results down by
constraint, scenario, domain and language pair, and reports per-constraint pass
rates so a low IF_Score can be traced to the constraint causing it. Missing or
empty predictions score 0 and stay in the denominator. Duplicate or unknown
`case_id`s are rejected. Provider failures and invalid or incomplete Judge scores abort the run rather
than silently becoming quality scores. This public release validates the exact
0/0.5/1 verdict, including the soft-constraint entries; malformed verdicts are
not excluded from the denominator or treated as a passed instruction.

`--limit N` scores the first N instances as a smoke check and marks the summary as
non-formal. Subset and `--skip-judge` scores are not full-benchmark results.

Scores obtained with a different Judge model, provider or decoding configuration
are not comparable. Report the Judge configuration alongside any new numbers.

## Links

- Technical report: [Index-Translate Technical Report](https://github.com/bilibili/Index-Translate)

## Citation

```bibtex
@misc{indextranslate2026insttransbench,
  title        = {Instruction-Following Translation Bench},
  author       = {{Index LLM Team}},
  year         = {2026},
  howpublished = {Evaluation benchmark},
  note         = {InstTrans benchmark of the Index-Translate model family}
}
```

Cite the technical report for the model family, the training recipe, and the full
evaluation suite:

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

## License

This dataset is released under the **Creative Commons
Attribution–NonCommercial 4.0 International (CC BY-NC 4.0)** license. You may
share and adapt the dataset for non-commercial purposes with appropriate
attribution. See [LICENSE](LICENSE) and the
[full license text](https://creativecommons.org/licenses/by-nc/4.0/).

## Benchmark collection

Part of the [Index-Translate Benchmarks collection](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7).
