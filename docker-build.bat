@echo off
REM Docker build script for Audio Sync GUI (Windows)

echo Building Audio Sync GUI Docker image...
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
            echo Docker Desktop is now running! Continuing with build...
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
            echo Docker Desktop is now running! Continuing with build...
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

REM Build the image
docker build -t audio-sync-gui:latest .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful!
    echo You can now run the container using:
    echo   docker-compose up
    echo   or
    echo   docker-run.bat
) else (
    echo.
    echo Build failed. Please check the error messages above.
)

pause
