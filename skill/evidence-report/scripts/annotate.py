#!/usr/bin/env python3
"""
證據紅框工具（通用版）｜知識包小腸蒐證技能包 kg-evidence-report

把一批證據截圖裡的「關鍵原話」自動畫上紅框，長截圖自動裁到有紅框的段落。
紅框以外的內容一字不改 ← 這是證據的公信力來源（報告 legend 會寫明）。

OCR 引擎用 ocrbox（macOS 內建 Vision，吐文字＋像素座標，才能定位畫框）。

用法:
    # 1. 先編譯 OCR 引擎（只需一次）
    swiftc scripts/ocrbox.swift -o scripts/ocrbox
    # 2. 跑標示
    python3 scripts/annotate.py --src <證據圖資料夾> --spec <spec.json> [--out <輸出資料夾>]

spec.json 格式（兩種寫法，可混用）:
    {
      "E01_課程文宣.jpg": ["保證學會", "不滿意全額退費"],   ← 簡寫：只列關鍵句
      "E05_長截圖.png": {                                      ← 完整寫法
        "keys": ["要總部核准", "再等兩週", "已經在處理"],
        "skip_single": ["的", "應該是"],         ← 太短的詞只在整行完全相符時才框（避免亂框）
        "manual_crops": [[600, 2780], [3700, 4110]]  ← 手動指定長截圖裁切 y 區間（像素），不填則自動分群
      }
    }

輸出: <out>/<同檔名>.jpg（長截圖切多張時加 _a/_b/_c…）+ _index.json（每張框了幾個、輸出哪些）
"""
import subprocess, json, os, sys, argparse
from PIL import Image, ImageDraw

RED = (225, 29, 72)  # 與報告模板 --mark 同色

def load_spec(path):
    raw = json.load(open(path, encoding="utf-8"))
    norm = {}
    for fn, v in raw.items():
        if fn.startswith("_"):  # 「_說明」這類註解欄位，不是證據圖
            continue
        if isinstance(v, list):
            norm[fn] = {"keys": v, "skip_single": [], "manual_crops": []}
        else:
            norm[fn] = {"keys": v.get("keys", []),
                        "skip_single": v.get("skip_single", []),
                        "manual_crops": v.get("manual_crops", [])}
    return norm

def ocr_lines(ocr_bin, img_path):
    out = subprocess.run([ocr_bin, img_path], capture_output=True, text=True).stdout
    return [l.split("\t") for l in out.splitlines() if l.count("\t") >= 4]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="證據圖資料夾")
    ap.add_argument("--spec", required=True, help="spec.json 路徑")
    ap.add_argument("--out", default=None, help="輸出資料夾（預設 <src>/標示）")
    a = ap.parse_args()

    src = a.src
    out = a.out or os.path.join(src, "標示")
    os.makedirs(out, exist_ok=True)
    ocr_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocrbox")
    if not os.path.exists(ocr_bin):
        sys.exit("❌ 找不到 ocrbox 執行檔，先編譯：swiftc scripts/ocrbox.swift -o scripts/ocrbox")

    spec = load_spec(a.spec)
    res = {}
    for fn, cfg in spec.items():
        p = os.path.join(src, fn)
        if not os.path.exists(p):
            print(f"⚠️  跳過（找不到檔）: {fn}"); continue
        keys, skip_single = cfg["keys"], set(cfg["skip_single"])
        im = Image.open(p).convert("RGB"); W, H = im.size
        lines = ocr_lines(ocr_bin, p)

        # 1. 比對關鍵句 → 命中的文字外框
        hits = []
        for x0, y0, x1, y1, t in lines:
            for k in keys:
                ok = (t.strip() == k) if k in skip_single else (k in t)
                if ok:
                    hits.append([int(float(x0)), int(float(y0)), int(float(x1)), int(float(y1))]); break

        # 2. 垂直相鄰的框合併成一塊
        hits.sort(key=lambda b: b[1]); boxes = []
        for b in hits:
            if boxes and b[1] - boxes[-1][3] < 0.03 * H + 25 and not (b[0] > boxes[-1][2] or b[2] < boxes[-1][0]):
                m = boxes[-1]; boxes[-1] = [min(m[0], b[0]), min(m[1], b[1]), max(m[2], b[2]), max(m[3], b[3])]
            else:
                boxes.append(b)

        # 3. 畫圓角紅框
        d = ImageDraw.Draw(im); pad = max(8, int(W * 0.012)); lw = max(5, int(W * 0.007))
        for x0, y0, x1, y1 in boxes:
            d.rounded_rectangle([max(0, x0 - pad), max(0, y0 - pad), min(W - 1, x1 + pad), min(H - 1, y1 + pad)],
                                radius=pad, outline=RED, width=lw)

        # 4. 長截圖裁切（手動優先 → 自動分群 → 不裁）
        if cfg["manual_crops"]:
            crops = [tuple(c) for c in cfg["manual_crops"]]
        elif H > 2.0 * W and boxes:
            ctx = int(W * 0.35); groups = []
            for b in boxes:
                if groups and b[1] - groups[-1][1] < int(W * 0.9):
                    groups[-1][1] = max(groups[-1][1], b[3])
                else:
                    groups.append([b[1], b[3]])
            crops = [(max(0, g0 - ctx), min(H, g1 + ctx)) for g0, g1 in groups]
        else:
            crops = [(0, H)]

        # 5. 輸出（寬超過 1100 縮到 1100）
        outs = []; base = fn.rsplit(".", 1)[0]
        for i, (y0, y1) in enumerate(crops):
            o = im.crop((0, y0, W, y1))
            if o.width > 1100:
                o = o.resize((1100, int(o.height * 1100 / o.width)))
            name = f"{base}{'' if len(crops) == 1 else '_' + 'abcdefg'[i]}.jpg"
            o.save(os.path.join(out, name), quality=85); outs.append(name)
        res[fn] = {"boxes": len(boxes), "outs": outs}
        print(f"{fn}  紅框 {len(boxes)}  →  {outs}")

    json.dump(res, open(os.path.join(out, "_index.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n✅ 完成，輸出在 {out}/（_index.json 有清單）")
    miss = [fn for fn, r in res.items() if r["boxes"] == 0]
    if miss:
        print(f"⚠️  這些圖一個關鍵句都沒框到，檢查 spec 的字串是否跟截圖「簡繁/標點」一致：{miss}")

if __name__ == "__main__":
    main()
