@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM HomeWatch - Simple WiFi Monitor
REM One-click setup and run script for Windows
REM ============================================================

title HomeWatch Setup and Run

echo.
echo ============================================================
echo    HomeWatch - Simple WiFi Monitor Setup
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [INFO] Working directory: %SCRIPT_DIR%
echo.

REM Check if virtual environment exists, if not create it
if not exist "venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated

REM Upgrade pip
echo.
echo [SETUP] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo.
echo [SETUP] Installing dependencies...
echo         This may take a minute...
echo.

REM Install packages one by one for better error handling
pip install flask --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install flask
    pause
    exit /b 1
)
echo [OK] Flask installed

pip install flask-cors --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install flask-cors
    pause
    exit /b 1
)
echo [OK] Flask-CORS installed

pip install apscheduler --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install apscheduler
    pause
    exit /b 1
)
echo [OK] APScheduler installed

REM Try to install scapy (may require Npcap on Windows)
echo.
echo [SETUP] Installing Scapy (for network capture)...
pip install scapy --quiet
if errorlevel 1 (
    echo [WARNING] Scapy installation had issues - will run in demo mode
) else (
    echo [OK] Scapy installed
)

REM Create data directory if needed
if not exist "data" mkdir data

echo.
echo ============================================================
echo    Setup Complete! Starting HomeWatch...
echo ============================================================
echo.
echo    IMPORTANT NOTES:
echo    ----------------
echo    1. Open your browser to: http://localhost:5000
echo    2. The app will run in DEMO MODE (generates sample data)
echo    3. For real network capture on Windows, you need:
echo       - Npcap installed: https://npcap.com/#download
echo       - Run this script as Administrator
echo.
echo    Press Ctrl+C to stop the server
echo.
echo ============================================================
echo.

REM Start the application
python app.py

REM If we get here, the app stopped
echo.
echo [INFO] HomeWatch stopped
pause
