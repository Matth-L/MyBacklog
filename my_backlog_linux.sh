#!/usr/bin/env bash
# Starts MyBacklog on Linux/macOS: verifies Python is available and new
# enough, creates a virtual environment if needed, installs dependencies
# (falling back to unpinned "latest compatible" versions if the exact pins
# in requirements.txt don't have a wheel for this Python yet — the exact
# situation a brand-new Python release can hit before packages have caught
# up), then starts the app and opens your browser.
set -u
cd "$(dirname "$0")"

MIN_MAJOR=3
MIN_MINOR=10

echo "MyBacklog — startup check"
echo "=========================="

# ---------------------------------------------------------------- 1. Find Python
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
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  if ! "$PYTHON_BIN" -m venv .venv; then
    echo
    echo "ERROR: Couldn't create the virtual environment."
    echo "On some Linux distros you may need to install the venv module first, e.g.:"
    echo "  sudo apt install python3-venv"
    exit 1
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# ---------------------------------------------------------------- 4. Keep pip itself current
# An outdated pip is a common, confusing cause of "no matching distribution
# found" on a Python version newer than the pinned packages expected — pip's
# own wheel-resolution logic improves with each release.
echo "Checking pip..."
python -m pip install --quiet --upgrade pip

# ---------------------------------------------------------------- 5. Install dependencies
echo "Installing dependencies..."
if python -m pip install --quiet -r requirements.txt; then
  echo "Dependencies installed."
else
  echo
  echo "The pinned dependency versions failed to install (this usually means"
  echo "your Python version is newer than what those exact versions support)."
  echo "Retrying with the latest compatible versions instead..."
  FALLBACK_REQS=$(python scripts/list_requirement_names.py)
  if python -m pip install --quiet --upgrade $FALLBACK_REQS; then
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
python app.py
