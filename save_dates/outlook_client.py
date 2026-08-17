from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from save_dates.config import (
    BODY_CHAR_LIMIT,
    CATEGORY_NAME,
    DEFAULT_MAX_EMAILS,
    DEFAULT_SCAN_DAYS,
    REMINDER_MINUTES_ALL_DAY,
    REMINDER_MINUTES_TIMED,
)
from save_dates.extract import (
    extract_all,
    html_to_text,
    local_tz,
    match_threshold,
    score_search_fields,
    snippet_around_query,
)

OL_MAIL = 43
OL_MEETING_REQUEST = 53
OL_FOLDER_INBOX = 6
OL_FOLDER_JUNK = 23
OL_APPOINTMENT = 1
OL_TASK = 3
OL_TENTATIVE = 1
PR_INTERNET_MESSAGE_ID = "http://schemas.microsoft.com/mapi/proptag/0x1035001F"
PR_LIST_UNSUBSCRIBE = "http://schemas.microsoft.com/mapi/proptag/0x1045001F"


def _to_naive_local(value: datetime) -> datetime:
    tz = local_tz()
    if value.tzinfo is None:
        return value
    return value.astimezone(tz).replace(tzinfo=None)


def _from_outlook_dt(value: Any) -> datetime:
    tz = local_tz()
    naive = datetime(
        int(value.year),
        int(value.month),
        int(value.day),
        int(getattr(value, "hour", 0)),
        int(getattr(value, "minute", 0)),
        int(getattr(value, "second", 0)),
    )
    return naive.replace(tzinfo=tz)


def _is_meeting_invite(item: Any) -> bool:
    try:
        class_id = int(item.Class)
    except Exception:
        class_id = 0
    if class_id in {OL_MEETING_REQUEST, 26, 54}:
        return True
    try:
        message_class = str(item.MessageClass or "")
    except Exception:
        message_class = ""
    if message_class.startswith("IPM.Schedule"):
        return True
    try:
        if int(getattr(item, "MeetingStatus", 0) or 0) != 0:
            return True
    except Exception:
        pass
    return False


def _safe_str(item: Any, name: str, default: str = "") -> str:
    try:
        value = getattr(item, name, default)
        return str(value or default)
    except Exception:
        return default


def _clipped_body(item: Any) -> str:
    try:
        raw = item.Body
    except Exception:
        raw = None
    if raw:
        text = str(raw)
        return text[:BODY_CHAR_LIMIT] if len(text) > BODY_CHAR_LIMIT else text
    html = _safe_str(item, "HTMLBody")
    if not html:
        return ""
    return html_to_text(html)[:BODY_CHAR_LIMIT]


def mail_to_candidates(item: Any, now: datetime | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Read one mail item and return (email_id, candidates). Caller should drop the COM item."""
    email_id = _safe_str(item, "EntryID")
    if not email_id:
        return "", []
    if _is_meeting_invite(item):
        return email_id, []
    try:
        class_id = int(item.Class)
    except Exception:
        return email_id, []
    if class_id != OL_MAIL:
        return email_id, []

    try:
        received = _from_outlook_dt(item.ReceivedTime)
    except Exception:
        return email_id, []

    subject = _safe_str(item, "Subject") or "(无主题)"
    sender = _safe_str(item, "SenderName") or _safe_str(item, "SenderEmailAddress") or "未知发件人"
    body = _clipped_body(item)
    internet_id = ""
    try:
        internet_id = str(item.PropertyAccessor.GetProperty(PR_INTERNET_MESSAGE_ID) or "")
    except Exception:
        internet_id = ""
    list_unsubscribe = False
    try:
        list_unsubscribe = bool(item.PropertyAccessor.GetProperty(PR_LIST_UNSUBSCRIBE))
    except Exception:
        list_unsubscribe = False
    store_id = ""
    mailbox = ""
    try:
        store = item.Parent.Store
        store_id = str(store.StoreID or "")
        mailbox = str(store.DisplayName or "")
    except Exception:
        store_id = ""

    now = now or datetime.now(local_tz())
    events = extract_all(subject, body, received, now=now, list_unsubscribe=list_unsubscribe, sender=sender)
    candidates = [
        {
            "email_id": email_id,
            "internet_id": internet_id,
            "store_id": store_id,
            "mailbox": mailbox,
            "subject": subject,
            "sender": sender,
            "received_at": received.isoformat(timespec="seconds"),
            "title": event.title,
            "start_at": event.start.isoformat(timespec="minutes"),
            "end_at": event.end.isoformat(timespec="minutes"),
            "all_day": event.all_day,
            "snippet": event.snippet,
            "matched_text": event.matched_text,
            "confidence": event.confidence,
            "fuzzy": event.fuzzy,
            "kind": event.kind,
            "task_type": event.task_type,
        }
        for event in events
    ]
    return email_id, candidates


def _mailbox_label(ns: Any, store: Any) -> str:
    store_id = str(getattr(store, "StoreID", "") or "")
    try:
        for account in ns.Accounts:
            try:
                if str(account.DeliveryStore.StoreID) == store_id:
                    return str(account.SmtpAddress or account.DisplayName or store.DisplayName or "")
            except Exception:
                continue
    except Exception:
        pass
    return str(getattr(store, "DisplayName", "") or "")


def _iter_inboxes(ns: Any):
    seen: set[str] = set()
    stores = []
    try:
        stores = list(ns.Stores)
    except Exception:
        stores = []
    if not stores:
        inbox = ns.GetDefaultFolder(OL_FOLDER_INBOX)
        yield inbox, str(ns.CurrentUser.Name), str(getattr(inbox, "StoreID", "") or "")
        return
    for store in stores:
        try:
            sid = str(store.StoreID)
            if not sid or sid in seen:
                continue
            seen.add(sid)
            inbox = store.GetDefaultFolder(OL_FOLDER_INBOX)
            yield inbox, _mailbox_label(ns, store), sid
        except Exception:
            continue


def scan_inbox_with_namespace(
    ns: Any,
    days: int = DEFAULT_SCAN_DAYS,
    max_emails: int = DEFAULT_MAX_EMAILS,
    skip_check: Callable[[str], bool] | None = None,
    sink: Callable[[list[dict[str, Any]]], None] | None = None,
    mark_seen: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    days = max(1, min(int(days), 90))
    max_emails = max(10, min(int(max_emails), 200))
    now = datetime.now(local_tz())
    cutoff = now - timedelta(days=days)
    scanned = 0
    skipped_invite = 0
    skipped_processed = 0
    found = 0
    mailboxes: list[str] = []

    for inbox, mailbox, _store_id in _iter_inboxes(ns):
        if scanned >= max_emails:
            break
        if mailbox and mailbox not in mailboxes:
            mailboxes.append(mailbox)
        try:
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for item in items:
            try:
                if scanned >= max_emails:
                    break
                try:
                    received = _from_outlook_dt(item.ReceivedTime)
                except Exception:
                    continue
                if received < cutoff:
                    break
                if _is_meeting_invite(item):
                    skipped_invite += 1
                    continue
                try:
                    class_id = int(item.Class)
                except Exception:
                    continue
                if class_id != OL_MAIL:
                    continue

                scanned += 1
                email_id = _safe_str(item, "EntryID")
                if not email_id:
                    continue
                if skip_check and skip_check(email_id):
                    skipped_processed += 1
                    continue

                _, candidates = mail_to_candidates(item, now=now)
                if mailbox:
                    for row in candidates:
                        row["mailbox"] = row.get("mailbox") or mailbox
                found += len(candidates)
                if candidates and sink:
                    sink(candidates)
                if mark_seen:
                    mark_seen(email_id)
            finally:
                item = None

    return {
        "scanned": scanned,
        "skipped_invite": skipped_invite,
        "skipped_processed": skipped_processed,
        "found": found,
        "account": str(ns.CurrentUser.Name),
        "mailboxes": mailboxes,
    }


def _search_hits_from_mail(
    query: str,
    item: Any,
    mailbox: str,
    now: datetime,
) -> list[dict[str, Any]]:
    subject = _safe_str(item, "Subject") or "(无主题)"
    sender = _safe_str(item, "SenderName") or _safe_str(item, "SenderEmailAddress") or "未知发件人"
    body = _clipped_body(item)
    score, highlight = score_search_fields(query, subject, sender, body)
    if score < match_threshold(query):
        return []
    _, candidates = mail_to_candidates(item, now=now)
    hits: list[dict[str, Any]] = []
    if candidates:
        for row in candidates:
            if mailbox:
                row["mailbox"] = row.get("mailbox") or mailbox
            field_score, field_hit = score_search_fields(
                query,
                row.get("subject") or "",
                row.get("snippet") or "",
                row.get("title") or "",
                row.get("sender") or "",
                row.get("matched_text") or "",
                body,
            )
            row["score"] = round(max(score, field_score), 3)
            row["highlight"] = field_hit or highlight
            row["source"] = "mail"
            row["extracted"] = True
            row["status"] = ""
            row["can_open_mail"] = True
            hits.append(row)
        return hits
    try:
        received = _from_outlook_dt(item.ReceivedTime)
        received_at = received.isoformat(timespec="seconds")
    except Exception:
        received_at = now.isoformat(timespec="seconds")
    snippet = snippet_around_query(body or subject, query, highlight)
    hits.append(
        {
            "email_id": _safe_str(item, "EntryID"),
            "internet_id": "",
            "store_id": "",
            "mail_url": "",
            "mailbox": mailbox,
            "subject": subject,
            "sender": sender,
            "received_at": received_at,
            "title": subject[:80],
            "start_at": received_at,
            "end_at": received_at,
            "all_day": False,
            "snippet": snippet,
            "matched_text": highlight,
            "confidence": round(min(0.7, 0.4 + score * 0.3), 2),
            "fuzzy": True,
            "kind": "event",
            "task_type": "",
            "score": round(score, 3),
            "highlight": highlight,
            "source": "mail",
            "extracted": False,
            "status": "",
            "can_open_mail": True,
        }
    )
    try:
        store = item.Parent.Store
        hits[-1]["store_id"] = str(store.StoreID or "")
        hits[-1]["mailbox"] = hits[-1]["mailbox"] or str(store.DisplayName or "")
    except Exception:
        pass
    return hits


def search_recent_mail_with_namespace(
    ns: Any,
    query: str,
    days: int = DEFAULT_SCAN_DAYS,
    max_emails: int = DEFAULT_MAX_EMAILS,
) -> dict[str, Any]:
    query = (query or "").strip()
    days = max(1, min(int(days), 90))
    max_emails = max(10, min(int(max_emails), 200))
    now = datetime.now(local_tz())
    cutoff = now - timedelta(days=days)
    scanned = 0
    hits: list[dict[str, Any]] = []
    if not query:
        return {"items": [], "scanned": 0}

    for inbox, mailbox, _store_id in _iter_inboxes(ns):
        if scanned >= max_emails:
            break
        try:
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for item in items:
            try:
                if scanned >= max_emails:
                    break
                try:
                    received = _from_outlook_dt(item.ReceivedTime)
                except Exception:
                    continue
                if received < cutoff:
                    break
                if _is_meeting_invite(item):
                    continue
                try:
                    class_id = int(item.Class)
                except Exception:
                    continue
                if class_id != OL_MAIL:
                    continue
                scanned += 1
                hits.extend(_search_hits_from_mail(query, item, mailbox, now))
            finally:
                item = None
    return {"items": hits, "scanned": scanned}


def create_calendar_event_with_app(
    app: Any,
    title: str,
    start: datetime,
    end: datetime,
    all_day: bool,
    body: str,
) -> str:
    appt = app.CreateItem(OL_APPOINTMENT)
    appt.Subject = title[:255]
    appt.Start = _to_naive_local(start)
    appt.End = _to_naive_local(end)
    appt.AllDayEvent = bool(all_day)
    appt.Body = body
    appt.BusyStatus = OL_TENTATIVE
    appt.Categories = CATEGORY_NAME
    appt.ReminderSet = True
    appt.ReminderMinutesBeforeStart = (
        REMINDER_MINUTES_ALL_DAY if all_day else REMINDER_MINUTES_TIMED
    )
    appt.Save()
    entry_id = str(appt.EntryID)
    return entry_id


def create_task_with_app(app: Any, title: str, body: str) -> str:
    task = app.CreateItem(OL_TASK)
    task.Subject = title[:255]
    task.Body = body
    try:
        task.Categories = CATEGORY_NAME
    except Exception:
        pass
    task.Save()
    return str(task.EntryID)


def _get_item(ns: Any, entry_id: str, store_id: str | None = None) -> Any:
    item = None
    if store_id:
        try:
            item = ns.GetItemFromID(entry_id, store_id)
        except Exception:
            item = None
    if item is None:
        try:
            item = ns.GetItemFromID(entry_id)
        except Exception:
            item = None
    if item is None:
        try:
            for store in ns.Stores:
                try:
                    item = ns.GetItemFromID(entry_id, store.StoreID)
                    if item:
                        break
                except Exception:
                    continue
        except Exception:
            item = None
    if item is None:
        raise RuntimeError("mail_not_found")
    return item


def delete_item_with_namespace(ns: Any, entry_id: str) -> None:
    if not entry_id:
        return
    item = _get_item(ns, entry_id)
    item.Delete()


def _folder_for_store(ns: Any, folder_id: int, store_id: str | None = None) -> Any:
    if store_id:
        try:
            for store in ns.Stores:
                if str(store.StoreID) == str(store_id):
                    return store.GetDefaultFolder(folder_id)
        except Exception:
            pass
    return ns.GetDefaultFolder(folder_id)


def move_mail_with_namespace(ns: Any, entry_id: str, folder_id: int, store_id: str | None = None) -> str:
    item = _get_item(ns, entry_id, store_id)
    folder = _folder_for_store(ns, folder_id, store_id)
    moved = item.Move(folder)
    return str(getattr(moved, "EntryID", "") or entry_id)


def display_mail(ns: Any, entry_id: str, store_id: str | None = None) -> None:
    if not entry_id or str(entry_id).startswith("demo-"):
        raise RuntimeError("mail_is_demo")
    item = _get_item(ns, entry_id, store_id)
    item.Display(False)
    try:
        inspector = item.GetInspector
        inspector.Activate()
    except Exception:
        pass
    try:
        ns.Application.ActiveWindow.Activate()
    except Exception:
        pass
