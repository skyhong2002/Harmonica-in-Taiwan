#!/usr/bin/env python3
"""Build structured public calendar event candidates from public feed posts."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
DATA_DIR = SITE_ROOT / "data"
FEEDS_DIR = SITE_ROOT / "feeds"
SOURCE_PATH = API_DIR / "events.json"
JSON_PATH = API_DIR / "public-calendar-events.json"
JS_PATH = DATA_DIR / "public-calendar-events.js"
ICS_PATH = FEEDS_DIR / "public-calendar.ics"
TIMEZONE = "Asia/Taipei"
TAIWAN_TZ = dt.timezone(dt.timedelta(hours=8))

HARMONICA_TERMS = [
    "口琴",
    "harmonica",
    "ハーモニカ",
    "クロマチック",
    "複音",
    "半音階",
]

EVENT_TERMS = [
    "演出",
    "音樂會",
    "音乐会",
    "公演",
    "成發",
    "成果展",
    "講座",
    "工作坊",
    "音樂節",
    "音楽祭",
    "concert",
    "recital",
    "live",
    "festival",
    "コンサート",
    "ライブ",
    "開演",
    "開場",
    "場次",
]

DATE_RANGE_RE = re.compile(
    r"(?P<left>(?:\d{2,4}[./-])?\d{1,2}\s*(?:[./-]|月)\s*\d{1,2}\s*(?:日)?)"
    r"\s*(?:→|~|〜|–|-|至|到)\s*"
    r"(?P<right>(?:\d{2,4}[./-])?\d{1,2}\s*(?:[./-]|月)\s*\d{1,2}\s*(?:日)?)"
)
FULL_DATE_RE = re.compile(r"(?P<year>\d{2,4})\s*(?:年|[./-])\s*(?P<month>\d{1,2})\s*(?:月|[./-])\s*(?P<day>\d{1,2})\s*(?:日)?")
MONTH_DAY_RE = re.compile(r"(?<!\d)(?P<month>\d{1,2})\s*(?:月|[./])\s*(?P<day>\d{1,2})\s*(?:日)?(?!\d)")
COMPACT_RANGE_RE = re.compile(r"(?<!\d)(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})\s*[-~〜]\s*(?P<end_month>\d{2})(?P<end_day>\d{2})(?!\d)")
TIME_RE = re.compile(r"(?<!\d)(?P<hour>[01]?\d|2[0-3])[:：](?P<minute>[0-5]\d)(?!\d)")
LOCATION_RE = re.compile(r"(?:地點|地点|場地|會場|会場|場所|上課地點|活動地點|📍)\s*[｜|:：]?\s*(?P<place>[^\n。；;，,]{2,48})")


def parse_datetime(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", text):
        text = text.replace(" ", "T") + ":00+08:00"
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = dt.datetime.strptime(text, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TAIWAN_TZ)
    return parsed.astimezone(TAIWAN_TZ)


def normalized_year(year: int, reference_year: int) -> int:
    if year < 100:
        return 2000 + year
    if 100 <= year < 200:
        return year + 1911
    if year < 1000:
        return reference_year
    return year


def safe_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def infer_month_day(month: int, day: int, posted_at: dt.datetime | None) -> dt.date | None:
    reference = posted_at.date() if posted_at else dt.datetime.now(TAIWAN_TZ).date()
    candidate = safe_date(reference.year, month, day)
    if candidate is None:
        return None
    if candidate < reference - dt.timedelta(days=45):
        next_year = safe_date(reference.year + 1, month, day)
        return next_year or candidate
    return candidate


def parse_loose_date(text: str, posted_at: dt.datetime | None) -> dt.date | None:
    cleaned = text.strip().replace(" ", "")
    full = FULL_DATE_RE.search(cleaned)
    if full:
        year = normalized_year(int(full.group("year")), (posted_at or dt.datetime.now(TAIWAN_TZ)).year)
        return safe_date(year, int(full.group("month")), int(full.group("day")))
    month_day = MONTH_DAY_RE.search(cleaned)
    if month_day:
        return infer_month_day(int(month_day.group("month")), int(month_day.group("day")), posted_at)
    return None


def text_has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def nearby_context(text: str, start: int, end: int, radius: int = 60) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)]


def extract_time(text: str) -> str:
    match = TIME_RE.search(text)
    if not match:
        return ""
    return f"{int(match.group('hour')):02d}:{match.group('minute')}"


def extract_location(text: str) -> str:
    match = LOCATION_RE.search(text)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group("place")).strip(" ｜|:：")


def event_title(item: dict[str, Any]) -> str:
    source = str(item.get("source") or "").strip()
    text = str(item.get("text") or item.get("title") or "").strip()
    quoted = re.search(r"《([^》]{2,36})》", text)
    if quoted:
        core = f"《{quoted.group(1)}》"
    else:
        line = next((part.strip() for part in re.split(r"[\n。]", text) if part.strip()), "")
        core = re.sub(r"\s+", " ", line)[:42].strip()
    if source and core and source not in core:
        return f"{source}｜{core}"
    return core or source or "公開口琴活動"


def normalized_event_identity(title: str, source: Any, start: dt.date) -> tuple[str, str, str]:
    compact_title = re.sub(r"\s+", "", title)
    compact_title = re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", "", compact_title, flags=re.UNICODE)
    compact_source = re.sub(r"\s+", "", str(source or ""))
    return (compact_source.lower(), compact_title[:48].lower(), start.isoformat())


def date_candidates(text: str, posted_at: dt.datetime | None) -> list[tuple[dt.date, dt.date, str]]:
    candidates: list[tuple[dt.date, dt.date, str]] = []
    seen: set[tuple[dt.date, dt.date]] = set()

    for match in COMPACT_RANGE_RE.finditer(text):
        year = normalized_year(int(match.group("year")), (posted_at or dt.datetime.now(TAIWAN_TZ)).year)
        start = safe_date(year, int(match.group("month")), int(match.group("day")))
        end = safe_date(year, int(match.group("end_month")), int(match.group("end_day")))
        if start and end and end >= start and (end - start).days <= 7:
            key = (start, end)
            if key not in seen:
                seen.add(key)
                candidates.append((start, end, nearby_context(text, match.start(), match.end())))

    for match in DATE_RANGE_RE.finditer(text):
        start = parse_loose_date(match.group("left"), posted_at)
        end = parse_loose_date(match.group("right"), posted_at)
        if start and end and end >= start and (end - start).days <= 14:
            key = (start, end)
            if key not in seen:
                seen.add(key)
                candidates.append((start, end, nearby_context(text, match.start(), match.end())))

    occupied = [range(match.start(), match.end()) for match in DATE_RANGE_RE.finditer(text)]
    for regex in (FULL_DATE_RE, MONTH_DAY_RE):
        for match in regex.finditer(text):
            if any(match.start() in span or match.end() in span for span in occupied):
                continue
            date = parse_loose_date(match.group(0), posted_at)
            if not date:
                continue
            context = nearby_context(text, match.start(), match.end())
            if not text_has_any(context, EVENT_TERMS):
                continue
            key = (date, date)
            if key not in seen:
                seen.add(key)
                candidates.append((date, date, context))

    return candidates


def item_key(item: dict[str, Any], start: dt.date) -> str:
    source = str(item.get("source_id") or item.get("source") or "")
    link = str(item.get("link") or "")
    raw = f"{source}|{link}|{start.isoformat()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def extract_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen_links_dates: set[tuple[str, str]] = set()
    seen_event_identity: set[tuple[str, str, str]] = set()
    now_date = dt.datetime.now(TAIWAN_TZ).date()
    min_date = now_date - dt.timedelta(days=2)
    max_date = now_date + dt.timedelta(days=420)

    for item in items:
        text = "\n".join(str(item.get(key) or "") for key in ("source", "title", "text"))
        if not text_has_any(text, HARMONICA_TERMS):
            continue
        if not text_has_any(text, EVENT_TERMS):
            continue
        posted_at = parse_datetime(item.get("posted_at_local")) or parse_datetime(item.get("posted_at"))
        for start_date, end_date, context in date_candidates(text, posted_at):
            if start_date < min_date or start_date > max_date:
                continue
            link = str(item.get("link") or "")
            dedupe_key = (link, start_date.isoformat())
            if dedupe_key in seen_links_dates:
                continue
            seen_links_dates.add(dedupe_key)
            title = event_title(item)
            identity = normalized_event_identity(title, item.get("source"), start_date)
            if identity in seen_event_identity:
                continue
            seen_event_identity.add(identity)
            time_text = extract_time(context) or extract_time(text)
            start = f"{start_date.isoformat()}T{time_text}:00+08:00" if time_text else start_date.isoformat()
            end = end_date.isoformat()
            if time_text:
                end_dt = dt.datetime.combine(start_date, dt.time.fromisoformat(time_text), TAIWAN_TZ) + dt.timedelta(hours=2)
                if end_date > start_date:
                    end_dt = dt.datetime.combine(end_date, dt.time(23, 59), TAIWAN_TZ)
                end = end_dt.isoformat()
            elif end_date >= start_date:
                end = (end_date + dt.timedelta(days=1)).isoformat()
            events.append(
                {
                    "id": item_key(item, start_date),
                    "title": title,
                    "source": item.get("source") or "",
                    "platform": item.get("platform") or "",
                    "start": start,
                    "end": end,
                    "allDay": not bool(time_text),
                    "location": extract_location(text),
                    "evidenceUrl": link,
                    "postedAt": item.get("posted_at_local") or item.get("posted_at") or "",
                    "confidence": "inferred",
                    "note": "由公開貼文文字自動抽取，請以來源連結為準。",
                }
            )

    events.sort(key=lambda row: (row["start"], row["source"], row["title"]))
    return events


def escape_ics(value: Any) -> str:
    text = str(value or "")
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_ics_line(line: str) -> str:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts: list[str] = []
    current = ""
    current_len = 0
    for char in line:
        char_len = len(char.encode("utf-8"))
        if current and current_len + char_len > 75:
            parts.append(current)
            current = " " + char
            current_len = 1 + char_len
        else:
            current += char
            current_len += char_len
    if current:
        parts.append(current)
    return "\r\n".join(parts)


def ics_datetime(value: str, *, all_day: bool, is_end: bool = False) -> str:
    if all_day:
        return value.replace("-", "")
    parsed = dt.datetime.fromisoformat(value)
    return parsed.astimezone(TAIWAN_TZ).strftime("%Y%m%dT%H%M%S")


def write_ics(events: list[dict[str, Any]], generated_at: str) -> None:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Harmonica Observe Taiwan//Public Calendar//ZH-TW",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics('臺灣口琴公開演出')}",
        f"X-WR-TIMEZONE:{TIMEZONE}",
    ]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for event in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{event['id']}@harmonica.observe.tw")
        lines.append(f"DTSTAMP:{stamp}")
        if event["allDay"]:
            lines.append(f"DTSTART;VALUE=DATE:{ics_datetime(event['start'], all_day=True)}")
            lines.append(f"DTEND;VALUE=DATE:{ics_datetime(event['end'], all_day=True)}")
        else:
            lines.append(f"DTSTART;TZID={TIMEZONE}:{ics_datetime(event['start'], all_day=False)}")
            lines.append(f"DTEND;TZID={TIMEZONE}:{ics_datetime(event['end'], all_day=False)}")
        lines.append(f"SUMMARY:{escape_ics(event['title'])}")
        if event.get("location"):
            lines.append(f"LOCATION:{escape_ics(event['location'])}")
        description = f"{event.get('note', '')}\\n來源：{event.get('evidenceUrl', '')}".strip()
        lines.append(f"DESCRIPTION:{escape_ics(description)}")
        if event.get("evidenceUrl"):
            lines.append(f"URL:{escape_ics(event['evidenceUrl'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    ICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ICS_PATH.write_text("\r\n".join(fold_ics_line(line) for line in lines) + "\r\n", encoding="utf-8")


def main() -> int:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    generated_at = dt.datetime.now(TAIWAN_TZ).isoformat(timespec="seconds")
    events = extract_events([item for item in items if isinstance(item, dict)])
    output = {
        "version": 1,
        "generatedAt": generated_at,
        "timezone": TIMEZONE,
        "count": len(events),
        "source": "/api/events.json",
        "ics": "/feeds/public-calendar.ics",
        "rightsNote": "只整理公開貼文中的活動 metadata、日期與來源連結；請以原始公開貼文或售票/報名頁為準。",
        "events": events,
    }
    JSON_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JS_PATH.write_text(
        "window.publicCalendarEvents = "
        + json.dumps(output, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    write_ics(events, generated_at)
    print(f"Built {len(events)} public calendar events.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
