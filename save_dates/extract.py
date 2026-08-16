from __future__ import annotations

import html as html_lib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from calendar import monthrange
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from tzlocal import get_localzone

from save_dates.config import BODY_CHAR_LIMIT, MAX_FUTURE_DAYS, PAST_GRACE_HOURS

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
    return unique


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
    return tasks


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
    return [
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
