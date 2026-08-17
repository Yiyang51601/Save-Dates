from datetime import datetime
from zoneinfo import ZoneInfo

from save_dates.priority import attach_priority, priority_score, sort_pending

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 16, 18, 0, tzinfo=TZ)


def _item(**kwargs):
    row = {
        "id": kwargs.pop("id", 1),
        "title": "Campus lecture",
        "subject": "Campus lecture",
        "snippet": "Join us in Alumni Hall.",
        "matched_text": "",
        "sender": "Student Union",
        "mailbox": "yuan@school.edu",
        "kind": "event",
        "start_at": "2026-08-17T15:00",
        "task_type": "",
    }
    row.update(kwargs)
    return row


def test_sooner_event_outranks_later_event():
    soon = priority_score(_item(start_at="2026-08-17T15:00"), now=NOW)
    later = priority_score(_item(start_at="2026-09-20T15:00"), now=NOW)
    assert soon > later


def test_dated_event_outranks_task_and_promo():
    event = priority_score(_item(kind="event", start_at="2026-09-20T15:00"), now=NOW)
    task = priority_score(
        _item(kind="task", title="Finish chapter 3", subject="Reading", start_at="2026-08-16T00:00"),
        now=NOW,
    )
    promo = priority_score(
        _item(
            kind="promo",
            title="Flash sale 40% off",
            snippet="Click to unsubscribe.",
            sender="Deals noreply",
        ),
        now=NOW,
    )
    assert event > task > promo


def test_urgency_keywords_boost_and_pending_sorts_high_first():
    plain = attach_priority(_item(id=1, title="Weekly seminar"), now=NOW)
    urgent = attach_priority(
        _item(id=2, title="RSVP by deadline", snippet="Please reply ASAP 务必尽快"),
        now=NOW,
    )
    promo = attach_priority(_item(id=3, kind="promo", title="Coupon inside"), now=NOW)
    assert urgent["priority"] > plain["priority"]
    ordered = sort_pending([promo, plain, urgent])
    assert [row["id"] for row in ordered] == [2, 1, 3]
    assert urgent["priority_band"] == "high"
    assert promo["priority_band"] == "low"
