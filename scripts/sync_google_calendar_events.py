#!/usr/bin/env python3
"""Sync generated public calendar events to the public Google Calendar."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
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


def load_calendar_metadata_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with CALENDAR_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (row.get("calendar_id") or "").strip():
                rows.append({key: (value or "").strip() for key, value in row.items()})
    if not rows:
        raise RuntimeError(f"No calendar_id found in {CALENDAR_CSV}")
    return rows


def load_calendar_metadata() -> dict[str, str]:
    return load_calendar_metadata_rows()[0]


def load_calendar_id() -> str:
    return load_calendar_metadata()["calendar_id"]


def load_events(path: Path = EVENTS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", [])
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, dict)]


def calendar_description(event: dict[str, Any]) -> str:
    return "\n".join(
        part
        for part in [
            str(event.get("details") or "").strip(),
            str(event.get("evidenceUrl") or "").strip(),
        ]
        if part
    )


def event_resource(event: dict[str, Any]) -> dict[str, Any]:
    timezone = str(event.get("timezone") or "Asia/Taipei").strip()
    body: dict[str, Any] = {
        "summary": event.get("eventName") or event.get("title") or "公開口琴活動",
        "location": event.get("location") or "",
        "description": calendar_description(event),
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
        body["start"] = {"dateTime": event.get("start"), "timeZone": timezone}
        body["end"] = {"dateTime": event.get("end"), "timeZone": timezone}
    if event.get("evidenceUrl"):
        body["attachments"] = []
    return body


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


def load_token_info(token_path: Path) -> dict[str, Any]:
    env_info = {
        "client_id": os.environ.get("HARMONICA_GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("HARMONICA_GOOGLE_CLIENT_SECRET", "").strip(),
        "refresh_token": os.environ.get("HARMONICA_GOOGLE_REFRESH_TOKEN", "").strip(),
        "token_uri": os.environ.get("HARMONICA_GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token").strip(),
    }
    if env_info["client_id"] and env_info["client_secret"] and env_info["refresh_token"]:
        return env_info
    return json.loads(token_path.read_text(encoding="utf-8"))


def refresh_access_token(token_info: dict[str, Any]) -> str:
    payload = urllib.parse.urlencode(
        {
            "client_id": token_info.get("client_id") or "",
            "client_secret": token_info.get("client_secret") or "",
            "refresh_token": token_info.get("refresh_token") or "",
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        token_info.get("token_uri") or "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Google OAuth refresh response did not include access_token.")
    return token


class CalendarRestRequest:
    def __init__(self, method: str, url: str, token: str, body: dict[str, Any] | None = None):
        self.method = method
        self.url = url
        self.token = token
        self.body = body

    def execute(self) -> dict[str, Any]:
        data = None
        headers = {"Authorization": f"Bearer {self.token}"}
        if self.body is not None:
            data = json.dumps(self.body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(self.url, data=data, headers=headers, method=self.method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Google Calendar API {self.method} failed: HTTP {exc.code} {detail}") from exc
        if not raw:
            return {}
        return json.loads(raw)


class CalendarRestEvents:
    def __init__(self, token: str):
        self.token = token

    @staticmethod
    def _base(calendar_id: str) -> str:
        return "https://www.googleapis.com/calendar/v3/calendars/" + urllib.parse.quote(calendar_id, safe="")

    @staticmethod
    def _query_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def list(self, *, calendarId: str, **params: Any) -> CalendarRestRequest:
        query = urllib.parse.urlencode({key: self._query_value(value) for key, value in params.items() if value is not None})
        return CalendarRestRequest("GET", f"{self._base(calendarId)}/events?{query}", self.token)

    def patch(self, *, calendarId: str, eventId: str, body: dict[str, Any]) -> CalendarRestRequest:
        url = f"{self._base(calendarId)}/events/{urllib.parse.quote(eventId, safe='')}"
        return CalendarRestRequest("PATCH", url, self.token, body)

    def insert(self, *, calendarId: str, body: dict[str, Any]) -> CalendarRestRequest:
        return CalendarRestRequest("POST", f"{self._base(calendarId)}/events", self.token, body)

    def delete(self, *, calendarId: str, eventId: str) -> CalendarRestRequest:
        url = f"{self._base(calendarId)}/events/{urllib.parse.quote(eventId, safe='')}"
        return CalendarRestRequest("DELETE", url, self.token)


class CalendarRestService:
    def __init__(self, token: str):
        self._events = CalendarRestEvents(token)
        self._calendars = CalendarRestCalendars(token)

    def events(self) -> CalendarRestEvents:
        return self._events

    def calendars(self) -> "CalendarRestCalendars":
        return self._calendars


class CalendarRestCalendars:
    def __init__(self, token: str):
        self.token = token

    def patch(self, *, calendarId: str, body: dict[str, Any]) -> CalendarRestRequest:
        url = "https://www.googleapis.com/calendar/v3/calendars/" + urllib.parse.quote(calendarId, safe="")
        return CalendarRestRequest("PATCH", url, self.token, body)


def sync_calendar_metadata(service, calendar_id: str, metadata: dict[str, str]) -> bool:
    body = {
        "summary": metadata.get("calendar_name") or "口琴公開活動",
        "description": metadata.get("purpose") or "",
        "timeZone": metadata.get("timezone") or "Asia/Taipei",
    }
    service.calendars().patch(calendarId=calendar_id, body=body).execute()
    return True


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


def metadata_events_path(metadata: dict[str, str]) -> Path:
    configured = metadata.get("events_path") or str(EVENTS_PATH.relative_to(PROJECT_ROOT))
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def sync_one_calendar(service, metadata: dict[str, str]) -> dict[str, Any]:
    calendar_id = metadata["calendar_id"]
    source_events = load_events(metadata_events_path(metadata))
    sync_calendar_metadata(service, calendar_id, metadata)
    existing = existing_managed_events(service, calendar_id)
    wanted_ids = {str(event.get("id") or "") for event in source_events if event.get("id")}
    result: dict[str, Any] = {
        "calendarKey": metadata.get("calendar_key") or "",
        "eventMode": metadata.get("event_mode") or "",
        "calendarId": calendar_id,
        "calendarName": metadata.get("calendar_name") or "",
        "eventsPath": str(metadata_events_path(metadata).relative_to(PROJECT_ROOT)),
        "metadataUpdated": True,
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "kept": len(wanted_ids),
        "status": "ok",
    }
    for event in source_events:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        body = event_resource(event)
        if event_id in existing:
            service.events().patch(
                calendarId=calendar_id,
                eventId=existing[event_id]["id"],
                body=body,
            ).execute()
            result["updated"] += 1
        else:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            result["created"] += 1

    for event_id, item in existing.items():
        if event_id not in wanted_ids:
            service.events().delete(calendarId=calendar_id, eventId=item["id"]).execute()
            result["deleted"] += 1
    return result


def selected_calendar_metadata(
    rows: list[dict[str, str]], *, calendar_key: str = "", calendar_id: str = ""
) -> list[dict[str, str]]:
    selected = list(rows)
    if calendar_key:
        selected = [row for row in selected if row.get("calendar_key") == calendar_key]
        if not selected:
            raise RuntimeError(f"Unknown calendar key: {calendar_key}")
    if calendar_id:
        selected = [dict(selected[0], calendar_id=calendar_id)]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", type=Path, default=Path(os.environ.get("HARMONICA_GOOGLE_TOKEN_JSON", DEFAULT_TOKEN_PATH)))
    parser.add_argument("--calendar-id", default="")
    parser.add_argument("--calendar-key", default="")
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    token_path = args.token.expanduser()
    status: dict[str, Any] = {
        "version": 2,
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

    calendar_metadata_rows = selected_calendar_metadata(
        load_calendar_metadata_rows(),
        calendar_key=args.calendar_key,
        calendar_id=args.calendar_id,
    )
    try:
        from googleapiclient.discovery import build
    except ModuleNotFoundError:
        token = refresh_access_token(load_token_info(token_path))
        service = CalendarRestService(token)
        status["client"] = "rest"
    else:
        creds = load_credentials(token_path)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        status["client"] = "google-api-python-client"
    results: list[dict[str, Any]] = []
    for metadata in calendar_metadata_rows:
        try:
            results.append(sync_one_calendar(service, metadata))
        except Exception as exc:
            results.append(
                {
                    "calendarKey": metadata.get("calendar_key") or "",
                    "eventMode": metadata.get("event_mode") or "",
                    "calendarId": metadata.get("calendar_id") or "",
                    "calendarName": metadata.get("calendar_name") or "",
                    "status": "error",
                    "error": str(exc),
                    "created": 0,
                    "updated": 0,
                    "deleted": 0,
                    "kept": 0,
                }
            )
    for field in ("created", "updated", "deleted", "kept"):
        status[field] = sum(int(result.get(field) or 0) for result in results)
    failures = [result for result in results if result.get("status") != "ok"]
    status["calendars"] = results
    status["status"] = "degraded" if failures else "ok"
    status["message"] = (
        f"Google Calendar sync completed for {len(results) - len(failures)}/{len(results)} calendars."
    )
    write_status(status)
    print(
        "Google Calendar sync completed: "
        f"calendars={len(results) - len(failures)}/{len(results)} "
        f"created={status['created']} updated={status['updated']} "
        f"deleted={status['deleted']} kept={status['kept']}"
    )
    return 1 if failures and args.required else 0


if __name__ == "__main__":
    raise SystemExit(main())
