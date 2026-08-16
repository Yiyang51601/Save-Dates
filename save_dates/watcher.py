from __future__ import annotations

import queue
import threading
import time
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Callable

from save_dates import db
from save_dates.config import (
    WATCH_IDLE_SEC,
    WATCH_RECENT_IDS,
    WATCH_RETRY_SEC,
)
from save_dates.graph_runtime import GraphRuntime
from save_dates.outlook_client import (
    OL_FOLDER_INBOX,
    OL_FOLDER_JUNK,
    create_calendar_event_with_app,
    create_task_with_app,
    delete_item_with_namespace,
    display_mail,
    mail_to_candidates,
    move_mail_with_namespace,
    scan_inbox_with_namespace,
)


@dataclass
class WatchSnapshot:
    connected: bool
    watching: bool
    account: str = ""
    error: str = ""
    generation: int = 0
    last_added: int = 0
    backend: str = ""
    graph_logged_in: bool = False
    classic_running: bool = False
    new_outlook_running: bool = False


class _AppEvents:
    def OnNewMailEx(self, entry_id_collection: str) -> None:
        runtime = OutlookRuntime.instance
        if runtime:
            runtime.handle_entry_ids(str(entry_id_collection or ""))

    def OnQuit(self) -> None:
        runtime = OutlookRuntime.instance
        if runtime:
            runtime.handle_outlook_quit()


class _InboxEvents:
    def OnItemAdd(self, item: Any) -> None:
        try:
            runtime = OutlookRuntime.instance
            if runtime:
                runtime.handle_item(item)
        finally:
            item = None


class OutlookRuntime:
    instance: "OutlookRuntime | None" = None

    def __init__(self, on_notify: Callable[[int], None] | None = None) -> None:
        self._on_notify = on_notify
        self._jobs: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cv = threading.Condition()
        self._generation = 0
        self._last_added = 0
        self._connected = False
        self._watching = False
        self._account = ""
        self._error = "outlook_connecting"
        self._recent_ids: deque[str] = deque(maxlen=WATCH_RECENT_IDS)
        self._app = None
        self._ns = None
        self._app_events = None
        self._inbox_events = None
        self._inbox_items = None
        self._retry_at = 0.0

    def start(self) -> None:
        OutlookRuntime.instance = self
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="save-dates-outlook", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._cv:
            self._cv.notify_all()
        if self._thread:
            self._thread.join(timeout=2)
        OutlookRuntime.instance = None

    def snapshot(self) -> WatchSnapshot:
        return WatchSnapshot(
            connected=self._connected,
            watching=self._watching,
            account=self._account,
            error=self._error,
            generation=self._generation,
            last_added=self._last_added,
        )

    def wait(self, last_generation: int, timeout: float) -> int:
        with self._cv:
            if self._generation != last_generation:
                return self._generation
            self._cv.wait(timeout)
            return self._generation

    def notify(self, added: int = 0) -> None:
        with self._cv:
            self._generation += 1
            self._last_added = added
            self._cv.notify_all()
        if self._on_notify:
            self._on_notify(added)

    def submit(self, fn: Callable[[], Any], timeout: float = 120) -> Any:
        future: Future = Future()
        self._jobs.put((fn, future))
        return future.result(timeout=timeout)

    def scan(self, days: int, max_emails: int, include_processed: bool) -> dict[str, Any]:
        def _job() -> dict[str, Any]:
            if self._ns is None:
                raise RuntimeError("outlook_not_connected")
            added = 0

            def sink(items: list[dict[str, Any]]) -> None:
                nonlocal added
                added += db.insert_candidates(items)

            result = scan_inbox_with_namespace(
                self._ns,
                days=days,
                max_emails=max_emails,
                skip_check=None if include_processed else db.is_handled,
                sink=sink,
                mark_seen=db.mark_seen,
            )
            result["added"] = added
            if added:
                self.notify(added)
            return result

        return self.submit(_job)

    def create_event(self, **kwargs: Any) -> str:
        def _job() -> str:
            if self._app is None:
                raise RuntimeError("outlook_not_connected")
            return create_calendar_event_with_app(self._app, **kwargs)

        return self.submit(_job)

    def create_task(self, **kwargs: Any) -> str:
        def _job() -> str:
            if self._app is None:
                raise RuntimeError("outlook_not_connected")
            return create_task_with_app(self._app, **kwargs)

        return self.submit(_job)

    def delete_written(self, entry_id: str) -> None:
        def _job() -> None:
            if self._ns is None:
                raise RuntimeError("outlook_not_connected")
            delete_item_with_namespace(self._ns, entry_id)

        self.submit(_job)

    def move_to_junk(self, email_id: str, store_id: str = "") -> str:
        def _job() -> str:
            if self._ns is None:
                raise RuntimeError("outlook_not_connected")
            return move_mail_with_namespace(self._ns, email_id, OL_FOLDER_JUNK, store_id or None)

        return self.submit(_job)

    def restore_from_junk(self, email_id: str, store_id: str = "") -> str:
        def _job() -> str:
            if self._ns is None:
                raise RuntimeError("outlook_not_connected")
            return move_mail_with_namespace(self._ns, email_id, OL_FOLDER_INBOX, store_id or None)

        return self.submit(_job)

    def open_mail(self, entry_id: str, store_id: str | None = None) -> None:
        def _job() -> None:
            if self._ns is None:
                raise RuntimeError("outlook_not_connected")
            display_mail(self._ns, entry_id, store_id)

        self.submit(_job)

    def handle_entry_ids(self, raw: str) -> None:
        if self._ns is None:
            return
        for entry_id in raw.replace("\n", ",").split(","):
            entry_id = entry_id.strip()
            if not entry_id:
                continue
            item = None
            try:
                item = self._ns.GetItemFromID(entry_id)
                self.handle_item(item)
            except Exception:
                continue
            finally:
                item = None

    def handle_item(self, item: Any) -> None:
        if item is None:
            return
        try:
            email_id = str(getattr(item, "EntryID", "") or "")
        except Exception:
            return
        if not email_id or email_id in self._recent_ids or db.is_handled(email_id):
            return
        self._recent_ids.append(email_id)
        try:
            _, candidates = mail_to_candidates(item)
        except Exception:
            return
        added = db.insert_candidates(candidates) if candidates else 0
        db.mark_seen(email_id)
        if added:
            self.notify(added)

    def handle_outlook_quit(self) -> None:
        self._release_outlook()
        self._connected = False
        self._watching = False
        self._error = "outlook_closed"
        self._retry_at = time.monotonic() + WATCH_RETRY_SEC
        self.notify(0)

    def _loop(self) -> None:
        import pythoncom

        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                if not self._should_connect():
                    if self._app is not None:
                        self._release_outlook()
                        self._connected = False
                        self._watching = False
                        self._error = ""
                        self.notify(0)
                elif self._app is None and now >= self._retry_at:
                    try:
                        self._connect()
                    except Exception as exc:
                        self._connected = False
                        self._watching = False
                        self._error = _friendly_error(exc)
                        self._retry_at = now + WATCH_RETRY_SEC
                self._drain_jobs()
                pythoncom.PumpWaitingMessages()
                time.sleep(WATCH_IDLE_SEC)
        finally:
            self._release_outlook()
            pythoncom.CoUninitialize()

    def _should_connect(self) -> bool:
        return db.get_settings().get("backend", "auto") != "graph"

    def _connect(self) -> None:
        import win32com.client

        self._release_outlook()
        try:
            app = win32com.client.GetActiveObject("Outlook.Application")
        except Exception as exc:
            raise RuntimeError("outlook_not_running") from exc
        ns = app.GetNamespace("MAPI")
        account = str(ns.CurrentUser.Name)
        inbox = ns.GetDefaultFolder(OL_FOLDER_INBOX)
        items = inbox.Items
        self._app = app
        self._ns = ns
        self._inbox_items = items
        self._app_events = win32com.client.DispatchWithEvents(app, _AppEvents)
        self._inbox_events = win32com.client.DispatchWithEvents(items, _InboxEvents)
        self._account = account
        self._connected = True
        self._watching = True
        self._error = ""
        self.notify(0)

    def _release_outlook(self) -> None:
        self._app_events = None
        self._inbox_events = None
        self._inbox_items = None
        self._ns = None
        self._app = None
        self._watching = False

    def _drain_jobs(self) -> None:
        while True:
            try:
                fn, future = self._jobs.get_nowait()
            except queue.Empty:
                return
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(fn())
                except Exception as exc:
                    future.set_exception(exc)


def _friendly_error(exc: Exception) -> str:
    message = str(exc)
    if message in {
        "outlook_not_running",
        "outlook_not_connected",
        "outlook_closed",
        "outlook_connecting",
        "mail_not_found",
        "mail_is_demo",
    }:
        return message
    lowered = message.lower()
    if (
        "参数错误" in message
        or "outlook" in lowered
        or "invalid class" in lowered
        or "com" in lowered
        or "-2147024809" in message
    ):
        return "outlook_not_running"
    return "outlook_not_running"


class MailboxHub:
    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._generation = 0
        self._last_added = 0
        self.classic = OutlookRuntime(on_notify=self.notify)
        self.graph = GraphRuntime(on_notify=self.notify)
        self.graph._classic_connected = lambda: self.classic.snapshot().connected

    def start(self) -> None:
        self.classic.start()
        self.graph.start()

    def stop(self) -> None:
        self.graph.stop()
        self.classic.stop()

    def snapshot(self) -> WatchSnapshot:
        from save_dates.outlook_detect import classic_outlook_running, new_outlook_running

        classic = self.classic.snapshot()
        graph = self.graph.snapshot()
        backend_pref = db.get_settings().get("backend", "auto")
        classic_running = classic_outlook_running()
        new_running = new_outlook_running()
        active = _active_backend(backend_pref, classic.connected, graph["connected"])
        if active == "classic":
            return WatchSnapshot(
                connected=True,
                watching=classic.watching,
                account=classic.account,
                error="",
                generation=self._generation,
                last_added=self._last_added,
                backend="classic",
                graph_logged_in=graph["logged_in"],
                classic_running=classic_running,
                new_outlook_running=new_running,
            )
        if active == "graph":
            return WatchSnapshot(
                connected=True,
                watching=graph["watching"],
                account=graph["account"],
                error="",
                generation=self._generation,
                last_added=self._last_added,
                backend="graph",
                graph_logged_in=True,
                classic_running=classic_running,
                new_outlook_running=new_running,
            )
        error = _disconnected_error(
            backend_pref,
            classic.error,
            graph["error"],
            graph["logged_in"],
            classic_running,
            new_running,
        )
        return WatchSnapshot(
            connected=False,
            watching=False,
            account=graph["account"] or classic.account,
            error=error,
            generation=self._generation,
            last_added=self._last_added,
            backend="",
            graph_logged_in=graph["logged_in"],
            classic_running=classic_running,
            new_outlook_running=new_running,
        )

    def wait(self, last_generation: int, timeout: float) -> int:
        with self._cv:
            if self._generation != last_generation:
                return self._generation
            self._cv.wait(timeout)
            return self._generation

    def notify(self, added: int = 0) -> None:
        with self._cv:
            self._generation += 1
            self._last_added = added
            self._cv.notify_all()

    def scan(self, days: int, max_emails: int, include_processed: bool) -> dict[str, Any]:
        snap = self.snapshot()
        if not snap.connected:
            raise RuntimeError(snap.error or "outlook_not_connected")
        if snap.backend == "graph":
            return self.graph.scan(days, max_emails, include_processed)
        return self.classic.scan(days, max_emails, include_processed)

    def create_event(self, **kwargs: Any) -> str:
        snap = self.snapshot()
        if not snap.connected:
            raise RuntimeError(snap.error or "outlook_not_connected")
        if snap.backend == "graph":
            return self.graph.create_event(**kwargs)
        return self.classic.create_event(**kwargs)

    def create_task(self, **kwargs: Any) -> str:
        snap = self.snapshot()
        if not snap.connected:
            raise RuntimeError(snap.error or "outlook_not_connected")
        if snap.backend == "graph":
            return self.graph.create_task(**kwargs)
        return self.classic.create_task(**kwargs)

    def delete_written(self, entry_id: str, kind: str = "event") -> None:
        if not entry_id:
            return
        snap = self.snapshot()
        if not snap.connected:
            raise RuntimeError(snap.error or "outlook_not_connected")
        if snap.backend == "graph":
            self.graph.delete_written(entry_id, kind)
            return
        self.classic.delete_written(entry_id)

    def move_to_junk(self, email_id: str, store_id: str = "") -> str:
        snap = self.snapshot()
        if not snap.connected:
            raise RuntimeError(snap.error or "outlook_not_connected")
        if snap.backend == "graph":
            return self.graph.move_to_junk(email_id, store_id)
        return self.classic.move_to_junk(email_id, store_id)

    def restore_from_junk(self, email_id: str, store_id: str = "") -> str:
        snap = self.snapshot()
        if not snap.connected:
            raise RuntimeError(snap.error or "outlook_not_connected")
        if snap.backend == "graph":
            return self.graph.restore_from_junk(email_id, store_id)
        return self.classic.restore_from_junk(email_id, store_id)

    def open_mail(self, entry_id: str, store_id: str | None = None, mail_url: str = "") -> None:
        from save_dates.graph_client import is_graph_id, open_message_url

        if mail_url:
            open_message_url(mail_url)
            return
        if is_graph_id(entry_id):
            self.graph.open_mail(entry_id)
            return
        self.classic.open_mail(entry_id, store_id)

    def graph_login(self) -> dict[str, Any]:
        return self.graph.login()

    def graph_logout(self) -> None:
        self.graph.logout()


def _active_backend(pref: str, classic_on: bool, graph_on: bool) -> str:
    if pref == "classic":
        return "classic" if classic_on else ""
    if pref == "graph":
        return "graph" if graph_on else ""
    if classic_on:
        return "classic"
    if graph_on:
        return "graph"
    return ""


def _disconnected_error(
    pref: str,
    classic_error: str,
    graph_error: str,
    graph_logged_in: bool,
    classic_running: bool,
    new_running: bool,
) -> str:
    if pref == "graph":
        return graph_error or ("graph_login_needed" if not graph_logged_in else "graph_request_failed")
    if pref == "classic":
        return classic_error or "outlook_not_running"
    if new_running and not classic_running:
        if graph_error in {"graph_client_id_missing", "graph_auth_failed", "graph_auth_cancelled"}:
            return graph_error
        return "new_outlook_detected"
    return classic_error or graph_error or "outlook_not_running"


watcher = MailboxHub()
