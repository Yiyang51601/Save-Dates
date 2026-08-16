from __future__ import annotations

import re
from datetime import datetime

GENERIC_LABELS = {
    "outlook",
    "microsoft",
    "microsoft 365",
    "user",
    "administrator",
    "admin",
}


def given_name(account: str) -> str:
    raw = re.sub(r"\s*\([^)]*\)\s*", " ", account or "").strip()
    raw = re.sub(r"\s+", " ", raw)
    if not raw or raw.lower() in GENERIC_LABELS:
        return ""
    if "@" in raw and " " not in raw.split("@", 1)[0]:
        local = raw.split("@", 1)[0]
        token = re.split(r"[._+\-]", local)[0]
        if not token or token.lower() in GENERIC_LABELS:
            return ""
        return token[:1].upper() + token[1:]
    if "," in raw:
        after = raw.split(",", 1)[1].strip()
        if after:
            return after.split()[0]
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", raw):
        return raw if len(raw) == 2 else raw[1:]
    skip = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir"}
    tokens = [part for part in raw.split() if part.lower().rstrip(".") not in skip]
    if not tokens:
        return ""
    first = tokens[0].strip(".,")
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", first):
        return first if len(first) == 2 else first[1:]
    return first


def greeting_phrase(account: str, lang: str = "zh", now: datetime | None = None) -> str:
    name = given_name(account)
    hour = (now or datetime.now()).hour
    if lang == "en":
        if hour < 12:
            hello = "Good morning"
        elif hour < 18:
            hello = "Good afternoon"
        else:
            hello = "Good evening"
        return f"{hello}, {name}." if name else f"{hello}."
    if hour < 5 or hour >= 18:
        hello = "晚上好"
    elif hour < 11:
        hello = "早上好"
    elif hour < 13:
        hello = "中午好"
    else:
        hello = "下午好"
    return f"{hello}，{name}" if name else hello
