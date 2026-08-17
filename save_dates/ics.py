"""Parse calendar attachments (RFC 5545 VEVENT) into review candidates."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from save_dates.config import (
    ICS_EVENT_MAX,
    ICS_PAST_DAYS,
    LOCATION_WRITE_MAX,
    MAX_FUTURE_DAYS,
    NOTES_FIELD_MAX,
)
from save_dates.extract import ExtractedEvent, ensure_aware, html_to_text

_BEGIN = "BEGIN:VEVENT"
_END = "END:VEVENT"
_PROP = re.compile(r"^(?P<name>[A-Za-z0-9-]+)(?P<params>(?:;[^:]*)*):(?P<value>.*)$")
_DURATION = re.compile(
    r"^P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.I,
)


def is_ics_name(name: str, content_type: str = "") -> bool:
    lowered = (name or "").strip().lower()
    mime = (content_type or "").strip().lower()
    if lowered.endswith((".ics", ".ical", ".ifb")):
        return True
    return "text/calendar" in mime or mime == "text/calendar"


def decode_ics_bytes(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    raw = bytes(data)
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_ics_events(
    raw: str,
    *,
    now: datetime,
    tz: ZoneInfo,
    source_title: str = "",
    received_at: datetime | None = None,
) -> list[ExtractedEvent]:
    text = unfold_ics(raw)
    if _BEGIN not in text.upper():
        return []
    events: list[ExtractedEvent] = []
    upper = text.upper()
    start = 0
    while True:
        begin = upper.find(_BEGIN, start)
        if begin < 0:
            break
        end = upper.find(_END, begin + len(_BEGIN))
        if end < 0:
            break
        block = text[begin : end + len(_END)]
        try:
            parsed = _vevent_to_event(
                block,
                now=now,
                tz=tz,
                source_title=source_title,
                received_at=received_at,
            )
        except Exception:
            parsed = None
        if parsed:
            events.append(parsed)
        start = end + len(_END)
        if len(events) >= ICS_EVENT_MAX * 2:
            break
    events.sort(key=lambda item: (item.start < now - timedelta(hours=1), item.start, item.title))
    return events[:ICS_EVENT_MAX]


def unfold_ics(raw: str) -> str:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)


def _vevent_to_event(
    block: str,
    *,
    now: datetime,
    tz: ZoneInfo,
    source_title: str,
    received_at: datetime | None,
) -> ExtractedEvent | None:
    props = _properties(block)
    if (props.get("STATUS") or "").upper() == "CANCELLED":
        return None
    start, all_day = _parse_dt(props.get("DTSTART_RAW", ""), props.get("DTSTART_PARAMS", {}), tz)
    if start is None:
        return None
    end, end_all_day = _parse_dt(props.get("DTEND_RAW", ""), props.get("DTEND_PARAMS", {}), tz)
    if end is None:
        duration = _parse_duration(props.get("DURATION", ""))
        end = start + (duration or timedelta(days=1 if all_day else 0, hours=0 if all_day else 1))
        if all_day and duration is None:
            end = start + timedelta(days=1)
    elif all_day or end_all_day:
        all_day = True
        if end <= start:
            end = start + timedelta(days=1)
    elif end <= start:
        end = start + timedelta(hours=1)
    start = ensure_aware(start, tz)
    end = ensure_aware(end, tz)
    if not _valid_ics_window(start, now):
        return None
    title = _unescape(props.get("SUMMARY") or "") or (source_title or "日历事件")
    title = re.sub(r"\s+", " ", title).strip()[:80] or "日历事件"
    location = _unescape(props.get("LOCATION") or "").strip()
    location = re.sub(r"\s+", " ", location)[:LOCATION_WRITE_MAX]
    description = html_to_text(_unescape(props.get("DESCRIPTION") or ""))
    notes = _short_ics_notes(description)
    snippet = (description or location or title).replace("\n", " ").strip()[:160]
    return ExtractedEvent(
        title=title,
        start=start,
        end=end,
        all_day=all_day,
        snippet=snippet,
        matched_text=title,
        confidence=0.9,
        fuzzy=False,
        kind="event",
        location=location,
        notes=notes,
        date_kind="ics",
    )


def _valid_ics_window(start: datetime, now: datetime) -> bool:
    if start > now + timedelta(days=MAX_FUTURE_DAYS):
        return False
    if start < now - timedelta(days=ICS_PAST_DAYS):
        return False
    return True


def _short_ics_notes(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    if len(cleaned) > 240:
        cut = cleaned[:240]
        cleaned = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return cleaned[:NOTES_FIELD_MAX]


def _properties(block: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in (block or "").split("\n"):
        match = _PROP.match(line.strip())
        if not match:
            continue
        name = match["name"].upper()
        params = match["params"] or ""
        value = match["value"]
        if name == "DTSTART":
            rows["DTSTART_RAW"] = value
            rows["DTSTART_PARAMS"] = params
        elif name == "DTEND":
            rows["DTEND_RAW"] = value
            rows["DTEND_PARAMS"] = params
        else:
            rows[name] = value
    return rows


def _parse_dt(value: str, params: str, tz: ZoneInfo) -> tuple[datetime | None, bool]:
    raw = (value or "").strip()
    if not raw:
        return None, False
    param_map = _params(params)
    tzid = param_map.get("TZID", "")
    value_type = param_map.get("VALUE", "").upper()
    compact = re.sub(r"[-:]", "", raw)
    if "T" not in compact or value_type == "DATE":
        digits = re.sub(r"\D", "", compact)[:8]
        if len(digits) != 8:
            return None, True
        year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        try:
            return datetime(year, month, day, tzinfo=tz), True
        except ValueError:
            return None, True
    utc = compact.endswith("Z")
    compact = compact.rstrip("Z")
    stamp = compact.replace("T", "")
    if len(stamp) < 12 or not stamp[:12].isdigit():
        return None, False
    year, month, day = int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])
    hour, minute = int(stamp[8:10]), int(stamp[10:12])
    second = int(stamp[12:14]) if len(stamp) >= 14 and stamp[12:14].isdigit() else 0
    try:
        naive = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None, False
    if utc:
        return naive.replace(tzinfo=timezone.utc).astimezone(tz), False
    zone = _zone(tzid, tz)
    return naive.replace(tzinfo=zone).astimezone(tz), False


def _zone(tzid: str, fallback: ZoneInfo) -> ZoneInfo:
    name = (tzid or "").strip().strip('"')
    if not name:
        return fallback
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        aliases = {
            "US/Eastern": "America/New_York",
            "US/Central": "America/Chicago",
            "US/Pacific": "America/Los_Angeles",
            "Eastern Standard Time": "America/New_York",
            "China Standard Time": "Asia/Shanghai",
        }
        alias = aliases.get(name)
        if alias:
            try:
                return ZoneInfo(alias)
            except ZoneInfoNotFoundError:
                return fallback
        return fallback


def _params(raw: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in (raw or "").split(";"):
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        found[key.strip().upper()] = value.strip().strip('"')
    return found


def _parse_duration(value: str) -> timedelta | None:
    match = _DURATION.match((value or "").strip())
    if not match:
        return None
    weeks = int(match["weeks"] or 0)
    days = int(match["days"] or 0)
    hours = int(match["hours"] or 0)
    minutes = int(match["minutes"] or 0)
    seconds = int(match["seconds"] or 0)
    if not (weeks or days or hours or minutes or seconds):
        return None
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


def _unescape(value: str) -> str:
    text = value or ""
    text = text.replace("\\n", "\n").replace("\\N", "\n")
    text = text.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
    return text.strip()
