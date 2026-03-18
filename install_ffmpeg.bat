@echo off
echo Installing ffmpeg for audio playback...
echo.
echo This will use winget (Windows Package Manager) to install ffmpeg.
echo If winget is not available, please download ffmpeg manually from:
echo https://ffmpeg.org/download.html
echo.
pause

winget install ffmpeg

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ffmpeg installed successfully!
    echo Please restart the GUI application.
) else (
    echo.
    echo Installation failed. Please install ffmpeg manually:
    echo 1. Download from: https://ffmpeg.org/download.html
    echo 2. Extract to a folder (e.g., C:\ffmpeg)
    echo 3. Add the bin folder to your PATH environment variable
    echo    (e.g., C:\ffmpeg\bin)
)

pause

