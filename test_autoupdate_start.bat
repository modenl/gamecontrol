@echo off
echo Testing auto-updater startup simulation...

set "CURRENT_DIR=%~dp0dist"
set "CURRENT_EXE=%CURRENT_DIR%\GameTimeLimiter.exe"
set "LOG_FILE=%CURRENT_DIR%\test_startup.log"

echo Test started at %DATE% %TIME% > "%LOG_FILE%"
echo Current directory: %CD% >> "%LOG_FILE%"
echo Target directory: %CURRENT_DIR% >> "%LOG_FILE%"
echo Target executable: %CURRENT_EXE% >> "%LOG_FILE%"

cd /d "%CURRENT_DIR%"
echo After cd: %CD% >> "%LOG_FILE%"

REM Create wrapper script
set "WRAPPER_SCRIPT=%TEMP%\test_gamecontrol_%RANDOM%.bat"
echo Creating wrapper at: %WRAPPER_SCRIPT% >> "%LOG_FILE%"

echo @echo off > "%WRAPPER_SCRIPT%"
echo set "WRAPPER_LOG=%LOG_FILE%.wrapper" >> "%WRAPPER_SCRIPT%"
echo echo Wrapper script starting at %%DATE%% %%TIME%% ^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo echo Current directory before cd: %%CD%% ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo cd /d "%CURRENT_DIR%" >> "%WRAPPER_SCRIPT%"
echo echo Current directory after cd: %%CD%% ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo echo Starting executable: %CURRENT_EXE% ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo REM Clear PyInstaller environment variables that might interfere >> "%WRAPPER_SCRIPT%"
echo set "_MEIPASS=" >> "%WRAPPER_SCRIPT%"
echo set "_MEIPASS2=" >> "%WRAPPER_SCRIPT%"
echo echo Environment cleared ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo echo About to start application ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo "%CURRENT_EXE%" >> "%WRAPPER_SCRIPT%"
echo echo Application command executed ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo echo Application started, wrapper exiting ^>^> "%%WRAPPER_LOG%%" >> "%WRAPPER_SCRIPT%"
echo timeout /t 2 /nobreak ^>nul >> "%WRAPPER_SCRIPT%"
echo del /q "%%~f0" >> "%WRAPPER_SCRIPT%"

echo Starting application via wrapper script...
echo Wrapper script content: >> "%LOG_FILE%"
type "%WRAPPER_SCRIPT%" >> "%LOG_FILE%"
echo ========================================== >> "%LOG_FILE%"

start "" "%WRAPPER_SCRIPT%"

echo Test completed. Check logs:
echo - Main log: %LOG_FILE%
echo - Wrapper log: %LOG_FILE%.wrapper
pause 