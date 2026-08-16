"""Minimal application logger.

The goal is a clean terminal: no per-request HTTP access log spam, only the
events a user actually cares about (startup, automatic saves, imports,
exports, important errors, shutdown). Werkzeug's own access logger is
silenced in app.py; this module is the single place that prints anything to
stdout so the format stays consistent.
"""
from datetime import datetime

_LEVELS = {"info": "INFO", "warn": "WARN", "error": "ERROR"}


def _emit(level: str, message: str):
    ts = datetime.now().strftime("%H:%M:%S")
    tag = _LEVELS.get(level, "INFO")
    print(f"[{ts}] {tag:<5} {message}", flush=True)


def info(message: str):
    _emit("info", message)


def warn(message: str):
    _emit("warn", message)


def error(message: str):
    _emit("error", message)


def startup_banner(url: str):
    line = "=" * (len(url) + 22)
    print(line, flush=True)
    print(f"  MyBacklog is running at {url}", flush=True)
    print(line, flush=True)
    print("  Press Ctrl+C to stop.", flush=True)


def shutdown():
    _emit("info", "Application shutdown.")
