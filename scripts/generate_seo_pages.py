#!/usr/bin/env python3
"""Pre-render static SEO landing pages and dynamically rebuild sitemap.xml."""

from __future__ import annotations

import html
import json
import os
import urllib.parse
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"

SOURCES_JSON = SITE_ROOT / "api" / "sources.json"
EVENTS_JSON = SITE_ROOT / "api" / "public-calendar-events.json"
SCORES_JSON = SITE_ROOT / "api" / "scores.json"
SITEMAP_XML = SITE_ROOT / "sitemap.xml"

# Shared HTML parts
HEADER_HTML = """    <header class="site-header">
      <a class="brand" href="/" aria-label="臺灣口琴觀測站首頁">
        <img class="brand-logo" src="/assets/logo.svg?v=20260628-0342" alt="臺灣口琴觀測站" width="200" height="47">
      </a>
      <nav class="site-nav" aria-label="主要導覽">
        <a href="/">首頁</a>
        <a href="/post/">公開貼文</a>
        <a href="/post/source/">公開來源</a>
        <a href="/scores/">比賽指定曲</a>
        <a href="/scores/sources/">口琴譜源</a>
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
          <a href="https://github.com/skyhong2002/Harmonica-in-Taiwan" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
        <p class="footer-meta">只收錄公開可查資料 · 由 <a href="https://www.facebook.com/nycubmhc/" target="_blank" rel="noreferrer">陽明交大竹韻口琴社</a> 維運 · MIT License · © 2026 Sky Hong</p>
      </div>
    </footer>"""


def clean(val: str | None) -> str:
    return (val or "").strip()


def escape(val: str | None) -> str:
    return html.escape(clean(val))


def generate_source_page(entry: dict[str, Any]) -> str:
    entry_id = escape(entry.get("id"))
    name = escape(entry.get("name"))
    name_en = escape(entry.get("nameEn"))
    category = escape(entry.get("category"))
    entry_type = escape(entry.get("type"))
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
        "url": f"https://harmonica.observe.tw/source/{entry_id}/",
        "description": entry.get("summary") or entry.get("structuredSummary") or ""
    }
    if entry.get("nameEn"):
        json_ld_dict["alternateName"] = entry["nameEn"]
    
    links = entry.get("links") or []
    if links:
        json_ld_dict["sameAs"] = [link["url"] for link in links if link.get("url")]
        
    json_ld = json.dumps(json_ld_dict, ensure_ascii=False, indent=2)

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
    
    tags = entry.get("sourceTags") or []
    tags_row = ""
    if tags:
        tag_pills = " ".join(f'<span class="source-tag-pill" style="display: inline-block; padding: 2px 8px; margin: 2px; font-size: 0.85rem; background: var(--tag-bg, #e8f0fe); color: var(--tag-text, #1a73e8); border-radius: 4px;">#{escape(t)}</span>' for t in tags)
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
            links_list.append(f'<a href="{url}" target="_blank" rel="noreferrer" class="primary-link" style="margin: 5px; display: inline-block; padding: 6px 12px; border: 1px solid var(--border-color, #ccc); border-radius: 4px; text-decoration: none;">{label}</a>')
        links_html = f'<div class="feed-links" style="display: flex; flex-wrap: wrap; margin-top: 10px;">{" ".join(links_list)}</div>'
    else:
        links_html = '<p style="color: var(--text-muted, #666);">暫無公開社群連結</p>'

    og_image = f"https://harmonica.observe.tw{avatar_url}" if avatar_url and avatar_url.startswith("/") else "https://harmonica.observe.tw/assets/hero-harmonica-observe.webp"

    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{name}｜臺灣口琴觀測站</title>
    <meta name="description" content="{summary}">
    <link rel="canonical" href="https://harmonica.observe.tw/source/{entry_id}/">
    <meta property="og:title" content="{name}｜臺灣口琴觀測站">
    <meta property="og:description" content="{summary}">
    <meta property="og:type" content="profile">
    <meta property="og:url" content="https://harmonica.observe.tw/source/{entry_id}/">
    <meta property="og:image" content="{og_image}">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{name}｜臺灣口琴觀測站">
    <meta name="twitter:description" content="{summary}">
    <meta name="twitter:image" content="{og_image}">
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260628-0342" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260628-0342">
    <script type="application/ld+json">
{json_ld}
    </script>
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
      <section class="feed-page-hero">
        <div class="band-inner split-layout">
          <div class="source-hero-head" style="display: flex; align-items: center;">
            {avatar_html}
            <div>
              <p class="section-kicker" style="text-transform: uppercase; font-size: 0.9rem; letter-spacing: 0.05em; color: var(--primary, #1a73e8); font-weight: bold; margin: 0;">{category}</p>
              <h1 style="margin: 0.3rem 0 0 0; font-size: 2.2rem; font-weight: 800;">{name}</h1>
              {name_en_html}
            </div>
          </div>
          <div class="feed-page-summary">
            <p style="font-size: 1.1rem; line-height: 1.6; margin: 0 0 1.5rem 0;">{summary}</p>
            <div class="feed-links">
              <a href="/post/source/">返回公開來源列表</a>
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
                  <th scope="row" style="width: 25%; padding: 10px; text-align: left; font-weight: bold; border-bottom: 1px solid var(--border-color, #e0e0e0);">類別 / 類型</th>
                  <td style="padding: 10px; border-bottom: 1px solid var(--border-color, #e0e0e0);">{category} / {entry_type}</td>
                </tr>
                {country_row}
                {region_row}
                {city_row}
                {tags_row}
                {aliases_row}
              </tbody>
            </table>
            
            <h2 class="source-detail-title" style="font-size: 1.5rem; font-weight: 700; border-bottom: 2px solid var(--primary, #1a73e8); padding-bottom: 0.5rem; margin-bottom: 1rem;">公開聯絡與社群連結</h2>
            {links_html}
          </div>
        </div>
      </section>
    </main>

{FOOTER_HTML}
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
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260628-0342" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260628-0342">
    <script type="application/ld+json">
{json_ld}
    </script>
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
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
    description = f"臺灣全國學生音樂比賽口琴項目「{escape(category)}」歷年指定曲與公開出版、購譜或洽詢管道索引線索。"
    
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

    # Render rows
    rows_list = []
    for item in items:
        year = escape(item.get("schoolYear") or "-")
        status = escape(item.get("sourceStatus") or "-")
        division = escape(item.get("division") or "-")
        
        # Title building
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
    <title>{escape(category)} 指定曲與購譜線索｜臺灣口琴觀測站</title>
    <meta name="description" content="{description}">
    <link rel="canonical" href="https://harmonica.observe.tw/scores/{encoded_category}/">
    <meta property="og:title" content="{escape(category)} 指定曲與購譜線索｜臺灣口琴觀測站">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://harmonica.observe.tw/scores/{encoded_category}/">
    <meta property="og:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <meta property="og:site_name" content="臺灣口琴觀測站">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape(category)} 指定曲與購譜線索｜臺灣口琴觀測站">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="https://harmonica.observe.tw/assets/hero-harmonica-observe.webp">
    <link rel="icon" href="/assets/favicon-20260623.svg?v=20260628-0342" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v=20260628-0342">
    <script type="application/ld+json">
{json_ld}
    </script>
  </head>
  <body>
{HEADER_HTML}

    <main class="feed-page-main">
      <section class="feed-page-hero score-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Contest Pieces - {escape(category)}</p>
            <h1>{escape(category)} 指定曲索引</h1>
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


def generate_sitemap_xml(sources: list[dict[str, Any]], events: list[dict[str, Any]], categories: list[str]) -> str:
    url_templates = []
    
    # 7 Core Pages
    core_pages = [
        ("", "daily", "1.0"),
        ("post/", "daily", "0.8"),
        ("post/source/", "weekly", "0.8"),
        ("scores/", "weekly", "0.8"),
        ("scores/sources/", "weekly", "0.8"),
        ("submit/", "monthly", "0.5"),
        ("status/", "daily", "0.5"),
    ]
    for path, freq, priority in core_pages:
        url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/{path}</loc>
    <lastmod>2026-07-03</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    # Category Pages
    for category in categories:
        encoded = urllib.parse.quote(category)
        url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/scores/{encoded}/</loc>
    <lastmod>2026-07-03</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")

    # Source Pages
    for src in sources:
        src_id = clean(src.get("id"))
        if src_id:
            url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/source/{src_id}/</loc>
    <lastmod>2026-07-03</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>""")

    # Event Pages
    for ev in events:
        ev_id = clean(ev.get("id"))
        if ev_id:
            url_templates.append(f"""  <url>
    <loc>https://harmonica.observe.tw/event/{ev_id}/</loc>
    <lastmod>2026-07-03</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>""")

    url_content = "\n".join(url_templates)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_content}
</urlset>
"""


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

    # 2. Pre-render Source Pages
    source_count = 0
    for entry in entries:
        entry_id = clean(entry.get("id"))
        if not entry_id:
            continue
        page_dir = SITE_ROOT / "source" / entry_id
        page_dir.mkdir(parents=True, exist_ok=True)
        html_content = generate_source_page(entry)
        (page_dir / "index.html").write_text(html_content, encoding="utf-8")
        source_count += 1

    # 3. Pre-render Event Pages
    event_count = 0
    for event in events:
        event_id = clean(event.get("id"))
        if not event_id:
            continue
        page_dir = SITE_ROOT / "event" / event_id
        page_dir.mkdir(parents=True, exist_ok=True)
        html_content = generate_event_page(event)
        (page_dir / "index.html").write_text(html_content, encoding="utf-8")
        event_count += 1

    # 4. Pre-render Score Category Pages
    score_cat_count = 0
    for category in categories:
        category_scores = [item for item in scores if clean(item.get("program")) == category]
        page_dir = SITE_ROOT / "scores" / category
        page_dir.mkdir(parents=True, exist_ok=True)
        html_content = generate_scores_category_page(category, category_scores)
        (page_dir / "index.html").write_text(html_content, encoding="utf-8")
        score_cat_count += 1

    # 5. Rebuild sitemap
    sitemap_content = generate_sitemap_xml(entries, events, categories)
    SITEMAP_XML.write_text(sitemap_content, encoding="utf-8")

    print(f"SEO Pre-rendering completed:")
    print(f" - Generated {source_count} source pages under /source/<id>/")
    print(f" - Generated {event_count} event pages under /event/<id>/")
    print(f" - Generated {score_cat_count} score category pages under /scores/<category>/")
    print(f" - Rebuilt sitemap.xml with {len(entries) + len(events) + len(categories) + 7} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
