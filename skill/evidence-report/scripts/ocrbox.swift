import Foundation; import Vision; import AppKit
// 用法: ocrbox <圖檔>  -> 每行輸出: x0\ty0\tx1\ty1\ttext（像素座標，左上為原點）
// 編譯: swiftc ocrbox.swift -o ocrbox
// 用途: macOS 內建 Vision 文字辨識，回傳每段文字的像素外框 → 給 annotate.py 定位要畫紅框的關鍵句
let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }
let W = Double(cg.width), H = Double(cg.height)
let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate
req.recognitionLanguages = ["zh-Hans","zh-Hant","en-US"]; req.usesLanguageCorrection = false
try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
for r in req.results ?? [] { guard let c = r.topCandidates(1).first else { continue }
  let b = r.boundingBox
  print(String(format:"%.0f\t%.0f\t%.0f\t%.0f\t", b.minX*W, (1-b.maxY)*H, b.maxX*W, (1-b.minY)*H) + c.string) }
