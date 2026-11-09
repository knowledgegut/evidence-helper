#!/usr/bin/env python3
"""
HTML → PDF（macOS／Windows 都能用）｜知識包小腸蒐證技能包 kg-evidence-report

用瀏覽器的無頭模式當「純 PDF 後端」（吃報告模板的 @media print CSS：分欄、不切斷卡片）。
自動找：Windows → Edge（內建）或 Chrome；macOS → Chrome、Edge、Chromium。都不用另外安裝。
macOS 也可以照舊用 html_to_pdf.sh，結果一樣。

用法: python3 scripts/html_to_pdf.py <報告.html> [輸出.pdf]      （Windows 用 python 或 py）
  不給輸出路徑 → 同名 .pdf
"""
import os, pathlib, shutil, subprocess, sys, tempfile

for _s in (sys.stdout, sys.stderr):  # Windows 管線輸出預設不是 UTF-8，印 ✅ 會當掉
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def find_browser():
    if os.name == "nt":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"]
        cands = [os.path.join(r, rel) for rel in rels for r in roots if r]
    else:
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium"]
        cands += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")]
    return next((c for c in cands if c and os.path.isfile(c)), None)


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python3 scripts/html_to_pdf.py <報告.html> [輸出.pdf]")
    src = pathlib.Path(sys.argv[1]).resolve()
    if not src.is_file():
        sys.exit(f"❌ 找不到檔案：{src}")
    out = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.with_suffix(".pdf")

    exe = find_browser()
    if not exe:
        sys.exit("❌ 找不到 Edge 或 Chrome。改用手動：用瀏覽器打開報告 HTML → 列印 → 目的地選「另存為 PDF」。")

    # 用一個臨時的瀏覽器設定資料夾：你平常開著的瀏覽器不會被干擾，也不會把工作丟給它
    before = out.stat().st_mtime if out.is_file() else None
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                        f"--user-data-dir={prof}", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                        f"--print-to-pdf={out}", src.as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)

    if not out.is_file() or out.stat().st_mtime == before:  # 舊的同名 PDF 不算數
        sys.exit("❌ 沒產出 PDF，檢查 HTML 路徑與圖片相對路徑。")
    size = out.stat().st_size
    print(f"✅ PDF 產好: {out}  ({size // 1024} KB)")
    if size < 5000:
        print("⚠️  檔案很小，可能渲染失敗，打開看一眼再交付。")


if __name__ == "__main__":
    main()
