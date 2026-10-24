@echo off
rem Pricing Workbench laptop acceptance (SPEC 13). Runs on the GC work laptop with the pinned Python 3.12.
setlocal
cd /d "%~dp0pricing-workbench-0.1.0-ws0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 not found via the py launcher. Install the pinned runtime ^(requirements-native.txt^) first.
  pause
  exit /b 1
)
py -3.12 tools\laptop_check.py > "%~dp0laptop_check_console.txt" 2>&1
set RC=%ERRORLEVEL%
type "%~dp0laptop_check_console.txt"
echo.
echo Exit code %RC%. Send the LAPTOP CHECK line (or laptop_check_console.txt) back to the session.
pause
