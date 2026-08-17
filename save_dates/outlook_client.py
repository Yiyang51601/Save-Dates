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
from save_dates.display_title import attach_display_titles
from save_dates.extract import (
    ExtractedEvent,
    extract_all,
    extract_location_notes,
    html_to_text,
    local_tz,
    match_threshold,
    score_search_fields,
    snippet_around_query,
)

OL_MAIL = 43
OL_APPOINTMENT_ITEM = 26
OL_MEETING_REQUEST = 53
OL_MEETING_CANCELLATION = 54
OL_FOLDER_INBOX = 6
OL_FOLDER_JUNK = 23
OL_APPOINTMENT = 1
OL_TASK = 3
OL_TENTATIVE = 1
OL_MAIL_ITEM_TYPE = 0
OL_EXCHANGE_PUBLIC_FOLDER = 1
PR_INTERNET_MESSAGE_ID = "http://schemas.microsoft.com/mapi/proptag/0x1035001F"
PR_LIST_UNSUBSCRIBE = "http://schemas.microsoft.com/mapi/proptag/0x1045001F"
PR_STORE_SMTP = (
    "http://schemas.microsoft.com/mapi/proptag/0x39FE001F",
    "http://schemas.microsoft.com/mapi/proptag/0x5D01001F",
)
_SCANNABLE_CLASSES = {
    OL_MAIL,
    OL_APPOINTMENT_ITEM,
    OL_MEETING_REQUEST,
    OL_MEETING_CANCELLATION,
}
_INBOX_NAMES = {
    "inbox",
    "收件箱",
    "boîte de réception",
    "posta in arrivo",
    "bandeja de entrada",
    "posteingang",
}
_SKIP_STORE_NAMES = ("public folders", "internet calendar", "rss", "sharepoint")


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


def _item_class(item: Any) -> int:
    try:
        return int(item.Class)
    except Exception:
        return 0


def _is_meeting_invite(item: Any) -> bool:
    class_id = _item_class(item)
    if class_id in {OL_APPOINTMENT_ITEM, OL_MEETING_REQUEST, OL_MEETING_CANCELLATION}:
        return True
    try:
        message_class = str(item.MessageClass or "")
    except Exception:
        message_class = ""
    return message_class.startswith("IPM.Schedule")


def _is_scannable_item(item: Any) -> bool:
    if _item_class(item) in _SCANNABLE_CLASSES:
        return True
    return _is_meeting_invite(item)


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


def _meeting_times(item: Any) -> tuple[datetime, datetime, bool] | None:
    for obj in (item,):
        try:
            start = _from_outlook_dt(obj.Start)
            end = _from_outlook_dt(obj.End)
            all_day = bool(getattr(obj, "AllDayEvent", False))
            return start, end, all_day
        except Exception:
            pass
    try:
        appt = item.GetAssociatedAppointment(False)
        start = _from_outlook_dt(appt.Start)
        end = _from_outlook_dt(appt.End)
        all_day = bool(getattr(appt, "AllDayEvent", False))
        return start, end, all_day
    except Exception:
        return None


def _events_from_item(
    item: Any,
    subject: str,
    body: str,
    sender: str,
    received: datetime,
    now: datetime,
    list_unsubscribe: bool,
) -> list[ExtractedEvent]:
    events = extract_all(
        subject,
        body,
        received,
        now=now,
        list_unsubscribe=list_unsubscribe,
        sender=sender,
    )
    if events or not _is_meeting_invite(item):
        return events
    times = _meeting_times(item)
    if not times:
        return []
    start, end, all_day = times
    if start.tzinfo is None:
        start = start.replace(tzinfo=now.tzinfo)
        end = end.replace(tzinfo=now.tzinfo)
    if start < now - timedelta(hours=12) or start > now + timedelta(days=400):
        return []
    title = (subject or "会议邀请")[:80]
    location, notes = extract_location_notes(subject, body)
    outlook_loc = _safe_str(item, "Location").strip()
    return [
        ExtractedEvent(
            title=title,
            start=start,
            end=end,
            all_day=all_day,
            snippet=(body or subject)[:160],
            matched_text=title,
            confidence=0.72,
            fuzzy=False,
            kind="event",
            location=location or outlook_loc[:255],
            notes=notes,
        )
    ]


def mail_to_candidates(item: Any, now: datetime | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Read one mail/meeting item and return (email_id, candidates). Caller should drop the COM item."""
    email_id = _safe_str(item, "EntryID")
    if not email_id:
        return "", []
    if not _is_scannable_item(item):
        return email_id, []

    try:
        received = _from_outlook_dt(item.ReceivedTime)
    except Exception:
        times = _meeting_times(item)
        if times is None:
            return email_id, []
        received = times[0]

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
    store_id, mailbox = _mailbox_from_item(item)

    now = now or datetime.now(local_tz())
    events = _events_from_item(item, subject, body, sender, received, now, list_unsubscribe)
    outlook_loc = _safe_str(item, "Location").strip()
    candidates = [
        attach_display_titles(
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
                "location": event.location or outlook_loc[:255],
                "notes": event.notes or "",
            }
        )
        for event in events
    ]
    return email_id, candidates


def _mailbox_from_item(item: Any) -> tuple[str, str]:
    store_id = ""
    mailbox = ""
    try:
        store = item.Parent.Store
        store_id = str(store.StoreID or "")
        mailbox = str(store.DisplayName or "")
        try:
            mailbox = _mailbox_label(item.Session, store) or mailbox
        except Exception:
            pass
    except Exception:
        return "", mailbox
    return store_id, mailbox


def _com_items(collection: Any) -> list[Any]:
    if collection is None:
        return []
    if isinstance(collection, (list, tuple)):
        return list(collection)
    items: list[Any] = []
    try:
        count = int(collection.Count)
        for index in range(1, count + 1):
            try:
                items.append(collection.Item(index))
            except Exception:
                continue
        if items:
            return items
    except Exception:
        pass
    try:
        return list(collection)
    except Exception:
        return []


def _account_smtp(account: Any) -> str:
    for attr in ("SmtpAddress", "DisplayName", "UserName"):
        try:
            value = str(getattr(account, attr, "") or "").strip()
        except Exception:
            value = ""
        if value:
            return value
    return ""


def _store_smtp(store: Any) -> str:
    try:
        accessor = store.PropertyAccessor
    except Exception:
        return ""
    for prop in PR_STORE_SMTP:
        try:
            value = str(accessor.GetProperty(prop) or "").strip()
        except Exception:
            value = ""
        if value and "@" in value:
            return value
    return ""


def _skip_store(store: Any) -> bool:
    try:
        if int(getattr(store, "ExchangeStoreType", 2) or 2) == OL_EXCHANGE_PUBLIC_FOLDER:
            return True
    except Exception:
        pass
    name = str(getattr(store, "DisplayName", "") or "").strip().lower()
    return any(token in name for token in _SKIP_STORE_NAMES)


def _inbox_for_store(store: Any) -> Any:
    try:
        inbox = store.GetDefaultFolder(OL_FOLDER_INBOX)
        if inbox is not None:
            return inbox
    except Exception:
        pass
    try:
        root = store.GetRootFolder()
    except Exception:
        return None
    for folder in _com_items(getattr(root, "Folders", None)):
        try:
            name = str(getattr(folder, "Name", "") or "").strip().lower()
        except Exception:
            name = ""
        if name in _INBOX_NAMES:
            return folder
        try:
            if int(getattr(folder, "DefaultItemType", -1) or -1) == OL_MAIL_ITEM_TYPE and name in _INBOX_NAMES:
                return folder
        except Exception:
            continue
    return None


def _mailbox_label(ns: Any, store: Any) -> str:
    store_id = str(getattr(store, "StoreID", "") or "")
    try:
        for account in _com_items(getattr(ns, "Accounts", None)):
            try:
                if str(account.DeliveryStore.StoreID) == store_id:
                    return _account_smtp(account) or str(store.DisplayName or "")
            except Exception:
                continue
    except Exception:
        pass
    return _store_smtp(store) or str(getattr(store, "DisplayName", "") or "")


def _iter_stores(ns: Any) -> list[Any]:
    stores = [store for store in _com_items(getattr(ns, "Stores", None)) if store is not None]
    if stores:
        return stores
    found: list[Any] = []
    seen: set[str] = set()
    for folder in _com_items(getattr(ns, "Folders", None)):
        try:
            store = folder.Store
            sid = str(getattr(store, "StoreID", "") or "")
            if store is None or (sid and sid in seen):
                continue
            if sid:
                seen.add(sid)
            found.append(store)
        except Exception:
            continue
    return found


def _iter_inboxes(ns: Any):
    seen: set[str] = set()
    stores = _iter_stores(ns)
    yielded = False
    for store in stores:
        try:
            if _skip_store(store):
                continue
            sid = str(getattr(store, "StoreID", "") or "")
            if sid and sid in seen:
                continue
            inbox = _inbox_for_store(store)
            if inbox is None:
                continue
            if sid:
                seen.add(sid)
            yielded = True
            yield inbox, _mailbox_label(ns, store), sid
        except Exception:
            continue
    if yielded:
        return
    try:
        inbox = ns.GetDefaultFolder(OL_FOLDER_INBOX)
        yield inbox, str(ns.CurrentUser.Name), str(getattr(inbox, "StoreID", "") or "")
    except Exception:
        return


def list_mailbox_report(ns: Any) -> dict[str, list[str]]:
    readable: list[str] = []
    unread: list[str] = []
    seen: set[str] = set()
    for _inbox, mailbox, _store_id in _iter_inboxes(ns):
        label = str(mailbox or "").strip()
        if label and label not in seen:
            readable.append(label)
            seen.add(label)
    for account in _com_items(getattr(ns, "Accounts", None)):
        label = _account_smtp(account)
        if label and label not in seen:
            unread.append(label)
            seen.add(label)
    return {"mailboxes": readable + unread, "unread_mailboxes": unread}


def list_mailboxes(ns: Any) -> list[str]:
    return list_mailbox_report(ns)["mailboxes"]


def _store_quotas(store_count: int, max_emails: int) -> list[int]:
    n = max(1, store_count)
    base, extra = divmod(max(1, max_emails), n)
    if base == 0:
        base = 1
        extra = 0
    return [base + (1 if i < extra else 0) for i in range(n)]


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
    report = list_mailbox_report(ns)
    mailboxes = report["mailboxes"]
    inboxes = list(_iter_inboxes(ns))
    quotas = _store_quotas(len(inboxes), max_emails) if inboxes else []

    for (inbox, mailbox, _store_id), quota in zip(inboxes, quotas):
        store_scanned = 0
        try:
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for item in items:
            try:
                if store_scanned >= quota:
                    break
                try:
                    received = _from_outlook_dt(item.ReceivedTime)
                except Exception:
                    continue
                if received < cutoff:
                    break
                if not _is_scannable_item(item):
                    continue
                is_invite = _is_meeting_invite(item)
                email_id = _safe_str(item, "EntryID")
                if not email_id:
                    continue
                if skip_check and skip_check(email_id):
                    skipped_processed += 1
                    store_scanned += 1
                    scanned += 1
                    continue

                _, candidates = mail_to_candidates(item, now=now)
                if is_invite and not candidates:
                    skipped_invite += 1
                    store_scanned += 1
                    scanned += 1
                    continue
                store_scanned += 1
                scanned += 1
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
        "unread_mailboxes": report["unread_mailboxes"],
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
            hits.append(attach_display_titles(row))
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
    hits[-1] = attach_display_titles(hits[-1])
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

    inboxes = list(_iter_inboxes(ns))
    quotas = _store_quotas(len(inboxes), max_emails) if inboxes else []
    for (inbox, mailbox, _store_id), quota in zip(inboxes, quotas):
        store_scanned = 0
        try:
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for item in items:
            try:
                if store_scanned >= quota:
                    break
                try:
                    received = _from_outlook_dt(item.ReceivedTime)
                except Exception:
                    continue
                if received < cutoff:
                    break
                if not _is_scannable_item(item):
                    continue
                store_scanned += 1
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
    location: str = "",
) -> str:
    appt = app.CreateItem(OL_APPOINTMENT)
    appt.Subject = title[:255]
    appt.Start = _to_naive_local(start)
    appt.End = _to_naive_local(end)
    appt.AllDayEvent = bool(all_day)
    loc = (location or "").strip()
    if loc:
        try:
            appt.Location = loc[:255]
        except Exception:
            pass
    text = body or ""
    if text:
        try:
            appt.Body = text
        except Exception:
            try:
                appt.HTMLBody = text
            except Exception:
                pass
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
            for store in _com_items(getattr(ns, "Stores", None)):
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
            for store in _com_items(getattr(ns, "Stores", None)):
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
