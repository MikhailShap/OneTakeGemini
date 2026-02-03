@echo off
echo Building OneTake...
cd /d "%~dp0"

REM Check if icon.png exists
if not exist "icon.png" (
    echo ERROR: icon.png not found! Please save the icon as icon.png in this folder.
    pause
    exit /b 1
)

REM Convert PNG to ICO
echo Converting icon...
.\venv\Scripts\python.exe convert_icon.py icon.png icon.ico
if errorlevel 1 (
    echo ERROR: Failed to convert icon
    pause
    exit /b 1
)

REM Build with PyInstaller
echo Building executable...
.\venv\Scripts\pyinstaller.exe --clean OneTake.spec
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo Build complete! Executable is in dist\OneTake.exe
pause
