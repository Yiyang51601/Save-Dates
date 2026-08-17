from __future__ import annotations

import html as html_lib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from calendar import monthrange
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from tzlocal import get_localzone

from save_dates.config import (
    BODY_CHAR_LIMIT,
    LOCATION_WRITE_MAX,
    MAX_FUTURE_DAYS,
    NOTES_FIELD_MAX,
    PAST_GRACE_HOURS,
)
from save_dates.mail_search import expand_query

CN_WEEKDAY = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}

EN_WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "mon": 0,
    "tue": 1,
    "tues": 1,
    "wed": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

EN_MONTH = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

POSITIVE_KEYWORDS = (
    "截止", "截止日期", "报名", "活动", "会议", "讲座", "开幕", "闭幕", "举办",
    "将于", "定于", "邀请", "参加", "出席", "演出", "比赛", "发布会", "答辩",
    "考试", "面试", "开学", "典礼", "仪式", "培训", "工作坊", "参观", "开放日",
    "导师", "组会", "见面", "约", "讨论", "方便", "交稿", "提交", "草稿", "论文",
    "修改", "回复我", "office hours", "let's meet", "can we meet", "available",
    "please send", "catch up", "1:1", "standup", "by eod", "due by",
    "deadline", "due", "event", "meeting", "webinar", "rsvp", "workshop",
    "seminar", "interview", "exam", "session", "kickoff", "launch",
    "请准时", "时间：", "日期：", "when:", "date:", "starts", "beginning",
)

NEGATIVE_HINTS = (
    "unsubscribe", "版权所有", "copyright", "privacy policy", "隐私政策",
    "sent from my", "来自于我的",
)


@dataclass
class ExtractedEvent:
    title: str
    start: datetime
    end: datetime
    all_day: bool
    snippet: str
    matched_text: str
    confidence: float
    fuzzy: bool = False
    kind: str = "event"
    task_type: str = ""
    location: str = ""
    notes: str = ""


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        soup = BeautifulSoup(raw, "lxml")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        text = soup.get_text("\n")
    else:
        text = raw
    text = html_lib.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:BODY_CHAR_LIMIT]


_LOCATION_LABELS = (
    "举办地点", "活动地点", "会议地点", "举办地", "地点", "地址", "位置", "场地",
    "教室", "会议室", "楼层",
    "meeting room", "classroom", "building", "venue", "location", "address",
    "where", "place", "room", "hall",
)
_NOTE_LABELS = (
    "入口指引", "着装要求", "注意事项", "停车位", "入口", "进门", "着装", "注意",
    "提醒", "要带", "需带", "携带", "请带", "停车", "议程", "流程", "备注",
    "what to bring", "please bring", "please note", "dress code", "meeting link",
    "join zoom", "join teams", "enter via", "how to get there", "entrance",
    "instructions", "instruction", "parking", "agenda", "reminder", "access",
    "bring", "rsvp", "notes", "note", "zoom", "teams", "meet",
)
_SKIP_LABELS = (
    "开始时间", "结束时间", "时间", "日期", "开始", "结束", "主题", "标题",
    "发件人", "datetime", "subject", "title", "starts", "ends", "start", "end",
    "when", "date", "time", "from",
)
_MEET_URL = re.compile(
    r"https?://[^\s<>\"']*(?:zoom\.us|zoom\.com|teams\.microsoft\.com|teams\.live\.com|"
    r"meet\.google\.com|webex\.com|gotomeet(?:ing)?\.com)[^\s<>\"']*",
    re.I,
)
_ONLINE_LOC = re.compile(
    r"(?i)^(zoom|teams|google meet|meet|webex|online|virtual|线上|线上会议|网络会议|视频会议)$"
)
_DATEISH_LOC = re.compile(
    r"(?i)^\s*(?:\d{4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*[日号]?"
    r"(?:\s*[（(]?星期?[一二三四五六日天][)）]?)?"
    r"|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|(?:mon|tues?|wed|thurs?|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|(?:january|february|march|april|may|june|july|august|september|october|november|december)"
)
_EN_PLACE_NOUN = (
    r"Hall|Building|Center|Centre|Auditorium|Theatre|Theater|Library|"
    r"Lab|Laboratory|Room|Classroom|Lounge|Quad|Stadium|Office|"
    r"Chapel|Gym|Gymnasium|Ballroom|Pavilion|Annex"
)
_EN_AT_PLACE = re.compile(
    r"(?i)\b(?:in|at|@)\s+(?!the\s+(?:email|message|meantime|morning|afternoon|evening)\b)"
    r"(?:the\s+)?("
    r"(?:[A-Z][\w.'\-]*(?:\s+[A-Z][\w.'\-]*){0,6}\s+)?(?:" + _EN_PLACE_NOUN + r")"
    r"(?:\s+[A-Z]?\d{2,5}(?:\s*/\s*[A-Z]?\d{2,5})*)?"
    r")"
)
_CN_AT_PLACE = re.compile(
    r"在\s*"
    r"((?:[A-Za-z][A-Za-z0-9 .'\-]{0,40}|[\u4e00-\u9fff0-9A-Za-z]{0,24})?"
    r"(?:礼堂|大厅|教室|会议室|报告厅|中心|大楼|大厦|图书馆|办公楼|馆|厅))"
)
_FLOOR_TOKEN = re.compile(
    r"(?<!\d)(\d{1,2})\s*楼|(?:floor|level)\s*(\d{1,2})",
    re.I,
)
_ROOM_CODE = re.compile(r"\b([A-Z]\d{2,4}(?:\s*/\s*[A-Z]?\d{2,4})+)\b")
_EN_ROOM = re.compile(r"(?i)\b(?:room|rm\.?)\s*([A-Za-z]?\d{2,5}(?:\s*/\s*[A-Za-z]?\d{2,5})*)")
_CN_ROOM = re.compile(r"(?:教室|会议室|室)\s*([A-Za-z]?\d{2,5}(?:\s*/\s*[A-Za-z]?\d{2,5})*)")
_NOTE_LOOSE = re.compile(
    r"(?i)((?:please\s+)?(?:bring|rsvp\b|enter(?:\s+via)?|park(?:ing)?(?:\s+at)?|"
    r"wear|dress(?:\s+code)?)\s*[^\n。.]{3,72})"
)
_NOTE_LINE_MAX = 80
_CLAUSE_SPLIT = re.compile(r"[。！？!?\n]|[；;]")
_NOTE_PREFIX = re.compile(
    r"(?i)^(建议|请您?|请|kindly\s+|please\s+(?:be\s+sure\s+to\s+)?|"
    r"make\s+sure\s+to\s+|remember\s+to\s+|we\s+recommend\s+(?:that\s+you\s+)?)"
)
_NOTE_FROM = re.compile(r"(?i)^(?:从|via|from)\s+")
_NOTE_TAIL = re.compile(
    r"(?i)(?:，|,)\s*(?:现场有.{0,24}(?:需要使用|请参加|要用)|欢迎参加|"
    r"there\s+will\s+be.{0,40}|see\s+you\s+there.{0,20}|looking\s+forward.{0,40})$"
)
_ENTER_VIA = re.compile(r"(?i)入口进")
_SOFT_SPLIT = re.compile(
    r"(?i)(?:，|,)\s*(?=现场|欢迎|there\s+will|so\s+that|because\s+there)"
)


def _all_field_labels() -> tuple[str, ...]:
    return tuple(
        sorted(
            set(_LOCATION_LABELS) | set(_NOTE_LABELS) | set(_SKIP_LABELS),
            key=len,
            reverse=True,
        )
    )


_FIELD_LABEL_RE = re.compile(
    r"(?i)(?P<label>" + "|".join(re.escape(label) for label in _all_field_labels()) + r")\s*[:：]"
)


def _clip_field(value: str, limit: int) -> str:
    value = (value or "").strip(" \t\r\n，,;；|-")
    if not value:
        return ""
    value = value.split("\n\n")[0]
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n+", " ", value).strip()
    if len(value) > limit:
        cut = value[:limit]
        value = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return value.strip(" ，,;；")


def _first_clause(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    soft = _SOFT_SPLIT.search(text)
    if soft and soft.start() >= 6:
        text = text[: soft.start()].strip()
    match = _CLAUSE_SPLIT.search(text)
    if match and match.start() >= 6:
        text = text[: match.start()].strip()
    return text.strip(" ，,;；")


def _short_phrase(value: str, limit: int = _NOTE_LINE_MAX) -> str:
    text = _first_clause(_clip_field(value, max(limit * 3, 48)))
    text = _NOTE_PREFIX.sub("", text).strip()
    text = _NOTE_FROM.sub("", text).strip()
    text = _NOTE_TAIL.sub("", text).strip()
    text = _ENTER_VIA.sub("入口", text)
    text = re.sub(r"\s{2,}", " ", text)
    return _clip_field(text, limit)


def _clean_loc(value: str) -> str:
    value = _first_clause(value)
    value = _clip_field(value, LOCATION_WRITE_MAX)
    value = value.replace("，", " ").replace("、", " ").replace("；", " ")
    value = re.sub(r"[ \t,]+", " ", value).strip(" ,")
    return value[:LOCATION_WRITE_MAX]


def _is_dateish(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    return bool(_DATEISH_LOC.match(text)) and len(text) < 40


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip().lower())


def _labeled_fields(text: str) -> list[tuple[str, str]]:
    matches = list(_FIELD_LABEL_RE.finditer(text or ""))
    rows: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[match.end() : end].split("\n\n")[0]
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        value = lines[0] if lines else ""
        if len(value) < 8 and len(lines) > 1:
            value = f"{value} {lines[1]}".strip()
        value = _clip_field(value, 160)
        if value:
            rows.append((_norm_label(match["label"]), value))
    return rows


def _join_place(*parts: str) -> str:
    seen: list[str] = []
    blob = ""
    for part in parts:
        piece = _clean_loc(part)
        if not piece or _is_dateish(piece):
            continue
        lowered = piece.casefold()
        if blob and lowered in blob.casefold():
            continue
        if any(lowered == item.casefold() for item in seen):
            continue
        seen.append(piece)
        blob = " ".join(seen)
    return blob[:LOCATION_WRITE_MAX]


def _meet_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in _MEET_URL.finditer(text or ""):
        url = match.group(0).rstrip(").,;；，]>\"'")
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        urls.append(url)
    return urls


def _fallback_location(text: str) -> str:
    en = _EN_AT_PLACE.search(text or "")
    if en:
        return _clean_loc(en.group(1))
    cn = _CN_AT_PLACE.search(text or "")
    if cn:
        return _clean_loc(cn.group(1))
    return ""


def _extra_floor_room(text: str, location: str) -> str:
    blob = location or ""
    floor = ""
    room = ""
    floor_match = _FLOOR_TOKEN.search(text or "")
    if floor_match:
        number = floor_match.group(1) or floor_match.group(2)
        token = floor_match.group(0)
        floor = token if "楼" in token else f"Floor {number}"
    room_match = _EN_ROOM.search(text or "") or _CN_ROOM.search(text or "")
    if room_match:
        room = _clean_loc(room_match.group(0))
    else:
        code = _ROOM_CODE.search(text or "")
        if code:
            room = code.group(1)
    return _join_place(blob, floor, room)


def extract_location_notes(subject: str, body: str) -> tuple[str, str]:
    """Pull venue/location and extra instructions from any CN/EN event mail."""
    text = html_to_text("\n".join(part for part in (subject, body) if part))
    if not text:
        return "", ""

    loc_labels = {_norm_label(label) for label in _LOCATION_LABELS}
    note_labels = {_norm_label(label) for label in _NOTE_LABELS}
    skip_labels = {_norm_label(label) for label in _SKIP_LABELS}
    venue_parts: list[str] = []
    building = ""
    room = ""
    floor = ""
    note_lines: list[str] = []
    note_seen: set[str] = set()
    labeled_notes = 0

    def add_note(label: str, value: str, *, phrase: bool = True) -> None:
        text_value = _short_phrase(value) if phrase else _clip_field(value, LOCATION_WRITE_MAX)
        if not text_value or _is_dateish(text_value):
            return
        if phrase and len(text_value) > 100 and len(text_value) > max(40, len(text) // 4):
            return
        key = fold_search(text_value)
        if key in note_seen:
            return
        note_seen.add(key)
        pretty = label.strip()
        line = f"{pretty}：{text_value}" if pretty else text_value
        cap = LOCATION_WRITE_MAX + 8 if not phrase else _NOTE_LINE_MAX + 12
        note_lines.append(line[:cap])

    for label, value in _labeled_fields(text):
        if label in skip_labels:
            continue
        if label in loc_labels:
            if label in {"building", "大楼", "大厦"}:
                building = building or value
            elif label in {"room", "教室", "会议室", "室", "hall"}:
                room = room or value
            elif label in {"楼层", "楼"}:
                floor = floor or value
            else:
                venue_parts.append(value)
            continue
        if label in note_labels:
            before = len(note_lines)
            add_note(label, value)
            if len(note_lines) > before:
                labeled_notes += 1

    location = _join_place(*(venue_parts + [building, floor, room]))
    if not location:
        location = _fallback_location(text)
    if location:
        location = _extra_floor_room(text, location)
    elif building or room or floor:
        location = _join_place(building, floor, room)

    urls = _meet_urls(text)
    first_url = urls[0] if urls else ""
    if location and _ONLINE_LOC.match(location) and first_url:
        location = _join_place(location, first_url)
    elif not location and first_url:
        location = first_url[:LOCATION_WRITE_MAX]
    for url in urls:
        if location and url.casefold() in location.casefold():
            continue
        add_note("链接", url, phrase=False)

    if not labeled_notes:
        for match in _NOTE_LOOSE.finditer(text):
            snippet = _short_phrase(match.group(1))
            if snippet and not _is_dateish(snippet):
                add_note("", snippet)

    notes = "\n".join(note_lines[:8]).strip()[:NOTES_FIELD_MAX]
    if location and notes:
        kept: list[str] = []
        for line in notes.split("\n"):
            payload = re.sub(r"^[^：:]{1,20}[:：]\s*", "", line).strip()
            if payload and payload.casefold() in location.casefold() and len(payload) <= len(location):
                continue
            kept.append(line)
        notes = "\n".join(kept).strip()
    return location, notes


def attach_location_notes(
    events: list[ExtractedEvent],
    subject: str,
    body: str,
) -> list[ExtractedEvent]:
    if not events:
        return events
    location, notes = extract_location_notes(subject, body)
    for event in events:
        if not event.location:
            event.location = location
        if not event.notes:
            event.notes = notes
    return events


def local_tz() -> ZoneInfo:
    tz = get_localzone()
    if isinstance(tz, ZoneInfo):
        return tz
    return ZoneInfo(str(tz))


def ensure_aware(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _clip_snippet(text: str, start: int, end: int, radius: int = 90) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    snippet = text[lo:hi].replace("\n", " ").strip()
    if lo > 0:
        snippet = "…" + snippet
    if hi < len(text):
        snippet = snippet + "…"
    return snippet


def _nearby_score(text: str, start: int, end: int) -> float:
    window = text[max(0, start - 80) : min(len(text), end + 80)].lower()
    score = 0.0
    for word in POSITIVE_KEYWORDS:
        if word.lower() in window:
            score += 0.12
    for word in NEGATIVE_HINTS:
        if word in window:
            score -= 0.2
    return min(score, 0.45)


def _parse_time_near(text: str, around: int) -> time | None:
    window = text[around : min(len(text), around + 48)]
    return parse_time(window) or parse_time(text[max(0, around - 24) : around + 48])


def parse_time(fragment: str) -> time | None:
    if not fragment:
        return None
    frag = fragment.strip()
    period = None
    period_match = re.search(
        r"(凌晨|早上|早晨|上午|中午|下午|傍晚|晚上|今晚|明晚|afternoon|morning|evening|night|noon|am|pm|a\.m\.|p\.m\.)",
        frag,
        re.I,
    )
    if period_match:
        period = period_match.group(1).lower().replace(".", "")

    patterns = [
        r"(\d{1,2})\s*[:：时点]\s*(\d{2})\s*分?",
        r"(\d{1,2})\s*点\s*半",
        r"(\d{1,2})\s*[点时]",
        r"(\d{1,2})\s*[:.]\s*(\d{2})\s*(am|pm)?",
    ]
    hour = None
    minute = 0
    matched_pm = None
    for pattern in patterns:
        m = re.search(pattern, frag, re.I)
        if not m:
            continue
        hour = int(m.group(1))
        if "半" in pattern:
            minute = 30
        elif m.lastindex and m.lastindex >= 2 and m.group(2) and m.group(2).isdigit():
            minute = int(m.group(2))
        if m.lastindex and m.lastindex >= 3 and m.group(3):
            matched_pm = m.group(3).lower()
        break
    token = (matched_pm or period or "").lower()
    if hour is None:
        if token in {"下午", "傍晚", "afternoon"}:
            return time(15, 0)
        if token in {"晚上", "今晚", "明晚", "evening", "night"}:
            return time(19, 0)
        if token in {"上午", "早上", "早晨", "morning"}:
            return time(10, 0)
        if token in {"中午", "noon"}:
            return time(12, 0)
        return None
    if minute >= 60 or hour > 24:
        return None
    if token in {"pm", "p.m", "下午", "傍晚", "晚上", "今晚", "明晚", "afternoon", "evening", "night"} and hour < 12:
        hour += 12
    if token in {"am", "a.m", "凌晨", "早上", "早晨", "上午"} and hour == 12:
        hour = 0
    if token == "中午" and hour < 11:
        hour = 12
    if hour == 24:
        hour = 0
    if hour > 23:
        return None
    return time(hour, minute)


def _this_or_next_weekday(ref: datetime, weekday: int, week: str | None) -> datetime:
    ref_date = ref.date()
    this_monday = ref_date - timedelta(days=ref_date.weekday())
    if week in {"下", "下个", "下週", "next"}:
        target = this_monday + timedelta(days=7 + weekday)
    elif week in {"本", "这", "這", "this"}:
        target = this_monday + timedelta(days=weekday)
    else:
        days_ahead = (weekday - ref_date.weekday()) % 7
        target = ref_date + timedelta(days=days_ahead)
    return datetime(target.year, target.month, target.day, tzinfo=ref.tzinfo)


def _apply_time(day: datetime, t: time | None, all_day_hours: int = 1) -> tuple[datetime, datetime, bool]:
    tz = day.tzinfo
    if t is None:
        start = datetime(day.year, day.month, day.day, tzinfo=tz)
        end = start + timedelta(days=1)
        return start, end, True
    start = datetime(day.year, day.month, day.day, t.hour, t.minute, tzinfo=tz)
    end = start + timedelta(hours=all_day_hours)
    return start, end, False


def _valid_future(start: datetime, now: datetime) -> bool:
    if start < now - timedelta(hours=PAST_GRACE_HOURS):
        return False
    if start > now + timedelta(days=MAX_FUTURE_DAYS):
        return False
    return True


def _title_from_context(subject: str, text: str, match_start: int, match_end: int) -> str:
    subject = (subject or "").strip()
    if subject and not re.fullmatch(r"(通知|公告|转发|fw|fwd|re:.*|自动回复)", subject, re.I):
        cleaned = re.sub(r"^(re|fw|fwd|转发)\s*[:：]\s*", "", subject, flags=re.I).strip()
        if cleaned:
            return cleaned[:80]
    window = text[max(0, match_start - 40) : min(len(text), match_end + 80)]
    sentence = re.split(r"[。！？\n]", window)[0].strip(" ，,;；")
    sentence = re.sub(r"\s+", " ", sentence)
    return (sentence or subject or "邮件中的日程")[:80]


def _add_event(
    events: list[ExtractedEvent],
    subject: str,
    text: str,
    span_start: int,
    span_end: int,
    start: datetime,
    end: datetime,
    all_day: bool,
    matched: str,
    now: datetime,
    extra_confidence: float = 0.0,
    fuzzy: bool = False,
) -> None:
    if not _valid_future(start, now):
        return
    snippet = _clip_snippet(text, span_start, span_end)
    confidence = 0.42 + extra_confidence
    if not all_day:
        confidence += 0.22
    if fuzzy:
        confidence -= 0.08
    confidence += _nearby_score(text, span_start, span_end)
    if any(k.lower() in (subject or "").lower() for k in POSITIVE_KEYWORDS):
        confidence += 0.1
    confidence = max(0.2, min(confidence, 0.97))
    title = _title_from_context(subject, text, span_start, span_end)
    events.append(
        ExtractedEvent(
            title=title,
            start=start,
            end=end,
            all_day=all_day,
            snippet=snippet,
            matched_text=matched.strip(),
            confidence=round(confidence, 2),
            fuzzy=fuzzy,
            kind="event",
        )
    )


_CN_FULL = re.compile(r"(?P<y>\d{4})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*[日号]?")
_CN_MD = re.compile(r"(?<!\d)(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*[日号]")
_ISO = re.compile(r"(?<!\d)(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})(?!\d)")
_US = re.compile(r"(?<!\d)(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})(?!\d)")
_EN = re.compile(
    r"(?P<mon>january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\.?\s+"
    r"(?P<d>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*,\s*(?P<y>\d{4}))?",
    re.I,
)
_EN_DM = re.compile(
    r"(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(?P<mon>january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\.?"
    r"(?:\s*,?\s*(?P<y>\d{4}))?",
    re.I,
)
_CN_WEEK = re.compile(
    r"(?P<approx>大概|大约|约)?(?P<week>下个?|本|这|這)?(?:周|週|星期|礼拜|禮拜)(?P<w>[一二三四五六日天])(?P<around>左右|前后)?"
)
_EN_WEEK = re.compile(
    r"(?P<approx>around|about|roughly)?\s*(?P<week>next|this)?\s*(?P<w>monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thurs?|thu|fri|sat|sun)\b",
    re.I,
)
_RELATIVE = re.compile(r"(?P<rel>大后天|后天|今天|明天|今晚|明晚|today|tomorrow)")
_FUZZY_NEXT_WEEK = re.compile(r"下个?(?:周|週|星期|礼拜|禮拜)(?![一二三四五六日天])|next\s+week", re.I)
_FUZZY_THIS_WEEK = re.compile(r"(?:本|这|這)(?:周|週|星期|礼拜|禮拜)(?![一二三四五六日天])|this\s+week", re.I)
_FUZZY_NEXT_MONTH = re.compile(r"下个?月|next\s+month", re.I)
_FUZZY_MONTH_END = re.compile(r"(?<!\d月)(?:本)?月底|end\s+of\s+(?:the\s+)?month", re.I)
_FUZZY_MONTH_START = re.compile(r"(?<!\d月)(?:本)?月初|start\s+of\s+(?:the\s+)?month", re.I)
_FUZZY_MID_MONTH = re.compile(r"(?<!\d月)(?:本)?中旬|mid[- ]month", re.I)
_FUZZY_DAYS = re.compile(r"(?:这|這)?几天|这两天|几天后|in\s+a\s+few\s+days", re.I)
_FUZZY_IN_WEEK = re.compile(r"一周后|一星期后|in\s+a\s+week", re.I)
_FUZZY_EN_MONTH = re.compile(
    r"(?P<when>early|mid|late)\s+(?P<mon>january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\.?",
    re.I,
)
_FUZZY_CN_MONTH_PART = re.compile(r"(?P<m>\d{1,2})\s*月(?P<part>上旬|中旬|下旬|初|底)")
_RANGE_CN = re.compile(
    r"(?P<m1>\d{1,2})\s*月\s*(?P<d1>\d{1,2})\s*[日号]?\s*[-~～—至到]+\s*"
    r"(?:(?P<m2>\d{1,2})\s*月\s*)?(?P<d2>\d{1,2})\s*[日号]?"
)


def _safe_date(year: int, month: int, day: int, tz) -> datetime | None:
    try:
        return datetime(year, month, day, tzinfo=tz)
    except ValueError:
        return None


def extract_events(
    subject: str,
    body: str,
    received_at: datetime,
    now: datetime | None = None,
    tz: ZoneInfo | None = None,
) -> list[ExtractedEvent]:
    tz = tz or local_tz()
    received_at = ensure_aware(received_at, tz)
    now = ensure_aware(now or datetime.now(tz), tz)
    text = html_to_text("\n".join(part for part in (subject, body) if part))
    if not text:
        return []

    events: list[ExtractedEvent] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in occupied)

    def consume(span: tuple[int, int]) -> None:
        occupied.append(span)

    for m in _RANGE_CN.finditer(text):
        y = received_at.year
        m1, d1 = int(m["m1"]), int(m["d1"])
        m2 = int(m["m2"]) if m["m2"] else m1
        d2 = int(m["d2"])
        start_day = _safe_date(y, m1, d1, tz)
        end_day = _safe_date(y, m2, d2, tz)
        if not start_day or not end_day:
            continue
        if start_day < received_at - timedelta(days=30):
            start_day = start_day.replace(year=y + 1)
            end_day = end_day.replace(year=end_day.year + 1)
        if end_day < start_day:
            continue
        t = _parse_time_near(text, m.end())
        start, _, all_day = _apply_time(start_day, t)
        end = datetime(end_day.year, end_day.month, end_day.day, tzinfo=tz) + timedelta(days=1)
        if t:
            end = datetime(end_day.year, end_day.month, end_day.day, t.hour, t.minute, tzinfo=tz) + timedelta(hours=1)
            all_day = False
        _add_event(events, subject, text, m.start(), m.end(), start, end, all_day, m.group(0), now, extra_confidence=0.12)
        consume(m.span())

    def handle_ymd(year: int, month: int, day: int, match: re.Match, extra_confidence: float = 0.0) -> None:
        if overlaps(*match.span()):
            return
        day_dt = _safe_date(year, month, day, tz)
        if not day_dt:
            return
        t = _parse_time_near(text, match.end())
        start, end, all_day = _apply_time(day_dt, t)
        _add_event(
            events,
            subject,
            text,
            match.start(),
            match.end(),
            start,
            end,
            all_day,
            match.group(0),
            now,
            extra_confidence=extra_confidence,
        )
        consume(match.span())

    for m in _CN_FULL.finditer(text):
        handle_ymd(int(m["y"]), int(m["m"]), int(m["d"]), m, extra_confidence=0.16)

    for m in _ISO.finditer(text):
        handle_ymd(int(m["y"]), int(m["m"]), int(m["d"]), m, extra_confidence=0.14)

    for m in _US.finditer(text):
        month, day, year = int(m["m"]), int(m["d"]), int(m["y"])
        if month > 12 and day <= 12:
            month, day = day, month
        handle_ymd(year, month, day, m, extra_confidence=0.1)

    for m in _EN.finditer(text):
        month = EN_MONTH[m["mon"].lower().rstrip(".")]
        year = int(m["y"]) if m["y"] else received_at.year
        handle_ymd(year, month, int(m["d"]), m, extra_confidence=0.12)

    for m in _EN_DM.finditer(text):
        month = EN_MONTH[m["mon"].lower().rstrip(".")]
        year = int(m["y"]) if m["y"] else received_at.year
        handle_ymd(year, month, int(m["d"]), m, extra_confidence=0.12)

    for m in _CN_MD.finditer(text):
        if overlaps(*m.span()):
            continue
        month, day = int(m["m"]), int(m["d"])
        year = received_at.year
        day_dt = _safe_date(year, month, day, tz)
        if not day_dt:
            continue
        if day_dt.date() < (received_at - timedelta(days=14)).date():
            day_dt = _safe_date(year + 1, month, day, tz)
            if not day_dt:
                continue
        t = _parse_time_near(text, m.end())
        start, end, all_day = _apply_time(day_dt, t)
        _add_event(events, subject, text, m.start(), m.end(), start, end, all_day, m.group(0), now, extra_confidence=0.08)
        consume(m.span())

    for m in _CN_WEEK.finditer(text):
        if overlaps(*m.span()):
            continue
        weekday = CN_WEEKDAY[m["w"]]
        week = m["week"]
        day_dt = _this_or_next_weekday(received_at, weekday, week)
        t = _parse_time_near(text, m.end())
        start, end, all_day = _apply_time(day_dt, t)
        fuzzy = bool(m["approx"] or m["around"])
        _add_event(
            events, subject, text, m.start(), m.end(), start, end, all_day, m.group(0), now,
            extra_confidence=0.06, fuzzy=fuzzy,
        )
        consume(m.span())

    for m in _EN_WEEK.finditer(text):
        if overlaps(*m.span()):
            continue
        weekday = EN_WEEKDAY[m["w"].lower()]
        week = (m["week"] or "").lower() or None
        day_dt = _this_or_next_weekday(received_at, weekday, week)
        t = _parse_time_near(text, m.end())
        start, end, all_day = _apply_time(day_dt, t)
        fuzzy = bool(m["approx"])
        _add_event(
            events, subject, text, m.start(), m.end(), start, end, all_day, m.group(0), now,
            extra_confidence=0.05, fuzzy=fuzzy,
        )
        consume(m.span())

    relative_map = {
        "今天": 0,
        "today": 0,
        "今晚": 0,
        "明天": 1,
        "tomorrow": 1,
        "明晚": 1,
        "后天": 2,
        "大后天": 3,
    }
    for m in _RELATIVE.finditer(text):
        if overlaps(*m.span()):
            continue
        key = m["rel"].lower()
        if key not in relative_map and m["rel"] not in relative_map:
            continue
        offset = relative_map.get(key, relative_map.get(m["rel"], None))
        if offset is None:
            continue
        day_dt = received_at + timedelta(days=offset)
        t = _parse_time_near(text, m.end())
        if m["rel"] in {"今晚", "明晚"} and t is None:
            t = time(19, 0)
        start, end, all_day = _apply_time(day_dt, t)
        _add_event(events, subject, text, m.start(), m.end(), start, end, all_day, m.group(0), now, extra_confidence=0.04)
        consume(m.span())

    def add_fuzzy_day(match: re.Match, day_dt: datetime | None, extra: float = 0.0) -> None:
        if not day_dt or overlaps(*match.span()):
            return
        start, end, all_day = _apply_time(day_dt, None)
        _add_event(
            events, subject, text, match.start(), match.end(), start, end, all_day,
            match.group(0), now, extra_confidence=extra, fuzzy=True,
        )
        consume(match.span())

    monday = received_at.date() - timedelta(days=received_at.weekday())
    for m in _FUZZY_NEXT_WEEK.finditer(text):
        add_fuzzy_day(m, datetime(monday.year, monday.month, monday.day, tzinfo=tz) + timedelta(days=7))
    for m in _FUZZY_THIS_WEEK.finditer(text):
        friday = datetime(monday.year, monday.month, monday.day, tzinfo=tz) + timedelta(days=4)
        if friday.date() < received_at.date():
            continue
        add_fuzzy_day(m, friday)
    for m in _FUZZY_NEXT_MONTH.finditer(text):
        y, mo = received_at.year, received_at.month + 1
        if mo == 13:
            y, mo = y + 1, 1
        add_fuzzy_day(m, _safe_date(y, mo, 1, tz))
    for m in _FUZZY_MONTH_END.finditer(text):
        last = monthrange(received_at.year, received_at.month)[1]
        add_fuzzy_day(m, _safe_date(received_at.year, received_at.month, last, tz))
    for m in _FUZZY_MONTH_START.finditer(text):
        day = _safe_date(received_at.year, received_at.month, 1, tz)
        if day and day.date() < received_at.date():
            y, mo = received_at.year, received_at.month + 1
            if mo == 13:
                y, mo = y + 1, 1
            day = _safe_date(y, mo, 1, tz)
        add_fuzzy_day(m, day)
    for m in _FUZZY_MID_MONTH.finditer(text):
        add_fuzzy_day(m, _safe_date(received_at.year, received_at.month, 15, tz))
    for m in _FUZZY_DAYS.finditer(text):
        add_fuzzy_day(m, received_at + timedelta(days=3))
    for m in _FUZZY_IN_WEEK.finditer(text):
        add_fuzzy_day(m, received_at + timedelta(days=7))
    part_day = {"上旬": 5, "初": 5, "中旬": 15, "下旬": 25, "底": 28}
    for m in _FUZZY_CN_MONTH_PART.finditer(text):
        month = int(m["m"])
        day = part_day.get(m["part"], 15)
        year = received_at.year
        day_dt = _safe_date(year, month, min(day, monthrange(year, month)[1]), tz)
        if day_dt and day_dt.date() < (received_at - timedelta(days=14)).date():
            day_dt = _safe_date(year + 1, month, min(day, monthrange(year + 1, month)[1]), tz)
        add_fuzzy_day(m, day_dt)
    en_part_day = {"early": 5, "mid": 15, "late": 25}
    for m in _FUZZY_EN_MONTH.finditer(text):
        month = EN_MONTH[m["mon"].lower().rstrip(".")]
        day = en_part_day[m["when"].lower()]
        year = received_at.year
        day_dt = _safe_date(year, month, day, tz)
        if day_dt and day_dt.date() < (received_at - timedelta(days=14)).date():
            day_dt = _safe_date(year + 1, month, day, tz)
        add_fuzzy_day(m, day_dt)

    unique: list[ExtractedEvent] = []
    seen: set[tuple[str, str]] = set()
    for event in sorted(events, key=lambda e: (-e.confidence, e.start)):
        key = (event.start.isoformat(timespec="minutes"), event.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return attach_location_notes(unique, subject, body)


_HOMEWORK = re.compile(
    r"(作业|功课|习题|预习|复习|阅读|看完|必读|必看|这本书|准备考试|备考|"
    r"homework|assignment|reading(?: list)?|finish (?:chapter|the chapter)|"
    r"prepare for (?:the )?exam|study for)",
    re.I,
)
_MEET_OPEN = re.compile(
    r"(约个时间|约时间|定个时间|确认时间|有空见面|方便见面|还没约|还没定时间|"
    r"约好了|还没赴约|找时间见面|"
    r"let me know when|when are you free|schedule a (?:time|meeting)|"
    r"let'?s (?:find a time|meet)|can we (?:find a time|meet)|pick a time)",
    re.I,
)
_FOLLOW = re.compile(
    r"(等你回复|请回复时间|还没回|waiting for (?:your )?reply|"
    r"please (?:reply|confirm).{0,12}time|follow up)",
    re.I,
)
_DATE_HINT = re.compile(
    r"\d{1,2}\s*月|星期|周[一二三四五六日天]|tomorrow|today|tonight|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{4}\s*[-/]|next week|this week|下周|本周|后天|明天",
    re.I,
)


def _sentence_around(text: str, index: int) -> str:
    start = max(0, text.rfind("。", 0, index), text.rfind("\n", 0, index), text.rfind(". ", 0, index))
    end_marks = [text.find(ch, index) for ch in "。\n"]
    end_marks.append(text.find(". ", index))
    ends = [i for i in end_marks if i != -1]
    end = min(ends) if ends else len(text)
    if start:
        start += 1
    return text[start:end]


def _add_task(
    tasks: list[ExtractedEvent],
    subject: str,
    text: str,
    match: re.Match,
    received_at: datetime,
    task_type: str,
    extra: float,
) -> None:
    snippet = _clip_snippet(text, match.start(), match.end())
    title = _title_from_context(subject, text, match.start(), match.end())
    if title in {"邮件中的日程", ""}:
        title = match.group(0).strip()[:80]
    tasks.append(
        ExtractedEvent(
            title=title[:80],
            start=received_at.replace(hour=0, minute=0, second=0, microsecond=0),
            end=received_at.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
            all_day=True,
            snippet=snippet,
            matched_text=match.group(0).strip(),
            confidence=round(min(0.72, 0.48 + extra), 2),
            fuzzy=True,
            kind="task",
            task_type=task_type,
        )
    )


def extract_tasks(
    subject: str,
    body: str,
    received_at: datetime,
    dated_events: list[ExtractedEvent] | None = None,
    tz: ZoneInfo | None = None,
) -> list[ExtractedEvent]:
    tz = tz or local_tz()
    received_at = ensure_aware(received_at, tz)
    text = html_to_text("\n".join(part for part in (subject, body) if part))
    if not text:
        return []
    lowered = text.lower()
    if any(hint in lowered for hint in NEGATIVE_HINTS):
        if len(text) > 400 and not _HOMEWORK.search(text[:800]):
            return []
    dated_events = dated_events or []
    tasks: list[ExtractedEvent] = []
    seen_types: set[str] = set()
    body_text = text[len(subject) :] if subject and text.startswith(subject) else text

    def consider(pattern: re.Pattern, task_type: str, extra: float, allow_with_dates: bool) -> None:
        if task_type in seen_types:
            return
        if dated_events and not allow_with_dates:
            return
        for match in pattern.finditer(text):
            sentence = _sentence_around(text, match.start())
            if _DATE_HINT.search(sentence):
                continue
            in_subject = bool(subject) and match.start() <= len(subject)
            if in_subject and (dated_events or pattern.search(body_text)):
                continue
            _add_task(tasks, subject, text, match, received_at, task_type, extra)
            seen_types.add(task_type)
            return

    consider(_HOMEWORK, "homework", 0.16, allow_with_dates=True)
    consider(_MEET_OPEN, "meet", 0.12, allow_with_dates=False)
    consider(_FOLLOW, "followup", 0.08, allow_with_dates=False)
    return attach_location_notes(tasks, subject, body)


_KEEP_HINTS = (
    "导师", "组会", "答辩", "教务", "作业", "功课", "canvas", "gradescope",
    "advisor", "professor", "registrar", "office hours", "ta hours",
)
_PROMO_UNSUB = re.compile(r"unsubscribe|退订|取消订阅|opt[-\s]?out|manage (?:your )?preferences", re.I)
_PROMO_SALE = re.compile(
    r"优惠券|coupon|限时折扣|限时特惠|flash sale|\d+\s?%\s*off|抢购|大促销|清仓|"
    r"this email was sent to|您收到此邮件是因为|view in browser|查看网页版",
    re.I,
)


def extract_promo(
    subject: str,
    body: str,
    received_at: datetime,
    tz: ZoneInfo | None = None,
    list_unsubscribe: bool = False,
    sender: str = "",
) -> list[ExtractedEvent]:
    tz = tz or local_tz()
    received_at = ensure_aware(received_at, tz)
    text = html_to_text("\n".join(part for part in (sender, subject, body) if part))
    if not text:
        return []
    lowered = text.lower()
    if any(hint in lowered for hint in _KEEP_HINTS):
        return []
    unsub = list_unsubscribe or bool(_PROMO_UNSUB.search(text))
    sale = bool(_PROMO_SALE.search(text))
    if not unsub and not sale:
        return []
    if sale and not unsub and len(text) < 80:
        return []
    match = _PROMO_UNSUB.search(text) or _PROMO_SALE.search(text)
    matched = "List-Unsubscribe" if list_unsubscribe and not match else (match.group(0) if match else "promo")
    snippet = _clip_snippet(text, match.start(), match.end()) if match else text[:160]
    title = (subject or matched).strip()[:80] or "促销邮件"
    start = received_at.replace(hour=0, minute=0, second=0, microsecond=0)
    items = [
        ExtractedEvent(
            title=title,
            start=start,
            end=start + timedelta(days=1),
            all_day=True,
            snippet=snippet,
            matched_text=matched.strip()[:80],
            confidence=round(0.58 + (0.12 if unsub else 0) + (0.06 if sale else 0), 2),
            fuzzy=False,
            kind="promo",
            task_type="ad",
        )
    ]
    return attach_location_notes(items, subject, body)


def extract_all(
    subject: str,
    body: str,
    received_at: datetime,
    now: datetime | None = None,
    tz: ZoneInfo | None = None,
    list_unsubscribe: bool = False,
    sender: str = "",
) -> list[ExtractedEvent]:
    events = extract_events(subject, body, received_at, now=now, tz=tz)
    tasks = extract_tasks(subject, body, received_at, dated_events=events, tz=tz)
    items = events + tasks
    if items:
        return items
    return extract_promo(
        subject, body, received_at, tz=tz, list_unsubscribe=list_unsubscribe, sender=sender
    )


_LATIN_TOKEN = re.compile(r"[a-z0-9']+", re.I)
_CJK_BLOCK = re.compile(r"[\u4e00-\u9fff]+")


def fold_search(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").casefold()


def fuzzy_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def match_threshold(query: str) -> float:
    n = len(fold_search(query))
    if n <= 2:
        return 0.9
    if n <= 4:
        return 0.8
    return 0.72


def _token_windows(token: str, query: str) -> list[str]:
    """Compare whole Latin tokens so 'exam' does not match 'example'."""
    if not token:
        return []
    return [token]


def _candidate_fragments(folded_text: str, folded_query: str) -> list[str]:
    fragments: list[str] = []
    qn = len(folded_query)
    for token in _LATIN_TOKEN.findall(folded_text):
        if abs(len(token) - qn) <= max(3, qn // 2) or qn <= len(token):
            fragments.extend(_token_windows(token, folded_query))
    q_cjk = len(re.findall(r"[\u4e00-\u9fff]", folded_query))
    if q_cjk:
        width = q_cjk
        for block in _CJK_BLOCK.findall(folded_text):
            if folded_query in block:
                fragments.append(folded_query)
                continue
            w = min(max(width, 1), len(block))
            step = 1 if len(block) <= 80 else max(1, w)
            for i in range(0, len(block) - w + 1, step):
                fragments.append(block[i : i + w])
    if len(folded_text) <= max(48, qn * 4):
        fragments.append(folded_text)
    return fragments


def best_fuzzy_hit(query: str, text: str) -> tuple[float, str]:
    """Return (score 0-1, matched fragment) for a typo-tolerant search."""
    q = fold_search(query)
    t = fold_search(text)
    if not q or not t:
        return 0.0, ""
    if any("\u4e00" <= ch <= "\u9fff" for ch in q):
        if q in t:
            return 1.0, q
    elif re.search(rf"(?<![a-z0-9]){re.escape(q)}(?![a-z0-9])", t):
        return 1.0, q
    best = 0.0
    frag = ""
    for candidate in _candidate_fragments(t, q):
        score = fuzzy_ratio(q, candidate)
        if score > best:
            best = score
            frag = candidate
            if best >= 0.99:
                break
    if not frag:
        return 0.0, ""
    return best, frag


def fuzzy_score(query: str, text: str) -> float:
    return best_fuzzy_hit(query, text)[0]


def _score_fields_one(term: str, *fields: str) -> tuple[float, str]:
    best = 0.0
    frag = ""
    for field in fields:
        score, hit = best_fuzzy_hit(term, field or "")
        if score > best:
            best = score
            frag = hit
    return best, frag


def score_search_fields(query: str, *fields: str) -> tuple[float, str]:
    """Score the typed query and any EN↔ZH synonyms against subject/body fields."""
    best = 0.0
    frag = ""
    for term in expand_query(query):
        score, hit = _score_fields_one(term, *fields)
        if score < match_threshold(term):
            continue
        if score > best:
            best = score
            frag = hit
    return best, frag


def snippet_around_query(text: str, query: str, fragment: str = "", radius: int = 90) -> str:
    hay = text or ""
    if not hay:
        return ""
    needle = fragment or query or ""
    if needle:
        match = re.search(re.escape(needle), hay, re.I)
        if match:
            return _clip_snippet(hay, match.start(), match.end(), radius=radius)
        folded = fold_search(hay)
        folded_needle = fold_search(needle)
        idx = folded.find(folded_needle) if folded_needle else -1
        if idx >= 0:
            end = min(len(hay), idx + max(len(needle), 1))
            return _clip_snippet(hay, idx, end, radius=radius)
    clipped = hay[: radius * 2].replace("\n", " ").strip()
    return clipped + ("…" if len(hay) > radius * 2 else "")
