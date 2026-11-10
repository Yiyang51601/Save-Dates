"""Windows logon autostart for Save Dates.

Startup is off unless the user turns it on. Turning it off deletes only this
app's Run values, Startup-folder shortcuts, and scheduled tasks. Nothing here
recreates an entry while the setting is off.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

OUR_RUN_NAMES = frozenset({"save dates", "savedates"})
OUR_SHORTCUT_STEMS = frozenset({"save dates", "savedates"})
TASK_NAMES = ("Save Dates", "SaveDates")
RUN_VALUE_NAME = "Save Dates"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_KEY_WOW = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
_APPROVED_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
_APPROVED_STARTUP = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def launch_command() -> str:
    """Command used only after the user opts in."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    from save_dates.config import app_dir

    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    exe = pythonw if pythonw.is_file() else python
    root = str(app_dir())
    code = f"import sys; sys.path.insert(0, {root!r}); import save_dates.__main__"
    return f'"{exe}" -c "{code}"'


def is_our_run_value(name: str, data: str) -> bool:
    if (name or "").strip().casefold() in OUR_RUN_NAMES:
        return True
    text = (data or "").casefold()
    return "savedates.exe" in text or "-m save_dates" in text or "save_dates.__main__" in text


def is_our_shortcut(name: str, target: str, arguments: str = "") -> bool:
    if Path(name).stem.casefold() in OUR_SHORTCUT_STEMS:
        return True
    if Path(target or "").name.casefold() == "savedates.exe":
        return True
    blob = f"{target or ''} {arguments or ''}".casefold()
    return "-m save_dates" in blob or "save_dates.__main__" in blob


def is_our_task(name: str) -> bool:
    return (name or "").strip().casefold() in OUR_RUN_NAMES


def approved_name_is_ours(name: str) -> bool:
    text = (name or "").strip()
    if text.casefold() in OUR_RUN_NAMES:
        return True
    return Path(text).stem.casefold() in OUR_SHORTCUT_STEMS


def approved_disabled(blob: bytes | None) -> bool:
    # StartupApproved: first byte 3 means the user disabled the entry.
    return bool(blob) and blob[0] == 3


def windows_turned_off(
    approved: dict[str, bytes],
    hkcu_run: dict[str, str],
    shortcuts: dict[str, tuple[str, str]],
) -> bool:
    """True when Windows Settings disabled an entry that is still installed."""
    for name, data in hkcu_run.items():
        if is_our_run_value(name, data) and approved_disabled(approved.get(name)):
            return True
    for path, (target, args) in shortcuts.items():
        filename = Path(path).name
        if is_our_shortcut(filename, target, args) and approved_disabled(approved.get(filename)):
            return True
    return False


def startup_directories() -> list[Path]:
    folders: list[Path] = []
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("ProgramData", "")
    if appdata:
        folders.append(Path(appdata) / "Microsoft/Windows/Start Menu/Programs/Startup")
    if programdata:
        folders.append(Path(programdata) / "Microsoft/Windows/Start Menu/Programs/Startup")
    return folders


def path_in_startup_folder(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for folder in startup_directories():
        try:
            resolved.relative_to(folder.resolve())
        except (OSError, ValueError):
            continue
        return True
    return False


def plan_autostart(
    *,
    enabled: bool,
    command: str,
    hkcu_run: dict[str, str],
    other_run: list[dict[str, str]],
    approved: dict[str, bytes],
    shortcuts: dict[str, tuple[str, str]],
    tasks: set[str],
    rewrite: bool = False,
) -> dict:
    """Return the startup state to keep. Does not touch the machine.

    A launch never creates an entry. ``rewrite=True`` is the explicit opt-in
    (settings checkbox or tray menu) and is the only path that adds one.
    An existing entry is not rewritten on later launches.
    """
    want = enabled is True
    hkcu = dict(hkcu_run)
    if want and not rewrite and windows_turned_off(approved, hkcu, shortcuts):
        want = False

    other = [dict(item) for item in other_run if not is_our_run_value(item.get("name", ""), item.get("data", ""))]
    kept_shortcuts = {
        path: spec
        for path, spec in shortcuts.items()
        if not is_our_shortcut(Path(path).name, spec[0], spec[1])
    }
    kept_tasks = {name for name in tasks if not is_our_task(name)}
    approved_delete: list[str] = []

    unrelated = {name: data for name, data in hkcu.items() if not is_our_run_value(name, data)}
    ours = {name: data for name, data in hkcu.items() if is_our_run_value(name, data)}
    wrote = False
    if not want:
        approved_delete.extend(ours)
        hkcu_out = unrelated
    elif rewrite:
        hkcu_out = dict(unrelated)
        hkcu_out[RUN_VALUE_NAME] = command
        wrote = ours.get(RUN_VALUE_NAME) != command
        approved_delete.append(RUN_VALUE_NAME)
        approved_delete.extend(name for name in ours if name != RUN_VALUE_NAME)
    elif ours:
        keep_name = RUN_VALUE_NAME if RUN_VALUE_NAME in ours else next(iter(ours))
        hkcu_out = dict(unrelated)
        hkcu_out[keep_name] = ours[keep_name]
        approved_delete.extend(name for name in ours if name != keep_name)
    else:
        # Setting still says on, but the entry is gone. Do not put it back.
        want = False
        hkcu_out = unrelated

    for path, spec in shortcuts.items():
        filename = Path(path).name
        if is_our_shortcut(filename, spec[0], spec[1]):
            approved_delete.append(filename)
    for item in other_run:
        if is_our_run_value(item.get("name", ""), item.get("data", "")):
            approved_delete.append(item.get("name", ""))

    seen: set[str] = set()
    unique_approved: list[str] = []
    for name in approved_delete:
        if name and name not in seen and approved_name_is_ours(name):
            seen.add(name)
            unique_approved.append(name)

    return {
        "enabled": want,
        "hkcu_run": hkcu_out,
        "other_run": other,
        "shortcuts": kept_shortcuts,
        "tasks": kept_tasks,
        "approved_delete": unique_approved,
        "wrote": wrote,
    }


def diff_operations(before: dict, after: dict) -> list[tuple]:
    """OS changes that move ``before`` toward ``after``.

    Unrelated Run values, shortcuts, and tasks are never included, even if
    ``after`` dropped them.
    """
    ops: list[tuple] = []
    before_hkcu = before.get("hkcu_run") or {}
    after_hkcu = after.get("hkcu_run") or {}
    for name, data in before_hkcu.items():
        if name not in after_hkcu and is_our_run_value(name, data):
            ops.append(("delete_hkcu", name))
    for name, value in after_hkcu.items():
        if before_hkcu.get(name) == value:
            continue
        if name == RUN_VALUE_NAME and is_our_run_value(name, value):
            ops.append(("set_hkcu", name, value))
    before_other = {(item.get("id"), item.get("name")): item for item in before.get("other_run") or []}
    after_other = {(item.get("id"), item.get("name")) for item in after.get("other_run") or []}
    for key, item in before_other.items():
        if key in after_other:
            continue
        if is_our_run_value(item.get("name", ""), item.get("data", "")):
            ops.append(("delete_other", item.get("id", ""), item.get("name", "")))
    before_shortcuts = before.get("shortcuts") or {}
    after_shortcuts = after.get("shortcuts") or {}
    for path, spec in before_shortcuts.items():
        if path in after_shortcuts:
            continue
        target, args = spec[0], spec[1]
        if is_our_shortcut(Path(path).name, target, args):
            ops.append(("delete_shortcut", path, target, args))
    for name in before.get("tasks") or ():
        if name in (after.get("tasks") or ()):
            continue
        if is_our_task(name):
            ops.append(("delete_task", name))
    for name in after.get("approved_delete") or []:
        if approved_name_is_ours(name):
            ops.append(("delete_approved", name))
    return ops


def reconcile_installed_autostart(enabled: bool, *, rewrite: bool = False) -> bool:
    """Make installed entries match ``enabled``. Only an explicit rewrite adds one."""
    if sys.platform != "win32":
        return False
    before = load_snapshot()
    after = plan_autostart(
        enabled=enabled is True,
        command=launch_command(),
        hkcu_run=before["hkcu_run"],
        other_run=before["other_run"],
        approved=before["approved"],
        shortcuts=before["shortcuts"],
        tasks=before["tasks"],
        rewrite=rewrite is True,
    )
    commit_snapshot(before, after)
    if after["wrote"]:
        logging.info("Added Windows startup entry %s", RUN_VALUE_NAME)
    elif not after["enabled"]:
        removed = [op for op in diff_operations(before, after) if op[0] != "set_hkcu"]
        if removed:
            logging.info("Removed Windows startup entries: %s", removed)
    return bool(after["enabled"])


def load_snapshot() -> dict:
    hkcu = _read_sz(_HKCU(), _RUN_KEY)
    other: list[dict[str, str]] = []
    for ident, root, subkey in (
        ("HKLM", _HKLM(), _RUN_KEY),
        ("HKLM_WOW", _HKLM(), _RUN_KEY_WOW),
    ):
        for name, data in _read_sz(root, subkey).items():
            other.append({"id": ident, "name": name, "data": data})
    approved = _read_binary(_HKCU(), _APPROVED_RUN)
    for name, blob in _read_binary(_HKCU(), _APPROVED_STARTUP).items():
        approved.setdefault(name, blob)
    return {
        "hkcu_run": hkcu,
        "other_run": other,
        "approved": approved,
        "shortcuts": _read_shortcuts(),
        "tasks": {name for name in TASK_NAMES if _task_exists(name)},
    }


def commit_snapshot(before: dict, after: dict) -> None:
    for op in diff_operations(before, after):
        kind = op[0]
        try:
            if kind == "delete_hkcu":
                _delete_value(_HKCU(), _RUN_KEY, op[1])
            elif kind == "set_hkcu":
                _set_hkcu_run(op[2])
            elif kind == "delete_other":
                root, subkey = _other_root(op[1])
                if root is not None:
                    _delete_value(root, subkey, op[2])
            elif kind == "delete_shortcut":
                remove_startup_shortcut(Path(op[1]), op[2], op[3])
            elif kind == "delete_task":
                _delete_task(op[1])
            elif kind == "delete_approved":
                _delete_value(_HKCU(), _APPROVED_RUN, op[1])
                _delete_value(_HKCU(), _APPROVED_STARTUP, op[1])
        except OSError:
            logging.exception("Could not apply startup change %s", op)


def remove_startup_shortcut(path: Path, target: str, arguments: str) -> bool:
    if not is_our_shortcut(path.name, target, arguments):
        return False
    if not path_in_startup_folder(path):
        return False
    path.unlink(missing_ok=True)
    return True


def _HKCU():
    import winreg

    return winreg.HKEY_CURRENT_USER


def _HKLM():
    import winreg

    return winreg.HKEY_LOCAL_MACHINE


def _other_root(ident: str):
    if ident == "HKLM":
        return _HKLM(), _RUN_KEY
    if ident == "HKLM_WOW":
        return _HKLM(), _RUN_KEY_WOW
    return None, ""


def _read_values(root, subkey: str) -> list[tuple[str, object]]:
    import winreg

    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            count = winreg.QueryInfoKey(key)[1]
            values = []
            for index in range(count):
                values.append(winreg.EnumValue(key, index))
            return values
    except OSError:
        return []


def _read_sz(root, subkey: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for name, data, _typ in _read_values(root, subkey):
        if isinstance(data, str):
            found[str(name)] = data
    return found


def _read_binary(root, subkey: str) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for name, data, _typ in _read_values(root, subkey):
        if isinstance(data, bytes):
            found[str(name)] = data
    return found


def _delete_value(root, subkey: str, name: str) -> None:
    import winreg

    if not name:
        return
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        return
    except OSError:
        logging.info("Startup value could not be deleted: %s %s", subkey, name)


def _set_hkcu_run(command: str) -> None:
    import winreg

    if not is_our_run_value(RUN_VALUE_NAME, command):
        return
    with winreg.OpenKey(_HKCU(), _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)


def _read_shortcuts() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for folder in startup_directories():
        if not folder.is_dir():
            continue
        for path in folder.glob("*.lnk"):
            found[str(path)] = _read_shortcut(path)
    return found


def _read_shortcut(path: Path) -> tuple[str, str]:
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortcut(str(path))
        return str(link.TargetPath or ""), str(link.Arguments or "")
    except Exception:
        logging.info("Could not read startup shortcut %s", path)
        return "", ""


def _task_exists(name: str) -> bool:
    if not is_our_task(name):
        return False
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", name],
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _delete_task(name: str) -> None:
    if not is_our_task(name):
        return
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", name, "/F"],
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        logging.info("Could not delete scheduled task %s", name)
