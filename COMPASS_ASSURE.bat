@echo off
setlocal enabledelayedexpansion
title COMPASS — Continuous Production Assurance
color 0D

cd /d "%~dp0"

echo ===============================================================================
echo   COMPASS — Continuous Production Assurance System
echo   DISCOVER - INVENTORY - ANALYZE - ATTACK - VERIFY - REPORT
echo ===============================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    color 0C
    echo [ERROR] Virtual environment not found!
    pause
    exit /b 1
)

:: Parse mode from command line argument (default: --quick)
set MODE=--quick
if not "%~1"=="" set MODE=%~1

echo [*] Running assurance pipeline with mode: %MODE%
echo.

.venv\Scripts\python.exe assurance\compass_assure.py %MODE%

echo.
echo [*] Assurance pipeline complete.
echo     Reports saved to: assurance\reports\
echo.
pause
