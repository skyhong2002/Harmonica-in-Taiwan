#!/usr/bin/env python3
"""Pre-render static SEO landing pages and dynamically rebuild sitemap.xml."""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import generate_rss_feeds as feed_render

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"

SOURCES_JSON = SITE_ROOT / "api" / "sources.json"
EVENTS_JSON = SITE_ROOT / "api" / "public-calendar-events.json"
SCORES_JSON = SITE_ROOT / "api" / "scores.json"
SITEMAP_XML = SITE_ROOT / "sitemap.xml"

# Shared HTML parts
HEADER_HTML = """    <header class="site-header">
      <a class="brand" href="/" aria-label="臺灣口琴觀測站首頁">
        <img class="brand-logo" src="/assets/logo.svg?v=20260704-avatar" alt="臺灣口琴觀測站" width="200" height="47">
      </a>
      <nav class="site-nav" aria-label="主要導覽">
        <a href="/post/">公開貼文</a>
        <a href="/source/">公開來源</a>
        <a href="/scores/">比賽指定曲</a>
        <a href="/status/">狀態</a>
      </nav>
    </header>"""

FOOTER_HTML = """    <footer class="site-footer">
      <div class="site-footer-inner">
        <div class="footer-brand">
          <span class="footer-title">臺灣口琴觀測站</span>
          <p>公開口琴活動、社團、貼文影片與補助資訊索引。</p>
        </div>
        <nav class="footer-links" aria-label="頁尾導覽">
          <a href="/feeds/">RSS</a>
          <a href="/submit/">資料回報</a>
          <a href="/api/latest.json">API</a>
          <a href="/sitemap.xml">Sitemap</a>
          <a href="https://github.com/skyhong2002/Harmonica-in-Taiwan" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
        <p class="footer-meta">只收錄公開可查資料 · 由 <a href="https://www.facebook.com/nycubmhc/" target="_blank" rel="noreferrer">陽明交大竹韻口琴社</a> 維運 · MIT License · © 2026 Sky Hong</p>
      </div>
    </footer>"""


def clean(val: str | None) -> str:
    return (val or "").strip()


def normalize_generated_html(content: str) -> str:
    return "\n".join(line.rstrip() for line in content.splitlines()) + "\n"


def escape(val: str | None) -> str:
    return html.escape(clean(val))


def file_lastmod(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def newest_lastmod(paths: list[Path]) -> str:
    existing_paths = [path for path in paths if path.exists()]
    if not existing_paths:
        return datetime.now().date().isoformat()
    newest_mtime = max(path.stat().st_mtime for path in existing_paths)
    return datetime.fromtimestamp(newest_mtime).date().isoformat()


def format_update_card(up: dict[str, Any], index: int) -> str:
    item = dict(up)
    item["matched_keywords"] = [
        keyword for keyword in item.get("matched_keywords", []) if keyword != "口琴"
    ]
    item.setdefault("link", "#")
    return feed_render.render_home_feed_item(item, index=index)

def format_score_row(score: dict[str, Any]) -> str:
    year = escape(score.get("schoolYear") or "-")
    status = escape(score.get("sourceStatus") or "-")
    program = escape(score.get("program") or "-")
    division = escape(score.get("division") or "-")
    title = escape(score.get("title") or "-")
    composer = escape(score.get("composer") or "-")
    arranger = escape(score.get("arranger") or "-")
    publisher = escape(score.get("publisher") or "-")
    note = escape(score.get("notes") or score.get("performanceNote") or "-")

    links = score.get("links") or []
    source_link = links[0].get("url") if links else ""
    source_label = links[0].get("label") if links else "來源"

    source_html = f'<a href="{escape(source_link)}" target="_blank" rel="noreferrer" style="color: var(--primary, #1a73e8); text-decoration: underline;">{escape(source_label)}</a>' if source_link else '<span style="color:#999;">-</span>'

    return f"""
          <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: center;">{year}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: center;">{status}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{program}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{division}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; font-weight: bold;">{title}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{composer}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{arranger}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{publisher}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; font-size: 0.85rem; color:#555;">{note}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: center;">{source_html}</td>
          </tr>
"""

def format_scores_table(scores: list[dict[str, Any]]) -> str:
    rows = "".join(format_score_row(s) for s in scores)
    return f"""
    <div style="overflow-x: auto; margin-top: 1rem;">
      <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem;">
        <thead>
          <tr style="background: #f8faf8; border-bottom: 2px solid #ccc;">
            <th style="padding: 10px; text-align: center;">學年度</th>
            <th style="padding: 10px; text-align: center;">狀態</th>
            <th style="padding: 10px;">項目</th>
            <th style="padding: 10px;">組別</th>
            <th style="padding: 10px;">曲目</th>
            <th style="padding: 10px;">作曲</th>
            <th style="padding: 10px;">編曲</th>
            <th style="padding: 10px;">出版社</th>
            <th style="padding: 10px;">備註</th>
            <th style="padding: 10px; text-align: center;">來源</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
"""


def source_related_link(other: dict[str, Any]) -> str:
    other_name = escape(other.get("name"))
    other_slug = make_slug(other)
    return f'<li><a href="/source/{other_slug}/">{other_name}</a></li>'


def source_related_panel(panel_id: str, label: str, sources: list[dict[str, Any]], active: bool = False) -> str:
    if sources:
        body = f'<ul class="source-related-list">{"".join(source_related_link(other) for other in sources)}</ul>'
    else:
        body = '<p class="source-related-empty">暫無其他來源</p>'
    hidden_attr = "" if active else " hidden"
    return f"""
              <div class="source-related-panel" data-source-related-panel="{escape(panel_id)}"{hidden_attr}>
                <h4>{escape(label)}</h4>
                {body}
              </div>
"""


def source_related_facets(entry: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entry_id = clean(entry.get("id"))
    facets: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_facet(kind: str, label: str, values: set[str]) -> None:
        cleaned_values = {clean(value) for value in values if clean(value)}
        if not cleaned_values:
            return
        key = f"{kind}:{label.casefold()}"
        if key in seen:
            return
        seen.add(key)
        related = []
        for other in entries:
            if clean(other.get("id")) == entry_id:
                continue
            other_values = source_facet_values(other, kind)
            if cleaned_values.intersection(other_values):
                related.append(other)
            if len(related) >= 6:
                break
        facets.append({"id": f"related-{len(facets)}", "kind": kind, "label": label, "sources": related})

    country = clean(entry.get("country"))
    if country:
        add_facet("country", country, {country})

    region_parts = [part.strip() for part in re.split(r"[/／；;、,，]", clean(entry.get("region"))) if part.strip()]
    for part in region_parts:
        if part and part != country:
            add_facet("region", part, {part})

    for tag in entry.get("sourceTags") or []:
        tag_label = f"#{clean(tag).lstrip('#')}"
        add_facet("tag", tag_label, {clean(tag).lstrip("#")})

    return facets


def source_facet_values(entry: dict[str, Any], kind: str) -> set[str]:
    if kind == "country":
        return {clean(entry.get("country"))}
    if kind == "region":
        values = set()
        values.update(part.strip() for part in re.split(r"[/／；;、,，]", clean(entry.get("region"))) if part.strip())
        return values
    if kind == "tag":
        return {clean(tag).lstrip("#") for tag in entry.get("sourceTags") or []}
    return set()


def encoded_path_part(value: str) -> str:
    return urllib.parse.quote(clean(value), safe="")


def source_region_values(entry: dict[str, Any], country_values: set[str] | None = None) -> set[str]:
    values: set[str] = set()
    countries = country_values or {clean(entry.get("country"))}
    country_keys = {value.casefold() for value in countries if value}
    for part in re.split(r"[/／；;、,，]", clean(entry.get("region"))):
        region = part.strip()
        if not region:
            continue
        if region.casefold() in country_keys:
            continue
        values.add(region)
    return values


def source_facet_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        {
            "kind": "category",
            "label": "類別",
            "path": "category",
            "page_title": "口琴公開來源類別",
            "value_fn": lambda entry: {clean(entry.get("category"))} if clean(entry.get("category")) else set(),
        },
        {
            "kind": "region",
            "label": "地區",
            "path": "region",
            "page_title": "口琴公開來源地區",
            "value_fn": source_region_values,
        },
        {
            "kind": "tag",
            "label": "Tag",
            "path": "tag",
            "page_title": "口琴公開來源 tag",
            "value_fn": lambda entry: {clean(tag).lstrip("#") for tag in entry.get("sourceTags") or [] if clean(tag)},
        },
    ]
    groups: list[dict[str, Any]] = []
    for spec in specs:
        value_entries: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            for value in spec["value_fn"](entry):
                if value:
                    value_entries.setdefault(value, []).append(entry)
        values = [
            {"value": value, "entries": value_entries[value]}
            for value in sorted(value_entries, key=lambda item: (-len(value_entries[item]), item))
            if len(value_entries[value]) >= 2
        ]
        groups.append({**spec, "values": values})
    return groups


def generate_source_page(
    entry: dict[str, Any],
    entry_updates: list[dict[str, Any]],
    related_facets: list[dict[str, Any]],
) -> str:
    entry_id = escape(entry.get("id"))
    slug = make_slug(entry)
    name = escape(entry.get("name"))
    name_en = escape(entry.get("nameEn"))
    category = escape(entry.get("category"))
    entry_type = escape(entry.get("type"))
    original_type = escape(entry.get("originalType"))
    country = escape(entry.get("country"))
    region = escape(entry.get("region"))
    city_focus = escape(entry.get("cityOrFocus"))
    summary = escape(entry.get("summary") or entry.get("structuredSummary"))
    avatar_url = clean(entry.get("avatarUrl"))
    initials = escape(entry.get("sourceInitials") or (name[0] if name else "H"))

    # JSON-LD
    schema_type = "Organization"
    if category == "演奏者":
        schema_type = "Person"
    elif category in ("學校社團", "樂團", "教學單位", "教學工作室"):
        schema_type = "MusicGroup"

    json_ld_dict = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": entry.get("name"),
        "url": f"https://harmonica.observe.tw/source/{slug}/",
        "description": entry.get("summary") or entry.get("structuredSummary") or ""
    }
    if entry.get("nameEn"):
        json_ld_dict["alternateName"] = entry["nameEn"]

    links = entry.get("links") or []
    if links:
        json_ld_dict["sameAs"] = [link["url"] for link in links if link.get("url")]

    json_ld = json.dumps(json_ld_dict, ensure_ascii=False, indent=2)

    # Breadcrumb JSON-LD
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "首頁",
                "item": "https://harmonica.observe.tw/"
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "公開來源",
                "item": "https://harmonica.observe.tw/source/"
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": entry.get("name"),
                "item": f"https://harmonica.observe.tw/source/{slug}/"
            }
        ]
    }
    json_ld_breadcrumb = json.dumps(breadcrumb_ld, ensure_ascii=False, indent=2)

    # Avatar HTML
    if avatar_url:
        avatar_html = f"""<span class="source-avatar entry-avatar" style="width: 80px; height: 80px; font-size: 2rem; margin-right: 1.5rem;">
  <img src="{escape(avatar_url)}" alt="{name} 頭貼" referrerpolicy="no-referrer">
 </span>"""
    else:
        avatar_html = f"""<span class="source-avatar entry-avatar source-avatar-fallback" style="width: 80px; height: 80px; font-size: 2rem; margin-right: 1.5rem; display: flex; align-items: center; justify-content: center; background: var(--bg-muted, #f0f0f0); border-radius: 50%; color: var(--text-muted, #666);" aria-hidden="true">{initials}</span>"""

    # Optional Rows
    name_en_html = f'<p class="entry-en" style="font-size: 1.1rem; opacity: 0.8; margin-top: 0.2rem;">{name_en}</p>' if name_en and name_en != name else ""
    country_row = f'<tr><th scope="row" style="padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">國家</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{country}</td></tr>' if country else ""
    region_row = f'<tr><th scope="row" style="padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">地區</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{region}</td></tr>' if region and region != country else ""
    city_row = f'<tr><th scope="row" style="padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">城市 / 焦點</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{city_focus}</td></tr>' if city_focus else ""
    original_type_row = f'<tr><th scope="row" style="padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">說明</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{original_type}</td></tr>' if original_type and original_type != entry_type else ""

    tags = entry.get("sourceTags") or []
    tags_row = ""
    if tags:
        tag_pills = " ".join(f'<span class="pill hashtag-chip">#{escape(t)}</span>' for t in tags)
        tags_row = f'<tr><th scope="row" style="padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">標籤</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{tag_pills}</td></tr>'

    aliases = entry.get("aliases") or []
    aliases_row = ""
    if aliases:
        aliases_row = f'<tr><th scope="row" style="padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">別名</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{escape("、".join(aliases))}</td></tr>'

    links_html = ""
    if links:
        links_list = []
        for link in links:
            url = escape(link.get("url"))
            label = escape(link.get("label") or "連結")
            links_list.append(f'<a href="{url}" target="_blank" rel="noreferrer">{label}</a>')
        links_html = f'<div class="feed-links source-contact-links">{" ".join(links_list)}</div>'
    else:
        links_html = '<p style="color: var(--text-muted, #666);">暫無公開社群連結</p>'

    og_image = f"https://harmonica.observe.tw{avatar_url}" if avatar_url and avatar_url.startswith("/") else "https://harmonica.observe.tw/assets/hero-harmonica-observe.webp"

    # Related Updates Section
    updates_html = ""
    if entry_updates:
        cards_html = "".join(format_update_card(up, index) for index, up in enumerate(entry_updates))
        updates_html = f"""
            <h2 class="source-detail-title">近期公開更新</h2>
            <div class="source-updates-grid" data-source-feed-grid>
              {cards_html}
            </div>
"""

    if related_facets:
        chips_html = "".join(
            f'<button type="button" class="feed-option-chip source-related-chip" data-source-related-chip="{escape(facet["id"])}" aria-pressed="{"true" if index == 0 else "false"}" data-filter-state="{"include" if index == 0 else "off"}">{escape(facet["label"])}</button>'
            for index, facet in enumerate(related_facets)
        )
        panels_html = "".join(
            source_related_panel(facet["id"], facet["label"], facet["sources"], active=index == 0)
            for index, facet in enumerate(related_facets)
        )
        related_body = f"""
              <div class="source-related-chips" role="listbox" aria-label="相關來源條件">
                {chips_html}
              </div>
              <div class="source-related-panels">
                {panels_html}
              </div>
"""
    else:
        related_body = '<p class="source-related-empty">暫無可探索的相關來源</p>'

    related_sources_section = f"""
            <h2 class="source-detail-title">探索相關來源</h2>
            <div class="source-related" data-source-related>
              {related_body}
            </div>
"""

    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{name}｜口琴公開來源｜臺灣口琴觀測站</title>
    <meta name="description" content="{summary}">
    <link rel="canonical" href="https://harmonica.observe.tw/source/{slug}/">
    <meta property="og:title" content="{name}｜口琴公開來源｜臺灣口琴觀測站">
    <meta property="og:description" content="{summary}">
    <meta property="og:type" content="profile">
    <meta property="og:url" content="https://harmonica.observe.tw/source/{slug}/">
    <meta property="og:image" content="{og_image}">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{name}｜口琴公開來源｜臺灣口琴觀測站">
    <meta name="twitter:description" content="{summary}">
    <meta name="twitter:image" content="{og_image}">
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260704-avatar">
    <script type="application/ld+json">
{json_ld}
    </script>
    <script type="application/ld+json">
{json_ld_breadcrumb}
    </script>
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
      <nav aria-label="breadcrumb" class="breadcrumb-nav" style="font-size: 0.9rem; margin: 1rem auto; max-width: 1200px; padding: 0 1rem; color: var(--text-muted, #666);">
        <a href="/" style="color: var(--primary, #1a73e8); text-decoration: none;">首頁</a> ›
        <a href="/source/" style="color: var(--primary, #1a73e8); text-decoration: none;">公開來源</a> ›
        <span>{name}</span>
      </nav>

      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div class="source-hero-head" style="display: flex; align-items: center;">
            {avatar_html}
            <div>
              <p class="section-kicker" style="text-transform: uppercase; font-size: 0.9rem; letter-spacing: 0.05em; color: var(--primary, #1a73e8); font-weight: bold; margin: 0;">{entry_type}</p>
              <h1 style="margin: 0.3rem 0 0 0; font-size: 2.2rem; font-weight: 800;">{name}</h1>
              {name_en_html}
            </div>
          </div>
          <div class="feed-page-summary">
            <p style="font-size: 1.1rem; line-height: 1.6; margin: 0 0 1.5rem 0;">{summary}</p>
            <div class="feed-links">
              <a href="/source/">返回公開來源列表</a>
              <a href="/">前往首頁</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band">
        <div class="band-inner">
          <div class="source-detail-card card" style="background: var(--bg-card, #ffffff); border-radius: 8px; padding: 2rem; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 2rem;">
            <h2 class="source-detail-title" style="font-size: 1.5rem; font-weight: 700; border-bottom: 2px solid var(--primary, #1a73e8); padding-bottom: 0.5rem; margin-top: 0; margin-bottom: 1.5rem;">基本資訊</h2>
            <table class="source-detail-table" style="width: 100%; border-collapse: collapse; margin-bottom: 2.5rem;">
              <tbody>
                <tr>
                  <th scope="row" style="width: 25%; padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">類型</th>
                  <td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{entry_type}</td>
                </tr>
                {original_type_row}
                {country_row}
                {region_row}
                {city_row}
                {tags_row}
                {aliases_row}
              </tbody>
            </table>

            <h2 class="source-detail-title">公開聯絡與社群連結</h2>
            {links_html}

            {updates_html}
            {related_sources_section}
          </div>
        </div>
      </section>
    </main>

{FOOTER_HTML}
    <script src="/assets/app.js?v=20260704-avatar"></script>
  </body>
</html>
"""


def generate_event_page(event: dict[str, Any]) -> str:
    event_id = escape(event.get("id"))
    title = escape(event.get("title") or event.get("eventName") or "公開口琴活動")
    start = escape(event.get("start"))
    end = escape(event.get("end"))
    location = escape(event.get("location") or "臺灣")
    details = escape(event.get("details"))
    evidence_url = clean(event.get("evidenceUrl"))
    all_day = bool(event.get("allDay"))
    source = escape(event.get("source"))

    time_label = start
    if end and end != start:
        time_label = f"{start} 至 {end}"
    if all_day:
        time_label += " (全天活動)"

    description = f"公開口琴演出活動「{title}」，時間：{time_label}，地點：{location}。"
    if details:
        description += f" 活動內容：{details}"
    description = description[:250]

    # JSON-LD
    json_ld_dict = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.get("title") or event.get("eventName") or "公開口琴活動",
        "startDate": event.get("start"),
        "endDate": event.get("end") or event.get("start"),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": event.get("location") or "臺灣",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "TW"
            }
        },
        "description": event.get("details") or event.get("title") or ""
    }
    if evidence_url:
        json_ld_dict["offers"] = {
            "@type": "Offer",
            "url": evidence_url,
            "availability": "https://schema.org/InStock"
        }
    json_ld = json.dumps(json_ld_dict, ensure_ascii=False, indent=2)

    # Breadcrumb JSON-LD
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "首頁",
                "item": "https://harmonica.observe.tw/"
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "公開貼文",
                "item": "https://harmonica.observe.tw/post/"
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": title,
                "item": f"https://harmonica.observe.tw/event/{event_id}/"
            }
        ]
    }
    json_ld_breadcrumb = json.dumps(breadcrumb_ld, ensure_ascii=False, indent=2)

    # rows
    location_row = f'<tr><th scope="row" style="width: 25%; padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">地點</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{location}</td></tr>' if location else ""
    source_row = f'<tr><th scope="row" style="width: 25%; padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">資訊來源</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{source}</td></tr>' if source else ""
    details_row = f'<tr><th scope="row" style="width: 25%; padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">活動說明</th><td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{details}</td></tr>' if details else ""

    action_button = ""
    if evidence_url:
        action_button = f"""<div style="margin-top: 2rem; display: flex; gap: 10px;">
  <a href="{escape(evidence_url)}" target="_blank" rel="noreferrer" class="primary-link" style="display: inline-block; padding: 10px 20px; background: var(--primary, #1a73e8); color: white; border-radius: 4px; text-decoration: none; font-weight: bold;">查看原始貼文/購票連結</a>
</div>"""

    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}｜臺灣口琴公開演出｜臺灣口琴觀測站</title>
    <meta name="description" content="{description}">
    <link rel="canonical" href="https://harmonica.observe.tw/event/{event_id}/">
    <meta property="og:title" content="{title}｜臺灣口琴公開演出">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://harmonica.observe.tw/event/{event_id}/">
    <meta property="og:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}｜臺灣口琴公開演出">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260704-avatar">
    <script type="application/ld+json">
{json_ld}
    </script>
    <script type="application/ld+json">
{json_ld_breadcrumb}
    </script>
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
      <nav aria-label="breadcrumb" class="breadcrumb-nav" style="font-size: 0.9rem; margin: 1rem auto; max-width: 1200px; padding: 0 1rem; color: var(--text-muted, #666);">
        <a href="/" style="color: var(--primary, #1a73e8); text-decoration: none;">首頁</a> ›
        <a href="/post/" style="color: var(--primary, #1a73e8); text-decoration: none;">公開貼文</a> ›
        <span>{title}</span>
      </nav>

      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker" style="text-transform: uppercase; font-size: 0.9rem; letter-spacing: 0.05em; color: var(--primary, #1a73e8); font-weight: bold; margin: 0;">公開活動演出</p>
            <h1 style="margin: 0.3rem 0 0 0; font-size: 2.2rem; font-weight: 800;">{title}</h1>
          </div>
          <div class="feed-page-summary">
            <p style="font-size: 1.1rem; line-height: 1.6; margin: 0 0 1.5rem 0;">{description}</p>
            <div class="feed-links">
              <a href="/">返回演出日曆</a>
              <a href="/post/">看公開貼文</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band">
        <div class="band-inner">
          <div class="event-detail-card card" style="background: var(--bg-card, #ffffff); border-radius: 8px; padding: 2rem; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 2rem;">
            <h2 class="source-detail-title" style="font-size: 1.5rem; font-weight: 700; border-bottom: 2px solid var(--primary, #1a73e8); padding-bottom: 0.5rem; margin-top: 0; margin-bottom: 1.5rem;">活動詳情</h2>
            <table class="source-detail-table" style="width: 100%; border-collapse: collapse;">
              <tbody>
                <tr>
                  <th scope="row" style="width: 25%; padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">時間</th>
                  <td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{time_label}</td>
                </tr>
                {location_row}
                {source_row}
                {details_row}
              </tbody>
            </table>

            {action_button}
          </div>
        </div>
      </section>
    </main>

{FOOTER_HTML}
  </body>
</html>
"""


def generate_scores_category_page(category: str, items: list[dict[str, Any]]) -> str:
    encoded_category = urllib.parse.quote(category)
    description = f"整理全國學生音樂比賽口琴項目{escape(category)}指定曲，包含學年度、組別、曲名、作曲者、出版社與公開佐證來源。"

    # JSON-LD Dataset
    json_ld_dict = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"學生音樂比賽口琴項目【{category}】歷年指定曲索引",
        "description": f"收錄臺灣全國學生音樂比賽口琴項目「{category}」歷年指定曲名稱、作曲、編曲及公開出版、購譜線索之索引數據。",
        "url": f"https://harmonica.observe.tw/scores/{encoded_category}/",
        "license": "https://opensource.org/licenses/MIT",
        "creator": {
            "@type": "Organization",
            "name": "臺灣口琴觀測站"
        }
    }
    json_ld = json.dumps(json_ld_dict, ensure_ascii=False, indent=2)

    # Breadcrumb JSON-LD
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "首頁",
                "item": "https://harmonica.observe.tw/"
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "比賽指定曲",
                "item": "https://harmonica.observe.tw/scores/"
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": f"{category}指定曲",
                "item": f"https://harmonica.observe.tw/scores/{encoded_category}/"
            }
        ]
    }
    json_ld_breadcrumb = json.dumps(breadcrumb_ld, ensure_ascii=False, indent=2)

    # Render rows
    rows_list = []
    for item in items:
        year = escape(item.get("schoolYear") or "-")
        status = escape(item.get("sourceStatus") or "-")
        division = escape(item.get("division") or "-")

        title_main = clean(item.get("title"))
        title_alt = clean(item.get("titleAlt"))
        title_display = title_main
        if title_alt and title_alt != title_main:
            title_display = f"{title_main} ({title_alt})"
        title_display = escape(title_display)

        composer = escape(item.get("composer") or "-")
        arranger = escape(item.get("arranger") or "-")
        publisher = escape(item.get("publisher") or "-")
        purchase_note = escape(item.get("purchaseNote") or "-")

        links = item.get("links") or []
        source_link_html = "-"
        if links:
            source_link_html = f'<a class="score-source-link" href="{escape(links[0]["url"])}" target="_blank" rel="noreferrer">{escape(links[0].get("label") or "官方來源")}</a>'

        rows_list.append(f"""                <tr style="border-bottom: 1px solid var(--border-color, #e0e0e0); font-size: 0.95rem;">
                  <td style="padding: 12px 8px;">{year}</td>
                  <td style="padding: 12px 8px;">{status}</td>
                  <td style="padding: 12px 8px;">{division}</td>
                  <th scope="row" style="padding: 12px 8px; text-align: left; font-weight: normal;">{title_display}</th>
                  <td style="padding: 12px 8px;">{composer}</td>
                  <td style="padding: 12px 8px;">{arranger}</td>
                  <td style="padding: 12px 8px;">{publisher}</td>
                  <td style="padding: 12px 8px; font-size: 0.85rem; max-width: 250px; overflow-wrap: break-word;">{purchase_note}</td>
                  <td style="padding: 12px 8px;">{source_link_html}</td>
                </tr>""")

    table_rows = "\n".join(rows_list)

    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(category)}指定曲索引｜全國學生音樂比賽指定曲｜臺灣口琴觀測站</title>
    <meta name="description" content="{description}">
    <link rel="canonical" href="https://harmonica.observe.tw/scores/{encoded_category}/">
    <meta property="og:title" content="{escape(category)}指定曲索引｜全國學生音樂比賽指定曲｜臺灣口琴觀測站">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://harmonica.observe.tw/scores/{encoded_category}/">
    <meta property="og:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape(category)}指定曲索引｜全國學生音樂比賽指定曲｜臺灣口琴觀測站">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260704-avatar">
    <script type="application/ld+json">
{json_ld}
    </script>
    <script type="application/ld+json">
{json_ld_breadcrumb}
    </script>
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
      <nav aria-label="breadcrumb" class="breadcrumb-nav" style="font-size: 0.9rem; margin: 1rem auto; max-width: 1200px; padding: 0 1rem; color: var(--text-muted, #666);">
        <a href="/" style="color: var(--primary, #1a73e8); text-decoration: none;">首頁</a> ›
        <a href="/scores/" style="color: var(--primary, #1a73e8); text-decoration: none;">比賽指定曲</a> ›
        <span>{escape(category)}指定曲</span>
      </nav>

      <section class="feed-page-hero score-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">全國學生音樂比賽</p>
            <h1>{escape(category)}指定曲索引</h1>
          </div>
          <div class="feed-page-summary">
            <p>全國學生音樂比賽口琴項目指定曲「{escape(category)}」歷年指定曲與公開出版、購譜或洽詢管道。本頁共收錄 {len(items)} 筆指定曲線索。</p>
            <div class="feed-links">
              <a href="/scores/">看全部指定曲</a>
              <a href="/scores/sources/">看口琴譜源</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band score-band">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Pieces List</p>
              <h2>{escape(category)} 歷年指定曲項目</h2>
            </div>
          </div>

          <div class="score-list-container" style="overflow-x: auto; background: var(--bg-card, #ffffff); border-radius: 8px; padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <table class="score-table" style="width: 100%; min-width: 900px; border-collapse: collapse; text-align: left;">
              <thead>
                <tr style="border-bottom: 2px solid var(--primary, #1a73e8); font-weight: bold;">
                  <th scope="col" style="padding: 12px 8px; width: 80px;">學年度</th>
                  <th scope="col" style="padding: 12px 8px; width: 80px;">狀態</th>
                  <th scope="col" style="padding: 12px 8px; width: 100px;">類組</th>
                  <th scope="col" style="padding: 12px 8px;">曲名</th>
                  <th scope="col" style="padding: 12px 8px; width: 120px;">作曲者</th>
                  <th scope="col" style="padding: 12px 8px; width: 120px;">編曲者</th>
                  <th scope="col" style="padding: 12px 8px; width: 150px;">出版/洽詢單位</th>
                  <th scope="col" style="padding: 12px 8px;">購譜線索</th>
                  <th scope="col" style="padding: 12px 8px; width: 80px;">來源</th>
                </tr>
              </thead>
              <tbody>
                {table_rows}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>

{FOOTER_HTML}
  </body>
</html>
"""


def make_slug(entry: dict[str, Any]) -> str:
    entry_id = source_public_id(entry)
    name_en = clean(entry.get("nameEn"))
    name = clean(entry.get("name"))
    text = name_en if name_en else name
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if text:
        return f"{entry_id}-{text}"
    return entry_id


def source_public_id(entry: dict[str, Any]) -> str:
    entry_id = clean(entry.get("id"))
    match = re.match(r"^watchlist-(\d+)$", entry_id)
    if match:
        return match.group(1)
    return entry_id


def extract_date(timestamp_str: str | None) -> str | None:
    if not timestamp_str:
        return None
    match = re.match(r"^\d{4}-\d{2}-\d{2}", timestamp_str.strip())
    if match:
        return match.group(0)
    return None


def generate_sitemap_xml(
    sources: list[dict[str, Any]],
    events: list[dict[str, Any]],
    categories: list[str],
    updates: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    source_groups: list[dict[str, Any]] | None = None,
) -> str:
    url_templates = []
    events_lastmod = file_lastmod(EVENTS_JSON)
    build_date_fallback = datetime.now(timezone(timedelta(hours=8))).date().isoformat()

    # Load score sources for lastmod calculation
    score_sources = []
    try:
        SCORE_SOURCES_JSON = SITE_ROOT / "api" / "score-sources.json"
        if SCORE_SOURCES_JSON.exists():
            score_sources = json.loads(SCORE_SOURCES_JSON.read_text(encoding="utf-8")).get("scoreSources") or []
    except Exception:
        pass

    # Extract dynamic timestamps
    post_dates = [extract_date(up.get("posted_at") or up.get("posted_at_local")) for up in updates]
    newest_post = max([d for d in post_dates if d], default=build_date_fallback)

    source_dates = [extract_date(s.get("latestUpdateAt") or s.get("latestUpdateLocal")) for s in sources]
    newest_source = max([d for d in source_dates if d], default=build_date_fallback)

    score_dates = [extract_date(s.get("lastVerifiedAt")) for s in scores]
    newest_score = max([d for d in score_dates if d], default=build_date_fallback)

    score_source_dates = [extract_date(s.get("lastSeenAt")) for s in score_sources]
    newest_score_source = max([d for d in score_source_dates if d], default=build_date_fallback)

    core_lastmods = {
        "": newest_post,
        "post/": newest_post,
        "source/": newest_source,
        "scores/": newest_score,
        "scores/sources/": newest_score_source,
        "feeds/": newest_post,
        "submit/": file_lastmod(SITE_ROOT / "submit" / "index.html") if (SITE_ROOT / "submit" / "index.html").exists() else build_date_fallback,
        "status/": file_lastmod(SITE_ROOT / "api" / "status.json") if (SITE_ROOT / "api" / "status.json").exists() else build_date_fallback,
    }

    # 8 Core Pages
    core_pages = [
        ("", "daily", "1.0"),
        ("post/", "daily", "0.8"),
        ("source/", "weekly", "0.8"),
        ("scores/", "weekly", "0.8"),
        ("scores/sources/", "weekly", "0.8"),
        ("feeds/", "daily", "0.6"),
        ("submit/", "monthly", "0.5"),
        ("status/", "daily", "0.5"),
    ]
    for path, freq, priority in core_pages:
        url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/{path}</loc>
    <lastmod>{core_lastmods[path]}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    # Category Pages
    for category in categories:
        encoded = urllib.parse.quote(category)
        cat_scores = [s for s in scores if clean(s.get("program")) == category]
        cat_dates = [extract_date(s.get("lastVerifiedAt")) for s in cat_scores]
        cat_lastmod = max([d for d in cat_dates if d], default=newest_score)
        url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/scores/{encoded}/</loc>
    <lastmod>{cat_lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")

    # Source Pages
    for src in sources:
        src_id = clean(src.get("id"))
        if src_id:
            slug = make_slug(src)
            src_date = extract_date(src.get("latestUpdateAt") or src.get("latestUpdateLocal"))
            src_lastmod = src_date if src_date else newest_source
            url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/source/{slug}/</loc>
    <lastmod>{src_lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>""")

    # Source facet landing pages
    for group in source_groups or []:
        for facet in group.get("values") or []:
            value = clean(facet.get("value"))
            if not value:
                continue
            encoded = encoded_path_part(value)
            url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/source/{group["path"]}/{encoded}/</loc>
    <lastmod>{newest_source}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.65</priority>
  </url>""")

    # Event Pages
    for ev in events:
        ev_id = clean(ev.get("id"))
        if ev_id:
            ev_date = extract_date(ev.get("postedAt"))
            ev_lastmod = ev_date if ev_date else events_lastmod
            url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/event/{ev_id}/</loc>
    <lastmod>{ev_lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>""")

    url_content = "\n".join(url_templates)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_content}
</urlset>
"""


def format_feed_time(value: str) -> str:
    if not value or value == "-":
        return "-"
    try:
        dt_part = value.split("T")
        if len(dt_part) == 2:
            date_str = dt_part[0]
            time_str = dt_part[1][:5]
            if "+00:00" in value or "Z" in value:
                cleaned = value.replace("Z", "+00:00")
                dt_obj = datetime.fromisoformat(cleaned)
                taipei_tz = dt_obj.astimezone(timezone(timedelta(hours=8)))
                return taipei_tz.strftime("%Y-%m-%d %H:%M")
            return f"{date_str} {time_str}"
    except Exception:
        pass
    return value


def replace_stat(content: str, name: str, value: Any) -> str:
    content = re.sub(
        r'(<strong\s+[^>]*data-stat="' + re.escape(name) + r'"[^>]*>)[^<]*(</strong>)',
        rf'\g<1>{value}\g<2>',
        content
    )
    content = re.sub(
        r'(<span\s+[^>]*data-stat="' + re.escape(name) + r'"[^>]*>)[^<]*(</span>)',
        rf'\g<1>{value}\g<2>',
        content
    )
    return content


def render_source_avatar(avatar_url: str | None, source_name: str, initials: str) -> str:
    if avatar_url:
        return f'<span class="source-avatar entry-avatar"><img src="{escape(avatar_url)}" alt="{escape(source_name)} 頭貼" loading="lazy" referrerpolicy="no-referrer"></span>'
    return f'<span class="source-avatar entry-avatar source-avatar-fallback" aria-hidden="true">{escape(initials)}</span>'


def render_hashtag_button(tag: str, className: str) -> str:
    return f'<button type="button" class="{className}" data-directory-hashtag="{escape(tag)}" data-directory-filter="hashtags">#{escape(tag)}</button>'


def render_entry_card_html(entry: dict[str, Any]) -> str:
    name = escape(entry.get("name"))
    name_en = escape(entry.get("nameEn") or "")
    slug = make_slug(entry)
    category = escape(entry.get("category"))
    summary = escape(entry.get("summary") or entry.get("sourceSummary") or entry.get("type") or "公開來源")
    aliases = entry.get("aliases") or []
    aliases_html = f'<p class="entry-aliases">也收錄：{"、".join(escape(a) for a in aliases[:4])}</p>' if aliases else ""
    initials = escape(entry.get("sourceInitials") or (name[0] if name else "H"))

    avatar_html = render_source_avatar(entry.get("avatarUrl"), name, initials)

    countries = "".join(f'<button type="button" class="region-tag-pill" data-directory-hashtag="{escape(entry.get("country"))}" data-directory-filter="country">#{escape(entry.get("country"))}</button>' if entry.get("country") else "")
    region = entry.get("region") or ""
    region_btn = f'<button type="button" class="region-tag-pill" data-directory-hashtag="{escape(region)}" data-directory-filter="region">#{escape(region)}</button>' if region and region != entry.get("country") else ""

    latest = f'<span class="entry-latest">最新 {escape(entry.get("latestUpdateLocal"))}</span>' if entry.get("latestUpdateLocal") else ""
    locations = countries + region_btn
    context_html = f'<div class="entry-context">{locations}{latest}</div>' if locations or latest else ""

    tags = entry.get("sourceTags") or []
    tags_html = f'<div class="entry-tags">{"".join(render_hashtag_button(t, "source-tag-pill") for t in tags[:8])}</div>' if tags else ""

    links = entry.get("links") or []
    links_list = []
    for link in links:
        url = escape(link.get("url"))
        label = escape(link.get("label") or "連結")
        links_list.append(f'<a href="{url}" target="_blank" rel="noreferrer">{label}</a>')
    links_html = f'<div class="entry-links">{"".join(links_list)}</div>'

    return f"""
      <article class="entry-card">
        <div class="entry-card-head">
          {avatar_html}
          <div class="entry-title-block">
            <h3><a href="/source/{slug}/" class="entry-landing-link">{name}</a></h3>
            <p class="entry-en">{name_en}</p>
            {aliases_html}
          </div>
        </div>
        {context_html}
        {tags_html}
        <p class="entry-summary">{summary}</p>
        {links_html}
      </article>
"""


def format_source_item_list_json_ld(
    entries: list[dict[str, Any]],
    name: str = "口琴公開來源索引",
    description: str = "臺灣與海外口琴社團、樂團、演奏者、教學、場館與公開社群來源索引。",
    url: str = "https://harmonica.observe.tw/source/",
) -> str:
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "description": description,
        "url": url,
        "numberOfItems": len(entries),
        "itemListElement": [],
    }
    for index, entry in enumerate(entries, start=1):
        slug = make_slug(entry)
        item = {
            "@type": "ListItem",
            "position": index,
            "name": clean(entry.get("name")),
            "url": f"https://harmonica.observe.tw/source/{slug}/",
        }
        description = clean(entry.get("summary") or entry.get("sourceSummary") or entry.get("type"))
        if description:
            item["description"] = description
        item_list["itemListElement"].append(item)
    json_ld = json.dumps(item_list, ensure_ascii=False, indent=2)
    return f"""    <script type="application/ld+json" data-generated="source-item-list">
{json_ld}
    </script>"""


def format_static_directory_cards(entries: list[dict[str, Any]]) -> str:
    cards = "".join(render_entry_card_html(entry) for entry in entries)
    cards = "\n".join(line.rstrip() for line in cards.splitlines())
    return f"""
            <!-- DIRECTORY_STATIC_START -->
{cards}
            <!-- DIRECTORY_STATIC_END -->
"""


def generate_source_index_base_page() -> str:
    return """<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>公開來源｜臺灣口琴觀測站</title>
    <meta name="description" content="臺灣口琴社團、樂團、演奏者、教學、場館與公開來源索引。">
    <link rel="canonical" href="https://harmonica.observe.tw/source/">
    <meta property="og:title" content="公開來源｜臺灣口琴觀測站">
    <meta property="og:description" content="臺灣口琴社團、樂團、演奏者、教學、場館與公開來源索引。">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://harmonica.observe.tw/source/">
    <meta property="og:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="公開來源｜臺灣口琴觀測站">
    <meta name="twitter:description" content="臺灣口琴社團、樂團、演奏者、教學、場館與公開來源索引。">
    <meta name="twitter:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Dataset",
      "@id": "https://harmonica.observe.tw/source/#dataset",
      "name": "臺灣口琴公開來源與目錄索引",
      "description": "臺灣口琴社團、樂團、演奏者、教學、場館與公開社群/影音來源之 metadata 索引數據庫。",
      "url": "https://harmonica.observe.tw/source/",
      "license": "https://opensource.org/licenses/MIT",
      "creator": {
        "@type": "Organization",
        "name": "臺灣口琴觀測站"
      }
    }
    </script>
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260704-directory-view">
  </head>
  <body>
""" + HEADER_HTML + """

    <main class="feed-page-main">
      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Public Sources</p>
            <h1>公開來源</h1>
          </div>
          <div class="feed-page-summary">
            <p>臺灣與海外口琴社團、樂團、演奏者、教學、場館、活動與公開社群來源索引。</p>
            <div class="feed-links">
              <a href="/feeds/sources.xml">RSS 訂閱</a>
              <a href="/api/sources.json">JSON</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band directory-band" id="directory" aria-labelledby="directory-title">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Directory</p>
              <h2 id="directory-title">公開來源列表</h2>
            </div>
            <p class="data-date" id="result-count">載入公開來源...</p>
          </div>

          <div id="directory-filter-panel" aria-label="公開來源搜尋與篩選"></div>

          <div class="directory-grid" id="directory-list">
          </div>
        </div>
      </section>

      <section class="band source-band" aria-labelledby="sources-title">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Source Boundary</p>
            <h2 id="sources-title">只發布公開可查資料</h2>
          </div>
          <div class="source-points">
            <p>網站只使用公開連結、名稱、類型、地區、樂器與來源標籤。</p>
            <p>內部備註、監看規則、私人憑證、成員資料與非公開曲譜入口不會進入公開資料包。</p>
            <p>不適合公開展示的資料會暫時不顯示。</p>
          </div>
        </div>
      </section>
    </main>

""" + FOOTER_HTML + """

    <script src="/data/site-data.js?v=20260704-avatar"></script>
    <script src="/assets/app.js?v=20260704-directory-view"></script>
  </body>
</html>
"""


def write_source_index_redirect() -> None:
    redirect_url = "https://harmonica.observe.tw/source/"
    redirect_dir = SITE_ROOT / "post" / "source"
    redirect_dir.mkdir(parents=True, exist_ok=True)
    redirect_html = f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url={redirect_url}">
    <link rel="canonical" href="{redirect_url}">
    <title>頁面已移動｜臺灣口琴觀測站</title>
  </head>
  <body>
    <p>公開來源索引已移到 <a href="{redirect_url}">{redirect_url}</a>。</p>
  </body>
</html>
"""
    (redirect_dir / "index.html").write_text(redirect_html, encoding="utf-8")


def generate_source_facet_page(group: dict[str, Any], value: str, entries: list[dict[str, Any]]) -> str:
    path = clean(group["path"])
    encoded_value = encoded_path_part(value)
    label = clean(group["label"])
    title = f"{value}｜{group['page_title']}｜臺灣口琴觀測站"
    description = f"整理公開來源中標示為「{value}」的口琴社團、樂團、演奏者、教學、活動與場館資料，共 {len(entries)} 筆。"
    canonical = f"https://harmonica.observe.tw/source/{path}/{encoded_value}/"
    item_list_script = format_source_item_list_json_ld(
        entries,
        name=f"{value}｜{group['page_title']}",
        description=description,
        url=canonical,
    )
    cards = "\n".join(line.rstrip() for line in "".join(render_entry_card_html(entry) for entry in entries).splitlines())
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "首頁",
                "item": "https://harmonica.observe.tw/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "公開來源",
                "item": "https://harmonica.observe.tw/source/",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": f"{label}：{value}",
                "item": canonical,
            },
        ],
    }
    json_ld_breadcrumb = json.dumps(breadcrumb_ld, ensure_ascii=False, indent=2)

    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <meta name="description" content="{escape(description)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{escape(title)}">
    <meta property="og:description" content="{escape(description)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape(title)}">
    <meta name="twitter:description" content="{escape(description)}">
    <meta name="twitter:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
{item_list_script}
    <script type="application/ld+json">
{json_ld_breadcrumb}
    </script>
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260704-avatar">
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
      <nav aria-label="breadcrumb" class="breadcrumb-nav" style="font-size: 0.9rem; margin: 1rem auto; max-width: 1200px; padding: 0 1rem; color: var(--text-muted, #666);">
        <a href="/" style="color: var(--primary, #1a73e8); text-decoration: none;">首頁</a> ›
        <a href="/source/" style="color: var(--primary, #1a73e8); text-decoration: none;">公開來源</a> ›
        <span>{escape(label)}：{escape(value)}</span>
      </nav>

      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Source {escape(group["kind"])}</p>
            <h1>{escape(value)}口琴公開來源</h1>
          </div>
          <div class="feed-page-summary">
            <p>{escape(description)}</p>
            <div class="feed-links">
              <a href="/source/">全部公開來源</a>
              <a href="/feeds/sources.xml">來源索引 RSS</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band directory-band" aria-labelledby="source-facet-title">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">{escape(label)}</p>
              <h2 id="source-facet-title">{escape(value)}來源列表</h2>
            </div>
            <p class="data-date">{len(entries)} 筆公開來源</p>
          </div>
          <div class="directory-grid">
{cards}
          </div>
        </div>
      </section>
    </main>

{FOOTER_HTML}
  </body>
</html>
"""


def format_score_sources_table(score_sources: list[dict[str, Any]]) -> str:
    rows = []
    for item in score_sources:
        source_links = item.get("links") or []
        source_link_url = source_links[0].get("url") if source_links else ""
        source_link_label = source_links[0].get("label") if source_links else "佐證"
        source_html = f'<a class="score-source-link" href="{escape(source_link_url)}" target="_blank" rel="noreferrer" title="{escape(source_link_label)}">佐證</a>' if source_link_url else '<span class="score-source-link muted" title="未標示佐證">佐證</span>'

        rows.append(f"""
      <tr>
        <th scope="row" class="score-title-cell" title="{escape(item.get("sourceName") or "-")}">{escape(item.get("sourceName") or "-")}</th>
        <td class="score-program" title="{escape(item.get("sourceType") or "-")}">{escape(item.get("sourceType") or "-")}</td>
        <td class="score-status" title="{escape(item.get("platform") or "-")}">{escape(item.get("platform") or "-")}</td>
        <td class="score-title-cell" title="{escape(item.get("scoreTitle") or "-")}">{escape(item.get("scoreTitle") or "-")}</td>
        <td class="score-composer" title="{escape(item.get("composer") or "-")}">{escape(item.get("composer") or "-")}</td>
        <td class="score-composer" title="{escape(item.get("arranger") or "-")}">{escape(item.get("arranger") or "-")}</td>
        <td class="score-note-inline" title="{escape(item.get("instrumentation") or "-")}">{escape(item.get("instrumentation") or "-")}</td>
        <td class="score-program" title="{escape(item.get("format") or "-")}">{escape(item.get("format") or "-")}</td>
        <td class="score-publisher" title="{escape(item.get("purchaseMethod") or "-")}">{escape(item.get("purchaseMethod") or "-")}</td>
        <td class="score-year" title="{escape(item.get("price") or "-")}">{escape(item.get("price") or "-")}</td>
        <td class="score-status" title="{escape(item.get("availability") or "-")}">{escape(item.get("availability") or "-")}</td>
        <td class="score-source-cell">{source_html}</td>
        <td class="score-note-inline" title="{escape(item.get("rightsNote") or "-")}">{escape(item.get("rightsNote") or "-")}</td>
      </tr>
""")
    table_rows = "".join(rows)
    return f"""
      <table class="score-table score-source-table" style="--score-table-width: 1480px">
        <caption>口琴譜源 metadata、購買或洽詢方式與公開佐證連結</caption>
        <colgroup>
          <col style="width: 144px"><col style="width: 120px"><col style="width: 92px"><col style="width: 250px"><col style="width: 120px"><col style="width: 150px"><col style="width: 210px"><col style="width: 110px"><col style="width: 190px"><col style="width: 92px"><col style="width: 100px"><col style="width: 74px"><col style="width: 240px">
        </colgroup>
        <thead>
          <tr>
            <th scope="col">來源</th>
            <th scope="col">類型</th>
            <th scope="col">平台</th>
            <th scope="col">曲名／譜集</th>
            <th scope="col">作曲</th>
            <th scope="col">編曲</th>
            <th scope="col">編制</th>
            <th scope="col">形式</th>
            <th scope="col">購買／洽詢</th>
            <th scope="col">價格</th>
            <th scope="col">狀態</th>
            <th scope="col">佐證</th>
            <th scope="col">權利註記</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
"""


def update_core_pages(
    entries: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    scores_payload: dict[str, Any],
) -> None:
    source_index_path = SITE_ROOT / "source" / "index.html"
    source_index_path.parent.mkdir(parents=True, exist_ok=True)
    source_index_path.write_text(generate_source_index_base_page(), encoding="utf-8")

    # 1. Load api/score-sources.json
    try:
        SCORE_SOURCES_JSON = SITE_ROOT / "api" / "score-sources.json"
        score_sources_payload = json.loads(SCORE_SOURCES_JSON.read_text(encoding="utf-8"))
        score_sources = score_sources_payload.get("scoreSources") or []
    except Exception as e:
        print(f"Error loading score sources: {e}")
        score_sources_payload = {}
        score_sources = []

    # 2. Load api/status.json
    try:
        STATUS_JSON = SITE_ROOT / "api" / "status.json"
        status_payload = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading status metrics: {e}")
        status_payload = {}

    # 3. Load api/catalog.json
    try:
        CATALOG_JSON = SITE_ROOT / "api" / "catalog.json"
        catalog_payload = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
        feeds_catalog = catalog_payload.get("feeds") or []
    except Exception as e:
        print(f"Error loading feeds catalog: {e}")
        feeds_catalog = []

    # 4. Load api/latest.json for feedGeneratedAt
    try:
        LATEST_JSON = SITE_ROOT / "api" / "latest.json"
        latest_payload = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        feed_generated_at_raw = latest_payload.get("generatedAt", "-")
    except Exception as e:
        print(f"Error loading latest.json for time: {e}")
        feed_generated_at_raw = "-"

    watch_source_count = status_payload.get("metrics", {}).get("watchSources", 562)
    watch_sources_info = status_payload.get("watchSources", {})
    platforms = watch_sources_info.get("platforms", {})

    facebook_count = platforms.get("facebook", 0)
    youtube_count = platforms.get("youtube", 0)
    instagram_count = platforms.get("instagram", 0)
    threads_count = platforms.get("threads", 0)
    x_count = platforms.get("x", 0)

    rsshub_sources_count = instagram_count + threads_count + x_count or 293
    apify_source_count = facebook_count or 143
    directory_entry_count = status_payload.get("metrics", {}).get("directoryEntries", len(entries))

    feed_generated_at = format_feed_time(feed_generated_at_raw)
    generated_at = format_feed_time(status_payload.get("generatedAt", "-"))

    score_count = len(scores)
    years = []
    for s in scores:
        try:
            years.append(int(s.get("schoolYear")))
        except (ValueError, TypeError, KeyError):
            pass
    score_year_range = f"{min(years)}-{max(years)}" if years else "-"
    score_publisher_count = len(scores_payload.get("stats", {}).get("publishers", []))
    score_generated_at = format_feed_time(scores_payload.get("generatedAt", "-"))

    score_source_count = len(score_sources)
    score_source_distinct_count = score_sources_payload.get("stats", {}).get("distinctSources", 0)
    score_source_title_count = score_sources_payload.get("stats", {}).get("titledItems", 0)
    score_source_generated_at = format_feed_time(score_sources_payload.get("generatedAt", "-"))

    core_pages = [
        ("index.html", {}),
        ("post/index.html", {}),
        ("source/index.html", {}),
        ("scores/index.html", {
            "inject_selector": r'(<div[^>]*id="score-list"[^>]*>).*?(</div>)',
            "inject_content": format_scores_table(scores)
        }),
        ("scores/sources/index.html", {
            "inject_selector": r'(<div[^>]*id="score-source-list"[^>]*>).*?(</div>)',
            "inject_content": format_score_sources_table(score_sources)
        }),
    ]

    for rel_path, inject_info in core_pages:
        page_path = SITE_ROOT / rel_path
        if not page_path.exists():
            continue
        try:
            content = page_path.read_text(encoding="utf-8")

            content = replace_stat(content, "watchSourceCount", watch_source_count)
            content = replace_stat(content, "rsshubSourceCount", rsshub_sources_count)
            content = replace_stat(content, "apifySourceCount", apify_source_count)
            content = replace_stat(content, "directoryEntryCount", directory_entry_count)
            content = replace_stat(content, "totalEntries", directory_entry_count)
            content = replace_stat(content, "feedGeneratedAt", feed_generated_at)
            content = replace_stat(content, "generatedAt", generated_at)
            content = replace_stat(content, "scoreCount", score_count)
            content = replace_stat(content, "scoreYearRange", score_year_range)
            content = replace_stat(content, "scorePublisherCount", score_publisher_count)
            content = replace_stat(content, "scoreGeneratedAt", score_generated_at)
            content = replace_stat(content, "scoreSourceCount", score_source_count)
            content = replace_stat(content, "scoreSourceDistinctCount", score_source_distinct_count)
            content = replace_stat(content, "scoreSourceTitleCount", score_source_title_count)
            content = replace_stat(content, "scoreSourceGeneratedAt", score_source_generated_at)

            if inject_info:
                pattern = re.compile(inject_info["inject_selector"], re.DOTALL)
                content = pattern.sub(rf'\g<1>{inject_info["inject_content"]}\g<2>', content)

            if rel_path == "source/index.html":
                content = re.sub(
                    r'\n\s*<script type="application/ld\+json"[^>]*data-generated="source-item-list"[^>]*>.*?</script>',
                    "",
                    content,
                    flags=re.DOTALL,
                )
                source_item_list_script = format_source_item_list_json_ld(entries)
                content = content.replace(
                    '    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">',
                    f'{source_item_list_script}\n    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260704-avatar" type="image/svg+xml">',
                    1,
                )
                content = re.sub(
                    r'(<div class="directory-grid" id="directory-list">)(?:\s*<!-- DIRECTORY_STATIC_START -->.*?<!-- DIRECTORY_STATIC_END -->\s*)?(</div>)',
                    rf'\g<1>{format_static_directory_cards(entries)}\g<2>',
                    content,
                    flags=re.DOTALL,
                )

            page_path.write_text(content, encoding="utf-8")
            print(f"Updated core page: {rel_path}")
        except Exception as e:
            print(f"Error updating core page {rel_path}: {e}")

    feeds_html_path = SITE_ROOT / "feeds" / "index.html"
    if feeds_html_path.exists():
        try:
            content = feeds_html_path.read_text(encoding="utf-8")
            for feed in feeds_catalog:
                feed_id = feed.get("id")
                item_count = feed.get("count", 0)
                pattern = re.compile(
                    r'(<p\s+class="section-kicker">' + re.escape(feed_id) + r'</p>.*?<span\s+class="pill">)[^<]*(</span>)',
                    re.DOTALL
                )
                content = pattern.sub(rf'\g<1>{item_count} 筆\g<2>', content)
            feeds_html_path.write_text(content, encoding="utf-8")
            print("Updated feeds catalog page")
        except Exception as e:
            print(f"Error updating feeds catalog: {e}")


def main() -> int:
    # 1. Load data
    try:
        sources_payload = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
        entries = sources_payload.get("entries") or []
    except Exception as e:
        print(f"Error loading sources: {e}")
        entries = []

    try:
        events_payload = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))
        events = events_payload.get("events") or []
    except Exception as e:
        print(f"Error loading events: {e}")
        events = []

    try:
        scores_payload = json.loads(SCORES_JSON.read_text(encoding="utf-8"))
        scores = scores_payload.get("scores") or []
        categories = scores_payload.get("stats", {}).get("programs") or ["口琴合奏", "口琴四重奏", "口琴獨奏"]
    except Exception as e:
        print(f"Error loading scores: {e}")
        scores = []
        categories = ["口琴合奏", "口琴四重奏", "口琴獨奏"]

    # Load latest updates
    LATEST_JSON = SITE_ROOT / "api" / "latest.json"
    try:
        latest_payload = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
        updates = latest_payload.get("updates") or []
    except Exception as e:
        print(f"Error loading latest updates: {e}")
        updates = []

    # 2. Pre-render Source Pages
    source_groups = source_facet_groups(entries)
    source_count = 0
    for entry in entries:
        entry_id = clean(entry.get("id"))
        if not entry_id:
            continue

        # Match updates
        entry_updates = [
            up for up in updates
            if clean(up.get("directory_entry_id")) == entry_id
            and not feed_render.is_instagram_story_item(up)
        ]

        slug = make_slug(entry)

        related_facets = source_related_facets(entry, entries)

        slug_dir = SITE_ROOT / "source" / slug
        slug_dir.mkdir(parents=True, exist_ok=True)
        html_content = normalize_generated_html(
            generate_source_page(entry, entry_updates, related_facets)
        )
        (slug_dir / "index.html").write_text(html_content, encoding="utf-8")

        redirect_aliases = {entry_id, source_public_id(entry)}
        for alias in sorted(redirect_aliases):
            if not alias or alias == slug:
                continue
            old_dir = SITE_ROOT / "source" / alias
            old_dir.mkdir(parents=True, exist_ok=True)
            redirect_url = f"https://harmonica.observe.tw/source/{slug}/"
            redirect_html = f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <title>重新導向中...</title>
    <meta http-equiv="refresh" content="0; url={redirect_url}">
    <link rel="canonical" href="{redirect_url}">
  </head>
  <body>
    <p>頁面已移動，正在重新導向至 <a href="{redirect_url}">{redirect_url}</a>...</p>
  </body>
</html>
"""
            (old_dir / "index.html").write_text(redirect_html, encoding="utf-8")

        source_count += 1

    # 3. Pre-render source facet landing pages
    source_facet_count = 0
    for group in source_groups:
        for facet in group.get("values") or []:
            value = clean(facet.get("value"))
            facet_entries = facet.get("entries") or []
            if not value or not facet_entries:
                continue
            page_dir = SITE_ROOT / "source" / group["path"] / value
            page_dir.mkdir(parents=True, exist_ok=True)
            html_content = normalize_generated_html(generate_source_facet_page(group, value, facet_entries))
            (page_dir / "index.html").write_text(html_content, encoding="utf-8")
            source_facet_count += 1

    # 4. Pre-render Event Pages
    event_count = 0
    for event in events:
        event_id = clean(event.get("id"))
        if not event_id:
            continue
        page_dir = SITE_ROOT / "event" / event_id
        page_dir.mkdir(parents=True, exist_ok=True)
        html_content = normalize_generated_html(generate_event_page(event))
        (page_dir / "index.html").write_text(html_content, encoding="utf-8")
        event_count += 1

    # 5. Pre-render Score Category Pages
    score_cat_count = 0
    for category in categories:
        category_scores = [item for item in scores if clean(item.get("program")) == category]
        page_dir = SITE_ROOT / "scores" / category
        page_dir.mkdir(parents=True, exist_ok=True)
        html_content = normalize_generated_html(generate_scores_category_page(category, category_scores))
        (page_dir / "index.html").write_text(html_content, encoding="utf-8")
        score_cat_count += 1

    # 6. Pre-render Core Pages (index, post, source, scores, scores/sources, feeds)
    update_core_pages(entries, scores, scores_payload)
    write_source_index_redirect()

    # 7. Rebuild sitemap
    sitemap_content = generate_sitemap_xml(entries, events, categories, updates, scores, source_groups)
    SITEMAP_XML.write_text(sitemap_content, encoding="utf-8")

    print(f"SEO Pre-rendering completed:")
    print(f" - Generated {source_count} source pages under /source/<id>/")
    print(f" - Generated {source_facet_count} source facet pages under /source/<facet>/<value>/")
    print(f" - Generated {event_count} event pages under /event/<id>/")
    print(f" - Generated {score_cat_count} score category pages under /scores/<category>/")
    print(f" - Rebuilt sitemap.xml with {len(entries) + source_facet_count + len(events) + len(categories) + 8} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
