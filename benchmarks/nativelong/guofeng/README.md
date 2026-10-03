# GuoFeng: reconstruction recipe for 84 long-document cases

This recipe reconstructs 84 Chinese-to-English test cases from six GuoFeng books. The 4K, 8K, 16K, 32K and 64K bands contain 24, 24, 12, 12 and 12 cases respectively. It provides the metadata and extraction coordinates needed to reconstruct the text from the official data.

- Official repository: https://github.com/longyuewangdcu/GuoFeng-Webnovel
- Official registration/download form: https://forms.gle/YqJPkfLgGmACbnbU6
- Upstream terms: https://github.com/longyuewangdcu/GuoFeng-Webnovel#copyright-and-licence
- Cite [WMT 2023 literary task](https://aclanthology.org/2023.wmt-1.3/) and [WMT 2024 literary task](https://aclanthology.org/2024.wmt-1.58/), following the upstream citation guidance.

Obtain GuoFeng V1 Train through the official process and follow its non-commercial research and redistribution conditions. This recipe grants no additional rights to the corpus. The resulting local test text must not be confused with the text-free public recipe or uploaded as part of it.

## Reconstruct

Run from the repository root, using Python 3.10+ and the standard library only. Put the official V1 Train files in `raw/`:

```bash
python3 guofeng/reconstruct.py \
  --source raw/train.zh \
  --reference raw/train.en \
  --output reconstructed/guofeng
```

The script verifies both official file hashes, applies the numerical extraction recipe, and checks all 168 case source/reference hashes before writing output. It recreates `cases.jsonl`, `requests.jsonl`, `references.jsonl`, the SEGALE alignment units and document boundaries, and a manifest. Reconstruction uses frozen endpoints; no tokenizer, inference model or reselection is needed. The output directory must be new.

| File | Purpose |
|---|---|
| `case-index.tsv` | Readable case ID, book ID/name, length band and original first/last lines |
| `case-index.jsonl` | Complete case metadata and expected source/reference hashes |
| `books.jsonl` | Six books and their registered intervals |
| `units.jsonl` | Numerical raw-line and character spans, chapter IDs and null flags |
| `recipe.json` | Coordinate rules, official links, unit count and provenance |
| `document-boundaries.jsonl` | Frozen chapter membership and endpoints |
| `manifest.json`, `prompt.txt` | Frozen test definition and exact prompt |
| `reconstruct.py` | Standalone reconstruction script |

## Coordinates and changes

Raw line numbers are **1-based physical lines in the official files**, including the lines occupied by `<BOOK>` and `<CHAPTER>` tags. First/last lines in the TSV are inclusive bounds, not instructions to copy every intervening line. `units.jsonl` is authoritative for unit selection and ordering.

Character spans are **0-based, half-open Unicode code-point intervals**, after removing only the raw line's CR/LF terminator. Each side's `*_keep_spans` lists the substrings to retain; `[]` yields an empty alignment unit. Join the resulting units with LF, including empty units. Marker/title/metadata deletions are represented by these spans. Selected raw rows require only deletion or blanking, never insertion of replacement text. Unit indices retain their original coordinates.

The six book IDs are `45-jsys` (绝世药神), `86-wzxajddyx` (我只想安静地打游戏), `175-frnmjydl` (夫人你马甲又掉了), `152-dwyx` (低维游戏), `127-dylr` (大医凌然), and `134-kcsfcyxks` (亏成首富从游戏开始). These are project-defined held-out intervals from official Train, not the official WMT test split.

The 127-dylr start-8k and start-32k inputs contain an `undefined` source row; reconstruction preserves that existing defect. The script checks reconstructed text against the published case hashes and writes file checksums for the output.
