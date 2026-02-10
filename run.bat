@echo off
echo Starting Mouse Movement Recorder...
echo.
python recorder.py
if errorlevel 1 (
    echo.
    echo ERROR: Python not found or script failed.
    echo.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
)