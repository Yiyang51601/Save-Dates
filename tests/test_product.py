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
        assert body["greeting"]

        scan = client.post("/api/scan", json={"demo": True})
        assert scan.status_code == 200
        payload = scan.json()
        assert payload["ok"] is True
        assert payload["added"] >= 1

        listed = client.get("/api/candidates?status=pending")
        assert listed.status_code == 200
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
