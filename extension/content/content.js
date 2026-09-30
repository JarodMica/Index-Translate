// content.js — 内容脚本，注入到每个网页
// 职责：提取页面可翻译的文本节点，分批发给 background 翻译，把译文插回页面。
// 支持两种显示模式：双语对照（译文插在原文下方）、替换原文（可选悬停显示原文）。

(() => {
  // 防止重复注入
  if (window.__llmTranslatorInjected) return;
  window.__llmTranslatorInjected = true;

  const BATCH_SIZE = 4; // 每批翻译的段落数（小模型易格式错乱，调小批次）
  const MAX_CONCURRENT = 3; // 同时进行的批次请求数
  const MIN_TEXT_LENGTH = 2; // 忽略过短的文本
  const SKIP_TAGS = new Set([
    "SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "SELECT",
    "CODE", "PRE", "KBD", "SVG", "CANVAS", "IFRAME",
  ]);
  // 视为"块级翻译单元"的标签：整块文本一起翻译，语义更完整
  const BLOCK_TAGS = new Set([
    "P", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "TD", "TH",
    "BLOCKQUOTE", "FIGCAPTION", "DT", "DD", "SUMMARY",
  ]);

  let translating = false;
  let cancelRequested = false; // 用户点击"停止翻译"后置位，worker 不再领取新批次
  let translatedNodes = []; // 记录每个已翻译块的信息（含显示模式），用于"还原"

  // ---------- 占位符系统 ----------
  // 提取文本时，将 LaTeX 公式、行内代码等替换为占位符（如 %%MATH_0%%），
  // 防止 LLM 翻译/改动它们。翻译完成后再还原回原始内容。

  // 检测各类数学公式的 CSS 选择器（兼容 MathJax / KaTeX / 知乎等）
  const MATH_SELECTORS = [
    'script[type^="math/tex"]',                    // MathJax 原始 LaTeX（知乎等）
    'annotation[encoding="application/x-tex"]',    // MathML 中的 LaTeX 注释（KaTeX）
    '.MathJax',                                    // MathJax 渲染结果
    '.katex',                                      // KaTeX 渲染结果
    '[class*="ztext-math"]',                       // 知乎特定
    '[data-tex]',                                  // 带 data-tex 属性的元素
  ].join(", ");

  function extractWithPlaceholders(element) {
    const placeholders = {};
    let counter = 0;
    const clone = element.cloneNode(true);

    // 替换数学公式为占位符
    clone.querySelectorAll(MATH_SELECTORS).forEach((el) => {
      // 优先取 <annotation> 或 <script> 中的 LaTeX 源码，避免把渲染后的乱码存进去
      const annotation = el.querySelector?.('annotation[encoding="application/x-tex"]');
      const scriptTex = el.tagName === "SCRIPT" ? el.textContent : null;
      const dataTex = el.getAttribute?.("data-tex");
      const tex = annotation?.textContent || scriptTex || dataTex || el.textContent;

      if (!tex || !tex.trim()) return;
      const key = `%%MATH_${counter++}%%`;
      placeholders[key] = tex.trim();
      el.replaceWith(document.createTextNode(key));
    });

    // 替换行内代码为占位符
    clone.querySelectorAll("code, kbd").forEach((el) => {
      const key = `%%CODE_${counter++}%%`;
      placeholders[key] = el.textContent;
      el.replaceWith(document.createTextNode(key));
    });

    const text = clone.innerText?.trim() || "";
    return { text, placeholders };
  }

  function restorePlaceholders(text, placeholders) {
    let result = text;
    for (const [key, original] of Object.entries(placeholders)) {
      result = result.replaceAll(key, original);
    }
    return result;
  }

  // ---------- 文本提取 ----------

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden";
  }

  function shouldSkip(el) {
    if (SKIP_TAGS.has(el.tagName)) return true;
    if (el.classList.contains("llm-translation")) return true; // 我们自己插入的译文
    if (el.isContentEditable) return true;
    return false;
  }

  // 收集块级翻译单元。返回 [{ element, text }]
  function collectBlocks() {
    const blocks = [];
    const seen = new Set();

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, {
      acceptNode(el) {
        if (shouldSkip(el)) return NodeFilter.FILTER_REJECT;
        if (BLOCK_TAGS.has(el.tagName)) return NodeFilter.FILTER_ACCEPT;
        return NodeFilter.FILTER_SKIP;
      },
    });

    let el;
    while ((el = walker.nextNode())) {
      // 嵌套的块级元素（如 li > p）只取最内层，避免重复翻译
      if (el.querySelector(Array.from(BLOCK_TAGS).join(","))) continue;
      if (seen.has(el)) continue;
      if (!isVisible(el)) continue;
      if (el.dataset.llmTranslated === "1") continue;

      const { text, placeholders } = extractWithPlaceholders(el);
      if (!text || text.length < MIN_TEXT_LENGTH) continue;
      // 纯数字/符号跳过
      if (/^[\d\s\p{P}]+$/u.test(text)) continue;

      seen.add(el);
      blocks.push({ element: el, text, placeholders });
    }
    return blocks;
  }

  // ---------- 译文插入 ----------

  // mode: "bilingual" 双语对照（默认） | "replace" 替换原文（可选悬停显示原文）
  // 返回是否算作"已处理"：空译文返回 false（留待重试/续翻），
  // 译文与原文相同返回 true 并打标记（该段无需翻译，避免下次重复送翻）。
  function insertTranslation(block, translation, mode) {
    if (!translation || translation.trim() === "") return false;
    if (translation.trim() === block.text) {
      block.element.dataset.llmTranslated = "1";
      translatedNodes.push({ mode: "skip", element: block.element });
      return true;
    }

    // 还原占位符：把 %%MATH_0%% 等替换回原始 LaTeX / 代码
    translation = restorePlaceholders(translation, block.placeholders);
    const element = block.element;

    if (mode === "replace") {
      // 把原文的子节点整体移入隐藏的 span（不销毁 DOM，保住链接和事件），
      // 译文 span 放在原位置显示；hover 时通过 CSS 显示原文。
      const originalWrap = document.createElement("span");
      originalWrap.className = "llm-original";
      while (element.firstChild) originalWrap.appendChild(element.firstChild);

      const transWrap = document.createElement("span");
      transWrap.className = "llm-translation-text";
      transWrap.textContent = translation;

      element.appendChild(transWrap);
      element.appendChild(originalWrap);
      element.dataset.llmTranslated = "1";
      element.dataset.llmMode = "replace";
      translatedNodes.push({ mode, element, transWrap, originalWrap });
    } else {
      const wrapper = document.createElement("div");
      wrapper.className = "llm-translation";
      wrapper.textContent = translation;

      element.dataset.llmTranslated = "1";
      element.insertAdjacentElement("afterend", wrapper);
      translatedNodes.push({ mode, element, translationEl: wrapper });
    }
    return true;
  }

  function restorePage() {
    clearHoverState();
    for (const rec of translatedNodes) {
      if (rec.mode === "replace") {
        // 移除译文，把原文子节点从隐藏 span 移回原元素
        rec.transWrap.remove();
        while (rec.originalWrap.firstChild) {
          rec.element.appendChild(rec.originalWrap.firstChild);
        }
        rec.originalWrap.remove();
        rec.element.classList.remove("llm-show-original");
      } else if (rec.mode !== "skip") {
        rec.translationEl.remove();
      }
      delete rec.element.dataset.llmTranslated;
      delete rec.element.dataset.llmMode;
    }
    translatedNodes = [];
  }

  // ---------- 替换模式：悬停延迟显示原文 ----------
  // 悬停 HOVER_DELAY_MS 后才切回原文，避免鼠标扫过时页面闪动。
  // 受「悬停显示原文」开关控制，关闭后不再响应悬停。

  const HOVER_DELAY_MS = 1000;
  let hoverTimer = null;
  let hoverEl = null;
  let hoverOriginalEnabled = true;

  function clearHoverState() {
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = null;
    hoverEl?.classList.remove("llm-show-original");
    hoverEl = null;
  }

  document.addEventListener("mouseover", (event) => {
    if (!hoverOriginalEnabled) return;
    const el = event.target.closest?.('[data-llm-mode="replace"]');
    if (el === hoverEl) return; // 仍在同一段落内移动（进入子节点也会触发 mouseover）
    clearHoverState();
    if (el) {
      hoverEl = el;
      hoverTimer = setTimeout(() => el.classList.add("llm-show-original"), HOVER_DELAY_MS);
    }
  });

  // ---------- 翻译流程 ----------

  function sendBatch(texts) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "TRANSLATE_BATCH", texts }, (resp) => {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
        } else {
          resolve(resp || { ok: false, error: "无响应" });
        }
      });
    });
  }

  async function translatePage(onProgress) {
    if (translating) return { ok: false, error: "正在翻译中" };
    translating = true;
    cancelRequested = false;

    try {
      const blocks = collectBlocks();
      if (blocks.length === 0) {
        return { ok: false, error: translatedNodes.length > 0 ? "全部段落已翻译完成" : "没有找到可翻译的内容" };
      }

      // 统计口径为整个页面：续翻时把之前已处理的段落也计入，避免出现 "40/15" 这种混乱显示
      const alreadyDone = translatedNodes.length;
      const pageTotal = alreadyDone + blocks.length;

      // 读取显示模式设置（bilingual 双语对照 / replace 替换原文）
      const { displayMode } = await chrome.storage.sync.get({ displayMode: "bilingual" });

      let done = 0;
      let firstError = null;

      // 切分批次
      const batches = [];
      for (let i = 0; i < blocks.length; i += BATCH_SIZE) {
        batches.push(blocks.slice(i, i + BATCH_SIZE));
      }

      // worker pool：MAX_CONCURRENT 个 worker 从队列领取批次，先完成的先插入译文
      let nextBatch = 0;
      async function worker() {
        while (nextBatch < batches.length && !cancelRequested) {
          const batch = batches[nextBatch++];
          const resp = await sendBatch(batch.map((b) => b.text));

          // 在途请求返回后仍然插入译文（API 已消耗，不浪费）
          if (resp.ok) {
            batch.forEach((block, j) => insertTranslation(block, resp.translations[j], displayMode));
          } else if (!firstError) {
            firstError = resp.error;
          }

          done += batch.length;
          onProgress?.(alreadyDone + done, pageTotal);
        }
      }

      await Promise.all(
        Array.from({ length: Math.min(MAX_CONCURRENT, batches.length) }, worker)
      );

      if (cancelRequested) {
        return { ok: true, total: pageTotal, translated: translatedNodes.length, cancelled: true };
      }
      if (translatedNodes.length === 0 && firstError) {
        return { ok: false, error: firstError };
      }
      return { ok: true, total: pageTotal, translated: translatedNodes.length, warning: firstError };
    } finally {
      translating = false;
    }
  }

  // ---------- 划词翻译 ----------
  // 划选文本松开鼠标后，在选区旁弹出"译"按钮；点击按钮翻译选中文本，气泡显示结果。
  // 按钮只在 mouseup 后出现，不需要防抖延迟；误触仅是按钮闪现，不会发起请求。
  // 仅在弹窗选择"划词翻译"方式时生效。
  // autoTranslate 开启时，停止划词 1 秒后直接翻译并显示结果（不再弹按钮）。

  let workMode = "page";
  let autoTranslate = false;
  chrome.storage.sync.get({ workMode: "page", autoTranslate: false, hoverOriginal: true }).then((v) => {
    workMode = v.workMode;
    autoTranslate = v.autoTranslate;
    hoverOriginalEnabled = v.hoverOriginal;
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync") return;
    if (changes.workMode) {
      workMode = changes.workMode.newValue;
      if (workMode !== "selection") hideSelectionUI();
    }
    if (changes.autoTranslate) {
      autoTranslate = changes.autoTranslate.newValue;
    }
    if (changes.hoverOriginal) {
      hoverOriginalEnabled = changes.hoverOriginal.newValue;
      if (!hoverOriginalEnabled) clearHoverState(); // 正在显示原文的段落立即切回译文
    }
  });

  function selectionActive() {
    return workMode === "selection";
  }

  let triggerEl = null;
  let bubbleEl = null;
  let pendingSelection = null; // { text, rect }

  function ensureSelectionUI() {
    if (triggerEl) return;
    triggerEl = document.createElement("div");
    triggerEl.className = "llm-select-trigger";
    triggerEl.textContent = "译";
    // mousedown 阻止默认行为，避免点击按钮时浏览器清除当前选区
    triggerEl.addEventListener("mousedown", (e) => e.preventDefault());
    triggerEl.addEventListener("click", onTriggerClick);

    bubbleEl = document.createElement("div");
    bubbleEl.className = "llm-select-bubble";

    document.body.append(triggerEl, bubbleEl);
  }

  function hideSelectionUI() {
    if (triggerEl) triggerEl.style.display = "none";
    if (bubbleEl) bubbleEl.style.display = "none";
  }

  function placeTrigger(rect) {
    triggerEl.style.display = "block";
    const size = 26;
    const left = Math.min(rect.right + 6, window.innerWidth - size - 8);
    const top = Math.min(rect.bottom + 6, window.innerHeight - size - 8);
    triggerEl.style.left = `${Math.max(8, left)}px`;
    triggerEl.style.top = `${Math.max(8, top)}px`;
  }

  function showBubble(rect, text, isError = false) {
    bubbleEl.textContent = text;
    bubbleEl.className = "llm-select-bubble" + (isError ? " error" : "");
    bubbleEl.style.display = "block";
    // 先显示再测量，保证气泡不超出视口
    const bw = bubbleEl.offsetWidth;
    const bh = bubbleEl.offsetHeight;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - bw - 8));
    const top = rect.bottom + 8 + bh > window.innerHeight
      ? Math.max(8, rect.top - bh - 8) // 下方放不下就放上方
      : rect.bottom + 8;
    bubbleEl.style.left = `${left}px`;
    bubbleEl.style.top = `${top}px`;
  }

  async function translateSelection(text, rect) {
    showBubble(rect, "翻译中…");
    const resp = await sendBatch([text]);
    if (bubbleEl.style.display === "none") return; // 用户已关闭气泡，丢弃结果
    if (resp.ok) {
      showBubble(rect, resp.translations[0]?.trim() || "（空结果）");
    } else {
      showBubble(rect, "翻译失败: " + (resp.error || "未知错误"), true);
    }
  }

  async function onTriggerClick() {
    if (!pendingSelection) return;
    const { text, rect } = pendingSelection;
    triggerEl.style.display = "none";
    await translateSelection(text, rect);
  }

  // 自动翻译：停止划词 AUTO_DELAY_MS 后直接翻译，无需点击按钮
  const AUTO_DELAY_MS = 1000;
  let autoTimer = null;
  function clearAutoTimer() {
    if (autoTimer) clearTimeout(autoTimer);
    autoTimer = null;
  }

  document.addEventListener("mouseup", (event) => {
    if (!selectionActive()) return;
    if (event.target.closest?.(".llm-select-trigger, .llm-select-bubble")) return;
    // 双击选词时选区在 mouseup 之后才更新，推迟到下一轮事件循环再读取
    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel?.toString().trim() || "";
      if (!text || sel.isCollapsed || text.length > 2000) {
        clearAutoTimer();
        hideSelectionUI();
        return;
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      pendingSelection = { text, rect };

      if (autoTranslate) {
        // 自动模式：延迟后直接翻译，不再弹按钮
        ensureSelectionUI();
        clearAutoTimer();
        triggerEl.style.display = "none";
        autoTimer = setTimeout(() => translateSelection(text, rect), AUTO_DELAY_MS);
      } else {
        ensureSelectionUI();
        bubbleEl.style.display = "none";
        placeTrigger(rect);
      }
    }, 0);
  });

  document.addEventListener("mousedown", (event) => {
    if (event.target.closest?.(".llm-select-trigger, .llm-select-bubble")) return;
    clearAutoTimer();
    hideSelectionUI();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      clearAutoTimer();
      hideSelectionUI();
    }
  });

  // 按钮/气泡是 fixed 定位，页面滚动后位置会脱离选区，直接隐藏。
  // 注意：气泡内部滚动（overflow:auto）在捕获阶段也会经过 window，需排除，
  // 否则用户在气泡内滚轮翻页时气泡会误关。
  window.addEventListener("scroll", (event) => {
    if (event.target === bubbleEl || bubbleEl?.contains(event.target)) return;
    clearAutoTimer();
    hideSelectionUI();
  }, true);

  // ---------- 消息处理（来自 popup） ----------

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "TRANSLATE_PAGE") {
      translatePage((done, total) => {
        chrome.runtime.sendMessage({ type: "PROGRESS", done, total }).catch?.(() => {});
      }).then(sendResponse);
      return true;
    }
    if (message.type === "RESTORE_PAGE") {
      restorePage();
      sendResponse({ ok: true });
      return false;
    }
    if (message.type === "CANCEL_TRANSLATE") {
      cancelRequested = true;
      sendResponse({ ok: true });
      return false;
    }
    if (message.type === "GET_STATUS") {
      sendResponse({ ok: true, translating, translatedCount: translatedNodes.length });
      return false;
    }
  });
})();
