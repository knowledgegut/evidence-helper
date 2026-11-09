# ocrbox.ps1｜知識包小腸蒐證技能包 kg-evidence-report（Windows 版的 ocrbox）
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File ocrbox.ps1 <圖檔>
#   -> 每行輸出: x0<Tab>y0<Tab>x1<Tab>y1<Tab>文字（像素座標，左上為原點），跟 macOS 的 ocrbox 完全同格式
# 引擎: Windows 10／11 內建文字辨識（Windows.Media.Ocr），不用安裝任何東西、不連網。
# 語言: 優先用中文（繁體 → 簡體），這台沒裝中文辨識就退回可用語言，並在錯誤輸出提示怎麼補裝。
#       想指定語言可設環境變數 KG_OCR_LANG（例：zh-Hans-CN 掃簡體截圖）。
# 這支檔案要存成「UTF-8 含 BOM」，Windows PowerShell 5.1 才讀得懂中文。
param([Parameter(Mandatory = $true)][string]$Path)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false

function Warn([string]$msg) { [Console]::Error.WriteLine($msg) }

if (-not (Test-Path -LiteralPath $Path)) { Warn "❌ 找不到圖檔：$Path"; exit 1 }
$full = (Resolve-Path -LiteralPath $Path).ProviderPath

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Foundation.IAsyncOperation`1, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapTransform, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapBounds, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.ExifOrientationMode, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.ColorManagementMode, Windows.Foundation, ContentType = WindowsRuntime]

# WinRT 非同步 → 等結果
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await($op, [Type]$type) {
    $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $null = $t.Wait(-1)
    $t.Result
}

# 1. 挑辨識語言：指定的 → 繁中 → 簡中 → 任何中文 → 使用者語言 → 第一個可用
$langs = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages)
if ($langs.Count -eq 0) {
    Warn "❌ 這台 Windows 沒有任何文字辨識語言。用系統管理員身分開 PowerShell 執行：Add-WindowsCapability -Online -Name 'Language.OCR~~~zh-TW~0.0.1.0'"
    exit 2
}
$want = @()
if ($env:KG_OCR_LANG) { $want += $env:KG_OCR_LANG }
$want += @('zh-Hant-TW', 'zh-TW', 'zh-Hant', 'zh-Hant-HK', 'zh-HK', 'zh-Hans-CN', 'zh-CN', 'zh-Hans')
$pick = $null
foreach ($tag in $want) {
    $pick = $langs | Where-Object { $_.LanguageTag -eq $tag } | Select-Object -First 1
    if ($pick) { break }
}
if (-not $pick) { $pick = $langs | Where-Object { $_.LanguageTag -like 'zh*' } | Select-Object -First 1 }
if ($pick) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($pick)
} else {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langs[0]) }
    $have = ($langs | ForEach-Object { $_.LanguageTag }) -join ', '
    Warn "⚠️ 這台 Windows 沒裝中文文字辨識（現有：$have），中文字會辨識不到。補裝（免費）：用系統管理員身分開 PowerShell 執行 Add-WindowsCapability -Online -Name 'Language.OCR~~~zh-TW~0.0.1.0'（簡體截圖再加 zh-CN），或到「設定 → 時間與語言 → 語言」新增中文（繁體，台灣）。"
}
if (-not $engine) { Warn "❌ 文字辨識引擎建立失敗。"; exit 2 }

# 2. 讀圖（不套 EXIF 旋轉，座標跟 Python 的 PIL 一致）
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($full)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$W = [double]$decoder.PixelWidth; $H = [double]$decoder.PixelHeight

# 3. 引擎有圖片尺寸上限 → 太寬就等比縮小，太長（長截圖）就切段辨識、重疊區只算一次
$max = [double][Windows.Media.Ocr.OcrEngine]::MaxImageDimension
$s = [Math]::Min(1.0, $max / $W)
$sw = [uint32][Math]::Floor($W * $s); $sh = [uint32][Math]::Floor($H * $s)
$tile = [uint32][Math]::Min($sh, $max)
$overlap = [uint32][Math]::Min(300, [Math]::Floor($tile / 4))
$starts = @(); $y = [uint32]0
while ($true) { $starts += $y; if ($y + $tile -ge $sh) { break }; $y = [uint32]($y + $tile - $overlap) }

$sb = New-Object System.Text.StringBuilder
$inv = [Globalization.CultureInfo]::InvariantCulture
for ($i = 0; $i -lt $starts.Count; $i++) {
    $y0 = $starts[$i]; $th = [uint32][Math]::Min($tile, $sh - $y0)
    $tr = New-Object Windows.Graphics.Imaging.BitmapTransform
    $tr.ScaledWidth = $sw; $tr.ScaledHeight = $sh
    $b = New-Object Windows.Graphics.Imaging.BitmapBounds
    $b.X = 0; $b.Y = $y0; $b.Width = $sw; $b.Height = $th
    $tr.Bounds = $b
    $bmp = Await ($decoder.GetSoftwareBitmapAsync(
            [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied, $tr,
            [Windows.Graphics.Imaging.ExifOrientationMode]::IgnoreExifOrientation,
            [Windows.Graphics.Imaging.ColorManagementMode]::DoNotColorManage)) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    $lo = if ($i -gt 0) { $y0 + $overlap / 2 } else { 0 }
    $hi = if ($i -lt $starts.Count - 1) { $y0 + $th - $overlap / 2 } else { [double]::MaxValue }
    foreach ($line in $res.Lines) {
        $ws = @($line.Words); if ($ws.Count -eq 0) { continue }
        $x0 = [double]::MaxValue; $ly0 = [double]::MaxValue; $x1 = 0.0; $ly1 = 0.0
        $text = ''; $prev = ''
        foreach ($wd in $ws) {  # 注意：PowerShell 變數不分大小寫，別用 $w（會蓋掉圖寬 $W）
            $r = $wd.BoundingRect
            $x0 = [Math]::Min($x0, $r.X); $ly0 = [Math]::Min($ly0, $r.Y)
            $x1 = [Math]::Max($x1, $r.X + $r.Width); $ly1 = [Math]::Max($ly1, $r.Y + $r.Height)
            # 中文辨識會把每個字當一個「詞」、中間塞空白 → 只有英數字之間才補空白，中文黏回去（才比對得到關鍵句）
            $t = $wd.Text
            if ($text -ne '' -and $prev -match '[A-Za-z0-9]$' -and $t -match '^[A-Za-z0-9]') { $text += ' ' }
            $text += $t; $prev = $t
        }
        $cy = $y0 + ($ly0 + $ly1) / 2
        if ($cy -lt $lo -or $cy -ge $hi) { continue }
        $text = $text -replace "[`t`r`n]", ' '
        $vals = @(($x0 / $s), (($ly0 + $y0) / $s), ($x1 / $s), (($ly1 + $y0) / $s)) | ForEach-Object { [Math]::Round($_).ToString($inv) }
        $null = $sb.Append(($vals -join "`t") + "`t" + $text + "`n")
    }
}
[Console]::Out.Write($sb.ToString())
