// options.js — 设置页逻辑：读写 chrome.storage.sync，测试 API 连通性

const fields = ["apiBaseUrl", "apiKey", "model", "targetLang", "extraHeaders"];
const statusEl = document.getElementById("status");

const DEFAULTS = {
  apiBaseUrl: "http://localhost:8000/v1",
  apiKey: "",
  model: "Index-Translate-2B",
  targetLang: "中文",
  extraHeaders: "",
};

function setStatus(text, cls = "") {
  statusEl.textContent = text;
  statusEl.className = cls;
}

async function loadSettings() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  for (const key of fields) {
    document.getElementById(key).value = stored[key] ?? DEFAULTS[key];
  }
}

async function saveSettings() {
  const settings = {};
  for (const key of fields) {
    settings[key] = document.getElementById(key).value.trim();
  }
  await chrome.storage.sync.set(settings);
  return settings;
}

document.getElementById("saveBtn").addEventListener("click", async () => {
  await saveSettings();
  setStatus("已保存 ✓", "ok");
});

document.getElementById("testBtn").addEventListener("click", async () => {
  await saveSettings();
  setStatus("测试中，正在翻译 \"Hello, world!\" …");
  chrome.runtime.sendMessage({ type: "TEST_CONNECTION" }, (resp) => {
    if (chrome.runtime.lastError) {
      setStatus("测试失败: " + chrome.runtime.lastError.message, "error");
    } else if (resp?.ok) {
      setStatus(`连接成功 ✓  示例译文: ${resp.sample}`, "ok");
    } else {
      setStatus("测试失败: " + (resp?.error || "未知错误"), "error");
    }
  });
});

document.getElementById("clearCacheBtn").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "CLEAR_CACHE" }, (resp) => {
    if (resp?.ok) {
      setStatus("翻译缓存已清除 ✓", "ok");
    } else {
      setStatus("清除缓存失败", "error");
    }
  });
});

// 预设按钮
document.querySelectorAll(".presets button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.getElementById("apiBaseUrl").value = btn.dataset.url;
    if (btn.dataset.model) {
      document.getElementById("model").value = btn.dataset.model;
    }
    document.getElementById("extraHeaders").value = btn.dataset.headers || "";
  });
});

loadSettings();
