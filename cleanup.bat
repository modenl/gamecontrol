@echo off
chcp 65001 >nul
echo ========================================
echo GameTimeLimiter 进程清理工具
echo ========================================
echo.

echo 正在检查残留进程...
python cleanup_processes.py

echo.
echo 按任意键退出...
pause >nul 