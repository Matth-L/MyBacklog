"""Prints the bare package names from requirements.txt (one line, space
separated), stripping version pins — e.g. "Flask==3.1.3" -> "Flask".

Used by my_backlog_linux.sh / my_backlog_windows.bat as a fallback: if
installing the exact pinned versions fails (typically because a very new
Python release doesn't have wheels for them yet), the scripts reinstall
using just these bare names so pip picks the latest compatible version
instead. Kept as a real script rather than an inline one-liner embedded in
the shell/batch files, since embedding Python source with its own quotes
inside a shell command string (especially in cmd.exe's `for /f ('...')`
syntax) is a well-known source of quoting bugs.
"""
import re
from pathlib import Path

req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
names = []
for line in req_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#"):
        names.append(re.split(r"[=<>~]", line, 1)[0])
print(" ".join(names))
