@echo off
chcp 65001 >nul
echo ========================================
echo GameTimeLimiter 自动进程清理
echo ========================================
echo.

echo 正在自动清理残留进程和临时文件...
python cleanup_processes.py --auto --kill --clean-temp

echo.
echo 清理完成！
timeout /t 3 >nul 