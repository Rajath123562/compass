@echo off
setlocal enabledelayedexpansion
title COMPASS — AI Interface Assistant
color 0B

:: Ensure working directory is the repository root
cd /d "%~dp0"

echo ===============================================================================
echo        COMPASS — AI-Based Digital Interface Guidance System
echo                     Production Release v14.0-certified
echo ===============================================================================
echo.

:: 1. Detect Python Executable (virtualenv, WindowsApps, Python bin, or system PATH)
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "C:\Windows\py.exe" set "PYTHON_EXE=C:\Windows\py.exe"

if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    py --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    color 0C
    echo [ERROR] Neither .venv nor system Python was found on PATH.
    echo Please install Python 3.10+ and ensure it is added to your PATH.
    echo.
    pause
    exit /b 1
)

:: 2. Pre-flight Cleanup (Release any ports from previous unclean runs)
echo [*] Checking for and cleaning up any stale background processes...
"!PYTHON_EXE!" scripts\stop_compass.py >nul 2>&1
ping -n 2 127.0.0.1 >nul

:: 2.5 Local AI Engine Detection (Ollama)
echo [*] Checking local AI engine (Ollama on port 11434)...
"!PYTHON_EXE!" -c "import socket; s = socket.socket(); s.settimeout(0.4); exit(s.connect_ex(('127.0.0.1', 11434)))" >nul 2>&1
if errorlevel 1 goto :OLLAMA_OFFLINE
echo [*] Local AI engine (Ollama) is active and ready.
goto :LAUNCH_SERVICES

:OLLAMA_OFFLINE
echo [!] Ollama is not active on port 11434. Checking if installed...
where ollama >nul 2>&1
if errorlevel 1 goto :NO_OLLAMA
echo [*] Starting local 'ollama serve' in background...
start "" /b ollama serve >nul 2>&1
ping -n 2 127.0.0.1 >nul
echo [*] Ollama engine service started.
goto :LAUNCH_SERVICES

:NO_OLLAMA
echo [!] Notice: 'ollama' not detected in system PATH. (COMPASS will run in local-safe mode).

:LAUNCH_SERVICES
echo.

:: 3. Launch COMPASS Supervisor (Backend + Frontend + Overlay + Browser)
echo [*] Launching COMPASS All-in-One:
echo     - FastAPI Backend API : http://127.0.0.1:8000
echo     - React + Vite Web UI : http://127.0.0.1:5173
echo     - Desktop Overlay HUD : Active
echo     - Web Browser         : Opening automatically...
echo.
echo ===============================================================================
echo   To STOP COMPASS at any time: Press [Ctrl + C] in this window,
echo   or run STOP_COMPASS.bat
echo ===============================================================================
echo.

:: Run unified supervisor (starts Backend, Frontend, Overlay, and opens Browser once ready)
"!PYTHON_EXE!" scripts\start_compass.py --open-browser --with-overlay %*

:: If supervisor exits, report status
echo.
echo [COMPASS] Session ended. Cleaning up background services...
"!PYTHON_EXE!" scripts\stop_compass.py >nul 2>&1
echo [COMPASS] All services stopped cleanly.
echo.
pause
