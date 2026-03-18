#!/bin/bash
# Requirements Checker for Linux/macOS
# Checks if all required components are installed

echo "========================================"
echo "Audio Sync GUI - Requirements Checker"
echo "========================================"
echo ""

ALL_OK=1

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[X] Python 3 is NOT installed"
    echo "    Install: sudo apt-get install python3 (Ubuntu/Debian)"
    ALL_OK=0
else
    echo "[OK] Python 3 is installed"
    python3 --version
fi

echo ""

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "[X] pip3 is NOT available"
    ALL_OK=0
else
    echo "[OK] pip3 is available"
fi

echo ""

# Check required packages
echo "Checking required packages..."
echo ""

python3 -c "import pygame" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[X] pygame - NOT installed"
    ALL_OK=0
else
    echo "[OK] pygame"
fi

python3 -c "import sounddevice" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[X] sounddevice - NOT installed"
    ALL_OK=0
else
    echo "[OK] sounddevice"
fi

python3 -c "import numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[X] numpy - NOT installed"
    ALL_OK=0
else
    echo "[OK] numpy"
fi

python3 -c "import pydub" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[X] pydub - NOT installed"
    ALL_OK=0
else
    echo "[OK] pydub"
fi

python3 -c "import yt_dlp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[X] yt-dlp - NOT installed"
    ALL_OK=0
else
    echo "[OK] yt-dlp"
fi

python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[X] requests - NOT installed"
    ALL_OK=0
else
    echo "[OK] requests"
fi

echo ""
echo "========================================"
if [ $ALL_OK -eq 1 ]; then
    echo "All required packages are installed!"
    echo "You can run the application."
else
    echo "Some required packages are missing."
    echo "Run ./install.sh to install them."
fi
echo "========================================"
echo ""
