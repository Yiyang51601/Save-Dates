from __future__ import annotations

import json
from pathlib import Path

from save_dates.desktop import close_window_quits
from save_dates.windows_startup import (
    diff_operations,
    is_our_run_value,
    is_our_shortcut,
    plan_autostart,
    reconcile_installed_autostart,
    remove_startup_shortcut,
)

COMMAND = r'"F:\Save Dates\dist\SaveDates\SaveDates.exe"'
STARTUP = r"C:\Users\me\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"


def _plan(**overrides):
    base = {
        "enabled": False,
        "command": COMMAND,
        "hkcu_run": {},
        "other_run": [],
        "approved": {},
        "shortcuts": {},
        "tasks": set(),
        "rewrite": False,
    }
    base.update(overrides)
    return plan_autostart(**base)


def test_close_window_quits_instead_of_hiding():
    assert close_window_quits() is True
    text = Path("save_dates/desktop.py").read_text(encoding="utf-8")
    assert "window.hide()" not in text
    startup = Path("save_dates/windows_startup.py").read_text(encoding="utf-8")
    assert "schtasks" in startup
    assert "/Create" not in startup


def test_turning_off_removes_only_this_app_and_does_not_come_back():
    hkcu = {
        "OneDrive": r'"C:\Program Files\Microsoft OneDrive\OneDrive.exe"',
        "Save Dates": COMMAND,
        "SaveDates": COMMAND,
        "Grammarly": "Grammarly.exe",
        "SmartConnect": r'"C:\Program Files\Lenovo\Ready For Assistant\SmartConnect.exe" /startup',
    }
    other = [
        {"id": "HKLM", "name": "SecurityHealth", "data": r"C:\Windows\system32\SecurityHealthSystray.exe"},
        {"id": "HKLM", "name": "SaveDates", "data": COMMAND},
    ]
    shortcuts = {
        STARTUP + r"\safe - 快捷方式.lnk": (r"C:\huorong-m\safe.vbs", ""),
        STARTUP + r"\Save Dates.lnk": (COMMAND.strip('"'), ""),
        STARTUP + r"\Notes.lnk": (r"C:\Windows\notepad.exe", ""),
    }
    tasks = {"Save Dates", "SaveDates", "Office Feature Updates", "ScanForUpdates"}
    first = _plan(
        enabled=False,
        hkcu_run=hkcu,
        other_run=other,
        shortcuts=shortcuts,
        tasks=tasks,
    )
    assert first["wrote"] is False
    assert first["enabled"] is False
    assert "Save Dates" not in first["hkcu_run"]
    assert "SaveDates" not in first["hkcu_run"]
    assert "OneDrive" in first["hkcu_run"]
    assert "Grammarly" in first["hkcu_run"]
    assert "SmartConnect" in first["hkcu_run"]
    assert [item["name"] for item in first["other_run"]] == ["SecurityHealth"]
    assert list(first["shortcuts"]) == [
        STARTUP + r"\safe - 快捷方式.lnk",
        STARTUP + r"\Notes.lnk",
    ]
    assert first["tasks"] == {"Office Feature Updates", "ScanForUpdates"}

    second = _plan(enabled=False, hkcu_run=first["hkcu_run"], other_run=first["other_run"], shortcuts=first["shortcuts"], tasks=first["tasks"])
    assert second["wrote"] is False
    assert "Save Dates" not in second["hkcu_run"]
    assert second["hkcu_run"]["OneDrive"] == hkcu["OneDrive"]


def test_launch_does_not_rewrite_or_recreate_startup():
    existing = _plan(enabled=True, hkcu_run={"OneDrive": "od", "Save Dates": COMMAND})
    assert existing["wrote"] is False
    assert existing["enabled"] is True
    assert existing["hkcu_run"]["Save Dates"] == COMMAND
    assert existing["hkcu_run"]["OneDrive"] == "od"

    changed = _plan(
        enabled=True,
        command=COMMAND + " --again",
        hkcu_run={"Save Dates": COMMAND, "OneDrive": "od"},
    )
    assert changed["wrote"] is False
    assert changed["hkcu_run"]["Save Dates"] == COMMAND

    missing = _plan(enabled=True, hkcu_run={"OneDrive": "od"})
    assert missing["enabled"] is False
    assert missing["wrote"] is False
    assert "Save Dates" not in missing["hkcu_run"]
    assert missing["hkcu_run"]["OneDrive"] == "od"


def test_windows_settings_off_is_not_turned_back_on():
    disabled = _plan(
        enabled=True,
        hkcu_run={"Save Dates": COMMAND, "OneDrive": "od"},
        approved={"Save Dates": bytes([3, 0, 0, 0])},
    )
    assert disabled["enabled"] is False
    assert disabled["wrote"] is False
    assert "Save Dates" not in disabled["hkcu_run"]
    assert disabled["hkcu_run"]["OneDrive"] == "od"

    enabled_flag = _plan(
        enabled=True,
        hkcu_run={"Save Dates": COMMAND},
        approved={"Save Dates": bytes([2, 0, 0, 0])},
    )
    assert enabled_flag["enabled"] is True
    assert enabled_flag["wrote"] is False


def test_explicit_opt_in_is_the_only_way_to_add_startup():
    added = _plan(enabled=True, rewrite=True, hkcu_run={"OneDrive": "od"})
    assert added["enabled"] is True
    assert added["wrote"] is True
    assert added["hkcu_run"] == {"OneDrive": "od", "Save Dates": COMMAND}

    again = _plan(
        enabled=True,
        rewrite=True,
        hkcu_run=added["hkcu_run"],
        approved={"Save Dates": bytes([3, 0, 0, 0])},
    )
    assert again["enabled"] is True
    assert again["hkcu_run"]["Save Dates"] == COMMAND
    assert "Save Dates" in again["approved_delete"]


def test_diff_never_touches_unrelated_entries():
    before = {
        "hkcu_run": {
            "OneDrive": "od",
            "Save Dates": COMMAND,
            "Grammarly": "g",
        },
        "other_run": [
            {"id": "HKLM", "name": "SecurityHealth", "data": "sec"},
            {"id": "HKLM", "name": "SaveDates", "data": COMMAND},
        ],
        "shortcuts": {
            STARTUP + r"\safe - 快捷方式.lnk": (r"C:\huorong-m\safe.vbs", ""),
            STARTUP + r"\Save Dates.lnk": (r"F:\Save Dates\dist\SaveDates\SaveDates.exe", ""),
        },
        "tasks": {"Office Feature Updates", "Save Dates"},
    }
    after = {
        "hkcu_run": {},
        "other_run": [],
        "shortcuts": {},
        "tasks": set(),
        "approved_delete": ["OneDrive", "SecurityHealth", "safe - 快捷方式.lnk", "Save Dates", "Save Dates.lnk"],
    }
    ops = diff_operations(before, after)
    assert ("delete_hkcu", "Save Dates") in ops
    assert ("delete_other", "HKLM", "SaveDates") in ops
    assert ("delete_task", "Save Dates") in ops
    assert ("delete_shortcut", STARTUP + r"\Save Dates.lnk", r"F:\Save Dates\dist\SaveDates\SaveDates.exe", "") in ops
    assert ("delete_approved", "Save Dates") in ops
    assert ("delete_approved", "Save Dates.lnk") in ops
    assert not any("OneDrive" in op for op in ops)
    assert not any("Grammarly" in op for op in ops)
    assert not any("SecurityHealth" in op for op in ops)
    assert not any("Office Feature Updates" in op for op in ops)
    assert not any("safe" in str(op) for op in ops)
    assert not any(op[0] == "set_hkcu" for op in ops)


def test_off_plan_has_no_set_operation():
    before = {
        "hkcu_run": {"OneDrive": "od", "Save Dates": COMMAND},
        "other_run": [{"id": "HKLM", "name": "SecurityHealth", "data": "sec"}],
        "shortcuts": {STARTUP + r"\safe - 快捷方式.lnk": (r"C:\huorong-m\safe.vbs", "")},
        "tasks": {"Office Feature Updates"},
    }
    after = _plan(
        enabled=False,
        hkcu_run=before["hkcu_run"],
        other_run=before["other_run"],
        shortcuts=before["shortcuts"],
        tasks=before["tasks"],
    )
    ops = diff_operations(before, after)
    assert ops == [("delete_hkcu", "Save Dates"), ("delete_approved", "Save Dates")]
    assert not is_our_run_value("OneDrive", "od")
    assert not is_our_shortcut("safe - 快捷方式.lnk", r"C:\huorong-m\safe.vbs", "")
    assert is_our_shortcut("Save Dates.lnk", "", "")
    assert is_our_run_value("Helper", r"C:\Apps\SaveDates.exe")


def test_remove_shortcut_stays_inside_startup_folder(tmp_path, monkeypatch):
    startup = tmp_path / "Startup"
    desktop = tmp_path / "Desktop"
    startup.mkdir()
    desktop.mkdir()
    monkeypatch.setattr("save_dates.windows_startup.startup_directories", lambda: [startup])
    ours = startup / "Save Dates.lnk"
    ours.write_bytes(b"lnk")
    other = startup / "safe - 快捷方式.lnk"
    other.write_bytes(b"lnk")
    desktop_link = desktop / "Save Dates.lnk"
    desktop_link.write_bytes(b"lnk")
    assert remove_startup_shortcut(ours, r"F:\Save Dates\dist\SaveDates\SaveDates.exe", "") is True
    assert not ours.exists()
    assert remove_startup_shortcut(other, r"C:\huorong-m\safe.vbs", "") is False
    assert other.exists()
    assert remove_startup_shortcut(desktop_link, r"F:\Save Dates\dist\SaveDates\SaveDates.exe", "") is False
    assert desktop_link.exists()


def test_reconcile_off_uses_plan_and_does_not_enable(monkeypatch):
    stored = {
        "hkcu_run": {"OneDrive": "od", "Save Dates": COMMAND},
        "other_run": [{"id": "HKLM", "name": "SecurityHealth", "data": "sec"}],
        "approved": {},
        "shortcuts": {STARTUP + r"\safe - 快捷方式.lnk": (r"C:\huorong-m\safe.vbs", "")},
        "tasks": {"Office Feature Updates"},
    }
    commits = []
    monkeypatch.setattr("save_dates.windows_startup.load_snapshot", lambda: stored)
    monkeypatch.setattr("save_dates.windows_startup.commit_snapshot", lambda before, after: commits.append(after))
    assert reconcile_installed_autostart(False) is False
    assert commits[0]["wrote"] is False
    assert "Save Dates" not in commits[0]["hkcu_run"]
    assert commits[0]["hkcu_run"]["OneDrive"] == "od"
    assert commits[0]["other_run"][0]["name"] == "SecurityHealth"
    assert "safe" in next(iter(commits[0]["shortcuts"]))
    stored["hkcu_run"] = commits[0]["hkcu_run"]
    assert reconcile_installed_autostart(True) is False
    assert commits[-1]["wrote"] is False
    assert "Save Dates" not in commits[-1]["hkcu_run"]


def test_start_with_windows_defaults_off_and_stays_off(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    from save_dates import db

    db.clear_session_backend()
    try:
        assert db.get_settings()["start_with_windows"] is False
        db.save_settings({"lang": "zh"})
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "start_with_windows" not in raw
        assert db.get_settings()["start_with_windows"] is False
        assert db.save_settings({"start_with_windows": "yes"})["start_with_windows"] is False
        assert db.save_settings({"start_with_windows": True})["start_with_windows"] is True
        db.save_settings({"lang": "en"})
        assert db.get_settings()["start_with_windows"] is True
        assert db.save_settings({"start_with_windows": False})["start_with_windows"] is False
        db.save_settings({"backend": "classic"})
        assert db.get_settings()["start_with_windows"] is False
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        assert raw["start_with_windows"] is False
    finally:
        db.clear_session_backend()


def test_settings_api_opt_in_does_not_run_on_other_saves(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    calls = []

    def fake(enabled, rewrite=False):
        calls.append((enabled, rewrite))
        return enabled is True and rewrite is True

    monkeypatch.setattr("save_dates.windows_startup.reconcile_installed_autostart", fake)
    from fastapi.testclient import TestClient

    from save_dates import db
    from save_dates.server import app

    db.clear_session_backend()
    try:
        with TestClient(app) as client:
            assert client.get("/api/settings").json()["start_with_windows"] is False
            saved = client.put("/api/settings", json={"start_with_windows": True})
            assert saved.status_code == 200
            assert saved.json()["start_with_windows"] is True
            assert calls == [(True, True)]
            off = client.put("/api/settings", json={"start_with_windows": False})
            assert off.json()["start_with_windows"] is False
            assert calls == [(True, True), (False, False)]
            client.put("/api/settings", json={"lang": "zh"})
            assert calls == [(True, True), (False, False)]
            assert client.get("/api/settings").json()["start_with_windows"] is False
    finally:
        db.clear_session_backend()
