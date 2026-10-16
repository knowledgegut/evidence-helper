#!/usr/bin/env bash
# HTML → PDF｜知識包小腸蒐證技能包 kg-evidence-report
# 用 Chrome 無頭當「純 PDF 後端」（吃報告模板的 @media print CSS：分欄、不切斷卡片）。
# 只支援 macOS 的 Chrome；Windows／沒裝 Chrome：用瀏覽器打開報告 HTML → 列印 → 另存 PDF。
#
# 用法: bash html_to_pdf.sh <報告.html> [輸出.pdf]
#   不給輸出路徑 → 同名 .pdf
set -euo pipefail

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || { echo "❌ 找不到 Chrome：$CHROME"; exit 1; }

IN="${1:?用法: bash html_to_pdf.sh <報告.html> [輸出.pdf]}"
[ -f "$IN" ] || { echo "❌ 找不到檔案：$IN"; exit 1; }
ABS="$(cd "$(dirname "$IN")" && pwd)/$(basename "$IN")"
OUT="${2:-${ABS%.html}.pdf}"

"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$ABS" 2>/dev/null

if [ -f "${OUT}" ]; then
  SIZE=$(stat -f%z "${OUT}")
  KB=$(( SIZE / 1024 ))
  echo "✅ PDF 產好: ${OUT}  (${KB} KB)"
  [ "${SIZE}" -lt 5000 ] && echo "⚠️  檔案很小，可能渲染失敗，打開看一眼再交付。"
else
  echo "❌ 沒產出 PDF，檢查 HTML 路徑與圖片相對路徑。"; exit 1
fi
