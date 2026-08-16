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
