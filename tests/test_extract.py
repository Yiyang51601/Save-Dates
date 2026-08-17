from datetime import datetime
from zoneinfo import ZoneInfo

from save_dates.extract import extract_all, extract_events, html_to_text, parse_time

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 16, 15, 6, tzinfo=TZ)
RECEIVED = datetime(2026, 8, 16, 9, 0, tzinfo=TZ)


def _first(subject: str, body: str, received=RECEIVED):
    events = extract_events(subject, body, received, now=NOW, tz=TZ)
    assert events, f"expected events in: {body}"
    return events[0]


def test_chinese_datetime_afternoon():
    event = _first("讲座通知", "将于2026年8月20日下午3点在大礼堂举办讲座，欢迎参加。")
    assert event.start.year == 2026
    assert event.start.month == 8
    assert event.start.day == 20
    assert event.start.hour == 15
    assert event.start.minute == 0
    assert event.start.tzinfo == TZ
    assert event.all_day is False


def test_month_day_uses_email_year():
    event = _first("活动", "报名截止：8月25日，请尽快提交。")
    assert event.start.date().isoformat() == "2026-08-25"
    assert event.all_day is True


def test_next_friday_from_sunday_email():
    event = _first("例会", "请于下周五下午2点到会议室开会。")
    assert event.start.date().isoformat() == "2026-08-21"
    assert event.start.hour == 14


def test_this_friday_in_past_is_ignored():
    events = extract_events("通知", "本周五已经结束。", RECEIVED, now=NOW, tz=TZ)
    assert events == []


def test_bare_friday_means_upcoming():
    event = _first("提醒", "周五晚上7点放映。")
    assert event.start.date().isoformat() == "2026-08-21"
    assert event.start.hour == 19


def test_tomorrow_relative_to_email_not_today():
    received = datetime(2026, 8, 15, 20, 0, tzinfo=TZ)
    event = _first("更新", "明天上午10点截止报名。", received)
    assert event.start.date().isoformat() == "2026-08-16"
    assert event.start.hour == 10


def test_iso_date_all_day():
    event = _first("Deadline", "截止日期：2026-09-01。")
    assert event.start.date().isoformat() == "2026-09-01"
    assert event.all_day is True


def test_english_datetime():
    event = _first("Seminar", "Join us on August 20, 2026 at 3:00 PM in the auditorium.")
    assert event.start.month == 8
    assert event.start.day == 20
    assert event.start.hour == 15
    assert event.all_day is False


def test_date_range():
    event = _first("开放日", "活动时间为8月20日至8月22日，欢迎参观。")
    assert event.start.date().isoformat() == "2026-08-20"
    assert event.end.date().isoformat() == "2026-08-23"
    assert event.all_day is True


def test_past_date_filtered():
    events = extract_events("旧闻", "2026年8月1日已经举办完毕。", RECEIVED, now=NOW, tz=TZ)
    assert events == []


def test_html_stripped_before_parse():
    body = "<html><p>会议定于<strong>2026年8月28日</strong>上午9点</p></html>"
    event = _first("会议", body)
    assert event.start.day == 28
    assert event.start.hour == 9
    assert "<" not in html_to_text(body)


def test_parse_time_half_past():
    assert parse_time("下午3点半").hour == 15
    assert parse_time("下午3点半").minute == 30


def test_advisor_thread_and_next_week():
    events = extract_events("Re: 论文修改", "下周把修改稿发我，周四左右也可以组会。", RECEIVED, now=NOW, tz=TZ)
    dates = {event.start.date().isoformat() for event in events}
    assert "2026-08-17" in dates
    assert "2026-08-20" in dates
    assert any(event.fuzzy for event in events)


def test_around_weekday_is_fuzzy():
    event = _first("组会", "周四左右方便见面吗？")
    assert event.start.date().isoformat() == "2026-08-20"
    assert event.fuzzy is True


def test_english_next_week_and_around_thursday():
    week = _first("Re: draft", "Please send the revised chapter next week.")
    assert week.fuzzy is True
    assert week.start.date().isoformat() == "2026-08-17"
    around = _first("Meeting", "Can we meet around Thursday afternoon?")
    assert around.start.date().isoformat() == "2026-08-20"
    assert around.start.hour == 15
    assert around.fuzzy is True


def test_end_of_month_fuzzy():
    event = _first("提醒", "本月底前把表格交了。")
    assert event.start.date().isoformat() == "2026-08-31"
    assert event.fuzzy is True


def test_homework_without_date_is_task():
    items = extract_all("阅读", "请把第三章看完，另外准备考试。", RECEIVED, now=NOW, tz=TZ)
    tasks = [item for item in items if item.kind == "task"]
    events = [item for item in items if item.kind == "event"]
    assert events == []
    assert tasks
    assert tasks[0].task_type == "homework"


def test_unscheduled_meet_is_task():
    items = extract_all("Re: 组会", "我们约个时间见面讨论论文。", RECEIVED, now=NOW, tz=TZ)
    assert items
    assert all(item.kind == "task" for item in items)
    assert any(item.task_type == "meet" for item in items)


def test_waiting_for_reply_is_followup_task():
    items = extract_all("时间确认", "等你回复方便的时间。", RECEIVED, now=NOW, tz=TZ)
    assert items
    assert items[0].kind == "task"
    assert items[0].task_type == "followup"


def test_dated_homework_is_event_not_task():
    items = extract_all("作业", "周五交作业。", RECEIVED, now=NOW, tz=TZ)
    assert items
    assert all(item.kind == "event" for item in items)
    assert not any(item.kind == "task" for item in items)


def test_homework_can_sit_beside_a_dated_event():
    items = extract_all(
        "提醒",
        "周五下午开会。另外请把第三章看完。",
        RECEIVED,
        now=NOW,
        tz=TZ,
    )
    kinds = {item.kind for item in items}
    assert "event" in kinds
    assert "task" in kinds
    assert any(item.task_type == "homework" for item in items)


def test_promo_with_unsubscribe():
    items = extract_all(
        "限时折扣",
        "优惠券即将过期。不想再收到请点退订。",
        RECEIVED,
        now=NOW,
        tz=TZ,
    )
    assert items
    assert items[0].kind == "promo"


def test_dated_mail_is_not_promo_even_with_unsubscribe():
    items = extract_all(
        "讲座通知",
        "周五下午3点在大礼堂举办讲座。不想收通知请退订。",
        RECEIVED,
        now=NOW,
        tz=TZ,
    )
    assert items
    assert all(item.kind != "promo" for item in items)
    assert any(item.kind == "event" for item in items)


def test_advisor_sender_is_not_promo():
    items = extract_all(
        "提醒",
        "请尽快看一下草稿。",
        RECEIVED,
        now=NOW,
        tz=TZ,
        sender="导师",
    )
    assert all(item.kind != "promo" for item in items)


def test_fuzzy_orientation_accepts_typo():
    from save_dates.extract import best_fuzzy_hit, fuzzy_score, match_threshold

    exact = fuzzy_score("orientation", "Welcome to student orientation week.")
    typo, fragment = best_fuzzy_hit("orientation", "New student orientattion starts Monday.")
    unrelated = fuzzy_score("orientation", "grocery list apples bananas milk")
    assert exact == 1.0
    assert typo >= 0.85
    assert "orient" in fragment
    assert unrelated < match_threshold("orientation")
    assert fuzzy_score("讲座", "本周五下午3点举办讲座，欢迎参加。") == 1.0


def test_extracts_location_and_notes_from_labeled_event_mail():
    from save_dates.extract import extract_location_notes

    subject = "SPH epi new student Orientation"
    body = (
        "时间：2026年8月20日（周四）\n"
        "地点：Public Health Building 5楼，A521/A522\n"
        "入口：建议从 Fifth Avenue 入口进（大雕塑正下方）\n"
        "要带：充满电的手机、平板或电脑，现场有活动需要使用。"
    )
    event = _first(subject, body)
    assert event.start.year == 2026
    assert event.start.month == 8
    assert event.start.day == 20
    location, notes = extract_location_notes(subject, body)
    assert "Public Health Building" in location
    assert "A521" in location
    assert "5楼" in location
    assert "入口" in notes
    assert "Fifth Avenue" in notes
    assert "要带" in notes or "手机" in notes
    assert event.location == location
    assert event.notes == notes
    assert "Orientation" in event.title


def test_extracts_english_venue_rsvp_and_what_to_bring():
    event = _first(
        "Campus lecture",
        "Join us on August 21, 2026 at 3:00 PM.\n"
        "Venue: Alumni Hall Room 200\n"
        "RSVP: please reply by Wednesday\n"
        "What to bring: student ID",
    )
    assert event.start.day == 21
    assert "Alumni Hall" in event.location
    assert "200" in event.location
    assert "RSVP" in event.notes or "reply" in event.notes.lower()
    assert "student ID" in event.notes


def test_zoom_link_becomes_location_when_no_physical_place():
    event = _first(
        "Seminar",
        "Seminar on August 22, 2026 at 10:00 AM\n"
        "Join Zoom: https://pitt.zoom.us/j/123456789",
    )
    assert "zoom.us" in event.location.lower()
    assert event.start.day == 22


def test_physical_place_keeps_zoom_in_notes():
    event = _first(
        "Hybrid meeting",
        "Meeting on August 23, 2026 at 2:00 PM\n"
        "Location: Cathedral of Learning Room 332\n"
        "Zoom: https://pitt.zoom.us/j/987654321",
    )
    assert "Cathedral of Learning" in event.location
    assert "332" in event.location
    assert "zoom.us" in event.notes.lower()
    assert "zoom.us" not in event.location.lower()


def test_building_and_room_labels_are_combined():
    event = _first(
        "Office hours",
        "August 24, 2026 at 11:00 AM\nBuilding: Public Health Building\nRoom: A521/A522",
    )
    assert "Public Health Building" in event.location
    assert "A521" in event.location


def test_empty_location_and_notes_when_mail_has_none():
    event = _first("Deadline", "截止日期：2026-09-01。")
    assert event.start.date().isoformat() == "2026-09-01"
    assert event.location == ""
    assert event.notes == ""


def test_chinese_unlabeled_hall_is_location():
    event = _first("讲座通知", "将于2026年8月20日下午3点在大礼堂举办讲座，欢迎参加。")
    assert "礼堂" in event.location
    assert event.start.hour == 15
