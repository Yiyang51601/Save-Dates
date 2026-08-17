from datetime import datetime
from zoneinfo import ZoneInfo

from save_dates.config import DEFAULT_GRAPH_CLIENT_ID, GRAPH_REDIRECT_URI, GRAPH_SCOPES
from save_dates.graph_client import message_to_candidates

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 16, 15, 6, tzinfo=TZ)


def test_graph_message_extracts_chinese_datetime():
    email_id, items = message_to_candidates(
        {
            "id": "AAMkAGI-test",
            "subject": "讲座通知",
            "from": {"emailAddress": {"name": "学生会", "address": "union@school.edu"}},
            "receivedDateTime": "2026-08-16T13:00:00Z",
            "body": {"contentType": "text", "content": "周五下午3点在大礼堂举办讲座，欢迎参加。"},
            "internetMessageId": "<id@school.edu>",
            "webLink": "https://outlook.office.com/mail/id/demo",
            "meetingMessageType": "none",
            "isDraft": False,
        },
        now=NOW,
    )
    assert email_id.startswith("graph:")
    assert items
    assert items[0]["mail_url"].startswith("https://outlook.office.com/")
    assert "2026-08-21" in items[0]["start_at"]


def test_graph_meeting_invite_without_date_is_skipped():
    email_id, items = message_to_candidates(
        {
            "id": "invite-1",
            "subject": "Meeting",
            "receivedDateTime": "2026-08-16T13:00:00Z",
            "meetingMessageType": "meetingRequest",
            "isDraft": False,
        },
        now=NOW,
    )
    assert email_id == "graph:invite-1"
    assert items == []


def test_graph_meeting_invite_with_date_is_kept():
    email_id, items = message_to_candidates(
        {
            "id": "invite-2",
            "subject": "Pitt CS Forum",
            "receivedDateTime": "2026-08-16T13:00:00Z",
            "meetingMessageType": "meetingRequest",
            "isDraft": False,
            "body": {
                "contentType": "text",
                "content": "Join us on August 20, 2026 at 3:00 PM in Alumni Hall.",
            },
        },
        now=NOW,
    )
    assert email_id == "graph:invite-2"
    assert items
    assert "2026-08-20" in items[0]["start_at"]
    assert items[0]["title_zh"]
    assert "Alumni Hall" in (items[0].get("location") or "")


def test_graph_auth_is_public_native_client():
    import inspect

    from save_dates import graph_auth

    source = inspect.getsource(graph_auth)
    assert DEFAULT_GRAPH_CLIENT_ID == "65f4dd53-e782-46a4-a0b1-8ccd331dd6ff"
    assert GRAPH_REDIRECT_URI == "http://localhost"
    assert GRAPH_SCOPES == ("User.Read", "Mail.Read", "Mail.ReadWrite", "Calendars.ReadWrite")
    assert "PublicClientApplication" in source
    assert "acquire_token_interactive" in source
    assert "http://localhost" in source
    assert "client_secret" not in source
    assert "client_credential" not in source


def test_graph_calendar_payload_includes_location_and_body(monkeypatch):
    from datetime import datetime, timedelta

    from save_dates import graph_client

    captured = {}

    def fake_request(method, url, token, json=None):
        captured["json"] = json
        return {"id": "evt-1"}

    monkeypatch.setattr(graph_client, "graph_request", fake_request)
    start = datetime(2026, 8, 20, 9, 0, tzinfo=TZ)
    event_id = graph_client.create_calendar_event(
        "tok",
        "SPH Orientation",
        start,
        start + timedelta(hours=1),
        False,
        body="入口：建议从 Fifth Avenue 入口进\n要带：充满电的手机",
        location="Public Health Building 5楼 A521/A522",
    )
    payload = captured["json"]
    assert event_id == "evt-1"
    assert payload["subject"] == "SPH Orientation"
    assert payload["location"]["displayName"].startswith("Public Health")
    assert "A521" in payload["location"]["displayName"]
    assert "入口" in payload["body"]["content"]
    assert "要带" in payload["body"]["content"]


def test_graph_calendar_omits_empty_location(monkeypatch):
    from datetime import datetime, timedelta

    from save_dates import graph_client

    captured = {}

    def fake_request(method, url, token, json=None):
        captured["json"] = json
        return {"id": "evt-2"}

    monkeypatch.setattr(graph_client, "graph_request", fake_request)
    start = datetime(2026, 9, 1, tzinfo=TZ)
    graph_client.create_calendar_event(
        "tok", "Deadline", start, start + timedelta(days=1), True, body="source", location=""
    )
    assert "location" not in captured["json"]
    assert captured["json"]["body"]["content"] == "source"
