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
ASSET_VERSION = "20260623-2138"
BRAND_LOGO_HTML = f'<img class="brand-logo" src="/assets/logo.svg?v={ASSET_VERSION}" alt="臺灣口琴觀測站" width="230" height="41">'
FOOTER_HTML = """<footer class="site-footer">
      <div class="site-footer-inner">
        <div class="footer-brand">
          <span class="footer-title">臺灣口琴觀測站</span>
          <p>公開口琴活動、社團、貼文影片與補助資訊索引。</p>
        </div>
        <nav class="footer-links" aria-label="頁尾導覽">
          <a href="/directory/">公開名錄</a>
          <a href="/feeds/">RSS</a>
          <a href="/api/latest.json">API</a>
          <a href="https://github.com/skyhong2002/Harmonica-in-Taiwan" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
        <p class="footer-meta">只收錄公開可查資料 · MIT License · © 2026 Sky Hong</p>
      </div>
    </footer>"""

TAIPEI_TZ = dt.timezone(dt.timedelta(hours=8))
SOURCE_PROFILE_BY_ID: dict[str, dict[str, str]] = {}

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
    url = str(source.get("url") or "").strip()
    if url:
        return url
    if kind == "facebook_page_posts":
        page = str(source.get("page") or source.get("username") or "").strip().strip("/")
        return f"https://www.facebook.com/{page}/" if page else ""
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
            profile_url,
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
                "id": source_id,
                "name": str(source.get("name") or cached.get("name") or source_id),
                "account": str(source.get("username") or source.get("page") or cached.get("account") or ""),
                "platform": str(source.get("platform") or cached.get("platform") or ""),
                **cached,
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
        ]
    )


def has_any_marker(text: str, markers: list[str]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def candidate_category_ids(row: dict[str, Any]) -> list[str]:
    text = candidate_text(row)
    ids = ["posts-videos"]
    if has_any_marker(text, EVENT_KEYWORDS):
        ids.append("events")
    if has_any_marker(text, OPPORTUNITY_KEYWORDS):
        ids.append("opportunities")
    if has_any_marker(text, STUDENT_SOURCE_MARKERS):
        ids.append("student-clubs")
    if has_any_marker(text, VIDEO_KEYWORDS) and "posts-videos" not in ids:
        ids.append("posts-videos")
    return ids


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


def public_update_row(row: dict[str, Any]) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    source = str(row.get("source_name") or row.get("source_id") or "公開來源")
    text = compact_multiline(str(row.get("text") or ""), 1200)
    title = compact(f"{source}｜{text}", 120)
    headline = first_content_line(text, 120) or source
    link = str(row.get("url") or PUBLIC_BASE_URL)
    categories = candidate_category_ids(row)
    images = [str(url) for url in (row.get("images") or []) if url]
    image_url = str(row.get("image_url") or (images[0] if images else ""))
    local_image_url = cache_image(image_url)
    profile = SOURCE_PROFILE_BY_ID.get(source_id, {})
    avatar_source_url = str(
        row.get("source_avatar_url")
        or row.get("avatar_source_url")
        or profile.get("avatar_source_url")
        or ""
    )
    avatar_url = cache_avatar(avatar_source_url)
    return {
        "title": title,
        "headline": headline,
        "link": link,
        "source_id": source_id,
        "source": source,
        "account": row.get("account") or profile.get("account") or "",
        "platform": row.get("platform") or "",
        "posted_at": row.get("posted_at") or "",
        "posted_at_local": local_date(str(row.get("posted_at") or "")),
        "seen_at": row.get("seen_at") or "",
        "matched_keywords": row.get("matched_keywords") or [],
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
            f"關鍵字：{', '.join(public_row.get('matched_keywords') or [])}" if public_row.get("matched_keywords") else "",
            "",
            str(public_row.get("text") or ""),
        ]
        if part != ""
    )
    add_text(item, "description", description)


def build_update_items(rows: list[dict[str, Any]], limit: int, category_id: str | None = None) -> list[dict[str, Any]]:
    public_rows: list[dict[str, Any]] = []
    seen_items: set[str] = set()

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
        if len(public_rows) >= limit:
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


def write_feed_data_js(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]]) -> None:
    payload = {
        "generatedAt": dt.datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M"),
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


def write_api_files(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]]) -> None:
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


def generate_updates(limit: int) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    global SOURCE_PROFILE_BY_ID
    rows = read_candidate_rows()
    SOURCE_PROFILE_BY_ID = build_source_profiles(rows)
    public_rows = build_update_items(rows, limit)
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

    write_feed_data_js(public_rows, categorized)
    write_api_files(public_rows, categorized)
    write_homepage_latest(public_rows, categorized)
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


def render_home_feed_item(item: dict[str, Any]) -> str:
    image = item.get("image_url")
    thumb_html = (
        f'<span class="home-feed-thumb"><img src="{html_escape(image)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>'
        if image
        else ""
    )
    excerpt = homepage_excerpt(item.get("text"), limit=260, max_lines=4, skip_first=True)
    excerpt_html = f'<span class="feed-latest-excerpt">{excerpt}</span>' if excerpt else ""
    category_html = render_category_pills(item)
    return f"""
      <article class="home-feed-card">
        <div class="home-feed-source">
          {render_source_avatar(item)}
          <div>
            <span class="feed-latest-meta">{html_escape(item.get("posted_at_local") or "未標示")} · {html_escape(item.get("platform") or "public")}</span>
            <strong>{html_escape(item.get("source") or "公開來源")}</strong>
          </div>
        </div>
        <a class="home-feed-body" href="{html_escape(item.get("link"))}" target="_blank" rel="noreferrer">
          <span class="home-feed-copy">
            <h3>{html_escape(item.get("headline") or item.get("title") or "公開更新")}</h3>
            {excerpt_html}
          </span>
          {thumb_html}
        </a>
        <div class="home-feed-footer">
          <div class="entry-meta">{category_html}</div>
          <a class="feed-open-link" href="{html_escape(item.get("link"))}" target="_blank" rel="noreferrer">開啟來源</a>
        </div>
      </article>
    """


def render_home_feed_links(categorized: dict[str, list[dict[str, Any]]]) -> str:
    links = [
        f'<a href="{html_escape(feed_page_url(category))}">{html_escape(category["short_title"])} {len(categorized.get(category["id"], []))} 筆</a>'
        for category in FEED_CATEGORIES
    ]
    links.append('<a href="/feeds/">全部 RSS</a>')
    return f"""
      <div class="feed-filter-row">
        <span class="feed-filter-label">分類 feed</span>
        <div class="feed-links">{"".join(links)}</div>
      </div>
    """


def write_homepage_latest(public_rows: list[dict[str, Any]], categorized: dict[str, list[dict[str, Any]]]) -> None:
    start = "            <!-- FEED_LATEST_START -->"
    end = "            <!-- FEED_LATEST_END -->"
    text = HOME_PAGE.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return
    item_html = "\n".join(render_home_feed_item(item) for item in public_rows[:8])
    if not item_html:
        item_html = '<div class="empty-state">目前沒有近期待觀測項目。</div>'
    latest_html = render_home_feed_links(categorized) + "\n" + item_html
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
                  {render_source_avatar(item, "source-avatar source-avatar-small")}
                  <div>
                    <p class="feed-item-meta">{html_escape(item.get("posted_at_local") or "未標示")} · {html_escape(item.get("platform") or "public")}</p>
                    <strong>{html_escape(item.get("source"))}</strong>
                  </div>
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
          <a href="{html_escape(feed_page_url(category))}">看頁面</a>
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
        <a href="/#directory">名錄</a>
        <a href="/feeds/">RSS</a>
        <a href="/#submit">投稿修正</a>
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
        <a href="/#directory">名錄</a>
        <a href="/feeds/">RSS</a>
        <a href="/#submit">投稿修正</a>
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
              <a href="/feeds/sources.xml">來源名錄 RSS</a>
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


def generate_sources(limit: int) -> int:
    data = parse_site_data(SITE_DATA)
    entries = data.get("entries", [])[:limit]
    now = dt.datetime.now(dt.timezone.utc)
    rss = build_channel(
        "臺灣口琴觀測站：公開來源名錄",
        "公開口琴社團、團體、演奏者、教學與場館來源名錄。",
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
        description = "\n".join(
            part
            for part in [
                f"分類：{entry.get('category') or '未分類'}",
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
    parser.add_argument("--updates-limit", type=int, default=50)
    parser.add_argument("--sources-limit", type=int, default=150)
    args = parser.parse_args()

    updates, categorized = generate_updates(args.updates_limit)
    sources_count = generate_sources(args.sources_limit)
    print(
        json.dumps(
            {
                "updates": len(updates),
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
