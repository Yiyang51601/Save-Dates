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
