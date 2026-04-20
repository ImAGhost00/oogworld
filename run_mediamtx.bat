@echo off
REM MediaMTX startup script for Windows with C922 webcam
REM Prerequisites: Download mediamtx.exe from https://github.com/bluenviron/mediamtx/releases
REM               Place in same directory as this script

echo Starting MediaMTX for OogWorld terrarium...
echo.
echo Config: mediamtx.yml
echo Stream available at:
echo   - RTSP: rtsp://localhost:8554/oogway
echo   - HLS:  http://localhost:8888/oogway
echo   - WebRTC: http://localhost:8889/oogway
echo.
echo To connect from server, use your Windows IP instead of localhost:
echo   http://YOUR_LOCAL_IP:8889/oogway
echo.
echo Press Ctrl+C to stop.
echo.

if not exist mediamtx.exe (
    echo ERROR: mediamtx.exe not found in current directory.
    echo Download from: https://github.com/bluenviron/mediamtx/releases
    pause
    exit /b 1
)

mediamtx.exe

pause
