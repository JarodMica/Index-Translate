# LLM 网页翻译插件 — 技术路线文档

> 项目：index-page-mt（LLM Page Translator）
> 版本：v0.1.0（已实现）→ v1.0.0（目标）
> 最后更新：2026-08-06

---

## 一、整体架构

```
┌──────────────────────────────────────────────────────────┐
│                    Chrome Extension MV3                  │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐ │
│  │   popup/     │  │  options/   │  │  content/        │ │
│  │  弹窗 UI     │  │  设置页     │  │  content.js      │ │
│  │  翻译/还原   │  │  API 配置   │  │  + content.css   │ │
│  └──────┬───────┘  └──────┬──────┘  │  注入到每个网页  │ │
│         │                 │         └────────┬─────────┘ │
│         │  chrome.       │                   │           │
│         │  runtime.      │                   │           │
│         │  sendMessage   │                   │           │
│         ▼                 ▼                   ▼           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              background.js (SW)                     │ │
│  │                                                     │ │
│  │  ┌─────────────┐ ┌──────────┐ ┌──────────────────┐ │ │
│  │  │ LLM 适配层  │ │ 缓存层   │ │ 请求调度/重试    │ │ │
│  │  │  openai     │ │ key=hash │ │  并发+限流+排队   │ │ │
│  │  │  compat.    │ │ →transl. │ │  429 自动退避     │ │ │
│  │  └──────┬──────┘ └──────────┘ └──────────────────┘ │ │
│  │         │                                            │ │
│  └─────────┼────────────────────────────────────────────┘ │
│            │  declarativeNetRequest                      │
│            │  (移除 Origin 头)                            │
│            ▼                                              │
│     ┌───────────────┐                                    │
│     │  LLM API 网关  │  OpenAI 兼容 /chat/completions   │
│     │  /v1           │  vLLM / SGLang / ...             │
│     └───────────────┘                                    │
└──────────────────────────────────────────────────────────┘
```

**各部分的职责边界**：

| 模块 | 运行环境 | 职责 |
|------|---------|------|
| content.js | 网页页面上下文 | DOM 遍历、文本提取、译文插入/还原 |
| background.js | Service Worker（独立线程） | API 调用、翻译编排、缓存、请求重试 |
| popup | 网页页面上下文（弹窗） | 触发翻译/还原、显示进度 |
| options | 网页页面上下文（设置页） | 配置管理、连接测试 |

翻译指令的流向：**popup → content.js**（提取文本）→ **background.js**（调 API）→ **content.js**（插入译文）。content 和 background 之间通过 `chrome.runtime.sendMessage` 通信。

---

## 二、页面文本提取（断句策略）

这是翻译质量的第一个环节——提取什么、以什么粒度提取，直接决定了上下文窗口的利用效率和译文的连贯性。

### 2.1 提取目标：块级翻译单元

以**块级 HTML 元素**为翻译单元，而非单词、句子或整段 div。

**采用的块级标签**：
```
P, H1–H6, LI, TD, TH, BLOCKQUOTE, FIGCAPTION, DT, DD, SUMMARY
```

选择理由：
- **P / H\***：标准段落标题，语义完整
- **LI**：列表项各自独立翻译，避免列表标签混入文本干扰 LLM
- **TD / TH**：表格单元格是独立的语义单元
- 共同特点：`innerText` 直接返回可读文本，不需要额外清理

**排除的标签**：
```
SCRIPT, STYLE, NOSCRIPT, TEXTAREA, INPUT, SELECT, CODE, PRE,
KBD, SVG, CANVAS, IFRAME
```
- CODE / PRE：代码块不应翻译
- INPUT / TEXTAREA：表单元素不是展示内容
- SVG / CANVAS：非文本内容

### 2.2 提取算法

```
1. TreeWalker 遍历 document.body（show_element 模式）
2. 对每个候选元素，filter 逻辑：
   a. 若元素在 SKIP_TAGS 中 → FILER_REJECT（跳过整棵子树）
   b. 若在 BLOCK_TAGS 中 → FILTER_ACCEPT
   c. 其他 → FILTER_SKIP（不接受但继续遍历子节点）
3. 对接受的元素做后处理：
   a. 嵌套块级元素（如 li > p）只取最内层，避免重复翻译
   b. 跳过不可见元素（display:none / visibility:hidden）
   c. 跳过已标记 data-llm-translated 的元素
   d. 跳过 text.length < 2 的空/过短元素
   e. 跳过纯数字/符号的元素（正则 /[\d\s\p{P}]+/u）
   f. 跳过 contentEditable 元素
```

### 2.3 未来：中文断句优化

中文没有天然的词边界空格，分词处理和英文不同。不过在我们这个架构里，**分句断点不在提取阶段处理，而是交给 LLM**：

- 提取阶段：以块级元素为单位，保持语义完整性
- prompt 中要求 LLM "逐项翻译"，模型天然擅长断句
- 只需要确保单个块的 token 数不超出模型上下文窗口即可

如果未来做**句子级翻译**（如逐句高亮），则需要增加分句逻辑：

```
中文分句标点：。！？；…
英文分句标点：. ! ? ;
通用：换行符 \n\n
```

用正则 `/(?<=[。！？；…?!.])\s*/` 或更复杂的基于 Unicode 断句规则切分。

---

## 三、翻译 Pipeline

### 3.1 批次处理

页面段落按批次发给 API，而非逐段逐段调用：

```
BATCH_SIZE = 10  （默认值，可调）

流程：
page_paragraphs → [p0..p9] → API → [t0..t9]
                 [p10..p19] → API → [t10..t19]
                 ...（串行执行）

插入：
t_i 插入到 p_i 的 afterend 位置
```

选择 10 的依据：
- 太大：单个请求 token 过多、超时风险增加、出错重试代价大
- 太小：请求数多，429 限流风险高，延迟叠加
- 10 是一个经验值，后续根据实测调整

### 3.2 Token 管理

发给 API 的请求结构：

```json
{
  "model": "Index-Translate-2B",
  "temperature": 0.2,
  "messages": [
    {
      "role": "system",
      "content": "<翻译 prompt，约占 150-200 tokens>"
    },
    {
      "role": "user",
      "content": "<JSON 数组，每个元素是原文段落>"
    }
  ]
}
```

**单批最大输入量估算**：
- 模型上下文：8K~128K（取决于具体模型）
- system prompt：~200 tokens
- JSON 开销：`["` `"]`、逗号、转义引号等
- 安全上限：预留 output tokens（通常是 input 的 1.5~2 倍中文输出）
- **经验公式**：单批输入控制在 2000~3000 tokens 内

**单段估算**：
- 英文：~1.3 tokens/word，一段约 100~200 tokens
- 10 段 ≈ 1000~2000 tokens，安全范围内

**动态批次大小**（未来优化）：
```js
// 简单估算：按字符数动态调整批次大小
function estimateTokens(text) {
  // 粗略：英文 ~4 字符/token，中文 ~2 字符/token
  return Math.ceil(text.length / 3);
}

function buildBatches(blocks, maxTokensPerBatch = 3000) {
  const batches = [];
  let currentBatch = [];
  let currentTokens = 0;

  for (const block of blocks) {
    const tokens = estimateTokens(block.text);
    if (currentTokens + tokens > maxTokensPerBatch && currentBatch.length > 0) {
      batches.push(currentBatch);
      currentBatch = [];
      currentTokens = 0;
    }
    currentBatch.push(block);
    currentTokens += tokens;
  }
  if (currentBatch.length > 0) batches.push(currentBatch);
  return batches;
}
```

### 3.3 Prompt 工程

当前 system prompt 设计：

```
你是一个专业的翻译引擎。将用户给出的 JSON 字符串数组中的每一项翻译成{目标语言}。
要求：
1. 只输出一个 JSON 字符串数组，长度与输入完全一致，顺序一一对应。
2. 保留原文中的专有名词、代码、数字格式。
3. 如果某项本身就是目标语言或无需翻译（如纯数字、URL），原样返回该项。
4. 不要输出任何解释或 markdown 代码块标记。
```

**为什么用 JSON 数组格式**：
- 保持段落一一对应，无需额外 ID 标记
- 解析简单可靠（相比分隔符格式）
- 模型对此格式的遵循度高（属于 I/O 格式约束类任务）

**后续 prompt 优化方向**：

1. **带上下文的 prompt**：把同一批次的多个段落一起发给模型，能保持翻译的一致性和连贯性
2. **术语表注入**：在 system prompt 中添加领域专有名词的指定译法
3. **风格约束**：添加翻译风格要求（如学术、口语、技术文档等）
4. **few-shot**：添加少量示例翻译，提升特定场景的翻译质量

```js
// 示例：带术语表的 system prompt 构建
function buildSystemPrompt(targetLang, glossary = {}) {
  let prompt = `你是一个专业的翻译引擎。将用户给出的 JSON 字符串数组中的每一项翻译成${targetLang}。`;

  if (Object.keys(glossary).length > 0) {
    prompt += `\n\n术语表（必须严格遵循）：\n`;
    for (const [en, zh] of Object.entries(glossary)) {
      prompt += `- "${en}" → "${zh}"\n`;
    }
  }

  prompt += `\n要求：\n1. 只输出一个 JSON 字符串数组...`;
  return prompt;
}
```

### 3.4 响应解析

模型返回的内容需要容错解析，因为输出可能有几种异常格式：

```
正常：["译文1", "译文2", "译文3"]
异常1：```json\n["译文1", "译文2"]\n```    ← markdown 代码块包裹
异常2：这是翻译结果：\n["译文1", "译文2"]   ← 前面有废话
异常3：["译文1"]                             ← 长度比输入少（模型省略了部分）
异常4：{"translations": ["译文1"]}           ← 不是数组
```

**解析流程**（`parseTranslations` 函数）：

```
1. trim() 去首尾空白
2. 尝试匹配 /```(?:json)?\s*([\s\S]*?)\s*```/ 提取代码块内容
3. JSON.parse()
4. 若失败，尝试截取第一个 [ 到最后一个 ] 之间的内容再 parse
5. 若非数组，报错
6. 长度不足：用空字符串补齐（容错，不丢段落映射）
7. 长度超长：截断（slice）
8. 非字符串元素：String() 强转
```

---

## 四、译文展示模式

### 4.1 双语对照（当前）

```
原文段落（不变）
  ┌─────────────────────────────────┐
  │ ╎ 译文段落（蓝色左边框）         │
  └─────────────────────────────────┘
```

- 每个译文作为新 `div.llm-translation` 插入到原文的 `afterend`
- 原文 DOM 结构完全不变，译文是额外元素
- 通过 `data-llm-translated` 属性标记已翻译的元素，防止重复翻译
- 还原时直接 remove 这些插入的 DOM 节点

### 4.2 替换模式（计划）

```
译文段落（替代原文位置，原文隐藏而非删除）
  ↕ hover 时显示原文
```

实现方案：

```css
/* 替换模式的 CSS */
.llm-replaced-original {
  display: none;
}
.llm-replaced-translation:hover .llm-original-text {
  display: block;
  color: #888;
  font-size: 0.9em;
}
```

```js
// 替换模式的 DOM 操作
function replaceWithTranslation(block, translation) {
  // 隐藏原文，不删除（方便还原）
  block.element.dataset.llmHidden = "1";
  block.element.style.display = "none";

  const wrapper = document.createElement("div");
  wrapper.className = "llm-replaced-translation";

  // 译文
  const translationEl = document.createElement("span");
  translationEl.textContent = translation;
  wrapper.appendChild(translationEl);

  // hover 显示原文（原文内容暂存）
  const originalEl = document.createElement("div");
  originalEl.className = "llm-original-text";
  originalEl.style.display = "none";
  originalEl.textContent = block.text;
  wrapper.appendChild(originalEl);

  block.element.insertAdjacentElement("afterend", wrapper);
}
```

### 4.3 行内高亮模式（计划）

在原文基础上，对已翻译的文本做行内颜色高亮，hover 显示译文：

```
Machine learning [→ 机器学习] is a branch of artificial intelligence [→ 人工智能].
```

适用于短文本场景，需要句子级提取和精确定位。

---

## 五、性能优化

### 5.1 并发请求

当前：串行（批次 A 完成后才开始批次 B）

```
当前：  [===A===] → [===B===] → [===C===] → 完成
优化后：[===A===]
        [===B===]  → 所有完成后批量插入
        [===C===]
```

**实现方案**：

```js
const MAX_CONCURRENT = 3; // 最大并发数

async function translateParallel(blocks) {
  const batches = buildBatches(blocks);
  const results = new Array(batches.length);
  const executing = new Set();

  for (let i = 0; i < batches.length; i++) {
    const idx = i;
    const promise = sendBatch(batches[idx].map(b => b.text))
      .then(resp => { results[idx] = resp; })
      .finally(() => { executing.delete(promise); });

    executing.add(promise);

    if (executing.size >= MAX_CONCURRENT) {
      await Promise.race(executing);
    }
  }

  await Promise.all(executing);

  // 批量插入译文
  for (let i = 0; i < batches.length; i++) {
    if (results[i]?.ok) {
      batches[i].forEach((block, j) =>
        insertTranslation(block, results[i].translations[j])
      );
    }
  }
}
```

**注意**：并发可能导致翻译质量略降（模型缺少跨段上下文），但速度提升显著。可作为选项让用户选择。

### 5.2 翻译缓存

相同内容不重复翻译，极大提升重复访问同一网站时的速度。

**缓存 key 设计**：

```js
// 方案 A：内容 hash（推荐）
function cacheKey(text, targetLang, model) {
  // 简单拼接 hash，不依赖外部库
  const input = `${text}|||${targetLang}|||${model}`;
  // 使用 FNV-1a 或简单 hash
  return hashString(input);
}

// 缓存存储结构（chrome.storage.local，限制 ~5MB）
// key: cacheKey
// value: { translation, timestamp }
```

**缓存淘汰策略**：
- `chrome.storage.local` 有 ~5MB 上限
- LRU 淘汰：按访问时间排序，超出容量时删除最旧的
- TTL：超过 7 天的缓存自动失效（网页内容会更新）

```js
const CACHE_MAX = 2000; // 最多缓存条目
const CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 天

async function getCachedTranslation(key) {
  const result = await chrome.storage.local.get(key);
  const entry = result[key];
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL) {
    await chrome.storage.local.remove(key);
    return null;
  }
  return entry.translation;
}

async function setCache(key, translation) {
  const data = { [key]: { translation, timestamp: Date.now() } };
  await chrome.storage.local.set(data);
  // TODO: LRU 淘汰检查
}
```

### 5.3 流式显示（Streaming）

当前：整批返回后一次性插入 → 用户等待时间长

优化：用 SSE（Server-Sent Events）逐段流式返回：

```js
async function translateStream(texts, onPartial) {
  const resp = await fetch(url, {
    ...options,
    body: JSON.stringify({
      ...payload,
      stream: true, // 告诉 API 返回 SSE 流
    }),
  });

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // 保留不完整的行

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") break;

      try {
        const chunk = JSON.parse(data);
        const token = chunk.choices?.[0]?.delta?.content;
        if (token) {
          onPartial(token); // 逐 token 回调
        }
      } catch (e) {
        // 忽略不完整的 JSON
      }
    }
  }
}
```

**流式显示策略**：
- 首 token 到达时，立即插入一个空的译文容器
- 后续 token 逐个追加到容器中
- 光标跟随效果：最后插入的译文块自动滚动到可视区域

**限制**：
- vLLM / SGLang 本地模型默认支持 streaming
- 需要逐段调用而非批量（因为是流式），可考虑"伪批量流式"：先流式返回数组，解析到每个 `"` 结束时就插入对应段落

---

## 六、请求调度与限流

### 6.1 429 重试策略

部分网关/服务会有 429 限流，必须处理。

```js
async function requestWithRetry(fn, maxRetries = 3) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (err.status === 429 && attempt < maxRetries) {
        const retryAfter = err.headers?.["retry-after"];
        const baseDelay = retryAfter
          ? parseInt(retryAfter) * 1000
          : 1000 * Math.pow(2, attempt); // 指数退避: 1s, 2s, 4s
        const jitter = Math.random() * 500; // 随机抖动
        await sleep(baseDelay + jitter);
        continue;
      }
      throw err;
    }
  }
}
```

### 6.2 速率限制器（令牌桶）

主动限速，预防触发网关 429：

```js
class RateLimiter {
  constructor(maxPerMinute = 20) {
    this.maxPerMinute = maxPerMinute;
    this.tokens = maxPerMinute;
    this.lastRefill = Date.now();
  }

  async acquire() {
    this.refill();
    if (this.tokens <= 0) {
      const waitMs = 60000 / this.maxPerMinute;
      await sleep(waitMs);
      this.refill();
    }
    this.tokens--;
  }

  refill() {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 60000;
    this.tokens = Math.min(
      this.maxPerMinute,
      this.tokens + elapsed * this.maxPerMinute
    );
    this.lastRefill = now;
  }
}
```

### 6.3 完整的请求调度器

```js
class TranslationScheduler {
  constructor(settings) {
    this.settings = settings;
    this.limiter = new RateLimiter(20); // 20 requests/min
    this.queue = [];
    this.running = 0;
    this.maxConcurrent = settings.maxConcurrent || 3;
  }

  async submit(texts) {
    return new Promise((resolve, reject) => {
      this.queue.push({ texts, resolve, reject });
      this.processQueue();
    });
  }

  async processQueue() {
    while (
      this.running < this.maxConcurrent &&
      this.queue.length > 0
    ) {
      const task = this.queue.shift();
      this.running++;
      this.limiter.acquire().then(async () => {
        try {
          const result = await this.translate(task.texts);
          task.resolve(result);
        } catch (err) {
          task.reject(err);
        } finally {
          this.running--;
          this.processQueue();
        }
      });
    }
  }

  async translate(texts) {
    return requestWithRetry(() => callAPI(this.settings, texts));
  }
}
```

---

## 七、设置与配置

### 7.1 配置存储结构

使用 `chrome.storage.sync`（跨设备同步），结构：

```js
{
  apiBaseUrl: "http://localhost:8000/v1",     // API 地址
  apiKey: "",                                 // API Key（本地部署留空；明文存储在 Chrome 内部存储）
  model: "Index-Translate-2B",                   // 模型名
  targetLang: "中文",                             // 目标语言
  temperature: 0.2,                              // 温度
  extraHeaders: '{"X-Foo":"bar"}',               // 额外请求头（JSON 字符串）
  batchSize: 10,                                 // 批次大小
  displayMode: "bilingual",                      // 展示模式: bilingual | replace | inline
  maxConcurrent: 3,                              // 最大并发请求数
  glossary: {                                    // 术语表
    "Machine Learning": "机器学习",
    "API": "API"
  },
  cacheEnabled: true,                            // 启用翻译缓存
}
```

### 7.2 配置安全

- `apiKey` 存储在 `chrome.storage` 中，不在代码里硬编码
- `chrome.storage` 仅在本机可用，不会同步到 Google 账号（API Key 等敏感字段会被 Chrome 排除在同步之外）
- 翻译缓存存在 `chrome.storage.local`（仅本地，~5MB 上限）
- 不会将 API Key 发送到除配置的 API 地址以外的任何地方

---

## 八、多语言/多模型适配

### 8.1 目标语言支持

通过 prompt 中的 `{targetLang}` 参数控制，理论上支持所有 LLM 能理解的语言。设置页提供预设列表，同时支持自定义输入：

```
预设：中文、英文、日文、韩文、西班牙文、法文、德文…
自定义：任意语言名（直接写给模型即可）
```

### 8.2 多模型适配层

所有 LLM 服务都走 OpenAI 兼容接口（`/v1/chat/completions`），唯一差异是：

| 差异点 | 处理方式 |
|--------|---------|
| base URL 不同 | 用户在设置页配置 |
| API Key 有无 | 本地模型留空 |
| 额外请求头 | extraHeaders 配置 |
| 模型能力差异 | 暗色提示：推理模型较慢，建议用非推理模型 |
| streaming 支持 | 检测模型是否支持，不支持则回退到非流式 |

**不做**为每种模型写特殊适配——统一走 OpenAI 格式是当前的正确选择。如果未来遇到不兼容的模型（如 Claude 原生 API），再单独适配。

---

## 九、迭代阶段规划

### Phase 1：基础可用 ✅（v0.1，当前）
- [x] Manifest V3 框架
- [x] Chrome 插件基础结构（manifest / background / content / popup / options）
- [x] 块级段落提取（TreeWalker + 块级标签）
- [x] 批次翻译（JSON 数组格式）
- [x] 双语对照展示（译文块插入 afterend）
- [x] 一键还原
- [x] 设置页（API 地址 / Key / 模型 / 目标语言）
- [x] 预设快速填入（vLLM / SGLang × Index-Translate-2B / 9B）
- [x] 自定义额外请求头
- [x] Origin 头移除（解决扩展请求 403）
- [x] 测试连接功能

### Phase 2：稳定与性能
- [ ] **429 重试 + 指数退避**：处理网关限流
- [ ] **翻译缓存**：相同内容不重复请求，LRU + TTL 淘汰
- [ ] **批次并发**：3 路并发，速度提升 ~3x
- [ ] **流式显示**：逐段/逐 token 渲染，减少等待焦虑
- [ ] **错误处理增强**：网络断开、API 超时、token 超限的友好提示
- [ ] **翻译进度条**：显示"翻译中 15/42 段"

### Phase 3：翻译质量
- [ ] **自定义翻译 Prompt**：在设置页编辑 system prompt
- [ ] **术语表**：设置页维护专有名词对照表，注入 prompt
- [ ] **上下文连贯**：同一批次的段落作为连贯文本翻译，保持术语和语气一致
- [ ] **翻译风格选择**：学术 / 口语 / 技术文档 / 直译
- [ ] **自动语言检测**：跳过已是目标语言的页面
- [ ] **选择性翻译**：用户选中某段文字再翻译，而非整页

### Phase 4：交互体验
- [ ] **替换模式**：译文替代原文，hover 显示原文
- [ ] **行内高亮模式**：原文上 inline 标注译文
- [ ] **一键切换三种展示模式**（双语对照 / 替换 / 行内）
- [ ] **快捷键**：如 Alt+T 翻译，Alt+R 还原
- [ ] **翻译结果持久化**：页面刷新后仍显示上次译文（基于缓存）
- [ ] **右键菜单**：选中文字 → 右键 → 翻译选中内容

### Phase 5：高级功能
- [ ] **PDF 翻译**：处理 PDF.js 渲染的学术论文页面
- [ ] **图片文字翻译**：OCR + LLM 翻译截图/图片中的文字
- [ ] **翻译记忆库**：本地积累的翻译对，提供一致的译法
- [ ] **多模型切换**：针对不同场景用不同模型（快 vs 准）
- [ ] **翻译 API 中转**：自建翻译服务，支持团队共享术语库
- [ ] **Firefox 兼容**：调整 manifest 适配 Firefox MV2/MV3

---

## 十、关键技术决策与备忘

### 10.1 Manifest V3 vs V2

选择 V3 的原因：
- Chrome 已强制要求 V3，V2 即将停止支持
- V3 用 Service Worker 替代 Background Page，不占常驻内存
- Service Worker 有限制：不能用 `XMLHttpRequest`（必须用 fetch），有生命周期（空闲时会被杀）
- Service Worker 被唤醒时会重新执行 `setupOriginStrippingRule()`，`updateDynamicRules` 是幂等的，无副作用

### 10.2 Chrome 插件的 CORS

- Service Worker 发出的 fetch 请求不受网页的 CORS 限制（因为 SW 不在任何网页上下文中）
- 但浏览器会自动给请求附加 `Origin: chrome-extension://<id>` 头
- 部分网关/服务会拒绝非 http/https 的 Origin → 需要 declarativeNetRequest 移除
- 本地推理框架对 Origin 校验较宽松，必要时可通过扩展的 declarativeNetRequest 移除 Origin 头

### 10.3 chrome.storage 限制

- `chrome.storage.sync`：跨设备同步，每项 ~8KB，总 ~100KB
- `chrome.storage.local`：仅本地，每项 ~5MB，总 ~5MB
- 翻译缓存用 `sync` 还是 `local`？→ 缓存体积大，用 `local`；用户配置用 `sync`
- API Key 在 `sync` 中会被 Chrome 排除同步（安全策略），只留在本机

### 10.4 Service Worker 生命周期

MV3 的 Service Worker 在空闲 ~30 秒后会被 Chrome 终止。对我们的影响：
- 翻译过程中如果用户不操作，SW 可能被杀
- 解决方案：翻译期间通过持续的 `chrome.runtime.sendMessage` 保持 SW 活跃
- 或者在翻译期间用 `chrome.alarms` 定期唤醒

---

## 十一、开发规范

### 代码风格
- 纯原生 JS，不使用构建工具和 npm 依赖
- 使用 ES2020+ 语法（async/await、可选链、模板字符串）
- 不使用 TypeScript（简化开发流程，类型安全靠注释和代码审查）
- 函数和变量命名：camelCase，语义化

### Git 规范
- commit message：`<type>: <description>`
- type：feat / fix / refactor / docs / style / test
- 分支：`main`（稳定）、`dev`（开发）、`feat/*` / `fix/*`

### 测试方法
- 手动测试为主（插件无法用 Jest 等自动化测试）
- 各模块独立测试：`background.js` 的 API 调用可用 curl 验证
- `content.js` 可在浏览器 DevTools 的 Console 中模拟调用
- 设置页可通过"测试连接"功能验证 API 配置
