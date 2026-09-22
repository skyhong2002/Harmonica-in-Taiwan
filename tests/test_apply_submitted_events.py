import sys
import csv
import json
import tempfile
from unittest import mock
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import apply_submitted_events as submitted  # noqa: E402


class SubmittedEventMergeTests(unittest.TestCase):
    def test_submitted_event_requires_publishable_core_fields(self):
        self.assertIsNone(
            submitted.submitted_event(
                {
                    "submission_id": "response-1",
                    "evidence_url": "https://example.org/event",
                    "event_name": "活動",
                    "start": "2026-08-01",
                    "venue": "",
                }
            )
        )

    def test_merge_deduplicates_evidence_url_and_preserves_new_event(self):
        generated = [
            {
                "evidenceUrl": "https://example.org/already-there",
                "eventName": "既有活動",
                "start": "2026-08-01",
                "title": "既有活動",
            }
        ]
        duplicate = {
            "evidenceUrl": "https://example.org/already-there",
            "eventName": "不同名稱也不應重複",
            "start": "2026-08-01",
            "title": "不同名稱也不應重複",
        }
        new_event = {
            "evidenceUrl": "https://example.org/new",
            "eventName": "新活動",
            "start": "2026-08-02",
            "title": "新活動",
        }
        merged = submitted.merge_events(generated, [duplicate, new_event])
        self.assertEqual(len(merged), 2)
        self.assertEqual(
            {item["evidenceUrl"] for item in merged},
            {"https://example.org/already-there", "https://example.org/new"},
        )


class GlobalCalendarMergeTests(unittest.TestCase):
    def row(self, **values):
        return {"submission_id": "global", "evidence_url": "https://example.org/global", "event_name": "Global concert",
                "start": "2026-10-01T20:00:00+09:00", "end": "2026-10-01T21:00:00+09:00", "all_day": "false",
                "venue": "Tokyo concert hall", "country": "JP", "timezone": "Asia/Tokyo", "event_mode": "physical", **values}

    def test_legacy_rows_keep_taiwan_scope_but_new_missing_metadata_is_rejected(self):
        legacy = self.row(start="2026-10-01", end="2026-10-01", all_day="true")
        for key in ("country", "timezone", "event_mode"):
            legacy.pop(key)
        event = submitted.submitted_event(legacy)
        self.assertEqual(event["calendarType"], "taiwan_physical")
        self.assertEqual(event["timezone"], "Asia/Taipei")
        self.assertEqual(event["end"], "2026-10-02")
        self.assertIsNone(submitted.submitted_event({**legacy, "country": "JP"}))
        self.assertIsNone(submitted.submitted_event(self.row(timezone="")))
        self.assertIsNone(submitted.submitted_event(self.row(event_mode="taiwan_physical")))

    def test_routes_three_calendars_and_ics_preserves_source_zone(self):
        from submission_intake import EVENT_FIELDS
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            csv_path = root / "submitted.csv"
            rows = [self.row(),
                    self.row(submission_id="online", evidence_url="https://example.org/online", country="WORLD", timezone="UTC", event_mode="online", start="2026-10-01T12:00:00+00:00", end="2026-10-01T13:00:00+00:00", venue="Public livestream"),
                    self.row(submission_id="taiwan", evidence_url="https://example.org/taiwan", country="TW", timezone="Asia/Taipei", event_mode="physical", start="2026-10-01", end="2026-10-02", all_day="true", venue="Taipei")]
            with csv_path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            for name, filename in [('SUBMISSIONS','submitted.csv'), ('JSON_PATH','public.json'), ('OVERSEAS_JSON_PATH','overseas.json'), ('ONLINE_JSON_PATH','online.json'), ('JS_PATH','public.js')]:
                stack.enter_context(mock.patch.object(submitted, name, root / filename))
            for name, filename in [('ICS_PATH','public.ics'), ('OVERSEAS_ICS_PATH','overseas.ics'), ('ONLINE_ICS_PATH','online.ics')]:
                stack.enter_context(mock.patch.object(submitted.calendar, name, root / filename))
            (root / 'public.json').write_text(json.dumps({'events': [], 'generatedAt': '2026-09-23T00:00:00Z'}))
            for iteration in range(2):
                self.assertEqual(submitted.main(), 0)
                for lane in ('public','overseas','online'):
                    data = json.loads((root / (lane + '.json')).read_text())
                    self.assertEqual(data['count'], 1, (lane, iteration))
                    self.assertEqual(data['submittedEvents'], 1)
            overseas = json.loads((root / 'overseas.json').read_text())['events'][0]
            self.assertEqual(overseas['timezone'], 'Asia/Tokyo')
            self.assertEqual(overseas['calendarReview']['country'], 'JP')
            self.assertIn('DTSTART;TZID=Asia/Tokyo:20261001T200000', (root / 'overseas.ics').read_text())
            self.assertIn('DTSTART;TZID=UTC:20261001T120000', (root / 'online.ics').read_text())
            self.assertIn('DTEND;VALUE=DATE:20261003', (root / 'public.ics').read_text())


if __name__ == "__main__":
    unittest.main()
