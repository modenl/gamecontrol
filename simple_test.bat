@echo off
echo Simple test script starting...
cd /d "C:\Users\moden\work\gamecontrol\dist"
echo Current directory: %CD%
echo Clearing environment variables...
set "_MEIPASS="
set "_MEIPASS2="
echo Starting application...
"C:\Users\moden\work\gamecontrol\dist\GameTimeLimiter.exe"
echo Done.
pause 