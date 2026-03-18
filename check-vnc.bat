@echo off
REM Quick script to check if VNC container is running and accessible

echo Checking VNC container status...
echo.

docker ps | findstr audio-sync-gui-vnc >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Container is running
    echo.
    echo Checking port 5901...
    netstat -an | findstr ":5901" >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Port 5901 is listening
        echo.
        echo You can now connect with a VNC client to: localhost:5901
    ) else (
        echo [WARNING] Port 5901 not found in listening ports
        echo Container may still be starting...
    )
) else (
    echo [INFO] Container is not running
    echo.
    echo To start it, run: docker-run-vnc.bat
)

echo.
pause
