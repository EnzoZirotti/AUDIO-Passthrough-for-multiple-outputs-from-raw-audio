@echo off
REM Create a ZIP file of the distribution for easy sharing
echo ========================================
echo Creating Distribution ZIP
echo ========================================
echo.

if not exist "dist\BluetoothStreamer" (
    echo ERROR: Distribution not found!
    echo Please run build_distribution.bat first
    pause
    exit /b 1
)

echo Creating ZIP file...
cd dist
powershell -Command "Compress-Archive -Path BluetoothStreamer -DestinationPath ..\BluetoothStreamer-v1.0.0-Windows.zip -Force"
cd ..

if exist "BluetoothStreamer-v1.0.0-Windows.zip" (
    echo.
    echo ========================================
    echo ZIP file created successfully!
    echo ========================================
    echo.
    echo File: BluetoothStreamer-v1.0.0-Windows.zip
    echo Size: 
    dir "BluetoothStreamer-v1.0.0-Windows.zip" | find "BluetoothStreamer"
    echo.
    echo You can now share this ZIP file with others!
) else (
    echo ERROR: Failed to create ZIP file
    echo Make sure PowerShell is available
)

pause

