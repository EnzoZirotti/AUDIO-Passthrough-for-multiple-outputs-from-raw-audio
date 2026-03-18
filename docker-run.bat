@echo off
REM Docker run script for Audio Sync GUI (Windows)
REM This script simplifies running the Docker container on Windows

echo Audio Sync GUI - Docker Runner
echo.

REM Check if Docker is installed
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Docker is not installed. Please install Docker Desktop first.
    echo Download from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo ERROR: Docker Desktop is not running!
    echo ========================================
    echo.
    echo Would you like to start Docker Desktop now? (Y/N)
    set /p START_DOCKER=
    if /i "%START_DOCKER%"=="Y" (
        echo.
        echo Attempting to start Docker Desktop...
        if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
            start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
            echo Docker Desktop is starting...
            echo Please wait 30-60 seconds for it to fully start.
            echo Look for the whale icon in your system tray.
            echo.
            echo Press any key once Docker Desktop is running...
            pause >nul
            echo Checking Docker status...
            timeout /t 5 /nobreak >nul
            docker info >nul 2>&1
            if %ERRORLEVEL% NEQ 0 (
                echo Docker Desktop is still starting. Please wait a bit longer.
                echo You can run this script again once Docker Desktop is ready.
                pause
                exit /b 1
            )
            echo Docker Desktop is now running! Continuing...
            echo.
        ) else if exist "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe" (
            start "" "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"
            echo Docker Desktop is starting...
            echo Please wait 30-60 seconds for it to fully start.
            echo Look for the whale icon in your system tray.
            echo.
            echo Press any key once Docker Desktop is running...
            pause >nul
            echo Checking Docker status...
            timeout /t 5 /nobreak >nul
            docker info >nul 2>&1
            if %ERRORLEVEL% NEQ 0 (
                echo Docker Desktop is still starting. Please wait a bit longer.
                echo You can run this script again once Docker Desktop is ready.
                pause
                exit /b 1
            )
            echo Docker Desktop is now running! Continuing...
            echo.
        ) else (
            echo Could not find Docker Desktop installation.
            echo Please start Docker Desktop manually from the Start menu.
            echo Or run: start-docker.bat
            pause
            exit /b 1
        )
    ) else (
        echo.
        echo Please start Docker Desktop manually and run this script again.
        echo Or run: start-docker.bat
        pause
        exit /b 1
    )
)

echo Detected: Windows
echo.
echo ========================================
echo IMPORTANT: GUI Display on Windows
echo ========================================
echo.
echo Running GUI apps in Docker on Windows is complex.
echo You have two options:
echo.
echo Option 1: VNC (EASIEST - Recommended)
echo   Run: docker-run-vnc.bat
echo   Then connect with a VNC client to localhost:5901
echo.
echo Option 2: WSL2 + X11 Server (Advanced)
echo   1. Install WSL2 and VcXsrv X11 server
echo   2. Run Docker commands from WSL2
echo.
echo Option 3: Try direct run (may not show GUI)
echo   Continuing with docker-compose...
echo.
pause

REM Use docker-compose for easier setup
docker-compose up

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo Container failed to start or GUI not visible?
    echo ========================================
    echo.
    echo For Windows, the GUI likely won't display with this method.
    echo Please use: docker-run-vnc.bat instead!
    echo.
)

pause
