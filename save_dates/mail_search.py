from __future__ import annotations

import re

# Campus / event terms only. Unknown words are still searched as typed.
SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "orientation",
        "orientations",
        "orientation week",
        "o-week",
        "迎新",
        "迎新会",
        "迎新周",
        "迎新活动",
        "入学",
        "入学教育",
    ),
    (
        "deadline",
        "deadlines",
        "due date",
        "cutoff",
        "截止",
        "截止日期",
        "截止日",
    ),
    (
        "exam",
        "exams",
        "midterm",
        "final exam",
        "finals",
        "考试",
        "期中",
        "期末",
        "测验",
    ),
    (
        "meeting",
        "meetings",
        "会议",
        "组会",
        "开会",
        "例会",
    ),
    (
        "lecture",
        "lectures",
        "talk",
        "seminar",
        "讲座",
        "报告会",
        "公开课",
    ),
    (
        "interview",
        "interviews",
        "面试",
    ),
    (
        "workshop",
        "workshops",
        "培训",
        "工作坊",
    ),
    (
        "register",
        "registration",
        "rsvp",
        "sign-up",
        "signup",
        "报名",
        "注册",
    ),
    (
        "office hours",
        "office hour",
        "答疑",
        "答疑时间",
    ),
    (
        "defense",
        "defence",
        "答辩",
    ),
    (
        "homework",
        "assignment",
        "assignments",
        "作业",
    ),
    (
        "event",
        "events",
        "activity",
        "活动",
    ),
    (
        "ceremony",
        "典礼",
        "仪式",
    ),
    (
        "open day",
        "open house",
        "开放日",
        "校园开放日",
    ),
    (
        "advisor",
        "adviser",
        "supervisor",
        "导师",
    ),
)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'.-]*|[\u4e00-\u9fff]+")
_STOP = {
    "a",
    "an",
    "and",
    "at",
    "dr",
    "for",
    "in",
    "mr",
    "mrs",
    "ms",
    "of",
    "on",
    "or",
    "prof",
    "the",
    "to",
    "的",
    "了",
    "和",
    "与",
}


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _term_in(term: str, haystack_folded: str) -> bool:
    needle = term.casefold()
    if not needle:
        return False
    if _has_cjk(term):
        return needle in haystack_folded
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack_folded) is not None


def expand_query(query: str) -> list[str]:
    """Raw query first, then tokens, then EN↔ZH synonyms for known campus terms."""
    raw = " ".join((query or "").split())
    if not raw:
        return []
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        text = term.strip()
        if not text:
            return
        key = text.casefold()
        if key in seen:
            return
        seen.add(key)
        terms.append(text)

    add(raw)
    for token in _TOKEN_RE.findall(raw):
        if token.casefold() in _STOP:
            continue
        if _has_cjk(token) or len(token) >= 2:
            add(token)
    folded = raw.casefold()
    for group in SYNONYM_GROUPS:
        if any(_term_in(term, folded) for term in group):
            for term in group:
                add(term)
    return terms
