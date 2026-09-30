// popup.js — 弹窗逻辑：向当前标签页的 content script 发指令

const translateBtn = document.getElementById("translateBtn");
const restoreBtn = document.getElementById("restoreBtn");
const statusEl = document.getElementById("status");
const progressWrap = document.getElementById("progressWrap");
const progressBar = document.getElementById("progressBar");
const progressText = document.getElementById("progressText");
const displayModeEl = document.getElementById("displayMode");
const workModeEl = document.getElementById("workMode");
const pageSection = document.getElementById("pageSection");
const selectionHint = document.getElementById("selectionHint");
const autoTranslateRow = document.getElementById("autoTranslateRow");
const autoTranslateEl = document.getElementById("autoTranslate");

// 翻译方式：整页 / 划词。划词模式下隐藏整页翻译的按钮区
function applyWorkMode(mode) {
  const isSelection = mode === "selection";
  pageSection.style.display = isSelection ? "none" : "block";
  selectionHint.style.display = isSelection ? "block" : "none";
  autoTranslateRow.style.display = isSelection ? "flex" : "none";
}
chrome.storage.sync.get({ workMode: "page", autoTranslate: false }).then(({ workMode, autoTranslate }) => {
  workModeEl.value = workMode;
  autoTranslateEl.checked = autoTranslate;
  applyWorkMode(workMode);
});
workModeEl.addEventListener("change", () => {
  chrome.storage.sync.set({ workMode: workModeEl.value });
  applyWorkMode(workModeEl.value);
  setStatus("");
});
autoTranslateEl.addEventListener("change", () => {
  chrome.storage.sync.set({ autoTranslate: autoTranslateEl.checked });
});

// 显示模式：读取已保存的选择，变更时立即保存。
// 「悬停显示原文」勾选项仅在替换模式下展示
const hoverOriginalRow = document.getElementById("hoverOriginalRow");
const hoverOriginalEl = document.getElementById("hoverOriginal");

function applyDisplayMode(mode) {
  hoverOriginalRow.style.display = mode === "replace" ? "flex" : "none";
}
chrome.storage.sync.get({ displayMode: "bilingual", hoverOriginal: true }).then(({ displayMode, hoverOriginal }) => {
  displayModeEl.value = displayMode;
  hoverOriginalEl.checked = hoverOriginal;
  applyDisplayMode(displayMode);
});
displayModeEl.addEventListener("change", () => {
  chrome.storage.sync.set({ displayMode: displayModeEl.value });
  applyDisplayMode(displayModeEl.value);
});
hoverOriginalEl.addEventListener("change", () => {
  chrome.storage.sync.set({ hoverOriginal: hoverOriginalEl.checked });
});

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.className = isError ? "error" : "";
}

function showProgress(done, total) {
  progressWrap.style.display = "block";
  progressBar.max = total;
  progressBar.value = done;
  progressText.textContent = `${done} / ${total} 段`;
}

function hideProgress() {
  progressWrap.style.display = "none";
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function sendToTab(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (resp) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, error: chrome.runtime.lastError.message });
      } else {
        resolve(resp || { ok: false, error: "无响应" });
      }
    });
  });
}

// 监听 content script 上报的进度
chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "PROGRESS") {
    showProgress(message.done, message.total);
    setStatus("翻译中…");
  }
});

let translatingTabId = null; // 非 null 表示翻译进行中，此时按钮充当"停止"
let stopped = false; // 上次翻译被中途停止，按钮显示"继续翻译"

function setTranslatingUI(on) {
  if (on) {
    translateBtn.textContent = "停止翻译";
  } else {
    translateBtn.textContent = stopped ? "继续翻译" : "翻译当前页面";
  }
  translateBtn.classList.toggle("stop", on);
}

translateBtn.addEventListener("click", async () => {
  // 翻译进行中：按钮作为"停止"使用
  if (translatingTabId !== null) {
    const tabId = translatingTabId;
    await sendToTab(tabId, { type: "CANCEL_TRANSLATE" });
    translateBtn.disabled = true; // 等在途批次结束
    setStatus("正在停止…（等待已发出的请求完成）");
    // 弹窗可能是翻译中途重新打开的，收不到 TRANSLATE_PAGE 的返回值，
    // 轮询页面状态直到翻译结束，再恢复 UI
    const timer = setInterval(async () => {
      const st = await sendToTab(tabId, { type: "GET_STATUS" });
      if (!st.ok || !st.translating) {
        clearInterval(timer);
        translatingTabId = null;
        stopped = true;
        setTranslatingUI(false);
        translateBtn.disabled = false;
        hideProgress();
        if (st.ok) setStatus(`已停止：翻译了 ${st.translatedCount} 个段落`);
      }
    }, 300);
    return;
  }

  const tab = await getActiveTab();
  if (!tab?.id || !/^https?:/.test(tab.url || "")) {
    setStatus("当前页面不支持翻译（仅支持 http/https 页面）", true);
    return;
  }

  translatingTabId = tab.id;
  setTranslatingUI(true);
  setStatus("翻译中…");
  showProgress(0, 1);

  const resp = await sendToTab(tab.id, { type: "TRANSLATE_PAGE" });
  translatingTabId = null;
  stopped = !!resp.cancelled;
  setTranslatingUI(false);
  translateBtn.disabled = false;
  hideProgress();

  if (resp.ok) {
    let msg = resp.cancelled
      ? `已停止：翻译了 ${resp.translated}/${resp.total} 个段落`
      : `完成：翻译了 ${resp.translated}/${resp.total} 个段落`;
    if (!resp.cancelled && resp.translated < resp.total) {
      msg += "\n部分段落未成功，可再次点击补翻";
    }
    if (resp.warning) msg += `\n部分批次出错: ${resp.warning}`;
    setStatus(msg, !!resp.warning);
  } else {
    let hint = resp.error || "未知错误";
    if (/Receiving end does not exist/i.test(hint)) {
      hint = "内容脚本未加载，请刷新页面后重试";
    }
    setStatus("失败: " + hint, true);
  }
});

// 打开弹窗时查询页面翻译状态：翻译进行中则恢复"停止翻译"按钮；
// 页面已有部分译文（上次中途停止）则显示"继续翻译"
(async () => {
  const tab = await getActiveTab();
  if (!tab?.id) return;
  const resp = await sendToTab(tab.id, { type: "GET_STATUS" });
  if (!resp.ok) return;
  if (resp.translating) {
    translatingTabId = tab.id;
    setTranslatingUI(true);
    setStatus("翻译中…");
  } else if (resp.translatedCount > 0) {
    stopped = true;
    setTranslatingUI(false);
  }
})();

restoreBtn.addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab?.id) return;
  await sendToTab(tab.id, { type: "RESTORE_PAGE" });
  stopped = false;
  setTranslatingUI(false);
  setStatus("已还原");
});

document.getElementById("openOptions").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});
