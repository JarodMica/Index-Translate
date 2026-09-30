# echo-s2tt · 语音转文字翻译（字幕）

[English](README.md)

[Index-Echo-S2TT-2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) 和
[Index-Echo-S2TT-9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B)
把中文音视频翻成带时间戳的双语字幕（中 → 英/日/西）。模型包自包含：
权重 + `infer.py`（VAD 切窗、滑动上下文保证术语一致、支持译名表干预）。

## 快速开始

```bash
pip install torch==2.11.0 transformers==5.6.0 safetensors librosa soundfile silero-vad
# 系统需有 ffmpeg

# 最省事：包装脚本首次运行自动下载 2B 包
python s2tt.py input.mp4 --lang en            # 产物在 out/input.srt
python s2tt.py talk.wav --lang ja --size 9b   # 用 9B 包

# 或者直接操作模型包
huggingface-cli download IndexTeam/Index-Echo-S2TT-2B --local-dir ./Index-Echo-S2TT-2B
python Index-Echo-S2TT-2B/infer.py input.mp4 --out out_dir --target-lang en
```

产物：`<out>/<名字>.srt`（每条字幕两行：中文原文 + 目标语译文）和
`<out>/<名字>.windows.jsonl`（逐窗原始输出）。

常用参数（`s2tt.py` 会透传，也可直接传给 `infer.py`）：

- `--glossary "原名1:译名1,原名2:译名2"` —— 逐窗钉住术语译名
- `--max-win 60` —— VAD 切窗上限（秒）
- `--ctx-k 5` —— 前多少个窗喂进 `[Context]` 槽
- `--device cuda:1` —— 指定显卡

## 注意

- 2B bf16 约 10 GB 显存；A100 上约 1.4–1.7× 实时，一个文件占一张卡
  （多文件可分到多卡并行）。
- 源语种为中文；目标语支持英/日/西。
