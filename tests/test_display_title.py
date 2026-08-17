from save_dates.display_title import chinese_display_title, chinese_from_text


def test_prefers_chinese_already_in_subject():
    title = chinese_display_title(
        title="New Student Orientation",
        subject="New Student Orientation / 迎新周",
        snippet="Welcome to orientation week.",
    )
    assert title == "迎新周"


def test_english_lecture_gets_chinese_label():
    title = chinese_display_title(
        title="Campus open day lecture",
        subject="Campus open day lecture",
        snippet="Join us this Friday at 3:00 PM.",
        kind="event",
    )
    assert title.startswith("开放日")
    assert "Campus open day lecture" in title


def test_task_and_promo_follow_display_language():
    homework = chinese_display_title(
        title="Finish chapter 3",
        subject="Reading for seminar",
        kind="task",
        task_type="homework",
    )
    assert homework.startswith("作业")
    promo = chinese_display_title(
        title="Flash sale: 40% off everything",
        subject="Flash sale: 40% off everything",
        snippet="Limited-time coupon inside. Click to unsubscribe.",
        kind="promo",
        task_type="ad",
    )
    assert promo.startswith("促销广告")


def test_chinese_from_mixed_slash_title():
    assert chinese_from_text("Forum / 论坛讲座") == "论坛讲座"
