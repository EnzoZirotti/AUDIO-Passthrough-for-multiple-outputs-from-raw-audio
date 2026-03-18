@echo off
REM Build script for creating distribution package
echo ========================================
echo BluetoothStreamer Distribution Builder
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

echo Step 1: Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller setuptools wheel
if errorlevel 1 (
    echo ERROR: Failed to install build dependencies
    pause
    exit /b 1
)

echo.
echo Step 2: Installing application dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install application dependencies
    pause
    exit /b 1
)

echo.
echo Step 3: Creating distribution directory...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
mkdir dist

echo.
echo Step 4: Building executable with PyInstaller...
python -m PyInstaller --clean --noconfirm bluetoothstreamer.spec
if errorlevel 1 (
    echo ERROR: Failed to build executable
    pause
    exit /b 1
)

echo.
echo Step 5: Copying additional files...
if exist "dist\BluetoothStreamer" (
    copy /Y README.md "dist\BluetoothStreamer\" >nul
    copy /Y LICENSE "dist\BluetoothStreamer\" >nul 2>nul
    copy /Y QUICK_START.txt "dist\BluetoothStreamer\" >nul 2>nul
    if exist "install_ffmpeg.bat" copy /Y install_ffmpeg.bat "dist\BluetoothStreamer\" >nul
    if exist "install_ytdlp.bat" copy /Y install_ytdlp.bat "dist\BluetoothStreamer\" >nul
    echo Additional files copied.
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Distribution files are in: dist\BluetoothStreamer\
echo.
echo You can now:
echo 1. Test the executable: dist\BluetoothStreamer\BluetoothStreamer.exe
echo 2. Create a ZIP file for distribution
echo 3. Create an installer using Inno Setup or NSIS
echo.
pause

