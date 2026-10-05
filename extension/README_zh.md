# LLM Page Translator（index-page-mt）

[English](README.md) | 中文

一个使用**本地部署大模型**翻译网页的浏览器插件（Chrome / Edge / Firefox，Manifest V3），为 **[Index-Translate](https://huggingface.co/collections/IndexTeam/index-translate) 系列翻译模型**量身打造，兼容任何提供 OpenAI 格式接口的本地推理框架（vLLM / SGLang 等）。

纯原生 JS，**无需任何构建步骤**，目录即插件。

## 为什么推荐 Index-Translate

[Index-Translate-2B / 9B](https://huggingface.co/collections/IndexTeam/index-translate) 是专为翻译任务训练的模型，相比同尺寸通用模型：

- 翻译质量更高，支持百余种语言方向；
- 体积小、推理快，2B 模型一张消费级显卡即可流畅运行；
- 本地部署，网页内容不出本机/内网，无隐私与合规顾虑；
- 无 API Key、无按量计费，可离线使用。

模型下载（任选其一）：

- Hugging Face：[`IndexTeam/Index-Translate-2B`](https://huggingface.co/IndexTeam/Index-Translate-2B) · [`IndexTeam/Index-Translate-9B`](https://huggingface.co/IndexTeam/Index-Translate-9B)
- ModelScope：[IndexTeam 组织主页](https://modelscope.cn/organization/IndexTeam)（同名仓库）

## 目录结构

```
index-page-mt/
├── manifest.json            # 插件清单（Chrome / Edge，MV3）
├── manifest.firefox.json    # 插件清单（Firefox）
├── background.js            # Service Worker：调用大模型 API（绕开网页 CORS）
├── content/
│   ├── content.js           # 内容脚本：提取页面段落、插入双语译文
│   └── content.css          # 译文块样式
├── popup/
│   ├── popup.html           # 工具栏弹窗：翻译 / 还原 / 划词
│   └── popup.js
├── options/
│   ├── options.html         # 设置页：API 地址 / 模型 / 目标语言
│   └── options.js
└── scripts/
    └── build.sh             # 打包 Chrome / Firefox 安装包
```

---

## 第一步：本地部署模型

### 方案 A：vLLM（推荐）

安装（需要 NVIDIA GPU + CUDA 环境，详见 [vLLM 官方文档](https://docs.vllm.ai/)）：

```bash
pip install vllm
```

启动 OpenAI 兼容服务：

```bash
# 2B 模型（约需 8GB 显存）
vllm serve IndexTeam/Index-Translate-2B \
    --served-model-name Index-Translate-2B \
    --port 8000

# 9B 模型（约需 24GB 显存）
vllm serve IndexTeam/Index-Translate-9B \
    --served-model-name Index-Translate-9B \
    --port 8000
```

- `--served-model-name` 指定对外暴露的模型名，**插件设置里的"模型名称"必须填这个值**；
- 首次启动会自动从 Hugging Face 下载权重；国内网络可改用 ModelScope 下载后换本地路径，或设置 `HF_ENDPOINT=https://hf-mirror.com`；
- 想让局域网内其他机器访问，加 `--host 0.0.0.0`，插件端把地址改成 `http://<服务器IP>:8000/v1`。

### 方案 B：SGLang

```bash
pip install "sglang[all]"

# 2B 模型
python -m sglang.launch_server \
    --model-path IndexTeam/Index-Translate-2B \
    --served-model-name Index-Translate-2B \
    --port 30000

# 9B 模型
python -m sglang.launch_server \
    --model-path IndexTeam/Index-Translate-9B \
    --served-model-name Index-Translate-9B \
    --port 30000
```

SGLang 默认端口是 30000，其余注意事项与 vLLM 相同。

### 验证服务可用

```bash
curl http://localhost:8000/v1/models        # 确认 data[0].id 与插件里填的模型名一致

curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Index-Translate-2B","messages":[{"role":"user","content":"你好"}]}'
```

## 第二步：安装插件

1. 下载本仓库（`git clone` 或下载 ZIP 解压）；
2. 打开 Chrome / Edge，访问 `chrome://extensions/`；
3. 右上角打开 **开发者模式**；
4. 点击 **加载已解压的扩展程序**，选择本仓库目录；
5. （Firefox）访问 `about:debugging#/runtime/this-firefox` → **临时载入附加组件**，选择 `manifest.firefox.json`。

## 第三步：配置插件

点击插件图标 → **⚙ 打开设置**：

| 配置项 | 填写内容 |
|--------|----------|
| API 地址 | vLLM：`http://localhost:8000/v1`；SGLang：`http://localhost:30000/v1` |
| API Key | 本地部署留空 |
| 模型名称 | `Index-Translate-2B` 或 `Index-Translate-9B`（与 `--served-model-name` 一致） |
| 目标语言 | 中文 / 英文 / 日文 / 韩文 |

设置页提供 **vLLM / SGLang × 2B / 9B 四个快速填入按钮**，一键填好地址和模型名。点 **测试连接**，看到示例译文即配置成功。

## 使用

1. 打开任意外文网页（如 https://en.wikipedia.org/wiki/Machine_learning ）；
2. 点插件图标 → **翻译当前页面**；
3. 译文以蓝色左边框的块插入原文段落下方（双语对照）；也可切换 **替换原文** 模式（可勾选悬停显示原文）或 **划词翻译**；
4. 点 **还原页面** 移除全部译文；翻译结果会缓存 7 天，重复访问不再请求。

> 修改代码后，回到 `chrome://extensions/` 点插件卡片上的刷新按钮，并刷新测试网页。

## 工作原理

1. **content.js** 遍历页面 DOM，收集 `<p>` `<h1>-<h6>` `<li>` `<td>` 等块级元素的文本（跳过代码块、不可见元素、过短文本）；
2. 按每批 4 段、最多 3 路并发发消息给 **background.js**；
3. background 以 JSON 数组形式调用本地模型的 `/chat/completions` 接口，要求返回等长的译文数组（对 markdown 代码块包裹、输出截断等常见问题做了容错解析，格式异常自动重试）；
4. 译文插回原段落下方，带 `data-llm-translated` 标记防止重复翻译，可一键还原。

## 常见问题

- **报 403 / CORS 错误**：扩展已在网络层自动移除 `Origin` 头；如仍失败，请确认服务以 `--host 0.0.0.0` 启动且端口可达。
- **提示模型不存在**：模型名必须与启动参数 `--served-model-name` 完全一致，可用 `curl <地址>/v1/models` 查看实际名称。
- **翻译结果格式错乱 / 缺段**：小参数量模型的指令遵循能力有限，插件已内置重试与降级解析；如频繁出现，建议换用 9B 模型。
- **显存不足**：2B 约需 8GB、9B 约需 24GB 显存；可在 vLLM 启动时加 `--gpu-memory-utilization 0.85` 或 `--max-model-len 8192` 降低占用。

## 已知局限（后续迭代方向）

- [ ] 暂不支持流式输出，整批返回后才显示
- [ ] 动态加载的内容（无限滚动）不会自动翻译，需要再点一次
- [ ] 自定义翻译 prompt、术语表

## 开源协议

[Apache License 2.0](LICENSE)
