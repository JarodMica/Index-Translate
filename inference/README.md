# inference · Index-Translate Model Quickstarts

[中文](README_zh.md)

Minimal, tested inference scripts and cases for the open-sourced
[Index-Translate model family](https://huggingface.co/collections/IndexTeam/index-translate).

## Model map

| Model | Task | Quickstart |
|---|---|---|
| [Index-Translate-2B](https://huggingface.co/IndexTeam/Index-Translate-2B) / [9B](https://huggingface.co/IndexTeam/Index-Translate-9B) | text translation across 150 languages | [`llm/`](llm/) |
| [Index-NativeLong-2B](https://huggingface.co/IndexTeam/Index-Nailong-2B) / [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B) | long-document translation (2B: 262,144; 9B: 229,376 tokens; zh↔en / zh↔ja) | [`llm/`](llm/) |
| [Index-Homura-2B](https://huggingface.co/IndexTeam/Index-Homura-2B) / [9B](https://huggingface.co/IndexTeam/Index-Homura-9B) | translation with a target syllable count | [`llm/`](llm/) |
| [Index-Echo-S2ST-2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) / [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B) | speech-to-speech dubbing (zh→en/es/ja; en→zh/es/ja; voice-conditioned) | [`echo-s2st/`](echo-s2st/) |
| [Index-Echo-S2TT-2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) / [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B) | speech-to-text translation (zh audio/video → en/ja/es subtitles) | [`echo-s2tt/`](echo-s2tt/) |

Index-NativeLong uses the repository IDs `IndexTeam/Index-Nailong-2B` / `IndexTeam/Index-Nailong-9B`. Speech language coverage refers to the packaged interfaces.

## Quick-start paths

Run from the repository root. The server stays in the first terminal; run the client in a second terminal after it is ready.

```bash
pip install -U vllm
pip install -r inference/llm/requirements.txt
bash inference/llm/serve_vllm.sh translate-9b
```

```bash
python inference/llm/translate.py "你好，世界" --target en
```

For speech dependencies and runnable commands, see the [S2TT guide](echo-s2tt/README.md) and [S2ST guide](echo-s2st/README.md).

All scripts were tested end-to-end against the released weights before
publication; see each directory's README for details and `llm/cases/` for
input/output examples captured from real runs.

Related: [`../video-dub/`](../video-dub/) turns these models into a full
video-dubbing pipeline (vocal separation, VAD segmentation, timeline re-mux).
