#!/usr/bin/env python3
"""Watch public harmonica social feeds and write standalone candidate rows."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(os.environ.get("HARMONICA_OBSERVE_HOME", Path(__file__).resolve().parents[1])).expanduser()
DEFAULT_CONFIG = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
DEFAULT_SEEN = PROJECT_ROOT / "state" / "social_seen.json"
DEFAULT_CANDIDATES = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
DEFAULT_ERRORS = PROJECT_ROOT / "data" / "feeds" / "social_feed_errors.jsonl"
DEFAULT_INBOX = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"

GRAPH_VERSION = os.environ.get("HARMONICA_META_API_VERSION", "v25.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
RSSHUB_BASE = os.environ.get("HARMONICA_RSSHUB_BASE", "").rstrip("/")
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
IMG_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def project_path(value: str | os.PathLike[str]) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def http_json(url: str, params: dict[str, Any], token: str | None) -> dict[str, Any]:
    query = dict(params)
    if token:
        query["access_token"] = token
    full_url = url + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(full_url, headers={"User-Agent": "HarmonicaInTaiwanSocialWatcher/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def strip_html(value: str) -> str:
    text = BR_RE.sub("\n", value or "")
    text = TAG_RE.sub(" ", text)
    lines = [re.sub(r"[ \t]+", " ", html.unescape(line)).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def image_urls(value: str) -> list[str]:
    urls: list[str] = []
    for raw in IMG_RE.findall(value or ""):
        url = html.unescape(raw)
        if url and url not in urls:
            urls.append(url)
    return urls


def text_of(element: ET.Element, name: str) -> str:
    child = element.find(name)
    return (child.text or "").strip() if child is not None else ""


def atom_text(element: ET.Element, name: str) -> str:
    child = element.find(f"{{http://www.w3.org/2005/Atom}}{name}")
    return (child.text or "").strip() if child is not None else ""


def url_part(value: Any) -> str:
    return urllib.parse.quote(str(value or ""), safe="")


def format_rsshub_route(route: str, source: dict[str, Any]) -> str:
    values = {
        "username": url_part(source.get("username") or ""),
        "page": url_part(source.get("page") or source.get("username") or ""),
        "id": url_part(source.get("account_id") or source.get("page") or source.get("username") or ""),
    }
    if not route.startswith("/"):
        route = "/" + route
    for key, value in values.items():
        route = route.replace("{" + key + "}", value)
    return route


def rsshub_url(source: dict[str, Any]) -> str:
    base = str(source.get("rsshub_base") or RSSHUB_BASE).rstrip("/")
    if not base:
        return ""

    route = source.get("route")
    if route:
        return base + format_rsshub_route(str(route), source)

    kind = source.get("type")
    if kind == "rsshub_facebook_page":
        page = source.get("page") or source.get("username")
        return f"{base}/facebook/page/{url_part(page)}" if page else ""

    if kind == "rsshub_instagram_profile":
        username = source.get("username")
        if not username:
            return ""
        provider = str(source.get("provider") or "picuki")
        if provider in {"cookie", "instagram_cookie"}:
            return f"{base}/instagram/2/user/{url_part(username)}"
        if provider == "picnob":
            return f"{base}/picnob/profile/{url_part(username)}"
        if provider in {"private_api", "instagram"}:
            return f"{base}/instagram/user/{url_part(username)}"
        return f"{base}/picuki/profile/{url_part(username)}"

    return ""


def compact_text(text: str, limit: int = 1600) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (text or "").splitlines()]
    clean_lines: list[str] = []
    for line in lines:
        if line and (not clean_lines or clean_lines[-1] != line):
            clean_lines.append(line)
    cleaned = "\n".join(clean_lines).strip()
    return cleaned[:limit]


def normalize_post(
    source: dict[str, Any],
    *,
    post_id: str,
    text: str,
    url: str,
    posted_at: str,
    media_type: str = "",
    images: list[str] | None = None,
    source_avatar_url: str = "",
) -> dict[str, Any]:
    source_id = source["id"]
    return {
        "key": f"{source_id}:{post_id or url}",
        "source_id": source_id,
        "source_name": source.get("name") or source_id,
        "platform": source.get("platform") or source.get("type"),
        "account": source.get("username") or source.get("page") or source.get("url") or "",
        "post_id": post_id,
        "posted_at": posted_at,
        "url": url,
        "media_type": media_type,
        "images": images or [],
        "image_url": (images or [""])[0],
        "source_avatar_url": source_avatar_url,
        "text": compact_text(text),
    }


def fetch_rss(source: dict[str, Any]) -> list[dict[str, Any]]:
    url = source.get("url") or rsshub_url(source)
    if not url:
        return []
    req = urllib.request.Request(url, headers={"User-Agent": "HarmonicaInTaiwanSocialWatcher/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        root = ET.fromstring(response.read())

    posts: list[dict[str, Any]] = []
    channel_avatar = root.findtext("channel/image/url") or ""
    for item in root.findall(".//item"):
        title = text_of(item, "title")
        link = text_of(item, "link")
        desc = text_of(item, "description")
        images = image_urls(desc)
        published = text_of(item, "pubDate")
        guid = text_of(item, "guid") or link or title
        posts.append(
            normalize_post(
                source,
                post_id=guid,
                text="\n".join(part for part in [title, strip_html(desc)] if part),
                url=link,
                posted_at=published,
                images=images,
                source_avatar_url=channel_avatar,
            )
        )

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    atom_avatar = atom_text(root, "logo") or atom_text(root, "icon")
    for entry in root.findall(".//atom:entry", ns):
        title = atom_text(entry, "title")
        content = atom_text(entry, "content") or atom_text(entry, "summary")
        images = image_urls(content)
        posted_at = atom_text(entry, "updated") or atom_text(entry, "published")
        link = ""
        for link_el in entry.findall("atom:link", ns):
            if link_el.attrib.get("href"):
                link = link_el.attrib["href"]
                break
        post_id = atom_text(entry, "id") or link or title
        posts.append(
            normalize_post(
                source,
                post_id=post_id,
                text="\n".join(part for part in [title, strip_html(content)] if part),
                url=link,
                posted_at=posted_at,
                images=images,
                source_avatar_url=atom_avatar,
            )
        )

    return posts


def normalize_external_post(source: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    source_id = str(row.get("source_id") or source["id"])
    source_name = row.get("source_name") or source.get("name") or source_id
    account = row.get("account") or row.get("username") or row.get("page") or source.get("username") or source.get("page") or ""
    url = row.get("url") or row.get("link") or row.get("permalink") or ""
    post_id = row.get("post_id") or row.get("id") or row.get("guid") or url
    text_parts = [
        row.get("text"),
        row.get("caption"),
        row.get("message"),
        row.get("title"),
        row.get("description"),
        row.get("body"),
    ]
    post = normalize_post(
        {
            "id": source_id,
            "name": source_name,
            "platform": row.get("platform") or source.get("platform") or "external",
            "username": account,
        },
        post_id=str(post_id or ""),
        text="\n".join(str(part) for part in text_parts if part),
        url=str(url or ""),
        posted_at=str(row.get("posted_at") or row.get("published_at") or row.get("created_time") or row.get("date") or ""),
        media_type=str(row.get("media_type") or ""),
        images=[
            str(url)
            for url in (
                row.get("images")
                or row.get("image_urls")
                or ([row.get("image_url")] if row.get("image_url") else [])
            )
            if url
        ],
        source_avatar_url=str(row.get("source_avatar_url") or row.get("avatar_url") or row.get("profile_image_url") or ""),
    )
    if row.get("raw_source"):
        post["raw_source"] = str(row["raw_source"])
    if row.get("include_without_keywords"):
        post["include_without_keywords"] = True
    return post


def fetch_jsonl(source: dict[str, Any]) -> list[dict[str, Any]]:
    path = project_path(source.get("path") or DEFAULT_INBOX)
    if not path.exists():
        return []
    posts: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc
            if isinstance(row, dict):
                posts.append(normalize_external_post(source, row))
    return posts


def fetch_facebook_page(source: dict[str, Any], token: str) -> list[dict[str, Any]]:
    page = source.get("page") or source.get("username")
    if not page:
        return []
    if str(page).startswith(("http://", "https://")):
        return []
    limit = int(source.get("limit") or 5)
    path = urllib.parse.quote(str(page), safe="")
    data = http_json(
        f"{GRAPH_BASE}/{path}/published_posts",
        {
            "limit": min(max(limit, 1), 25),
            "fields": "id,message,created_time,permalink_url,attachments{title,description,url}",
        },
        token,
    )
    posts: list[dict[str, Any]] = []
    for item in data.get("data", []):
        attachment_text = ""
        attachments = item.get("attachments", {}).get("data", [])
        if attachments:
            attachment_text = "\n".join(
                part
                for attachment in attachments
                for part in [attachment.get("title") or "", attachment.get("description") or ""]
                if part
            )
        posts.append(
            normalize_post(
                source,
                post_id=item.get("id") or item.get("permalink_url") or "",
                text="\n".join(part for part in [item.get("message") or "", attachment_text] if part),
                url=item.get("permalink_url") or "",
                posted_at=item.get("created_time") or "",
            )
        )
    return posts


def fetch_source(source: dict[str, Any], token: str | None) -> list[dict[str, Any]]:
    kind = source.get("type")
    if kind in {"rss", "rsshub_facebook_page", "rsshub_instagram_profile"}:
        return fetch_rss(source)
    if kind in {"jsonl", "external_jsonl", "n8n_jsonl"}:
        return fetch_jsonl(source)
    if kind == "facebook_page_posts":
        return fetch_facebook_page(source, token) if token else []
    return []


def should_throttle_source(source: dict[str, Any], token: str | None) -> bool:
    kind = source.get("type")
    if kind in {"rss", "rsshub_facebook_page", "rsshub_instagram_profile", "jsonl", "external_jsonl", "n8n_jsonl"}:
        return True
    if kind == "facebook_page_posts" and token:
        return True
    return False


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    haystack = (text or "").lower()
    return [keyword for keyword in keywords if keyword.lower() in haystack]


def parse_post_time(value: str) -> dt.datetime | None:
    if not value:
        return None
    raw = value.strip()
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def too_old(posted_at: str, max_age_days: int | None, now: dt.datetime) -> bool:
    if not max_age_days:
        return False
    posted = parse_post_time(posted_at)
    if posted is None:
        return False
    return posted < now - dt.timedelta(days=max_age_days)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_candidates(path: Path, posts: list[dict[str, Any]]) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    append_jsonl(path, [{**post, "seen_at": now} for post in posts])


def append_errors(path: Path, errors: list[dict[str, str]]) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    append_jsonl(path, [{**error, "seen_at": now} for error in errors])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seen", type=Path, default=DEFAULT_SEEN)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--errors", type=Path, default=DEFAULT_ERRORS)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--emit-initial", action="store_true")
    parser.add_argument("--include-all-new", action="store_true")
    parser.add_argument("--max-post-age-days", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = load_json(args.config, {"sources": [], "keywords": []})
    sources = [source for source in config.get("sources", []) if source.get("enabled", True)]
    keywords = config.get("keywords") or []
    token = os.environ.get("HARMONICA_META_ACCESS_TOKEN")

    if args.check:
        by_type: dict[str, int] = {}
        for source in sources:
            by_type[str(source.get("type") or "unknown")] = by_type.get(str(source.get("type") or "unknown"), 0) + 1
        print(
            json.dumps(
                {
                    "config": str(args.config),
                    "sources_enabled": len(sources),
                    "source_types": by_type,
                    "rsshub_sources": sum(1 for source in sources if str(source.get("type") or "").startswith("rsshub_")),
                    "jsonl_sources": sum(1 for source in sources if source.get("type") in {"jsonl", "external_jsonl", "n8n_jsonl"}),
                    "facebook_sources": sum(1 for source in sources if source.get("type") == "facebook_page_posts"),
                    "has_meta_token": bool(token),
                    "default_inbox": str(DEFAULT_INBOX),
                    "seen_file": str(args.seen),
                    "candidates_file": str(args.candidates),
                    "errors_file": str(args.errors),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    first_run = not args.seen.exists()
    seen = load_json(args.seen, {"seen": {}, "initialized_at": None})
    seen_map: dict[str, str] = dict(seen.get("seen") or {})
    new_posts: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    fetched_count = 0
    skipped_old = 0
    now_utc = dt.datetime.now(dt.timezone.utc)

    for source in sources:
        try:
            posts = fetch_source(source, token)
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, json.JSONDecodeError, ValueError) as exc:
            errors.append(
                {
                    "source_id": str(source.get("id") or ""),
                    "source_type": str(source.get("type") or ""),
                    "error": str(exc),
                }
            )
            continue
        fetched_count += len(posts)
        for post in posts:
            key = post.get("key")
            if not key or key in seen_map:
                continue
            matched = match_keywords(post.get("text", ""), keywords)
            post["matched_keywords"] = matched
            if too_old(post.get("posted_at", ""), args.max_post_age_days, now_utc):
                skipped_old += 1
                seen_map[key] = dt.datetime.now(dt.timezone.utc).isoformat()
                continue
            if not args.baseline and (args.include_all_new or matched or post.get("include_without_keywords")):
                new_posts.append(post)
            seen_map[key] = dt.datetime.now(dt.timezone.utc).isoformat()
        if should_throttle_source(source, token):
            time.sleep(0.25)

    seen["seen"] = seen_map
    seen.setdefault("initialized_at", dt.datetime.now(dt.timezone.utc).isoformat())
    seen["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    save_json(args.seen, seen)

    if args.baseline:
        append_errors(args.errors, errors)
        if args.verbose:
            print(json.dumps({"baseline": True, "fetched_posts": fetched_count, "skipped_old_posts": skipped_old, "errors": errors}, ensure_ascii=False, indent=2))
        return 0

    if first_run and not args.emit_initial:
        append_errors(args.errors, errors)
        if args.verbose:
            print(json.dumps({"baseline": True, "fetched_posts": fetched_count, "skipped_old_posts": skipped_old, "errors": errors}, ensure_ascii=False, indent=2))
        return 0

    append_candidates(args.candidates, new_posts)
    append_errors(args.errors, errors)

    if new_posts or args.verbose:
        print(
            json.dumps(
                {
                    "new_relevant_posts": new_posts,
                    "skipped_old_posts": skipped_old,
                    "errors": errors if args.verbose else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
