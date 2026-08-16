from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

from save_dates import db
from save_dates.config import (
    GRAPH_STATE_PATH,
    GRAPH_WATCH_SEC,
    WATCH_RECENT_IDS,
)
from save_dates.graph_auth import acquire_token, cached_account_label, has_cached_account, logout
from save_dates.graph_client import (
    create_calendar_event,
    create_todo_task,
    delete_calendar_event,
    delete_todo_task,
    get_profile,
    is_graph_id,
    list_new_messages,
    message_to_candidates,
    move_graph_mail,
    open_graph_message,
    open_message_url,
    scan_inbox,
)


class GraphRuntime:
    def __init__(self, on_notify: Callable[[int], None] | None = None) -> None:
        self._on_notify = on_notify
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._interactive = False
        self._connected = False
        self._watching = False
        self._account = ""
        self._error = ""
        self._classic_connected = lambda: False
        self._recent_ids: deque[str] = deque(maxlen=WATCH_RECENT_IDS)
        self._last_received = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._load_state()
        self._thread = threading.Thread(target=self._loop, name="save-dates-graph", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def snapshot(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "watching": self._watching,
            "account": self._account or cached_account_label(),
            "error": self._error,
            "logged_in": self._connected or has_cached_account(),
        }

    def login(self) -> dict[str, Any]:
        self._interactive = True
        try:
            token = acquire_token(interactive=True)
            profile = get_profile(token)
            self._set_state(True, True, profile["label"], "")
            if not self._last_received:
                self._last_received = datetime.now(timezone.utc).isoformat()
                self._save_state()
            return profile
        except Exception as exc:
            self._set_state(False, False, "", _graph_error(exc))
            raise
        finally:
            self._interactive = False

    def logout(self) -> None:
        logout()
        if GRAPH_STATE_PATH.exists():
            GRAPH_STATE_PATH.unlink()
        self._last_received = ""
        self._set_state(False, False, "", "graph_login_needed")

    def scan(self, days: int, max_emails: int, include_processed: bool) -> dict[str, Any]:
        with self._lock:
            token = acquire_token(False)
            added = 0

            def sink(items: list[dict[str, Any]]) -> None:
                nonlocal added
                added += db.insert_candidates(items)

            result = scan_inbox(
                token,
                days=days,
                max_emails=max_emails,
                skip_check=None if include_processed else db.is_handled,
                sink=sink,
                mark_seen=db.mark_seen,
                account=self._account,
            )
            result["added"] = added
            if added:
                self._notify(added)
            return result

    def create_event(self, **kwargs: Any) -> str:
        with self._lock:
            token = acquire_token(False)
            return create_calendar_event(token, **kwargs)

    def create_task(self, **kwargs: Any) -> str:
        with self._lock:
            token = acquire_token(False)
            return create_todo_task(token, **kwargs)

    def delete_written(self, entry_id: str, kind: str = "event") -> None:
        with self._lock:
            token = acquire_token(False)
            if str(entry_id).startswith("todo:") or kind == "task":
                delete_todo_task(token, entry_id)
                return
            delete_calendar_event(token, entry_id)

    def move_to_junk(self, email_id: str, store_id: str = "") -> str:
        with self._lock:
            token = acquire_token(False)
            return move_graph_mail(token, email_id, "junkemail")

    def restore_from_junk(self, email_id: str, store_id: str = "") -> str:
        with self._lock:
            token = acquire_token(False)
            return move_graph_mail(token, email_id, "inbox")

    def open_mail(self, email_id: str, mail_url: str = "") -> None:
        if mail_url:
            open_message_url(mail_url)
            return
        if not is_graph_id(email_id):
            raise RuntimeError("mail_not_found")
        with self._lock:
            token = acquire_token(False)
            open_graph_message(token, email_id)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._interactive:
                    self._stop.wait(0.5)
                    continue
                if not self._should_run():
                    if self._watching:
                        self._watching = False
                        self._notify(0)
                    self._stop.wait(3)
                    continue
                self._tick()
            except Exception as exc:
                self._set_state(False, False, self._account, _graph_error(exc))
            wait = GRAPH_WATCH_SEC if self._watching else 4
            self._stop.wait(wait)

    def _should_run(self) -> bool:
        backend = db.get_settings().get("backend", "auto")
        if backend == "classic":
            return False
        if backend == "graph":
            return True
        return not self._classic_connected()

    def _tick(self) -> None:
        if not has_cached_account() and not get_client_id_safe():
            self._set_state(False, False, "", self._idle_error())
            return
        with self._lock:
            token = acquire_token(False)
            profile = get_profile(token)
            self._set_state(True, True, profile["label"], "")
            if not self._last_received:
                self._last_received = datetime.now(timezone.utc).isoformat()
                self._save_state()
                return
            since = datetime.fromisoformat(self._last_received.replace("Z", "+00:00"))
            messages = list_new_messages(token, since)
        added_total = 0
        newest = since
        for msg in reversed(messages):
            email_id, candidates = message_to_candidates(msg, mailbox=self._account)
            received = None
            try:
                received = datetime.fromisoformat(str(msg.get("receivedDateTime") or "").replace("Z", "+00:00"))
            except ValueError:
                received = None
            if received and received > newest:
                newest = received
            if not email_id or email_id in self._recent_ids or db.is_handled(email_id):
                continue
            self._recent_ids.append(email_id)
            added = db.insert_candidates(candidates) if candidates else 0
            db.mark_seen(email_id)
            added_total += added
        if newest:
            self._last_received = newest.astimezone(timezone.utc).isoformat()
            self._save_state()
        if added_total:
            self._notify(added_total)

    def _idle_error(self) -> str:
        if not get_client_id_safe() and (has_new_outlook() or db.get_settings().get("backend") == "graph"):
            return "graph_client_id_missing" if db.get_settings().get("backend") == "graph" else ""
        if has_cached_account():
            return "graph_login_needed"
        return ""

    def _set_state(self, connected: bool, watching: bool, account: str, error: str) -> None:
        changed = (
            self._connected != connected
            or self._watching != watching
            or self._account != account
            or self._error != error
        )
        self._connected = connected
        self._watching = watching
        self._account = account
        self._error = error
        if changed:
            self._notify(0)

    def _notify(self, added: int) -> None:
        if self._on_notify:
            self._on_notify(added)

    def _load_state(self) -> None:
        if not GRAPH_STATE_PATH.exists():
            return
        try:
            data = json.loads(GRAPH_STATE_PATH.read_text(encoding="utf-8"))
            self._last_received = str(data.get("last_received") or "")
        except Exception:
            self._last_received = ""

    def _save_state(self) -> None:
        GRAPH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        GRAPH_STATE_PATH.write_text(
            json.dumps({"last_received": self._last_received}, ensure_ascii=False),
            encoding="utf-8",
        )


def get_client_id_safe() -> str:
    from save_dates.graph_auth import get_client_id

    try:
        return get_client_id()
    except Exception:
        return ""


def has_new_outlook() -> bool:
    from save_dates.outlook_detect import new_outlook_running

    return new_outlook_running()


def _graph_error(exc: Exception) -> str:
    message = str(exc)
    if message in {
        "graph_login_needed",
        "graph_client_id_missing",
        "graph_auth_failed",
        "graph_auth_cancelled",
        "graph_request_failed",
        "mail_not_found",
    }:
        return message
    return "graph_request_failed"
