@echo off
setlocal enabledelayedexpansion
REM Starts MyBacklog on Windows: verifies Python is available and new
REM enough, creates a virtual environment if needed, installs dependencies
REM (falling back to unpinned "latest compatible" versions if the exact
REM pins in requirements.txt don't have a wheel for this Python yet -- the
REM exact situation a brand-new Python release can hit before packages
REM have caught up), then starts the app and opens your browser.
cd /d "%~dp0"

set MIN_MAJOR=3
set MIN_MINOR=10

echo MyBacklog - startup check
echo ==========================

REM ---------------------------------------------------------------- 1. Find Python
set PYTHON_BIN=
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 --version >nul 2>&1
    if !errorlevel!==0 set PYTHON_BIN=py -3
)
if "!PYTHON_BIN!"=="" (
    where python >nul 2>&1
    if !errorlevel!==0 set PYTHON_BIN=python
)

if "!PYTHON_BIN!"=="" (
    echo.
    echo ERROR: No Python installation found.
    echo Install Python %MIN_MAJOR%.%MIN_MINOR% or newer from https://www.python.org/downloads/
    echo During setup, tick "Add python.exe to PATH", then run this script again.
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------- 2. Check version
for /f "delims=" %%v in ('!PYTHON_BIN! -c "import platform;print(platform.python_version())"') do set FOUND_VERSION=%%v
for /f "delims=" %%v in ('!PYTHON_BIN! -c "import sys;print(1 if sys.version_info[:2] >= (%MIN_MAJOR%, %MIN_MINOR%) else 0)"') do set VERSION_OK=%%v

echo Found Python !FOUND_VERSION! (!PYTHON_BIN!)

if not "!VERSION_OK!"=="1" (
    echo.
    echo ERROR: MyBacklog needs Python %MIN_MAJOR%.%MIN_MINOR% or newer -- found !FOUND_VERSION!.
    echo Install a newer Python from https://www.python.org/downloads/ and try again.
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------- 3. Virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    !PYTHON_BIN! -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Couldn't create the virtual environment.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo ERROR: Couldn't activate the virtual environment.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------- 4. Keep pip itself current
REM An outdated pip is a common, confusing cause of "no matching distribution
REM found" on a Python version newer than the pinned packages expected --
REM pip's own wheel-resolution logic improves with each release.
echo Checking pip...
python -m pip install --quiet --upgrade pip

REM ---------------------------------------------------------------- 5. Install dependencies
echo Installing dependencies...
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo The pinned dependency versions failed to install ^(this usually means
    echo your Python version is newer than what those exact versions support^).
    echo Retrying with the latest compatible versions instead...
    for /f "delims=" %%r in ('python scripts\list_requirement_names.py') do set "FALLBACK_REQS=%%r"
    python -m pip install --quiet --upgrade !FALLBACK_REQS!
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency installation failed even without version pins.
        echo Please check your internet connection and Python installation, or
        echo open an issue with the error output above.
        echo.
        pause
        exit /b 1
    )
    echo Installed the latest compatible versions instead of the pinned ones.
) else (
    echo Dependencies installed.
)

REM ---------------------------------------------------------------- 6. Launch
echo.
echo Starting MyBacklog...
python app.py
pause
