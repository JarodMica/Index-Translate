// background.js — Service Worker
// 职责：接收 content script 发来的翻译请求，调用大模型 API，返回译文。
// 在后台调用 API 可以绕开网页自身的 CORS 限制（扩展有 host_permissions）。

  const DEFAULT_SETTINGS = {
  // 本插件面向本地部署的 Index-Translate 系列模型（vLLM / SGLang 等框架）；
  // 任何 OpenAI 兼容接口理论上都可用，但推荐本地部署：
  //   vLLM:   http://localhost:8000/v1   （vllm serve IndexTeam/Index-Translate-2B --served-model-name Index-Translate-2B）
  //   SGLang: http://localhost:30000/v1  （python -m sglang.launch_server --model-path IndexTeam/Index-Translate-2B --served-model-name Index-Translate-2B）
  apiBaseUrl: "http://localhost:8000/v1",
  apiKey: "",
  model: "Index-Translate-2B",
  targetLang: "中文",
  temperature: 0.2,
  extraHeaders: "", // JSON 对象字符串，如 {"X-Foo": "bar"}，会附加到每个 API 请求
};

const MAX_TOKENS = 4096; // 输出 token 上限，防止模型生成中途被截断（小模型尤易发生）
const MAX_ATTEMPTS = 3; // 模型格式错乱（JSON 解析失败）时的最大尝试次数

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

// 浏览器会给扩展发出的请求自动附加 Origin: chrome-extension://... 头，
// 部分本地服务（如 Ollama、带鉴权网关的部署）会因此返回 403。
// fetch 无法删除该头，这里用 declarativeNetRequest 在网络层移除。
// Firefox 的扩展源是随机 UUID，initiatorDomains 条件不适用，失败时降级为无条件规则。
async function setupOriginStrippingRule() {
  const baseRule = {
    id: 1,
    priority: 1,
    action: {
      type: "modifyHeaders",
      requestHeaders: [{ header: "Origin", operation: "remove" }],
    },
  };
  try {
    await chrome.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: [1],
      addRules: [
        {
          ...baseRule,
          condition: {
            initiatorDomains: [chrome.runtime.id],
            resourceTypes: ["xmlhttprequest"],
          },
        },
      ],
    });
  } catch (e) {
    try {
      await chrome.declarativeNetRequest.updateDynamicRules({
        removeRuleIds: [1],
        addRules: [
          {
            ...baseRule,
            condition: { resourceTypes: ["xmlhttprequest"] },
          },
        ],
      });
    } catch (e2) {
      console.warn("Origin 头移除规则注册失败（部分网关可能返回 403）:", e2.message);
    }
  }
}
setupOriginStrippingRule();

// ---------- 翻译缓存 ----------
// 按"段落文本 + 目标语言 + 模型"为 key 缓存译文，存 chrome.storage.local（~10MB 上限）。
// 段落粒度缓存：即使批次组合不同，单段命中也能省请求。

const CACHE_KEY = "llmTranslationCache";
const CACHE_MAX_ENTRIES = 2000;
const CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 天

function fnv1a(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(36);
}

async function loadCache() {
  const res = await chrome.storage.local.get(CACHE_KEY);
  return res[CACHE_KEY] || {};
}

async function saveCache(cache) {
  const entries = Object.entries(cache);
  // 超出容量时按最后访问时间淘汰最旧的（LRU）
  if (entries.length > CACHE_MAX_ENTRIES) {
    entries.sort((a, b) => a[1].t - b[1].t);
    for (const [key] of entries.slice(0, entries.length - CACHE_MAX_ENTRIES)) {
      delete cache[key];
    }
  }
  await chrome.storage.local.set({ [CACHE_KEY]: cache });
}

// 带缓存的批量翻译：先查缓存，只把未命中的段落发给 API，结果合并后写回缓存。
async function translateWithCache(texts, settings) {
  const cacheKeyOf = (text) => fnv1a(`${text}|${settings.targetLang}|${settings.model}`);
  const cache = await loadCache();
  const now = Date.now();

  const results = new Array(texts.length).fill("");
  const missIndexes = [];

  for (let i = 0; i < texts.length; i++) {
    const entry = cache[cacheKeyOf(texts[i])];
    if (entry && now - entry.t < CACHE_TTL) {
      results[i] = entry.v;
      entry.t = now; // 刷新访问时间（LRU）
    } else {
      missIndexes.push(i);
    }
  }

  if (missIndexes.length > 0) {
    const fresh = await translateBatch(missIndexes.map((i) => texts[i]), settings);
    missIndexes.forEach((i, j) => {
      results[i] = fresh[j];
      if (fresh[j]) {
        cache[cacheKeyOf(texts[i])] = { v: fresh[j], t: now };
      }
    });
  }

  await saveCache(cache);
  return results;
}

// 调用 OpenAI 兼容的 /chat/completions 接口翻译一批文本。
// 输入输出都用 JSON 数组，保证段落一一对应。
// 模型不遵循格式（JSON 解析失败）时重试，最多 MAX_ATTEMPTS 次；
// HTTP 错误（如 429 限流、Key 无效）不重试，直接报错。
async function translateBatch(texts, settings) {
  let lastErr = null;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      // 最后一次尝试才允许"纯文本降级"兜底，前几次失败就重试，争取拿到正确格式
      return await requestTranslation(texts, settings, attempt === MAX_ATTEMPTS);
    } catch (err) {
      if (err.noRetry) throw err;
      lastErr = err;
      console.warn(`[llm-translator] 第 ${attempt}/${MAX_ATTEMPTS} 次尝试失败: ${err.message}`);
    }
  }
  throw lastErr;
}

function requestTranslationError(message) {
  const err = new Error(message);
  err.noRetry = true;
  return err;
}

async function requestTranslation(texts, settings, isFinalAttempt) {
  const url = settings.apiBaseUrl.replace(/\/+$/, "") + "/chat/completions";

  const systemPrompt =
    `你是一个专业的翻译引擎。将用户给出的 JSON 字符串数组中的每一项翻译成${settings.targetLang}。\n` +
    `要求：\n` +
    `1. 只输出一个 JSON 字符串数组，长度与输入完全一致，顺序一一对应。\n` +
    `2. 保留原文中的专有名词、代码、数字格式。\n` +
    `3. 如果某项本身就是${settings.targetLang}或无需翻译（如纯数字、URL），原样返回该项。\n` +
    `4. 不要输出任何解释或 markdown 代码块标记。\n` +
    `5. 文本中可能出现占位符如 %%MATH_0%%、%%CODE_1%% 等，这是数学公式或代码的替代标记。\n` +
    `   必须原样保留这些占位符（包括大小写和编号），不要翻译、修改或省略它们。`;

  const headers = { "Content-Type": "application/json" };
  if (settings.apiKey) {
    headers["Authorization"] = `Bearer ${settings.apiKey}`;
  }
  if (settings.extraHeaders) {
    try {
      Object.assign(headers, JSON.parse(settings.extraHeaders));
    } catch (e) {
      throw requestTranslationError("额外请求头不是合法的 JSON: " + e.message);
    }
  }

  const resp = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: settings.model,
      temperature: settings.temperature,
      max_tokens: MAX_TOKENS,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: JSON.stringify(texts) },
      ],
    }),
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw requestTranslationError(`API 请求失败 (HTTP ${resp.status}): ${body.slice(0, 300)}`);
  }

  const data = await resp.json();
  const content = data?.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error("API 返回内容为空");
  }
  // 完整打印模型原始输出，便于在 Service Worker 控制台排查格式问题
  console.log("[llm-translator] 模型原始返回：\n" + content);

  return parseTranslations(content, texts.length, isFinalAttempt);
}

// 模型偶尔会包一层 ```json ... ```，或输出不合法 JSON，这里做容错解析。
// 对"输出中途被截断"的情况，尝试丢弃最后一项不完整的，救回前面完整的段落。
// allowPlainText：是否允许"纯文本降级"兜底——仅最后一次尝试开启，之前的失败交给重试。
function parseTranslations(content, expectedLength, allowPlainText) {
  let text = content.trim();
  const fenced = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/);
  if (fenced) text = fenced[1];

  let arr;
  try {
    arr = JSON.parse(text);
  } catch (e) {
    // 兜底 1：尝试截取第一个 [ 到最后一个 ] 之间的内容
    const start = text.indexOf("[");
    const end = text.lastIndexOf("]");
    if (start !== -1 && end > start) {
      try {
        arr = JSON.parse(text.slice(start, end + 1));
      } catch (_) {
        arr = null;
      }
    }
    // 兜底 2：模型输出中途截断（如字符串未闭合），丢掉最后一项不完整的，补 ] 再解析。
    // 会损失最后一段，因此仅在最后一次尝试时启用，之前的失败交给重试。
    if (!arr && allowPlainText) {
      const lastComma = text.lastIndexOf(",");
      if (lastComma > 0) {
        try {
          arr = JSON.parse(text.slice(0, lastComma) + "]");
        } catch (_) {
          arr = null;
        }
      }
    }
    // 兜底 3：模型完全没按 JSON 数组格式输出（小模型常直接返回纯文本译文），
    // 把整个内容当作第一条译文放行。仅在最后一次尝试时启用，否则先重试要格式。
    if (!arr && allowPlainText) {
      console.warn("[llm-translator] 模型未按 JSON 数组格式输出，已按纯文本降级处理:\n" + text);
      arr = [text];
    }
    if (!arr) {
      throw new Error("无法解析模型返回的 JSON: " + text.slice(0, 500));
    }
  }

  if (!Array.isArray(arr)) {
    throw new Error("模型返回的不是数组");
  }
  // 长度不一致时补齐/截断，避免整批失败
  if (arr.length < expectedLength) {
    arr = arr.concat(new Array(expectedLength - arr.length).fill(""));
  }
  return arr.slice(0, expectedLength).map((x) => (typeof x === "string" ? x : String(x)));
}

// 消息路由
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "TRANSLATE_BATCH") {
    (async () => {
      try {
        const settings = await getSettings();
        const translations = await translateWithCache(message.texts, settings);
        sendResponse({ ok: true, translations });
      } catch (err) {
        sendResponse({ ok: false, error: err.message });
      }
    })();
    return true; // 表示异步 sendResponse
  }

  if (message.type === "CLEAR_CACHE") {
    chrome.storage.local.remove(CACHE_KEY).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (message.type === "TEST_CONNECTION") {
    (async () => {
      try {
        const settings = await getSettings();
        const result = await translateBatch(["Hello, world!"], settings);
        sendResponse({ ok: true, sample: result[0] });
      } catch (err) {
        sendResponse({ ok: false, error: err.message });
      }
    })();
    return true;
  }
});
