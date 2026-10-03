# Sources and modifications

- SEGALE: https://github.com/NVlabs/SEGALE, commit `bc19b2bb2bcde0bc2d6154dc2b86024b673e319c`. Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. Apache-2.0.
- VecAlign fork used by SEGALE: https://github.com/shuoyangd/vecalign, commit `4f8b714598353a468596e704180a47bb5d3e2abe`. Original project: https://github.com/thompsonb/vecalign. Copyright 2019 Brian Thompson. Apache-2.0.
- COMET: https://github.com/Unbabel/COMET (installed dependency, not vendored).
- chrF implementation: https://github.com/mjpost/sacrebleu (installed dependency, not vendored).

The bundled SEGALE alignment file is modified: length-sorted embedding batches, dynamic padding and VecAlign subprocess error checks. The bundled VecAlign loader supports package-relative imports and building its extension. Project adapters preserve multiline units, filter blank target sentences, use cached in-process VecAlign search, score COMET with explicit null handling and add diagnostics/chrF2. `provenance.json` records the exact baseline and copied-file hashes. The portable scorer additionally accepts a pinned local XLM-R config/tokenizer.

SEGALE and VecAlign license texts and source copyright notices are retained. The evaluation wrapper and example are distributed under Apache-2.0 as well. This code license does not apply to BWB or GuoFeng book text.

Please cite the SEGALE paper: https://aclanthology.org/2025.emnlp-main.1645/ and VecAlign: https://aclanthology.org/D19-1136/.
