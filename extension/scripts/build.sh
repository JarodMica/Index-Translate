#!/usr/bin/env bash
# 打包脚本：分别产出 Chrome/Edge 和 Firefox 的安装包
# 用法：./scripts/build.sh
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' manifest.json | head -1)
OUT_DIR="dist"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# 公共文件
FILES="background.js content popup options README.md"

# --- Chrome / Edge 包（用默认 manifest.json）---
zip -r "$OUT_DIR/page-translator-chrome-v$VERSION.zip" manifest.json $FILES -x "*.DS_Store" > /dev/null
echo "✓ $OUT_DIR/page-translator-chrome-v$VERSION.zip  (Chrome / Edge 通用)"

# --- Firefox 包（用 manifest.firefox.json 替换 manifest.json）---
STAGE=$(mktemp -d)
cp -r $FILES "$STAGE/"
cp manifest.firefox.json "$STAGE/manifest.json"
(cd "$STAGE" && zip -r firefox.zip . -x "*.DS_Store" > /dev/null)
mv "$STAGE/firefox.zip" "$OUT_DIR/page-translator-firefox-v$VERSION.zip"
rm -rf "$STAGE"
echo "✓ $OUT_DIR/page-translator-firefox-v$VERSION.zip  (Firefox)"
