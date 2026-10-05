# Index-Dub Demo Web 应用

一个自包含的视频配音演示站：**上传视频 → 后台自动翻译配音 → 页面展示配音结果（原文/译文双语字幕）**。
每翻译一个视频自动入库为一个案例，顶部 tab 切换，历史案例只增不删。

![流程](https://img.shields.io/badge/pipeline-upload%20%E2%86%92%20dub%20%E2%86%92%20showcase-blue)

## 功能

- 📤 上传视频：**拖拽**或点击选择文件
- 🌐 语种选择：**源语言**（自动识别 / 中文 / English）+ **目标语言**（中/英/日/西），方向与官方 S2ST 一致（中 → 英/日/西；英 → 中/日/西），选了源语言后目标语言下拉自动过滤掉不支持的方向
- 📊 实时进度：提取音频 → 人声分离 → 切句 → 逐句配音（x/y）→ 合成 → 封装
- 🎬 结果展示：配音视频 + 双语字幕随播放滚动高亮，点字幕跳转，空格播放/暂停
- 🗂 案例缓存：每个成片自动注册为案例，历史案例永久保留
- 🔊 英文原声段自动保留（源语言==目标语言的片段不配音、回填原声并标注）

## 架构

```
浏览器 ──HTTP──> demo/app.py (FastAPI, 本目录) ──HTTP──> S2ST 推理服务
                 · 静态页 + Range 视频流          · 你自己部署 (deploy/serve_s2st.py)
                 · 上传/任务/进度 API             · 或任何已部署的 /s2st 服务
                 · 后台线程跑配音管线
```

**本应用不含模型权重**，推理走 HTTP 调用 S2ST 服务——服务可以自己部署，也可以用已有的。

## 安装

```bash
# 在 video-dub/ 目录下执行（下面的相对路径都相对它）
cd <repo>/video-dub

# 1. 配音管线依赖（video-dub/requirements.txt）
pip install -r requirements.txt

# 2. Web 应用依赖（video-dub/demo/requirements.txt）
pip install -r demo/requirements.txt

# 3. ffmpeg 需要在 PATH 中
ffmpeg -version
```

## 准备 S2ST 服务（二选一）

### 方案 A：使用已有的 S2ST 服务

如果已经有部署好的服务（内部或他人共享），直接拿它的 base URL 即可，跳到下一步。

### 方案 B：自己部署模型（单卡 GPU）

用仓库自带的 `deploy/serve_s2st.py` 把官方导出包（DubbingBridgeModel：ST LM + Hidden2CV + CosyVoice3）跑成 HTTP 服务：

```bash
# 在 GPU 机器上（9B 约需 22G 显存，2B 更少；int4 量化包可降到 ~10.6G）
python deploy/serve_s2st.py --model-dir /path/to/dubbing_2b_fulldir_cv3 --port 8094

# 验证
curl http://127.0.0.1:8094/healthz
# {"ok": true, "langs": ["en","es","ja","zh"]}
```

服务与 demo 不在同一台机器时，用 ssh 隧道转发到本地：

```bash
ssh -N -L 8094:127.0.0.1:8094 <gpu机器>
```

## 启动 demo

```bash
python3 demo/app.py --s2st-url http://127.0.0.1:8094 --port 8080
# 打开 http://127.0.0.1:8080/
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--s2st-url` | env `S2ST_URL` 或 `http://127.0.0.1:8094` | S2ST 服务地址 |
| `--port` | 8080 | Web 端口 |
| `--host` | 127.0.0.1 | 监听地址（要给别人访问用 `0.0.0.0`） |

## 使用

1. 把视频**拖进上传区**（或点击选择文件）
2. 选**源语言**（默认「自动识别」，模型自动判别中/英）和**目标语言**；选了源语言后，目标语言下拉只剩官方支持的方向（中 → 英/日/西；英 → 中/日/西），同语种方向会被服务端直接拒绝
3. 选项：**人声分离**（有 BGM 的视频建议开，首次运行 demucs 会下载约 80MB 模型）、**并行请求数**（默认 4）
4. 点**开始配音**，进度条实时显示当前步骤与逐句进度（x/y）
5. 完成后自动跳转到新案例：播放配音视频，右侧双语字幕滚动高亮，点字幕跳转对应时间点

逐句失败的片段不会中断任务：该时段**保留原始人声**并在字幕中标注"原声"（典型场景：中→英任务里源视频本身的英文台词）。

## 目录与数据

```
demo/
├── app.py              # Web 服务（FastAPI：上传/进度 API + 静态文件 + Range）
├── index.html          # 前端单页（上传/进度/案例/播放器）
├── case_registry.py    # 案例注册（cases/manifest.json + cases/<id>.json）
├── add_case.py         # 把已有配音结果手动注册为案例（见下）
├── uploads/            # 用户上传的原始视频（运行时生成）
├── results/<job_id>/   # 每个任务的成片 + srt + bilingual.srt + segments.json
└── cases/              # 展示数据（manifest + 每案例一份 json）
```

`uploads/`、`results/`、`cases/` 都是运行时数据，重启服务不丢失，删除对应目录即清理。

## 导入已有的配音结果

用命令行跑过 `dub_video.py` 的产出（mp4 + segments.json）可以直接注册进展示页：

```bash
cd demo
python3 add_case.py ../out/slzz.en.segments.json slzz.en.mp4 \
    "【森林之子】速通（中 → 英配音）" "Index S2ST 9B · 全片 8:16 · 88 句" \
    --tab "森林之子（9B）"
```

- 视频文件需在 demo 目录下（根目录或 `results/` 里），第二参数写相对路径
- 重复注册同一 id（= 视频文件名去扩展名）会覆盖该案例，不影响其他案例
- `segments.json` 里 `src` 为空的旧数据可以用 `--en-trans` 传入补充转写

## API 一览（想自己做前端的话）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/langs` | 语种表：`targets` 目标语种、`sources` 源语种、`directions` 支持的方向 |
| GET | `/api/cases` | 案例清单 |
| GET | `/api/cases/<id>` | 案例数据（meta + segments） |
| POST | `/api/dub` | multipart 上传：`file`, `lang`, `src_lang`(可空=自动), `separate`, `workers` → `{job_id}`；不支持的方向返回 400 |
| GET | `/api/jobs` / `/api/jobs/<id>` | 任务列表 / 单任务进度（step, seg_done/seg_total, log） |
| GET | `/api/healthz` | Web + S2ST 服务健康检查 |

## 常见问题

| 现象 | 原因/处理 |
|---|---|
| 视频能播但进度条拖不动 | 确认走的是 `app.py`（自带 Range 支持），不要用 `python -m http.server` |
| 上传后立刻失败 | 检查 `--s2st-url` 是否可达：`curl <url>/healthz` |
| 某几句没配音、字幕标"原声" | 该片段被识别为与目标同语种（如中→英任务里的英文台词），属正常保留 |
| 长视频很慢 | 服务是单并发推理；时长 ≈ 句数 × 单句耗时 / 并行度。9B 单句约 1.1-1.5× 句长，2B 快 3-5 倍 |
| demucs 报 SSL 证书错（macOS） | `export SSL_CERT_FILE=$(python3 -m certifi)` 后重启 |
