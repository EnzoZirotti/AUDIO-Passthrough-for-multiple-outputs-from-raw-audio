#!/bin/bash
# Universal Linux/macOS Installer for Audio Sync GUI
# This script installs all dependencies and sets up the application

echo "========================================"
echo "Audio Sync GUI - Universal Installer"
echo "========================================"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.7 or higher:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip"
    echo "  macOS: brew install python3"
    echo "  Or download from: https://www.python.org/downloads/"
    exit 1
fi

echo "[OK] Python is installed"
python3 --version
echo ""

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "[ERROR] pip3 is not available!"
    echo "Please install pip:"
    echo "  Ubuntu/Debian: sudo apt-get install python3-pip"
    echo "  macOS: python3 -m ensurepip --upgrade"
    exit 1
fi

echo "[OK] pip is available"
echo ""

# Upgrade pip first
echo "Upgrading pip..."
python3 -m pip install --upgrade pip --quiet
echo ""

# Install requirements
echo "Installing required packages..."
echo "This may take a few minutes..."
echo ""

python3 -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to install some packages!"
    echo "Please check the error messages above."
    exit 1
fi

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "You can now run the application using:"
echo "  python3 audio_sync_gui.py"
echo ""
echo "Or make it executable and run directly:"
echo "  chmod +x audio_sync_gui.py"
echo "  ./audio_sync_gui.py"
echo ""
