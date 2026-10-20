@echo off
setlocal enabledelayedexpansion
title Stop COMPASS Services
color 0E

:: Ensure working directory is the repository root
cd /d "%~dp0"

echo ===============================================================================
echo                   COMPASS — Safe Shutdown Manager
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

echo [*] Stopping all COMPASS processes and freeing ports (8000, 5173, 8001)...
"!PYTHON_EXE!" scripts\stop_compass.py

echo.
echo [*] Done. All COMPASS background processes have been terminated safely.
timeout /t 2 /nobreak >nul
