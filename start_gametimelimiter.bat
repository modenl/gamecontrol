@echo off
echo Starting GameTimeLimiter...

REM Set working directory to script location
cd /d "%~dp0"

REM Clean up any temporary PyInstaller files
echo Cleaning temporary files...
for /d %%d in ("%TEMP%\_MEI*") do rmdir /s /q "%%d" 2>nul
for /d %%d in ("%LOCALAPPDATA%\Temp\_MEI*") do rmdir /s /q "%%d" 2>nul

REM Start the application
echo Starting application...
if exist "GameTimeLimiter.exe" (
    start "" "GameTimeLimiter.exe"
) else if exist "dist\GameTimeLimiter.exe" (
    start "" "dist\GameTimeLimiter.exe"
) else if exist "dist\GameTimeLimiter\GameTimeLimiter.exe" (
    start "" "dist\GameTimeLimiter\GameTimeLimiter.exe"
) else (
    echo Error: GameTimeLimiter.exe not found
    pause
    exit /b 1
)

echo Application started
