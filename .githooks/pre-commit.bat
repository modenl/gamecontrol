@echo off
REM Pre-commit hook to enforce AI Development Guidelines

echo 🔍 Checking AI Development Guidelines compliance...

REM Get staged files
for /f "delims=" %%i in ('git diff --cached --name-only') do (
    call :check_file "%%i"
)

if "%VIOLATIONS_FOUND%"=="true" (
    echo.
    echo 🚫 Commit blocked due to AI Development Guidelines violations!
    echo.
    echo 📋 Alternatives:
    echo    • Instead of test_fix_*.py → Add to existing test files
    echo    • Instead of fix_*.py → Add self-repair logic to core modules
    echo    • Instead of *_FIX.md → Update README.md or existing docs
    echo.
    echo 📖 Read AI_DEVELOPMENT_GUIDELINES.md for complete rules
    exit /b 1
)

echo ✅ All files comply with AI Development Guidelines
exit /b 0

:check_file
set "file=%~1"
for %%f in ("%file%") do set "filename=%%~nxf"

REM Check forbidden patterns
echo %filename% | findstr /i "test_fix_" >nul && call :violation "%file%" "test_fix_*.py"
echo %filename% | findstr /i "test_debug_" >nul && call :violation "%file%" "test_debug_*.py"
echo %filename% | findstr /i "temp_test_" >nul && call :violation "%file%" "temp_test_*.py"
echo %filename% | findstr /i "test_temp_" >nul && call :violation "%file%" "test_temp_*.py"
echo %filename% | findstr /i "^fix_" >nul && call :violation "%file%" "fix_*.py"
echo %filename% | findstr /i "cleanup_" >nul && call :violation "%file%" "cleanup_*.py"
echo %filename% | findstr /i "repair_" >nul && call :violation "%file%" "repair_*.py"
echo %filename% | findstr /i "patch_" >nul && call :violation "%file%" "patch_*.py"
echo %filename% | findstr /i "debug_" >nul && call :violation "%file%" "debug_*.py"
echo %filename% | findstr /i "check_" >nul && call :violation "%file%" "check_*.py"
echo %filename% | findstr /i "diagnose_" >nul && call :violation "%file%" "diagnose_*.py"
echo %filename% | findstr /i "_FIX\.md$" >nul && call :violation "%file%" "*_FIX.md"
echo %filename% | findstr /i "_SOLUTION\.md$" >nul && call :violation "%file%" "*_SOLUTION.md"
echo %filename% | findstr /i "^TEMP_.*\.md$" >nul && call :violation "%file%" "TEMP_*.md"
echo %filename% | findstr /i "^DEBUG_.*\.md$" >nul && call :violation "%file%" "DEBUG_*.md"
goto :eof

:violation
echo ❌ VIOLATION: File '%~1' violates AI Development Guidelines
echo    Pattern '%~2' is forbidden
echo    See AI_DEVELOPMENT_GUIDELINES.md for alternatives
set "VIOLATIONS_FOUND=true"
goto :eof 