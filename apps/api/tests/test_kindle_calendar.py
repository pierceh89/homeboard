from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import unittest

from app.page_context import build_kindle_calendar_context


KST = ZoneInfo("Asia/Seoul")


class KindleCalendarContextTest(unittest.TestCase):
    def test_builds_context_for_today_events(self):
        now = datetime(2026, 5, 22, 9, 30, tzinfo=KST)
        events = [
            SimpleNamespace(
                uid="all-day",
                summary="",
                start=datetime(2026, 5, 22, 0, 0, tzinfo=KST),
                end=datetime(2026, 5, 23, 0, 0, tzinfo=KST),
                is_all_day=True,
            ),
            SimpleNamespace(
                uid="timed",
                summary="점심",
                start=datetime(2026, 5, 22, 12, 0, tzinfo=KST),
                end=datetime(2026, 5, 22, 13, 30, tzinfo=KST),
                is_all_day=False,
            ),
        ]

        context = build_kindle_calendar_context(now, events=events)

        self.assertEqual(context["calendar_date_label"], "5. 22. (금)")
        self.assertFalse(context["calendar_error"])
        self.assertEqual(
            context["calendar_schedules"],
            [
                {"summary": "제목 없는 일정", "time_label": "하루 종일"},
                {"summary": "점심", "time_label": "오후 12:00 - 오후 1:30"},
            ],
        )

    def test_builds_empty_context_when_no_events_exist(self):
        now = datetime(2026, 5, 22, 9, 30, tzinfo=KST)

        context = build_kindle_calendar_context(now, events=[])

        self.assertEqual(context["calendar_schedules"], [])
        self.assertFalse(context["calendar_error"])

    def test_builds_error_context_when_fetch_failed(self):
        now = datetime(2026, 5, 22, 9, 30, tzinfo=KST)

        context = build_kindle_calendar_context(now, events=None, error=True)

        self.assertEqual(context["calendar_date_label"], "일정 오류")
        self.assertEqual(context["calendar_schedules"], [])
        self.assertTrue(context["calendar_error"])


if __name__ == "__main__":
    unittest.main()
