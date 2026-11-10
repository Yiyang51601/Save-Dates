"""Repeat reminders stay off until the user opts in, and past times are skipped."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from save_dates.config import (
    ALL_DAY_REPEAT_DAY_BEFORE_HOUR,
    ALL_DAY_REPEAT_MORNING_HOUR,
    REPEAT_REMINDER_SOON_MINUTES,
)
from save_dates.graph_client import reminder_event_payload
from save_dates.reminders import (
    active_repeat_times,
    normalize_repeat_enabled,
    repeat_reminder_times,
)

TZ = ZoneInfo("America/New_York")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.DB_PATH", tmp_path / "save_dates.db")
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    from save_dates import db as database

    database.clear_session_backend()
    database.init_db()
    yield database
    database.clear_session_backend()


def _event(**overrides) -> dict:
    row = {
        "email_id": "mail-1",
        "subject": "Seminar",
        "sender": "a@pitt.edu",
        "received_at": "2026-11-01T10:00:00",
        "title": "Seminar",
        "start_at": "2026-11-20T15:00:00",
        "end_at": "2026-11-20T16:00:00",
        "all_day": False,
        "snippet": "",
        "matched_text": "Nov 20",
        "confidence": 0.9,
        "kind": "event",
        "task_type": "",
    }
    row.update(overrides)
    return row


def _pending(database, **overrides) -> dict:
    database.insert_candidates([_event(**overrides)])
    email_id = overrides.get("email_id", "mail-1")
    title = overrides.get("title", "Seminar")
    rows = [
        row
        for row in database.list_candidates("pending", limit=40)
        if row["email_id"] == email_id and row["title"] == title
    ]
    assert rows
    return rows[-1]


def test_repeat_defaults_off(db):
    assert db.get_settings()["repeat_reminders"] is False
    assert db.get_settings()["start_with_windows"] is False
    item = _pending(db)
    assert item["repeat_reminders"] is False
    assert item["reminder_entry_ids"] == []
    forced = _pending(db, email_id="mail-forced", title="Forced", repeat_reminders=True)
    assert forced["repeat_reminders"] is False
    db.save_settings({"lang": "zh"})
    raw = json.loads((db.SETTINGS_PATH).read_text(encoding="utf-8"))
    assert "repeat_reminders" not in raw
    assert db.get_settings()["repeat_reminders"] is False
    assert db.get_candidate(item["id"])["repeat_reminders"] is False


def test_explicit_enable_stores_the_choice(db, monkeypatch):
    item = _pending(db)
    stored = db.set_repeat_reminders(item["id"], True, ["outlook-a"])
    assert stored["repeat_reminders"] is True
    assert stored["reminder_entry_ids"] == ["outlook-a"]

    db.save_scan_candidates([_event()])
    rescanned = [
        row
        for row in db.list_candidates("pending", limit=20)
        if row["email_id"] == "mail-1" and row["title"] == "Seminar"
    ]
    assert len(rescanned) == 1
    assert rescanned[0]["repeat_reminders"] is True

    sibling = _event(title="Office hours", start_at="2026-11-21T15:00:00", end_at="2026-11-21T16:00:00")
    sibling["repeat_reminders"] = True
    db.save_scan_candidates([_event(), sibling])
    rows = db.list_candidates("pending", limit=20)
    by_title = {row["title"]: row for row in rows if row["email_id"] == "mail-1"}
    assert by_title["Seminar"]["repeat_reminders"] is True
    assert by_title["Office hours"]["repeat_reminders"] is False

    db.save_settings({"repeat_reminders": True})
    assert db.get_settings()["repeat_reminders"] is True
    assert db.get_candidate(by_title["Office hours"]["id"])["repeat_reminders"] is False
    db.save_settings({"lang": "en"})
    assert db.get_settings()["repeat_reminders"] is True
    assert db.get_settings()["start_with_windows"] is False


def test_disable_stops_repeats_and_is_not_turned_back_on(db, monkeypatch):
    item = _pending(db)
    db.set_status(item["id"], "accepted", "main-event")
    db.set_repeat_reminders(item["id"], True, ["rem-1", "rem-2"])
    deleted: list[tuple[str, str]] = []

    def _delete(entry_id: str, kind: str = "event") -> None:
        deleted.append((entry_id, kind))

    monkeypatch.setattr("save_dates.server.watcher.delete_written", _delete)
    from save_dates.server import _apply_repeat_choice

    stopped = _apply_repeat_choice(item["id"], False)
    assert deleted == [("rem-1", "event"), ("rem-2", "event")]
    assert stopped["repeat_reminders"] is False
    assert stopped["reminder_entry_ids"] == []
    assert db.list_repeat_events() == []

    db.save_scan_candidates([_event(repeat_reminders=True)])
    assert db.get_candidate(item["id"])["repeat_reminders"] is False

    def _flip(items):
        for row in items:
            row["repeat_reminders"] = True
            row["location"] = "Hall"
        return items

    monkeypatch.setattr("save_dates.extract.merge_related_events", _flip)
    _pending(db, email_id="mail-2", title="Other seminar")
    db.enrich_related_pending()
    assert db.get_candidate(item["id"])["repeat_reminders"] is False
    pending = db.list_candidates("pending", limit=20)
    assert pending
    assert all(row["repeat_reminders"] is False for row in pending)

    db.init_db()
    assert db.get_candidate(item["id"])["repeat_reminders"] is False
    assert db.get_settings()["repeat_reminders"] is False

    db.set_repeat_reminders(item["id"], True, ["rem-3"])

    def _fail(entry_id: str, kind: str = "event") -> None:
        raise RuntimeError("calendar_delete_failed")

    monkeypatch.setattr("save_dates.server.watcher.delete_written", _fail)
    with pytest.raises(HTTPException):
        _apply_repeat_choice(item["id"], False)
    still = db.get_candidate(item["id"])
    assert still["repeat_reminders"] is True
    assert still["reminder_entry_ids"] == ["rem-3"]


def test_past_reminder_times_are_skipped():
    assert REPEAT_REMINDER_SOON_MINUTES == 15
    assert ALL_DAY_REPEAT_DAY_BEFORE_HOUR == 9
    assert ALL_DAY_REPEAT_MORNING_HOUR == 8

    start = datetime(2026, 11, 10, 15, 0, tzinfo=TZ)
    half_hour_before = datetime(2026, 11, 10, 14, 30, tzinfo=TZ)
    times = repeat_reminder_times(start, False, half_hour_before)
    assert times == [datetime(2026, 11, 10, 14, 45, tzinfo=TZ)]

    early = datetime(2026, 11, 9, 10, 0, tzinfo=TZ)
    assert repeat_reminder_times(start, False, early) == [
        datetime(2026, 11, 9, 15, 0, tzinfo=TZ),
        datetime(2026, 11, 10, 14, 0, tzinfo=TZ),
        datetime(2026, 11, 10, 14, 45, tzinfo=TZ),
    ]
    assert repeat_reminder_times(start, False, datetime(2026, 11, 10, 14, 45, tzinfo=TZ)) == []
    assert repeat_reminder_times(start, False, datetime(2026, 11, 10, 14, 50, tzinfo=TZ)) == []

    all_day = datetime(2026, 11, 12, 0, 0, tzinfo=TZ)
    before_both = datetime(2026, 11, 11, 8, 0, tzinfo=TZ)
    assert repeat_reminder_times(all_day, True, before_both) == [
        datetime(2026, 11, 11, 9, 0, tzinfo=TZ),
        datetime(2026, 11, 12, 8, 0, tzinfo=TZ),
    ]
    after_day_before = datetime(2026, 11, 11, 12, 0, tzinfo=TZ)
    assert repeat_reminder_times(all_day, True, after_day_before) == [
        datetime(2026, 11, 12, 8, 0, tzinfo=TZ),
    ]
    assert repeat_reminder_times(all_day, True, datetime(2026, 11, 12, 8, 0, tzinfo=TZ)) == []

    future = {
        "kind": "event",
        "status": "accepted",
        "repeat_reminders": True,
        "all_day": False,
        "start_at": start.isoformat(),
    }
    assert len(active_repeat_times(future, early)) == 3
    future["repeat_reminders"] = False
    assert active_repeat_times(future, early) == []
    future["repeat_reminders"] = True
    future["status"] = "rejected"
    assert active_repeat_times(future, early) == []
    future["status"] = "pending"
    assert active_repeat_times(future, early) == []
    future["status"] = "accepted"
    future["kind"] = "task"
    assert active_repeat_times(future, early) == []
    future["kind"] = "promo"
    assert active_repeat_times(future, early) == []
    assert normalize_repeat_enabled({"kind": "event", "status": "rejected"}, True) is False
    assert normalize_repeat_enabled({"kind": "promo", "status": "pending"}, True) is False
    assert normalize_repeat_enabled({"kind": "task", "status": "pending"}, True) is False


def test_enabled_accept_writes_only_future_reminder_appointments(db, monkeypatch):
    item = _pending(db)
    db.set_status(item["id"], "accepted", "main-event")
    created: list[datetime] = []

    def _create(**kwargs):
        created.append(kwargs["when"])
        return f"ping-{len(created)}"

    monkeypatch.setattr("save_dates.server.watcher.create_reminder", _create)
    monkeypatch.setattr(
        "save_dates.server.datetime",
        type("Clock", (), {"now": staticmethod(lambda tz=None: datetime(2026, 11, 10, 14, 30, tzinfo=TZ))}),
    )
    from save_dates.server import _apply_repeat_choice

    db.update_candidate(
        item["id"],
        {"start_at": "2026-11-10T15:00:00-05:00", "end_at": "2026-11-10T16:00:00-05:00", "all_day": False},
    )
    saved = _apply_repeat_choice(item["id"], True)
    assert len(created) == 1
    assert created[0] == datetime(2026, 11, 10, 14, 45, tzinfo=TZ)
    assert saved["repeat_reminders"] is True
    assert saved["reminder_entry_ids"] == ["ping-1"]

    when = datetime(2026, 11, 10, 14, 45, tzinfo=TZ)
    payload = reminder_event_payload("提醒：Seminar", when, "note", "Hall")
    assert payload["isReminderOn"] is True
    assert payload["reminderMinutesBeforeStart"] == 0
    assert payload["showAs"] == "free"
    assert payload["isAllDay"] is False
    assert payload["start"]["dateTime"] == "2026-11-10T14:45:00"
    assert payload["start"]["timeZone"] == "America/New_York"
    assert payload["end"]["dateTime"] == "2026-11-10T14:50:00"


def test_ui_shows_opt_in_schedule():
    root = Path(__file__).resolve().parents[1]
    js = (root / "save_dates" / "static" / "app.js").read_text(encoding="utf-8")
    html = (root / "save_dates" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'data-field="repeat_reminders"' in js
    assert "提前 1 天、提前 1 小时、提前 15 分钟" in js
    assert "前一天上午 9:00（美东）" in js
    assert "当天上午 8:00（美东）" in js
    assert "1 day before, 1 hour before, and 15 minutes before" in js
    assert "9:00 the day before" in js
    assert "8:00 the morning of the event" in js
    assert "data-repeat-off" in js
    assert 'id="repeatRemindersSetting"' in html
    assert 'id="repeatPanel"' in html
