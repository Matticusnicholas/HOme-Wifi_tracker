@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM HomeWatch - Simple WiFi Monitor
REM One-click setup for REAL network capture on Windows
REM ============================================================

title HomeWatch Setup

REM Check for admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ============================================================
echo    HomeWatch - WiFi Monitor Setup
echo    REAL Network Capture Edition
echo ============================================================
echo.

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Check if Npcap is installed (required for real capture)
echo [CHECK] Looking for Npcap...
if exist "C:\Program Files\Npcap\NPFInstall.exe" (
    echo [OK] Npcap is installed
) else if exist "C:\Windows\System32\Npcap\NPFInstall.exe" (
    echo [OK] Npcap is installed
) else (
    echo [WARNING] Npcap is NOT installed!
    echo.
    echo Npcap is REQUIRED for real network capture.
    echo.

    choice /C YN /M "Do you want to download and install Npcap now"
    if errorlevel 2 (
        echo.
        echo [INFO] Skipping Npcap installation.
        echo        The app will NOT be able to capture real network traffic.
        echo.
    ) else (
        echo.
        echo [INFO] Downloading Npcap installer...

        REM Download Npcap
        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://npcap.com/dist/npcap-1.79.exe' -OutFile '%TEMP%\npcap-installer.exe'}"

        if exist "%TEMP%\npcap-installer.exe" (
            echo [OK] Download complete
            echo.
            echo [INFO] Running Npcap installer...
            echo        IMPORTANT: Check "WinPcap API-compatible Mode" during install!
            echo.
            start /wait "" "%TEMP%\npcap-installer.exe"
            del "%TEMP%\npcap-installer.exe" 2>nul
            echo [OK] Npcap installation completed
        ) else (
            echo [ERROR] Download failed. Please install manually from:
            echo         https://npcap.com/#download
            echo.
            pause
        )
    )
)

echo.

REM Check/create virtual environment
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
    echo [OK] Virtual environment exists
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
echo [SETUP] Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

REM Install dependencies
echo [SETUP] Installing dependencies...

pip install flask flask-cors apscheduler --quiet 2>nul
echo [OK] Flask packages installed

echo [SETUP] Installing Scapy for network capture...
pip install scapy --quiet 2>nul
echo [OK] Scapy installed

REM Create data directory
if not exist "data" mkdir data

echo.
echo ============================================================
echo    Setup Complete!
echo ============================================================
echo.
echo    Starting HomeWatch with REAL network capture...
echo.
echo    Open your browser to: http://localhost:5000
echo.
echo    Press Ctrl+C to stop
echo ============================================================
echo.

REM Run the app
python app.py

pause
