#!/usr/bin/env python3
"""Generate public RSS feeds for harmonica.observe.tw."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
SITE_DATA = SITE_ROOT / "data" / "site-data.js"
CANDIDATES = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
SOCIAL_SOURCES = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
SOURCE_PROFILES_CACHE = PROJECT_ROOT / "data" / "feeds" / "source_profiles.json"
UPDATES_OUT = SITE_ROOT / "feeds" / "updates.xml"
SOURCES_OUT = SITE_ROOT / "feeds" / "sources.xml"
UPDATES_JSON_OUT = SITE_ROOT / "feeds" / "updates.json"
FEED_DATA_JS = SITE_ROOT / "data" / "feed-data.js"
HOME_PAGE = SITE_ROOT / "index.html"
API_DIR = SITE_ROOT / "api"
FEED_IMAGE_DIR = SITE_ROOT / "assets" / "feed-images"
SOURCE_AVATAR_DIR = SITE_ROOT / "assets" / "source-avatars"
PUBLIC_BASE_URL = "https://harmonica.observe.tw"
ASSET_VERSION = "20260624-1718"
HOME_FEED_BATCH_SIZE = 12
DEFAULT_UPDATE_WINDOW_DAYS = 30
BRAND_LOGO_HTML = f'<img class="brand-logo" src="/assets/logo.svg?v={ASSET_VERSION}" alt="臺灣口琴觀測站" width="230" height="41">'
SUBMIT_LINK_HTML = '<a href="/submit/">資料回報</a>'
NAV_FEED_MENU = """<details class="nav-menu">
          <summary>河道</summary>
          <div class="nav-menu-popover">
            <a class="nav-feed-link" href="/#latest-feed" data-feed-category="all">全部公開更新</a>
            <a class="nav-feed-link" href="/?feed=events#latest-feed" data-feed-category="events">實體活動</a>
            <a class="nav-feed-link" href="/?feed=posts-videos#latest-feed" data-feed-category="posts-videos">貼文影片</a>
            <a class="nav-feed-link" href="/?feed=student-clubs#latest-feed" data-feed-category="student-clubs">學生社團</a>
            <a class="nav-feed-link" href="/?feed=opportunities#latest-feed" data-feed-category="opportunities">補助比賽</a>
          </div>
        </details>"""
FOOTER_HTML = """<footer class="site-footer">
      <div class="site-footer-inner">
        <div class="footer-brand">
          <span class="footer-title">臺灣口琴觀測站</span>
          <p>公開口琴活動、社團、貼文影片與補助資訊索引。</p>
        </div>
        <nav class="footer-links" aria-label="頁尾導覽">
          <a href="/directory/">資料索引</a>
          <a href="/feeds/">RSS</a>
          <a href="/api/latest.json">API</a>
          <a href="https://github.com/skyhong2002/Harmonica-in-Taiwan" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
        <p class="footer-meta">只收錄公開可查資料 · MIT License · © 2026 Sky Hong</p>
      </div>
    </footer>"""

TAIPEI_TZ = dt.timezone(dt.timedelta(hours=8))
SOURCE_PROFILE_BY_ID: dict[str, dict[str, str]] = {}
GENERIC_SOURCE_NAMES = {
    "apify facebook posts",
    "apify/facebook-posts-scraper",
    "apify_facebook_posts",
    "external public social feed inbox",
    "external_social_feed_inbox",
}

FEED_CATEGORIES = [
    {
        "id": "events",
        "title": "臺灣口琴觀測站：全臺口琴實體活動",
        "short_title": "實體活動",
        "description": "全臺灣公開口琴演出、成發、音樂會、講座、工作坊與可到場活動。",
        "page_title": "全臺灣口琴實體活動",
        "page_intro": "演出、成發、音樂會、講座、工作坊、音樂節與其他可以實體參與或到場觀察的活動。",
        "rss_path": "feeds/events.xml",
        "json_path": "feeds/events.json",
        "page_path": "feeds/events/index.html",
    },
    {
        "id": "posts-videos",
        "title": "臺灣口琴觀測站：口琴貼文與影片發布",
        "short_title": "貼文影片",
        "description": "全臺灣公開口琴相關社群貼文、影片發布與公開更新。",
        "page_title": "全臺灣口琴相關貼文與影片發布",
        "page_intro": "公開社群貼文、YouTube 或影片發布、活動倒數、花絮、演奏內容與其他口琴圈公開更新。",
        "rss_path": "feeds/posts-videos.xml",
        "json_path": "feeds/posts-videos.json",
        "page_path": "feeds/posts-videos/index.html",
    },
    {
        "id": "student-clubs",
        "title": "臺灣口琴觀測站：口琴學生社團動態",
        "short_title": "學生社團",
        "description": "全臺灣大專與高中職口琴社團公開動態。",
        "page_title": "全臺灣口琴學生社團動態",
        "page_intro": "大專與高中職口琴社團的成發、招生、社博、迎新、交流、寒暑訓與公開社群更新。",
        "rss_path": "feeds/student-clubs.xml",
        "json_path": "feeds/student-clubs.json",
        "page_path": "feeds/student-clubs/index.html",
    },
    {
        "id": "opportunities",
        "title": "臺灣口琴觀測站：補助與比賽資訊",
        "short_title": "補助比賽",
        "description": "口琴社團需要知道的補助、徵件、甄選、比賽、報名與截止資訊。",
        "page_title": "口琴社團需要知道的補助與比賽資訊",
        "page_intro": "適合社團幹部追蹤的補助、競賽、徵件、報名期限、指定曲、計畫申請與甄選資訊。",
        "rss_path": "feeds/opportunities.xml",
        "json_path": "feeds/opportunities.json",
        "page_path": "feeds/opportunities/index.html",
    },
]

CATEGORY_LABELS = {category["id"]: category["short_title"] for category in FEED_CATEGORIES}

CATALOG_JSON_OUT = SITE_ROOT / "feeds" / "catalog.json"
FEED_INDEX_OUT = SITE_ROOT / "feeds" / "index.html"

EVENT_KEYWORDS = [
    "實體",
    "現場",
    "入場",
    "免費入場",
    "售票",
    "購票",
    "報名",
    "演出",
    "音樂會",
    "成發",
    "成果發表",
    "公演",
    "講座",
    "工作坊",
    "大師班",
    "音樂節",
    "校慶",
    "社博",
    "迎新",
    "招生",
    "交流",
    "寒訓",
    "暑訓",
]

OPPORTUNITY_KEYWORDS = [
    "補助",
    "獎助",
    "申請",
    "計畫",
    "徵件",
    "徵選",
    "徵求",
    "甄選",
    "比賽",
    "競賽",
    "指定曲",
    "報名",
    "截止",
    "期限",
    "全國學生音樂比賽",
    "學生音樂比賽",
    "口琴合奏",
    "口琴四重奏",
]

VIDEO_KEYWORDS = [
    "影片",
    "新片",
    "首播",
    "上架",
    "發布",
    "發佈",
    "直播",
    "演奏影片",
    "youtube",
    "video",
    "premiere",
    "cover",
]

STUDENT_SOURCE_MARKERS = [
    "club",
    "harmonica club",
    "hmc",
    "ntubluesound",
    "ntnu",
    "nthu",
    "ncku",
    "fcu",
    "nutc",
    "ncue",
    "npust",
    "csmu",
    "nkust",
    "mcu",
    "ckhc",
    "hsnu",
    "tcfsh",
    "chgsh",
    "tnfsh",
    "kshs",
    "大學",
    "高中",
    "高職",
    "高工",
    "高商",
    "一中",
    "女中",
    "師大",
    "清大",
    "清華",
    "交大",
    "成大",
    "臺大",
    "台大",
    "學生",
    "社團",
    "口琴社",
]


def parse_site_data(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    prefix = "window.HARMONICA_OBSERVE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return json.loads(text.rstrip(";\n"))


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


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    raw = str(value).strip()
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


def rss_time(value: str | None, fallback: dt.datetime) -> str:
    parsed = parse_time(value)
    return email.utils.format_datetime(parsed or fallback)


def compact(value: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def compact_multiline(value: str, limit: int = 1200) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (value or "").splitlines()]
    clean_lines: list[str] = []
    for line in lines:
        if line and (not clean_lines or clean_lines[-1] != line):
            clean_lines.append(line)
    text = "\n".join(clean_lines).strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def first_content_line(value: str, limit: int = 120) -> str:
    for line in compact_multiline(value, limit=limit * 4).splitlines():
        if line.strip():
            return compact(line, limit)
    return compact(value, limit)


def image_extension(url: str, content_type: str) -> str:
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"


def cache_remote_image(url: str, image_dir: Path, public_prefix: str, max_bytes: int = 5_000_000) -> str:
    if not url:
        return ""
    if url.startswith("/assets/"):
        return url
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    existing = sorted(image_dir.glob(f"{digest}.*"))
    if existing:
        return f"{public_prefix}/{existing[0].name}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HarmonicaObserveImageCache/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return ""
            data = response.read(max_bytes)
    except (urllib.error.URLError, TimeoutError, OSError):
        return ""

    image_dir.mkdir(parents=True, exist_ok=True)
    ext = image_extension(url, content_type)
    path = image_dir / f"{digest}{ext}"
    path.write_bytes(data)
    return f"{public_prefix}/{path.name}"


def request_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:@")
    query = urllib.parse.quote(urllib.parse.unquote(parsed.query), safe="=&?/:@,+%")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))


def cache_image(url: str) -> str:
    return cache_remote_image(url, FEED_IMAGE_DIR, "/assets/feed-images")


def cache_avatar(url: str) -> str:
    return cache_remote_image(url, SOURCE_AVATAR_DIR, "/assets/source-avatars", max_bytes=2_000_000)


def url_part(value: Any) -> str:
    return urllib.parse.quote(str(value or "").strip(), safe="")


def format_rsshub_route(route: str, source: dict[str, Any]) -> str:
    values = {
        "username": url_part(source.get("username") or ""),
        "page": url_part(source.get("page") or source.get("username") or ""),
        "id": url_part(source.get("account_id") or source.get("page") or source.get("username") or ""),
    }
    for key, value in values.items():
        route = route.replace("{" + key + "}", value)
    return route


def source_feed_url(source: dict[str, Any]) -> str:
    base = str(source.get("rsshub_base") or "").rstrip("/")
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
    return str(source.get("url") or "")


def public_profile_url(source: dict[str, Any]) -> str:
    kind = source.get("type")
    for field in ("profile_url", "source_profile_url"):
        url = str(source.get(field) or "").strip()
        if url:
            return url
    url = str(source.get("url") or "").strip()
    if url and not source.get("route"):
        return url
    if kind == "facebook_page_posts":
        page = str(source.get("page") or source.get("username") or "").strip().strip("/")
        return f"https://www.facebook.com/{page}/" if page else ""
    if kind == "rsshub_instagram_profile":
        username = str(source.get("username") or "").strip().strip("/")
        return f"https://www.instagram.com/{username}/" if username else ""
    platform = str(source.get("platform") or "").casefold()
    username = str(source.get("username") or "").strip().strip("/").removeprefix("@")
    if username and (platform in {"x", "twitter"} or "twitter" in platform):
        return f"https://x.com/{username}"
    if username and "threads" in platform:
        return f"https://www.threads.net/@{username}"
    if username and "tiktok" in platform:
        return f"https://www.tiktok.com/@{username}"
    return ""


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


def fetch_html_profile(source: dict[str, Any]) -> dict[str, str]:
    profile_url = public_profile_url(source)
    profile: dict[str, str] = {
        "id": str(source.get("id") or ""),
        "name": str(source.get("name") or source.get("id") or ""),
        "account": str(source.get("username") or source.get("page") or source.get("url") or ""),
        "platform": str(source.get("platform") or source.get("type") or ""),
        "profile_url": profile_url,
        "avatar_source_url": "",
    }
    if not profile_url:
        return profile

    try:
        req = urllib.request.Request(
            request_url(profile_url),
            headers={"User-Agent": "Mozilla/5.0 HarmonicaObserveProfileCache/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read(2_000_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return profile

    title = html_meta(text, "og:title")
    description = html_meta(text, "og:description")
    canonical_url = html_meta(text, "og:url")
    avatar = html_meta(text, "og:image")
    if title:
        profile["title"] = title
    if description:
        profile["description"] = description
    if canonical_url:
        profile["profile_url"] = canonical_url
    if avatar:
        profile["avatar_source_url"] = avatar
    return profile


def fetch_source_profile(source: dict[str, Any]) -> dict[str, str]:
    if source.get("type") in {"youtube_ytdlp", "facebook_page_posts"}:
        return fetch_html_profile(source)

    feed_url = source_feed_url(source)
    profile: dict[str, str] = {
        "id": str(source.get("id") or ""),
        "name": str(source.get("name") or source.get("id") or ""),
        "account": str(source.get("username") or source.get("page") or ""),
        "platform": str(source.get("platform") or source.get("type") or ""),
        "profile_url": "",
        "avatar_source_url": "",
    }
    if not feed_url:
        return profile

    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": "HarmonicaObserveProfileCache/1.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            root = ET.fromstring(response.read(2_000_000))
    except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError):
        return profile

    channel = root.find("channel")
    if channel is not None:
        profile["title"] = channel.findtext("title") or ""
        profile["description"] = (channel.findtext("description") or "").replace(" - Powered by RSSHub", "").strip()
        profile["profile_url"] = channel.findtext("link") or ""
        profile["avatar_source_url"] = channel.findtext("image/url") or ""
    else:
        profile["avatar_source_url"] = root.findtext("{http://www.w3.org/2005/Atom}logo") or ""
    return profile


def build_source_profiles(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    needed_ids = {str(row.get("source_id") or "") for row in rows if row.get("source_id")}
    if not needed_ids:
        return {}

    source_config = read_json(SOCIAL_SOURCES, {"sources": []})
    sources = {
        str(source.get("id") or ""): source
        for source in source_config.get("sources", [])
        if isinstance(source, dict)
    }
    cache = read_json(SOURCE_PROFILES_CACHE, {"profiles": {}})
    profiles: dict[str, dict[str, str]] = {
        str(source_id): dict(profile)
        for source_id, profile in (cache.get("profiles") or {}).items()
        if isinstance(profile, dict)
    }

    changed = False
    for source_id in sorted(needed_ids):
        source = sources.get(source_id)
        if not source:
            continue
        cached = profiles.get(source_id) or {}
        if not cached.get("avatar_source_url"):
            fetched = fetch_source_profile(source)
            profiles[source_id] = {**cached, **fetched}
            changed = True
        else:
            profiles[source_id] = {
                **cached,
                "id": source_id,
                "name": str(source.get("name") or cached.get("name") or source_id),
                "account": str(source.get("username") or source.get("page") or cached.get("account") or ""),
                "platform": str(source.get("platform") or cached.get("platform") or ""),
            }

    if changed:
        write_json(
            SOURCE_PROFILES_CACHE,
            {
                "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                "profiles": profiles,
            },
        )
    return {source_id: profiles.get(source_id, {}) for source_id in needed_ids}


def persist_source_profiles(profiles: dict[str, dict[str, str]]) -> None:
    if not profiles:
        return
    cache = read_json(SOURCE_PROFILES_CACHE, {"profiles": {}})
    cached_profiles = cache.get("profiles") if isinstance(cache, dict) else {}
    if not isinstance(cached_profiles, dict):
        cached_profiles = {}

    merged: dict[str, dict[str, str]] = {
        str(source_id): dict(profile)
        for source_id, profile in cached_profiles.items()
        if isinstance(profile, dict)
    }
    changed = False
    for source_id, profile in profiles.items():
        if not source_id or not isinstance(profile, dict):
            continue
        current = dict(merged.get(source_id) or {})
        updated = dict(current)
        for key, value in profile.items():
            if value not in ("", None):
                updated[str(key)] = str(value)
        if updated != current:
            merged[source_id] = updated
            changed = True

    if changed:
        write_json(
            SOURCE_PROFILES_CACHE,
            {
                "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                "profiles": merged,
            },
        )


def local_date(value: str | None) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return "未標示"
    return parsed.astimezone(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M")


def item_guid(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{PUBLIC_BASE_URL}/feeds/{prefix}/{digest}"


def add_text(parent: ET.Element, tag: str, value: str) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = value
    return child


def build_channel(title: str, description: str, link: str) -> ET.Element:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    add_text(channel, "title", title)
    add_text(channel, "link", link)
    add_text(channel, "description", description)
    add_text(channel, "language", "zh-TW")
    add_text(channel, "lastBuildDate", email.utils.format_datetime(dt.datetime.now(dt.timezone.utc)))
    return rss


def write_xml(path: Path, root: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def candidate_sort_key(row: dict[str, Any]) -> dt.datetime:
    return parse_time(str(row.get("posted_at") or row.get("seen_at") or "")) or dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def candidate_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(field) or "")
        for field in [
            "source_id",
            "source_name",
            "platform",
            "account",
            "url",
            "media_type",
            "text",
            "matched_keywords",
            "keyword_matches",
            "llm_labels",
            "llm_categories",
            "llm_reason",
        ]
    )


def has_any_marker(text: str, markers: list[str]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def unique_values(values: list[Any], limit: int = 8) -> list[str]:
    items: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in items:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items


def llm_category_ids(row: dict[str, Any]) -> list[str]:
    values = row.get("llm_categories") or []
    if isinstance(values, str):
        values = re.split(r"[,，、\s]+", values)
    categories = unique_values(
        [str(value or "").strip() for value in values if str(value or "").strip() in CATEGORY_LABELS],
        limit=len(FEED_CATEGORIES),
    )
    if not categories:
        return []
    ids = ["posts-videos"]
    for category in categories:
        if category not in ids:
            ids.append(category)
    return ids


def candidate_category_ids(row: dict[str, Any]) -> list[str]:
    llm_ids = llm_category_ids(row)
    if row.get("llm_relevant") is False:
        return []

    text = candidate_text(row)
    ids = llm_ids or ["posts-videos"]
    if has_any_marker(text, EVENT_KEYWORDS):
        if "events" not in ids:
            ids.append("events")
    if has_any_marker(text, OPPORTUNITY_KEYWORDS):
        if "opportunities" not in ids:
            ids.append("opportunities")
    if has_any_marker(text, STUDENT_SOURCE_MARKERS):
        if "student-clubs" not in ids:
            ids.append("student-clubs")
    if has_any_marker(text, VIDEO_KEYWORDS) and "posts-videos" not in ids:
        ids.append("posts-videos")
    return ids


def candidate_display_tags(row: dict[str, Any]) -> list[str]:
    labels = row.get("llm_labels") or []
    if isinstance(labels, str):
        labels = re.split(r"[,，、\s]+", labels)
    keywords = row.get("matched_keywords") or []
    if isinstance(keywords, str):
        keywords = re.split(r"[,，、\s]+", keywords)
    return unique_values([*labels, *keywords], limit=8)


def read_candidate_rows() -> list[dict[str, Any]]:
    return sorted(read_jsonl(CANDIDATES), key=candidate_sort_key, reverse=True)


def candidate_dedupe_key(row: dict[str, Any], title: str) -> str:
    return str(row.get("url") or row.get("key") or title).strip().casefold()


def source_initials(source: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", source or "")
    if words:
        return "".join(word[0].upper() for word in words[:3])
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", source or "")
    if chinese_chars:
        return "".join(chinese_chars[:2])
    return "H"


def clean_source_display_name(value: Any) -> str:
    name = compact(str(value or ""), 180)
    if not name:
        return ""
    name = re.sub(r"\s+-\s+(YouTube|Instagram|Facebook)\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+\|\s+(YouTube|Instagram|Facebook)\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+\(@[^)]+\)\s*$", "", name)
    if " | " in name:
        name = name.split(" | ", 1)[0].strip()
    return compact(name, 120)


def is_generic_source_name(value: Any) -> bool:
    name = clean_source_display_name(value).casefold()
    return name in GENERIC_SOURCE_NAMES


def account_display_name(row: dict[str, Any], profile: dict[str, str]) -> str:
    account = str(row.get("account") or profile.get("account") or "").strip()
    if not account:
        return ""
    if account.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(account)
        account = parsed.path.strip("/")
        if account.startswith("@"):
            account = account[1:]
        elif account.startswith(("people/", "profile.php")):
            return ""
        elif "/" in account:
            account = account.split("/", 1)[0]
    return clean_source_display_name(account.removeprefix("@"))


def public_source_name(row: dict[str, Any], profile: dict[str, str]) -> str:
    source_display_name = clean_source_display_name(row.get("source_display_name"))
    source_name = clean_source_display_name(row.get("source_name"))
    account_name = account_display_name(row, profile)
    if source_display_name and not (
        account_name
        and source_display_name == account_name
        and source_name
        and not is_generic_source_name(source_name)
    ):
        return source_display_name

    if source_name and not is_generic_source_name(source_name):
        return source_name

    for value in [
        row.get("profile_name"),
        row.get("page_name"),
        profile.get("title"),
        profile.get("display_name"),
    ]:
        name = clean_source_display_name(value)
        if name:
            return name

    platform = str(row.get("platform") or profile.get("platform") or "").casefold()
    source_id = str(row.get("source_id") or "").casefold()
    if "facebook" in platform and (
        is_generic_source_name(row.get("source_name"))
        or source_id in GENERIC_SOURCE_NAMES
        or str(row.get("raw_source") or "").casefold() in GENERIC_SOURCE_NAMES
    ):
        if account_name:
            return account_name

    for value in [
        row.get("source_name"),
        profile.get("name"),
        row.get("source_id"),
    ]:
        name = clean_source_display_name(value)
        if name and not is_generic_source_name(name):
            return name
    return "公開來源"


def public_source_profile_url(row: dict[str, Any], profile: dict[str, str]) -> str:
    for value in [
        row.get("source_profile_url"),
        row.get("profile_url"),
        profile.get("profile_url"),
        row.get("account"),
    ]:
        url = str(value or "").strip()
        if url.startswith(("http://", "https://")):
            return url

    account = str(row.get("account") or profile.get("account") or "").strip().strip("/")
    if not account:
        return ""
    platform = str(row.get("platform") or profile.get("platform") or "").casefold()
    account = account.removeprefix("@")
    if "instagram" in platform:
        return f"https://www.instagram.com/{url_part(account)}/"
    if "facebook" in platform:
        return f"https://www.facebook.com/{account}/"
    if "youtube" in platform:
        if account.startswith("channel/") or account.startswith("c/") or account.startswith("user/"):
            return f"https://www.youtube.com/{account}"
        return f"https://www.youtube.com/@{url_part(account)}"
    if platform in {"x", "twitter"} or "twitter" in platform:
        return f"https://x.com/{url_part(account)}"
    if "threads" in platform:
        return f"https://www.threads.net/@{url_part(account)}"
    if "tiktok" in platform:
        account = account if account.startswith("@") else f"@{account}"
        return f"https://www.tiktok.com/{url_part(account)}"
    return ""


def public_update_row(row: dict[str, Any]) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    profile = SOURCE_PROFILE_BY_ID.get(source_id, {})
    source = public_source_name(row, profile)
    source_system_name = str(row.get("source_name") or profile.get("name") or row.get("source_id") or "")
    if is_generic_source_name(source_system_name):
        source_system_name = source
    source_profile_url = public_source_profile_url(row, profile)
    text = compact_multiline(str(row.get("text") or ""), 1200)
    title = compact(f"{source}｜{text}", 120)
    headline = first_content_line(text, 120) or source
    link = str(row.get("url") or PUBLIC_BASE_URL)
    categories = candidate_category_ids(row)
    display_tags = candidate_display_tags(row)
    images = [str(url) for url in (row.get("images") or []) if url]
    image_url = str(row.get("image_url") or (images[0] if images else ""))
    local_image_url = cache_image(image_url)
    avatar_source_url = str(
        row.get("source_avatar_url")
        or row.get("avatar_source_url")
        or profile.get("avatar_source_url")
        or ""
    )
    avatar_url = cache_avatar(avatar_source_url)
    if source_id and avatar_source_url:
        cached_profile = SOURCE_PROFILE_BY_ID.setdefault(source_id, {})
        if not cached_profile.get("avatar_source_url") or not cached_profile.get("avatar_url"):
            cached_profile["avatar_source_url"] = avatar_source_url
        if avatar_url and not cached_profile.get("avatar_url"):
            cached_profile["avatar_url"] = avatar_url
    return {
        "title": title,
        "headline": headline,
        "link": link,
        "source_id": source_id,
        "source": source,
        "source_system_name": source_system_name,
        "source_profile_url": source_profile_url,
        "account": row.get("account") or profile.get("account") or "",
        "platform": row.get("platform") or "",
        "posted_at": row.get("posted_at") or "",
        "posted_at_local": local_date(str(row.get("posted_at") or "")),
        "seen_at": row.get("seen_at") or "",
        "matched_keywords": display_tags,
        "keyword_matches": row.get("keyword_matches") or [],
        "llm_relevant": row.get("llm_relevant"),
        "llm_confidence": row.get("llm_confidence"),
        "llm_labels": row.get("llm_labels") or [],
        "llm_categories": row.get("llm_categories") or [],
        "llm_reason": row.get("llm_reason") or "",
        "text": text,
        "images": images,
        "source_image_url": image_url,
        "image_url": local_image_url or image_url,
        "source_avatar_url": avatar_source_url,
        "avatar_url": avatar_url,
        "source_initials": source_initials(source),
        "categories": categories,
        "category_labels": [CATEGORY_LABELS.get(category, category) for category in categories],
        "key": row.get("key") or item_guid("updates", link + title),
        "_dedupe_key": candidate_dedupe_key(row, title),
    }


def add_update_item(channel: ET.Element, public_row: dict[str, Any]) -> None:
    item = ET.SubElement(channel, "item")
    add_text(item, "title", str(public_row["title"]))
    add_text(item, "link", str(public_row["link"]))
    add_text(item, "guid", str(public_row["key"]))
    add_text(item, "pubDate", rss_time(str(public_row.get("posted_at") or public_row.get("seen_at") or ""), dt.datetime.now(dt.timezone.utc)))
    description = "\n".join(
        part
        for part in [
            f"來源：{public_row.get('source')}",
            f"平台：{public_row.get('platform') or 'public'}",
            f"時間：{public_row.get('posted_at') or '未標示'}",
            f"標籤：{', '.join(public_row.get('matched_keywords') or [])}" if public_row.get("matched_keywords") else "",
            "",
            str(public_row.get("text") or ""),
        ]
        if part != ""
    )
    add_text(item, "description", description)


def build_update_items(rows: list[dict[str, Any]], limit: int | None = None, category_id: str | None = None) -> list[dict[str, Any]]:
    public_rows: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    max_items = max(0, int(limit or 0))

    for row in rows:
        public_row = public_update_row(row)
        if category_id and category_id not in public_row["categories"]:
            continue
        dedupe_key = str(public_row["_dedupe_key"])
        if dedupe_key in seen_items:
            continue
        seen_items.add(dedupe_key)
        public_row.pop("_dedupe_key", None)
        public_rows.append(public_row)
        if max_items and len(public_rows) >= max_items:
            break

    return public_rows


def write_update_json(path: Path, items: list[dict[str, Any]], category: dict[str, str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"items": items}
    if category:
        payload["category"] = {
            "id": category["id"],
            "title": category["page_title"],
            "description": category["description"],
            "rss": f"{PUBLIC_BASE_URL}/{category['rss_path']}",
            "page": f"{PUBLIC_BASE_URL}/{category['page_path'].removesuffix('/index.html')}/",
        }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def category_payload(category: dict[str, str], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": category["id"],
        "title": category["page_title"],
        "shortTitle": category["short_title"],
        "description": category["description"],
        "page": f"/{category['page_path'].removesuffix('/index.html')}/",
        "rss": f"/{category['rss_path']}",
        "json": f"/{category['json_path']}",
        "items": items,
        "count": len(items),
    }


def write_feed_data_js(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]], window_days: int) -> None:
    payload = {
        "generatedAt": dt.datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
        "updatesWindowDays": window_days,
        "updates": public_rows,
        "feeds": [
            category_payload(category, categorized.get(category["id"], []))
            for category in FEED_CATEGORIES
        ],
    }
    FEED_DATA_JS.parent.mkdir(parents=True, exist_ok=True)
    FEED_DATA_JS.write_text(
        "window.HARMONICA_OBSERVE_FEEDS = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def api_category_payload(category: dict[str, str], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": category["id"],
        "title": category["page_title"],
        "shortTitle": category["short_title"],
        "description": category["description"],
        "page": f"{PUBLIC_BASE_URL}{feed_page_url(category)}",
        "rss": f"{PUBLIC_BASE_URL}/{category['rss_path']}",
        "json": f"{PUBLIC_BASE_URL}/api/{category['id']}.json",
        "sourceJson": f"{PUBLIC_BASE_URL}/{category['json_path']}",
        "count": len(items),
        "items": items,
    }


def write_api_files(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]], window_days: int) -> None:
    API_DIR.mkdir(parents=True, exist_ok=True)
    feeds = [
        api_category_payload(category, categorized.get(category["id"], []))
        for category in FEED_CATEGORIES
    ]
    catalog = [
        {
            "id": feed["id"],
            "title": feed["title"],
            "shortTitle": feed["shortTitle"],
            "description": feed["description"],
            "page": feed["page"],
            "rss": feed["rss"],
            "json": feed["json"],
            "count": feed["count"],
        }
        for feed in feeds
    ]
    payload = {
        "generatedAt": dt.datetime.now(TAIPEI_TZ).isoformat(),
        "updatesWindowDays": window_days,
        "site": PUBLIC_BASE_URL,
        "updates": public_rows,
        "feeds": feeds,
    }
    (API_DIR / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (API_DIR / "catalog.json").write_text(json.dumps({"site": PUBLIC_BASE_URL, "feeds": catalog}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for feed in feeds:
        (API_DIR / f"{feed['id']}.json").write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_update_rss(path: Path, title: str, description: str, link: str, items: list[dict[str, Any]]) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    rss = build_channel(title, description, link)
    channel = rss.find("channel")
    assert channel is not None

    for item in items:
        add_update_item(channel, item)
    if not items:
        add_text(channel, "pubDate", email.utils.format_datetime(now))

    write_xml(path, rss)


def filter_recent_candidate_rows(rows: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    if days <= 0:
        return rows
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    recent_rows: list[dict[str, Any]] = []
    for row in rows:
        timestamp = parse_time(str(row.get("posted_at") or row.get("seen_at") or ""))
        if timestamp and timestamp >= cutoff:
            recent_rows.append(row)
    return recent_rows


def generate_updates(window_days: int = DEFAULT_UPDATE_WINDOW_DAYS, limit: int | None = None) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    global SOURCE_PROFILE_BY_ID
    rows = filter_recent_candidate_rows(read_candidate_rows(), window_days)
    profile_rows = [
        row for row in rows if row.get("raw_source") != "public-link-backfill"
    ]
    SOURCE_PROFILE_BY_ID = build_source_profiles(profile_rows)
    public_rows = build_update_items(rows, limit)
    persist_source_profiles(SOURCE_PROFILE_BY_ID)
    write_update_rss(
        UPDATES_OUT,
        "臺灣口琴觀測站：公開更新",
        "公開口琴活動、貼文與資訊候選更新。",
        f"{PUBLIC_BASE_URL}/feeds/",
        public_rows,
    )
    write_update_json(UPDATES_JSON_OUT, public_rows)

    categorized: dict[str, list[dict[str, Any]]] = {}
    for category in FEED_CATEGORIES:
        items = build_update_items(rows, limit, category["id"])
        categorized[category["id"]] = items
        write_update_rss(
            SITE_ROOT / category["rss_path"],
            category["title"],
            category["description"],
            f"{PUBLIC_BASE_URL}/{category['page_path'].removesuffix('/index.html')}/",
            items,
        )
        write_update_json(SITE_ROOT / category["json_path"], items, category)

    write_feed_data_js(public_rows, categorized, window_days)
    write_api_files(public_rows, categorized, window_days)
    write_homepage_latest(public_rows, categorized, window_days)
    write_feed_pages(categorized)
    return public_rows, categorized


def html_escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def html_lines(value: Any) -> str:
    lines = str(value or "").splitlines()
    if not lines:
        return ""
    return "<br>".join(html_escape(line) for line in lines)


def homepage_excerpt(value: Any, limit: int = 220, max_lines: int = 3, skip_first: bool = False) -> str:
    text = compact_multiline(str(value or ""), limit)
    lines = text.splitlines()
    if skip_first and lines:
        lines = lines[1:]
    lines = lines[:max_lines]
    return "<br>".join(html_escape(line) for line in lines if line)


def render_keyword_pills(keywords: list[str]) -> str:
    if not keywords:
        return ""
    return "".join(f'<span class="pill">{html_escape(keyword)}</span>' for keyword in keywords[:6])


def render_category_pills(item: dict[str, Any]) -> str:
    labels = item.get("category_labels") or [
        CATEGORY_LABELS.get(category, category)
        for category in (item.get("categories") or [])
    ]
    return "".join(f'<span class="pill">{html_escape(label)}</span>' for label in labels)


def render_home_tag_pills(item: dict[str, Any]) -> str:
    keywords = list(item.get("matched_keywords") or [])[:5]
    return "".join(f'<span class="pill feed-tag-pill">{html_escape(keyword)}</span>' for keyword in keywords)


def render_source_avatar(item: dict[str, Any], class_name: str = "source-avatar") -> str:
    avatar = item.get("avatar_url")
    source = item.get("source") or "公開來源"
    initials = item.get("source_initials") or source_initials(str(source))
    if avatar:
        return (
            f'<span class="{class_name}">'
            f'<img src="{html_escape(avatar)}" alt="{html_escape(source)} 頭貼" loading="lazy" referrerpolicy="no-referrer">'
            "</span>"
        )
    return f'<span class="{class_name} source-avatar-fallback" aria-hidden="true">{html_escape(initials)}</span>'


def render_source_identity(item: dict[str, Any], class_name: str = "source-avatar", meta_class: str = "feed-latest-meta") -> str:
    source = item.get("source") or "公開來源"
    meta = f"{item.get('posted_at_local') or '未標示'} · {item.get('platform') or 'public'}"
    body = (
        f'{render_source_avatar(item, class_name)}'
        "<div>"
        f'<span class="{meta_class}">{html_escape(meta)}</span>'
        f"<strong>{html_escape(source)}</strong>"
        "</div>"
    )
    profile_url = str(item.get("source_profile_url") or "").strip()
    if profile_url:
        return (
            f'<a class="source-identity-link" href="{html_escape(profile_url)}" '
            f'target="_blank" rel="noreferrer" aria-label="開啟 {html_escape(source)} 個人首頁">'
            f"{body}</a>"
        )
    return body


def render_home_feed_item(item: dict[str, Any]) -> str:
    image = item.get("image_url")
    thumb_html = (
        f'<span class="home-feed-thumb"><img src="{html_escape(image)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>'
        if image
        else ""
    )
    body_class = "home-feed-body" if thumb_html else "home-feed-body home-feed-body-no-image"
    excerpt = homepage_excerpt(item.get("text"), limit=260, max_lines=4, skip_first=True)
    excerpt_html = f'<span class="feed-latest-excerpt">{excerpt}</span>' if excerpt else ""
    category_html = render_category_pills(item) + render_home_tag_pills(item)
    return f"""
      <article class="home-feed-card">
        <div class="home-feed-source">
          {render_source_identity(item)}
        </div>
        <div class="{body_class}">
          <h3 class="home-feed-title">{html_escape(item.get("headline") or item.get("title") or "公開更新")}</h3>
          {thumb_html}
          {excerpt_html}
        </div>
        <div class="home-feed-footer">
          <div class="entry-meta">{category_html}</div>
          <a class="feed-open-link" href="{html_escape(item.get("link"))}" target="_blank" rel="noreferrer">開啟來源</a>
        </div>
      </article>
    """


def render_home_filter_chip_options(values: list[str], data_name: str, fallback_label: str) -> str:
    chips = [
        f'<button type="button" class="feed-option-chip" data-feed-{html_escape(data_name)}="all" aria-pressed="true">{html_escape(fallback_label)}</button>'
    ]
    chips.extend(
        f'<button type="button" class="feed-option-chip" data-feed-{html_escape(data_name)}="{html_escape(value)}" aria-pressed="false">{html_escape(value)}</button>'
        for value in values
    )
    return "".join(chips)


def render_home_feed_filters(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]], window_days: int) -> str:
    chips = [
        f"""
          <button type="button" class="feed-filter-chip" data-feed-category="all" aria-pressed="true">
            <span>全部</span>
            <strong>{len(public_rows)}</strong>
          </button>
        """
    ]
    for category in FEED_CATEGORIES:
        category_id = category["id"]
        short_title = category["short_title"]
        chips.append(
            f"""
          <button type="button" class="feed-filter-chip" data-feed-category="{html_escape(category_id)}" aria-pressed="false">
            <span>{html_escape(short_title)}</span>
            <strong>{len(categorized.get(category_id, []))}</strong>
          </button>
        """
        )
    sources = sorted({str(item.get("source")) for item in public_rows if item.get("source")})
    platforms = sorted({str(item.get("platform")) for item in public_rows if item.get("platform")})
    tags = sorted({str(keyword) for item in public_rows for keyword in (item.get("matched_keywords") or []) if keyword})
    return f"""
      <div class="feed-river-controls">
        <div class="feed-river-summary">
          <p class="feed-filter-label">河道篩選</p>
          <strong>全部 · 最近 {window_days} 天 · {len(public_rows)} / {len(public_rows)} 筆</strong>
        </div>
        <div class="feed-filter-chips" aria-label="分類篩選">
          {"".join(chips)}
        </div>
        <div class="feed-filter-tools">
          <label class="search-field feed-search-field">
            <span class="sr-only">搜尋河道</span>
            <input id="feed-search-input" type="search" placeholder="搜尋標題、內文、tag 或來源">
          </label>
          <button class="feed-reset-button" type="button">重設</button>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">平台</span>
          <div class="feed-option-chips" aria-label="平台篩選，可複選">{render_home_filter_chip_options(platforms, "platform", "全部平台")}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">Tag</span>
          <div class="feed-option-chips" aria-label="Tag 篩選，可複選">{render_home_filter_chip_options(tags, "tag", "全部 tag")}</div>
        </div>
        <div class="feed-filter-chip-group">
          <span class="feed-chip-group-label">來源</span>
          <div class="feed-option-chips" aria-label="來源篩選，可複選">{render_home_filter_chip_options(sources, "source", "全部來源")}</div>
        </div>
      </div>
    """


def render_home_feed_load_more(total: int, visible: int) -> str:
    if not total or visible >= total:
        return ""
    return f"""
      <div class="feed-load-more-wrap">
        <span class="feed-load-more-status">已顯示 {visible} / {total} 筆</span>
        <button class="feed-load-more-button" type="button">載入更多</button>
      </div>
    """


def estimate_home_feed_height(item: dict[str, Any]) -> int:
    text = " ".join(
        str(value or "")
        for value in [
            item.get("headline"),
            item.get("title"),
            item.get("source"),
            item.get("excerpt"),
            " ".join(item.get("matched_keywords") or []),
        ]
    )
    media_weight = 120 if item.get("image_url") else 0
    return 230 + media_weight + min(180, len(text) // 3)


def render_home_feed_columns(rows: list[dict[str, Any]], column_count: int = 3) -> str:
    if not rows:
        return '<div class="empty-state">目前沒有近期待觀測項目。</div>'
    columns: list[list[dict[str, Any]]] = [[] for _ in range(column_count)]
    heights = [0] * column_count
    for item in rows:
        column_index = min(range(column_count), key=lambda index: heights[index])
        columns[column_index].append(item)
        heights[column_index] += estimate_home_feed_height(item)
    rendered_columns = []
    for index, column_rows in enumerate(columns, start=1):
        column_html = "\n".join(render_home_feed_item(item) for item in column_rows)
        rendered_columns.append(
            f'      <div class="feed-river-column" data-feed-column="{index}">\n'
            f"{column_html}\n"
            "      </div>"
        )
    return "\n".join(rendered_columns)


def write_homepage_latest(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]], window_days: int) -> None:
    start = "            <!-- FEED_LATEST_START -->"
    end = "            <!-- FEED_LATEST_END -->"
    text = HOME_PAGE.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return
    visible_rows = public_rows[:HOME_FEED_BATCH_SIZE]
    latest_html = (
        render_home_feed_filters(public_rows, categorized, window_days)
        + f'\n      <div class="feed-river">\n{render_home_feed_columns(visible_rows)}\n      </div>'
        + render_home_feed_load_more(len(public_rows), len(visible_rows))
    )
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    HOME_PAGE.write_text(f"{before}{start}\n{latest_html}\n            {end}{after}", encoding="utf-8")


def render_update_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-state">目前沒有符合這個分類的近期待觀測項目。</div>'

    cards = []
    for item in items:
        keywords = render_keyword_pills(list(item.get("matched_keywords") or []))
        image = item.get("image_url")
        image_html = (
            f"""
              <a class="feed-item-image" href="{html_escape(item.get("link"))}" target="_blank" rel="noreferrer">
                <img src="{html_escape(image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
              </a>
            """
            if image
            else ""
        )
        cards.append(
            f"""
            <article class="feed-item-card">
              {image_html}
              <div class="feed-item-main">
                <div class="feed-item-source">
                  {render_source_identity(item, "source-avatar source-avatar-small", "feed-item-meta")}
                </div>
                <h2>{html_escape(item.get("headline") or item.get("title"))}</h2>
                <p class="feed-item-text">{html_lines(item.get("text"))}</p>
              </div>
              <div class="feed-item-actions">
                <div class="entry-meta">{keywords}</div>
                <a class="primary-link" href="{html_escape(item.get("link"))}" target="_blank" rel="noreferrer">開啟來源</a>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def feed_page_url(category: dict[str, str]) -> str:
    return f"/{category['page_path'].removesuffix('/index.html')}/"


def render_feed_category_card(category: dict[str, str], count: int) -> str:
    return f"""
      <article class="feed-category-card">
        <div>
          <p class="section-kicker">{html_escape(category["id"])}</p>
          <h2>{html_escape(category["page_title"])}</h2>
          <p>{html_escape(category["description"])}</p>
        </div>
        <div class="feed-card-actions">
          <span class="pill">{count} 筆</span>
          <a href="/{html_escape(category["rss_path"])}">RSS</a>
        </div>
      </article>
    """


def render_feed_page(category: dict[str, str], items: list[dict[str, Any]]) -> str:
    rss_url = f"/{category['rss_path']}"
    json_url = f"/{category['json_path']}"
    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html_escape(category["page_title"])}｜臺灣口琴觀測站</title>
    <meta name="description" content="{html_escape(category["description"])}">
    <link rel="icon" href="/assets/favicon-20260623.svg?v={ASSET_VERSION}" type="image/svg+xml">
    <link rel="alternate" type="application/rss+xml" title="{html_escape(category["title"])}" href="{html_escape(rss_url)}">
    <link rel="stylesheet" href="/assets/styles.css?v={ASSET_VERSION}">
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="/" aria-label="臺灣口琴觀測站首頁">
        {BRAND_LOGO_HTML}
      </a>
      <nav class="site-nav" aria-label="主要導覽">
        <a href="/#latest-feed">最新</a>
        {NAV_FEED_MENU}
        <a href="/directory/">資料索引</a>
        <a href="/feeds/">RSS</a>
        {SUBMIT_LINK_HTML}
      </nav>
    </header>

    <main class="feed-page-main">
      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Hermes RSS</p>
            <h1>{html_escape(category["page_title"])}</h1>
          </div>
          <div class="feed-page-summary">
            <p>{html_escape(category["page_intro"])}</p>
            <div class="feed-links">
              <a href="{html_escape(rss_url)}">RSS 訂閱</a>
              <a href="{html_escape(json_url)}">JSON</a>
              <a href="/feeds/">全部分類</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Latest</p>
              <h2>目前項目</h2>
            </div>
            <p class="data-date">{len(items)} 筆</p>
          </div>
          <div class="feed-item-list">
            {render_update_cards(items)}
          </div>
        </div>
      </section>
    </main>

    {FOOTER_HTML}
  </body>
</html>
"""


def render_feed_index(categorized: dict[str, list[dict[str, Any]]]) -> str:
    cards = "\n".join(
        render_feed_category_card(category, len(categorized.get(category["id"], [])))
        for category in FEED_CATEGORIES
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hermes RSS 分類｜臺灣口琴觀測站</title>
    <meta name="description" content="給 Bamboo Hermes 訂閱的臺灣口琴公開資訊分類 RSS。">
    <link rel="icon" href="/assets/favicon-20260623.svg?v={ASSET_VERSION}" type="image/svg+xml">
    <link rel="alternate" type="application/rss+xml" title="臺灣口琴觀測站公開更新" href="/feeds/updates.xml">
    <link rel="stylesheet" href="/assets/styles.css?v={ASSET_VERSION}">
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="/" aria-label="臺灣口琴觀測站首頁">
        {BRAND_LOGO_HTML}
      </a>
      <nav class="site-nav" aria-label="主要導覽">
        <a href="/#latest-feed">最新</a>
        {NAV_FEED_MENU}
        <a href="/directory/">資料索引</a>
        <a href="/feeds/">RSS</a>
        {SUBMIT_LINK_HTML}
      </nav>
    </header>

    <main class="feed-page-main">
      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Hermes RSS</p>
            <h1>分類公開更新</h1>
          </div>
          <div class="feed-page-summary">
            <p>Bamboo Hermes 可以分別訂閱這些 RSS。每條 feed 都只來自公開來源，且和頁面顯示共用同一份資料。</p>
            <div class="feed-links">
              <a href="/feeds/updates.xml">總更新 RSS</a>
              <a href="/feeds/sources.xml">來源索引 RSS</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band">
        <div class="band-inner feed-category-grid">
          {cards}
        </div>
      </section>
    </main>

    {FOOTER_HTML}
  </body>
</html>
"""


def write_feed_pages(categorized: dict[str, list[dict[str, Any]]]) -> None:
    FEED_INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    FEED_INDEX_OUT.write_text(render_feed_index(categorized), encoding="utf-8")
    catalog = []
    for category in FEED_CATEGORIES:
        page = SITE_ROOT / category["page_path"]
        page.parent.mkdir(parents=True, exist_ok=True)
        items = categorized.get(category["id"], [])
        page.write_text(render_feed_page(category, items), encoding="utf-8")
        catalog.append(
            {
                "id": category["id"],
                "title": category["page_title"],
                "description": category["description"],
                "page": f"{PUBLIC_BASE_URL}{feed_page_url(category)}",
                "rss": f"{PUBLIC_BASE_URL}/{category['rss_path']}",
                "json": f"{PUBLIC_BASE_URL}/{category['json_path']}",
                "items": len(items),
            }
        )
    CATALOG_JSON_OUT.write_text(json.dumps({"feeds": catalog}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bump_html_asset_versions() -> None:
    for path in SITE_ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        updated = re.sub(r"\?v=\d{8}-\d{4}", f"?v={ASSET_VERSION}", text)
        updated = "\n".join(line.rstrip() for line in updated.splitlines()) + "\n"
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def generate_sources(limit: int) -> int:
    data = parse_site_data(SITE_DATA)
    entries = data.get("entries", [])[:limit]
    now = dt.datetime.now(dt.timezone.utc)
    rss = build_channel(
        "臺灣口琴觀測站：來源索引",
        "公開口琴社團、團體、演奏者、教學與場館的來源索引。",
        f"{PUBLIC_BASE_URL}/#directory",
    )
    channel = rss.find("channel")
    assert channel is not None

    for entry in entries:
        name = str(entry.get("name") or "公開來源")
        links = entry.get("links") or []
        first_link = links[0].get("url") if links and isinstance(links[0], dict) else f"{PUBLIC_BASE_URL}/#directory"
        item = ET.SubElement(channel, "item")
        add_text(item, "title", name)
        add_text(item, "link", str(first_link))
        add_text(item, "guid", item_guid("sources", name + str(first_link)))
        add_text(item, "pubDate", rss_time(str(data.get("generatedAt") or ""), now))
        summary = compact(str(entry.get("summary") or entry.get("type") or ""), 500)
        source_tags = "、".join(str(tag) for tag in (entry.get("sourceTags") or []) if str(tag).strip())
        description = "\n".join(
            part
            for part in [
                f"分類：{entry.get('category') or '未分類'}",
                f"Tag：{source_tags}" if source_tags else "",
                f"地區：{entry.get('region') or '未標示'}",
                f"查核：{entry.get('status') or '待確認'}",
                "",
                summary,
            ]
            if part != ""
        )
        add_text(item, "description", html.escape(description))

    write_xml(SOURCES_OUT, rss)
    API_DIR.mkdir(parents=True, exist_ok=True)
    (API_DIR / "sources.json").write_text(
        json.dumps(
            {
                "site": PUBLIC_BASE_URL,
                "generatedAt": data.get("generatedAt") or "",
                "count": len(entries),
                "stats": data.get("stats") or {},
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--updates-days", type=int, default=DEFAULT_UPDATE_WINDOW_DAYS)
    parser.add_argument("--updates-limit", type=int, default=0)
    parser.add_argument("--sources-limit", type=int, default=150)
    args = parser.parse_args()

    updates, categorized = generate_updates(args.updates_days, args.updates_limit)
    sources_count = generate_sources(args.sources_limit)
    bump_html_asset_versions()
    print(
        json.dumps(
            {
                "updates": len(updates),
                "updates_window_days": args.updates_days,
                "updates_limit": args.updates_limit or None,
                "categorized_updates": {
                    category["id"]: len(categorized.get(category["id"], []))
                    for category in FEED_CATEGORIES
                },
                "sources": sources_count,
                "updates_feed": str(UPDATES_OUT),
                "sources_feed": str(SOURCES_OUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
