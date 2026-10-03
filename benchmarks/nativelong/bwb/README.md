# BWB metadata for 84 long-document cases

This public release contains **no BWB text or reference translations**. Obtain
BWB Train from the [official download](https://drive.google.com/drive/folders/12K1-DWmpEdqkaR_61aogdywsALDg4z1L)
and follow the [upstream terms](https://github.com/EleanorJiang/BlonDe/blob/main/TERMS_OF_USE).
These are project-defined held-out windows from six books, not the official
80-document annotated test. Bands 4K/8K/16K/32K/64K contain 24/24/12/12/12 cases.

## Delivered metadata

- `case-index.jsonl`: case IDs, bands, chapter/alignment endpoints and expected
  source/reference hashes; no source/reference text.
- `chapter-map.jsonl`: 1,924 ordered chapters mapped to physical upstream records.
- `books.jsonl`: book names, IDs and upstream archive-member information.
- `manifest.json` and `provenance.json`: the original construction and provenance.
- `prompt.txt`: the exact generation prompt, `zh-en-document-v3`.

`ordered_record_1based` is a project-restored record position, not a title chapter
number. `official_aggregate_record_1based` is the physical record in
`train/<book_id>.chs` and `.enu`. The mapping inverts
`sorted(range(record_count), key=lambda i: f'{i}_')`; this is a validated project
reconstruction rule, not upstream filename metadata.

Case endpoint indices are half-open alignment-unit intervals in the project
canonical book/run. Use the chapter mapping and expected hashes to validate any
local reconstruction. This release does not supply an automated BWB reconstruction
script; metadata loading alone cannot reproduce the text or reference units.
After obtaining matching local text, use the case/prediction formats in the
[evaluation guide](../evaluation/README.md). The two-document evaluator example
can be run independently of the corpus.

Selected books: 45, 57, 69, 238, 253 and 254. Book 238 windows do not cross the
chapter-58 gap. The metadata describes the existing frozen test and preserves
its original quality characteristics.

Cite [BlonDe (NAACL 2022)](https://aclanthology.org/2022.naacl-main.111/) and the
[upstream discourse annotations (ACL 2023)](https://aclanthology.org/2023.acl-long.435/)
where applicable. No additional corpus rights are granted by this package.
