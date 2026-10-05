// content.js 的 node 级单测（零依赖，用 node:vm + 最小 DOM/chrome stub 加载脚本）。
// 覆盖：TRANSLATE_PAGE 抛错时必须 sendResponse（否则 popup 永远等不到响应）；
//       进度上报失败（popup 已关闭 / sendMessage 同步抛错）不得中断翻译。
//
// 运行（绿）：node extension/tests/content.test.mjs
// 红/绿对照：IT_CONTENT_REF=9cc5ee7 node extension/tests/content.test.mjs
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(here, "..", "..");
const CONTENT_FILE = path.join(here, "..", "content", "content.js");

// 支持指定 ref 加载"修前"版本做红/绿对照（如 IT_CONTENT_REF=9cc5ee7）。
function contentSource() {
  if (process.env.IT_CONTENT_SRC) return fs.readFileSync(process.env.IT_CONTENT_SRC, "utf8");
  if (process.env.IT_CONTENT_REF) {
    return execFileSync("git", ["show", `${process.env.IT_CONTENT_REF}:extension/content/content.js`], {
      cwd: REPO,
      encoding: "utf8",
    });
  }
  return fs.readFileSync(CONTENT_FILE, "utf8");
}

function makeElement(text = "") {
  return {
    tagName: "P",
    isContentEditable: false,
    firstChild: null,
    textContent: text,
    dataset: {},
    classList: { contains: () => false, add() {}, remove() {} },
    querySelector: () => null,
    querySelectorAll: () => [],
    insertAdjacentElement() {},
    appendChild() {},
    remove() {},
    cloneNode: () => ({
      innerText: text,
      querySelector: () => null,
      querySelectorAll: () => [],
      getAttribute: () => null,
      replaceWith() {},
    }),
  };
}

async function waitFor(predicate, timeoutMs = 1000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return true;
    await new Promise((r) => setTimeout(r, 5));
  }
  return predicate();
}

// 加载 content.js：createTreeWalker 决定 collectBlocks 的行为，
// sendMessage 决定进度上报是否失败。
function loadContent(opts = {}) {
  const calls = { progress: 0, batches: [] };
  let listener = null;
  const win = {
    addEventListener() {},
    getSelection: () => null,
    getComputedStyle: () => ({ display: "block", visibility: "visible" }),
  };
  const documentStub = {
    addEventListener() {},
    createElement: () => makeElement(),
    createTextNode: () => ({}),
    querySelectorAll: () => [],
    body: {},
    createTreeWalker:
      opts.createTreeWalker ||
      (() => {
        throw new Error("DOM boom");
      }),
  };
  const chrome = {
    storage: {
      sync: { get: async (defaults) => ({ ...defaults, ...(opts.sync || {}) }) },
      onChanged: { addListener() {} },
    },
    runtime: {
      lastError: null,
      onMessage: { addListener: (fn) => { listener = fn; } },
      // 注意：进度上报刻意"同步抛错"（模拟扩展上下文失效 / 部分实现返回 undefined），
      // 这正是原来 `.catch?.()` 挡不住的情况。
      sendMessage: (message, cb) => {
        if (message.type === "PROGRESS") {
          calls.progress += 1;
          throw new Error("Extension context invalidated");
        }
        calls.batches.push(message.texts);
        if (cb) cb({ ok: true, translations: message.texts.map((t) => `T:${t}`) });
        return undefined;
      },
    },
  };
  const sandbox = {
    window: win,
    document: documentStub,
    chrome,
    console: { log() {}, warn() {}, error() {}, info() {} },
    NodeFilter: { SHOW_ELEMENT: 1, FILTER_ACCEPT: 1, FILTER_REJECT: 2, FILTER_SKIP: 3 },
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
  vm.createContext(sandbox);
  vm.runInContext(contentSource(), sandbox, { filename: CONTENT_FILE });
  return { listener, calls, sandbox };
}

test("TRANSLATE_PAGE：translatePage 抛错时也必须回包错误", async () => {
  const { listener } = loadContent();
  assert.equal(typeof listener, "function", "content.js 应该注册 onMessage 监听");
  let resp;
  const asyncReply = listener({ type: "TRANSLATE_PAGE" }, {}, (r) => { resp = r; });
  assert.equal(asyncReply, true, "异步回包必须返回 true");
  assert.ok(await waitFor(() => resp !== undefined), "sendResponse 从未被调用（popup 会一直转圈）");
  assert.equal(resp.ok, false);
  assert.match(String(resp.error), /DOM boom/);
});

test("TRANSLATE_PAGE：抛错后 translating 复位，可以再次发起", async () => {
  const { listener } = loadContent();
  let first;
  listener({ type: "TRANSLATE_PAGE" }, {}, (r) => { first = r; });
  await waitFor(() => first !== undefined);
  let second;
  listener({ type: "TRANSLATE_PAGE" }, {}, (r) => { second = r; });
  await waitFor(() => second !== undefined);
  assert.notEqual(second.error, "正在翻译中");
});

test("TRANSLATE_PAGE：进度上报同步抛错不中断翻译，结果照常返回", async () => {
  const { listener, calls } = loadContent({
    sync: { workMode: "page", autoTranslate: false, hoverOriginal: true, displayMode: "bilingual" },
    createTreeWalker: () => {
      const el = makeElement("Hello world");
      let yielded = false;
      return {
        nextNode: () => {
          if (yielded) return null;
          yielded = true;
          return el;
        },
      };
    },
  });
  let resp;
  listener({ type: "TRANSLATE_PAGE" }, {}, (r) => { resp = r; });
  assert.ok(await waitFor(() => resp !== undefined), "进度上报抛错后 sendResponse 没有被调用");
  assert.equal(resp.ok, true);
  assert.equal(resp.translated, 1);
  assert.equal(calls.progress, 1, "应该尝试上报过一次进度");
  // 注意：vm 跨 realm 的数组原型不同，用 deepStrictEqual 比较需先转成本 realm 数组
  assert.equal(calls.batches.length, 1);
  assert.deepEqual(Array.from(calls.batches[0]), ["Hello world"]);
});
