@echo off
REM Docker run script with VNC support (Windows-friendly)

echo ========================================
echo Audio Sync GUI - VNC Mode
echo ========================================
echo.
echo This will start the app with VNC server.
echo You can access the GUI via VNC client or web browser.
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Desktop is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Check if VNC image exists
docker images audio-sync-gui-vnc:latest >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo VNC image not found. Building it now...
    echo This may take a few minutes...
    docker build -f Dockerfile.vnc -t audio-sync-gui-vnc:latest .
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Build failed!
        pause
        exit /b 1
    )
)

echo.
echo Starting container with VNC...
echo.
echo ========================================
echo IMPORTANT: How to access the GUI
echo ========================================
echo.
echo Option 1: Web Browser (EASIEST - Recommended)
echo   1. Wait for container to start
echo   2. Open: http://localhost:6080/vnc.html
echo   3. Click "Connect" button
echo.
echo Option 2: VNC Client
echo   1. Download a VNC client (e.g., TightVNC, RealVNC)
echo   2. Connect to: localhost:5901
echo   3. Password: (no password - press Enter)
echo.
echo The container will keep running. Press Ctrl+C to stop.
echo.
pause

REM Start the container
echo.
echo Building and starting container...
echo This may take a moment on first run...
echo.
docker-compose -f docker-compose.vnc.yml up --build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo Error starting container!
    echo ========================================
    echo.
    echo Check the error messages above.
    echo Common issues:
    echo - Port 5901 already in use
    echo - Docker Desktop not running
    echo - Insufficient resources
    echo.
    echo To check if port is in use:
    echo   netstat -an ^| findstr 5901
    echo.
) else (
    echo.
    echo Container stopped.
)

pause
