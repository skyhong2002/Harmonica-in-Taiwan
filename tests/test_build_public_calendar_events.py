import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_public_calendar_events as calendar  # noqa: E402


class PublicCalendarExtractionTests(unittest.TestCase):
    def test_multi_event_post_uses_candidate_specific_fields(self):
        item = {
            "source": "臺灣口琴音樂節 Taiwan Harmonica Music Festival",
            "source_id": "ig_taiwanharmonica",
            "platform": "instagram",
            "posted_at_local": "2026-07-14 15:47",
            "link": "https://www.instagram.com/p/Daw_UL_kxiZ/",
            "text": (
                "📌2026 臺灣口琴音樂節即將於 8 月 7 日至 8 月 9 日，"
                "在國立陽明交通大學光復校區與新竹市文化局演藝廳登場！\n"
                "本年度特別規劃兩場音樂節前導活動，而本場「前導音樂會」即為第二場活動！\n"
                "前導音樂會採線上報名，名額有限。\n"
                "2026 臺灣口琴音樂節：前導音樂會資訊\n"
                "📍時間：2026/07/25 (六) 14:00\n"
                "📍地點：竹東親愛愛樂音樂巷-音樂廳\n"
                "(新竹縣竹東鎮東林路194巷8號)"
            ),
        }

        events = calendar.extract_events(
            [item],
            overrides={},
            llm_token="",
            llm_cache={"version": 1, "items": {}},
        )

        prelude = next(event for event in events if event["start"].startswith("2026-07-25"))
        self.assertEqual(prelude["title"], "2026 臺灣口琴音樂節：前導音樂會")
        self.assertEqual(prelude["start"], "2026-07-25T14:00:00+08:00")
        self.assertEqual(prelude["end"], "2026-07-25T16:00:00+08:00")
        self.assertEqual(prelude["location"], "竹東親愛愛樂音樂巷-音樂廳")
        self.assertFalse(prelude["allDay"])

        festival = next(event for event in events if event["start"].startswith("2026-08-07"))
        self.assertEqual(
            festival["location"],
            "國立陽明交通大學光復校區與新竹市文化局演藝廳",
        )
        self.assertEqual(festival["calendarReview"]["country"], "臺灣")
        self.assertNotEqual(festival["venue"], "線上直播")

    def test_pin_time_is_not_treated_as_location(self):
        text = "📍時間：2026/07/25 14:00\n📍地點：竹東親愛愛樂音樂巷-音樂廳"
        self.assertEqual(calendar.extract_location(text), "竹東親愛愛樂音樂巷-音樂廳")

    def test_narrative_location_does_not_include_leading_date(self):
        text = "活動將於 8 月 7 日至 8 月 9 日在國立陽明交通大學光復校區登場"
        self.assertEqual(calendar.extract_location(text), "國立陽明交通大學光復校區")

    def test_cancelled_event_is_not_published(self):
        item = {
            "source": "臺灣口琴音樂節 THMF",
            "source_id": "ig_taiwanharmonica",
            "platform": "instagram",
            "posted_at_local": "2026-07-15 12:00",
            "link": "https://example.test/cancelled",
            "text": "⚠️活動停辦公告：2026/08/07 於新竹市文化局演藝廳舉行的口琴音樂會取消。",
        }
        self.assertEqual(
            calendar.extract_events(
                [item],
                overrides={},
                llm_token="",
                llm_cache={"version": 1, "items": {}},
            ),
            [],
        )

    def test_online_registration_does_not_override_taiwan_review(self):
        review_text = "前導音樂會 竹東親愛愛樂音樂巷-音樂廳 新竹縣竹東鎮 需線上報名"
        is_online, is_taiwan = calendar.review_event_modes("臺灣", review_text)
        self.assertFalse(is_online)
        self.assertTrue(is_taiwan)
        self.assertFalse(calendar.is_online_event_text("免費參與，請先線上報名"))
        self.assertTrue(calendar.is_online_event_text("線上講座，請先線上報名"))


if __name__ == "__main__":
    unittest.main()
