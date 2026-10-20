# COMPASS Launcher for Windows PowerShell
$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "COMPASS - AI Interface Assistant"

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "       COMPASS - AI-Based Digital Interface Guidance System" -ForegroundColor Cyan
Write-Host "                    Production Release v14.0-certified" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Virtual Environment / Python Executable
$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        $pythonExe = "python"
    } else {
        Write-Host "[ERROR] Neither .venv\Scripts\python.exe nor system python found!" -ForegroundColor Red
        Write-Host "Please ensure Python 3.10+ is installed and in your PATH."
        Read-Host "Press Enter to exit..."
        exit 1
    }
}

# 2. Pre-flight Cleanup
Write-Host "[*] Checking for and cleaning up any stale background processes..." -ForegroundColor Yellow
& $pythonExe (Join-Path $PSScriptRoot "scripts\stop_compass.py") *>$null
Start-Sleep -Seconds 1

# 3. Check Local AI Engine (Ollama)
Write-Host "[*] Checking local AI engine (Ollama on port 11434)..." -ForegroundColor Yellow
$ollamaOnline = $false
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect("127.0.0.1", 11434)
    $client.Close()
    $ollamaOnline = $true
} catch {
    $ollamaOnline = $false
}

if (-not $ollamaOnline) {
    Write-Host "[!] Ollama is not active on port 11434. Checking if installed..." -ForegroundColor DarkYellow
    if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
        Write-Host "[*] Starting local 'ollama serve' in background..." -ForegroundColor Green
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "[*] Ollama engine service started." -ForegroundColor Green
    } else {
        Write-Host "[!] Notice: 'ollama' not found in PATH. If using LM Studio, ensure its local server is running on port 1234." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "[*] Local AI engine (Ollama) is active and ready." -ForegroundColor Green
}
Write-Host ""

# 4. Launch COMPASS Supervisor
Write-Host "[*] Launching COMPASS Services:" -ForegroundColor Cyan
Write-Host "    - FastAPI Backend API : http://127.0.0.1:8000"
Write-Host "    - React + Vite Web UI : http://127.0.0.1:5173"
Write-Host "    - Interactive Browser : Opening automatically..."
Write-Host ""
Write-Host "===============================================================================" -ForegroundColor Gray
Write-Host "  To STOP COMPASS: Press [Ctrl + C] in this window" -ForegroundColor Gray
Write-Host "===============================================================================" -ForegroundColor Gray
Write-Host ""

& $pythonExe (Join-Path $PSScriptRoot "scripts\start_compass.py") --open-browser --with-overlay @args
