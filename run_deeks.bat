@echo off
title Deeks Voice Assistant
echo Starting Deeks...
cd /d "%~dp0"

:: Activate the virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [Warning] Virtual environment not found. Running with global python.
)

:: Run the main script
python main.py

echo.
echo Deeks has stopped.
pause
