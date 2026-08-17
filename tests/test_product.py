from __future__ import annotations

import json

from fastapi.testclient import TestClient

from save_dates.server import app


def test_home_and_static():
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Save Dates" in home.text
        assert "connectPicker" in home.text
        assert "pickClassic" in home.text
        assert "pickGraph" in home.text
        assert "connectPersistOnce" in home.text
        assert "connectPersistAlways" in home.text
        assert "进阶 · 仅新 Outlook" in home.text
        assert "经典 Outlook" in home.text
        assert "mailSearch" in home.text
        assert "searchPlaceholder" in home.text
        css = client.get("/static/styles.css")
        assert css.status_code == 200
        assert "empty-hint-out" in css.text
        assert "connect-persist" in css.text
        js = client.get("/static/app.js")
        assert js.status_code == 200
        assert "搜邮件里的活动" in js.text
        assert "Search mail for events" in js.text
        assert "选择邮箱连接方式" in js.text
        assert "How do you want to connect?" in js.text
        assert "仅此次" in js.text
        assert "This time only" in js.text
        assert "记住选择" in js.text
        assert "persist_backend" in js.text
        assert "You do not type an Application ID" in js.text
        assert "connectPickerAutoShown" in js.text
        assert "detectSystemLang" in js.text
        assert "emptyHintSessionDone" in js.text
        assert "empty-hint-out" in js.text
        assert "mailboxSelect" in home.text
        assert "mailboxPick" in home.text
        assert "mailboxSeg" not in home.text
        assert "退出示例" in js.text
        assert "Exit sample" in js.text
        assert "demoExitBtn" in js.text
        assert "exit_demo" in js.text
        assert "全部邮箱" in js.text
        assert "All mailboxes" in js.text
        assert "学校邮箱被拦 Graph" in js.text
        assert "Needs admin approval" in js.text
        assert "未找到该邮箱，请在经典 Outlook 添加并保持运行" in js.text
        assert "cardTitle" in js.text
        assert "title_zh" in js.text
        assert "currentMailbox = \"\"" in js.text
        assert "mailboxHint" in home.text
        assert "讲座通知" not in js.text
        assert "导师往来" not in js.text
        assert "advisor threads" not in js.text
        assert "在等新邮件。会议、截止日期、活动里的日期会出现在这里。" in js.text
        assert "Waiting for mail. Dated items from meetings, deadlines, and events will show up here." in js.text


def test_status_and_demo_review_flow():
    with TestClient(app) as client:
        status = client.get("/api/status")
        assert status.status_code == 200
        body = status.json()
        assert "connected" in body
        assert "watching" in body
        assert "counts" in body
        assert "timezone" in body
        assert "greeting" in body
        assert "mailboxes" in body
        assert "unread_mailboxes" in body
        assert isinstance(body["mailboxes"], list)
        assert isinstance(body["unread_mailboxes"], list)
        assert body["greeting"]

        scan = client.post("/api/scan", json={"demo": True})
        assert scan.status_code == 200
        payload = scan.json()
        assert payload["ok"] is True
        assert payload["added"] >= 1

        listed = client.get("/api/candidates?status=pending")
        assert listed.status_code == 200
        assert isinstance(listed.json()["mailboxes"], list)
        assert isinstance(listed.json().get("unread_mailboxes"), list)
        items = listed.json()["items"]
        assert items
        first = items[0]
        patched = client.patch(
            f"/api/candidates/{first['id']}",
            json={"title": "产品测试标题-独立", "all_day": True, "start_at": "2026-10-01T00:00"},
        )
        assert patched.status_code == 200
        assert patched.json()["item"]["title"] == "产品测试标题-独立"
        assert patched.json()["item"]["all_day"] is True

        rejected = client.post(f"/api/candidates/{first['id']}/reject")
        assert rejected.status_code == 200
        assert rejected.json()["item"]["status"] == "rejected"


def test_language_setting_and_demo_cannot_open_mail():
    with TestClient(app) as client:
        saved = client.put("/api/settings", json={"lang": "en"})
        assert saved.status_code == 200
        assert saved.json()["lang"] == "en"
        assert saved.json()["lang_set"] is True
        assert client.get("/api/settings").json()["lang"] == "en"
        assert client.get("/api/settings").json()["lang_set"] is True

        scan = client.post("/api/scan", json={"demo": True})
        assert scan.status_code == 200
        item = client.get("/api/candidates?status=pending").json()["items"][0]
        assert item["can_open_mail"] is False
        assert item.get("title_zh")
        assert any("\u4e00" <= ch <= "\u9fff" for ch in item["title_zh"])
        opened = client.post(f"/api/candidates/{item['id']}/open-mail")
        assert opened.status_code == 400
        assert opened.json()["detail"] == "mail_is_demo"
        client.put("/api/settings", json={"lang": "zh"})


def test_backend_setting_roundtrip():
    with TestClient(app) as client:
        saved = client.put("/api/settings", json={"backend": "graph"})
        assert saved.status_code == 200
        assert saved.json()["backend"] == "graph"
        settings = client.get("/api/settings").json()
        assert settings["backend"] == "graph"
        assert settings["has_bundled_graph_client"] is True
        client.put("/api/settings", json={"backend": "auto"})


def test_session_backend_is_not_written_to_disk(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    from save_dates import db

    db.clear_session_backend()
    db.save_settings({"lang": "zh", "graph_client_id": "keep-me"})
    try:
        db.set_session_backend("classic")
        settings = db.get_settings()
        assert settings["backend"] == "classic"
        assert settings["lang"] == "zh"
        assert settings["graph_client_id"] == "keep-me"
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        assert raw["backend"] == "auto"
        assert raw["lang"] == "zh"
        assert raw["graph_client_id"] == "keep-me"
        db.clear_session_backend()
        assert db.get_settings()["backend"] == "auto"
    finally:
        db.clear_session_backend()


def test_persist_backend_false_is_session_only(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", settings_path)
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    from save_dates import db

    db.clear_session_backend()
    try:
        with TestClient(app) as client:
            client.put("/api/settings", json={"lang": "en", "graph_client_id": "keep-id"})
            saved = client.put("/api/settings", json={"backend": "classic", "persist_backend": False})
            assert saved.status_code == 200
            assert saved.json()["backend"] == "classic"
            assert client.get("/api/settings").json()["backend"] == "classic"
            raw = json.loads(settings_path.read_text(encoding="utf-8"))
            assert raw.get("backend") == "auto"
            assert raw.get("lang") == "en"
            assert raw.get("graph_client_id") == "keep-id"
            once_graph = client.put("/api/settings", json={"backend": "graph", "persist_backend": False})
            assert once_graph.json()["backend"] == "graph"
            raw = json.loads(settings_path.read_text(encoding="utf-8"))
            assert raw.get("backend") == "auto"
            assert raw.get("graph_client_id") == "keep-id"
            always = client.put("/api/settings", json={"backend": "graph", "persist_backend": True})
            assert always.json()["backend"] == "graph"
            raw = json.loads(settings_path.read_text(encoding="utf-8"))
            assert raw["backend"] == "graph"
            assert raw["lang"] == "en"
            assert raw["graph_client_id"] == "keep-id"
            client.put("/api/settings", json={"backend": "auto"})
    finally:
        db.clear_session_backend()


def test_auto_backend_asks_user_to_choose_connection():
    from save_dates.watcher import _disconnected_error

    assert _disconnected_error("auto", "outlook_not_running", "", False, False, True) == "choose_connection"
    assert _disconnected_error("auto", "", "", False, False, False) == "choose_connection"
    assert _disconnected_error("classic", "", "", False, False, True) == "outlook_not_running"
    assert _disconnected_error("graph", "", "", False, False, True) == "graph_login_needed"


def test_desktop_show_without_window_is_404():
    with TestClient(app) as client:
        response = client.post("/api/desktop/show")
        assert response.status_code == 404
        assert response.json()["detail"] == "no_desktop_window"


def test_microsoft_login_uses_bundled_public_client():
    from save_dates.config import DEFAULT_GRAPH_CLIENT_ID, GRAPH_REDIRECT_URI, GRAPH_SCOPES
    from save_dates.graph_auth import get_client_id

    assert DEFAULT_GRAPH_CLIENT_ID == "65f4dd53-e782-46a4-a0b1-8ccd331dd6ff"
    assert GRAPH_REDIRECT_URI == "http://localhost"
    assert GRAPH_SCOPES == ("User.Read", "Mail.Read", "Mail.ReadWrite", "Calendars.ReadWrite")
    with TestClient(app) as client:
        client.put("/api/settings", json={"graph_client_id": "", "backend": "graph"})
        settings = client.get("/api/settings").json()
        assert settings["has_bundled_graph_client"] is True
        assert get_client_id() == DEFAULT_GRAPH_CLIENT_ID
        home = client.get("/")
        assert "msLoginBtn" in home.text
        assert "graphOverride" in home.text
        js = client.get("/static/app.js").text
        assert "不用填写应用 ID" in js
        client.put("/api/settings", json={"backend": "auto"})


def test_real_scan_without_outlook_is_controlled():
    with TestClient(app) as client:
        status = client.get("/api/status").json()
        if status["connected"]:
            return
        response = client.post("/api/scan", json={"days": 7, "max_emails": 20})
        assert response.status_code == 400
        assert response.json()["detail"]


def test_demo_includes_task_and_accept_saves_locally():
    with TestClient(app) as client:
        scan = client.post("/api/scan", json={"demo": True})
        assert scan.status_code == 200
        items = client.get("/api/candidates?status=pending").json()["items"]
        tasks = [item for item in items if item.get("kind") == "task"]
        events = [item for item in items if item.get("kind") != "task"]
        assert events
        assert tasks
        accepted = client.post(f"/api/candidates/{tasks[0]['id']}/accept")
        assert accepted.status_code == 200
        assert accepted.json()["item"]["status"] == "accepted"


def test_reject_and_accept_can_be_undone():
    with TestClient(app) as client:
        client.post("/api/scan", json={"demo": True})
        items = client.get("/api/candidates?status=pending").json()["items"]
        first = items[0]
        rejected = client.post(f"/api/candidates/{first['id']}/reject")
        assert rejected.json()["item"]["status"] == "rejected"
        undone = client.post(f"/api/candidates/{first['id']}/undo")
        assert undone.status_code == 200
        assert undone.json()["item"]["status"] == "pending"

        task = next(item for item in items if item.get("kind") == "task")
        client.post(f"/api/candidates/{task['id']}/accept")
        restored = client.post(f"/api/candidates/{task['id']}/undo")
        assert restored.status_code == 200
        assert restored.json()["item"]["status"] == "pending"


def test_demo_exit_clears_sample_mail():
    with TestClient(app) as client:
        scan = client.post("/api/scan", json={"demo": True})
        assert scan.status_code == 200
        assert scan.json()["demo"] is True
        items = client.get("/api/candidates?status=pending").json()["items"]
        assert items
        assert any(str(item["email_id"]).startswith("demo-") for item in items)
        boxes = {item.get("mailbox") for item in items if item.get("mailbox")}
        assert "yuan@school.edu" in boxes
        assert "yuan@personal.com" in boxes
        exited = client.post("/api/scan", json={"exit_demo": True})
        assert exited.status_code == 200
        payload = exited.json()
        assert payload["ok"] is True
        assert payload["demo"] is False
        leftover = client.get("/api/candidates?status=pending").json()["items"]
        assert not any(str(item["email_id"]).startswith("demo-") for item in leftover)


def test_list_mailboxes_refreshes_new_classic_stores():
    from save_dates.outlook_client import list_mailboxes

    class Store:
        def __init__(self, sid, name):
            self.StoreID = sid
            self.DisplayName = name

        def GetDefaultFolder(self, _kind):
            return object()

    class Account:
        def __init__(self, store, smtp):
            self.DeliveryStore = store
            self.SmtpAddress = smtp
            self.DisplayName = smtp

    class Namespace:
        def __init__(self, stores, accounts):
            self.Stores = stores
            self.Accounts = accounts

    first = Store("s1", "School")
    names = list_mailboxes(Namespace([first], [Account(first, "yuan@school.edu")]))
    assert names == ["yuan@school.edu"]
    second = Store("s2", "Personal")
    names = list_mailboxes(
        Namespace(
            [first, second],
            [Account(first, "yuan@school.edu"), Account(second, "yuan@personal.com")],
        )
    )
    assert names == ["yuan@school.edu", "yuan@personal.com"]


def test_graph_mailbox_list_follows_signed_in_account():
    from save_dates.graph_runtime import GraphRuntime

    runtime = GraphRuntime()
    runtime._account = "first@outlook.com"
    assert runtime.mailboxes() == ["first@outlook.com"]
    runtime._account = "later@school.edu"
    assert runtime.mailboxes() == ["later@school.edu"]


def test_scan_inbox_keeps_all_store_mailboxes_when_email_cap_hits():
    from datetime import datetime, timezone

    from save_dates.outlook_client import scan_inbox_with_namespace

    class Mail:
        Class = 43
        Subject = "hello"
        SenderName = "A"
        SenderEmailAddress = "a@x.com"
        EntryID = "id-1"
        Body = ""
        ReceivedTime = datetime.now(timezone.utc)

        class PropertyAccessor:
            @staticmethod
            def GetProperty(_name):
                raise RuntimeError("no")

        class Parent:
            class Store:
                StoreID = "s1"
                DisplayName = "one@x.com"

    class Items(list):
        def Sort(self, *_args, **_kwargs):
            return None

    class Inbox:
        def __init__(self, mails):
            self.Items = Items(mails)

    class Store:
        def __init__(self, sid, inbox):
            self.StoreID = sid
            self.DisplayName = sid
            self._inbox = inbox

        def GetDefaultFolder(self, _kind):
            return self._inbox

    class Account:
        def __init__(self, store, smtp):
            self.DeliveryStore = store
            self.SmtpAddress = smtp
            self.DisplayName = smtp

    class Namespace:
        def __init__(self, stores, accounts):
            self.Stores = stores
            self.Accounts = accounts
            self.CurrentUser = type("User", (), {"Name": "Yuan"})()

    old = Store("old", Inbox([Mail() for _ in range(30)]))
    new = Store("new", Inbox([]))
    ns = Namespace(
        [old, new],
        [Account(old, "old@x.com"), Account(new, "new@x.com")],
    )
    result = scan_inbox_with_namespace(ns, days=14, max_emails=10)
    assert result["mailboxes"] == ["old@x.com", "new@x.com"]
    assert result["scanned"] == 5
    assert result["unread_mailboxes"] == []


def test_list_mailboxes_includes_display_name_and_unread_accounts():
    from save_dates.outlook_client import list_mailbox_report, list_mailboxes

    class ComCollection(list):
        @property
        def Count(self):
            return len(self)

        def Item(self, index):
            return self[index - 1]

    class Store:
        def __init__(self, sid, name, inbox=True):
            self.StoreID = sid
            self.DisplayName = name
            self.ExchangeStoreType = 2
            self._inbox = object() if inbox else None

        def GetDefaultFolder(self, _kind):
            if self._inbox is None:
                raise RuntimeError("no inbox")
            return self._inbox

    class BrokenStore:
        StoreID = "broken"
        DisplayName = "Pitt"
        ExchangeStoreType = 0

        def GetDefaultFolder(self, _kind):
            raise RuntimeError("fail")

        def GetRootFolder(self):
            raise RuntimeError("fail")

    class Account:
        def __init__(self, store, smtp):
            self.DeliveryStore = store
            self.SmtpAddress = smtp
            self.DisplayName = smtp

    class Namespace:
        def __init__(self, stores, accounts):
            self.Stores = stores
            self.Accounts = accounts

    pitt_store = Store("pitt", "yic327@pitt.edu")
    personal = Store("p1", "Personal")
    names = list_mailboxes(
        Namespace(
            ComCollection([personal, pitt_store]),
            ComCollection([Account(personal, "yuan@personal.com")]),
        )
    )
    assert names == ["yuan@personal.com", "yic327@pitt.edu"]

    report = list_mailbox_report(
        Namespace(
            ComCollection([personal]),
            ComCollection(
                [Account(personal, "yuan@personal.com"), Account(BrokenStore(), "yic327@pitt.edu")]
            ),
        )
    )
    assert "yuan@personal.com" in report["mailboxes"]
    assert "yic327@pitt.edu" in report["mailboxes"]
    assert report["unread_mailboxes"] == ["yic327@pitt.edu"]


def test_inbox_found_via_root_folder_when_default_fails():
    from save_dates.outlook_client import list_mailboxes

    class Folder:
        def __init__(self, name):
            self.Name = name
            self.DefaultItemType = 0

    class Root:
        def __init__(self, folders):
            self.Folders = folders

    class Store:
        StoreID = "imap-pitt"
        DisplayName = "yic327@pitt.edu"
        ExchangeStoreType = 2

        def GetDefaultFolder(self, _kind):
            raise RuntimeError("IMAP default missing")

        def GetRootFolder(self):
            return Root([Folder("Inbox")])

    class Namespace:
        Stores = [Store()]
        Accounts = []

    assert list_mailboxes(Namespace()) == ["yic327@pitt.edu"]


def test_scan_fair_share_reads_later_store():
    from datetime import datetime, timedelta, timezone

    from save_dates.outlook_client import scan_inbox_with_namespace

    now = datetime.now(timezone.utc)
    future = now + timedelta(days=10)
    date_text = future.strftime("%Y-%m-%d")

    class PropertyAccessor:
        @staticmethod
        def GetProperty(_name):
            raise RuntimeError("no")

    class Mail:
        def __init__(self, entry_id, subject, body, store_id, mailbox):
            self.Class = 43
            self.MessageClass = "IPM.Note"
            self.Subject = subject
            self.SenderName = "A"
            self.SenderEmailAddress = "a@x.com"
            self.EntryID = entry_id
            self.Body = body
            self.ReceivedTime = now
            self.PropertyAccessor = PropertyAccessor
            self.Parent = type("Parent", (), {"Store": type("Store", (), {"StoreID": store_id, "DisplayName": mailbox})()})()

    class Items(list):
        def Sort(self, *_args, **_kwargs):
            return None

    class Inbox:
        def __init__(self, mails):
            self.Items = Items(mails)

    class Store:
        def __init__(self, sid, inbox, name):
            self.StoreID = sid
            self.DisplayName = name
            self._inbox = inbox

        def GetDefaultFolder(self, _kind):
            return self._inbox

    class Account:
        def __init__(self, store, smtp):
            self.DeliveryStore = store
            self.SmtpAddress = smtp
            self.DisplayName = smtp

    class Namespace:
        def __init__(self, stores, accounts):
            self.Stores = stores
            self.Accounts = accounts
            self.CurrentUser = type("User", (), {"Name": "Yuan"})()

    personal_mails = [
        Mail(f"p-{i}", "hello", "", "personal", "yuan@personal.com") for i in range(30)
    ]
    pitt_mail = Mail(
        "pitt-1",
        "Pitt CS Forum",
        "Join us on " + date_text + " at 3:00 PM in Alumni Hall.",
        "pitt",
        "yic327@pitt.edu",
    )
    personal = Store("personal", Inbox(personal_mails), "Personal")
    pitt = Store("pitt", Inbox([pitt_mail]), "Pitt")
    ns = Namespace(
        [personal, pitt],
        [Account(personal, "yuan@personal.com"), Account(pitt, "yic327@pitt.edu")],
    )
    found = []
    result = scan_inbox_with_namespace(ns, days=14, max_emails=10, sink=found.extend)
    assert "yic327@pitt.edu" in result["mailboxes"]
    assert result["scanned"] == 6
    assert any(row.get("mailbox") == "yic327@pitt.edu" for row in found)


def test_meeting_invite_with_date_becomes_candidate():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from save_dates.outlook_client import mail_to_candidates

    now = datetime(2026, 8, 16, 15, 6, tzinfo=ZoneInfo("America/New_York"))

    class Invite:
        Class = 53
        MessageClass = "IPM.Schedule.Meeting.Request"
        Subject = "Pitt lecture"
        SenderName = "CS"
        SenderEmailAddress = "cs@pitt.edu"
        EntryID = "inv-1"
        Body = "Join us on August 20, 2026 at 3:00 PM in Alumni Hall."
        ReceivedTime = datetime(2026, 8, 16, 13, 0, tzinfo=timezone.utc)
        Start = datetime(2026, 8, 20, 15, 0)
        End = datetime(2026, 8, 20, 16, 0)
        AllDayEvent = False

        class PropertyAccessor:
            @staticmethod
            def GetProperty(_name):
                raise RuntimeError("no")

        class Parent:
            class Store:
                StoreID = "pitt"
                DisplayName = "yic327@pitt.edu"

    email_id, items = mail_to_candidates(Invite(), now=now)
    assert email_id == "inv-1"
    assert items
    assert items[0]["kind"] == "event"
    assert "2026-08-20" in items[0]["start_at"]
    assert items[0]["title_zh"]


def test_regular_mail_with_meeting_status_is_not_dropped():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from save_dates.outlook_client import mail_to_candidates

    now = datetime(2026, 8, 16, 15, 6, tzinfo=ZoneInfo("America/New_York"))

    class Mail:
        Class = 43
        MessageClass = "IPM.Note"
        MeetingStatus = 1
        Subject = "Eventbrite: campus forum"
        SenderName = "Eventbrite"
        SenderEmailAddress = "e@eventbrite.com"
        EntryID = "ev-1"
        Body = "Join us on August 20, 2026 at 3:00 PM."
        ReceivedTime = datetime(2026, 8, 16, 13, 0, tzinfo=timezone.utc)

        class PropertyAccessor:
            @staticmethod
            def GetProperty(_name):
                raise RuntimeError("no")

        class Parent:
            class Store:
                StoreID = "pitt"
                DisplayName = "yic327@pitt.edu"

    email_id, items = mail_to_candidates(Mail(), now=now)
    assert email_id == "ev-1"
    assert items


def test_demo_promo_can_be_cleared_locally():
    with TestClient(app) as client:
        client.post("/api/scan", json={"demo": True})
        items = client.get("/api/candidates?status=pending").json()["items"]
        promo = next(item for item in items if item.get("kind") == "promo")
        cleared = client.post(f"/api/candidates/{promo['id']}/accept")
        assert cleared.status_code == 200
        assert cleared.json()["item"]["status"] == "accepted"


def test_search_any_keyword_is_bilingual_and_does_not_write_calendar():
    with TestClient(app) as client:
        client.put("/api/settings", json={"lang": "zh"})
        client.post("/api/scan", json={"demo": True})
        before = client.get("/api/status").json()["counts"]
        for query in ("讲座", "lecture", "orientation", "迎新", "组会", "学生会"):
            payload = client.get("/api/search", params={"q": query}).json()
            assert payload["q"] == query
            assert payload["items"], query
            assert payload["items"][0]["received_at"] >= payload["items"][-1]["received_at"]
        typo = client.get("/api/search", params={"q": "orientattion"})
        assert typo.status_code == 200
        assert typo.json()["items"]
        after = client.get("/api/status").json()["counts"]
        assert after.get("accepted", 0) == before.get("accepted", 0)
        empty = client.get("/api/search", params={"q": ""})
        assert empty.status_code == 200
        assert empty.json()["items"] == []


def test_search_ranks_latest_received_first():
    from save_dates.search import _merge

    older = {
        "email_id": "old",
        "title": "workshop",
        "start_at": "2026-01-01T15:00",
        "kind": "event",
        "received_at": "2026-01-01T10:00:00",
        "score": 1.0,
        "id": 1,
    }
    newer = {
        "email_id": "new",
        "title": "workshop",
        "start_at": "2026-08-16T15:00",
        "kind": "event",
        "received_at": "2026-08-16T18:00:00",
        "score": 0.8,
        "id": 2,
    }
    merged = _merge([older], [newer], limit=12)
    assert merged[0]["email_id"] == "new"
