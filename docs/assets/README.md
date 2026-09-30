# Figures and demo previews

All charts use the updated official demo data captured on 2026-09-30. `website_chart_data.json` records all 14 radar models, fixed axis ranges, and the 86 displayed values from the 12 bar charts. `seven_category_scores_raw.csv` contains the seven raw radar categories. Values are frozen locally for reproducible figures; no network request is needed when rendering.

## Radar

The seven axes are WMT, FLORES, instruction following, low-resource translation, subtitle translation, MEME, and books/fiction. Instruction following averages instTrans and IFMTBench IFscore; subtitles average OpenSubtitles and MuST-Cinema; books/fiction average OPUS-Books and GuoFeng-Webnovel.

Each axis uses `100 * (score - min) / (max - min)` over all 14 models. The default curves show Index-Translate-35B-A3B (preview), 9B, 2B, DeepSeek-V4.1-Flash, GPT-5.6-Sol, and the best non-Index score per category. The gray dashed envelope includes models not drawn individually and does not represent one model. The blue dashed line is Index-Translate-2B. Distances and polygon areas are not raw score differences or accuracy percentages.

## Bar charts

The text overview includes general translation, instruction translation, five-domain translation, MEME, and both low-resource metrics. The instruction Quality panel averages instTrans quality and IFMTBench XCOMET-XXL; the IFscore panel averages the corresponding instruction-following scores. These website summaries differ from the individual benchmark columns in the evaluation tables. The five domains are OPUS-Books, WMT Biomedical, MTNT, MuST-Cinema, and GuoFeng-Webnovel.

The Echo overview includes S2TT and the demo's deployed 2B S2ST comparison with a pipeline and SeamlessM4T-v2. The latter does not perform voice cloning. These S2ST values have a different evaluation scope from the six-direction, size-matched study in the report. Homura uses the demo's SandGlass overall score and length adherence; overall score is distinct from translation quality in the detailed table. NativeLong uses the demo's 64K GuoFeng and BWB Track A3 comparison.

Every bar axis starts at zero. Models and displayed values follow the demo. Detailed tables retain their own metrics and settings. 35B-A3B remains **preview**.

## Reproduction

Requires Python, matplotlib, and numpy:

```bash
python docs/assets/render_benchmark_overviews.py --suffix .en
python docs/assets/render_benchmark_overviews.py --language zh --font /path/to/a/CJK/font.ttf --suffix .zh
```

This emits vector SVG/PDF figures and PNG previews; the repository tracks the README SVGs. The report uses the same generator with its frozen data and no suffix. The article uses Chinese PNGs. `render_radar.py` is a compatibility alias for the unified generator and accepts the same options.

`echo-s2st.png` and `echo-s2tt.png` preview the official demo videos. Their README links open the hosted MP4 files; no video binaries are stored in this repository.

- [Updated demo](https://index-translate.bilibili.com/?p=/site/home.html)
- [Speech-to-speech video](https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo.mp4)
- [Multilingual subtitle video](https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo-s2tt.mp4)

新版七维图包含 35B-A3B（preview），按全部 14 款模型固定各轴的 min–max 范围。灰色虚线为逐维非 Index 最优组合，蓝色虚线为 2B。指令遵循取 instTrans 与 IFMTBench IFscore 均值；字幕、书籍网文分别取两项数据集均值。柱状图沿用 Demo 的数值和对比集合；各项明细评测保留独立口径。
