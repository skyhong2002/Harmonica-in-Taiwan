import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_public_calendar_events as calendar


class CalendarLocationHeuristicsTests(unittest.TestCase):
    def review(self, **extra):
        return dict(include=True, country='臺灣', eventMode='taiwan_physical', timezone='Asia/Taipei', candidateDateMatches=True, eventName='Christmas Concert 山下伶', venue='鶴見區民文化センター サルビアホール', city='橫濱市', details='2026年12月13日15:00開演。', reason='日本橫濱的實體口琴演出；不是臺灣活動。', confidence=0.98, **extra)

    def test_explicit_yokohama_venue_repairs_legacy_cached_classification(self):
        for city in ('橫濱市', '横浜市', 'Yokohama'):
            review = self.review()
            review['city'] = city
            result = calendar.normalize_llm_calendar_review(review)
            self.assertTrue(result['include'])
            self.assertEqual(result['country'], '日本')
            self.assertEqual(result['eventMode'], 'overseas_physical')
            self.assertEqual(result['timezone'], 'Asia/Tokyo')

    def test_negative_reason_is_not_positive_taiwan_location_evidence(self):
        review = self.review()
        review.update(country='日本', eventMode='overseas_physical', city='', venue='サルビアホール', timezone='Asia/Tokyo')
        result = calendar.normalize_llm_calendar_review(review)
        self.assertEqual(result['country'], '日本')
        self.assertEqual(result['eventMode'], 'overseas_physical')

    def test_online_mode_is_not_replaced_by_studio_location(self):
        review = self.review()
        review.update(country='線上', eventMode='online', eventName='YouTube live stream', details='YouTube live stream', timezone='Asia/Tokyo')
        result = calendar.normalize_llm_calendar_review(review)
        self.assertEqual(result['eventMode'], 'online')
        self.assertEqual(result['country'], '線上')

    def test_unknown_place_does_not_default_to_taiwan(self):
        review = self.review()
        review.update(country='', eventMode='', city='', venue='Unknown hall', eventName='Harmonica concert', details='', reason='')
        result = calendar.normalize_llm_calendar_review(review)
        self.assertEqual(result['country'], '')
        self.assertFalse(result['include'])

    def test_offline_cached_review_is_repaired_without_inference(self):
        with patch.object(calendar, 'candidate_fingerprint', return_value='cached'), patch.object(calendar.watchdog, 'curl_json', side_effect=AssertionError('Network forbidden')):
            result = calendar.review_candidate_with_llm({}, start='', end='', context='', cache={'items': {'cached': self.review()}}, token='', base_url='', model='', timeout=1, stats={})
        self.assertEqual(result['country'], '日本')
        self.assertEqual(result['timezone'], 'Asia/Tokyo')

class CalendarAnnouncedTimesTests(unittest.TestCase):
    def item(self, text):
        return {'source': 'Dr. Blue 口琴樂團', 'text': text, 'link': 'https://example.org/announcement', 'posted_at': calendar.dt.datetime.now(calendar.dt.timezone.utc).isoformat()}

    def test_full_width_range_with_weekdays_expands_only_explicit_daily_schedule(self):
        text = '口琴音樂會【日期】09/25（五）～09/28（一）\n【時間】每晚 20:30～21:30\n【地點】武陵富野渡假村 2F展演廳'
        days = calendar.explicit_daily_candidates(text, calendar.parse_datetime('2026-09-06'))
        self.assertEqual([day.isoformat() for day, _, _ in days], ['2026-09-25', '2026-09-26', '2026-09-27', '2026-09-28'])
        self.assertEqual(calendar.explicit_daily_candidates(text.replace('每晚', ''), calendar.parse_datetime('2026-09-06')), [])
        self.assertEqual(calendar.explicit_daily_candidates(text.replace('20:30～21:30', '20:30'), calendar.parse_datetime('2026-09-06')), [])

    def test_daily_extraction_retains_four_announced_one_hour_performances(self):
        start = calendar.dt.datetime.now(calendar.TAIWAN_TZ).date() + calendar.dt.timedelta(days=3)
        last = start + calendar.dt.timedelta(days=3)
        text = f'口琴音樂會\n【日期】{start:%Y/%m/%d}～{last:%Y/%m/%d}\n【時間】每晚 20:30～21:30\n【地點】武陵富野渡假村 2F展演廳'
        events = calendar.extract_events([self.item(text)])
        self.assertEqual(len(events), 4)
        for offset, event in enumerate(events):
            day = start + calendar.dt.timedelta(days=offset)
            self.assertEqual(event['start'], f'{day}T20:30:00+08:00')
            self.assertEqual(event['end'], f'{day}T21:30:00+08:00')
            self.assertFalse(event['allDay'])
            self.assertFalse(event['endEstimated'])
            self.assertEqual(event['location'], '武陵富野渡假村 2F展演廳')

    def test_announced_overnight_end_rolls_to_next_civil_day(self):
        day = calendar.dt.datetime.now(calendar.TAIWAN_TZ).date() + calendar.dt.timedelta(days=3)
        events = calendar.extract_events([self.item(f'口琴音樂會 {day:%Y/%m/%d} 23:30～00:30\n地點：臺北音樂廳')])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['end'], f'{day + calendar.dt.timedelta(days=1)}T00:30:00+08:00')
        self.assertFalse(events[0]['endEstimated'])

    def test_unannounced_end_keeps_calendar_placeholder_explicitly_marked_estimated(self):
        day = calendar.dt.datetime.now(calendar.TAIWAN_TZ).date() + calendar.dt.timedelta(days=3)
        events = calendar.extract_events([self.item(f'口琴音樂會 {day:%Y/%m/%d} 20:30\n地點：臺北音樂廳')])
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]['endEstimated'])
        self.assertIn('End time not announced', calendar.calendar_description(events[0]))

class ExplicitRangeLocalizationTests(unittest.TestCase):
    def test_announced_ranges_support_ampm_and_east_asian_period_labels(self):
        for text, expected in [
            ('8:00–9:00 PM', ('20:00', '21:00')),
            ('11:30–1:00 PM', ('11:30', '13:00')),
            ('11:30 PM – 1:00 AM', ('23:30', '01:00')),
            ('下午 7:30～8:30', ('19:30', '20:30')),
            ('오후 7:30～8:30', ('19:30', '20:30')),
            ('午前 10:30～11:30', ('10:30', '11:30')),
            ('20:30～21:30', ('20:30', '21:30')),
        ]:
            self.assertEqual(calendar.explicit_time_range(text), expected)
        self.assertIsNone(calendar.explicit_time_range('Doors 19:00. Concert 20:30.'))


class CalendarAdversarialLocationAndScheduleTests(unittest.TestCase):
    def test_foreign_venue_name_does_not_override_known_city_country(self):
        review = dict(include=True, country='United States', eventMode='overseas_physical', timezone='America/New_York', candidateDateMatches=True, eventName='Harmonica concert', venue='Japan Society', city='New York', confidence=.99)
        result = calendar.normalize_llm_calendar_review(review)
        self.assertEqual(result['country'], 'United States')
        self.assertEqual(result['timezone'], 'America/New_York')

    def test_hotel_daily_breakfast_cannot_become_daily_concert(self):
        text = '口琴音樂會住宿方案\n住宿日期：2026/09/26～2026/09/29\n每天早餐07:00～09:00\n口琴演出只有2026/09/26晚上20:00\n地點：臺北音樂廳'
        self.assertEqual(calendar.explicit_daily_candidates(text, calendar.parse_datetime('2026-09-01')), [])
        self.assertEqual(calendar.extract_events([{'source': '口琴演出', 'text': text, 'link': 'https://example.org/hotel', 'posted_at': '2026-09-01'}]), [])

    def test_additional_schedule_times_require_review_instead_of_daily_expansion(self):
        text = '口琴音樂會\n【日期】09/25（五）～09/28（一）\n【時間】每晚 20:30～21:30\n早餐 07:00～09:00\n【地點】武陵富野渡假村'
        self.assertEqual(calendar.explicit_daily_candidates(text, calendar.parse_datetime('2026-09-01')), [])


if __name__ == '__main__':
    unittest.main()
