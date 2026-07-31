#!/usr/bin/env python3
"""Merge verified form-submitted events into generated calendar outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_public_calendar_events as calendar


SUBMISSIONS = PROJECT_ROOT / "data" / "sources" / "harmonica-submitted-events.csv"
JSON_PATH = PROJECT_ROOT / "site" / "api" / "public-calendar-events.json"
JS_PATH = PROJECT_ROOT / "site" / "data" / "public-calendar-events.js"


def clean(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return clean(value).casefold() in {"1", "true", "yes", "y", "是"}


def event_id(row: dict[str, str]) -> str:
    raw = f"{clean(row.get('submission_id'))}|{clean(row.get('evidence_url'))}"
    return "submission-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def submitted_event(row: dict[str, str]) -> dict[str, Any] | None:
    evidence_url = clean(row.get("evidence_url"))
    name = clean(row.get("event_name"))
    start = clean(row.get("start"))
    venue = clean(row.get("venue"))
    if not all((evidence_url, name, start, venue)):
        return None
    city = clean(row.get("city"))
    location = venue if not city or city in venue else f"{city} {venue}"
    return {
        "id": event_id(row),
        "title": name,
        "eventName": name,
        "source": "臺灣口琴觀測站資料回報",
        "platform": "public-form",
        "start": start,
        "end": clean(row.get("end")) or start,
        "allDay": truthy(row.get("all_day")),
        "calendarType": calendar.TAIWAN_PHYSICAL,
        "timezone": calendar.TIMEZONE,
        "location": location,
        "venue": venue,
        "city": city,
        "details": clean(row.get("details")),
        "evidenceUrl": evidence_url,
        "confidence": 1.0,
        "calendarReview": {
            "include": True,
            "country": "臺灣",
            "eventMode": calendar.TAIWAN_PHYSICAL,
            "timezone": calendar.TIMEZONE,
            "eventName": name,
            "venue": venue,
            "city": city,
            "details": clean(row.get("details")),
            "reason": "verified public Google Form submission",
            "confidence": 1.0,
        },
        "postedAt": clean(row.get("verified_at")),
        "images": [],
        "image_url": "",
    }


def load_submitted_events(path: Path = SUBMISSIONS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [event for row in csv.DictReader(handle) if (event := submitted_event(row))]


def event_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        clean(event.get("evidenceUrl")),
        clean(event.get("eventName") or event.get("title")).casefold(),
        clean(event.get("start")),
    )


def merge_events(
    generated: list[dict[str, Any]], submitted: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = list(generated)
    existing_urls = {clean(event.get("evidenceUrl")) for event in generated}
    existing_keys = {event_key(event) for event in generated}
    for event in submitted:
        if clean(event.get("evidenceUrl")) in existing_urls or event_key(event) in existing_keys:
            continue
        merged.append(event)
        existing_urls.add(clean(event.get("evidenceUrl")))
        existing_keys.add(event_key(event))
    return sorted(merged, key=lambda item: (clean(item.get("start")), clean(item.get("title"))))


def main() -> int:
    if not JSON_PATH.exists():
        raise SystemExit(f"Generated calendar JSON not found: {JSON_PATH}")
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    generated = [item for item in payload.get("events", []) if isinstance(item, dict)]
    submitted = load_submitted_events()
    events = calendar.deduplicate_events(merge_events(generated, submitted))
    payload["events"] = events
    payload["count"] = len(events)
    payload["submittedEvents"] = len([item for item in events if item.get("platform") == "public-form"])
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JS_PATH.parent.mkdir(parents=True, exist_ok=True)
    JS_PATH.write_text(
        "window.publicCalendarEvents = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    calendar.write_ics(events, clean(payload.get("generatedAt")))
    print(f"Merged {len(submitted)} submitted events; {len(events)} total public calendar events.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
