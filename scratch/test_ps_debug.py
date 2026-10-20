import sys, os
sys.path.insert(0, os.path.abspath("."))
from perception.ocr_engine import POWERSHELL_EXE, WinRTOcrBackend
import subprocess, json
from pathlib import Path

p = Path("scratch/test_ocr_sample.png").resolve()
safe_path = str(p).replace("'", "''")

ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | ? {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }}

Function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}}

[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{safe_path}')) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) {{
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
}}

$ocrResult = $engine.RecognizeAsync($bitmap)
$res = Await ($ocrResult) ([Windows.Media.Ocr.OcrResult])

$lines = @()
foreach ($line in $res.Lines) {{
    $words = @()
    foreach ($w in $line.Words) {{
        $words += @{{
            text = $w.Text
            x = [int]$w.BoundingRect.X
            y = [int]$w.BoundingRect.Y
            width = [int]$w.BoundingRect.Width
            height = [int]$w.BoundingRect.Height
        }}
    }}
    $lines += @{{
        text = $line.Text
        words = $words
    }}
}}

@{{ lines = $lines }} | ConvertTo-Json -Depth 5 -Compress
"""

res = subprocess.run([POWERSHELL_EXE, "-NoProfile", "-NonInteractive", "-Command", ps_script], capture_output=True, text=True)
print("STDOUT:", repr(res.stdout))
print("STDERR:", repr(res.stderr))
print("CODE:", res.returncode)
