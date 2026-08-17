from __future__ import annotations

from typing import Any

from save_dates import db
from save_dates.config import (
    SEARCH_MAX_EMAILS,
    SEARCH_QUERY_MAX,
    SEARCH_RESULT_LIMIT,
    SEARCH_SCAN_DAYS,
)
from save_dates.display_title import attach_display_titles
from save_dates.extract import match_threshold, score_search_fields, snippet_around_query
from save_dates.priority import attach_priority

SEARCH_FIELDS = ("subject", "snippet", "title", "sender", "matched_text", "location", "notes")


def _clip_query(query: str) -> str:
    return (query or "").strip()[:SEARCH_QUERY_MAX]


def _query_usable(query: str) -> bool:
    text = _clip_query(query)
    if not text:
        return False
    if len(text) >= 2:
        return True
    return bool(next((ch for ch in text if "\u4e00" <= ch <= "\u9fff"), None))


def _score_item(query: str, item: dict[str, Any], extra: str = "") -> tuple[float, str]:
    fields = [str(item.get(name) or "") for name in SEARCH_FIELDS]
    if extra:
        fields.append(extra)
    return score_search_fields(query, *fields)


def _decorate(
    item: dict[str, Any],
    query: str,
    source: str,
    extra: str = "",
    extracted: bool | None = None,
) -> dict[str, Any]:
    score, highlight = _score_item(query, item, extra=extra)
    snippet = str(item.get("snippet") or "")
    if highlight and snippet and highlight.lower() not in snippet.lower() and extra:
        snippet = snippet_around_query(extra, query, highlight)
    row = dict(item)
    row["score"] = round(float(score), 3)
    row["highlight"] = highlight
    row["source"] = source
    row["snippet"] = snippet
    if extracted is None:
        extracted = source != "mail" or bool(item.get("id"))
    row["extracted"] = bool(extracted)
    row.setdefault("status", item.get("status") or ("pending" if item.get("id") else ""))
    email_id = str(row.get("email_id") or "")
    mail_url = str(row.get("mail_url") or "")
    row["can_open_mail"] = bool(row.get("can_open_mail")) or (
        (bool(email_id) and not email_id.startswith("demo-")) or bool(mail_url)
    )
    return attach_priority(attach_display_titles(row))


def _dedup_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("email_id") or ""),
        str(item.get("start_at") or ""),
        str(item.get("title") or ""),
        str(item.get("kind") or "event"),
    )


def _rank_key(item: dict[str, Any]) -> tuple[str, float]:
    return (str(item.get("received_at") or ""), float(item.get("score") or 0))


def _merge(db_hits: list[dict[str, Any]], mail_hits: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    chosen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in mail_hits + db_hits:
        key = _dedup_key(item)
        current = chosen.get(key)
        if current is None:
            chosen[key] = item
            continue
        prefer_db = bool(item.get("id")) and not current.get("id")
        newer = _rank_key(item) > _rank_key(current)
        if prefer_db or (bool(item.get("id")) == bool(current.get("id")) and newer):
            chosen[key] = item
    ranked = sorted(chosen.values(), key=_rank_key, reverse=True)
    return ranked[:limit]


def search_saved(query: str, limit: int = SEARCH_RESULT_LIMIT) -> list[dict[str, Any]]:
    query = _clip_query(query)
    if not _query_usable(query):
        return []
    threshold = match_threshold(query)
    hits: list[dict[str, Any]] = []
    for item in db.list_searchable(limit=200):
        row = _decorate(item, query, "saved")
        if row["score"] < threshold:
            continue
        hits.append(row)
    hits.sort(key=_rank_key, reverse=True)
    return hits[: max(limit * 2, limit)]


def search_live_mail(
    query: str,
    days: int = SEARCH_SCAN_DAYS,
    max_emails: int = SEARCH_MAX_EMAILS,
) -> dict[str, Any]:
    query = _clip_query(query)
    empty = {"items": [], "scanned": 0, "live": False}
    if not _query_usable(query):
        return empty
    from save_dates.watcher import watcher

    snap = watcher.snapshot()
    if not snap.connected:
        return empty
    days = max(1, min(int(days or SEARCH_SCAN_DAYS), SEARCH_SCAN_DAYS))
    max_emails = max(10, min(int(max_emails or SEARCH_MAX_EMAILS), SEARCH_MAX_EMAILS))
    try:
        result = watcher.search_mail(query, days=days, max_emails=max_emails)
    except Exception:
        return empty
    items = result.get("items") or []
    return {
        "items": items,
        "scanned": int(result.get("scanned") or 0),
        "live": True,
    }


def _promote_extracted(items: list[dict[str, Any]]) -> int:
    """Insert extracted events/tasks as pending review items. Mail-only hits stay display-only."""
    added = 0
    for item in items:
        if not item.get("extracted"):
            continue
        if item.get("id"):
            continue
        existing = db.find_candidate_match(
            str(item.get("email_id") or ""),
            str(item.get("title") or ""),
            str(item.get("start_at") or ""),
            str(item.get("kind") or "event"),
            str(item.get("task_type") or ""),
        )
        if existing:
            item["id"] = existing["id"]
            item["status"] = existing["status"]
            item["can_open_mail"] = existing.get("can_open_mail", item.get("can_open_mail"))
            continue
        if db.insert_candidates([item]):
            added += 1
            found = db.find_candidate_match(
                str(item.get("email_id") or ""),
                str(item.get("title") or ""),
                str(item.get("start_at") or ""),
                str(item.get("kind") or "event"),
                str(item.get("task_type") or ""),
            )
            if found:
                item["id"] = found["id"]
                item["status"] = found["status"]
    return added


def run_search(
    query: str,
    days: int | None = None,
    max_emails: int | None = None,
    limit: int = SEARCH_RESULT_LIMIT,
) -> dict[str, Any]:
    query = _clip_query(query)
    if not _query_usable(query):
        return {"q": query, "items": [], "scanned": 0, "live": False, "added": 0}
    saved = search_saved(query, limit=limit)
    live = search_live_mail(query, days=days or SEARCH_SCAN_DAYS, max_emails=max_emails or SEARCH_MAX_EMAILS)
    items = _merge(saved, live.get("items") or [], limit=limit)
    added = _promote_extracted(items)
    if added:
        from save_dates.watcher import watcher

        watcher.notify(added)
    return {
        "q": query,
        "items": items,
        "scanned": int(live.get("scanned") or 0),
        "live": bool(live.get("live")),
        "added": added,
    }
