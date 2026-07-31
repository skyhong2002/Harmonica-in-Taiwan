import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import sync_google_calendar_events as sync  # noqa: E402


class FakeRequest:
    def __init__(self, result=None):
        self.result = result or {}

    def execute(self):
        return self.result


class FakeEvents:
    def __init__(self, existing):
        self.existing = existing
        self.patched = []
        self.inserted = []
        self.deleted = []

    def list(self, **kwargs):
        return FakeRequest({"items": self.existing})

    def patch(self, **kwargs):
        self.patched.append(kwargs)
        return FakeRequest()

    def insert(self, **kwargs):
        self.inserted.append(kwargs)
        return FakeRequest()

    def delete(self, **kwargs):
        self.deleted.append(kwargs)
        return FakeRequest()


class FakeCalendars:
    def patch(self, **kwargs):
        return FakeRequest()


class FakeService:
    def __init__(self, existing):
        self.fake_events = FakeEvents(existing)

    def events(self):
        return self.fake_events

    def calendars(self):
        return FakeCalendars()


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

    def test_sync_keeps_one_copy_and_deletes_duplicate_managed_events(self):
        private = {
            sync.PRIVATE_MARKER_KEY: sync.PRIVATE_MARKER_VALUE,
            sync.PRIVATE_EVENT_ID_KEY: "same-event",
        }
        service = FakeService(
            [
                {"id": "older-copy", "created": "2026-07-01T00:00:00Z", "extendedProperties": {"private": private}},
                {"id": "newer-copy", "created": "2026-07-02T00:00:00Z", "extendedProperties": {"private": private}},
            ]
        )
        original_load_events = sync.load_events
        try:
            sync.load_events = lambda path: [
                {
                    "id": "same-event",
                    "eventName": "同一活動",
                    "start": "2026-08-08",
                    "end": "2026-08-09",
                    "allDay": True,
                }
            ]
            result = sync.sync_one_calendar(
                service,
                {
                    "calendar_id": "calendar@example.test",
                    "calendar_key": "taiwan",
                    "events_path": "site/api/public-calendar-events.json",
                },
            )
        finally:
            sync.load_events = original_load_events

        self.assertEqual(service.fake_events.patched[0]["eventId"], "older-copy")
        self.assertEqual([item["eventId"] for item in service.fake_events.deleted], ["newer-copy"])
        self.assertEqual(result["duplicatesDeleted"], 1)
        self.assertEqual(result["deleted"], 1)

    def test_sync_refuses_to_empty_a_calendar_when_source_has_no_events(self):
        private = {
            sync.PRIVATE_MARKER_KEY: sync.PRIVATE_MARKER_VALUE,
            sync.PRIVATE_EVENT_ID_KEY: "existing-event",
        }
        service = FakeService(
            [{"id": "live-copy", "created": "2026-07-01T00:00:00Z", "extendedProperties": {"private": private}}]
        )
        original_load_events = sync.load_events
        try:
            sync.load_events = lambda path: []
            result = sync.sync_one_calendar(
                service,
                {
                    "calendar_id": "calendar@example.test",
                    "calendar_key": "taiwan",
                    "events_path": "site/api/public-calendar-events.json",
                },
            )
        finally:
            sync.load_events = original_load_events

        self.assertEqual(result["status"], "error")
        self.assertEqual(service.fake_events.deleted, [])
        self.assertEqual(result["deleted"], 0)

    def test_allow_empty_lets_an_empty_source_clear_the_calendar(self):
        private = {
            sync.PRIVATE_MARKER_KEY: sync.PRIVATE_MARKER_VALUE,
            sync.PRIVATE_EVENT_ID_KEY: "existing-event",
        }
        service = FakeService(
            [{"id": "live-copy", "created": "2026-07-01T00:00:00Z", "extendedProperties": {"private": private}}]
        )
        original_load_events = sync.load_events
        try:
            sync.load_events = lambda path: []
            result = sync.sync_one_calendar(
                service,
                {
                    "calendar_id": "calendar@example.test",
                    "calendar_key": "taiwan",
                    "events_path": "site/api/public-calendar-events.json",
                },
                allow_empty=True,
            )
        finally:
            sync.load_events = original_load_events

        self.assertEqual(result["status"], "ok")
        self.assertEqual([item["eventId"] for item in service.fake_events.deleted], ["live-copy"])
        self.assertEqual(result["deleted"], 1)


class SyncLockTests(unittest.TestCase):
    def test_second_holder_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "nested" / "sync.lock"
            with sync.sync_lock(lock_path) as first:
                self.assertTrue(first)
                with sync.sync_lock(lock_path) as second:
                    self.assertFalse(second)

    def test_lock_is_released_when_the_body_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "sync.lock"
            with self.assertRaises(RuntimeError):
                with sync.sync_lock(lock_path) as acquired:
                    self.assertTrue(acquired)
                    raise RuntimeError("boom")
            with sync.sync_lock(lock_path) as reacquired:
                self.assertTrue(reacquired)


if __name__ == "__main__":
    unittest.main()
