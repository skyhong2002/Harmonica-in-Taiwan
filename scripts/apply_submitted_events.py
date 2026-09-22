#!/usr/bin/env python3
"""Merge verified form-submitted events into generated calendar outputs."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_public_calendar_events as calendar
from submission_intake import event_context, parse_event_time, NeedsReview


SUBMISSIONS = PROJECT_ROOT / "data" / "sources" / "harmonica-submitted-events.csv"
JSON_PATH = PROJECT_ROOT / "site" / "api" / "public-calendar-events.json"
JS_PATH = PROJECT_ROOT / "site" / "data" / "public-calendar-events.js"
OVERSEAS_JSON_PATH = PROJECT_ROOT / "site" / "api" / "overseas-calendar-events.json"
ONLINE_JSON_PATH = PROJECT_ROOT / "site" / "api" / "online-calendar-events.json"


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
    # Only records from the pre-global CSV schema inherit the historical Taiwan scope.
    metadata_fields = ("country", "timezone", "event_mode")
    metadata = dict(row)
    if not any(field in row for field in metadata_fields):
        metadata.update(country="TW", timezone="Asia/Taipei", event_mode="taiwan_physical")
    try:
        country, timezone, mode = event_context(metadata)
        all_day = truthy(row.get("all_day"))
        start_value = parse_event_time(start, all_day=all_day, timezone=timezone)
        end_value = parse_event_time(clean(row.get("end")) or start, all_day=all_day, timezone=timezone)
        if end_value < start_value:
            return None
        # CSV dates are inclusive. Calendar/ICS all-day ends are exclusive.
        if all_day:
            end_value += dt.timedelta(days=1)
        start, end = start_value.isoformat(), end_value.isoformat()
    except NeedsReview:
        return None
    city = clean(row.get("city"))
    location = venue if not city or city in venue else f"{city} {venue}"
    return {
        "id": event_id(row),
        "title": name,
        "eventName": name,
        "source": "Harmonica Observatory community submission",
        "platform": calendar.SUBMITTED_PLATFORM,
        "start": start,
        "end": end,
        "allDay": all_day,
        "calendarType": mode,
        "country": country,
        "timezone": timezone,
        "location": location,
        "venue": venue,
        "city": city,
        "details": clean(row.get("details")),
        "evidenceUrl": evidence_url,
        "confidence": 1.0,
        "calendarReview": {
            "include": True,
            "country": country,
            "eventMode": mode,
            "timezone": timezone,
            "eventName": name,
            "venue": venue,
            "city": city,
            "details": clean(row.get("details")),
            "reason": "verified public community submission",
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
    submitted = load_submitted_events(SUBMISSIONS)
    routes = (
        (calendar.TAIWAN_PHYSICAL, JSON_PATH, calendar.ICS_PATH, "Taiwan harmonica events"),
        (calendar.OVERSEAS_PHYSICAL, OVERSEAS_JSON_PATH, calendar.OVERSEAS_ICS_PATH, "International harmonica events"),
        (calendar.ONLINE, ONLINE_JSON_PATH, calendar.ONLINE_ICS_PATH, "Online harmonica events"),
    )
    counts = {}
    for mode, json_path, ics_path, title in routes:
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            payload = calendar.calendar_payload(
                [], mode=mode, generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                ics_path="/feeds/" + ics_path.name, criteria=title, overrides=0, llm={},
            )
        # Re-route historical submitted items after metadata is corrected, and
        # make a repeated merge reflect removed/moderated CSV rows as well.
        generated = [item for item in payload.get("events", []) if isinstance(item, dict)
                     and item.get("platform") != calendar.SUBMITTED_PLATFORM]
        selected = [item for item in submitted if item["calendarType"] == mode]
        events = calendar.deduplicate_events(merge_events(generated, selected))
        payload.update(events=events, count=len(events), calendarType=mode,
                       timezonePolicy="event-local", submittedEvents=sum(
                           item.get("platform") == calendar.SUBMITTED_PLATFORM for item in events))
        calendar.atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if mode == calendar.TAIWAN_PHYSICAL:
            calendar.atomic_write_text(
                JS_PATH, "window.publicCalendarEvents = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")
        calendar.write_ics(events, clean(payload.get("generatedAt")), path=ics_path, calendar_name=title)
        counts[mode] = len(events)
    print(f"Merged {len(submitted)} submitted events across calendars: {json.dumps(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
