"""Chinese display titles for review cards. Glossary first, then optional network."""

from __future__ import annotations

import re
from typing import Any

from save_dates.translator import cache_get, enqueue_translation, translate_to_zh

_CJK = re.compile(r"[\u4e00-\u9fff]")
_PREFIX = re.compile(r"^(re|fw|fwd|转发)\s*[:：]\s*", re.I)

# More specific patterns first.
_EVENT_KINDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"orientation|welcome week|迎新", re.I), "迎新"),
    (re.compile(r"open\s*day|开放日", re.I), "开放日"),
    (re.compile(r"info\s*session|说明会", re.I), "说明会"),
    (re.compile(r"career\s*fair|招聘会|招聘", re.I), "招聘会"),
    (re.compile(r"commencement|graduation|毕业典礼|典礼", re.I), "典礼"),
    (re.compile(r"office\s*hours|答疑", re.I), "答疑时间"),
    (re.compile(r"webinar|网络研讨", re.I), "网络研讨会"),
    (re.compile(r"workshop|工作坊", re.I), "工作坊"),
    (re.compile(r"seminar|研讨", re.I), "研讨会"),
    (re.compile(r"forum|论坛", re.I), "论坛"),
    (re.compile(r"lecture|talk\b|讲座", re.I), "讲座"),
    (re.compile(r"midterm|final\b|exam|考试|期中|期末", re.I), "考试"),
    (re.compile(r"deadline|due\s+date|due\s+by|截止", re.I), "截止日期"),
    (re.compile(r"interview|面试", re.I), "面试"),
    (re.compile(r"eventbrite|\brsvp\b|invitation", re.I), "活动邀请"),
    (re.compile(r"training|培训", re.I), "培训"),
    (re.compile(r"meeting|standup|kickoff|组会|会议", re.I), "会议"),
    (re.compile(r"event\b|活动", re.I), "活动"),
]

_TASK_ZH = {"homework": "作业", "meet": "待约", "followup": "跟进"}
_PROMO_PAT = re.compile(r"flash\s*sale|coupon|%\s*off|sale\b|折扣|优惠|清仓|促销", re.I)


def has_chinese(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _clean(text: str) -> str:
    return _PREFIX.sub("", (text or "").strip())


def chinese_from_text(text: str) -> str:
    text = _clean(text)
    if not text or not has_chinese(text):
        return ""
    parts = [part.strip() for part in re.split(r"\s*[|/／·•]\s*", text) if part.strip()]
    cjk_parts = [part for part in parts if has_chinese(part)]
    if cjk_parts:
        return max(cjk_parts, key=lambda part: (len(_CJK.findall(part)), len(part)))[:80]
    return text[:80]


def _kind_label(blob: str, kind: str, task_type: str) -> str:
    if kind == "task":
        return _TASK_ZH.get(task_type or "", "待办")
    if kind == "promo":
        return "促销广告" if _PROMO_PAT.search(blob) else "广告"
    for pattern, label in _EVENT_KINDS:
        if pattern.search(blob):
            return label
    return "日程"


def chinese_display_title(
    title: str = "",
    subject: str = "",
    snippet: str = "",
    kind: str = "event",
    task_type: str = "",
) -> str:
    for raw in (title, subject, snippet):
        found = chinese_from_text(raw)
        if found:
            return found
    blob = " ".join(part for part in (title, subject, snippet) if part)
    label = _kind_label(blob, kind, task_type)
    english = _clean(title) or _clean(subject)
    if not english:
        return label
    short = english[:48].rstrip(" .,:;/-")
    if short and short != label:
        return f"{label}：{short}"[:80]
    return label


def needs_translation(text: str) -> bool:
    raw = text or ""
    if not re.search(r"[A-Za-z]{3,}", raw):
        return False
    latin = len(re.findall(r"[A-Za-z]", raw))
    cjk = len(_CJK.findall(raw))
    return latin >= 8 and latin > cjk


def _want_zh_display() -> bool:
    try:
        from save_dates.db import get_settings

        return get_settings().get("lang") != "en"
    except Exception:
        return True


def _translate_short(text: str, *, wait: bool) -> str:
    source = (text or "").strip()
    if not source or not needs_translation(source):
        return ""
    cached = cache_get(source)
    if cached:
        return cached
    if wait:
        got = translate_to_zh(source, network=True)
        return got if has_chinese(got) else ""
    enqueue_translation(source)
    return ""


def _display_title_zh(
    title: str,
    subject: str,
    snippet: str,
    kind: str,
    task_type: str,
    *,
    wait: bool,
) -> str:
    for raw in (title, subject):
        found = chinese_from_text(raw)
        if found:
            return found
    english = _clean(title) or _clean(subject)
    translated = _translate_short(english, wait=wait)
    if translated:
        return translated[:80]
    return chinese_display_title(
        title=title,
        subject=subject,
        snippet=snippet,
        kind=kind,
        task_type=task_type,
    )


def attach_display_titles(item: dict[str, Any], *, wait: bool = False) -> dict[str, Any]:
    row = dict(item)
    title = str(row.get("title") or "")
    subject = str(row.get("subject") or "")
    snippet = str(row.get("snippet") or "")
    kind = str(row.get("kind") or "event")
    task_type = str(row.get("task_type") or "")
    glossary = chinese_display_title(
        title=title,
        subject=subject,
        snippet=snippet,
        kind=kind,
        task_type=task_type,
    )
    if _want_zh_display():
        row["title_zh"] = _display_title_zh(
            title, subject, snippet, kind, task_type, wait=wait
        )
        snippet_zh = snippet
        if snippet and needs_translation(snippet):
            translated = _translate_short(snippet[:200], wait=wait)
            if translated:
                snippet_zh = translated
        row["snippet_zh"] = snippet_zh
    else:
        row["title_zh"] = glossary
        row["snippet_zh"] = snippet
    return row


def calendar_write_title(item: dict[str, Any]) -> str:
    """Chinese display title for Outlook when the UI is 中; original otherwise."""
    raw = str(item.get("title") or "").strip()
    if not _want_zh_display():
        return raw
    if has_chinese(raw) and not needs_translation(raw):
        return raw
    translated = _display_title_zh(
        raw,
        str(item.get("subject") or ""),
        str(item.get("snippet") or ""),
        str(item.get("kind") or "event"),
        str(item.get("task_type") or ""),
        wait=True,
    )
    return translated or raw
