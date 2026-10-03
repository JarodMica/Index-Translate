# Index-Translate benchmarks

[Hugging Face collection](https://huggingface.co/collections/IndexTeam/index-translate-benchmarks-6ac16fee5057f40abd7d31b7) · [中文索引](../README_zh.md#benchmarks)

This directory mirrors the reviewed evaluation scripts, prompts, licenses and
instructions from four public dataset releases. Data and case metadata are hosted
on Hugging Face. `releases.json` pins their commits and records each delivered
file's size and SHA256 (local `.gitignore` rules are excluded). The downloadable NAtIveLong metadata contains no novels or
reference translations.

| Benchmark | Data / metadata | Evaluation entry point | Guide |
|---|---|---|---|
| MEME | [Meme-Translation-Bench](https://huggingface.co/datasets/IndexTeam/Meme-Translation-Bench), 3,638 cases and 857 definitions | `meme/evaluate.py` | [Guide](meme/README.md) |
| instTrans | [InstTrans-Bench](https://huggingface.co/datasets/IndexTeam/InstTrans-Bench), 3,000 tasks | `insttrans/evaluate.py` | [Guide](insttrans/README.md) |
| SandGlass | [Sandglass-Bench](https://huggingface.co/datasets/IndexTeam/Sandglass-Bench), 3,600 cases | `sandglass/evaluate.py` | [Guide](sandglass/README.md) |
| NAtIveLong | [NAtIveLong](https://huggingface.co/datasets/IndexTeam/NAtIveLong), 84 BWB + 84 GuoFeng case records | `nativelong/evaluation/run.py` and scoring tools | [Guide](nativelong/README.md) |

## Download the pinned data

From the repository root, use Python 3.11 in a virtual environment:

```bash
python3.11 -m venv .venv-benchmarks
source .venv-benchmarks/bin/activate
pip install 'huggingface_hub>=0.36,<2'
python benchmarks/download_data.py all
# Or fetch only one benchmark:
python benchmarks/download_data.py meme
# Verify an existing download without making network requests:
python benchmarks/download_data.py all --verify-only
```

The downloader fetches only omitted data/metadata files at the pinned commits,
checks their size and SHA256, and verifies the mirrored release files listed in `releases.json`. It never
overwrites modified local files. Run it before following a benchmark's guide.
Files remain under their benchmark directory so the original relative paths work.

## Run an evaluation

Install dependencies and run the commands **inside the selected benchmark's
directory**, using its guide. Each benchmark has its own requirements; use separate
virtual environments for NAtIveLong's pinned torch/COMET stack and the API-based
Judges. For example:

```bash
cd benchmarks/sandglass
pip install -r requirements.txt
python prepare_inputs.py --output outputs/model_inputs.jsonl
# Generate saved predictions using your own inference engine, then:
python evaluate.py --predictions outputs/predictions.jsonl \
  --output-dir outputs/syllables --skip-judge
```

`--skip-judge` reports only an offline check, not a full benchmark score. Set the
provider credentials documented by each guide to run a complete Judge evaluation.
Keep references and scoring metadata out of model inputs. Report model revisions,
generation settings, missing-prediction coverage and Judge configuration.

NAtIveLong requires official corpora obtained under their upstream terms. BWB has
metadata and official acquisition instructions; it has no automatic text
reconstruction utility. GuoFeng includes a reconstruction recipe and script. The
synthetic scoring example is bundled under `nativelong/evaluation/example/`.

## Review and licensing

`RELEASE_REVIEW.md` in each directory records the published changes and validation
limits. GitHub scripts match the pinned Hugging Face release. Offline validation
covered input/reference separation, fixed missing-prediction denominators,
malformed Judge scores and existing NAtIveLong unit tests. No live Judge evaluation,
full GPU alignment run or new leaderboard measurement was performed for release.

Licenses are component-specific: MEME and instTrans use CC BY-NC 4.0; SandGlass
uses MIT; NAtIveLong retains its evaluation dependency licenses and upstream corpus
terms. Consult each directory's license and guide. The root repository license
does not replace these terms.
