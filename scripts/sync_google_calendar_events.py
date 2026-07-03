#!/usr/bin/env python3
"""Sync generated public calendar events to the public Google Calendar."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = PROJECT_ROOT / "site" / "api" / "public-calendar-events.json"
CALENDAR_CSV = PROJECT_ROOT / "data" / "sources" / "harmonica-public-calendars.csv"
STATUS_PATH = PROJECT_ROOT / "site" / "api" / "public-calendar-sync.json"
DEFAULT_TOKEN_PATH = Path.home() / ".hermes" / "profiles" / "bamboo" / "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
PRIVATE_MARKER_KEY = "harmonicaObserve"
PRIVATE_MARKER_VALUE = "public-calendar"
PRIVATE_EVENT_ID_KEY = "harmonicaObserveEventId"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_calendar_id() -> str:
    with CALENDAR_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            calendar_id = (row.get("calendar_id") or "").strip()
            if calendar_id:
                return calendar_id
    raise RuntimeError(f"No calendar_id found in {CALENDAR_CSV}")


def load_events() -> list[dict[str, Any]]:
    payload = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    events = payload.get("events", [])
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, dict)]


def event_resource(event: dict[str, Any]) -> dict[str, Any]:
    description_parts = [
        f"活動名稱：{event.get('eventName') or event.get('title')}" if event.get("eventName") or event.get("title") else "",
        f"時間：{event_time_label(event)}",
        f"地點：{event.get('location')}" if event.get("location") else "",
        f"相關資訊：{event.get('details')}" if event.get("details") else "",
        f"來源：{event.get('evidenceUrl')}" if event.get("evidenceUrl") else "",
    ]
    body: dict[str, Any] = {
        "summary": event.get("eventName") or event.get("title") or "公開口琴活動",
        "location": event.get("location") or "",
        "description": "\n".join(part for part in description_parts if part),
        "source": {"title": "臺灣口琴觀測站", "url": event.get("evidenceUrl") or "https://harmonica.observe.tw/"},
        "extendedProperties": {
            "private": {
                PRIVATE_MARKER_KEY: PRIVATE_MARKER_VALUE,
                PRIVATE_EVENT_ID_KEY: str(event.get("id") or ""),
            }
        },
    }
    if event.get("allDay"):
        body["start"] = {"date": str(event.get("start"))[:10]}
        body["end"] = {"date": str(event.get("end"))[:10]}
    else:
        body["start"] = {"dateTime": event.get("start"), "timeZone": "Asia/Taipei"}
        body["end"] = {"dateTime": event.get("end"), "timeZone": "Asia/Taipei"}
    if event.get("evidenceUrl"):
        body["attachments"] = []
    return body


def event_time_label(event: dict[str, Any]) -> str:
    start = str(event.get("start") or "")
    end = str(event.get("end") or "")
    if not start:
        return ""
    if event.get("allDay"):
        if not end or end[:10] == start[:10]:
            return start[:10]
        try:
            inclusive_end = dt.date.fromisoformat(end[:10]) - dt.timedelta(days=1)
        except ValueError:
            return f"{start[:10]} - {end[:10]}"
        return start[:10] if inclusive_end.isoformat() == start[:10] else f"{start[:10]} - {inclusive_end.isoformat()}"
    try:
        parsed = dt.datetime.fromisoformat(start)
    except ValueError:
        return start
    return parsed.astimezone(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def load_credentials(token_path: Path):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    env_info = {
        "client_id": os.environ.get("HARMONICA_GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("HARMONICA_GOOGLE_CLIENT_SECRET", "").strip(),
        "refresh_token": os.environ.get("HARMONICA_GOOGLE_REFRESH_TOKEN", "").strip(),
        "token_uri": os.environ.get("HARMONICA_GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token").strip(),
        "scopes": SCOPES,
    }
    if env_info["client_id"] and env_info["client_secret"] and env_info["refresh_token"]:
        info = env_info
    else:
        info = json.loads(token_path.read_text(encoding="utf-8"))
    creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json() + "\n", encoding="utf-8")
    return creds


def env_credentials_available() -> bool:
    return all(
        os.environ.get(name, "").strip()
        for name in [
            "HARMONICA_GOOGLE_CLIENT_ID",
            "HARMONICA_GOOGLE_CLIENT_SECRET",
            "HARMONICA_GOOGLE_REFRESH_TOKEN",
        ]
    )


def existing_managed_events(service, calendar_id: str) -> dict[str, dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc)
    time_min = (now - dt.timedelta(days=7)).isoformat().replace("+00:00", "Z")
    page_token = None
    found: dict[str, dict[str, Any]] = {}
    while True:
        response = service.events().list(
            calendarId=calendar_id,
            privateExtendedProperty=f"{PRIVATE_MARKER_KEY}={PRIVATE_MARKER_VALUE}",
            singleEvents=True,
            showDeleted=False,
            timeMin=time_min,
            maxResults=2500,
            pageToken=page_token,
        ).execute()
        for item in response.get("items", []):
            private = ((item.get("extendedProperties") or {}).get("private") or {})
            event_id = private.get(PRIVATE_EVENT_ID_KEY)
            if event_id:
                found[event_id] = item
        page_token = response.get("nextPageToken")
        if not page_token:
            return found


def write_status(payload: dict[str, Any]) -> None:
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", type=Path, default=Path(os.environ.get("HARMONICA_GOOGLE_TOKEN_JSON", DEFAULT_TOKEN_PATH)))
    parser.add_argument("--calendar-id", default=os.environ.get("HARMONICA_PUBLIC_CALENDAR_ID", ""))
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    token_path = args.token.expanduser()
    status: dict[str, Any] = {
        "version": 1,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "skipped",
        "calendarId": args.calendar_id or "",
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "kept": 0,
    }
    if not token_path.exists() and not env_credentials_available():
        status["message"] = f"Google token not found: {token_path}"
        write_status(status)
        if args.required:
            print(status["message"], file=sys.stderr)
            return 1
        print(status["message"])
        return 0

    try:
        from googleapiclient.discovery import build
    except ModuleNotFoundError as exc:
        status["message"] = "google-api-python-client is not installed in this Python environment."
        write_status(status)
        if args.required:
            print(status["message"], file=sys.stderr)
            return 1
        print(status["message"])
        return 0

    calendar_id = args.calendar_id or load_calendar_id()
    status["calendarId"] = calendar_id
    creds = load_credentials(token_path)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    source_events = load_events()
    existing = existing_managed_events(service, calendar_id)
    wanted_ids = {str(event.get("id") or "") for event in source_events if event.get("id")}

    for event in source_events:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        body = event_resource(event)
        if event_id in existing:
            service.events().patch(calendarId=calendar_id, eventId=existing[event_id]["id"], body=body).execute()
            status["updated"] += 1
        else:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            status["created"] += 1

    for event_id, item in existing.items():
        if event_id not in wanted_ids:
            service.events().delete(calendarId=calendar_id, eventId=item["id"]).execute()
            status["deleted"] += 1

    status["kept"] = len(wanted_ids)
    status["status"] = "ok"
    status["message"] = "Google Calendar sync completed."
    write_status(status)
    print(
        "Google Calendar sync completed: "
        f"created={status['created']} updated={status['updated']} deleted={status['deleted']} kept={status['kept']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
