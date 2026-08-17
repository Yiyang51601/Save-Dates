from __future__ import annotations

from fastapi.testclient import TestClient

from save_dates.server import app


def test_home_and_static():
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Save Dates" in home.text
        assert "进阶 · 仅新 Outlook" in home.text
        assert "经典 Outlook" in home.text
        css = client.get("/static/styles.css")
        assert css.status_code == 200
        js = client.get("/static/app.js")
        assert js.status_code == 200


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
        assert client.get("/api/settings").json()["lang"] == "en"

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
        assert settings["has_bundled_graph_client"] is False
        client.put("/api/settings", json={"backend": "auto"})


def test_desktop_show_without_window_is_404():
    with TestClient(app) as client:
        response = client.post("/api/desktop/show")
        assert response.status_code == 404
        assert response.json()["detail"] == "no_desktop_window"


def test_microsoft_login_requires_client_id():
    with TestClient(app) as client:
        client.put("/api/settings", json={"graph_client_id": "", "backend": "graph"})
        response = client.post("/api/microsoft/login")
        assert response.status_code == 400
        assert response.json()["detail"] == "graph_client_id_missing"
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
