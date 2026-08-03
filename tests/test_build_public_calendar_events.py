import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_public_calendar_events as calendar  # noqa: E402


class PublicCalendarExtractionTests(unittest.TestCase):
    def test_date_candidates_accept_day_month_tour_dates(self):
        text = "CY LEO ASIA TOUR 2026 concert\n30/8 Hong Kong\n23/9 Taipei, Taiwan\n3/10 Singapore"

        candidates = calendar.date_candidates(text, calendar.parse_datetime("2026-07-31 08:00"))

        self.assertEqual(
            [start.isoformat() for start, _end, _context in candidates],
            ["2026-08-30", "2026-09-23", "2026-10-03"],
        )

    def test_deduplicate_events_keeps_more_complete_same_day_event(self):
        vague = {
            "id": "vague",
            "eventName": "桂冠之聲：2026臺灣口琴音樂節Gala音樂會",
            "title": "桂冠之聲：2026臺灣口琴音樂節Gala音樂會",
            "start": "2026-08-08",
            "location": "臺灣口琴音樂節活動場地",
            "confidence": 0.95,
            "source": "轉貼來源",
        }
        complete = {
            "id": "complete",
            "eventName": "桂冠之聲 Voices of the Laureates",
            "title": "桂冠之聲 Voices of the Laureates",
            "start": "2026-08-08T19:00:00+08:00",
            "location": "新竹市文化局演藝廳音樂廳",
            "confidence": 0.98,
            "source": "主辦單位",
        }

        self.assertEqual(calendar.deduplicate_events([vague, complete]), [complete])

    def test_deduplicate_events_does_not_merge_generic_festival_sessions(self):
        events = [
            {
                "id": "session-a",
                "eventName": "臺灣口琴音樂節 前導音樂會",
                "title": "臺灣口琴音樂節 前導音樂會",
                "start": "2026-08-08T14:00:00+08:00",
                "location": "新竹第一會場",
                "source": "主辦單位",
            },
            {
                "id": "session-b",
                "eventName": "臺灣口琴音樂節 Gala 音樂會",
                "title": "臺灣口琴音樂節 Gala 音樂會",
                "start": "2026-08-08T19:00:00+08:00",
                "location": "新竹第二會場",
                "source": "主辦單位",
            },
        ]

        self.assertEqual(len(calendar.deduplicate_events(events)), 2)

    def test_deduplicate_events_preserves_same_name_at_different_times(self):
        events = [
            {
                "id": "matinee",
                "eventName": "口琴體驗工作坊",
                "title": "口琴體驗工作坊",
                "start": "2026-08-08T14:00:00+08:00",
                "location": "新竹市文化局演藝廳",
                "source": "主辦單位",
            },
            {
                "id": "evening",
                "eventName": "口琴體驗工作坊",
                "title": "口琴體驗工作坊",
                "start": "2026-08-08T19:00:00+08:00",
                "location": "新竹市文化局演藝廳",
                "source": "主辦單位",
            },
        ]

        self.assertEqual(len(calendar.deduplicate_events(events)), 2)

    def test_deduplicate_events_merges_overlapping_multiday_festival_variants(self):
        events = [
            {
                "id": "partial",
                "eventName": "第十五届亚太口琴节",
                "title": "第十五届亚太口琴节",
                "start": "2026-07-23",
                "end": "2026-07-24",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "中国江阴",
                "confidence": 0.84,
                "source": "轉貼來源",
            },
            {
                "id": "complete",
                "eventName": "第十五屆亞太口琴節",
                "title": "第十五屆亞太口琴節",
                "start": "2026-07-24",
                "end": "2026-07-29",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "中國無錫",
                "confidence": 0.98,
                "source": "受邀演出團體",
            },
            {
                "id": "single-day",
                "eventName": "第十五屆亞太口琴節",
                "title": "第十五屆亞太口琴節",
                "start": "2026-07-25",
                "end": "2026-07-26",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "中國無錫",
                "confidence": 0.95,
                "source": "受邀演出團體",
            },
        ]

        self.assertEqual(calendar.deduplicate_events(events), [events[1]])

    def test_deduplicate_events_preserves_adjacent_same_name_concerts(self):
        events = [
            {
                "id": "day-one",
                "eventName": "巡迴音樂會",
                "title": "巡迴音樂會",
                "start": "2026-07-23",
                "end": "2026-07-24",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "東京",
                "source": "主辦單位",
            },
            {
                "id": "day-two",
                "eventName": "巡迴音樂會",
                "title": "巡迴音樂會",
                "start": "2026-07-24",
                "end": "2026-07-25",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "大阪",
                "source": "主辦單位",
            },
        ]

        self.assertEqual(len(calendar.deduplicate_events(events)), 2)

    def test_deduplicate_events_keeps_distinct_same_organiser_events_on_one_day(self):
        events = [
            {
                "id": "concert",
                "eventName": "新竹市立青少年口琴樂團 春季音樂會",
                "title": "新竹市立青少年口琴樂團 春季音樂會",
                "start": "2026-05-01",
                "location": "新竹市文化局演藝廳",
                "confidence": 0.9,
                "source": "主辦單位",
            },
            {
                "id": "recruitment",
                "eventName": "新竹市立青少年口琴樂團 團員招募說明會",
                "title": "新竹市立青少年口琴樂團 團員招募說明會",
                "start": "2026-05-01",
                "location": "竹科館",
                "confidence": 0.8,
                "source": "轉貼來源",
            },
        ]

        self.assertEqual(
            [event["id"] for event in calendar.deduplicate_events(events)],
            ["concert", "recruitment"],
        )

    def test_deduplicate_events_keeps_verified_submission_over_scraped_event(self):
        submitted = {
            "id": "submission-1",
            "eventName": "口琴音樂會",
            "title": "口琴音樂會",
            "start": "2026-09-01",
            "location": "台北中山堂",
            "confidence": 1.0,
            "platform": calendar.SUBMITTED_PLATFORM,
            "source": "臺灣口琴觀測站資料回報",
        }
        scraped = {
            "id": "scraped-1",
            "eventName": "口琴音樂會",
            "title": "口琴音樂會",
            "start": "2026-09-01T19:30:00+08:00",
            "location": "台北中山堂",
            "confidence": 1.0,
            "source": "instagram",
        }

        self.assertEqual(calendar.deduplicate_events([submitted, scraped]), [submitted])
        self.assertEqual(calendar.deduplicate_events([scraped, submitted]), [submitted])

    def test_deduplicate_events_preserves_back_to_back_camp_sessions(self):
        events = [
            {
                "id": "session-one",
                "eventName": "口琴夏令營",
                "title": "口琴夏令營",
                "start": "2026-07-06",
                "end": "2026-07-10",
                "allDay": True,
                "calendarType": calendar.TAIWAN_PHYSICAL,
                "location": "臺北",
                "confidence": 0.9,
                "source": "主辦單位",
            },
            {
                "id": "session-two",
                "eventName": "口琴夏令營",
                "title": "口琴夏令營",
                "start": "2026-07-10",
                "end": "2026-07-14",
                "allDay": True,
                "calendarType": calendar.TAIWAN_PHYSICAL,
                "location": "高雄",
                "confidence": 0.9,
                "source": "主辦單位",
            },
        ]

        self.assertEqual(len(calendar.deduplicate_events(events)), 2)

    def test_deduplicate_events_returns_events_sorted_by_start(self):
        events = [
            {
                "id": "partial-festival",
                "eventName": "第十五届亚太口琴节",
                "title": "第十五届亚太口琴节",
                "start": "2026-07-23",
                "end": "2026-07-24",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "中国江阴",
                "confidence": 0.84,
                "source": "轉貼來源",
            },
            {
                "id": "complete-festival",
                "eventName": "第十五屆亞太口琴節",
                "title": "第十五屆亞太口琴節",
                "start": "2026-07-24",
                "end": "2026-07-29",
                "allDay": True,
                "calendarType": calendar.OVERSEAS_PHYSICAL,
                "location": "中國無錫",
                "confidence": 0.98,
                "source": "受邀演出團體",
            },
            {
                "id": "unrelated",
                "eventName": "口琴獨奏會",
                "title": "口琴獨奏會",
                "start": "2026-07-23T10:00:00+08:00",
                "location": "臺北",
                "confidence": 0.9,
                "source": "主辦單位",
            },
        ]

        deduped = calendar.deduplicate_events(events)
        starts = [event["start"] for event in deduped]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual([event["id"] for event in deduped], ["unrelated", "complete-festival"])

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

    def test_llm_review_classifies_all_three_calendar_modes(self):
        overseas = calendar.normalize_llm_calendar_review(
            {
                "include": True,
                "eventMode": "overseas_physical",
                "candidateDateMatches": True,
                "country": "日本",
                "timezone": "Asia/Tokyo",
                "eventName": "東京口琴音樂會",
                "venue": "Tokyo Concert Hall",
                "city": "東京",
                "confidence": 0.96,
            }
        )
        online = calendar.normalize_llm_calendar_review(
            {
                "include": True,
                "eventMode": "online",
                "candidateDateMatches": True,
                "country": "線上",
                "timezone": "Europe/Berlin",
                "eventName": "Online Harmonica Workshop",
                "venue": "YouTube Live",
                "confidence": 0.93,
            }
        )
        taiwan = calendar.normalize_llm_calendar_review(
            {
                "include": True,
                "eventMode": "taiwan_physical",
                "candidateDateMatches": True,
                "country": "臺灣",
                "timezone": "UTC",
                "eventName": "新竹口琴音樂會",
                "venue": "新竹市文化局演藝廳",
                "details": "採線上報名",
                "confidence": 0.98,
            }
        )
        self.assertEqual(overseas["eventMode"], calendar.OVERSEAS_PHYSICAL)
        self.assertEqual(overseas["timezone"], "Asia/Tokyo")
        self.assertEqual(online["eventMode"], calendar.ONLINE)
        self.assertEqual(online["timezone"], "Europe/Berlin")
        self.assertEqual(taiwan["eventMode"], calendar.TAIWAN_PHYSICAL)
        self.assertEqual(taiwan["timezone"], "Asia/Taipei")
        self.assertEqual(
            calendar.classify_event_mode(
                "臺灣",
                "大阪 心斎橋PARCO 14F SPACE14",
                calendar.TAIWAN_PHYSICAL,
            ),
            calendar.OVERSEAS_PHYSICAL,
        )
        self.assertEqual(calendar.infer_country("東京 田園調布"), "日本")
        self.assertEqual(calendar.infer_country("中国江阴"), "中國")

        mismatched = calendar.normalize_llm_calendar_review(
            {
                "include": True,
                "eventMode": "overseas_physical",
                "candidateDateMatches": False,
                "country": "新加坡",
                "timezone": "Asia/Singapore",
                "eventName": "Wonderful Sunday",
                "venue": "Singapore HAS Clubhouse",
                "confidence": 0.99,
            }
        )
        self.assertFalse(mismatched["include"])

    def test_overseas_event_keeps_local_timezone_in_ics(self):
        event = {
            "id": "tokyo-event",
            "title": "東京口琴音樂會",
            "start": "2026-08-02T19:00:00+09:00",
            "end": "2026-08-02T21:00:00+09:00",
            "allDay": False,
            "timezone": "Asia/Tokyo",
            "location": "Tokyo Concert Hall",
            "evidenceUrl": "https://example.test/tokyo",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overseas.ics"
            calendar.write_ics(
                [event],
                "2026-07-15T12:00:00+08:00",
                path=path,
                calendar_name="國外口琴實體活動",
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("DTSTART;TZID=Asia/Tokyo:20260802T190000", text)
        self.assertIn("X-WR-CALNAME:國外口琴實體活動", text)


if __name__ == "__main__":
    unittest.main()
