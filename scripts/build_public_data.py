#!/usr/bin/env python3
"""Build the public data bundle for harmonica.observe.tw."""

from __future__ import annotations

import csv
import email.utils
import hashlib
import json
import re
import urllib.parse
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
DATA_OUT = SITE_ROOT / "data" / "site-data.js"
CANDIDATES = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
SOURCE_PROFILES_CACHE = PROJECT_ROOT / "data" / "feeds" / "source_profiles.json"
SOCIAL_SOURCES = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
SOURCE_TAG_CACHE = PROJECT_ROOT / "state" / "source_llm_tags.json"
SOURCE_AVATAR_DIR = SITE_ROOT / "assets" / "source-avatars"
TAIPEI_TZ = timezone(timedelta(hours=8))
AVATAR_PLATFORM_PRIORITY = {
    "instagram": 0,
    "facebook": 1,
    "youtube": 2,
}
DEFAULT_AVATAR_PLATFORM_PRIORITY = 99
TAG_VALUE_SPLIT_RE = re.compile(r"\s*(?:[,，、/／+&]|\band\b|\s+)\s*", re.IGNORECASE)
TAG_FORBIDDEN_CHARS_RE = re.compile(r"[,，、/／+&\s]")

SOURCE_FILES = [
    ("watchlist", PROJECT_ROOT / "data" / "sources" / "harmonica-source-watchlist-public.csv"),
    ("club", PROJECT_ROOT / "data" / "sources" / "harmonica-clubs-public.csv"),
]

LINK_FIELDS = [
    ("website_url", "網站"),
    ("fb_url", "Facebook"),
    ("ig_url", "Instagram"),
    ("youtube_url", "YouTube"),
    ("x_url", "X"),
    ("threads_url", "Threads"),
    ("tiktok_url", "TikTok"),
    ("contact_public_url", "公開聯絡"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value: str | None) -> str:
    return (value or "").strip()


def normalize_tag_values(value: Any, *, limit: int = 8) -> list[str]:
    if isinstance(value, str):
        raw_values: list[Any] = [value]
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = []

    tags: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        if not text:
            continue
        for tag in TAG_VALUE_SPLIT_RE.split(text):
            tag = tag.strip()
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= limit:
                return tags
    return tags


def normalize_key(value: str | None) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", clean(value).casefold())


def is_public_url(value: str) -> bool:
    return value.startswith("https://") or value.startswith("http://")


def parse_time(value: str | None) -> datetime | None:
    raw = clean(value)
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def local_time_label(value: datetime) -> str:
    return value.astimezone(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")


def url_handles(url: str) -> set[str]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.casefold().removeprefix("www.")
    path_parts = [
        urllib.parse.unquote(part).strip("@")
        for part in parsed.path.split("/")
        if part.strip("/")
    ]
    handles: set[str] = set()
    if not path_parts:
        return handles
    first = path_parts[0]
    if "instagram.com" in host or "threads.net" in host:
        if first not in {"p", "reel", "reels", "tv", "stories"}:
            handles.add(first)
    elif "facebook.com" in host:
        if first not in {"p", "people", "pages", "profile.php"}:
            handles.add(first)
    elif host in {"x.com", "twitter.com"}:
        if first not in {"home", "i", "intent", "search", "share", "hashtag", "explore"}:
            handles.add(first)
    elif "tiktok.com" in host:
        if first.startswith("@"):
            handles.add(first)
    elif "youtube.com" in host and first.startswith("@"):
        handles.add(first)
    elif "youtube.com" in host and first not in {"channel", "c", "user"}:
        handles.add(first)
    return {normalize_key(handle) for handle in handles if handle}


def source_initials(source: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", source or "")
    if words:
        return "".join(word[0].upper() for word in words[:3])
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", source or "")
    if chinese_chars:
        return "".join(chinese_chars[:2])
    return "H"


def entry_match_keys(entry: dict[str, object]) -> set[str]:
    keys = {
        normalize_key(str(entry.get("name") or "")),
        normalize_key(str(entry.get("nameEn") or "")),
    }
    for alias in entry.get("aliases", []):
        keys.add(normalize_key(str(alias or "")))
    keywords = str(entry.get("keywords") or "")
    if keywords:
        keys.add(normalize_key(keywords))
    for link in entry.get("links", []):
        if isinstance(link, dict):
            keys.update(url_handles(str(link.get("url") or "")))
    return {key for key in keys if key}


def profile_match_keys(profile: dict[str, Any]) -> set[str]:
    keys = {
        normalize_key(str(profile.get("name") or "")),
        normalize_key(str(profile.get("account") or "")),
    }
    source_id = str(profile.get("id") or "")
    for prefix in ("ig_", "fb_", "yt_", "youtube_", "x_", "twitter_", "threads_", "tiktok_"):
        if source_id.startswith(prefix):
            keys.add(normalize_key(source_id[len(prefix) :]))
    for field in ("account", "profile_url"):
        value = str(profile.get(field) or "")
        if is_public_url(value):
            keys.update(url_handles(value))
    return {key for key in keys if key}


def candidate_match_keys(row: dict[str, Any]) -> set[str]:
    keys = {
        normalize_key(str(row.get("source_name") or "")),
        normalize_key(str(row.get("account") or "")),
    }
    source_id = str(row.get("source_id") or "")
    for prefix in ("ig_", "fb_", "yt_", "youtube_", "x_", "twitter_", "threads_", "tiktok_"):
        if source_id.startswith(prefix):
            keys.add(normalize_key(source_id[len(prefix) :]))
    if row.get("url"):
        keys.update(url_handles(str(row.get("url"))))
    return {key for key in keys if key}


def entry_tag_fingerprint(entry: dict[str, object]) -> str:
    payload = {
        "name": entry.get("name") or "",
        "nameEn": entry.get("nameEn") or "",
        "aliases": entry.get("aliases") or [],
        "category": entry.get("category") or "",
        "type": entry.get("type") or "",
        "region": entry.get("region") or "",
        "cityOrFocus": entry.get("cityOrFocus") or "",
        "summary": entry.get("summary") or "",
        "keywords": entry.get("keywords") or "",
        "links": entry.get("links") or [],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_link_key(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.casefold().removeprefix("www.")
    path = "/".join(
        urllib.parse.unquote(part).strip().strip("@").casefold()
        for part in parsed.path.split("/")
        if part.strip("/")
    )
    if any(
        domain in host
        for domain in ("facebook.com", "instagram.com", "youtube.com", "x.com", "twitter.com", "threads.net", "tiktok.com")
    ):
        handles = sorted(url_handles(url))
        if handles:
            return f"{host}:{handles[0]}"
    return f"{host}/{path}".rstrip("/")


def entry_identity_keys(entry: dict[str, object]) -> set[str]:
    keys: set[str] = set()
    for link in entry.get("links", []):
        if isinstance(link, dict):
            key = canonical_link_key(str(link.get("url") or ""))
            if key:
                keys.add(key)
    return keys


def social_identity_keys(entry: dict[str, object]) -> set[str]:
    keys: set[str] = set()
    for link in entry.get("links", []):
        if not isinstance(link, dict):
            continue
        url = str(link.get("url") or "")
        host = urllib.parse.urlparse(url).netloc.casefold()
        if any(
            domain in host
            for domain in ("facebook.com", "instagram.com", "youtube.com", "x.com", "twitter.com", "threads.net", "tiktok.com")
        ):
            key = canonical_link_key(url)
            if key:
                keys.add(key)
    return keys


def entry_text(entry: dict[str, object]) -> str:
    return " ".join(
        str(entry.get(field) or "")
        for field in ("name", "nameEn", "category", "type", "country", "region", "cityOrFocus", "summary", "keywords")
    )


def source_like(entry: dict[str, object]) -> bool:
    text = entry_text(entry)
    return any(word in text for word in ("來源", "教學", "工作室", "教室", "專賣店", "品牌", "器材", "平台"))


def person_like(entry: dict[str, object]) -> bool:
    return "個人" in entry_text(entry)


def duplicate_entries(left: dict[str, object], right: dict[str, object]) -> bool:
    if normalize_key(str(left.get("name") or "")) == normalize_key(str(right.get("name") or "")):
        return True

    left_keys = entry_identity_keys(left)
    right_keys = entry_identity_keys(right)
    shared_keys = left_keys & right_keys
    if len(shared_keys) >= 2:
        return True

    left_social = social_identity_keys(left)
    right_social = social_identity_keys(right)
    shared_social = left_social & right_social
    if shared_social and ((person_like(left) and source_like(right)) or (person_like(right) and source_like(left))):
        return True

    return False


def entry_score(entry: dict[str, object]) -> tuple[int, int, int, int, int]:
    name = str(entry.get("name") or "")
    generic_penalty = sum(word in name for word in ("相關", "子來源", "新團體", "參考來源"))
    return (
        1 if entry.get("status") == "已查核" else 0,
        len(entry.get("links", []) or []),
        -generic_penalty,
        1 if source_like(entry) and not person_like(entry) else 0,
        -len(name),
    )


def best_entry(entries: list[dict[str, object]]) -> dict[str, object]:
    return max(entries, key=entry_score)


def summary_score(entry: dict[str, object], primary: dict[str, object]) -> tuple[int, int, int, int, int, int]:
    summary = str(entry.get("summary") or "")
    noisy_words = ("相關來源", "監看", "觀察", "線索", "資料來源", "參考來源")
    generic_name_words = ("相關", "子來源", "新團體", "參考來源")
    parts = [part for part in summary.split(" / ") if part]
    return (
        1 if entry.get("source") == "club" and entry.get("category") == "學校社團" else 0,
        1 if entry is primary else 0,
        1 if entry.get("status") == "已查核" else 0,
        -sum(word in summary for word in noisy_words),
        -sum(word in str(entry.get("name") or "") for word in generic_name_words),
        -abs(len(parts) - 3),
        -len(summary),
    )


def best_summary_entry(entries: list[dict[str, object]], primary: dict[str, object]) -> dict[str, object]:
    return max(entries, key=lambda entry: summary_score(entry, primary))


def strongest_status(entries: list[dict[str, object]]) -> str:
    statuses = [str(entry.get("status") or "") for entry in entries]
    if "已查核" in statuses:
        return "已查核"
    if "部分查核" in statuses:
        return "部分查核"
    return "待確認"


def strongest_source_status(entries: list[dict[str, object]]) -> str:
    statuses = [str(entry.get("sourceStatus") or "") for entry in entries if entry.get("sourceStatus")]
    if any("已查核" in status and "部分" not in status for status in statuses):
        return "已查核公開連結"
    if any("部分" in status for status in statuses):
        return "部分已查核公開連結"
    return statuses[0] if statuses else ""


def merge_unique_strings(values: list[str]) -> list[str]:
    merged: list[str] = []
    for value in values:
        text = clean(value)
        if text and text not in merged:
            merged.append(text)
    return merged


def merge_links(entries: list[dict[str, object]]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in sorted(entries, key=lambda item: -len(item.get("links", []) or [])):
        for link in entry.get("links", []):
            if not isinstance(link, dict):
                continue
            url = str(link.get("url") or "")
            key = canonical_link_key(url)
            if not url or key in seen:
                continue
            links.append({"label": str(link.get("label") or "公開連結"), "url": url})
            seen.add(key)
    return links


def merge_group(entries: list[dict[str, object]]) -> dict[str, object]:
    primary = best_entry(entries)
    summary_entry = best_summary_entry(entries, primary)
    aliases = merge_unique_strings(
        [
            str(value)
            for entry in entries
            for value in (entry.get("name"), entry.get("nameEn"))
            if value and value != primary.get("name") and value != primary.get("nameEn")
        ]
    )
    summaries = merge_unique_strings([str(entry.get("summary") or "") for entry in entries])
    keywords = merge_unique_strings([str(entry.get("keywords") or "") for entry in entries])
    types = merge_unique_strings([str(entry.get("type") or "") for entry in entries])
    countries = merge_unique_strings([str(entry.get("country") or "") for entry in entries])
    regions = merge_unique_strings([str(entry.get("region") or "") for entry in entries])
    focuses = merge_unique_strings([str(entry.get("cityOrFocus") or "") for entry in entries])

    merged = dict(primary)
    merged["id"] = "+".join(str(entry.get("id") or "") for entry in entries if entry.get("id"))
    merged["aliases"] = aliases
    merged["links"] = merge_links(entries)
    merged["type"] = " / ".join(types[:3])
    merged["country"] = str(primary.get("country") or (countries[0] if countries else ""))
    merged["region"] = " / ".join(regions[:3])
    merged["cityOrFocus"] = " / ".join(focuses[:3])
    merged["summary"] = str(summary_entry.get("summary") or " / ".join(summaries[:1]))
    merged["keywords"] = " ".join(keywords)
    merged["status"] = strongest_status(entries)
    merged["sourceStatus"] = strongest_source_status(entries)
    merged["source"] = "+".join(sorted({str(entry.get("source") or "") for entry in entries if entry.get("source")}))
    return merged


def merge_duplicate_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    parent = list(range(len(entries)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left_index, left in enumerate(entries):
        for right_index in range(left_index + 1, len(entries)):
            if duplicate_entries(left, entries[right_index]):
                union(left_index, right_index)

    groups: dict[int, list[dict[str, object]]] = {}
    for index, entry in enumerate(entries):
        groups.setdefault(find(index), []).append(entry)
    return [merge_group(group) for group in groups.values()]


def fallback_source_tags(entry: dict[str, object]) -> list[str]:
    text = " ".join(
        str(entry.get(field) or "")
        for field in ("name", "nameEn", "category", "type", "region", "cityOrFocus", "summary", "keywords")
    )
    tags: list[str] = []
    category = str(entry.get("category") or "")
    if category:
        tags.append(category)
    for needle, tag in [
        ("學校", "學生社團"),
        ("學生", "學生社團"),
        ("大學", "大專社團"),
        ("高中", "高中社團"),
        ("高級中學", "高中社團"),
        ("樂團", "團體樂團"),
        ("團體", "團體樂團"),
        ("個人", "演奏者"),
        ("教學", "教學"),
        ("課程", "課程"),
        ("工作室", "工作室"),
        ("音樂節", "音樂節"),
        ("比賽", "比賽"),
        ("成發", "成發"),
        ("半音階", "半音階"),
        ("複音", "複音"),
        ("十孔", "十孔"),
        ("重奏", "重奏"),
        ("國際", "國際交流"),
    ]:
        if needle in text:
            tags.append(tag)
    if "口琴" in text or tags:
        tags.insert(0, "口琴")
    return list(dict.fromkeys(tag for tag in tags if tag))[:8]


def source_tag_cache() -> dict[str, dict[str, Any]]:
    if not SOURCE_TAG_CACHE.exists():
        return {}
    data = json.loads(SOURCE_TAG_CACHE.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else {}
    return items if isinstance(items, dict) else {}


def apply_source_tags(entry: dict[str, object], cache: dict[str, dict[str, Any]]) -> None:
    cached = cache.get(entry_tag_fingerprint(entry)) or {}
    tags = cached.get("sourceTags") or cached.get("tags") or []
    source_tags = normalize_tag_values(tags)
    entry["sourceTags"] = source_tags[:8] if source_tags else fallback_source_tags(entry)

    summary = str(cached.get("sourceSummary") or cached.get("summary") or "").strip()
    if summary:
        entry["sourceSummary"] = summary

    reason = str(cached.get("sourceTagReason") or cached.get("reason") or "").strip()
    if reason:
        entry["sourceTagReason"] = reason


def cached_avatar_url(avatar_source_url: str) -> str:
    if not avatar_source_url:
        return ""
    if avatar_source_url.startswith("/assets/"):
        return avatar_source_url
    digest = hashlib.sha256(avatar_source_url.encode("utf-8")).hexdigest()[:20]
    existing = sorted(SOURCE_AVATAR_DIR.glob(f"{digest}.*"))
    if not existing:
        return ""
    return f"/assets/source-avatars/{existing[0].name}"


def profile_platform(profile: dict[str, Any]) -> str:
    platform = str(profile.get("platform") or "").casefold()
    if platform:
        return platform

    source_id = str(profile.get("id") or "").casefold()
    if source_id.startswith("ig_"):
        return "instagram"
    if source_id.startswith("fb_"):
        return "facebook"
    if source_id.startswith(("yt_", "youtube_")):
        return "youtube"

    profile_url = str(profile.get("profile_url") or profile.get("account") or "").casefold()
    if "instagram.com" in profile_url:
        return "instagram"
    if "facebook.com" in profile_url:
        return "facebook"
    if "youtube.com" in profile_url or "youtu.be" in profile_url:
        return "youtube"
    return platform


def avatar_platform_priority(platform: str) -> int:
    return AVATAR_PLATFORM_PRIORITY.get(platform, DEFAULT_AVATAR_PLATFORM_PRIORITY)


def avatar_payload_rank(payload: dict[str, Any]) -> tuple[int, int, str]:
    priority = payload.get("avatarPriority")
    if priority in (None, ""):
        priority = DEFAULT_AVATAR_PLATFORM_PRIORITY
    return (
        0 if payload.get("avatarUrl") else 1,
        int(priority),
        str(payload.get("avatarSource") or ""),
    )


def avatar_profiles_by_key() -> dict[str, dict[str, Any]]:
    if not SOURCE_PROFILES_CACHE.exists():
        return {}
    data = json.loads(SOURCE_PROFILES_CACHE.read_text(encoding="utf-8"))
    profiles = data.get("profiles") if isinstance(data, dict) else {}
    if not isinstance(profiles, dict):
        return {}

    by_key: dict[str, dict[str, Any]] = {}
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        platform = profile_platform(profile)
        source_name = str(profile.get("name") or profile.get("title") or "")
        avatar = cached_avatar_url(
            str(profile.get("avatar_url") or profile.get("avatar_source_url") or "")
        )
        payload = {
            "avatarUrl": avatar,
            "sourceInitials": source_initials(source_name),
            "avatarSource": source_name,
            "avatarPlatform": platform,
            "avatarPriority": avatar_platform_priority(platform),
        }
        for key in profile_match_keys(profile):
            existing = by_key.get(key)
            if existing and avatar_payload_rank(existing) <= avatar_payload_rank(payload):
                continue
            by_key[key] = payload
    return by_key


def apply_avatar(entry: dict[str, object], avatars: dict[str, dict[str, Any]]) -> None:
    matches = [
        avatars[key]
        for key in sorted(entry_match_keys(entry))
        if key in avatars
    ]
    best = min(matches, key=avatar_payload_rank) if matches else {}
    entry["avatarUrl"] = str(best.get("avatarUrl") or "")
    entry["sourceInitials"] = source_initials(str(entry.get("name") or best.get("avatarSource") or ""))


def read_candidates() -> list[dict[str, Any]]:
    if not CANDIDATES.exists():
        return []
    rows: list[dict[str, Any]] = []
    with CANDIDATES.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def is_source_page_backfill(row: dict[str, Any]) -> bool:
    if row.get("raw_source") == "public-link-backfill":
        return True
    media_type = str(row.get("media_type") or "")
    post_id = str(row.get("post_id") or "")
    return media_type in {"source_page", "directory_source_page"} or post_id.startswith("source_page:")


def latest_updates_by_key() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in read_candidates():
        if is_source_page_backfill(row):
            continue
        posted = parse_time(str(row.get("posted_at") or row.get("seen_at") or ""))
        if posted is None:
            continue
        update = {
            "dt": posted,
            "source": row.get("source_name") or row.get("source_id") or "",
            "url": row.get("url") or "",
            "title": row.get("text") or "",
        }
        for key in candidate_match_keys(row):
            existing = latest.get(key)
            if existing is None or posted > existing["dt"]:
                latest[key] = update
    return latest


def apply_latest_update(entry: dict[str, object], latest: dict[str, dict[str, Any]]) -> None:
    matches = [latest[key] for key in entry_match_keys(entry) if key in latest]
    if not matches:
        entry["latestUpdateAt"] = ""
        entry["latestUpdateLocal"] = ""
        entry["latestUpdateSource"] = ""
        entry["latestUpdateUrl"] = ""
        return

    update = max(matches, key=lambda item: item["dt"])
    dt = update["dt"]
    entry["_latestUpdateSort"] = dt.timestamp()
    entry["latestUpdateAt"] = dt.isoformat()
    entry["latestUpdateLocal"] = local_time_label(dt)
    entry["latestUpdateSource"] = str(update.get("source") or "")
    entry["latestUpdateUrl"] = str(update.get("url") or "")


def link_bundle(row: dict[str, str]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for field, label in LINK_FIELDS:
        url = clean(row.get(field))
        if is_public_url(url) and url not in seen:
            links.append({"label": label, "url": url})
            seen.add(url)

    opentix_query = clean(row.get("opentix_query"))
    if is_public_url(opentix_query) and opentix_query not in seen:
        links.append({"label": "OPENTIX", "url": opentix_query})

    return links


def public_status(source_status: str) -> str:
    if "已查核" in source_status and "部分" not in source_status:
        return "已查核"
    if "部分" in source_status:
        return "部分查核"
    if "待查" in source_status or "未確認" in source_status:
        return "待確認"
    return "待確認"


def category_for(row: dict[str, str], source: str) -> str:
    raw_type = clean(row.get("type"))
    raw_region = clean(row.get("region"))
    text = " ".join(
        clean(row.get(field))
        for field in ("type", "role", "focus", "school_or_org", "region")
    )
    if source == "club" or "學校" in text or "學生" in text:
        return "學校社團"
    if "活動" in raw_type or "售票" in raw_type or "音樂節" in text or "比賽" in raw_type:
        return "活動資訊"
    if "個人" in raw_type:
        return "演奏者"
    if "團體" in raw_type or "樂團" in raw_type:
        return "團體樂團"
    if "教學" in text or "樂器" in text or "工作室" in text or "品牌" in text:
        return "教學器材"
    if "場館" in text or "文化局" in text or "平台" in text:
        return "場館平台"
    if raw_region and "台灣" not in raw_region:
        return "國際交流"
    return "其他來源"


def entry_from_row(row: dict[str, str], source: str, row_number: int) -> dict[str, object] | None:
    links = link_bundle(row)
    if not links:
        return None

    name = clean(row.get("name"))
    if not name:
        return None

    source_status = clean(row.get("source_status"))
    city_or_focus = clean(row.get("city")) or clean(row.get("focus"))
    public_summary_parts = [
        clean(row.get("school_or_org")),
        clean(row.get("focus")),
        clean(row.get("instruments")),
        clean(row.get("role")),
    ]
    summary = " / ".join(part for part in public_summary_parts if part)

    return {
        "id": f"{source}-{row_number}",
        "name": name,
        "nameEn": clean(row.get("name_en")),
        "category": category_for(row, source),
        "type": clean(row.get("type")),
        "country": clean(row.get("country")),
        "region": clean(row.get("region")),
        "cityOrFocus": city_or_focus,
        "summary": summary,
        "status": public_status(source_status),
        "sourceStatus": source_status,
        "keywords": clean(row.get("keywords")),
        "links": links,
        "source": source,
    }


def validate_public_entries(entries: list[dict[str, object]]) -> None:
    errors: list[str] = []
    for entry in entries:
        name = str(entry.get("name") or entry.get("id") or "未命名來源")
        if not clean(str(entry.get("country") or "")):
            errors.append(f"{name}: missing country")
        for tag in entry.get("sourceTags") or []:
            text = str(tag or "").strip()
            if not text:
                continue
            if TAG_FORBIDDEN_CHARS_RE.search(text) or re.search(r"\band\b", text, re.IGNORECASE):
                errors.append(f"{name}: composite sourceTag {text!r}")
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors[:40])
        if len(errors) > 40:
            formatted += f"\n- ... and {len(errors) - 40} more"
        raise SystemExit("Invalid public source entries:\n" + formatted)


def build_entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for source, path in SOURCE_FILES:
        for row_number, row in enumerate(read_csv(path), start=2):
            entry = entry_from_row(row, source, row_number)
            if entry:
                entries.append(entry)

    merged_entries = merge_duplicate_entries(entries)

    latest = latest_updates_by_key()
    avatars = avatar_profiles_by_key()
    tag_cache = source_tag_cache()
    for entry in merged_entries:
        apply_latest_update(entry, latest)
        apply_avatar(entry, avatars)
        apply_source_tags(entry, tag_cache)

    sorted_entries = sorted(
        merged_entries,
        key=lambda item: (
            -float(item.get("_latestUpdateSort") or 0),
            str(item.get("category", "")),
            str(item.get("name", "")),
        ),
    )
    for entry in sorted_entries:
        entry.pop("_latestUpdateSort", None)
    validate_public_entries(sorted_entries)
    return sorted_entries


def count_by(entries: list[dict[str, object]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry.get(field) or "未分類")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def social_source_stats() -> dict[str, object]:
    config = read_json(SOCIAL_SOURCES, {"sources": []})
    sources = [
        source
        for source in config.get("sources", [])
        if source.get("enabled", True) and source.get("type") != "jsonl"
    ]
    platforms: dict[str, int] = {}
    types: dict[str, int] = {}
    for source in sources:
        platform = str(source.get("platform") or source.get("type") or "unknown")
        source_type = str(source.get("type") or "unknown")
        platforms[platform] = platforms.get(platform, 0) + 1
        types[source_type] = types.get(source_type, 0) + 1

    rsshub_sources = [
        source
        for source in sources
        if str(source.get("type") or "").startswith("rsshub_") or bool(source.get("rsshub_base"))
    ]
    facebook_sources = sum(1 for source in sources if source.get("type") == "facebook_page_posts")
    return {
        "totalSources": len(sources),
        "rsshubSources": len(rsshub_sources),
        "apifySources": facebook_sources,
        "facebookSources": facebook_sources,
        "youtubeSources": sum(1 for source in sources if source.get("type") == "youtube_ytdlp"),
        "platforms": dict(sorted(platforms.items(), key=lambda item: item[0])),
        "types": dict(sorted(types.items(), key=lambda item: item[0])),
    }


def main() -> None:
    entries = build_entries()
    payload = {
        "generatedAt": date.today().isoformat(),
        "entries": entries,
        "stats": {
            "totalEntries": len(entries),
            "verifiedEntries": sum(1 for entry in entries if entry.get("status") == "已查核"),
            "categories": count_by(entries, "category"),
            "countries": count_by(entries, "country"),
            "statuses": count_by(entries, "status"),
            "watchSources": social_source_stats(),
        },
    }

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    DATA_OUT.write_text(
        "window.HARMONICA_OBSERVE_DATA = " + data + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {DATA_OUT.relative_to(PROJECT_ROOT)} with {len(entries)} public entries")


if __name__ == "__main__":
    main()
