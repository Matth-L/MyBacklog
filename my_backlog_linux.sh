#!/usr/bin/env bash
# Starts MyBacklog on Linux/macOS: verifies Python is available and new
# enough, creates a virtual environment if needed, installs dependencies
# (falling back to unpinned "latest compatible" versions if the exact pins
# in requirements.txt don't have a wheel for this Python yet — the exact
# situation a brand-new Python release can hit before packages have caught
# up), then starts the app and opens your browser.
set -eu
cd "$(dirname "$0")"

MIN_MAJOR=3
MIN_MINOR=10

echo "MyBacklog — startup check"
echo "=========================="

# ---------------------------------------------------------------- 1. Find Python
# Checks both names because which one exists varies by distro/OS: Debian,
# Ubuntu, and macOS (Homebrew) only ship "python3"; some other distros and
# most Windows-via-WSL setups also provide a plain "python". Everything
# below always goes through $PYTHON_BIN (never a bare "python"), so it
# works the same regardless of which one this machine happens to have.
PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo
  echo "ERROR: No Python installation found (looked for 'python3' and 'python')."
  echo "Install Python $MIN_MAJOR.$MIN_MINOR or newer from https://www.python.org/downloads/"
  echo "and make sure it's on your PATH, then run this script again."
  exit 1
fi

# ---------------------------------------------------------------- 2. Check version
VERSION_CHECK=$("$PYTHON_BIN" -c "
import sys
major, minor = sys.version_info[:2]
print(f'{major}.{minor}')
print(1 if (major, minor) >= ($MIN_MAJOR, $MIN_MINOR) else 0)
")
FOUND_VERSION=$(echo "$VERSION_CHECK" | head -1)
VERSION_OK=$(echo "$VERSION_CHECK" | tail -1)

echo "Found Python $FOUND_VERSION ($PYTHON_BIN)"

if [ "$VERSION_OK" != "1" ]; then
  echo
  echo "ERROR: MyBacklog needs Python $MIN_MAJOR.$MIN_MINOR or newer — found $FOUND_VERSION."
  echo "Install a newer Python from https://www.python.org/downloads/ and try again."
  exit 1
fi

# ---------------------------------------------------------------- 3. Virtual environment
# Checked by the activate *script* existing, not just the .venv directory:
# a previous run can leave behind a .venv folder that exists but is
# incomplete (interrupted install, missing the "python3-venv" system
# package on Debian/Ubuntu so "venv" silently produces a broken
# environment, disk full mid-creation, etc.). Testing only "-d .venv"
# would trust that stale, broken folder forever and fail on every future
# run with "No such file or directory" on activate — exactly the
# confusing error this is meant to prevent. If it's broken, wipe it and
# start clean instead.
if [ -f ".venv/bin/activate" ]; then
  echo "Using existing virtual environment."
else
  if [ -d ".venv" ]; then
    echo "Found an incomplete .venv from a previous run — recreating it..."
    rm -rf .venv
  else
    echo "Creating virtual environment..."
  fi
  if ! "$PYTHON_BIN" -m venv .venv; then
    echo
    echo "ERROR: Couldn't create the virtual environment."
    echo "On some Linux distros you may need to install the venv module first, e.g.:"
    echo "  sudo apt install python3-venv"
    exit 1
  fi
  if [ ! -f ".venv/bin/activate" ]; then
    echo
    echo "ERROR: The virtual environment was created but looks incomplete"
    echo "(.venv/bin/activate is missing). This usually also means the"
    echo "'python3-venv' system package isn't installed, e.g.:"
    echo "  sudo apt install python3-venv"
    echo "Delete the .venv folder and run this script again after installing it."
    exit 1
  fi
fi

# Calling the venv's own interpreter by its full path from here on (rather
# than relying on a bare "python"/"pip" after activation) means every
# command below is unambiguous regardless of whether this system's plain
# "python" points at Python 2, doesn't exist at all, or isn't on PATH the
# way the activated shell expects — the exact "python vs python3" mismatch
# that varies machine to machine. "source activate" is still run too, since
# it's harmless and also sets up the environment for anyone who continues
# working in this same terminal afterward.
VENV_PY="$(pwd)/.venv/bin/python"
# shellcheck disable=SC1091
source .venv/bin/activate

# ---------------------------------------------------------------- 4. Keep pip itself current
# An outdated pip is a common, confusing cause of "no matching distribution
# found" on a Python version newer than the pinned packages expected — pip's
# own wheel-resolution logic improves with each release.
echo "Checking pip..."
"$VENV_PY" -m pip install --quiet --upgrade pip

# ---------------------------------------------------------------- 5. Install dependencies
echo "Installing dependencies..."
if "$VENV_PY" -m pip install --quiet -r requirements.txt; then
  echo "Dependencies installed."
else
  echo
  echo "The pinned dependency versions failed to install (this usually means"
  echo "your Python version is newer than what those exact versions support)."
  echo "Retrying with the latest compatible versions instead..."
  FALLBACK_REQS=$("$VENV_PY" scripts/list_requirement_names.py)
  if "$VENV_PY" -m pip install --quiet --upgrade $FALLBACK_REQS; then
    echo "Installed the latest compatible versions instead of the pinned ones."
  else
    echo
    echo "ERROR: Dependency installation failed even without version pins."
    echo "Please check your internet connection and Python installation, or"
    echo "open an issue with the error output above."
    exit 1
  fi
fi

# ---------------------------------------------------------------- 6. Launch
echo
echo "Starting MyBacklog..."
"$VENV_PY" app.py
