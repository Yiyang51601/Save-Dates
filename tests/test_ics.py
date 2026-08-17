from datetime import datetime
from zoneinfo import ZoneInfo

from save_dates.ics import is_ics_name, parse_ics_events

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 8, 17, 13, 0, tzinfo=TZ)

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Save Dates//Test//EN
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260824T090000
DTEND;TZID=America/New_York:20260824T105000
SUMMARY:EPID 2180 Lecture
LOCATION:Public Health Building A521
DESCRIPTION:Bring a charged laptop
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260825T140000
DTEND;TZID=America/New_York:20260825T155000
SUMMARY:GSR meeting
LOCATION:GSPH Room 221
DESCRIPTION:Weekly GSR calendar
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260826
DTEND;VALUE=DATE:20260827
SUMMARY:Department review
LOCATION:Cathedral of Learning
END:VEVENT
END:VCALENDAR
"""


def test_is_ics_name():
    assert is_ics_name("ClassesandGSR_Yiyang.ics")
    assert is_ics_name("schedule.ICAL")
    assert is_ics_name("invite", "text/calendar")
    assert not is_ics_name("photo.png", "image/png")


def test_parse_ics_multiple_vevents_keep_location():
    events = parse_ics_events(SAMPLE_ICS, now=NOW, tz=TZ, source_title="class calendar")
    assert len(events) == 3
    by_title = {event.title: event for event in events}
    lecture = by_title["EPID 2180 Lecture"]
    assert lecture.start.day == 24
    assert lecture.start.hour == 9
    assert lecture.all_day is False
    assert "Public Health Building" in lecture.location
    assert "A521" in lecture.location
    assert "laptop" in lecture.notes.lower()
    gsr = by_title["GSR meeting"]
    assert gsr.start.day == 25
    assert "221" in gsr.location
    review = by_title["Department review"]
    assert review.all_day is True
    assert review.start.day == 26
    assert "Cathedral" in review.location
