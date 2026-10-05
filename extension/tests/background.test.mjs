// background.js 的 node 级单测（零依赖，用 node:vm + chrome API stub 直接加载脚本源码）。
// 覆盖：parseTranslations 的各类降级、请求体 chat_template_kwargs、
//       saveCache 失败不丢译文、并发批次的缓存读-改-写串行化、DNR 降级规则作用域。
//
// 运行（绿）：node extension/tests/background.test.mjs
// 红/绿对照：IT_BACKGROUND_SRC=<修前的 background.js 路径> node extension/tests/background.test.mjs
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(here, "..", "..");
const BACKGROUND_FILE = path.join(here, "..", "background.js");
const CACHE_KEY = "llmTranslationCache";

// 支持指定 ref 加载"修前"版本做红/绿对照（如 IT_BACKGROUND_REF=9cc5ee7）。
function backgroundSource() {
  if (process.env.IT_BACKGROUND_SRC) return fs.readFileSync(process.env.IT_BACKGROUND_SRC, "utf8");
  if (process.env.IT_BACKGROUND_REF) {
    return execFileSync("git", ["show", `${process.env.IT_BACKGROUND_REF}:extension/background.js`], {
      cwd: REPO,
      encoding: "utf8",
    });
  }
  return fs.readFileSync(BACKGROUND_FILE, "utf8");
}

const SETTINGS = {
  apiBaseUrl: "http://localhost:8000/v1",
  apiKey: "",
  model: "Index-Translate-2B",
  targetLang: "中文",
  temperature: 0.2,
  extraHeaders: "",
};

const flush = () => new Promise((r) => setTimeout(r, 1));

function okResponse(content) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ choices: [{ message: { content } }] }),
    text: async () => content,
  };
}

// 在受控的 chrome/fetch 环境里加载 background.js，返回脚本内可见的顶层函数与记录到的调用。
function loadBackground(opts = {}) {
  const store = opts.initialStore ? JSON.parse(JSON.stringify(opts.initialStore)) : {};
  const log = { updateDynamicRules: [], bodies: [], sets: 0, warnings: [] };
  const chrome = {
    runtime: {
      id: "test-extension-id",
      getURL: (p) => {
        if (opts.getURLThrows) throw new Error("no runtime");
        return (opts.origin || "chrome-extension://test-extension-id/") + p;
      },
      onMessage: { addListener: (fn) => (chrome.listener = fn) },
    },
    storage: {
      sync: { get: async (defaults) => ({ ...defaults, ...(opts.sync || {}) }) },
      local: {
        get: async (key) => (key in store ? { [key]: JSON.parse(JSON.stringify(store[key])) } : {}),
        set: async (obj) => {
          if (opts.setDelayMs) await new Promise((r) => setTimeout(r, opts.setDelayMs));
          log.sets += 1;
          if (opts.setFails) throw new Error("QUOTA_BYTES exceeded");
          Object.assign(store, JSON.parse(JSON.stringify(obj)));
        },
        remove: async () => {},
      },
    },
    declarativeNetRequest: {
      updateDynamicRules: async (arg) => {
        log.updateDynamicRules.push(JSON.parse(JSON.stringify(arg)));
        if (opts.dnrFirstCallFails && log.updateDynamicRules.length === 1) {
          throw new Error("invalid condition: initiatorDomains");
        }
      },
    },
  };
  const sandbox = {
    chrome,
    console: {
      log() {},
      warn: (...a) => log.warnings.push(a.join(" ")),
      error() {},
      info() {},
    },
    fetch: async (url, init) => {
      const body = JSON.parse(init.body);
      log.bodies.push(body);
      if (opts.fetchDelayMs) await new Promise((r) => setTimeout(r, opts.fetchDelayMs));
      const texts = JSON.parse(body.messages[1].content);
      return okResponse(JSON.stringify(texts.map((t) => `T:${t}`)));
    },
    URL,
    Promise,
    Object,
    Array,
    JSON,
    Date,
    Math,
    String,
    Number,
    Boolean,
    Error,
    Set,
    Map,
    setTimeout,
    clearTimeout,
  };
  const context = vm.createContext(sandbox);
  vm.runInContext(backgroundSource(), context, { filename: BACKGROUND_FILE });
  return { sandbox, store, log, chrome };
}

test("parseTranslations：标准数组 / 代码块包裹 / 长度补齐", () => {
  const { sandbox } = loadBackground();
  const parse = sandbox.parseTranslations;
  assert.deepEqual(Array.from(parse('["你好","世界"]', 2, false)), ["你好", "世界"]);
  assert.deepEqual(Array.from(parse('```json\n["你好","世界"]\n```', 2, false)), ["你好", "世界"]);
  assert.deepEqual(Array.from(parse('["只有一条"]', 3, false)), ["只有一条", "", ""]);
  assert.deepEqual(Array.from(parse('["a","b","c"]', 2, false)), ["a", "b"]);
});

test("parseTranslations：输出被截断时丢弃最后一项并救回前面", () => {
  const { sandbox } = loadBackground();
  assert.deepEqual(Array.from(sandbox.parseTranslations('["你好","世界","未闭合', 3, true)), [
    "你好",
    "世界",
    "",
  ]);
});

test("parseTranslations：裸字符串仅在末次尝试降级为纯文本", () => {
  const { sandbox } = loadBackground();
  // 非末次尝试：先重试，不给降级
  assert.throws(() => sandbox.parseTranslations('"你好"', 1, false), /不是数组/);
  // 末次尝试：裸字符串本身就是译文，直接放行
  assert.deepEqual(Array.from(sandbox.parseTranslations('"你好"', 1, true)), ["你好"]);
  // 单元素输入的裸字符串不应该变成带引号的 JSON 文本
  assert.equal(Array.from(sandbox.parseTranslations('"你好"', 1, true))[0], "你好");
});

test("parseTranslations：合法 JSON 对象（非数组）在末次尝试走纯文本降级", () => {
  const { sandbox } = loadBackground();
  assert.throws(() => sandbox.parseTranslations('{"text":"你好"}', 1, false), /不是数组/);
  const out = Array.from(sandbox.parseTranslations('{"text":"你好"}', 1, true));
  assert.equal(out.length, 1);
  assert.equal(typeof out[0], "string");
  assert.ok(out[0].includes("你好"), `降级结果应保留原文内容，实际：${out[0]}`);
});

test("requestTranslation：请求体带 chat_template_kwargs 关闭思维链，temperature 保持 0.2", async () => {
  const { sandbox, log } = loadBackground();
  const out = await sandbox.requestTranslation(["Hello"], SETTINGS, false);
  assert.deepEqual(Array.from(out), ["T:Hello"]);
  const body = log.bodies[0];
  assert.deepEqual(body.chat_template_kwargs, { enable_thinking: false });
  assert.equal(body.temperature, 0.2);
  assert.equal(body.model, "Index-Translate-2B");
  assert.equal(body.max_tokens, 4096);
});

test("saveCache 写失败时译文仍然返回（不因缓存报错丢结果）", async () => {
  const { sandbox, log } = loadBackground({ setFails: true });
  const out = await sandbox.translateWithCache(["Hello", "World"], SETTINGS);
  assert.deepEqual(Array.from(out), ["T:Hello", "T:World"]);
  assert.ok(log.sets >= 1, "应该尝试写过缓存");
  assert.ok(
    log.warnings.some((w) => w.includes("缓存")),
    `应记录缓存写失败警告，实际：${JSON.stringify(log.warnings)}`
  );
});

test("并发批次：缓存读-改-写串行化，不互相覆盖", async () => {
  const { sandbox, store } = loadBackground({ fetchDelayMs: 2, setDelayMs: 2 });
  const [a, b] = await Promise.all([
    sandbox.translateWithCache(["Hello"], SETTINGS),
    sandbox.translateWithCache(["World"], SETTINGS),
  ]);
  assert.deepEqual(Array.from(a), ["T:Hello"]);
  assert.deepEqual(Array.from(b), ["T:World"]);
  await flush();
  assert.equal(
    Object.keys(store[CACHE_KEY] || {}).length,
    2,
    "两个并发批次的译文都应写进缓存（旧实现会丢掉先写的那条）"
  );
});

test("DNR：主规则限定 initiatorDomains", async () => {
  const { log } = loadBackground();
  await flush();
  assert.equal(log.updateDynamicRules.length, 1);
  assert.deepEqual(log.updateDynamicRules[0].addRules[0].condition.initiatorDomains, [
    "test-extension-id",
  ]);
  assert.equal(
    log.updateDynamicRules[0].addRules[0].action.requestHeaders[0].operation,
    "remove"
  );
});

test("DNR：降级规则限定到扩展自身源（Firefox UUID），不再无条件摘 Origin", async () => {
  const { log } = loadBackground({
    dnrFirstCallFails: true,
    origin: "moz-extension://abc-uuid-1234/",
  });
  await flush();
  await flush();
  assert.equal(log.updateDynamicRules.length, 2, "降级路径应重试一次");
  const fallback = log.updateDynamicRules[1].addRules[0];
  assert.deepEqual(
    fallback.condition.initiatorDomains,
    ["abc-uuid-1234"],
    "降级规则必须限定到扩展自身 host"
  );
  for (const call of log.updateDynamicRules) {
    for (const rule of call.addRules) {
      assert.ok(
        Array.isArray(rule.condition.initiatorDomains) && rule.condition.initiatorDomains.length > 0,
        "任何规则都不能是无条件的（否则会摘掉全网请求的 Origin 头）"
      );
    }
  }
});

test("DNR：解析不出扩展自身源时不注册无条件规则", async () => {
  const { log } = loadBackground({ dnrFirstCallFails: true, getURLThrows: true });
  await flush();
  await flush();
  assert.equal(log.updateDynamicRules.length, 1, "不应再退化成无条件规则");
});
