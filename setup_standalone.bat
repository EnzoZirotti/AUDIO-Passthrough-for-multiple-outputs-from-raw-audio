@echo off
REM Create Standalone Executable for Windows
REM This creates a single .exe file that works without Python installation

echo ========================================
echo Creating Standalone Executable
echo ========================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo.
echo Building standalone executable...
echo This may take several minutes...
echo.

REM Build the executable
pyinstaller --onefile --windowed --name AudioSyncGUI --icon=NONE audio_sync_gui.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build Complete!
    echo ========================================
    echo.
    echo Executable created at: dist\AudioSyncGUI.exe
    echo.
    echo You can now share this .exe file - it works on any Windows computer!
    echo No Python installation needed.
    echo.
) else (
    echo.
    echo [ERROR] Build failed!
    echo Check the error messages above.
)

pause
