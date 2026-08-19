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
REM Checked by the activate script existing, not just the ".venv" folder: a
REM previous run can leave behind a .venv directory that exists but is
REM incomplete (interrupted install, disk full mid-creation, antivirus
REM blocking a file, etc.). Testing only "exist .venv" would trust that
REM stale, broken folder forever and fail on every future run trying to
REM call ".venv\Scripts\activate.bat" — recreate it instead if it's broken.
if exist ".venv\Scripts\activate.bat" (
    echo Using existing virtual environment.
) else (
    if exist ".venv" (
        echo Found an incomplete .venv from a previous run -- recreating it...
        rmdir /s /q ".venv"
    ) else (
        echo Creating virtual environment...
    )
    !PYTHON_BIN! -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Couldn't create the virtual environment.
        pause
        exit /b 1
    )
    if not exist ".venv\Scripts\activate.bat" (
        echo.
        echo ERROR: The virtual environment was created but looks incomplete
        echo ^(.venv\Scripts\activate.bat is missing^). Delete the .venv folder
        echo and run this script again.
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

REM Calling the venv's own interpreter by its full path from here on (rather
REM than relying on a bare "python" after activation) means every command
REM below is unambiguous no matter what "python" happens to resolve to on
REM this machine's PATH.
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

REM ---------------------------------------------------------------- 4. Keep pip itself current
REM An outdated pip is a common, confusing cause of "no matching distribution
REM found" on a Python version newer than the pinned packages expected --
REM pip's own wheel-resolution logic improves with each release.
echo Checking pip...
"%VENV_PY%" -m pip install --quiet --upgrade pip

REM ---------------------------------------------------------------- 5. Install dependencies
echo Installing dependencies...
"%VENV_PY%" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo The pinned dependency versions failed to install ^(this usually means
    echo your Python version is newer than what those exact versions support^).
    echo Retrying with the latest compatible versions instead...
    for /f "delims=" %%r in ('"%VENV_PY%" scripts\list_requirement_names.py') do set "FALLBACK_REQS=%%r"
    "%VENV_PY%" -m pip install --quiet --upgrade !FALLBACK_REQS!
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
"%VENV_PY%" app.py
pause
