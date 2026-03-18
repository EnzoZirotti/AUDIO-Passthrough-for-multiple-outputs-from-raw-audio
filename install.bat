@echo off
REM Universal Windows Installer for Audio Sync GUI
REM This script installs all dependencies and sets up the application

echo ========================================
echo Audio Sync GUI - Universal Installer
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed!
    echo.
    echo Please install Python 3.7 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python is installed
python --version
echo.

REM Check pip
python -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip is not available!
    echo Please reinstall Python with pip included.
    pause
    exit /b 1
)

echo [OK] pip is available
echo.

REM Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo.

REM Install requirements
echo Installing required packages...
echo This may take a few minutes...
echo.

python -m pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install some packages!
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ========================================
echo VB-CABLE Driver Installation
echo ========================================
echo.
echo This application works best with a Virtual Audio Cable.
echo Would you like to download and prepare the VB-CABLE installer?
echo (This is required for "pulling raw audio" features)
echo.
set /p INSTALL_VBCABLE="Download VB-CABLE? (y/n): "

if /i "%INSTALL_VBCABLE%"=="y" (
    echo.
    echo Downloading VB-CABLE Driver Pack...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $url = 'https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip'; $vbcable_zip = 'VBCABLE_Setup.zip'; Invoke-WebRequest -Uri $url -OutFile $vbcable_zip"
    
    if exist VBCABLE_Setup.zip (
        echo Extracting files...
        if not exist vbcable_temp mkdir vbcable_temp
        powershell -Command "Expand-Archive -Path VBCABLE_Setup.zip -DestinationPath vbcable_temp -Force"
        
        echo.
        echo [IMPORTANT] To complete installation:
        echo 1. A folder 'vbcable_temp' has been created.
        echo 2. RIGHT-CLICK 'VBCABLE_Setup_x64.exe' inside that folder.
        echo 3. Select 'Run as administrator'.
        echo 4. Click 'Install Driver'.
        echo 5. Reboot your computer if prompted.
        echo.
        
        start explorer vbcable_temp
    ) else (
        echo [ERROR] Failed to download VB-CABLE.
        echo Please download it manually from: https://vb-audio.com/Cable/
    )
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo You can now run the application using:
echo   run_gui.bat
echo.
echo Or directly:
echo   python audio_sync_gui.py
echo.
pause
