#!/usr/bin/env python3
"""Build the public data bundle for harmonica.observe.tw."""

from __future__ import annotations

import csv
import email.utils
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
TAIPEI_TZ = timezone(timedelta(hours=8))

SOURCE_FILES = [
    ("watchlist", PROJECT_ROOT / "data" / "sources" / "harmonica-source-watchlist-public.csv"),
    ("club", PROJECT_ROOT / "data" / "sources" / "harmonica-clubs-public.csv"),
]

LINK_FIELDS = [
    ("website_url", "網站"),
    ("fb_url", "Facebook"),
    ("ig_url", "Instagram"),
    ("youtube_url", "YouTube"),
    ("contact_public_url", "公開聯絡"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def clean(value: str | None) -> str:
    return (value or "").strip()


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
    if "instagram.com" in host:
        if first not in {"p", "reel", "reels", "tv", "stories"}:
            handles.add(first)
    elif "facebook.com" in host:
        if first not in {"people", "pages", "profile.php"}:
            handles.add(first)
    elif "youtube.com" in host and first.startswith("@"):
        handles.add(first)
    elif "youtube.com" in host and first not in {"channel", "c", "user"}:
        handles.add(first)
    return {normalize_key(handle) for handle in handles if handle}


def entry_match_keys(entry: dict[str, object]) -> set[str]:
    keys = {
        normalize_key(str(entry.get("name") or "")),
        normalize_key(str(entry.get("nameEn") or "")),
    }
    keywords = str(entry.get("keywords") or "")
    if keywords:
        keys.add(normalize_key(keywords))
    for link in entry.get("links", []):
        if isinstance(link, dict):
            keys.update(url_handles(str(link.get("url") or "")))
    return {key for key in keys if key}


def candidate_match_keys(row: dict[str, Any]) -> set[str]:
    keys = {
        normalize_key(str(row.get("source_name") or "")),
        normalize_key(str(row.get("account") or "")),
    }
    source_id = str(row.get("source_id") or "")
    for prefix in ("ig_", "fb_", "yt_", "youtube_"):
        if source_id.startswith(prefix):
            keys.add(normalize_key(source_id[len(prefix) :]))
    if row.get("url"):
        keys.update(url_handles(str(row.get("url"))))
    return {key for key in keys if key}


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


def latest_updates_by_key() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in read_candidates():
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
        "tier": clean(row.get("tier")),
        "region": clean(row.get("region")),
        "cityOrFocus": city_or_focus,
        "summary": summary,
        "status": public_status(source_status),
        "sourceStatus": source_status,
        "keywords": clean(row.get("keywords")),
        "links": links,
        "source": source,
    }


def build_entries() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for source, path in SOURCE_FILES:
        for row_number, row in enumerate(read_csv(path), start=2):
            entry = entry_from_row(row, source, row_number)
            if entry:
                entries.append(entry)

    best_by_name: dict[str, dict[str, object]] = {}
    for entry in entries:
        key = str(entry["name"]).casefold().replace(" ", "")
        existing = best_by_name.get(key)
        if not existing:
            best_by_name[key] = entry
            continue
        existing_links = existing.get("links", [])
        new_links = entry.get("links", [])
        existing_score = len(existing_links) + (2 if existing.get("status") == "已查核" else 0)
        new_score = len(new_links) + (2 if entry.get("status") == "已查核" else 0)
        if new_score > existing_score:
            best_by_name[key] = entry

    latest = latest_updates_by_key()
    for entry in best_by_name.values():
        apply_latest_update(entry, latest)

    sorted_entries = sorted(
        best_by_name.values(),
        key=lambda item: (
            -float(item.get("_latestUpdateSort") or 0),
            str(item.get("category", "")),
            str(item.get("tier", "Z") or "Z"),
            str(item.get("name", "")),
        ),
    )
    for entry in sorted_entries:
        entry.pop("_latestUpdateSort", None)
    return sorted_entries


def count_by(entries: list[dict[str, object]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry.get(field) or "未分類")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def main() -> None:
    entries = build_entries()
    payload = {
        "generatedAt": date.today().isoformat(),
        "entries": entries,
        "stats": {
            "totalEntries": len(entries),
            "verifiedEntries": sum(1 for entry in entries if entry.get("status") == "已查核"),
            "categories": count_by(entries, "category"),
            "statuses": count_by(entries, "status"),
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
