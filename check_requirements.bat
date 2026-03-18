@echo off
REM Requirements Checker for Windows
REM Checks if all required components are installed

echo ========================================
echo Audio Sync GUI - Requirements Checker
echo ========================================
echo.

set ALL_OK=1

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Python is NOT installed
    echo     Download from: https://www.python.org/downloads/
    set ALL_OK=0
) else (
    echo [OK] Python is installed
    python --version
)

echo.

REM Check pip
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] pip is NOT available
    set ALL_OK=0
) else (
    echo [OK] pip is available
)

echo.

REM Check required packages
echo Checking required packages...
echo.

python -c "import pygame" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] pygame - NOT installed
    set ALL_OK=0
) else (
    echo [OK] pygame
)

python -c "import sounddevice" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] sounddevice - NOT installed
    set ALL_OK=0
) else (
    echo [OK] sounddevice
)

python -c "import numpy" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] numpy - NOT installed
    set ALL_OK=0
) else (
    echo [OK] numpy
)

python -c "import pydub" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] pydub - NOT installed
    set ALL_OK=0
) else (
    echo [OK] pydub
)

python -c "import yt_dlp" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] yt-dlp - NOT installed
    set ALL_OK=0
) else (
    echo [OK] yt-dlp
)

python -c "import requests" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] requests - NOT installed
    set ALL_OK=0
) else (
    echo [OK] requests
)

echo.

REM Check optional Windows packages
echo Checking optional Windows packages...
echo.

python -c "import pyaudiowpatch" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] PyAudioWPatch - NOT installed (optional, for better WASAPI support)
) else (
    echo [OK] PyAudioWPatch
)

python -c "import comtypes" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] comtypes - NOT installed (optional, for volume control)
) else (
    echo [OK] comtypes
)

python -c "import pycaw" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] pycaw - NOT installed (optional, for volume control)
) else (
    echo [OK] pycaw
)

echo.
echo ========================================
if %ALL_OK% EQU 1 (
    echo All required packages are installed!
    echo You can run the application.
) else (
    echo Some required packages are missing.
    echo Run install.bat to install them.
)
echo ========================================
echo.

pause
