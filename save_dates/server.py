from __future__ import annotations

import asyncio
import json
import threading
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from save_dates import db
from save_dates.config import (
    DEFAULT_GRAPH_CLIENT_ID,
    DEFAULT_MAX_EMAILS,
    DEFAULT_SCAN_DAYS,
    HOST,
    PENDING_LIST_LIMIT,
    PORT,
    SEARCH_MAX_EMAILS,
    SEARCH_SCAN_DAYS,
    STATIC_DIR,
)
from save_dates.display_title import calendar_write_title
from save_dates.extract import ensure_aware, local_tz
from save_dates.greet import given_name, greeting_phrase
from save_dates.i18n import system_ui_lang
from save_dates.translator import set_translated_callback
from save_dates.watcher import watcher


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    set_translated_callback(lambda: watcher.notify(0))
    watcher.start()
    try:
        yield
    finally:
        set_translated_callback(None)
        watcher.stop()


app = FastAPI(title="Save Dates", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ScanRequest(BaseModel):
    days: int = Field(default=DEFAULT_SCAN_DAYS, ge=1, le=90)
    max_emails: int = Field(default=DEFAULT_MAX_EMAILS, ge=10, le=200)
    include_processed: bool = False
    demo: bool = False
    exit_demo: bool = False


class CandidatePatch(BaseModel):
    title: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    all_day: bool | None = None


class SettingsPatch(BaseModel):
    lang: str | None = None
    backend: str | None = None
    persist_backend: bool | None = None
    graph_client_id: str | None = None


class BatchRequest(BaseModel):
    action: str
    ids: list[int]


class SearchPinRequest(BaseModel):
    email_id: str
    internet_id: str = ""
    store_id: str = ""
    mail_url: str = ""
    subject: str
    sender: str
    received_at: str
    title: str
    start_at: str
    end_at: str
    all_day: bool = False
    snippet: str = ""
    matched_text: str = ""
    confidence: float = 0.5
    fuzzy: bool = False
    kind: str = "event"
    task_type: str = ""
    mailbox: str = ""


class SearchOpenRequest(BaseModel):
    email_id: str = ""
    store_id: str = ""
    mail_url: str = ""


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ensure_aware(dt, local_tz())


def _public_settings() -> dict:
    settings = dict(db.get_settings())
    settings["has_bundled_graph_client"] = bool(DEFAULT_GRAPH_CLIENT_ID.strip())
    return settings


def _snap_payload(snap, extra: dict | None = None) -> dict:
    settings = _public_settings()
    lang = settings.get("lang") or system_ui_lang()
    payload = {
        "connected": snap.connected,
        "watching": snap.watching,
        "account": snap.account,
        "given_name": given_name(snap.account),
        "greeting": greeting_phrase(snap.account, lang),
        "error": snap.error,
        "backend": snap.backend,
        "graph_logged_in": snap.graph_logged_in,
        "classic_running": snap.classic_running,
        "new_outlook_running": snap.new_outlook_running,
        "timezone": str(local_tz()),
        "counts": db.counts(),
        "settings": settings,
        "mailboxes": list(snap.mailboxes or []),
        "unread_mailboxes": list(snap.unread_mailboxes or []),
    }
    if extra:
        payload.update(extra)
    return payload


def _demo_candidates(lang: str = "zh") -> list[dict]:
    tz = local_tz()
    now = datetime.now(tz)
    stamp = now.strftime("%H%M%S")
    friday = now + timedelta(days=(4 - now.weekday()) % 7 or 7)
    start = friday.replace(hour=15, minute=0, second=0, microsecond=0)
    next_monday = (now - timedelta(days=now.weekday()) + timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if lang == "en":
        return [
            {
                "email_id": f"demo-{stamp}-1",
                "internet_id": "",
                "store_id": "",
                "subject": "Campus open day lecture",
                "sender": "Student Union",
                "received_at": now.isoformat(timespec="seconds"),
                "title": "Campus open day lecture",
                "start_at": start.isoformat(timespec="minutes"),
                "end_at": (start + timedelta(hours=1)).isoformat(timespec="minutes"),
                "all_day": False,
                "snippet": "Join us this Friday at 3:00 PM in the auditorium for the campus open day lecture.",
                "matched_text": "this Friday at 3:00 PM",
                "confidence": 0.91,
                "fuzzy": False,
                "kind": "event",
                "task_type": "",
                "mailbox": "yuan@school.edu",
            },
            {
                "email_id": f"demo-{stamp}-2",
                "internet_id": "",
                "store_id": "",
                "subject": "Re: thesis draft",
                "sender": "Advisor",
                "received_at": now.isoformat(timespec="seconds"),
                "title": "Send revised draft",
                "start_at": next_monday.isoformat(timespec="minutes"),
                "end_at": (next_monday + timedelta(days=1)).isoformat(timespec="minutes"),
                "all_day": True,
                "snippet": "Please send the revised draft next week. We can meet around Thursday if that works.",
                "matched_text": "next week",
                "confidence": 0.64,
                "fuzzy": True,
                "kind": "event",
                "task_type": "",
                "mailbox": "yuan@school.edu",
            },
            {
                "email_id": f"demo-{stamp}-3",
                "internet_id": "",
                "store_id": "",
                "subject": "Reading for seminar",
                "sender": "Advisor",
                "received_at": now.isoformat(timespec="seconds"),
                "title": "Finish chapter 3",
                "start_at": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="minutes"),
                "end_at": (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(timespec="minutes"),
                "all_day": True,
                "snippet": "Please finish chapter 3 and prepare for the exam. Let's find a time to meet after that.",
                "matched_text": "finish chapter 3",
                "confidence": 0.64,
                "fuzzy": True,
                "kind": "task",
                "task_type": "homework",
                "mailbox": "yuan@school.edu",
            },
            {
                "email_id": f"demo-{stamp}-4",
                "internet_id": "",
                "store_id": "",
                "subject": "Flash sale: 40% off everything",
                "sender": "ShopNow",
                "received_at": now.isoformat(timespec="seconds"),
                "title": "Flash sale: 40% off everything",
                "start_at": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="minutes"),
                "end_at": (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(timespec="minutes"),
                "all_day": True,
                "snippet": "Limited-time coupon inside. Click to unsubscribe if you no longer want these emails.",
                "matched_text": "unsubscribe",
                "confidence": 0.7,
                "fuzzy": False,
                "kind": "promo",
                "task_type": "ad",
                "mailbox": "yuan@personal.com",
            },
            {
                "email_id": f"demo-{stamp}-5",
                "internet_id": "",
                "store_id": "",
                "subject": "New Student Orientation / 迎新周",
                "sender": "Student Affairs",
                "received_at": now.isoformat(timespec="seconds"),
                "title": "New Student Orientation",
                "start_at": start.isoformat(timespec="minutes"),
                "end_at": (start + timedelta(hours=1)).isoformat(timespec="minutes"),
                "all_day": False,
                "snippet": "Welcome to orientation week / 迎新周. Please come to the auditorium this Friday at 3:00 PM.",
                "matched_text": "this Friday at 3:00 PM",
                "confidence": 0.9,
                "fuzzy": False,
                "kind": "event",
                "task_type": "",
                "mailbox": "yuan@school.edu",
            },
        ]
    return [
        {
            "email_id": f"demo-{stamp}-1",
            "internet_id": "",
            "store_id": "",
            "subject": "校园开放日讲座通知",
            "sender": "学生会",
            "received_at": now.isoformat(timespec="seconds"),
            "title": "校园开放日讲座",
            "start_at": start.isoformat(timespec="minutes"),
            "end_at": (start + timedelta(hours=1)).isoformat(timespec="minutes"),
            "all_day": False,
            "snippet": "本周五下午3点在大礼堂举办校园开放日讲座，欢迎参加。",
            "matched_text": "本周五下午3点",
            "confidence": 0.91,
            "fuzzy": False,
            "kind": "event",
            "task_type": "",
            "mailbox": "yuan@school.edu",
        },
        {
            "email_id": f"demo-{stamp}-2",
            "internet_id": "",
            "store_id": "",
            "subject": "Re: 论文修改",
            "sender": "导师",
            "received_at": now.isoformat(timespec="seconds"),
            "title": "提交修改稿",
            "start_at": next_monday.isoformat(timespec="minutes"),
            "end_at": (next_monday + timedelta(days=1)).isoformat(timespec="minutes"),
            "all_day": True,
            "snippet": "下周把修改稿发我。周四左右方便的话也可以组会。",
            "matched_text": "下周",
            "confidence": 0.64,
            "fuzzy": True,
            "kind": "event",
            "task_type": "",
            "mailbox": "yuan@school.edu",
        },
        {
            "email_id": f"demo-{stamp}-3",
            "internet_id": "",
            "store_id": "",
            "subject": "研讨课阅读",
            "sender": "导师",
            "received_at": now.isoformat(timespec="seconds"),
            "title": "看完第三章",
            "start_at": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="minutes"),
            "end_at": (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(timespec="minutes"),
            "all_day": True,
            "snippet": "请把第三章看完，另外准备考试。看完后我们约个时间见面。",
            "matched_text": "看完第三章",
            "confidence": 0.64,
            "fuzzy": True,
            "kind": "task",
            "task_type": "homework",
            "mailbox": "yuan@school.edu",
        },
        {
            "email_id": f"demo-{stamp}-4",
            "internet_id": "",
            "store_id": "",
            "subject": "限时四折清仓",
            "sender": "某电商",
            "received_at": now.isoformat(timespec="seconds"),
            "title": "限时四折清仓",
            "start_at": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="minutes"),
            "end_at": (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(timespec="minutes"),
            "all_day": True,
            "snippet": "限时折扣，优惠券即将过期。不想再收到可点退订。",
            "matched_text": "退订",
            "confidence": 0.7,
            "fuzzy": False,
            "kind": "promo",
            "task_type": "ad",
            "mailbox": "yuan@personal.com",
        },
        {
            "email_id": f"demo-{stamp}-5",
            "internet_id": "",
            "store_id": "",
            "subject": "迎新周 / Orientation 说明会",
            "sender": "学生事务",
            "received_at": now.isoformat(timespec="seconds"),
            "title": "迎新周说明会",
            "start_at": start.isoformat(timespec="minutes"),
            "end_at": (start + timedelta(hours=1)).isoformat(timespec="minutes"),
            "all_day": False,
            "snippet": "欢迎参加迎新周 orientation。本周五下午3点在大礼堂集合。",
            "matched_text": "本周五下午3点",
            "confidence": 0.9,
            "fuzzy": False,
            "kind": "event",
            "task_type": "",
            "mailbox": "yuan@school.edu",
        },
    ]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def api_status() -> dict:
    return _snap_payload(watcher.snapshot())


@app.get("/api/stream")
async def api_stream() -> StreamingResponse:
    async def generate():
        last = watcher.snapshot().generation
        while True:
            generation = await asyncio.to_thread(watcher.wait, last, 25.0)
            snap = watcher.snapshot()
            changed = generation != last
            payload = _snap_payload(
                snap,
                {
                    "type": "update" if changed else "ping",
                    "added": snap.last_added if changed else 0,
                },
            )
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            last = snap.generation

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/scan")
def api_scan(req: ScanRequest) -> dict:
    if req.exit_demo:
        removed = db.clear_pending_prefix("demo-")
        return {
            "ok": True,
            "demo": False,
            "exited": True,
            "removed": removed,
            "counts": db.counts(),
            "mailboxes": list(watcher.snapshot().mailboxes or []),
            "unread_mailboxes": list(watcher.snapshot().unread_mailboxes or []),
        }

    if req.demo:
        db.clear_pending_prefix("demo-")
        added = db.insert_candidates(_demo_candidates(db.get_settings()["lang"]))
        return {
            "ok": True,
            "demo": True,
            "scanned": 2,
            "skipped_invite": 0,
            "skipped_processed": 0,
            "found": 2,
            "added": added,
            "counts": db.counts(),
            "mailboxes": list(watcher.snapshot().mailboxes or []),
            "unread_mailboxes": list(watcher.snapshot().unread_mailboxes or []),
        }

    snap = watcher.snapshot()
    if not snap.connected:
        raise HTTPException(status_code=400, detail=snap.error or "outlook_not_connected")

    db.clear_pending_prefix("demo-")
    try:
        result = watcher.scan(
            days=req.days,
            max_emails=req.max_emails,
            include_processed=req.include_processed,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="scan_failed") from exc

    return {
        "ok": True,
        "demo": False,
        "scanned": result["scanned"],
        "skipped_invite": result["skipped_invite"],
        "skipped_processed": result["skipped_processed"],
        "found": result["found"],
        "added": result["added"],
        "account": result.get("account", ""),
        "mailboxes": list(result.get("mailboxes") or snap.mailboxes or []),
        "unread_mailboxes": list(result.get("unread_mailboxes") or snap.unread_mailboxes or []),
        "counts": db.counts(),
    }


@app.get("/api/candidates")
def api_list(status: str = "pending") -> dict:
    allowed = {"pending", "accepted", "rejected", "all"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="invalid_status")
    items = db.list_candidates(None if status == "all" else status, limit=PENDING_LIST_LIMIT)
    return {
        "items": items,
        "counts": db.counts(),
        "mailboxes": list(watcher.snapshot().mailboxes or []),
        "unread_mailboxes": list(watcher.snapshot().unread_mailboxes or []),
    }


@app.get("/api/search")
def api_search(q: str = "") -> dict:
    from save_dates.search import run_search

    return run_search(q, days=SEARCH_SCAN_DAYS, max_emails=SEARCH_MAX_EMAILS)


@app.post("/api/search/pin")
def api_search_pin(req: SearchPinRequest) -> dict:
    payload = req.model_dump()
    payload["kind"] = payload.get("kind") or "event"
    existing = db.find_candidate_match(
        payload["email_id"],
        payload["title"],
        payload["start_at"],
        payload["kind"],
        payload.get("task_type") or "",
    )
    if existing:
        return {"item": existing, "counts": db.counts(), "added": 0}
    db.insert_candidates([payload])
    item = db.find_candidate_match(
        payload["email_id"],
        payload["title"],
        payload["start_at"],
        payload["kind"],
        payload.get("task_type") or "",
    )
    if not item:
        raise HTTPException(status_code=500, detail="candidate_missing")
    watcher.notify(1)
    return {"item": item, "counts": db.counts(), "added": 1}


@app.post("/api/search/open-mail")
def api_search_open_mail(req: SearchOpenRequest) -> dict:
    email_id = str(req.email_id or "")
    mail_url = str(req.mail_url or "")
    if email_id.startswith("demo-"):
        raise HTTPException(status_code=400, detail="mail_is_demo")
    if not email_id and not mail_url:
        raise HTTPException(status_code=400, detail="mail_not_found")
    try:
        watcher.open_mail(email_id, req.store_id or None, mail_url=mail_url)
    except Exception as exc:
        message = str(exc)
        if message in {
            "mail_not_found",
            "mail_is_demo",
            "outlook_not_connected",
            "graph_login_needed",
        }:
            raise HTTPException(status_code=400, detail=message) from exc
        raise HTTPException(status_code=500, detail="mail_open_failed") from exc
    return {"ok": True}


@app.patch("/api/candidates/{candidate_id}")
def api_patch(candidate_id: int, patch: CandidatePatch) -> dict:
    current = db.get_candidate(candidate_id)
    if not current:
        raise HTTPException(status_code=404, detail="candidate_missing")
    fields = patch.model_dump(exclude_none=True)
    if "start_at" in fields:
        start = _parse_iso(fields["start_at"])
        fields["start_at"] = start.isoformat(timespec="minutes")
        all_day = fields.get("all_day", current["all_day"])
        if "end_at" not in fields:
            fields["end_at"] = (
                (start.replace(hour=0, minute=0) + timedelta(days=1)).isoformat(timespec="minutes")
                if all_day
                else (start + timedelta(hours=1)).isoformat(timespec="minutes")
            )
    if "end_at" in fields:
        fields["end_at"] = _parse_iso(fields["end_at"]).isoformat(timespec="minutes")
    try:
        updated = db.update_candidate(candidate_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"item": updated}


def _source_body(item: dict) -> str:
    lang = db.get_settings()["lang"]
    original = str(item.get("title") or item.get("subject") or "")
    if lang == "en":
        return (
            f"Source email: {item['subject']}\n"
            f"Original title: {original}\n"
            f"From: {item['sender']}\n"
            f"Received: {item['received_at']}\n"
            f"Excerpt: {item['snippet']}\n"
            f"Matched: {item['matched_text']}\n"
            "Added from Save Dates after confirmation. Open the original message from Save Dates."
        )
    return (
        f"来源邮件：{item['subject']}\n"
        f"原标题：{original}\n"
        f"发件人：{item['sender']}\n"
        f"收到时间：{item['received_at']}\n"
        f"原文摘录：{item['snippet']}\n"
        f"匹配文本：{item['matched_text']}\n"
        "（由 Save Dates 确认后写入。可在 Save Dates 中打开原邮件。）"
    )


def _accept_one(candidate_id: int) -> dict:
    item = db.get_candidate(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="candidate_missing")
    if item["status"] == "accepted":
        return item
    body = _source_body(item)
    if (item.get("kind") or "event") == "promo":
        entry_id = ""
        try:
            entry_id = watcher.move_to_junk(item["email_id"], item.get("store_id") or "")
        except Exception:
            entry_id = ""
        updated = db.set_status(candidate_id, "accepted", entry_id)
        return updated or item
    write_title = calendar_write_title(item)
    if (item.get("kind") or "event") == "task":
        entry_id = ""
        try:
            entry_id = watcher.create_task(title=write_title, body=body)
        except Exception:
            entry_id = ""
        updated = db.set_status(candidate_id, "accepted", entry_id)
        return updated or item
    start = _parse_iso(item["start_at"])
    end = _parse_iso(item["end_at"])
    if end <= start:
        end = start + (timedelta(days=1) if item["all_day"] else timedelta(hours=1))
    try:
        entry_id = watcher.create_event(
            title=write_title,
            start=start,
            end=end,
            all_day=bool(item["all_day"]),
            body=body,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="calendar_write_failed") from exc
    updated = db.set_status(candidate_id, "accepted", entry_id)
    return updated or item


@app.post("/api/candidates/{candidate_id}/accept")
def api_accept(candidate_id: int) -> dict:
    return {"item": _accept_one(candidate_id), "counts": db.counts()}


@app.post("/api/candidates/{candidate_id}/reject")
def api_reject(candidate_id: int) -> dict:
    item = db.set_status(candidate_id, "rejected")
    if not item:
        raise HTTPException(status_code=404, detail="candidate_missing")
    return {"item": item, "counts": db.counts()}


def _undo_one(candidate_id: int) -> dict:
    item = db.get_candidate(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="candidate_missing")
    if item["status"] == "pending":
        return {"item": item, "outlook_deleted": True}
    outlook_deleted = True
    entry_id = str(item.get("calendar_entry_id") or "")
    if item["status"] == "accepted" and entry_id:
        try:
            if (item.get("kind") or "event") == "promo":
                watcher.restore_from_junk(entry_id, item.get("store_id") or "")
            else:
                watcher.delete_written(entry_id, item.get("kind") or "event")
        except Exception:
            outlook_deleted = False
    updated = db.restore_pending(candidate_id)
    return {"item": updated or item, "outlook_deleted": outlook_deleted}


@app.post("/api/candidates/{candidate_id}/undo")
def api_undo(candidate_id: int) -> dict:
    result = _undo_one(candidate_id)
    result["counts"] = db.counts()
    return result


@app.post("/api/batch")
def api_batch(req: BatchRequest) -> dict:
    if req.action not in {"accept", "reject", "undo"}:
        raise HTTPException(status_code=400, detail="invalid_action")
    done = 0
    errors: list[str] = []
    outlook_deleted = True
    for candidate_id in req.ids:
        try:
            if req.action == "accept":
                _accept_one(candidate_id)
            elif req.action == "undo":
                result = _undo_one(candidate_id)
                outlook_deleted = outlook_deleted and bool(result.get("outlook_deleted", True))
            else:
                db.set_status(candidate_id, "rejected")
            done += 1
        except HTTPException as exc:
            errors.append(f"#{candidate_id}: {exc.detail}")
    return {
        "done": done,
        "errors": errors,
        "counts": db.counts(),
        "outlook_deleted": outlook_deleted,
    }


@app.get("/api/settings")
def api_get_settings() -> dict:
    return _public_settings()


@app.post("/api/desktop/show")
def api_desktop_show() -> dict:
    from save_dates.window_control import request_show

    if request_show():
        return {"ok": True}
    raise HTTPException(status_code=404, detail="no_desktop_window")


@app.put("/api/settings")
def api_put_settings(patch: SettingsPatch) -> dict:
    data = patch.model_dump(exclude_none=True)
    persist = data.pop("persist_backend", True)
    backend = data.get("backend")
    if backend in {"auto", "classic", "graph"} and persist is False:
        data.pop("backend", None)
        db.set_session_backend(backend)
        if data:
            db.save_settings(data)
    else:
        db.save_settings(data)
    watcher.notify(0)
    return db.get_settings()


@app.post("/api/microsoft/login")
def api_microsoft_login() -> dict:
    try:
        watcher.graph_login()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "graph_auth_failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="graph_auth_failed") from exc
    return api_status()


@app.post("/api/microsoft/logout")
def api_microsoft_logout() -> dict:
    watcher.graph_logout()
    return api_status()


@app.post("/api/candidates/{candidate_id}/open-mail")
def api_open_mail(candidate_id: int) -> dict:
    item = db.get_candidate(candidate_id)
    if not item:
        raise HTTPException(status_code=404, detail="candidate_missing")
    if not item.get("can_open_mail"):
        raise HTTPException(status_code=400, detail="mail_is_demo")
    mail_url = str(item.get("mail_url") or "")
    if mail_url:
        try:
            watcher.open_mail(item["email_id"], mail_url=mail_url)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="mail_open_failed") from exc
        return {"ok": True}
    snap = watcher.snapshot()
    if not snap.connected:
        raise HTTPException(status_code=400, detail=snap.error or "outlook_not_connected")
    try:
        watcher.open_mail(item["email_id"], item.get("store_id") or None)
    except Exception as exc:
        message = str(exc)
        if message in {
            "mail_not_found",
            "mail_is_demo",
            "outlook_not_connected",
            "graph_login_needed",
        }:
            raise HTTPException(status_code=400, detail=message) from exc
        raise HTTPException(status_code=500, detail="mail_open_failed") from exc
    return {"ok": True}


def main() -> None:
    url = f"http://{HOST}:{PORT}"

    def _open() -> None:
        webbrowser.open(url)

    threading.Timer(0.9, _open).start()
    print(f"Save Dates 已启动：{url}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
