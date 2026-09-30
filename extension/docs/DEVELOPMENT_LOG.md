# 开发日志 — LLM 网页翻译插件

> 项目：index-page-mt（LLM Page Translator）
> 仓库：https://github.com/bilibili/Index-Translate/tree/main/extension
> 时间：2026-08-06 ～ 2026-08-21
> 当前版本：v0.1.0

本文档记录项目从零到当前状态的完整工作，包括每个功能的实现方式、踩过的坑和解决方案。技术设计的完整细节见 [TECHNICAL_ROADMAP.md](./TECHNICAL_ROADMAP.md)。

---

## 一、项目概述

一个使用大模型 API 翻译网页的浏览器插件（Chrome / Edge / Firefox），面向 **本地部署** 的 OpenAI 兼容接口（vLLM / SGLang 等），推荐配合 Index-Translate 系列模型使用。纯原生 JS、零构建依赖、目录即插件。

**当前能力**：
- 一键整页翻译，双语对照 / 替换原文两种显示模式，一键还原，中途可停止、可续翻
- 划词翻译（点按钮或自动触发），结果气泡展示
- 兼容任意 OpenAI 格式 API，面向本地部署模型（vLLM / SGLang）
- LaTeX 公式和行内代码保护（知乎、arXiv 等数学内容网站）
- 翻译缓存 + 3 路并发 + 实时进度条；格式错乱自动重试，适配小模型
- Chrome / Edge / Firefox 三浏览器支持，一键打包

---

## 二、代码结构

```
page_translation/
├── manifest.json            # Chrome/Edge 插件清单（MV3）
├── manifest.firefox.json    # Firefox 专用清单
├── background.js            # Service Worker：API 调用、翻译缓存、Origin 头处理
├── content/
│   ├── content.js           # 内容脚本：文本提取、占位符保护、译文插入、并发调度
│   └── content.css          # 译文块样式（蓝色左边框）
├── popup/                   # 工具栏弹窗：翻译/还原按钮、进度条
├── options/                 # 设置页：API 配置、测试连接、清除缓存
├── scripts/build.sh         # 打包脚本：一键产出 Chrome 和 Firefox 安装包
├── docs/
│   ├── TECHNICAL_ROADMAP.md # 技术路线（架构、断句、pipeline、5 阶段规划）
│   └── DEVELOPMENT_LOG.md   # 本文档
└── dist/                    # 打包产物（git 忽略）
```

---

## 三、开发历程

### 3.1 初始框架搭建（commit `fb81fd9`）

**目标**：跑通"提取页面文本 → 调 LLM → 插回译文"的完整链路。

**核心设计决策**：

1. **Manifest V3 + 纯原生 JS**：Chrome 已强制 MV3；不引入构建工具，降低上手门槛，目录即插件。
2. **API 调用放在 background Service Worker**：扩展有 `host_permissions`，后台发请求不受网页 CORS 限制——这是能连本地 vLLM / SGLang 服务的关键。
3. **统一 OpenAI 兼容格式**：所有服务只是 base URL 和模型名不同，不为每家写适配器。
4. **JSON 数组批量翻译协议**：每批 10 段原文组成 JSON 数组发给模型，system prompt 要求返回等长数组，保证段落一一对应。
5. **文本提取以块级元素为单位**：TreeWalker 遍历 DOM，取 `P/H1-H6/LI/TD/TH` 等标签的 `innerText`，跳过 `SCRIPT/CODE/PRE`、不可见元素、纯数字、过短文本；嵌套块级元素只取最内层。
6. **双语对照展示**：译文作为新 div 插入原文 afterend，原文 DOM 不动，还原时直接 remove。
7. **容错解析**：模型输出可能被 ```` ```json ```` 包裹或夹杂废话，解析时做了多层兜底（代码块提取 → 直接 parse → 截取 `[...]` → 长度补齐/截断）。

### 3.2 接入自建网关（同期）

**需求**：使用自建的 OpenAI 兼容 API 网关。

**遇到的问题和解决**：

| 问题 | 原因 | 解决 |
|------|------|------|
| 网关需要自定义请求头 | 网关侧开启了内容审查类开关，需要附加请求头关闭 | 设置页新增"额外请求头"配置（JSON 格式），background 请求时合并 |
| 插件请求返回 403，curl 却正常 | 浏览器给扩展请求自动附加 `Origin: chrome-extension://...`，网关 WAF 拒绝该 Origin | 用 `declarativeNetRequest` 动态规则在网络层移除扩展自身请求的 Origin 头 |
| 偶发 429 | 网关限流 | 暂靠并发数控制（3 路），完整的指数退避重试规划在后续版本 |

**调试方法备忘**：插件后台的报错在 `chrome://extensions/` → 点插件卡片的 "Service Worker" 链接 → DevTools（Console 看日志，Network 看实际请求）。

设置页同时加了预设按钮（vLLM / SGLang 本地部署的 Index-Translate-2B / 9B），一键填入地址和模型名。

### 3.3 推送代码仓库（commit `fb81fd9` push）

- 仓库：`https://github.com/bilibili/Index-Translate/tree/main/extension`，主分支 `main`
- API Key 不入库：key 存在 `chrome.storage` 中，由用户在设置页填写

### 3.4 LaTeX 公式和代码保护（commit `a4288a9`）

**问题**：知乎等网站的数学公式翻译后变成 LaTeX 源码直接显示（如 `\mathcal{L}(\mu, D) = ...`）。

**原因**：MathJax 渲染的页面在 DOM 里保留原始 LaTeX 源码（`<script type="math/tex">`、`data-tex` 属性），`innerText` 把源码一起提取了，LLM 会试图"翻译"它。

**解决方案 — 占位符系统**：
1. **提取时**：clone 元素副本，用 CSS 选择器找到公式和代码节点，替换为 `%%MATH_0%%` / `%%CODE_1%%` 占位符，同时保存原始内容映射。覆盖 MathJax（`script[type^="math/tex"]`）、KaTeX（`annotation[encoding="application/x-tex"]`）、知乎特定（`[data-tex]`、`[class*="ztext-math"]`）、行内代码（`code/kbd`）。
2. **prompt 约束**：system prompt 明确要求"占位符必须原样保留，不翻译不修改不省略"。
3. **译文插入时**：`replaceAll` 把占位符还原为原始 LaTeX/代码。

LLM 全程看不到 LaTeX，从根本上杜绝公式被改动。

### 3.5 多浏览器适配（commit `f45d779` 一部分）

- **Edge**：零成本——Chromium 内核，直接用 Chrome 的 manifest 和包。
- **Firefox**：新增 `manifest.firefox.json`，差异点：
  - 后台脚本用 `background.scripts` 数组（Firefox 不支持 `service_worker` 字段）
  - `options_ui.page` 替代 `options_page`
  - 必须声明 `browser_specific_settings.gecko.id`
  - `declarativeNetRequest` 的 `initiatorDomains` 条件在 Firefox 下不适用（扩展源是随机 UUID），background.js 中加了 try-catch 降级为无条件规则
- **打包脚本** `scripts/build.sh`：一键产出 `dist/page-translator-chrome-v{版本}.zip`（Chrome/Edge 通用）和 `dist/page-translator-firefox-v{版本}.zip`。

### 3.6 Phase 2 性能优化（commit `f45d779`）

按技术路线的 Phase 2 实施（429 重试和流式显示按需求方决定暂不做）：

**① 翻译缓存**（background.js）
- **段落粒度**缓存（非批次粒度）：key = FNV-1a hash(`段落文本|目标语言|模型名`)，批次组合变化不影响命中
- 存 `chrome.storage.local`，LRU 淘汰（上限 2000 条）+ 7 天 TTL
- 部分命中时只把未命中段落发给 API，结果合并后写回
- 设置页新增"清除翻译缓存"按钮
- 效果：重复访问相同页面时几乎瞬时完成，零 API 消耗

**② 批次并发**（content.js）
- 串行 for 循环 → worker pool：3 个 worker 从批次队列领任务，先完成先插入
- 选 worker pool 而非 `Promise.all` 全量并发：控制在途请求数，避免触发网关 429
- 效果：长页面翻译速度约 3 倍
- 已知 trade-off：并发批次间无上下文共享，术语一致性略降（Phase 3 术语表可解决）

**③ 翻译进度条**（popup）
- 实时进度条 + "15 / 42 段" 文字，翻译完成后自动隐藏

### 3.7 Phase 4 交互体验（2026-08-20 ～ 08-21）

按 Phase 4 规划实施，快捷键、右键菜单暂缓，实际落地的功能：

**① 替换显示模式**（content.js / content.css / popup）
- 弹窗新增"显示模式"下拉框：双语对照（默认）/ 替换原文
- 替换模式下译文直接顶替原文显示，页面排版不变；原文子节点整体移入隐藏 span（不销毁 DOM，链接/图片/公式渲染保留），还原时移回
- 悬停段落 **1 秒**后切回原文（首版纯 CSS `:hover` 即时切换太突兀，改为 JS 定时器延迟），移开恢复译文；延迟时长为 `content.js` 里的 `HOVER_DELAY_MS`

**② 划词翻译**（content.js / content.css / popup）
- 交互方案选型：划词后弹"译"按钮，点击才翻译（否决了"划词直接翻译"——复制/双击选词都会误触发 API 调用；也否决了"划词+快捷键"——可发现性差）
- 弹窗新增"翻译方式"下拉框：整页翻译 / 划词翻译，两种方式互斥（整页模式下划词不弹按钮），选择持久化且即时生效
- 划词模式下附"自动翻译"勾选项：停止划词 1 秒后直接出译文，无需点按钮；期间任何鼠标/键盘/滚动操作都取消触发
- 结果气泡自适应视口位置（下方放不下翻上方）；长译文气泡内可滚轮翻页（修了两个 bug：window 捕获阶段 scroll 监听误伤气泡内部滚动、滚动链传导到页面触发"滚动即关闭"，后者用 `overscroll-behavior: contain` 切断）
- 划词结果同样走翻译缓存
- 跨段落选区按单条纯文本处理（未做段落级 DOM 映射，简单够用）
- 设置页曾有"启用划词翻译"总开关，与"翻译方式"入口冗余，已删除

**③ 停止 / 继续翻译**（content.js / popup）
- 翻译中按钮变红色"停止翻译"：worker 不再领取新批次，在途请求（≤3 个）等返回并插入译文（API 消耗不浪费）
- 停止后按钮变"继续翻译"，点击从剩余段落续翻（复用 `data-llm-translated` 去重，断点续翻零成本）；还原页面后按钮复位
- 弹窗关闭重开能通过 `GET_STATUS` 恢复正确按钮状态（翻译中→停止翻译；有部分译文→继续翻译），停止等待用轮询兜底

### 3.8 小模型（vLLM/SGLang 本地部署）适配（2026-08-21）

用户在 vLLM 上部署 Qwen3.5 2B 实测，暴露出小模型不遵循"输出等长 JSON 数组"协议的一系列问题，逐个解决：

| 问题 | 原因 | 解决 |
|------|------|------|
| 整批段落无译文，报"无法解析 JSON" | 2B 模型输出数组中途开始"叙述"而非翻译 | `BATCH_SIZE` 10 → 4（批次越小小模型越稳）；报错截断 200 → 500 字符；background 完整打印模型原始返回到 SW 控制台 |
| `Unterminated string in JSON` | 未设 `max_tokens`，vLLM 默认值偏小，长批次输出被服务端截断 | 请求显式带 `max_tokens: 4096`；解析层加"截断救回"兜底（丢弃最后一项不完整的，补 `]` 再解析） |
| 划词翻译报错但译文明明是对的 | 单条文本时小模型直接输出纯文本译文，不包 JSON 数组 | 解析层加"纯文本降级"兜底（整段内容当作译文放行） |
| 格式错乱偶发、重试可恢复 | 小模型指令遵循不稳定 | 批次级重试最多 3 次：仅 JSON 解析失败触发；HTTP 错误（429/Key 无效等）不重试；截断救回与纯文本降级两个有损兜底仅在最后一次尝试启用，前两次失败先重试要正确格式 |

**vLLM / SGLang 部署备忘**：两者均提供 OpenAI 兼容接口，插件零改动支持。设置页填 `http://<IP>:<端口>/v1`，Key 留空，模型名必须与服务端一致（`curl <base>/v1/models` 查 `data[0].id`；vLLM 是 `--model` 的值、默认端口 8000，SGLang 是 `--model-path` 的值、默认端口 30000，均可用 `--served-model-name` 起别名）。服务需 `--host 0.0.0.0` 才能被局域网访问。2B 量级模型格式遵循能力有限，插件已通过批次重试、截断救回、纯文本降级等机制适配，日常可用；追求更稳的格式遵循可用 9B。

---

## 四、分发方式

| 方式 | 适用场景 | 操作 |
|------|---------|------|
| git clone 源码 | 团队内部（推荐） | clone 后 `chrome://extensions/` 开发者模式加载目录 |
| zip 包 | 不方便 git 的同事 | `./scripts/build.sh` 打包，解压后同上加载 |
| Chrome Web Store | 对外发布（暂无计划） | 需 $5 开发者账号 + 隐私政策页面 URL + 审核 |

上架商店无需法律协议，但因插件会把页面文本发给 API，Google 要求提供隐私政策。开源协议（MIT/Apache 2.0）可选，内部项目暂未添加。

---

## 五、Git 提交历史

| commit | 内容 |
|--------|------|
| `fb81fd9` | 初始化插件框架（MV3、双语对照、设置页、预设、Origin 头移除、额外请求头） |
| `a4288a9` | LaTeX 公式/行内代码占位符保护；技术路线文档 |
| `f45d779` | Phase 2：翻译缓存、3 路并发、进度条；Firefox 适配；打包脚本 |
| `fa4ab58` | 开发日志 |
| `1143903` | Phase 4：替换模式、划词翻译、停止/继续；小模型适配（重试、兜底、批次调优） |

---

## 六、遗留问题与下一步

**已知问题**：
- 网关 429 限流未做自动重试（重试只针对模型格式错乱；触发限流时该批次直接失败，报错提示）
- 动态加载内容（无限滚动）需要手动再点一次翻译
- 推理类模型每次输出思维链，翻译偏慢——建议使用非推理的翻译专用模型（如 Index-Translate）
- 并发批次间术语一致性略降
- 小模型（2B 级）整页翻译仍可能偶发段落留空（有损兜底的代价），建议 7B 以上
- 划词跨段落按单条纯文本处理，多段排版依赖模型输出

**下一步候选**（按技术路线）：
- Phase 3 翻译质量：自定义 prompt、术语表、自动语言检测
- Phase 4 剩余项：快捷键、右键菜单
- 429 指数退避重试（如果实际使用中频繁触发）

---

## 七、测试备忘

- 改代码后：`chrome://extensions/` 点插件刷新按钮 + 刷新测试网页（改了 manifest 必须重载插件）
- 后台日志：插件卡片 → "Service Worker" 链接 → DevTools
- API 连通性：设置页"测试连接"按钮（翻译 "Hello, world!"），或直接 curl
- 公式保护：找知乎数学类文章验证公式在译文中原样保留
- 缓存验证：同一页面翻译 → 还原 → 再翻译，第二次应瞬时完成
- Ollama 本地测试：`OLLAMA_ORIGINS="*" ollama serve`（否则 403）
