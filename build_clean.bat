@echo off
chcp 65001 >nul
echo ========================================
echo GameTimeLimiter Build with Cleanup
echo ========================================
echo.

echo Step 1: Cleaning up build environment...
python cleanup_build.py
if errorlevel 1 (
    echo.
    echo ❌ Cleanup failed. Please check the output above.
    echo.
    pause
    exit /b 1
)

echo.
echo Step 2: Building application...
python build.py %*
if errorlevel 1 (
    echo.
    echo ❌ Build failed. Please check the output above.
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ Build completed successfully!
echo.
pause 