#!/usr/bin/env python3
"""Watch public harmonica social feeds and write standalone candidate rows."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import signal
import subprocess
import tempfile
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
DEFAULT_LLM_CACHE = PROJECT_ROOT / "state" / "social_llm_tags.json"

GRAPH_VERSION = os.environ.get("HARMONICA_META_API_VERSION", "v25.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
RSSHUB_BASE = os.environ.get("HARMONICA_RSSHUB_BASE", "").rstrip("/")
TAG_RE = re.compile(r"<[^>]+>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
IMG_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
VIDEO_POSTER_RE = re.compile(r"<video\b[^>]*\bposter=[\"']([^\"']+)[\"']", re.IGNORECASE)
VIDEO_SRC_RE = re.compile(r"<video\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
SOURCE_SRC_RE = re.compile(r"<source\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
TAG_VALUE_SPLIT_RE = re.compile(r"\s*(?:[,，、/／+&]|\band\b|\s+)\s*", re.IGNORECASE)
RSSHUB_ERROR_MESSAGE_RE = re.compile(r"Error Message:\s*<br\s*/?>\s*<code[^>]*>(.*?)</code>", re.IGNORECASE | re.DOTALL)
STORY_EMPTY_ERROR_PATTERNS = (
    "content does not exist",
    "user has no stories",
    "this route is empty",
    "profile is private",
)
OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_LLM_MODEL = "mimo-v2.5"
LLM_CATEGORIES = {"events", "posts-videos", "student-clubs", "opportunities"}
LLM_LABELS = {
    "口琴",
    "演出",
    "音樂會",
    "成發",
    "課程",
    "招生",
    "社博",
    "迎新",
    "交流",
    "比賽",
    "補助",
    "影片",
    "公開更新",
    "學生社團",
}
TRUTHY = {"1", "true", "yes", "y", "on"}


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


def rsshub_error_message(body: bytes) -> str:
    text = body.decode("utf-8", "replace")
    match = RSSHUB_ERROR_MESSAGE_RE.search(text)
    if match:
        text = match.group(1)
    return compact_text(strip_html(text), 500)


def is_story_empty_error(message: str) -> bool:
    lowered = (message or "").casefold()
    return any(pattern in lowered for pattern in STORY_EMPTY_ERROR_PATTERNS)


def image_urls(value: str) -> list[str]:
    urls: list[str] = []
    for raw in [*IMG_RE.findall(value or ""), *VIDEO_POSTER_RE.findall(value or "")]:
        url = html.unescape(raw)
        if url and url not in urls:
            urls.append(url)
    return urls


def video_urls(value: str) -> list[str]:
    urls: list[str] = []
    for raw in [*VIDEO_SRC_RE.findall(value or ""), *SOURCE_SRC_RE.findall(value or "")]:
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


def is_story_source(source: dict[str, Any]) -> bool:
    return str(source.get("type") or "") == "rsshub_instagram_story" or str(source.get("media_type") or "") == "instagram_story"


def normalize_post(
    source: dict[str, Any],
    *,
    post_id: str,
    text: str,
    url: str,
    posted_at: str,
    media_type: str = "",
    images: list[str] | None = None,
    videos: list[str] | None = None,
    source_avatar_url: str = "",
    source_feed_url: str = "",
    rsshub_guid: str = "",
    rsshub_title: str = "",
    story_fetched_at: str = "",
) -> dict[str, Any]:
    source_id = source["id"]
    account = source.get("username") or source.get("page") or source.get("url") or ""
    story_source = is_story_source(source)
    normalized_text = compact_text(text)
    if story_source and not normalized_text:
        normalized_text = f"Instagram story @{account}" if account else "Instagram story"
    post = {
        "key": f"{source_id}:{post_id or url}",
        "source_id": source_id,
        "source_name": source.get("name") or source_id,
        "platform": source.get("platform") or source.get("type"),
        "account": account,
        "post_id": post_id,
        "posted_at": posted_at,
        "url": url,
        "source_profile_url": source.get("profile_url") or source.get("source_profile_url") or "",
        "media_type": media_type or source.get("media_type") or "",
        "images": images or [],
        "image_url": (images or [""])[0],
        "videos": videos or [],
        "source_avatar_url": source_avatar_url,
        "text": normalized_text,
    }
    if source.get("include_without_keywords"):
        post["include_without_keywords"] = True
    if source.get("ephemeral"):
        post["ephemeral"] = True
    if source_feed_url:
        post["source_feed_url"] = source_feed_url
    if story_source:
        post.update(
            {
                "include_without_keywords": True,
                "media_type": "instagram_story",
                "story": True,
                "story_provider": source.get("story_provider") or "rsshub_picuki",
                "story_fetched_at": story_fetched_at,
                "source_feed_url": source_feed_url,
                "rsshub_guid": rsshub_guid,
                "rsshub_title": rsshub_title,
            }
        )
    return post


def fetch_rss(source: dict[str, Any]) -> list[dict[str, Any]]:
    url = source.get("url") or rsshub_url(source)
    if not url:
        return []
    req = urllib.request.Request(url, headers={"User-Agent": "HarmonicaInTaiwanSocialWatcher/1.0"})
    story_source = is_story_source(source)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            root = ET.fromstring(response.read())
    except urllib.error.HTTPError as exc:
        message = rsshub_error_message(exc.read())
        if story_source and exc.code in {404, 503} and is_story_empty_error(message):
            return []
        if message:
            raise ValueError(f"RSSHub HTTP {exc.code}: {message}") from exc
        raise

    posts: list[dict[str, Any]] = []
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    channel_avatar = root.findtext("channel/image/url") or ""
    for item in root.findall(".//item"):
        title = text_of(item, "title")
        link = text_of(item, "link")
        desc = text_of(item, "description")
        images = image_urls(desc)
        videos = video_urls(desc)
        published = text_of(item, "pubDate") or (fetched_at if story_source else "")
        guid = text_of(item, "guid") or link or title
        post_id = guid or (images + videos + [fetched_at])[0]
        posts.append(
            normalize_post(
                source,
                post_id=post_id,
                text="\n".join(part for part in [title, strip_html(desc)] if part),
                url=link,
                posted_at=published,
                images=images,
                videos=videos,
                source_avatar_url=channel_avatar,
                source_feed_url=url,
                rsshub_guid=guid,
                rsshub_title=title,
                story_fetched_at=fetched_at if story_source else "",
            )
        )

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    atom_avatar = atom_text(root, "logo") or atom_text(root, "icon")
    for entry in root.findall(".//atom:entry", ns):
        title = atom_text(entry, "title")
        content = atom_text(entry, "content") or atom_text(entry, "summary")
        images = image_urls(content)
        videos = video_urls(content)
        posted_at = atom_text(entry, "updated") or atom_text(entry, "published") or (fetched_at if story_source else "")
        link = ""
        for link_el in entry.findall("atom:link", ns):
            if link_el.attrib.get("href"):
                link = link_el.attrib["href"]
                break
        post_id = atom_text(entry, "id") or link or title
        if not post_id:
            post_id = (images + videos + [fetched_at])[0]
        posts.append(
            normalize_post(
                source,
                post_id=post_id,
                text="\n".join(part for part in [title, strip_html(content)] if part),
                url=link,
                posted_at=posted_at,
                images=images,
                videos=videos,
                source_avatar_url=atom_avatar,
                source_feed_url=url,
                rsshub_guid=post_id,
                rsshub_title=title,
                story_fetched_at=fetched_at if story_source else "",
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
        videos=[str(url) for url in (row.get("videos") or row.get("video_urls") or []) if url],
        source_avatar_url=str(row.get("source_avatar_url") or row.get("avatar_url") or row.get("profile_image_url") or ""),
    )
    for field in (
        "source_display_name",
        "source_profile_url",
        "profile_name",
        "page_name",
        "raw_source",
        "source_feed_url",
        "story_provider",
        "story_fetched_at",
        "rsshub_guid",
        "rsshub_title",
    ):
        if row.get(field):
            post[field] = row[field]
    if row.get("story"):
        post["story"] = True
    if row.get("ephemeral"):
        post["ephemeral"] = True
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
    if kind in {"rss", "rsshub_facebook_page", "rsshub_instagram_profile", "rsshub_instagram_story", "rsshub_twitter_user", "rsshub_threads_user"}:
        return fetch_rss(source)
    if kind in {"jsonl", "external_jsonl", "n8n_jsonl"}:
        return fetch_jsonl(source)
    if kind == "facebook_page_posts":
        return fetch_facebook_page(source, token) if token else []
    return []


def should_throttle_source(source: dict[str, Any], token: str | None) -> bool:
    kind = source.get("type")
    if kind in {"rss", "rsshub_facebook_page", "rsshub_instagram_profile", "rsshub_instagram_story", "rsshub_twitter_user", "rsshub_threads_user", "jsonl", "external_jsonl", "n8n_jsonl"}:
        return True
    if kind == "facebook_page_posts" and token:
        return True
    return False


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    haystack = (text or "").lower()
    return [keyword for keyword in keywords if keyword.lower() in haystack]


def env_truthy(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in TRUTHY


def unique_limited(values: list[Any], *, allowed: set[str] | None = None, limit: int = 8) -> list[str]:
    items: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        if allowed is not None and item not in allowed:
            continue
        if item not in items:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def split_tag_values(value: Any, *, limit: int = 8) -> list[str]:
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


def normalize_category(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    aliases = {
        "event": "events",
        "events": "events",
        "活動": "events",
        "實體活動": "events",
        "post": "posts-videos",
        "posts": "posts-videos",
        "video": "posts-videos",
        "videos": "posts-videos",
        "posts-videos": "posts-videos",
        "貼文": "posts-videos",
        "影片": "posts-videos",
        "student": "student-clubs",
        "student-clubs": "student-clubs",
        "club": "student-clubs",
        "學生社團": "student-clubs",
        "opportunity": "opportunities",
        "opportunities": "opportunities",
        "補助": "opportunities",
        "比賽": "opportunities",
    }
    return aliases.get(raw, raw)


def normalize_label(value: Any) -> str:
    raw = str(value or "").strip()
    aliases = {
        "活動": "演出",
        "實體活動": "演出",
        "concert": "音樂會",
        "event": "演出",
        "lesson": "課程",
        "workshop": "課程",
        "course": "課程",
        "competition": "比賽",
        "grant": "補助",
        "funding": "補助",
        "video": "影片",
        "student club": "學生社團",
    }
    return aliases.get(raw.casefold(), raw)


def normalize_label_values(value: Any, *, limit: int = 8) -> list[str]:
    if isinstance(value, str):
        raw_values: list[Any] = [value]
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = []

    labels: list[str] = []
    for raw in raw_values:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = normalize_label(text)
        candidates = [normalized] if normalized in LLM_LABELS else [normalize_label(tag) for tag in split_tag_values(text)]
        for label in candidates:
            if label in LLM_LABELS and label not in labels:
                labels.append(label)
            if len(labels) >= limit:
                return labels
    return labels


def normalize_llm_result(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    relevant_value = data.get("is_relevant", data.get("relevant", False))
    if isinstance(relevant_value, bool):
        relevant = relevant_value
    else:
        relevant = str(relevant_value or "").strip().casefold() in TRUTHY

    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence > 1 and confidence <= 100:
        confidence = confidence / 100
    confidence = max(0.0, min(confidence, 1.0))

    raw_labels = data.get("labels") or data.get("tags") or []
    labels = unique_limited(
        normalize_label_values(raw_labels),
        allowed=LLM_LABELS,
        limit=8,
    )

    raw_categories = data.get("categories") or data.get("category_ids") or []
    if isinstance(raw_categories, str):
        raw_categories = re.split(r"[,，、\s]+", raw_categories)
    categories = unique_limited(
        [normalize_category(category) for category in raw_categories if str(category or "").strip()],
        allowed=LLM_CATEGORIES,
        limit=4,
    )
    if relevant and not categories:
        categories = ["posts-videos"]
    if not relevant:
        categories = []
        labels = []

    reason = compact_text(str(data.get("reason") or data.get("summary") or ""), 160)
    return {
        "llm_relevant": relevant,
        "llm_confidence": round(confidence, 3),
        "llm_labels": labels,
        "llm_categories": categories,
        "llm_reason": reason,
    }


def merge_tags(primary: list[Any], fallback: list[Any], *, limit: int = 8) -> list[str]:
    return unique_limited(split_tag_values([*primary, *fallback], limit=limit), limit=limit)


def read_llm_token(service: str, account: str) -> tuple[str, str]:
    for key in ("HARMONICA_OPENCODE_GO_API_KEY", "OPENCODE_GO_API_KEY", "HARMONICA_LLM_API_KEY"):
        value = os.environ.get(key)
        if value:
            return value.strip(), f"env:{key}"

    candidates = [
        (service, account),
        (service, "harmonica"),
        ("harmonica-opencode-go", "harmonica"),
    ]
    seen_pairs: set[tuple[str, str]] = set()
    for keychain_service, keychain_account in candidates:
        if not keychain_service or not keychain_account or (keychain_service, keychain_account) in seen_pairs:
            continue
        seen_pairs.add((keychain_service, keychain_account))
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", keychain_service, "-a", keychain_account, "-w"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), f"keychain:{keychain_service}/{keychain_account}"
    return "", ""


def llm_endpoint(base_url: str) -> str:
    base = (base_url or OPENCODE_GO_BASE_URL).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


class RequestDeadline:
    def __init__(self, seconds: int) -> None:
        self.seconds = max(1, int(seconds or 1))
        self.previous_handler: Any = None

    def __enter__(self) -> None:
        if not hasattr(signal, "SIGALRM"):
            return
        self.previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self.raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not hasattr(signal, "SIGALRM"):
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.previous_handler)

    def raise_timeout(self, signum: int, frame: Any) -> None:
        raise TimeoutError(f"LLM request timed out after {self.seconds}s")


def post_fingerprint(post: dict[str, Any]) -> str:
    payload = {
        "key": post.get("key") or "",
        "source_id": post.get("source_id") or "",
        "source_name": post.get("source_name") or "",
        "posted_at": post.get("posted_at") or "",
        "url": post.get("url") or "",
        "text": post.get("text") or "",
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_json_object(text: str) -> dict[str, Any]:
    body = (text or "").strip()
    if body.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*", "", body, flags=re.IGNORECASE)
        body = re.sub(r"\s*```$", "", body).strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        start = body.find("{")
        end = body.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(body[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response was not a JSON object")
    return parsed


def chat_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("LLM response did not include choices")
    message = choices[0].get("message") or {}
    content = message.get("content") or choices[0].get("text") or ""
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            else:
                parts.append(str(part))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def curl_json(url: str, token: str, body: dict[str, Any], timeout: int) -> str:
    body_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(body, handle, ensure_ascii=False)
            body_path = handle.name

        config = "\n".join(
            [
                f'url = "{url}"',
                'request = "POST"',
                f"max-time = {max(1, int(timeout or 1))}",
                "silent",
                "show-error",
                "fail-with-body",
                f'header = "Authorization: Bearer {token}"',
                'header = "Content-Type: application/json"',
                'header = "Accept: application/json"',
                'header = "User-Agent: HarmonicaObserveLLMTagger/1.0"',
                f'data-binary = "@{body_path}"',
                "",
            ]
        )
        result = subprocess.run(
            ["curl", "--config", "-"],
            input=config,
            capture_output=True,
            text=True,
            timeout=max(2, int(timeout or 1) + 5),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"LLM curl timed out after {timeout}s") from exc
    finally:
        if body_path:
            try:
                Path(body_path).unlink()
            except OSError:
                pass

    if result.returncode != 0:
        detail = (result.stdout or result.stderr or "").strip()[:500]
        raise RuntimeError(f"LLM curl exited {result.returncode}: {detail}")
    return result.stdout


def llm_prompt(post: dict[str, Any], keyword_matches: list[str]) -> list[dict[str, str]]:
    source = post.get("source_name") or post.get("source_id") or "公開來源"
    user_payload = {
        "source": source,
        "source_id": post.get("source_id") or "",
        "platform": post.get("platform") or "",
        "account": post.get("account") or "",
        "posted_at": post.get("posted_at") or "",
        "url": post.get("url") or "",
        "keyword_matches": keyword_matches,
        "text": compact_text(str(post.get("text") or ""), 1800),
    }
    return [
        {
            "role": "system",
            "content": (
                "你是臺灣口琴觀測站的社群貼文分類器。"
                "只根據公開貼文文字、來源與 URL 判斷。只回傳 JSON，不要 Markdown。"
            ),
        },
        {
            "role": "user",
            "content": (
                "判斷這篇公開貼文是否值得收進臺灣口琴公開更新。"
                "只要是口琴演出、音樂會、成發、課程、招生、社博、迎新、交流、"
                "比賽、補助、指定曲、口琴影片、口琴社團或口琴演奏者公開更新，就算相關。"
                "如果只是一般音樂、班多鈕/手風琴、一般藝文活動，或來源名稱含 harmonica 但貼文內容無關，請標成不相關。"
                "categories 只能使用 events, posts-videos, student-clubs, opportunities；"
                "相關但無更精準分類時用 posts-videos。labels 只能使用："
                "口琴, 演出, 音樂會, 成發, 課程, 招生, 社博, 迎新, 交流, 比賽, 補助, 影片, 公開更新, 學生社團。"
                "回傳格式："
                '{"is_relevant":true,"confidence":0.0,"labels":[],"categories":[],"reason":"80字內理由"}'
                "\n\n貼文資料：\n"
                + json.dumps(user_payload, ensure_ascii=False, indent=2)
            ),
        },
    ]


def classify_with_llm(
    post: dict[str, Any],
    keyword_matches: list[str],
    *,
    token: str,
    base_url: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": llm_prompt(post, keyword_matches),
        "temperature": 0,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    response_body = curl_json(llm_endpoint(base_url), token, body, timeout)
    try:
        response_json = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not JSON: {response_body[:300]!r}") from exc
    response_text = chat_response_text(response_json)
    try:
        parsed = extract_json_object(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM message content was not JSON: {response_text[:300]!r}") from exc
    normalized = normalize_llm_result(parsed)
    return {
        **normalized,
        "llm_model": model,
        "llm_tagged_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def cached_llm_classification(
    post: dict[str, Any],
    keyword_matches: list[str],
    *,
    cache: dict[str, Any],
    token: str,
    base_url: str,
    model: str,
    timeout: int,
    stats: dict[str, Any],
) -> dict[str, Any] | None:
    items = cache.setdefault("items", {})
    if not isinstance(items, dict):
        items = {}
        cache["items"] = items
    cache_key = post_fingerprint(post)
    cached = items.get(cache_key)
    if isinstance(cached, dict):
        stats["cached"] = int(stats.get("cached") or 0) + 1
        return cached

    stats["requests"] = int(stats.get("requests") or 0) + 1
    attempts = max(1, int(os.environ.get("HARMONICA_LLM_RETRIES", "3") or "3"))
    fallback_models = [
        item.strip()
        for item in os.environ.get("HARMONICA_LLM_FALLBACK_MODELS", "kimi-k2.6").split(",")
        if item.strip()
    ]
    models = unique_limited([model, *fallback_models])
    last_error: Exception | None = None
    result: dict[str, Any] | None = None
    for candidate_model in models:
        for attempt in range(attempts):
            try:
                result = classify_with_llm(
                    post,
                    keyword_matches,
                    token=token,
                    base_url=base_url,
                    model=candidate_model,
                    timeout=timeout,
                )
                if candidate_model != model:
                    stats["fallback_uses"] = int(stats.get("fallback_uses") or 0) + 1
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                last_error = exc
                stats["retry_errors"] = int(stats.get("retry_errors") or 0) + 1
                if attempt + 1 < attempts:
                    time.sleep(min(2.0, 0.5 * (attempt + 1)))
        if result is not None:
            break
    if result is None:
        raise RuntimeError(f"LLM classification failed: {last_error}")
    items[cache_key] = result
    stats["cache_changed"] = True
    return result


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
    parser.add_argument("--llm-tags", dest="llm_tags", action="store_true", default=env_truthy("HARMONICA_ENABLE_LLM_TAGS", True))
    parser.add_argument("--no-llm-tags", dest="llm_tags", action="store_false")
    parser.add_argument("--llm-cache", type=Path, default=DEFAULT_LLM_CACHE)
    parser.add_argument("--llm-base-url", default=os.environ.get("HARMONICA_LLM_BASE_URL", OPENCODE_GO_BASE_URL))
    parser.add_argument("--llm-model", default=os.environ.get("HARMONICA_LLM_MODEL", DEFAULT_LLM_MODEL))
    parser.add_argument("--llm-timeout", type=int, default=int(os.environ.get("HARMONICA_LLM_TIMEOUT", "45")))
    parser.add_argument(
        "--llm-confidence-threshold",
        type=float,
        default=float(os.environ.get("HARMONICA_LLM_CONFIDENCE_THRESHOLD", "0.55")),
    )
    parser.add_argument(
        "--llm-keychain-service",
        default=os.environ.get("HARMONICA_LLM_KEYCHAIN_SERVICE", "harmonica-opencode-go"),
    )
    parser.add_argument(
        "--llm-keychain-account",
        default=os.environ.get("HARMONICA_LLM_KEYCHAIN_ACCOUNT", "harmonica"),
    )
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
                    "llm_tags_requested": bool(args.llm_tags),
                    "llm_base_url": args.llm_base_url,
                    "llm_model": args.llm_model,
                    "llm_cache": str(args.llm_cache),
                    "llm_keychain_service": args.llm_keychain_service,
                    "llm_keychain_account": args.llm_keychain_account,
                    "has_llm_env_token": any(
                        bool(os.environ.get(key))
                        for key in ("HARMONICA_OPENCODE_GO_API_KEY", "OPENCODE_GO_API_KEY", "HARMONICA_LLM_API_KEY")
                    ),
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
    llm_token, llm_token_source = read_llm_token(args.llm_keychain_service, args.llm_keychain_account) if args.llm_tags else ("", "")
    llm_should_tag = bool(args.llm_tags and llm_token and not args.baseline and (not first_run or args.emit_initial))
    llm_cache = load_json(args.llm_cache, {"version": 1, "items": {}}) if llm_should_tag else {"version": 1, "items": {}}
    llm_stats: dict[str, Any] = {
        "requested": bool(args.llm_tags),
        "enabled": llm_should_tag,
        "model": args.llm_model,
        "base_url": args.llm_base_url,
        "token_source": llm_token_source,
        "cached": 0,
        "requests": 0,
        "errors": 0,
        "cache_changed": False,
    }
    if args.llm_tags and not llm_token:
        llm_stats["disabled_reason"] = "missing_api_key"
    elif args.llm_tags and args.baseline:
        llm_stats["disabled_reason"] = "baseline"
    elif args.llm_tags and first_run and not args.emit_initial:
        llm_stats["disabled_reason"] = "initial_baseline_without_emit_initial"

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
            post["keyword_matches"] = matched
            post["matched_keywords"] = split_tag_values(matched)
            if too_old(post.get("posted_at", ""), args.max_post_age_days, now_utc):
                skipped_old += 1
                seen_map[key] = dt.datetime.now(dt.timezone.utc).isoformat()
                continue
            llm_result: dict[str, Any] | None = None
            if llm_should_tag:
                try:
                    llm_result = cached_llm_classification(
                        post,
                        matched,
                        cache=llm_cache,
                        token=llm_token,
                        base_url=args.llm_base_url,
                        model=args.llm_model,
                        timeout=args.llm_timeout,
                        stats=llm_stats,
                    )
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
                    llm_stats["errors"] = int(llm_stats.get("errors") or 0) + 1
                    errors.append(
                        {
                            "source_id": str(post.get("source_id") or source.get("id") or ""),
                            "source_type": "llm_tagger",
                            "error": f"{key}: {exc}",
                        }
                    )
                    llm_result = None
                if llm_result:
                    post.update(llm_result)
                    labels = split_tag_values(list(llm_result.get("llm_labels") or []))
                    post["matched_keywords"] = labels or (["公開更新"] if llm_result.get("llm_relevant") else [])

            if llm_result is not None:
                llm_relevant = bool(post.get("llm_relevant")) and float(post.get("llm_confidence") or 0) >= args.llm_confidence_threshold
                include_post = bool(args.include_all_new or post.get("include_without_keywords") or llm_relevant)
            else:
                include_post = bool(args.include_all_new or matched or post.get("include_without_keywords"))
            if not args.baseline and include_post:
                new_posts.append(post)
            seen_map[key] = dt.datetime.now(dt.timezone.utc).isoformat()
        if should_throttle_source(source, token):
            time.sleep(0.25)

    if llm_stats.get("cache_changed"):
        llm_cache["version"] = 1
        llm_cache["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_json(args.llm_cache, llm_cache)

    seen["seen"] = seen_map
    seen.setdefault("initialized_at", dt.datetime.now(dt.timezone.utc).isoformat())
    seen["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    save_json(args.seen, seen)

    if args.baseline:
        append_errors(args.errors, errors)
        if args.verbose:
            print(json.dumps({"baseline": True, "fetched_posts": fetched_count, "skipped_old_posts": skipped_old, "llm_tags": llm_stats, "errors": errors}, ensure_ascii=False, indent=2))
        return 0

    if first_run and not args.emit_initial:
        append_errors(args.errors, errors)
        if args.verbose:
            print(json.dumps({"baseline": True, "fetched_posts": fetched_count, "skipped_old_posts": skipped_old, "llm_tags": llm_stats, "errors": errors}, ensure_ascii=False, indent=2))
        return 0

    append_candidates(args.candidates, new_posts)
    append_errors(args.errors, errors)

    if new_posts or args.verbose:
        print(
            json.dumps(
                {
                    "new_relevant_posts": new_posts,
                    "skipped_old_posts": skipped_old,
                    "llm_tags": llm_stats,
                    "errors": errors if args.verbose else [],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
