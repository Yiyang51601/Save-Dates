"""Opt-in repeat reminders.

Outlook keeps a single ReminderMinutesBeforeStart on the real appointment.
A chosen repeat is several short free appointments, each reminding at its start,
so Outlook fires once per time. Nothing here runs unless the user turned that
event on, and times that have already passed are left out.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from save_dates.config import (
    ALL_DAY_REPEAT_DAY_BEFORE_HOUR,
    ALL_DAY_REPEAT_MORNING_HOUR,
    REPEAT_REMINDER_SOON_MINUTES,
)
from save_dates.extract import calendar_tz, ensure_aware


def _eastern(value: datetime) -> datetime:
    tz = calendar_tz()
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def _start_of(item: dict[str, Any]) -> datetime | None:
    raw = item.get("start_at")
    if isinstance(raw, datetime):
        return _eastern(raw)
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _eastern(ensure_aware(parsed, calendar_tz()))


def repeat_reminder_times(start: datetime, all_day: bool, now: datetime) -> list[datetime]:
    """Future reminder instants. Past times are omitted."""
    start_et = _eastern(start)
    now_et = _eastern(now)
    if all_day:
        day = start_et.date()
        tz = calendar_tz()
        planned = [
            datetime.combine(
                day - timedelta(days=1),
                datetime.min.time().replace(hour=ALL_DAY_REPEAT_DAY_BEFORE_HOUR),
                tzinfo=tz,
            ),
            datetime.combine(
                day,
                datetime.min.time().replace(hour=ALL_DAY_REPEAT_MORNING_HOUR),
                tzinfo=tz,
            ),
        ]
    else:
        planned = [
            start_et - timedelta(days=1),
            start_et - timedelta(hours=1),
            start_et - timedelta(minutes=REPEAT_REMINDER_SOON_MINUTES),
        ]
    return [moment for moment in planned if moment > now_et]


def normalize_repeat_enabled(item: dict[str, Any], enabled: bool) -> bool:
    """Ads, tasks, and skipped items cannot be turned on."""
    if not enabled:
        return False
    if (item.get("kind") or "event") != "event":
        return False
    if item.get("status") == "rejected":
        return False
    return True


def active_repeat_times(item: dict[str, Any], now: datetime) -> list[datetime]:
    """Times Outlook should still fire. Empty when repeats are off or not allowed."""
    if not item.get("repeat_reminders"):
        return []
    if not normalize_repeat_enabled(item, True):
        return []
    if item.get("status") != "accepted":
        return []
    start = _start_of(item)
    if start is None:
        return []
    return repeat_reminder_times(start, bool(item.get("all_day")), now)


def reminder_subject(title: str, lang: str) -> str:
    prefix = "Reminder: " if lang == "en" else "提醒："
    return f"{prefix}{(title or '').strip()}"[:255]
