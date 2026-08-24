from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from save_dates.obsidian import (
    append_daily_bullet,
    daily_bullet_line,
    daily_contains,
    default_vault_path,
    ensure_vault,
    event_filename,
    event_note_body,
    process_inbox_photos,
    sanitize_filename,
    should_write,
    write_candidate,
)

TZ = ZoneInfo("America/New_York")
START = datetime(2026, 8, 23, 15, 0, tzinfo=TZ)


def test_sanitize_filename_strips_windows_forbidden_chars():
    assert "\\" not in sanitize_filename(r"a\b/c")
    assert "/" not in sanitize_filename("a/b")
    dirty = 'Q: "Hello/World*?" <>|'
    clean = sanitize_filename(dirty)
    for ch in '\\/:*?"<>|':
        assert ch not in clean
    assert "Hello" in clean
    assert "World" in clean
    assert sanitize_filename("   ...  ") == "untitled"
    assert sanitize_filename("a" * 200).endswith("a") or len(sanitize_filename("a" * 200)) <= 80


def test_event_filename_uses_date_and_safe_title():
    name = event_filename(START, 'Midterm: CS 1501 / "Graphs"?')
    assert name.startswith("2026-08-23 ")
    assert name.endswith(".md")
    for ch in '\\/:*?"<>|':
        assert ch not in name


def test_daily_append_and_skip_duplicate(tmp_path: Path):
    daily = tmp_path / "Daily" / "2026-08-23.md"
    title = "GSR orientation"
    bullet = daily_bullet_line(title, START, False, "Public Health A521")
    assert append_daily_bullet(daily, START, bullet, title, False) is True
    text = daily.read_text(encoding="utf-8")
    assert "# 2026-08-23" in text
    assert text.count(title) == 1
    assert "15:00" in text
    assert "Public Health A521" in text

    again = daily_bullet_line(title, START, False, "Somewhere else")
    assert append_daily_bullet(daily, START, again, title, False) is False
    assert daily.read_text(encoding="utf-8").count(title) == 1

    later = datetime(2026, 8, 23, 18, 30, tzinfo=TZ)
    other = daily_bullet_line(title, later, False, "")
    assert daily_contains(daily.read_text(encoding="utf-8"), title, later, False) is False
    assert append_daily_bullet(daily, later, other, title, False) is True
    assert daily.read_text(encoding="utf-8").count("15:00") == 1
    assert "18:30" in daily.read_text(encoding="utf-8")


def test_write_candidate_makes_event_and_daily(tmp_path: Path):
    item = {
        "title": "Department seminar",
        "start_at": START.isoformat(timespec="minutes"),
        "end_at": datetime(2026, 8, 23, 16, 0, tzinfo=TZ).isoformat(timespec="minutes"),
        "all_day": False,
        "kind": "event",
        "location": "Cathedral 324",
        "notes": "Bring student ID",
        "matched_text": "seminar Friday 3pm",
        "mailbox": "yuan@pitt.edu",
        "subject": "Reminder: Department seminar",
        "email_id": "real-mail-1",
    }
    result = write_candidate(item, tmp_path)
    event_path = Path(result["event_note"])
    daily_path = Path(result["daily_note"])
    assert event_path.exists()
    assert daily_path.exists()
    body = event_path.read_text(encoding="utf-8")
    assert "America/New_York" in body
    assert "15:00" in body
    assert "Cathedral 324" in body
    assert "Bring student ID" in body
    assert "yuan@pitt.edu" in body
    assert "Reminder: Department seminar" in body
    assert result["daily_appended"] is True
    second = write_candidate(item, tmp_path)
    assert second["daily_appended"] is False
    assert daily_path.read_text(encoding="utf-8").count("Department seminar") == 1


def test_should_write_skips_demo_and_promo():
    settings = {
        "obsidian_write": True,
        "obsidian_vault": r"D:\Notes\Pitt",
    }
    assert should_write({"kind": "event", "email_id": "abc"}, settings) is True
    assert should_write({"kind": "event", "email_id": "demo-1"}, settings) is False
    assert should_write({"kind": "promo", "email_id": "abc"}, settings) is False
    assert should_write(
        {"kind": "task", "email_id": "abc"},
        {"obsidian_write": False, "obsidian_vault": "x"},
    ) is False


def test_inbox_photo_helper_embeds_without_ocr(tmp_path: Path):
    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    image = inbox / "poster.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    first = process_inbox_photos(tmp_path)
    assert first["created"]
    note = inbox / first["created"][0]
    text = note.read_text(encoding="utf-8")
    assert "![[poster.png]]" in text
    assert "日期:" in text
    assert "地点:" in text
    assert "要做:" in text
    second = process_inbox_photos(tmp_path)
    assert second["created"] == []
    assert "poster.png" in second["skipped"]


def test_settings_persist_vault_and_keep_on_lang_save(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    from save_dates import db

    db.clear_session_backend()
    vault = tmp_path / "Pitt"
    saved = db.save_settings({"obsidian_vault": str(vault), "obsidian_write": True})
    assert saved["obsidian_write"] is True
    assert saved["obsidian_export_on_join"] is True
    assert saved["obsidian_vault"] == str(vault)
    assert saved["obsidian_vault_path"] == str(vault)
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["obsidian_vault"] == str(vault)
    assert raw["obsidian_write"] is True
    db.save_settings({"lang": "en"})
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["obsidian_vault"] == str(vault)
    assert raw["obsidian_write"] is True
    assert raw["lang"] == "en"


def test_default_vault_path_prefers_d_when_present():
    path = default_vault_path()
    assert path in {Path(r"D:\Notes\Pitt"), Path(r"F:\Notes\Pitt")}
    if Path("D:/").exists():
        assert path == Path(r"D:\Notes\Pitt")


def test_ensure_vault_creates_beginner_folders(tmp_path: Path):
    ensure_vault(tmp_path)
    for name in ("Inbox", "Daily", "Events", "课程", "GSR", "生活", "_templates"):
        assert (tmp_path / name).is_dir()


def test_event_note_includes_original_english_when_title_translated():
    item = {
        "title": "Career Fair at the Petersen Events Center",
        "start_at": START.isoformat(timespec="minutes"),
        "end_at": START.isoformat(timespec="minutes"),
        "all_day": False,
        "kind": "event",
        "subject": "Pitt Career Fair",
        "mailbox": "yuan@pitt.edu",
        "location": "",
        "notes": "",
        "matched_text": "",
    }
    body = event_note_body(item, written_title="招聘会：Career Fair at the Petersen Events Center")
    assert "英文原标题:" in body
    assert "Career Fair at the Petersen Events Center" in body


def test_accept_event_exports_to_configured_vault(tmp_path: Path, monkeypatch):
    from datetime import datetime

    from fastapi.testclient import TestClient

    from save_dates.extract import local_tz
    from save_dates.server import app

    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.DB_PATH", tmp_path / "save_dates.db")
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    vault = tmp_path / "vault"

    from save_dates import db

    db.init_db()
    db.save_settings(
        {
            "lang": "en",
            "obsidian_vault": str(vault),
            "obsidian_write": True,
        }
    )

    def fake_create_event(**kwargs):
        return "cal-obsidian"

    monkeypatch.setattr("save_dates.server.watcher.create_event", fake_create_event)

    tz = local_tz()
    start = datetime(2026, 9, 1, 14, 0, tzinfo=tz)
    end = datetime(2026, 9, 1, 15, 0, tzinfo=tz)
    db.insert_candidates(
        [
            {
                "email_id": "obsidian-mail-1",
                "internet_id": "",
                "store_id": "",
                "mail_url": "",
                "subject": "Seminar reminder",
                "sender": "dept@pitt.edu",
                "received_at": start.isoformat(timespec="seconds"),
                "title": "Department seminar",
                "start_at": start.isoformat(timespec="minutes"),
                "end_at": end.isoformat(timespec="minutes"),
                "all_day": False,
                "snippet": "Friday seminar",
                "matched_text": "seminar 2pm",
                "confidence": 0.9,
                "fuzzy": False,
                "kind": "event",
                "task_type": "",
                "mailbox": "yuan@pitt.edu",
                "location": "Cathedral 324",
                "notes": "Bring ID",
            }
        ]
    )

    with TestClient(app) as client:
        items = client.get("/api/candidates?status=pending").json()["items"]
        event = next(item for item in items if item["email_id"] == "obsidian-mail-1")
        accepted = client.post(f"/api/candidates/{event['id']}/accept")
        assert accepted.status_code == 200

    event_files = list((vault / "Events").glob("*.md"))
    assert event_files
    note = event_files[0].read_text(encoding="utf-8")
    assert "Department seminar" in note
    assert "America/New_York" in note
    assert "Cathedral 324" in note
    daily = vault / "Daily" / "2026-09-01.md"
    assert daily.exists()
    daily_text = daily.read_text(encoding="utf-8")
    assert "14:00" in daily_text
    assert "Cathedral 324" in daily_text
    assert "Department seminar" in daily_text
    from datetime import datetime

    from fastapi.testclient import TestClient

    from save_dates.db import insert_candidates, save_settings
    from save_dates.extract import local_tz
    from save_dates.server import app

    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.DB_PATH", tmp_path / "save_dates.db")
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    vault = tmp_path / "vault"

    from save_dates import db

    db.init_db()
    save_settings = db.save_settings
    insert_candidates = db.insert_candidates
    save_settings({"obsidian_vault_path": str(vault), "obsidian_export_on_join": True})

    def fake_create_event(**kwargs):
        return "cal-obsidian"

    monkeypatch.setattr("save_dates.server.watcher.create_event", fake_create_event)

    tz = local_tz()
    start = datetime(2026, 9, 1, 14, 0, tzinfo=tz)
    end = datetime(2026, 9, 1, 15, 0, tzinfo=tz)
    insert_candidates(
        [
            {
                "email_id": "obsidian-mail-1",
                "internet_id": "",
                "store_id": "",
                "mail_url": "",
                "subject": "Seminar reminder",
                "sender": "dept@pitt.edu",
                "received_at": start.isoformat(timespec="seconds"),
                "title": "Department seminar",
                "start_at": start.isoformat(timespec="minutes"),
                "end_at": end.isoformat(timespec="minutes"),
                "all_day": False,
                "snippet": "Friday seminar",
                "matched_text": "seminar 2pm",
                "confidence": 0.9,
                "fuzzy": False,
                "kind": "event",
                "task_type": "",
                "mailbox": "yuan@pitt.edu",
                "location": "Cathedral 324",
                "notes": "Bring ID",
            }
        ]
    )

    with TestClient(app) as client:
        items = client.get("/api/candidates?status=pending").json()["items"]
        event = next(item for item in items if item["email_id"] == "obsidian-mail-1")
        accepted = client.post(f"/api/candidates/{event['id']}/accept")
        assert accepted.status_code == 200

    event_files = list((vault / "Events").glob("*.md"))
    assert event_files
    assert "Department seminar" in event_files[0].read_text(encoding="utf-8")
    daily = vault / "Daily" / "2026-09-01.md"
    assert daily.exists()
    assert "14:00" in daily.read_text(encoding="utf-8")
    assert "Cathedral 324" in daily.read_text(encoding="utf-8")
