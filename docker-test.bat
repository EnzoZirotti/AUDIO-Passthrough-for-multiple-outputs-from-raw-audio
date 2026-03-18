@echo off
REM Test script to diagnose Docker issues

echo ========================================
echo Docker Container Test
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Desktop is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)
echo [OK] Docker Desktop is running
echo.

REM Check if image exists
docker images audio-sync-gui:latest >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker image 'audio-sync-gui:latest' not found!
    echo Please run: docker-build.bat
    pause
    exit /b 1
)
echo [OK] Docker image exists
echo.

echo Testing container startup (non-GUI mode)...
echo.

REM Test if container can start and Python works
docker run --rm audio-sync-gui:latest python --version
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Container cannot run Python!
    pause
    exit /b 1
)
echo [OK] Python works in container
echo.

echo Testing imports...
docker run --rm audio-sync-gui:latest python -c "import tkinter; print('tkinter OK')"
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] tkinter import failed - GUI may not work
) else (
    echo [OK] tkinter import works
)
echo.

echo Testing main script syntax...
docker run --rm audio-sync-gui:latest python -m py_compile audio_sync_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] audio_sync_gui.py has syntax errors!
    pause
    exit /b 1
)
echo [OK] audio_sync_gui.py syntax is valid
echo.

echo ========================================
echo Container test complete!
echo ========================================
echo.
echo If all tests passed, the issue is likely with GUI display.
echo On Windows, you need X11 forwarding or WSL2 setup.
echo.
pause
