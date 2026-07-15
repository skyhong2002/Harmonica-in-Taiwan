import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import sync_google_calendar_events as sync  # noqa: E402


class GoogleCalendarSyncTests(unittest.TestCase):
    def test_timed_event_resource_preserves_event_timezone(self):
        resource = sync.event_resource(
            {
                "id": "tokyo-event",
                "eventName": "東京口琴音樂會",
                "start": "2026-08-02T19:00:00+09:00",
                "end": "2026-08-02T21:00:00+09:00",
                "allDay": False,
                "timezone": "Asia/Tokyo",
                "location": "Tokyo Concert Hall",
                "evidenceUrl": "https://example.test/tokyo",
            }
        )
        self.assertEqual(resource["start"]["timeZone"], "Asia/Tokyo")
        self.assertEqual(resource["end"]["timeZone"], "Asia/Tokyo")
        self.assertEqual(
            resource["extendedProperties"]["private"][sync.PRIVATE_EVENT_ID_KEY],
            "tokyo-event",
        )

    def test_calendar_metadata_contains_three_distinct_modes(self):
        rows = sync.load_calendar_metadata_rows()
        self.assertEqual(
            {row.get("event_mode") for row in rows},
            {"taiwan_physical", "overseas_physical", "online"},
        )
        self.assertEqual(len({row["calendar_id"] for row in rows}), 3)
        self.assertEqual(len(sync.selected_calendar_metadata(rows)), 3)
        self.assertEqual(
            [row["calendar_key"] for row in sync.selected_calendar_metadata(rows, calendar_key="online")],
            ["online"],
        )
        overridden = sync.selected_calendar_metadata(rows, calendar_id="explicit@example.test")
        self.assertEqual(len(overridden), 1)
        self.assertEqual(overridden[0]["calendar_id"], "explicit@example.test")


if __name__ == "__main__":
    unittest.main()
