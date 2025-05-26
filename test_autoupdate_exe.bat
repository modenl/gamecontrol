@echo off
echo ========================================
echo 可执行文件自动更新测试脚本
echo ========================================
echo.

REM 检查可执行文件是否存在
if not exist "dist\GameTimeLimiter.exe" (
    echo ❌ 错误：找不到 dist\GameTimeLimiter.exe
    echo 请先运行 python build.py 构建可执行文件
    echo.
    pause
    exit /b 1
)

echo 当前可用的测试选项：
echo 1. 测试版本 1.0.1 （会触发更新到最新版本）
echo 2. 测试版本 1.0.5 （会触发更新到最新版本）
echo 3. 测试版本 1.0.10 （会触发更新到最新版本）
echo 4. 正常启动（当前版本）
echo.

set /p choice="请选择测试选项 (1-4): "

if "%choice%"=="1" (
    echo 🧪 启动测试模式：版本 1.0.1
    "dist\GameTimeLimiter.exe" --test-version=1.0.1
) else if "%choice%"=="2" (
    echo 🧪 启动测试模式：版本 1.0.5
    "dist\GameTimeLimiter.exe" --test-version=1.0.5
) else if "%choice%"=="3" (
    echo 🧪 启动测试模式：版本 1.0.10
    "dist\GameTimeLimiter.exe" --test-version=1.0.10
) else if "%choice%"=="4" (
    echo 🚀 正常启动
    "dist\GameTimeLimiter.exe"
) else (
    echo ❌ 无效选择，正常启动
    "dist\GameTimeLimiter.exe"
)

echo.
echo 测试完成，按任意键退出...
pause >nul 