#!/usr/bin/env python3
"""Build structured public calendar event candidates from public feed posts."""

from __future__ import annotations

import datetime as dt
import argparse
import csv
import hashlib
import json
import re
import os
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import social_feed_watchdog as watchdog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
DATA_DIR = SITE_ROOT / "data"
FEEDS_DIR = SITE_ROOT / "feeds"
SOURCE_PATH = API_DIR / "events.json"
OVERRIDES_PATH = PROJECT_ROOT / "data" / "sources" / "harmonica-public-calendar-overrides.csv"
JSON_PATH = API_DIR / "public-calendar-events.json"
JS_PATH = DATA_DIR / "public-calendar-events.js"
ICS_PATH = FEEDS_DIR / "public-calendar.ics"
OVERSEAS_JSON_PATH = API_DIR / "overseas-calendar-events.json"
ONLINE_JSON_PATH = API_DIR / "online-calendar-events.json"
OVERSEAS_ICS_PATH = FEEDS_DIR / "overseas-calendar.ics"
ONLINE_ICS_PATH = FEEDS_DIR / "online-calendar.ics"
TIMEZONE = "Asia/Taipei"
TAIWAN_TZ = dt.timezone(dt.timedelta(hours=8))
DEFAULT_LLM_CACHE = PROJECT_ROOT / "state" / "public_calendar_llm_events.json"
CALENDAR_REVIEW_POLICY_VERSION = 6
TAIWAN_PHYSICAL = "taiwan_physical"
OVERSEAS_PHYSICAL = "overseas_physical"
ONLINE = "online"
EVENT_MODES = {TAIWAN_PHYSICAL, OVERSEAS_PHYSICAL, ONLINE}
SUBMITTED_PLATFORM = "public-form"
COUNTRY_TIMEZONES = {
    "台灣": "Asia/Taipei",
    "臺灣": "Asia/Taipei",
    "Taiwan": "Asia/Taipei",
    "日本": "Asia/Tokyo",
    "Japan": "Asia/Tokyo",
    "香港": "Asia/Hong_Kong",
    "Hong Kong": "Asia/Hong_Kong",
    "新加坡": "Asia/Singapore",
    "Singapore": "Asia/Singapore",
    "馬來西亞": "Asia/Kuala_Lumpur",
    "Malaysia": "Asia/Kuala_Lumpur",
    "韓國": "Asia/Seoul",
    "南韓": "Asia/Seoul",
    "South Korea": "Asia/Seoul",
    "中國": "Asia/Shanghai",
    "China": "Asia/Shanghai",
}
PLACE_COUNTRIES = {
    "日本": "日本",
    "東京": "日本",
    "東京都": "日本",
    "大阪": "日本",
    "和歌山": "日本",
    "名古屋": "日本",
    "Japan": "日本",
    "Tokyo": "日本",
    "Osaka": "日本",
    "香港": "香港",
    "Hong Kong": "香港",
    "新加坡": "新加坡",
    "Singapore": "新加坡",
    "馬來西亞": "馬來西亞",
    "Malaysia": "馬來西亞",
    "韓國": "韓國",
    "South Korea": "韓國",
    "中國": "中國",
    "中国": "中國",
    "江陰": "中國",
    "江阴": "中國",
    "China": "中國",
}

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
    "活動時間",
    "日時",
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
TIME_WITH_UNIT_RE = re.compile(r"(?P<prefix>上午|早上|中午|下午|晚上|夜|午前|午後)?\s*(?P<hour>[01]?\d|2[0-3])\s*(?:時|点|點)(?:\s*(?P<minute>[0-5]\d)\s*分?)?")
CHINESE_TIME_RE = re.compile(r"(?P<prefix>上午|早上|中午|下午|晚上|夜)?\s*(?P<hour>[一二兩三四五六七八九十]{1,3})\s*(?:點|時)(?P<half>半)?")
LOCATION_RE = re.compile(r"(?:地點|地点|場地|會場|会場|場所|上課地點|活動地點|舉辦地點)\s*[｜|:：]?\s*(?P<place>[^\n。；;，,]{2,48})")
PIN_LOCATION_RE = re.compile(
    r"📍\s*(?!時間|时间|日期|日時|日时|\d{1,4}\s*[./-])"
    r"(?P<place>[^\n。；;，,]{2,48})"
)
NARRATIVE_LOCATION_RE = re.compile(
    r"(?:在|於(?!\s*(?:\d{1,4}\s*(?:年|[./-])|\d{1,2}\s*月)))\s*"
    r"(?P<place>[^\n。；;，,]{2,80}?)"
    r"(?=(?:熱鬧)?(?:登場|舉行|舉辦|開演|展開))"
)
TAIWAN_PLACE_RE = re.compile(
    r"台灣|臺灣|台北|臺北|新北|基隆|桃園|新竹|苗栗|台中|臺中|彰化|南投|雲林|嘉義|台南|臺南|高雄|屏東|宜蘭|花蓮|台東|臺東|澎湖|金門|馬祖|陽明交通大學|陽明交大|衛武營|武陵|臺北生技園區|台北生技園區|大墩文化中心"
)
OVERSEAS_PLACE_RE = re.compile(
    r"日本|東京|東京都|大阪|和歌山|名古屋|香港|新加坡|Singapore|Japan|Tokyo|Osaka|Hong Kong|Malaysia|馬來西亞|恵比寿|BLUE NOTE PLACE|アーク栄"
)
ONLINE_EVENT_RE = re.compile(r"線上|直播|live\s*stream|livestream|streaming|online|YouTube\s*Live|IG\s*Live|Facebook\s*Live", re.IGNORECASE)
NON_LIVE_ONLINE_RE = re.compile(r"回顧|重播|隨選|archive|archived|アーカイブ|配信中|影片發布|影片回放", re.IGNORECASE)
ONLINE_LOGISTICS_RE = re.compile(
    r"(?:線上|網路|online\s+)(?:報名|購票|登記|申請|registration|tickets?)",
    re.IGNORECASE,
)
GENERIC_ONLINE_VENUE_RE = re.compile(r"^(?:線上|線上直播|網路直播|online|livestream)$", re.IGNORECASE)
CANCELLED_EVENT_RE = re.compile(r"停辦|取消(?:活動|演出|場次|音樂會|音乐会|公演|講座|工作坊)?|中止|開催中止", re.IGNORECASE)


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


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def load_overrides(path: Path = OVERRIDES_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    overrides: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            evidence_url = (row.get("evidence_url") or "").strip()
            if not evidence_url:
                continue
            start = (row.get("start") or "").strip()
            end = (row.get("end") or "").strip()
            event_name = (row.get("event_name") or "").strip()
            venue = (row.get("venue") or "").strip()
            city = (row.get("city") or "").strip()
            country = (row.get("country") or "臺灣").strip()
            mode = (row.get("event_mode") or "").strip() or classify_event_mode(
                country, f"{event_name} {venue} {city}"
            )
            timezone = valid_timezone(row.get("timezone")) or infer_timezone(country)
            if not start or not event_name or not venue:
                continue
            overrides[evidence_url] = {
                "eventName": event_name,
                "title": event_name,
                "start": start,
                "end": end or start,
                "allDay": truthy(row.get("all_day")),
                "venue": venue,
                "city": city,
                "location": venue if not city or city in venue else f"{city} {venue}",
                "details": (row.get("details") or "").strip(),
                "calendarType": mode,
                "timezone": timezone,
                "evidenceUrl": evidence_url,
                "confidence": 1.0,
                "calendarReview": {
                    "include": True,
                    "country": country,
                    "eventMode": mode,
                    "timezone": timezone,
                    "candidateDateMatches": True,
                    "eventName": event_name,
                    "venue": venue,
                    "city": city,
                    "details": (row.get("details") or "").strip(),
                    "reason": "manual override from public calendar overrides CSV",
                    "confidence": 1.0,
                },
            }
    return overrides


def text_has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def is_online_event_text(text: str) -> bool:
    event_text = ONLINE_LOGISTICS_RE.sub("", text)
    return bool(ONLINE_EVENT_RE.search(event_text)) and not bool(NON_LIVE_ONLINE_RE.search(event_text))


def valid_timezone(value: Any) -> str:
    timezone = str(value or "").strip()
    if not timezone:
        return ""
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return ""
    return timezone


def infer_timezone(country: str) -> str:
    return COUNTRY_TIMEZONES.get(str(country or "").strip(), "")


def infer_country(text: str) -> str:
    for marker, country in PLACE_COUNTRIES.items():
        if marker.casefold() in text.casefold():
            return country
    return ""


def classify_event_mode(country: str, text: str, requested_mode: str = "") -> str:
    country = str(country or "").strip()
    requested_mode = str(requested_mode or "").strip()
    has_taiwan_place = bool(TAIWAN_PLACE_RE.search(text))
    has_overseas_place = bool(OVERSEAS_PLACE_RE.search(text))
    is_taiwan = country in {"台灣", "臺灣", "Taiwan"} or has_taiwan_place
    is_online = country == "線上" or is_online_event_text(text)
    is_overseas = bool(country and country not in {"台灣", "臺灣", "Taiwan", "線上"}) or bool(
        has_overseas_place
    )
    if requested_mode == ONLINE and is_online:
        return ONLINE
    if country == "線上" and is_online:
        return ONLINE
    if requested_mode == OVERSEAS_PHYSICAL and is_overseas and not is_taiwan:
        return OVERSEAS_PHYSICAL
    if requested_mode == TAIWAN_PHYSICAL and is_taiwan and not is_overseas:
        return TAIWAN_PHYSICAL
    if has_overseas_place and not has_taiwan_place:
        return OVERSEAS_PHYSICAL
    if country and country not in {"台灣", "臺灣", "Taiwan", "線上"}:
        return OVERSEAS_PHYSICAL
    if country in {"台灣", "臺灣", "Taiwan"}:
        return TAIWAN_PHYSICAL
    if is_overseas:
        return OVERSEAS_PHYSICAL
    if is_taiwan:
        return TAIWAN_PHYSICAL
    if is_online:
        return ONLINE
    return ""


def review_event_modes(country: str, text: str) -> tuple[bool, bool]:
    mode = classify_event_mode(country, text)
    return mode == ONLINE, mode == TAIWAN_PHYSICAL


def nearby_context(text: str, start: int, end: int, radius: int = 60) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)]


def date_match_is_truncated(text: str, end: int) -> bool:
    return bool(re.match(r"\s*(?:…|\\.\\.\\.)", text[end:end + 6]))


def extract_time(text: str) -> str:
    match = TIME_RE.search(text)
    if match:
        return f"{int(match.group('hour')):02d}:{match.group('minute')}"
    match = TIME_WITH_UNIT_RE.search(text)
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        prefix = match.group("prefix") or ""
        if prefix in {"下午", "晚上", "夜", "午後"} and hour < 12:
            hour += 12
        if prefix == "中午" and hour < 11:
            hour += 12
        return f"{hour:02d}:{minute:02d}"
    match = CHINESE_TIME_RE.search(text)
    if not match:
        return ""
    numerals = {"一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    raw_hour = match.group("hour")
    if raw_hour == "十":
        hour = 10
    elif raw_hour.startswith("十"):
        hour = 10 + numerals.get(raw_hour[-1], 0)
    elif raw_hour.endswith("十"):
        hour = numerals.get(raw_hour[0], 0) * 10
    elif "十" in raw_hour:
        left, right = raw_hour.split("十", 1)
        hour = numerals.get(left, 0) * 10 + numerals.get(right, 0)
    else:
        hour = numerals.get(raw_hour, 0)
    if hour <= 0 or hour > 23:
        return ""
    prefix = match.group("prefix") or ""
    if prefix in {"下午", "晚上", "夜"} and hour < 12:
        hour += 12
    if prefix == "中午" and hour < 11:
        hour += 12
    minute = 30 if match.group("half") else 0
    return f"{hour:02d}:{minute:02d}"


def clean_location(value: str) -> str:
    return re.sub(
        r"^(?:地點|地点|場地|會場|会場|場所|上課地點|活動地點|📍)\s*[｜|:：]?\s*",
        "",
        re.sub(r"\s+", " ", value),
    ).strip(" ｜|:：")


def extract_location(text: str) -> str:
    match = LOCATION_RE.search(text) or PIN_LOCATION_RE.search(text) or NARRATIVE_LOCATION_RE.search(text)
    if not match:
        return ""
    return clean_location(match.group("place"))


def event_title(item: dict[str, Any], context: str = "") -> str:
    source = str(item.get("source") or "").strip()
    text = str(item.get("text") or item.get("title") or "").strip()
    context_lines = [
        re.sub(r"^[^\w\u3040-\u30ff\u3400-\u9fff]+", "", part).strip()
        for part in context.splitlines()
        if part.strip()
    ]
    info_lines = [
        re.sub(r"(?:資訊|资讯|信息|案内)\s*$", "", line).rstrip("：: |｜")
        for line in context_lines
        if text_has_any(line, EVENT_TERMS)
        and re.search(r"(?:資訊|资讯|信息|案内)\s*$", line)
    ]
    if info_lines:
        core = max(info_lines, key=len)
    else:
        quoted = re.search(r"《([^》]{2,36})》", context or text)
        if quoted:
            core = f"《{quoted.group(1)}》"
        else:
            line = next((part.strip() for part in re.split(r"[\n。]", text) if part.strip()), "")
            core = re.sub(r"\s+", " ", line)[:42].strip()
    source_lead = source.split(maxsplit=1)[0] if source else ""
    if source and core and source not in core and (not source_lead or source_lead not in core):
        return f"{source}｜{core}"
    return core or source or "公開口琴活動"


def compact_for_llm(text: str, limit: int = 2200) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, dict) else default


def atomic_write_text(path: Path, text: str) -> None:
    """Publish in one rename so the calendar sync never reads a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def candidate_fingerprint(item: dict[str, Any], start: str, end: str, context: str) -> str:
    payload = {
        "policyVersion": CALENDAR_REVIEW_POLICY_VERSION,
        "source": item.get("source") or "",
        "link": item.get("link") or "",
        "start": start,
        "end": end,
        "text": compact_for_llm(str(item.get("text") or item.get("title") or ""), 1200),
        "context": compact_for_llm(context, 500),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_llm_calendar_review(value: dict[str, Any]) -> dict[str, Any]:
    include = bool(value.get("include"))
    country = str(value.get("country") or "").strip()
    event_name = str(value.get("eventName") or "").strip()
    venue = str(value.get("venue") or "").strip()
    city = str(value.get("city") or "").strip()
    details = str(value.get("details") or "").strip()
    reason = str(value.get("reason") or "").strip()
    requested_mode = str(value.get("eventMode") or "").strip()
    candidate_date_matches = value.get("candidateDateMatches") is True
    confidence = value.get("confidence")
    try:
        confidence_value = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence_value = 0.0
    place_text = f"{venue} {city} {details} {reason}"
    mode = classify_event_mode(country, f"{event_name} {place_text}", requested_mode)
    timezone = valid_timezone(value.get("timezone")) or infer_timezone(country)
    if mode == TAIWAN_PHYSICAL:
        country = "臺灣"
        timezone = TIMEZONE
    elif mode == ONLINE:
        country = "線上"
    include = include and bool(mode) and candidate_date_matches
    if confidence_value < 0.5:
        include = False
    if include and (not event_name or (not venue and mode != ONLINE)):
        include = False
    return {
        "include": include,
        "country": country,
        "eventMode": mode,
        "timezone": timezone,
        "candidateDateMatches": candidate_date_matches,
        "eventName": event_name,
        "venue": venue or ("線上直播" if mode == ONLINE else ""),
        "city": city,
        "details": details,
        "reason": reason,
        "confidence": round(confidence_value, 3),
    }


def llm_calendar_prompt(item: dict[str, Any], start: str, end: str, context: str) -> list[dict[str, str]]:
    payload = {
        "source": item.get("source") or "",
        "platform": item.get("platform") or "",
        "postedAt": item.get("posted_at_local") or item.get("posted_at") or "",
        "url": item.get("link") or "",
        "candidateStart": start,
        "candidateEnd": end,
        "dateContext": compact_for_llm(context, 700),
        "text": compact_for_llm(str(item.get("text") or item.get("title") or ""), 2200),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是臺灣口琴觀測站的公開活動日曆審核器。"
                "只根據公開貼文文字判斷，收錄公開口琴活動；"
                "收錄範圍是：臺灣實體活動、臺灣以外的國外實體活動，以及國內外有明確時間的線上直播/線上講座/線上音樂會。"
                "三種 eventMode 必須互斥；有直播或線上報名資訊的實體活動仍依實際舉辦地點分類。"
                "排除已發生的回顧影片、一般貼文、非口琴活動、沒有明確活動時間的隨選影片。"
                "必須只判斷 candidateStart、candidateEnd 與 dateContext 對應的候選；"
                "如果全文其他段落有不同日期的另一個活動，請忽略它，不要拿來補這個候選。"
                "請只回傳 JSON，不要 Markdown。"
            ),
        },
        {
            "role": "user",
            "content": (
                "請判斷這個候選是否應加入「口琴公開活動」日曆，並萃取結構化資訊。\n"
                "JSON schema:\n"
                "{\n"
                '  "include": true/false,\n'
                '  "eventMode": "taiwan_physical、overseas_physical 或 online",\n'
                '  "candidateDateMatches": "只有 eventName 與 details 描述的活動日期確實等於 candidateStart 候選日期時才是 true",\n'
                '  "country": "臺灣、其他國家/地區，或線上",\n'
                '  "timezone": "活動公告時間所使用的 IANA timezone，例如 Asia/Taipei、Asia/Tokyo；無法可靠判斷則空字串",\n'
                '  "eventName": "活動名稱，不要放主辦帳號或貼文內文摘要",\n'
                '  "venue": "活動地點/場館名稱；純線上活動可填線上直播或平台名稱；不要放整段內文",\n'
                '  "city": "縣市或城市；純線上可空白",\n'
                '  "details": "一到兩句活動相關資訊，例如演出者、票價、報名、直播平台、場次；不要寫自動抽取說明",\n'
                '  "confidence": 0.0,\n'
                '  "reason": "簡短判斷理由"\n'
                "}\n\n"
                "若貼文同時提到其他日期的活動、旅程或比賽，不能把另一個活動名稱套到 candidateStart；"
                "日期不一致時 include 與 candidateDateMatches 都必須是 false。\n"
                f"候選資料：{json.dumps(payload, ensure_ascii=False)}"
            ),
        },
    ]


def review_candidate_with_llm(
    item: dict[str, Any],
    *,
    start: str,
    end: str,
    context: str,
    cache: dict[str, Any],
    token: str,
    base_url: str,
    model: str,
    timeout: int,
    stats: dict[str, int],
) -> dict[str, Any] | None:
    fingerprint = candidate_fingerprint(item, start, end, context)
    cached = ((cache.get("items") or {}).get(fingerprint))
    if isinstance(cached, dict):
        stats["cached"] = stats.get("cached", 0) + 1
        return normalize_llm_calendar_review(cached)
    if not token:
        return None
    body = {
        "model": model,
        "messages": llm_calendar_prompt(item, start, end, context),
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    response_body = watchdog.curl_json(watchdog.llm_endpoint(base_url), token, body, timeout)
    response = json.loads(response_body)
    parsed = watchdog.extract_json_object(watchdog.chat_response_text(response))
    normalized = normalize_llm_calendar_review(parsed)
    items = cache.setdefault("items", {})
    if isinstance(items, dict):
        items[fingerprint] = normalized
        cache["version"] = 1
        cache["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    stats["requests"] = stats.get("requests", 0) + 1
    return normalized


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
            if date_match_is_truncated(text, match.end()):
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


def fallback_calendar_review(item: dict[str, Any], title: str, location: str, text: str) -> dict[str, Any] | None:
    combined = f"{title} {location} {text}"
    country = infer_country(f"{title} {location}")
    if not country and TAIWAN_PLACE_RE.search(f"{title} {location}"):
        country = "臺灣"
    requested_mode = ONLINE if not location and is_online_event_text(combined) else ""
    mode = classify_event_mode(country, combined, requested_mode)
    if not mode:
        return None
    if not location and mode != ONLINE:
        return None
    timezone = TIMEZONE if mode == TAIWAN_PHYSICAL else infer_timezone(country)
    return {
        "include": True,
        "country": "線上" if mode == ONLINE else country,
        "eventMode": mode,
        "timezone": timezone,
        "candidateDateMatches": True,
        "eventName": title,
        "venue": location or ("線上直播" if mode == ONLINE else ""),
        "city": "",
        "details": "",
        "reason": "fallback public harmonica event match",
        "confidence": 0.35,
    }


def title_date_conflicts(title: str, start_date: dt.date) -> bool:
    dates = [
        (int(match.group("month")), int(match.group("day")))
        for match in MONTH_DAY_RE.finditer(title)
        if not date_match_is_truncated(title, match.end())
    ]
    if not dates:
        return False
    return all((month, day) != (start_date.month, start_date.day) for month, day in dates)


def event_start_date_key(event: dict[str, Any]) -> str:
    return str(event.get("start") or "")[:10]


def location_signature(location: Any) -> set[str]:
    text = str(location or "").lower()
    tokens = set(re.findall(r"[a-z0-9]{4,}", text))
    compact_cjk = re.sub(r"[^\u3400-\u9fff\u3040-\u30ff]+", "", text)
    for index in range(max(0, len(compact_cjk) - 3)):
        tokens.add(compact_cjk[index:index + 4])
    return tokens


def event_confidence(event: dict[str, Any]) -> float:
    try:
        return float(event.get("confidence") or 0)
    except (TypeError, ValueError):
        return 0.0


def event_has_time(event: dict[str, Any]) -> bool:
    return "T" in str(event.get("start") or "")


def should_replace_similar_event(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    # Verified form submissions always beat scraped events, whichever side they land on.
    existing_submitted = existing.get("platform") == SUBMITTED_PLATFORM
    candidate_submitted = candidate.get("platform") == SUBMITTED_PLATFORM
    if existing_submitted != candidate_submitted:
        return candidate_submitted
    existing_confidence = event_confidence(existing)
    candidate_confidence = event_confidence(candidate)
    if candidate_confidence > existing_confidence:
        return True
    if candidate_confidence == existing_confidence:
        return event_has_time(candidate) and not event_has_time(existing)
    return False


GENERIC_TITLE_ANCHORS = {
    "年度音樂會",
    "成果發表會",
    "臺灣口琴音樂節",
    "口琴音樂節",
    "口琴節",
    "演奏會",
    "音樂會",
}
MULTI_DAY_EVENT_RE = re.compile(
    r"(?:節|节|festival|大會|大会|賽|赛|contest|competition|營|营|camp)",
    re.IGNORECASE,
)
TITLE_VARIANT_TRANSLATION = str.maketrans(
    {
        "亚": "亞",
        "会": "會",
        "届": "屆",
        "节": "節",
        "赛": "賽",
    }
)


def normalized_title(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3040-\u30ff\u3400-\u9fff]+",
        "",
        str(value or "").translate(TITLE_VARIANT_TRANSLATION).casefold(),
    )


def leading_cjk_title_anchor(value: Any) -> str:
    match = re.match(r"\s*([\u3400-\u9fff]{4,})", str(value or ""))
    if not match:
        return ""
    anchor = match.group(1)
    if anchor in GENERIC_TITLE_ANCHORS or anchor.endswith(("口琴音樂節", "成果發表會")):
        return ""
    return anchor


def event_titles_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = left.get("eventName") or left.get("title")
    right_title = right.get("eventName") or right.get("title")
    left_normalized = normalized_title(left_title)
    right_normalized = normalized_title(right_title)
    if left_normalized and left_normalized == right_normalized:
        return True
    # The anchor fallback exists to fold a truncated record into a complete one. Two
    # equally detailed events that merely share an organiser prefix are usually distinct.
    if event_has_time(left) == event_has_time(right):
        return False
    left_anchor = leading_cjk_title_anchor(left_title)
    right_anchor = leading_cjk_title_anchor(right_title)
    return bool(left_anchor and left_anchor == right_anchor)


def event_times_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start = str(left.get("start") or "")
    right_start = str(right.get("start") or "")
    if "T" not in left_start or "T" not in right_start:
        return True
    return left_start[11:16] == right_start[11:16]


def all_day_date_range(event: dict[str, Any]) -> tuple[dt.date, dt.date] | None:
    if not event.get("allDay"):
        return None
    try:
        start = dt.date.fromisoformat(str(event.get("start") or "")[:10])
        end = dt.date.fromisoformat(str(event.get("end") or "")[:10])
    except ValueError:
        return None
    if end <= start:
        end = start + dt.timedelta(days=1)
    return start, end


def multi_day_events_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = normalized_title(left.get("eventName") or left.get("title"))
    right_title = normalized_title(right.get("eventName") or right.get("title"))
    if not left_title or left_title != right_title or not MULTI_DAY_EVENT_RE.search(left_title):
        return False
    if left.get("calendarType") != right.get("calendarType"):
        return False
    left_range = all_day_date_range(left)
    right_range = all_day_date_range(right)
    if not left_range or not right_range:
        return False
    left_start, left_end = left_range
    right_start, right_end = right_range
    overlap_start = max(left_start, right_start)
    overlap_end = min(left_end, right_end)
    if overlap_start < overlap_end:
        return True
    if overlap_start > overlap_end:
        return False
    # All-day end dates are exclusive, so touching ranges do not really overlap. Fold them
    # together only when one side is short enough to look like a truncated record.
    shortest = min(left_end - left_start, right_end - right_start)
    return shortest <= dt.timedelta(days=2)


def find_similar_event_index(events: list[dict[str, Any]], candidate: dict[str, Any]) -> int | None:
    candidate_location = location_signature(candidate.get("location"))
    for index, existing in enumerate(events):
        if multi_day_events_match(existing, candidate):
            return index
        if event_start_date_key(existing) != event_start_date_key(candidate):
            continue
        if not event_times_compatible(existing, candidate):
            continue
        existing_url = str(existing.get("evidenceUrl") or "").strip()
        candidate_url = str(candidate.get("evidenceUrl") or "").strip()
        if existing_url and existing_url == candidate_url:
            return index
        if event_titles_match(existing, candidate):
            return index
        if not candidate_location:
            continue
        existing_location = location_signature(existing.get("location"))
        if len(candidate_location & existing_location) >= 2:
            return index
    return None


def event_sort_key(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(event.get("start") or ""),
        str(event.get("source") or ""),
        str(event.get("title") or ""),
    )


def deduplicate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped_events: list[dict[str, Any]] = []
    seen_final: set[tuple[str, str, str]] = set()
    for event in sorted(events, key=event_sort_key):
        key = (
            normalized_title(event.get("eventName") or event.get("title")),
            re.sub(r"\s+", "", str(event.get("location") or "")).lower(),
            str(event.get("start") or ""),
        )
        if key in seen_final:
            continue
        similar_index = find_similar_event_index(deduped_events, event)
        if similar_index is not None:
            if should_replace_similar_event(deduped_events[similar_index], event):
                deduped_events[similar_index] = event
            continue
        seen_final.add(key)
        deduped_events.append(event)
    # In-place replacements can leave a later event sitting at an earlier index.
    return sorted(deduped_events, key=event_sort_key)


def extract_events(
    items: list[dict[str, Any]],
    *,
    overrides: dict[str, dict[str, Any]] | None = None,
    llm_token: str = "",
    llm_base_url: str = watchdog.OPENAI_BASE_URL,
    llm_model: str = watchdog.DEFAULT_LLM_MODEL,
    llm_timeout: int = 45,
    llm_cache: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen_links_dates: set[tuple[str, str]] = set()
    seen_event_identity: set[tuple[str, str, str]] = set()
    cache = llm_cache if isinstance(llm_cache, dict) else {"version": 1, "items": {}}
    override_by_url = overrides or {}
    used_overrides: set[str] = set()
    llm_stats: dict[str, int] = {"requests": 0, "cached": 0, "errors": 0}
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
        link = str(item.get("link") or "")
        if link in override_by_url:
            override = dict(override_by_url[link])
            start_for_id = parse_datetime(override.get("start"))
            start_date = start_for_id.date() if start_for_id else safe_date(*[int(part) for part in str(override.get("start", ""))[:10].split("-")])
            if start_date:
                override.update(
                    {
                        "id": item_key(item, start_date),
                        "source": item.get("source") or "",
                        "platform": item.get("platform") or "",
                        "postedAt": item.get("posted_at_local") or item.get("posted_at") or "",
                        "images": override.get("images") or item.get("images") or [],
                        "image_url": override.get("image_url") or item.get("image_url") or "",
                    }
                )
                events.append(override)
                used_overrides.add(link)
                seen_links_dates.add((link, start_date.isoformat()))
            continue
        candidates = date_candidates(text, posted_at)
        for start_date, end_date, context in candidates:
            if start_date < min_date or start_date > max_date:
                continue
            dedupe_key = (link, start_date.isoformat())
            if dedupe_key in seen_links_dates:
                continue
            seen_links_dates.add(dedupe_key)
            title = event_title(item, context)
            if CANCELLED_EVENT_RE.search(f"{title} {context}"):
                continue
            identity = normalized_event_identity(title, item.get("source"), start_date)
            if identity in seen_event_identity:
                continue
            seen_event_identity.add(identity)
            time_text = extract_time(context)
            if title_date_conflicts(title, start_date):
                continue
            start = f"{start_date.isoformat()}T{time_text}:00+08:00" if time_text else start_date.isoformat()
            end = end_date.isoformat()
            if time_text:
                end_dt = dt.datetime.combine(start_date, dt.time.fromisoformat(time_text), TAIWAN_TZ) + dt.timedelta(hours=2)
                if end_date > start_date:
                    end_dt = dt.datetime.combine(end_date, dt.time(23, 59), TAIWAN_TZ)
                end = end_dt.isoformat()
            elif end_date >= start_date:
                end = (end_date + dt.timedelta(days=1)).isoformat()
            location = extract_location(context)
            if not location and len(candidates) == 1:
                location = extract_location(text)
            review: dict[str, Any] | None = None
            if llm_token:
                try:
                    review = review_candidate_with_llm(
                        item,
                        start=start,
                        end=end,
                        context=context,
                        cache=cache,
                        token=llm_token,
                        base_url=llm_base_url,
                        model=llm_model,
                        timeout=llm_timeout,
                        stats=llm_stats,
                    )
                except Exception as exc:
                    llm_stats["errors"] = llm_stats.get("errors", 0) + 1
                    print(f"calendar LLM review failed for {link}: {exc}", file=sys.stderr)
            if review is None:
                review = fallback_calendar_review(item, title, location, text)
            if not review or not review.get("include"):
                continue
            if review.get("confidence") == 0.35 and not review.get("country") == "臺灣" and not time_text:
                continue
            event_name = str(review.get("eventName") or title).strip()
            venue = clean_location(str(review.get("venue") or location))
            city = str(review.get("city") or "").strip()
            details = str(review.get("details") or "").strip()
            country = str(review.get("country") or "").strip()
            mode = classify_event_mode(
                country,
                f"{event_name} {venue} {city} {details}",
                str(review.get("eventMode") or ""),
            )
            if not mode:
                continue
            if mode == ONLINE and (not time_text or not is_online_event_text(context)):
                continue
            if mode == TAIWAN_PHYSICAL and GENERIC_ONLINE_VENUE_RE.fullmatch(venue):
                venue = clean_location(location)
                if not venue:
                    continue
            timezone = valid_timezone(review.get("timezone")) or infer_timezone(country)
            if mode == TAIWAN_PHYSICAL:
                country = "臺灣"
                timezone = TIMEZONE
            elif mode == OVERSEAS_PHYSICAL:
                location_country = infer_country(f"{venue} {city}") or infer_country(details)
                if location_country:
                    country = location_country
                    timezone = infer_timezone(location_country) or timezone
            elif mode == ONLINE:
                country = "線上"
            if time_text and not timezone:
                continue
            timezone = timezone or TIMEZONE
            event_zone = ZoneInfo(timezone)
            start = start_date.isoformat()
            end = (end_date + dt.timedelta(days=1)).isoformat()
            if time_text:
                start_dt = dt.datetime.combine(start_date, dt.time.fromisoformat(time_text), event_zone)
                end_dt = start_dt + dt.timedelta(hours=2)
                if end_date > start_date:
                    end_dt = dt.datetime.combine(end_date, dt.time(23, 59), event_zone)
                start = start_dt.isoformat()
                end = end_dt.isoformat()
            review["country"] = country
            review["eventMode"] = mode
            review["timezone"] = timezone
            display_location = venue if not city or city in venue else f"{city} {venue}"
            events.append(
                {
                    "id": item_key(item, start_date),
                    "title": event_name,
                    "eventName": event_name,
                    "source": item.get("source") or "",
                    "platform": item.get("platform") or "",
                    "start": start,
                    "end": end,
                    "allDay": not bool(time_text),
                    "calendarType": mode,
                    "timezone": timezone,
                    "location": display_location,
                    "venue": venue,
                    "city": city,
                    "details": details,
                    "evidenceUrl": link,
                    "confidence": review.get("confidence") or 0,
                    "calendarReview": review,
                    "postedAt": item.get("posted_at_local") or item.get("posted_at") or "",
                    "images": item.get("images") or [],
                    "image_url": item.get("image_url") or "",
                }
            )

    cache["stats"] = llm_stats
    return deduplicate_events(events)


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


def ics_datetime(value: str, *, all_day: bool, timezone: str = TIMEZONE) -> str:
    if all_day:
        return value.replace("-", "")
    parsed = dt.datetime.fromisoformat(value)
    return parsed.astimezone(ZoneInfo(timezone)).strftime("%Y%m%dT%H%M%S")


def calendar_description(event: dict[str, Any]) -> str:
    return "\n".join(
        part
        for part in [
            str(event.get("details") or "").strip(),
            str(event.get("evidenceUrl") or "").strip(),
        ]
        if part
    )


def write_ics(
    events: list[dict[str, Any]],
    generated_at: str,
    *,
    path: Path = ICS_PATH,
    calendar_name: str = "臺灣口琴實體活動",
) -> None:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Harmonica Observe Taiwan//Public Calendar//ZH-TW",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics(calendar_name)}",
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
            event_timezone = valid_timezone(event.get("timezone")) or TIMEZONE
            lines.append(
                f"DTSTART;TZID={event_timezone}:"
                f"{ics_datetime(event['start'], all_day=False, timezone=event_timezone)}"
            )
            lines.append(
                f"DTEND;TZID={event_timezone}:"
                f"{ics_datetime(event['end'], all_day=False, timezone=event_timezone)}"
            )
        lines.append(f"SUMMARY:{escape_ics(event['title'])}")
        if event.get("location"):
            lines.append(f"LOCATION:{escape_ics(event['location'])}")
        lines.append(f"DESCRIPTION:{escape_ics(calendar_description(event))}")
        if event.get("evidenceUrl"):
            lines.append(f"URL:{escape_ics(event['evidenceUrl'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    atomic_write_text(path, "\r\n".join(fold_ics_line(line) for line in lines) + "\r\n")


def calendar_payload(
    events: list[dict[str, Any]],
    *,
    mode: str,
    generated_at: str,
    ics_path: str,
    criteria: str,
    overrides: int,
    llm: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": 2,
        "generatedAt": generated_at,
        "timezone": TIMEZONE,
        "calendarType": mode,
        "count": len(events),
        "source": "/api/events.json",
        "ics": ics_path,
        "rightsNote": "只整理公開貼文中的活動 metadata、日期與來源連結；請以原始公開貼文或售票/報名頁為準。",
        "criteria": criteria,
        "manualOverrides": overrides,
        "llm": llm,
        "events": events,
    }


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--llm-cache", type=Path, default=DEFAULT_LLM_CACHE)
    parser.add_argument("--llm-base-url", default=os.environ.get("HARMONICA_LLM_BASE_URL", watchdog.OPENAI_BASE_URL))
    parser.add_argument("--llm-model", default=os.environ.get("HARMONICA_LLM_MODEL", watchdog.DEFAULT_LLM_MODEL))
    parser.add_argument("--llm-timeout", type=int, default=int(os.environ.get("HARMONICA_LLM_TIMEOUT", "45")))
    parser.add_argument("--llm-keychain-service", default=os.environ.get("HARMONICA_LLM_KEYCHAIN_SERVICE", watchdog.DEFAULT_LLM_KEYCHAIN_SERVICE))
    parser.add_argument("--llm-keychain-account", default=os.environ.get("HARMONICA_LLM_KEYCHAIN_ACCOUNT", watchdog.DEFAULT_LLM_KEYCHAIN_ACCOUNT))
    args = parser.parse_args()
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    llm_cache = load_json(args.llm_cache, {"version": 1, "items": {}})
    llm_token = ""
    llm_token_source = ""
    if not args.no_llm:
        llm_token, llm_token_source = watchdog.read_llm_token(args.llm_keychain_service, args.llm_keychain_account)
    overrides = load_overrides()
    generated_at = dt.datetime.now(TAIWAN_TZ).isoformat(timespec="seconds")
    events = extract_events(
        [item for item in items if isinstance(item, dict)],
        overrides=overrides,
        llm_token=llm_token,
        llm_base_url=args.llm_base_url,
        llm_model=args.llm_model,
        llm_timeout=args.llm_timeout,
        llm_cache=llm_cache,
    )
    if llm_token:
        save_json(args.llm_cache, llm_cache)
    llm_metadata = {
        "enabled": bool(llm_token),
        "tokenSource": llm_token_source,
        "model": args.llm_model if llm_token else "",
        "stats": llm_cache.get("stats") or {},
    }
    events_by_mode = {
        mode: [event for event in events if event.get("calendarType") == mode]
        for mode in EVENT_MODES
    }
    output = calendar_payload(
        events_by_mode[TAIWAN_PHYSICAL],
        mode=TAIWAN_PHYSICAL,
        generated_at=generated_at,
        ics_path="/feeds/public-calendar.ics",
        criteria="實際舉辦地點在臺灣的公開口琴實體活動。",
        overrides=len(overrides),
        llm=llm_metadata,
    )
    overseas_output = calendar_payload(
        events_by_mode[OVERSEAS_PHYSICAL],
        mode=OVERSEAS_PHYSICAL,
        generated_at=generated_at,
        ics_path="/feeds/overseas-calendar.ics",
        criteria="實際舉辦地點在臺灣以外的公開口琴實體活動。",
        overrides=len(overrides),
        llm=llm_metadata,
    )
    online_output = calendar_payload(
        events_by_mode[ONLINE],
        mode=ONLINE,
        generated_at=generated_at,
        ics_path="/feeds/online-calendar.ics",
        criteria="國內外有明確日期、時間與直播或線上參與方式的公開口琴活動。",
        overrides=len(overrides),
        llm=llm_metadata,
    )
    for path, payload in [
        (JSON_PATH, output),
        (OVERSEAS_JSON_PATH, overseas_output),
        (ONLINE_JSON_PATH, online_output),
    ]:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(
        JS_PATH,
        "window.publicCalendarEvents = " + json.dumps(output, ensure_ascii=False, indent=2) + ";\n",
    )
    write_ics(events_by_mode[TAIWAN_PHYSICAL], generated_at)
    write_ics(
        events_by_mode[OVERSEAS_PHYSICAL],
        generated_at,
        path=OVERSEAS_ICS_PATH,
        calendar_name="國外口琴實體活動",
    )
    write_ics(
        events_by_mode[ONLINE],
        generated_at,
        path=ONLINE_ICS_PATH,
        calendar_name="線上口琴活動",
    )
    print(
        "Built public calendar events: "
        f"taiwan={len(events_by_mode[TAIWAN_PHYSICAL])} "
        f"overseas={len(events_by_mode[OVERSEAS_PHYSICAL])} "
        f"online={len(events_by_mode[ONLINE])}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
