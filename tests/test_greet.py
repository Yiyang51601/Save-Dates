from datetime import datetime

from save_dates.greet import given_name, greeting_phrase


def test_given_name_from_display_formats():
    assert given_name("Chen, Yuan") == "Yuan"
    assert given_name("Yuan Chen") == "Yuan"
    assert given_name("陈远达") == "远达"
    assert given_name("张伟") == "张伟"
    assert given_name("yuan.chen@school.edu") == "Yuan"
    assert given_name("Yuan Chen (yuan@school.edu)") == "Yuan"
    assert given_name("Outlook") == ""
    assert given_name("") == ""


def test_greeting_uses_name_and_hour():
    afternoon = datetime(2026, 8, 16, 16, 3)
    assert greeting_phrase("Chen, Yuan", "zh", afternoon) == "下午好，Yuan"
    assert greeting_phrase("Chen, Yuan", "en", afternoon) == "Good afternoon, Yuan."
    morning = datetime(2026, 8, 16, 8, 0)
    assert greeting_phrase("", "zh", morning) == "早上好"
    assert greeting_phrase("", "en", morning) == "Good morning."
