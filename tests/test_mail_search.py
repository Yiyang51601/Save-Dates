from datetime import datetime
from zoneinfo import ZoneInfo

from save_dates.extract import extract_all, score_search_fields
from save_dates.mail_search import expand_query

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 16, 15, 6, tzinfo=TZ)
RECEIVED = datetime(2026, 8, 16, 9, 0, tzinfo=TZ)


def test_expand_keeps_raw_query_and_unknown_words():
    terms = expand_query("Dr. Chen")
    folded = {item.casefold() for item in terms}
    assert "dr. chen" in folded
    assert "chen" in folded
    assert "orientation" not in folded


def test_expand_orientation_includes_chinese_synonyms():
    terms = {item.casefold() for item in expand_query("orientation")}
    assert "orientation" in terms
    assert "迎新" in terms
    assert "入学" in terms
    assert "迎新会" in terms


def test_expand_yingxin_includes_english_synonyms():
    terms = {item.casefold() for item in expand_query("迎新")}
    assert "迎新" in terms
    assert "orientation" in terms


def test_expand_meeting_and_exam_pairs():
    meeting = {item.casefold() for item in expand_query("组会")}
    assert "meeting" in meeting
    assert "组会" in meeting
    exam = {item.casefold() for item in expand_query("exam")}
    assert "考试" in exam
    lecture = {item.casefold() for item in expand_query("讲座")}
    assert "lecture" in lecture


def test_orientation_query_matches_chinese_only_mail():
    score, hit = score_search_fields(
        "orientation",
        "迎新周安排",
        "学生会",
        "本周五迎新活动，请新生准时到场。",
    )
    assert score >= 0.9
    assert hit


def test_yingxin_query_matches_english_only_mail():
    score, hit = score_search_fields(
        "迎新",
        "New Student Orientation Week",
        "ISSS",
        "Please attend orientation on Friday in the auditorium.",
    )
    assert score >= 0.9
    assert hit


def test_unknown_name_still_matches_subject_or_body():
    score, _ = score_search_fields(
        "Chen",
        "Re: paper",
        "Advisor",
        "Please send the revised draft to Chen before Friday.",
    )
    assert score >= 0.9
    miss, _ = score_search_fields(
        "Chen",
        "Office closed",
        "Facilities",
        "The building will reopen on Monday.",
    )
    assert miss == 0


def test_exam_does_not_match_example():
    score, _ = score_search_fields(
        "exam",
        "FYI",
        "Bot",
        "For example, bring a laptop to class.",
    )
    assert score == 0


def test_orientation_mail_can_extract_event_or_still_match():
    subject = "迎新周安排 Orientation Week"
    body = "迎新活动将于2026年8月20日下午3点在大礼堂举行。"
    score, _ = score_search_fields("orientation", subject, body)
    assert score >= 0.9
    items = extract_all(subject, body, RECEIVED, now=NOW, tz=TZ)
    assert items
    assert items[0].kind in {"event", "task"}
