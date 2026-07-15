import sys
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


if __name__ == "__main__":
    unittest.main()
