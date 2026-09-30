# echo-s2st · 语音到语音配音

[English](README.md)

[Index-Echo-S2ST-2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) 和
[Index-Echo-S2ST-9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B)
把中文或英文语音配音成英/西/日/中目标语，并保留原说话人音色
（ST LM → Hidden2CV mapper → CosyVoice3，单包自包含）。

## 快速开始

```bash
# 下载模型包（2B 约 13 GB，9B 约 26 GB）
huggingface-cli download IndexTeam/Index-Echo-S2ST-2B --local-dir ./Index-Echo-S2ST-2B

# 装依赖（完整锁定版本见模型仓库 README）
pip install torch==2.11.0 torchaudio transformers==5.6.0 librosa onnxruntime \
    wetext kaldifst conformer hydra-core HyperPyYAML soundfile safetensors

# 中文语音 → 英文配音
python dub.py input_zh.wav --lang en -o dub_en.wav

# 英文源也可以——源语种自动判定
python dub.py input_en.wav --lang zh -o dub_zh.wav
```

`--lang` 永远是**目标语**（`en/es/ja/zh`）；支持方向：中→英/西/日、英→中/西/日。

`dub.py` 会把转写和译文打到 stderr，并保存配音 wav。底层
`DubbingBridgeModel` Python API（批量调用、`return_info`、重试）见模型仓库
README。每个模型包还自带 `samples/`（输入样例 + 参考配音）和
`verify_export.py` 自检脚本。

## 注意

- 单张 CUDA 卡：2B ≥12 GB 显存，9B ≥24 GB；系统需有 ffmpeg。
- 输入宜短（单句 ≤30 s，模型按语句级配音调优）。长视频请用
  [`../../video-dub/`](../../video-dub/) 的完整管线（人声分离、VAD 切分、
  时间轴回贴）；`video-dub/deploy/serve_s2st.py` 可以把同一个包起成 HTTP 服务。
- 英文源短句约 1% 概率触发声码侧合成失败——重试即可（采样器有抖动）。
