# LLM Page Translator (index-page-mt)

English | [中文](README_zh.md)

A browser extension (Chrome / Edge / Firefox, Manifest V3) that translates web pages with a **locally deployed LLM**, purpose-built for the **[Index-Translate](https://huggingface.co/collections/IndexTeam/index-translate) model family**. It works with any local inference framework exposing an OpenAI-compatible API (vLLM / SGLang, etc.).

Pure vanilla JS — **no build step required**; the directory is the extension.

## Why Index-Translate

[Index-Translate-2B / 9B](https://huggingface.co/collections/IndexTeam/index-translate) are models trained specifically for translation. Compared with general-purpose models of similar size:

- Higher translation quality, covering 100+ language directions;
- Small and fast — the 2B model runs smoothly on a consumer GPU;
- Fully local — page content never leaves your machine/intranet, no privacy or compliance concerns;
- No API key, no pay-per-token, works offline.

Model weights (either source):

- Hugging Face: [`IndexTeam/Index-Translate-2B`](https://huggingface.co/IndexTeam/Index-Translate-2B) · [`IndexTeam/Index-Translate-9B`](https://huggingface.co/IndexTeam/Index-Translate-9B)
- ModelScope: [IndexTeam organization](https://modelscope.cn/organization/IndexTeam) (same repository names)

## Project layout

```
index-page-mt/
├── manifest.json            # Extension manifest (Chrome / Edge, MV3)
├── manifest.firefox.json    # Extension manifest (Firefox)
├── background.js            # Service worker: calls the LLM API (bypasses page CORS)
├── content/
│   ├── content.js           # Content script: extracts paragraphs, inserts bilingual translations
│   └── content.css          # Translation block styles
├── popup/
│   ├── popup.html           # Toolbar popup: translate / restore / selection mode
│   └── popup.js
├── options/
│   ├── options.html         # Settings page: API URL / model / target language
│   └── options.js
└── scripts/
    └── build.sh             # Packages Chrome / Firefox bundles
```

---

## Step 1: Deploy the model locally

### Option A: vLLM (recommended)

Install (requires an NVIDIA GPU with CUDA; see the [vLLM docs](https://docs.vllm.ai/)):

```bash
pip install vllm
```

Start the OpenAI-compatible server:

```bash
# 2B model (~8GB VRAM)
vllm serve IndexTeam/Index-Translate-2B \
    --served-model-name Index-Translate-2B \
    --port 8000

# 9B model (~24GB VRAM)
vllm serve IndexTeam/Index-Translate-9B \
    --served-model-name Index-Translate-9B \
    --port 8000
```

- `--served-model-name` sets the exposed model name — **the "Model name" field in the extension settings must match this value exactly**;
- The first run downloads weights from Hugging Face automatically; if HF is unreachable, download from ModelScope and pass a local path instead, or set `HF_ENDPOINT=https://hf-mirror.com`;
- To serve other machines on your LAN, add `--host 0.0.0.0` and point the extension at `http://<server-ip>:8000/v1`.

### Option B: SGLang

```bash
pip install "sglang[all]"

# 2B model
python -m sglang.launch_server \
    --model-path IndexTeam/Index-Translate-2B \
    --served-model-name Index-Translate-2B \
    --port 30000

# 9B model
python -m sglang.launch_server \
    --model-path IndexTeam/Index-Translate-9B \
    --served-model-name Index-Translate-9B \
    --port 30000
```

SGLang defaults to port 30000; everything else is the same as vLLM.

### Verify the server

```bash
curl http://localhost:8000/v1/models        # confirm data[0].id matches the model name in the extension

curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Index-Translate-2B","messages":[{"role":"user","content":"Hello"}]}'
```

## Step 2: Install the extension

1. Download this directory (`git clone` or ZIP);
2. Open Chrome / Edge and go to `chrome://extensions/`;
3. Enable **Developer mode** (top right);
4. Click **Load unpacked** and select this directory;
5. (Firefox) Go to `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on**, and pick `manifest.firefox.json`.

## Step 3: Configure the extension

Click the extension icon → **⚙ Settings**:

| Setting | Value |
|---------|-------|
| API URL | vLLM: `http://localhost:8000/v1`; SGLang: `http://localhost:30000/v1` |
| API Key | Leave empty for local deployment |
| Model name | `Index-Translate-2B` or `Index-Translate-9B` (must match `--served-model-name`) |
| Target language | Chinese / English / Japanese / Korean |

The settings page provides **four quick-fill buttons (vLLM / SGLang × 2B / 9B)** that fill in the URL and model name for you. Click **Test connection** — seeing a sample translation means everything is set up.

## Usage

1. Open any foreign-language page (e.g. https://en.wikipedia.org/wiki/Machine_learning );
2. Click the extension icon → **Translate this page**;
3. Translations appear below each original paragraph with a blue left border (bilingual mode); you can also switch to **replace original** mode (with optional hover-to-show-original) or **selection translation**;
4. Click **Restore page** to remove all translations. Results are cached for 7 days, so revisiting a page costs no extra requests.

> After modifying the code, go back to `chrome://extensions/`, click the reload button on the extension card, and refresh the test page.

## How it works

1. **content.js** walks the DOM and collects text from block-level elements (`<p>`, `<h1>`–`<h6>`, `<li>`, `<td>`, etc.), skipping code blocks, invisible elements, and overly short text;
2. Batches of **4 paragraphs** are sent to **background.js**, with up to **3 batches in flight** at the same time;
3. The background worker calls the local model's `/chat/completions` endpoint with a JSON array of source texts and asks for an equal-length array of translations (with tolerant parsing for markdown fences, truncated output, etc., and automatic retries on format errors);
4. Translations are inserted below the original paragraphs with a `data-llm-translated` marker to prevent duplicate translation, and can be removed in one click.

## FAQ

- **403 / CORS errors**: the extension already strips the `Origin` header at the network layer; if it still fails, make sure the server was started with `--host 0.0.0.0` and the port is reachable.
- **"Model not found"**: the model name must exactly match `--served-model-name`; check with `curl <base>/v1/models`.
- **Garbled format / missing paragraphs**: small models have limited instruction-following ability; the extension has built-in retries and degraded parsing, but if it happens often, switch to the 9B model.
- **Out of VRAM**: 2B needs ~8GB, 9B needs ~24GB; try `--gpu-memory-utilization 0.85` or `--max-model-len 8192` to reduce usage.

## Known limitations (roadmap)

- [ ] No streaming output yet — translations appear after each batch completes
- [ ] Dynamically loaded content (infinite scroll) is not translated automatically — click again
- [ ] Custom translation prompts / glossaries

## License

[Apache License 2.0](LICENSE)
