#!/usr/bin/env python3
"""Backfill one public source-page row for uncovered directory/social sources."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import build_public_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOCIAL_SOURCES = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
INBOX = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"
CANDIDATES = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
UNKNOWN_DATE = "1970-01-01T00:00:00+00:00"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def row_key(row: dict[str, Any]) -> str:
    return f"{row.get('source_id')}:{row.get('post_id') or row.get('url') or row.get('key')}"


def existing_keys(rows: list[dict[str, Any]]) -> set[str]:
    return {row_key(row) for row in rows if row.get("source_id")}


def row_source_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("source_id")) for row in rows if row.get("source_id")}


def request_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:@")
    query = urllib.parse.quote(urllib.parse.unquote(parsed.query), safe="=&?/:@,+%")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))


def compact(value: str, limit: int = 1200) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (value or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()[:limit]


def html_meta(text: str, property_name: str) -> str:
    patterns = [
        rf'<meta\s+property=["\']{re.escape(property_name)}["\']\s+content=["\']([^"\']+)["\']',
        rf'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']{re.escape(property_name)}["\']',
        rf'<meta\s+name=["\']{re.escape(property_name)}["\']\s+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def html_title(text: str) -> str:
    match = re.search(r"<title\b[^>]*>(.*?)</title>", text or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return compact(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))), 240)


def fetch_page_metadata(url: str, timeout: int) -> dict[str, str]:
    metadata = {"title": "", "description": "", "image_url": "", "published_at": ""}
    try:
        req = urllib.request.Request(
            request_url(url),
            headers={"User-Agent": "Mozilla/5.0 HarmonicaObserveSourceBackfill/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return metadata
            text = response.read(1_500_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
        return metadata

    metadata["title"] = compact(html_meta(text, "og:title") or html_title(text), 240)
    metadata["description"] = compact(
        html_meta(text, "og:description") or html_meta(text, "description"),
        900,
    )
    metadata["image_url"] = html_meta(text, "og:image")
    metadata["published_at"] = (
        html_meta(text, "article:published_time")
        or html_meta(text, "datePublished")
        or html_meta(text, "pubdate")
    )
    return metadata


def platform_for_url(url: str, fallback: str = "web") -> str:
    host = urllib.parse.urlparse(url).netloc.casefold()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "facebook.com" in host or "fb.com" in host:
        return "facebook"
    if "instagram.com" in host:
        return "instagram"
    if "x.com" in host or "twitter.com" in host:
        return "x"
    if "threads.net" in host:
        return "threads"
    if "tiktok.com" in host:
        return "tiktok"
    if "opentix.life" in host:
        return "opentix"
    return fallback


def source_public_url(source: dict[str, Any]) -> str:
    source_type = str(source.get("type") or "")
    for field in ("profile_url", "source_profile_url"):
        if source.get(field):
            return str(source[field])
    if source.get("url"):
        return str(source["url"])
    if source_type == "rsshub_instagram_profile" and source.get("username"):
        username = str(source["username"]).strip().strip("/")
        return f"https://www.instagram.com/{username}/"
    if source_type == "facebook_page_posts":
        page = str(source.get("page") or source.get("username") or "").strip().strip("/")
        if page:
            return f"https://www.facebook.com/{page}/"
    return ""


def best_entry_link(entry: dict[str, Any]) -> dict[str, str] | None:
    links = [link for link in entry.get("links", []) if isinstance(link, dict) and link.get("url")]
    if not links:
        return None
    priority = {"OPENTIX": 0, "網站": 1, "公開聯絡": 2, "YouTube": 3, "Instagram": 4, "Facebook": 5}
    return sorted(links, key=lambda link: priority.get(str(link.get("label") or ""), 99))[0]


def source_page_row(
    *,
    source_id: str,
    source_name: str,
    url: str,
    platform: str,
    account: str,
    media_type: str,
    metadata: dict[str, str],
    seen_at: str,
) -> dict[str, Any]:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    title = metadata.get("title") or source_name
    description = metadata.get("description") or ""
    text = compact("\n".join(part for part in [title, description, f"公開來源頁：{url}"] if part), 1800)
    image_url = metadata.get("image_url") or ""
    return {
        "account": account or url,
        "image_url": image_url,
        "images": [image_url] if image_url else [],
        "include_without_keywords": True,
        "key": f"{source_id}:source_page:{digest}",
        "matched_keywords": [],
        "media_type": media_type,
        "platform": platform,
        "post_id": f"source_page:{digest}",
        "posted_at": metadata.get("published_at") or UNKNOWN_DATE,
        "raw_source": "public-link-backfill",
        "seen_at": seen_at,
        "source_avatar_url": "",
        "source_id": source_id,
        "source_name": source_name,
        "text": text,
        "url": url,
    }


def candidate_keys_for_row(row: dict[str, Any]) -> set[str]:
    return build_public_data.candidate_match_keys(row)


def entry_has_row(entry: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    entry_keys = build_public_data.entry_match_keys(entry)
    return any(entry_keys & candidate_keys_for_row(row) for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-secs", type=int, default=8)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    source_config = read_json(SOCIAL_SOURCES, {"sources": []})
    existing_rows = read_jsonl(INBOX) + read_jsonl(CANDIDATES)
    existing_row_keys = existing_keys(existing_rows)
    covered_source_ids = row_source_ids(existing_rows)

    new_rows: list[dict[str, Any]] = []
    source_backfills = 0
    directory_backfills = 0

    for source in source_config.get("sources", []):
        if not source.get("enabled", True) or source.get("type") == "jsonl" or source.get("ephemeral"):
            continue
        source_id = str(source.get("id") or "")
        if not source_id or source_id in covered_source_ids:
            continue
        url = source_public_url(source)
        if not url:
            continue
        metadata = {} if args.skip_fetch else fetch_page_metadata(url, args.timeout_secs)
        row = source_page_row(
            source_id=source_id,
            source_name=str(source.get("name") or source_id),
            url=url,
            platform=str(source.get("platform") or platform_for_url(url)),
            account=str(source.get("username") or source.get("page") or source.get("url") or url),
            media_type="source_page",
            metadata=metadata,
            seen_at=now,
        )
        if row_key(row) not in existing_row_keys:
            new_rows.append(row)
            existing_row_keys.add(row_key(row))
            covered_source_ids.add(source_id)
            source_backfills += 1

    coverage_rows = existing_rows + new_rows
    for entry in build_public_data.build_entries():
        if entry_has_row(entry, coverage_rows):
            continue
        link = best_entry_link(entry)
        if not link:
            continue
        url = str(link["url"])
        source_id = "dir_" + re.sub(r"[^0-9a-z_]+", "_", str(entry["id"]).casefold()).strip("_")
        metadata = {} if args.skip_fetch else fetch_page_metadata(url, args.timeout_secs)
        row = source_page_row(
            source_id=source_id,
            source_name=str(entry["name"]),
            url=url,
            platform=platform_for_url(url),
            account=url,
            media_type="directory_source_page",
            metadata=metadata,
            seen_at=now,
        )
        if row_key(row) not in existing_row_keys:
            new_rows.append(row)
            existing_row_keys.add(row_key(row))
            coverage_rows.append(row)
            directory_backfills += 1

    if not args.no_write:
        append_jsonl(INBOX, new_rows)
        append_jsonl(CANDIDATES, new_rows)

    print(
        json.dumps(
            {
                "written": not args.no_write,
                "new_rows": len(new_rows),
                "source_backfills": source_backfills,
                "directory_backfills": directory_backfills,
                "inbox": str(INBOX),
                "candidates": str(CANDIDATES),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
