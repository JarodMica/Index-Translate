# index-dub · 视频翻译配音工作流

[English](README.md) | 中文

输入一个 mp4，用 **Index S2ST 语音同传模型** 直接生成目标语言的配音视频：

```
mp4 → 提取音频 → [可选: 人声分离] → VAD 切句(带时间戳) → 逐句 S2ST 配音 → 时间轴对齐合成 → 输出配音 mp4
```

S2ST 模型不支持过长输入（服务端上限约 10.5s），因此中间用 VAD 把语音切成短句（默认 ≤9.5s）并记录时间戳，逐句调用推理服务后按原时间轴拼回（必要时轻微变速对齐），同时可导出翻译字幕。

## 环境

- Python 3.9+，`ffmpeg` 在 PATH 中
- `pip install -r requirements.txt`
  - `demucs` 用于人声分离（默认开启，首次运行会下载模型，约 80MB；`--no-separate` 可关闭）
  - `silero-vad`/`torch` 用于精确切句；不装会自动回退到 ffmpeg silencedetect
- 一个可达的 S2ST 推理服务（见下文「推理服务」）

## 快速开始

```bash
# 把 input.mp4 配成英文（默认含人声分离 + 背景音回填）
python dub_video.py input.mp4 --lang en --s2st-url http://127.0.0.1:8094

# 干净人声素材可关掉分离提速，顺带导出字幕
python dub_video.py input.mp4 --lang en --no-separate --srt

# 日文输出、自定义切句上限
python dub_video.py input.mp4 --lang ja --max-seg 10
```

产物：

- `<input>.<lang>.mp4` — 配音后的视频
- `<input>.<lang>.srt` —（`--srt`）翻译字幕，时间轴与原片一致
- `<input>.<lang>.segments.json` — 每句的起止时间与译文，方便二次加工

支持目标语言：`en / es / ja / zh`（源语言自动识别 zh/en）。

## 工作原理

| 步骤 | 模块 | 说明 |
|---|---|---|
| 提取音频 | `index_dub/media.py` | ffmpeg 抽 16k 单声道 wav |
| 人声分离 | `index_dub/separate.py` | 默认开启，demucs two-stem；BGM 回填到配音下面，`--no-separate` 关闭、`--no-bgm` 丢弃伴奏 |
| 切句 | `index_dub/segment.py` | silero-vad 找语音段，短停顿合并，超长段在最安静点二次切分，全部带时间戳 |
| 配音 | `index_dub/s2st.py` | `POST {url}/s2st`（multipart: `file`=wav, `lang`=目标语言）→ `audio_b64`(24kHz wav) + 源文 + 译文 |
| 对齐合成 | `index_dub/timeline.py` | 每句放回原始时间段，与时间槽不一致时向两个方向变速（上限 `--max-stretch`，过短也会放慢填充），越界截断，静音补齐 |
| 封装 | `index_dub/media.py` | ffmpeg 音轨替换，视频流 copy 不重编码 |

## 推理服务

工作流默认调用 HTTP 服务（`--s2st-url` 或环境变量 `S2ST_URL`）。服务接口：

```
GET  /healthz            -> {"ok": true, "langs": ["en","es","ja","zh"]}
POST /s2st               multipart: file=<wav>, lang=<en|es|ja|zh>
                         -> {"ok": true, "audio_b64": "<24kHz wav base64>",
                             "sr": 24000, "zh": "<源文>", "text": "<译文>", ...}
POST /s2tt               同上，只返回文本翻译（不生成音频）
```

本地部署服务（离线、无需外部服务）的方式见 [deploy/](deploy/)（基于官方导出的
DubbingBridgeModel 一体化包，单卡 ~22G 显存）。

## 已知限制

- 源语言自动识别仅支持中文/英文（`zh/en`），其他源语言暂不支持
- 语速差异大时（如中→英长句）会有最多 `--max-stretch` 倍的变速，极限情况下按时间槽截断
- 变速是双向的：译文比原时间槽短时也会**放慢**填补（同样受 `--max-stretch` 上限约束），因此很短的句子听起来可能被拉长
- 单人说话效果最佳；多人重叠说话/强 BGM 场景依赖人声分离（默认已开启）
