from __future__ import annotations

import csv
import io
import subprocess
import time
from functools import lru_cache

_NAMES_CACHE: tuple[float, set[str]] | None = None
_CACHE_SEC = 2.5


def running_image_names() -> set[str]:
    global _NAMES_CACHE
    now = time.monotonic()
    if _NAMES_CACHE and now - _NAMES_CACHE[0] < _CACHE_SEC:
        return _NAMES_CACHE[1]
    try:
        raw = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
        )
    except Exception:
        names: set[str] = set()
    else:
        names = set()
        for row in csv.reader(io.StringIO(raw)):
            if row:
                names.add(row[0].strip().lower())
    _NAMES_CACHE = (now, names)
    return names


def classic_outlook_running() -> bool:
    return "outlook.exe" in running_image_names()


def new_outlook_running() -> bool:
    return "olk.exe" in running_image_names()


@lru_cache(maxsize=1)
def classic_outlook_installed() -> bool:
    import winreg

    paths = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE",
    )
    for path in paths:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path):
                return True
        except OSError:
            continue
    return False
