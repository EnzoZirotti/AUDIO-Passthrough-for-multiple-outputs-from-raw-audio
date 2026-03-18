@echo off
REM Script to start Docker Desktop if it's not running

echo Checking Docker Desktop status...
echo.

REM Check if Docker Desktop is already running
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Docker Desktop is already running!
    pause
    exit /b 0
)

echo Docker Desktop is not running.
echo Attempting to start Docker Desktop...
echo.

REM Try common Docker Desktop installation paths
set DOCKER_PATHS[0]="C:\Program Files\Docker\Docker\Docker Desktop.exe"
set DOCKER_PATHS[1]="C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"
set DOCKER_PATHS[2]="%LOCALAPPDATA%\Docker\Docker Desktop.exe"

REM Try to start Docker Desktop
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Docker Desktop is starting...
    echo Please wait for it to fully start (check the system tray for the whale icon).
    echo This may take 30-60 seconds.
    echo.
    echo Once Docker Desktop is running, you can run docker-build.bat
) else if exist "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe" (
    start "" "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"
    echo Docker Desktop is starting...
    echo Please wait for it to fully start (check the system tray for the whale icon).
    echo This may take 30-60 seconds.
    echo.
    echo Once Docker Desktop is running, you can run docker-build.bat
) else (
    echo Could not find Docker Desktop installation.
    echo.
    echo Please:
    echo 1. Install Docker Desktop from: https://www.docker.com/products/docker-desktop
    echo 2. Or manually start Docker Desktop from the Start menu
    echo 3. Then run docker-build.bat
)

pause
