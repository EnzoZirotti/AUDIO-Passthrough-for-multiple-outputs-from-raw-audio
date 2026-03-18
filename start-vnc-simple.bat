@echo off
REM Simple VNC startup script with better error handling

echo ========================================
echo Starting Audio Sync GUI with VNC
echo ========================================
echo.

REM Check Docker
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Desktop is not running!
    pause
    exit /b 1
)

REM Stop any existing container
echo Stopping any existing containers...
docker-compose -f docker-compose.vnc.yml down 2>nul

echo.
echo Building and starting container...
echo This will take a few minutes on first run...
echo.

REM Build and start
docker-compose -f docker-compose.vnc.yml up --build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start container!
    echo Check the error messages above.
    pause
    exit /b 1
)
