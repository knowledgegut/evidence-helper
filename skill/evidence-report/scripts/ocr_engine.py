#!/usr/bin/env python3
"""
文字辨識引擎切換器｜知識包小腸蒐證技能包 kg-evidence-report

annotate.py（畫紅框）和 anonymize_scan.py（遮個資掃描）共用這支：
  - macOS   → ocrbox（macOS 內建 Vision，先編譯一次：swiftc scripts/ocrbox.swift -o scripts/ocrbox）
  - Windows → ocrbox.ps1（Windows 內建文字辨識 Windows.Media.Ocr，不用安裝任何東西）
兩邊輸出格式完全相同：每行「x0<Tab>y0<Tab>x1<Tab>y1<Tab>文字」，像素座標、左上為原點。
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_warned = set()

# Windows 上 AI 代理人用管線接輸出時，Python 預設用 cp950／cp1252 → 印 ✅ 🚨 這類符號會當掉；統一改 UTF-8
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def _cmd():
    """回傳要跑的指令前綴；這台電腦跑不了就直接結束並說明怎麼辦。"""
    if sys.platform == "darwin":
        b = os.path.join(HERE, "ocrbox")
        if not os.path.exists(b):
            sys.exit("❌ 找不到 ocrbox 執行檔，先編譯（只需一次）：swiftc scripts/ocrbox.swift -o scripts/ocrbox")
        return [b]
    if os.name == "nt":
        ps1 = os.path.join(HERE, "ocrbox.ps1")
        if not os.path.exists(ps1):
            sys.exit("❌ 找不到 scripts/ocrbox.ps1，請把整個 scripts 資料夾放回原位再試。")
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]
    sys.exit("❌ 畫紅框／遮個資掃描目前支援 macOS 與 Windows；其他系統請手動在截圖上標註與檢查個資。")


def ocr_lines(img_path):
    """辨識一張圖 → 每行一組 [x0, y0, x1, y1, 文字]（座標是字串，照原 ocrbox 輸出）。"""
    try:
        r = subprocess.run(_cmd() + [img_path], capture_output=True)
    except FileNotFoundError:
        sys.exit("❌ 叫不起 Windows PowerShell（powershell.exe）。Windows 10／11 內建就有，請確認沒被公司電腦政策停用。")
    err = r.stderr.decode("utf-8", errors="replace").strip()
    if err and err not in _warned:  # Windows 缺中文辨識語言這類提示，同一句只印一次
        _warned.add(err)
        print(err, file=sys.stderr)
    out = r.stdout.decode("utf-8", errors="replace").lstrip("﻿")
    rows = [l.split("\t", 4) for l in out.splitlines() if l.count("\t") >= 4]
    if os.name == "nt":
        for row in rows:
            row[4] = _fix_win_dash(row[4])
    return rows


def _fix_win_dash(t):
    """Windows 文字辨識常把「-」和「一」看錯（2026-11-10 雲端實測：電話 0912一345一678、不-樣）。
    數字中間的一／長短橫線改回「-」，中文字中間的「-」改回「一」，紅框與遮個資才比對得到。Mac 不需要、不經過這裡。"""
    t = re.sub(r"(?<=\d)\s*[一ー－—–‐]\s*(?=\d)", "-", t)
    t = re.sub(r"^[-－](?=[一-鿿])", "一", t)  # 行首「-般訊息」→「一般訊息」
    return re.sub(r"(?<=[一-鿿])[-－](?=[一-鿿])", "一", t)
