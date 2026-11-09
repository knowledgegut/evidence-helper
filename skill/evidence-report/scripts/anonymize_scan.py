#!/usr/bin/env python3
"""
去品牌 / 遮個資掃描｜知識包小腸蒐證技能包 kg-evidence-report

交付前最後一道安全閘門：OCR 掃過每一張證據圖，抓有沒有露出
① 你自己的本名／帳號（不露自己）② 同行者本名 ③ 不該外流的第三方個資。
命中的圖 → 必須裁掉該段或遮掉，才能進報告。

跟畫紅框用同一顆文字辨識（macOS ocrbox／Windows ocrbox.ps1，取文字欄），不另裝 OCR。

用法:
    swiftc scripts/ocrbox.swift -o scripts/ocrbox   # 只需一次（macOS；Windows 不用，自動走 scripts/ocrbox.ps1）
    python3 scripts/anonymize_scan.py --src <證據圖資料夾> \
        --block "<你的本名>,<你的帳號>,<同行者本名>,<其他要擋的字>"
    # 或把要擋的字一行一個寫進檔案：--blockfile blocklist.txt

擋字清單一定要自己填（你的名字、帳號、同行者、不該外流的資訊）。
"""
import os, sys, argparse, glob
from ocr_engine import ocr_lines  # 同資料夾：macOS 走 ocrbox、Windows 走 ocrbox.ps1

DEFAULT_BLOCK = []
EXTS = ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG")

def ocr_text(img):
    return " ".join(parts[4] for parts in ocr_lines(img))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="證據圖資料夾")
    ap.add_argument("--block", default="", help="要擋的字，逗號分隔")
    ap.add_argument("--blockfile", default=None, help="要擋的字，一行一個")
    a = ap.parse_args()

    block = list(DEFAULT_BLOCK)
    block += [w.strip() for w in a.block.split(",") if w.strip()]
    if a.blockfile and os.path.exists(a.blockfile):
        block += [l.strip() for l in open(a.blockfile, encoding="utf-8") if l.strip()]
    block = list(dict.fromkeys(block))  # 去重保序

    imgs = sorted({f for pat in EXTS for f in glob.glob(os.path.join(a.src, pat))})
    if not imgs:
        sys.exit(f"❌ {a.src} 裡找不到圖")

    print(f"🔍 掃描 {len(imgs)} 張圖，擋字清單：{block}\n")
    flagged = []
    for img in imgs:
        text = ocr_text(img)
        hits = [w for w in block if w.lower() in text.lower()]
        name = os.path.basename(img)
        if hits:
            flagged.append((name, hits)); print(f"🚨 {name}  →  命中：{hits}")
        else:
            print(f"✅ {name}")

    print()
    if flagged:
        print(f"❌ 有 {len(flagged)} 張圖露出要擋的字，交付前必須裁掉該段或遮掉：")
        for name, hits in flagged:
            print(f"   - {name}：{hits}")
        sys.exit(1)
    print("✅ 全部乾淨，沒有露出要擋的字。")

if __name__ == "__main__":
    main()
