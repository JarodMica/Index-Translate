# inference · Index-Translate 模型推理快速上手

[English](README.md)

面向 [Index-Translate 开源模型家族](https://huggingface.co/collections/IndexTeam/index-translate)
的最小化推理脚本与实测用例（发布前全部对线上同款权重跑通）。

## 模型一览

| 模型 | 任务 | 入口 |
|---|---|---|
| [Index-Translate-2B](https://huggingface.co/IndexTeam/Index-Translate-2B) / [9B](https://huggingface.co/IndexTeam/Index-Translate-9B) / [35B-A3B（preview）](https://huggingface.co/IndexTeam/Index-Translate-35B-A3B) | 覆盖 150 种语言的文本翻译 | [`llm/`](llm/) |
| [Index-NativeLong-2B](https://huggingface.co/IndexTeam/Index-Nailong-2B) / [9B](https://huggingface.co/IndexTeam/Index-Nailong-9B) | 长文档翻译（2B：262,144；9B：229,376 tokens；中↔英 / 中↔日） | [`llm/`](llm/) |
| [Index-Homura-2B](https://huggingface.co/IndexTeam/Index-Homura-2B) / [9B](https://huggingface.co/IndexTeam/Index-Homura-9B) | 指定目标音节数的翻译 | [`llm/`](llm/) |
| [Index-Echo-S2ST-2B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-2B) / [9B](https://huggingface.co/IndexTeam/Index-Echo-S2ST-9B) | 语音到语音配音（中→英/西/日；英→中/西/日；参考源说话人音色） | [`echo-s2st/`](echo-s2st/) |
| [Index-Echo-S2TT-2B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-2B) / [9B](https://huggingface.co/IndexTeam/Index-Echo-S2TT-9B) | 语音转文字翻译（中文音视频 → 英/日/西字幕） | [`echo-s2tt/`](echo-s2tt/) |

Index-NativeLong 的实际仓库 ID 为 `IndexTeam/Index-Nailong-2B` / `IndexTeam/Index-Nailong-9B`。语音语言范围指当前发布包的接口覆盖。

## 默认推理参数

[默认设置总表](../README_zh.md#默认推理参数)统一对比五个模型家族的解码、输出预算、部署窗口、音频切窗、声音生成和可调入口。默认值以总表为准；下面的教程说明环境安装与任务用法。

## 快速上手入口

从仓库根目录运行。服务占用第一个终端；启动完成后，在第二个终端执行客户端命令。

```bash
pip install -U vllm
pip install -r inference/llm/requirements.txt
bash inference/llm/serve_vllm.sh translate-9b
```

```bash
python inference/llm/translate.py "你好，世界" --target en
```

语音模型的依赖与运行命令见 [S2TT 教程](echo-s2tt/README_zh.md)和 [S2ST 教程](echo-s2st/README_zh.md)。

各目录 README 有详细说明；`llm/cases/` 收录了真实运行的输入输出样例。

相关项目：[`../video-dub/`](../video-dub/) 把这些模型串成完整视频配音管线
（人声分离、VAD 切分、时间轴回贴）。
