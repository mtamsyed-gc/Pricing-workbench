@echo off
rem Pricing Workbench laptop acceptance (SPEC 13). Runs on the GC laptop with the pinned Python 3.12, from the
rem unzipped release (or check bundle): this file sits beside the pricing-workbench-<version> folder.
setlocal
set "PWDIR="
for /d %%D in ("%~dp0pricing-workbench-*") do set "PWDIR=%%~fD"
if not defined PWDIR (
  echo No pricing-workbench-^<version^> folder next to this file. Unzip the whole release first.
  pause
  exit /b 1
)
cd /d "%PWDIR%"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 not found via the py launcher. Install the pinned runtime ^(requirements-native.txt^) first.
  pause
  exit /b 1
)
echo Laptop check running. Results appear below as they are found; the test suite step takes 10 to 25 minutes.
echo Leave Excel alone while it runs. Double-click this file only once.
echo.
py -3.12 tools\laptop_check.py --console "%~dp0laptop_check_console.txt"
set RC=%ERRORLEVEL%
echo.
echo Exit code %RC%. Send the LAPTOP CHECK line (or laptop_check_console.txt) back to the session.
pause
