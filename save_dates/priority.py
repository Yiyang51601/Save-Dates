"""Local priority for the pending review list. No user setup."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from save_dates.extract import ensure_aware, local_tz

_URGENT = re.compile(
    r"\b(urgent|asap|immediately|eod)\b|as soon as|"
    r"deadline|due\s*(?:date|by|on)?|\brsvp\b|"
    r"截止|紧急|务必|尽快|马上|立刻",
    re.I,
)
_ACADEMIC = re.compile(
    r"\.edu\b|university|college|professor|advisor|faculty|registrar|"
    r"教务|学院|老师|导师|教授|大学|学校|同学",
    re.I,
)
_WORK = re.compile(r"\b(slack|zoom|teams|calendar)\b|noreply@|no-reply@", re.I)
_PROMO_HINT = re.compile(
    r"unsubscribe|newsletter|promo|marketing|coupon|% off|退订|优惠|促销",
    re.I,
)

_KIND_BASE = {"event": 1000, "task": 400, "promo": 40}


def _parse_start(value: str, now: datetime) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ensure_aware(dt, now.tzinfo or local_tz())


def _blob(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "subject", "snippet", "matched_text", "sender")
    )


def _time_points(item: dict[str, Any], now: datetime) -> int:
    kind = str(item.get("kind") or "event")
    if kind != "event":
        return 0
    start = _parse_start(str(item.get("start_at") or ""), now)
    if start is None:
        return 0
    hours = (start - now).total_seconds() / 3600.0
    if hours <= 0:
        return 48
    if hours <= 24:
        return 50
    if hours <= 48:
        return 42
    if hours <= 24 * 7:
        return 30
    if hours <= 24 * 14:
        return 18
    if hours <= 24 * 30:
        return 10
    return 4


def _urgency_points(blob: str) -> int:
    if not blob:
        return 0
    if _URGENT.search(blob):
        return 28
    return 0


def _sender_points(item: dict[str, Any], blob: str) -> int:
    kind = str(item.get("kind") or "event")
    sender = str(item.get("sender") or "")
    mailbox = str(item.get("mailbox") or "")
    hay = f"{sender} {mailbox} {blob}"
    score = 0
    if _ACADEMIC.search(hay):
        score += 10
    elif _WORK.search(hay):
        score += 5
    if kind == "promo" or _PROMO_HINT.search(hay):
        score -= 16
    return score


def priority_score(item: dict[str, Any], now: datetime | None = None) -> float:
    now = now or datetime.now(local_tz())
    kind = str(item.get("kind") or "event")
    base = _KIND_BASE.get(kind, 400)
    blob = _blob(item)
    return float(base + _time_points(item, now) + _urgency_points(blob) + _sender_points(item, blob))


def priority_band(score: float, item: dict[str, Any] | None = None) -> str:
    kind = str((item or {}).get("kind") or "event")
    if kind == "promo" or score < 420:
        return "low"
    if kind == "event" and score >= 1030:
        return "high"
    if kind == "task" and score >= 428:
        return "high"
    if score >= 1000 or (kind == "task" and score >= 410):
        return "medium"
    return "low"


def attach_priority(item: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    row = dict(item)
    score = priority_score(row, now=now)
    row["priority"] = round(score, 1)
    row["priority_band"] = priority_band(score, row)
    return row


def sort_pending(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda row: (
            -float(row.get("priority") or 0),
            str(row.get("start_at") or ""),
            int(row.get("id") or 0),
        ),
    )
