@echo off
REM ============================================================
REM HomeWatch - Quick Run (after setup is complete)
REM ============================================================

title HomeWatch

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Setup not complete! Run setup_and_run.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo.
echo ============================================
echo    HomeWatch - Simple WiFi Monitor
echo    http://localhost:5000
echo ============================================
echo.

python app.py

pause
