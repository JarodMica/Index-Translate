# Evaluation Results

[中文](evaluation_zh.md) · [Back to README](../README.md)

Full model comparisons, method summaries, and evaluation notes. Compare each metric within its own evaluation setting; the radar uses demo category aggregates rather than individual benchmark scores.

### Text translation (Index-Translate)

Multilingual text translation with instruction following across 150 languages. For the evaluated 2B/9B models, post-training combines general-translation, instruction-following, and meme-translation specialists via parameter interpolation (model soup, weights 0.8/0.1/0.1) plus targeted multi-teacher on-policy distillation (MOPD).

| Model | FLORES<br>COMET-22 | WMT24++<br>COMET-22 | WMT26<br>Judge | instTrans<br>Quality | instTrans<br>IFscore | IFMTBench<br>XCOMET-XXL | IFMTBench<br>IFscore | Vertical<br>mean | MEME |
|---|---|---|---|---|---|---|---|---|---|
| **Index-Translate-9B** | **0.8789** | 0.8601 | 75.35 | 0.6771 | **0.8209** | 0.7957 | 0.8760 | 0.8451 | 0.7387 |
| **Index-Translate-2B** | 0.8655 | 0.8489 | 60.26 | 0.5391 | 0.7569 | 0.7712 | 0.7584 | 0.8377 | 0.6443 |
| Hy-MT2-1.8B | 0.8522 | 0.8401 | 49.35 | 0.3181 | 0.4932 | 0.7493 | 0.7161 | 0.8314 | 0.3643 |
| Hy-MT2-7B | 0.8747 | 0.8593 | 60.51 | 0.5143 | 0.6079 | 0.8049 | 0.8741 | 0.8335 | 0.5139 |
| Hy-MT2-30B-A3B | 0.8787 | **0.8624** | 66.81 | 0.5725 | 0.6415 | **0.8177** | 0.9029 | **0.8459** | 0.5812 |
| TranslateGemma-12B | 0.8732 | 0.8524 | 71.19 | 0.4515 | 0.3068 | 0.8023 | 0.2892 | 0.8347 | 0.4281 |
| North-Small-Translate (218B-A25B) | 0.8784 | 0.8578 | 68.37 | 0.5697 | 0.5294 | 0.7657 | 0.8635 | 0.8357 | 0.6836 |
| Qwen3.5-2B (base) | 0.6983 | 0.6933 | 32.11 | 0.0999 | 0.2431 | 0.6197 | 0.3836 | 0.7557 | 0.2062 |
| Qwen3.5-9B (base) | 0.8316 | 0.8073 | 60.31 | 0.2467 | 0.0609 | 0.7341 | 0.5980 | 0.8199 | 0.5728 |
| Qwen3.5-35B-A3B | 0.8570 | 0.8290 | 71.33 | 0.3690 | 0.5204 | 0.7589 | 0.7822 | 0.8267 | 0.6447 |
| DeepSeek-V4.1-Flash | 0.8762 | 0.8510 | 83.55 | 0.6068 | 0.6374 | 0.7817 | 0.9090 | 0.8432 | **0.7424** |
| GPT-5.6-Sol | 0.8650 | 0.8469 | **89.10** | **0.6902** | 0.7624 | 0.7946 | **0.9367** | 0.8311 | 0.7194 |
| Gemini 3.5 Flash Lite | 0.8750 | 0.8497 | 79.52 | 0.6068 | 0.6374 | — | 0.7764 | 0.8131 | 0.7034 |

General capabilities (answer accuracy %) — Index-Translate-9B exceeds Hy-MT2-7B on all four benchmarks, while remaining below the Qwen3.5-9B base:

| Model | C-Eval | GPQA-Diamond | INCLUDE | MMMLU |
|---|---|---|---|---|
| Index-Translate-9B | 69.6 | 36.3 | 63.1 | 66.6 |
| Hy-MT2-7B | 57.4 | 30.5 | 50.3 | 52.3 |
| Qwen3.5-9B (base) | **86.6** | **75.8** | **70.2** | **75.9** |

### Speech-to-text translation (Index-Echo S2TT)

Connects a Qwen3-Omni AuT audio encoder to an Index-Translate 2B/9B decoder, trained end to end on speech translation. On the in-house video translation set (140 windows × 7 directions), Index-Echo-9B scores **0.857 on MT judge — between Qwen3.8-Omni-Flash (0.887) and Gemini-3.1-Pro with thinking (0.849)** — and, together with its 2B sibling, achieves the two lowest ASR and timestamp errors in the comparison.

| Model | MT judge ↑ | ASR error (median) ↓ | Start-time MAE (s) ↓ |
|---|---|---|---|
| Qwen3.8-Omni-Flash | **0.887** | 0.112 | 1.004 |
| **Index-Echo-9B** | 0.857 | 0.102 | 0.488 |
| Gemini-3.1-Pro (thinking) | 0.849 | 0.169 | 1.824 |
| Qwen3.8-LiveTranslate (streaming) | 0.833 | 0.186 | — |
| **Index-Echo-2B** | 0.825 | **0.088** | **0.395** |
| Gemini-2.5-Flash (thinking) | 0.817 | 0.201 | 2.402 |
| Qwen3-Omni | 0.700 | 0.139 | 1.145 |
| FireRed Audio | 0.448 | 0.128 | 0.765 |
| SeamlessM4T-v2 | 0.060 | 1.000 | — |

### Speech-to-speech translation (Index-Echo S2ST)

Initializes from the S2TT models and bridges to CosyVoice3 with a ~30M-parameter Hidden2CV mapper, trained by frozen-model alignment followed by differentiable reward optimization (DiffRO). Source audio supplies the reference prompt and CampPlus speaker embedding for voice conditioning. The released package supports six directions: zh→{en, es, ja} and en→{zh, es, ja}. End-to-end dubbing lowers mean content error vs. the S2TT+CosyVoice3 pipeline in 8 of 12 size–direction pairs, with speaker similarity within 0.01–0.02 of the pipeline.

| Direction | Size | Text judge ↑ | Content error ↓ (Pipeline → E2E) | Spk. sim ↑ (Pipeline → E2E) |
|---|---|---|---|---|
| zh→en (WER) | 2B | 0.830 | 0.0450 → 0.0709 | 0.722 → 0.743 |
| zh→es (WER) | 9B | 0.793 | 0.0916 → **0.0773** | 0.746 → 0.746 |
| zh→ja (Kata CER) | 9B | 0.815 | 0.0552 → **0.0436** | 0.778 → 0.782 |
| en→zh (CER) | 2B | 0.825 | 0.0614 → **0.0372** | 0.630 → 0.623 |
| en→ja (Kata CER) | 2B | 0.790 | 0.0342 → 0.0345 | 0.707 → 0.698 |

### Syllable-controlled translation (Index-Homura)

Adapts the 2B/9B text models to translation with an explicitly specified target syllable count, trained with GRPO on a length reward (following HOMURA). Evaluated on SandGlass (3,600 cases per model; 300 subtitle sentences × 4 target languages × 3 length budgets).

| Model | Quality ↑ | Mean \|d\| ↓ | Within ±1 ↑ | Within 10% ↑ | Slope ≈ 1 |
|---|---|---|---|---|---|
| **Index-Homura-9B (RL)** | 0.7863 | **0.0693** | **74.42%** | **81.92%** | **0.968** |
| Index-Homura-9B (SFT) | 0.8581 | 0.1752 | 41.39% | 45.75% | 0.680 |
| **Index-Homura-2B (RL)** | 0.7615 | 0.0962 | 54.39% | 63.08% | 0.947 |
| GPT-5.6-Sol (low) | 0.8715 | 0.3223 | 42.53% | 47.64% | 0.891 |
| DeepSeek-V4-Flash (no thinking) | **0.8742** | 0.3368 | 16.58% | 16.36% | 0.153 |
| Hy-MT2-7B | 0.8560 | 0.3174 | 18.14% | 18.86% | 0.195 |
| Hy-MT2-30B-A3B | 0.7554 | 0.2743 | 20.97% | 22.39% | 0.340 |
| Hy-MT2-1.8B | 0.5904 | 0.7080 | 14.58% | 16.72% | 0.222 |
| Hunyuan-MT-7B | 0.7188 | 1.0579 | 12.31% | 15.11% | 0.031 |

### Long-document translation (Index-NativeLong)

Extends training to complete documents, increasing sequence length from 4K to 128K during mid-training decay and post-training on entire books and full-length movie transcripts. Evaluated on 274 document windows (GuoFeng, BWB Track A3, Books) with document-SEGALE/COMET; means equally weight five 4K–64K length bins.

| Model | GuoFeng (zh→en) | BWB Track A3 (zh→en) | Books (en→zh) |
|---|---|---|---|
| **Index-NativeLong-9B** | **.7891** | **.7683** | **.8848** |
| Index-NativeLong-2B | .6701 | .7300 | .8651 |
| Qwen3.8 Flash | .7053 | .6823 | .8206 |
| GLM-5.3-Flash* | .7054 | .6691 | .8795 |
| North-Small-Translate-1.0 | .6160 | .6282 | .8350 |
| Hy-MT2-7B | .2082 | .1983 | .2360 |
| Hy-MT2-30B-A3B | .2904 | .2998 | .3306 |

\* Some GLM requests were refused; its Books scores average the remaining samples.

For more experimental results and analysis, please refer to our [technical report](Index_Translate_Series_Technical_Report.pdf).

## 35B-A3B preview results

The technical report also includes preview evaluation of Index-Translate-35B-A3B. The download table lists the released 2B and 9B checkpoints; the 35B-A3B WMT26 result is pending.

| Model | FLORES COMET-22 ↑ | WMT24++ COMET-22 ↑ | WMT26 ↑ | instTrans Quality ↑ | instTrans IFscore ↑ | IFMTBench XCOMET-XXL ↑ | IFMTBench IFscore ↑ | Vertical ↑ | MEME ↑ |
|---|---|---|---|---|---|---|---|---|---|
| Index-Translate-35B-A3B (preview) | 0.8796 | 0.8580 | — | 0.6815 | 0.8304 | 0.7917 | 0.8941 | 0.8434 | 0.7385 |

## IFMTBench preprocessing

The official set contains 7,344 examples. Evaluation removes 280 single-constraint examples with reference-translation or language-label quality issues, leaving 7,064 inputs; 7,063 receive valid judgments. Interpret the reported results under this protocol; see the technical report for details.
