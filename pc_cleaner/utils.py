"""Shared helpers: admin checks, sizes, PowerShell runner."""

import ctypes
import os
import subprocess
import sys


def is_windows():
    return os.name == "nt"


def is_admin():
    """True if the process is running with administrator rights."""
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Relaunch this program elevated (Windows only)."""
    if not is_windows():
        return
    exe = sys.executable
    params = " ".join('"%s"' % a for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params or None, None, 1)


def human_size(num_bytes):
    """Format bytes as a human readable string."""
    try:
        num = float(num_bytes)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0 or unit == "TB":
            if unit == "B":
                return "%d %s" % (num, unit)
            return "%.1f %s" % (num, unit)
        num /= 1024.0
    return "%.1f TB" % num


def run_powershell(script, timeout=600):
    """Run a PowerShell script, return CompletedProcess (stdout/stderr as text)."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )


def expand(path):
    """Expand env vars and normalize a Windows path."""
    return os.path.normpath(os.path.expandvars(path))


def safe_startswith(path, roots):
    """True if path is inside one of the whitelisted root directories."""
    p = os.path.normcase(os.path.abspath(path))
    for root in roots:
        r = os.path.normcase(os.path.abspath(root))
        if p == r or p.startswith(r + os.sep):
            return True
    return False
