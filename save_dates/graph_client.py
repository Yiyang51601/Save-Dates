from __future__ import annotations

import webbrowser
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote

import httpx

from save_dates.config import (
    BODY_CHAR_LIMIT,
    CATEGORY_NAME,
    DEFAULT_MAX_EMAILS,
    DEFAULT_SCAN_DAYS,
    GRAPH_ID_PREFIX,
    LOCATION_WRITE_MAX,
    REMINDER_MINUTES_ALL_DAY,
    REMINDER_MINUTES_TIMED,
)
from save_dates.display_title import attach_display_titles
from save_dates.extract import (
    extract_all,
    html_to_text,
    local_tz,
    match_threshold,
    score_search_fields,
    snippet_around_query,
)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
MEETING_TYPES = {
    "meetingrequest",
    "meetingcancelled",
    "meetingaccepted",
    "meetingtenativelyaccepted",
    "meetingdeclined",
}


def is_graph_id(email_id: str | None) -> bool:
    return str(email_id or "").startswith(GRAPH_ID_PREFIX)


def graph_message_id(email_id: str) -> str:
    return str(email_id)[len(GRAPH_ID_PREFIX) :]


def message_to_candidates(
    msg: dict[str, Any],
    now: datetime | None = None,
    mailbox: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    email_id = f"{GRAPH_ID_PREFIX}{msg.get('id') or ''}"
    if not msg.get("id"):
        return "", []
    if msg.get("isDraft"):
        return email_id, []

    received = _parse_graph_dt(msg.get("receivedDateTime"))
    if received is None:
        return email_id, []

    subject = str(msg.get("subject") or "(无主题)")
    sender = _sender_name(msg)
    body = _clipped_body(msg)
    now = now or datetime.now(local_tz())
    events = extract_all(subject, body, received, now=now, sender=sender)
    web_link = str(msg.get("webLink") or "")
    internet_id = str(msg.get("internetMessageId") or "")
    candidates = [
        attach_display_titles(
            {
                "email_id": email_id,
                "internet_id": internet_id,
                "store_id": "",
                "mail_url": web_link,
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
                "location": event.location or "",
                "notes": event.notes or "",
            }
        )
        for event in events
    ]
    return email_id, candidates


def scan_inbox(
    token: str,
    days: int = DEFAULT_SCAN_DAYS,
    max_emails: int = DEFAULT_MAX_EMAILS,
    skip_check: Callable[[str], bool] | None = None,
    sink: Callable[[list[dict[str, Any]]], None] | None = None,
    mark_seen: Callable[[str], None] | None = None,
    account: str = "",
) -> dict[str, Any]:
    days = max(1, min(int(days), 90))
    max_emails = max(10, min(int(max_emails), 200))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scanned = 0
    skipped_invite = 0
    skipped_processed = 0
    found = 0
    now = datetime.now(local_tz())
    url = _messages_url(cutoff, max_emails)
    while url and scanned < max_emails:
        payload = graph_request("GET", url, token)
        for msg in payload.get("value") or []:
            if scanned >= max_emails:
                break
            email_id = f"{GRAPH_ID_PREFIX}{msg.get('id') or ''}"
            if msg.get("isDraft"):
                continue
            is_invite = _is_meeting_invite(msg)
            scanned += 1
            if not msg.get("id"):
                continue
            if skip_check and skip_check(email_id):
                skipped_processed += 1
                continue
            _, candidates = message_to_candidates(msg, now=now, mailbox=account)
            if is_invite and not candidates:
                skipped_invite += 1
                scanned -= 1
                continue
            found += len(candidates)
            if candidates and sink:
                sink(candidates)
            if mark_seen:
                mark_seen(email_id)
        url = payload.get("@odata.nextLink")
    return {
        "scanned": scanned,
        "skipped_invite": skipped_invite,
        "skipped_processed": skipped_processed,
        "found": found,
        "account": account,
        "mailboxes": [account] if account else [],
        "unread_mailboxes": [],
    }


def _search_hits_from_message(
    query: str,
    msg: dict[str, Any],
    now: datetime,
    mailbox: str,
) -> list[dict[str, Any]]:
    subject = str(msg.get("subject") or "(无主题)")
    sender = _sender_name(msg)
    body = _clipped_body(msg)
    score, highlight = score_search_fields(query, subject, sender, body)
    if score < match_threshold(query):
        return []
    _, candidates = message_to_candidates(msg, now=now, mailbox=mailbox)
    if candidates:
        hits: list[dict[str, Any]] = []
        for row in candidates:
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
    received = _parse_graph_dt(msg.get("receivedDateTime"))
    received_at = (received or now).isoformat(timespec="seconds")
    email_id = f"{GRAPH_ID_PREFIX}{msg.get('id') or ''}"
    return [
        attach_display_titles(
            {
                "email_id": email_id,
                "internet_id": str(msg.get("internetMessageId") or ""),
                "store_id": "",
                "mail_url": str(msg.get("webLink") or ""),
                "mailbox": mailbox,
                "subject": subject,
                "sender": sender,
                "received_at": received_at,
                "title": subject[:80],
                "start_at": received_at,
                "end_at": received_at,
                "all_day": False,
                "snippet": snippet_around_query(body or subject, query, highlight),
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
                "can_open_mail": bool(msg.get("id") or msg.get("webLink")),
            }
        )
    ]


def search_recent_mail(
    token: str,
    query: str,
    days: int = DEFAULT_SCAN_DAYS,
    max_emails: int = DEFAULT_MAX_EMAILS,
    account: str = "",
) -> dict[str, Any]:
    query = (query or "").strip()
    days = max(1, min(int(days), 90))
    max_emails = max(10, min(int(max_emails), 200))
    if not query:
        return {"items": [], "scanned": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scanned = 0
    hits: list[dict[str, Any]] = []
    now = datetime.now(local_tz())
    url = _messages_url(cutoff, max_emails, inbox_only=False)
    while url and scanned < max_emails:
        payload = graph_request("GET", url, token)
        for msg in payload.get("value") or []:
            if scanned >= max_emails:
                break
            if msg.get("isDraft"):
                continue
            scanned += 1
            hits.extend(_search_hits_from_message(query, msg, now, account))
        url = payload.get("@odata.nextLink")
    return {"items": hits, "scanned": scanned}


def list_new_messages(token: str, since: datetime, top: int = 25) -> list[dict[str, Any]]:
    url = _messages_url(since - timedelta(seconds=30), top)
    payload = graph_request("GET", url, token)
    return list(payload.get("value") or [])


def get_profile(token: str) -> dict[str, str]:
    data = graph_request("GET", f"{GRAPH_ROOT}/me?$select=displayName,mail,userPrincipalName", token)
    name = str(data.get("displayName") or "")
    mail = str(data.get("mail") or data.get("userPrincipalName") or "")
    return {"name": name, "mail": mail, "label": name or mail}


def create_calendar_event(
    token: str,
    title: str,
    start: datetime,
    end: datetime,
    all_day: bool,
    body: str,
    location: str = "",
) -> str:
    tz_name = str(local_tz())
    payload = {
        "subject": title[:255],
        "body": {"contentType": "text", "content": (body or "")[:BODY_CHAR_LIMIT]},
        "start": {"dateTime": _wall_time(start), "timeZone": tz_name},
        "end": {"dateTime": _wall_time(end), "timeZone": tz_name},
        "isAllDay": bool(all_day),
        "showAs": "tentative",
        "categories": [CATEGORY_NAME],
        "isReminderOn": True,
        "reminderMinutesBeforeStart": (
            REMINDER_MINUTES_ALL_DAY if all_day else REMINDER_MINUTES_TIMED
        ),
    }
    loc = (location or "").strip()
    if loc:
        payload["location"] = {"displayName": loc[:LOCATION_WRITE_MAX]}
    data = graph_request("POST", f"{GRAPH_ROOT}/me/events", token, json=payload)
    return str(data.get("id") or "")


def create_todo_task(token: str, title: str, body: str) -> str:
    try:
        lists = graph_request("GET", f"{GRAPH_ROOT}/me/todo/lists", token)
        rows = lists.get("value") or []
        default = next((row for row in rows if row.get("wellknownListName") == "defaultList"), None)
        target = default or (rows[0] if rows else None)
        if not target or not target.get("id"):
            raise RuntimeError("task_write_failed")
        data = graph_request(
            "POST",
            f"{GRAPH_ROOT}/me/todo/lists/{target['id']}/tasks",
            token,
            json={
                "title": title[:255],
                "body": {"content": (body or "")[:BODY_CHAR_LIMIT], "contentType": "text"},
            },
        )
    except RuntimeError as exc:
        raise RuntimeError("task_write_failed") from exc
    task_id = str(data.get("id") or "")
    if not task_id:
        raise RuntimeError("task_write_failed")
    return f"todo:{target['id']}/{task_id}"


def delete_calendar_event(token: str, event_id: str) -> None:
    if not event_id:
        return
    try:
        graph_request("DELETE", f"{GRAPH_ROOT}/me/events/{quote(event_id, safe='')}", token)
    except RuntimeError as exc:
        if str(exc) != "mail_not_found":
            raise RuntimeError("calendar_delete_failed") from exc


def delete_todo_task(token: str, entry_id: str) -> None:
    if not entry_id:
        return
    rest = entry_id[5:] if entry_id.startswith("todo:") else entry_id
    list_id, sep, task_id = rest.partition("/")
    if not sep or not list_id or not task_id:
        raise RuntimeError("task_write_failed")
    try:
        graph_request(
            "DELETE",
            f"{GRAPH_ROOT}/me/todo/lists/{quote(list_id, safe='')}/tasks/{quote(task_id, safe='')}",
            token,
        )
    except RuntimeError as exc:
        if str(exc) != "mail_not_found":
            raise RuntimeError("task_write_failed") from exc


def _graph_mail_id(email_id: str) -> str:
    if is_graph_id(email_id):
        return graph_message_id(email_id)
    return email_id


def move_graph_mail(token: str, email_id: str, wellknown: str) -> str:
    folder = graph_request("GET", f"{GRAPH_ROOT}/me/mailFolders/{wellknown}", token)
    folder_id = str(folder.get("id") or "")
    if not folder_id:
        raise RuntimeError("junk_move_failed")
    msg_id = quote(_graph_mail_id(email_id), safe="")
    data = graph_request(
        "POST",
        f"{GRAPH_ROOT}/me/messages/{msg_id}/move",
        token,
        json={"destinationId": folder_id},
    )
    new_id = str(data.get("id") or "")
    if not new_id:
        raise RuntimeError("junk_move_failed")
    return f"{GRAPH_ID_PREFIX}{new_id}"


def open_message_url(url: str) -> None:
    if not url:
        raise RuntimeError("mail_not_found")
    webbrowser.open(url)


def open_graph_message(token: str, email_id: str) -> None:
    if not is_graph_id(email_id):
        raise RuntimeError("mail_not_found")
    msg_id = quote(graph_message_id(email_id), safe="")
    data = graph_request(
        "GET",
        f"{GRAPH_ROOT}/me/messages/{msg_id}?$select=webLink",
        token,
    )
    open_message_url(str(data.get("webLink") or ""))


def graph_request(method: str, url: str, token: str, **kwargs: Any) -> dict[str, Any]:
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Prefer", 'outlook.body-content-type="text"')
    with httpx.Client(timeout=30.0) as client:
        response = client.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            raise RuntimeError("graph_login_needed")
        if response.status_code == 404:
            raise RuntimeError("mail_not_found")
        if response.status_code >= 400:
            raise RuntimeError("graph_request_failed")
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


def _messages_url(since: datetime, top: int, *, inbox_only: bool = True) -> str:
    iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    select = (
        "id,subject,from,receivedDateTime,body,internetMessageId,"
        "webLink,meetingMessageType,isDraft"
    )
    query = (
        f"$orderby={quote('receivedDateTime desc')}"
        f"&$top={max(1, min(int(top), 50))}"
        f"&$filter={quote(f'receivedDateTime ge {iso}')}"
        f"&$select={select}"
    )
    root = (
        f"{GRAPH_ROOT}/me/mailFolders/inbox/messages"
        if inbox_only
        else f"{GRAPH_ROOT}/me/messages"
    )
    return f"{root}?{query}"


def _is_meeting_invite(msg: dict[str, Any]) -> bool:
    meeting_type = str(msg.get("meetingMessageType") or "none").lower()
    if meeting_type in MEETING_TYPES:
        return True
    odata_type = str(msg.get("@odata.type") or "").lower()
    return "eventmessage" in odata_type


def _sender_name(msg: dict[str, Any]) -> str:
    address = ((msg.get("from") or {}).get("emailAddress") or {})
    return str(address.get("name") or address.get("address") or "未知发件人")


def _clipped_body(msg: dict[str, Any]) -> str:
    body = msg.get("body") or {}
    content = str(body.get("content") or "")
    if str(body.get("contentType") or "").lower() == "html":
        content = html_to_text(content)
    preview = str(msg.get("bodyPreview") or "")
    text = content or preview
    return text[:BODY_CHAR_LIMIT] if len(text) > BODY_CHAR_LIMIT else text


def _parse_graph_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(local_tz())


def _wall_time(value: datetime) -> str:
    tz = local_tz()
    if value.tzinfo is None:
        local = value
    else:
        local = value.astimezone(tz).replace(tzinfo=None)
    return local.strftime("%Y-%m-%dT%H:%M:%S")
