#!/usr/bin/env python3
"""Build the public ingestion status page and JSON snapshot."""

from __future__ import annotations

import collections
import datetime as dt
import email.utils
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
STATUS_JSON_OUT = SITE_ROOT / "api" / "status.json"
STATUS_PAGE_OUT = SITE_ROOT / "status" / "index.html"
SOCIAL_SOURCES = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
SOCIAL_CANDIDATES = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
SOCIAL_INBOX = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"
SOCIAL_ERRORS = PROJECT_ROOT / "data" / "feeds" / "social_feed_errors.jsonl"
SOCIAL_SEEN = PROJECT_ROOT / "state" / "social_seen.json"
APIFY_LEDGER = PROJECT_ROOT / "state" / "apify_facebook_fetcher.json"
YOUTUBE_LEDGER = PROJECT_ROOT / "state" / "youtube_ytdlp_fetcher.json"
LATEST_API = SITE_ROOT / "api" / "latest.json"
SOURCES_API = SITE_ROOT / "api" / "sources.json"
PIPELINE_LOG = PROJECT_ROOT / "logs" / "pipeline.log"
PIPELINE_ERR_LOG = PROJECT_ROOT / "logs" / "pipeline.err.log"
ASSET_VERSION = "20260627-0150"
PUBLIC_BASE_URL = "https://harmonica.observe.tw"
TAIPEI_TZ = dt.timezone(dt.timedelta(hours=8))
CURRENT_ERROR_WINDOW_SECONDS = 15 * 60
FRESH_PIPELINE_HOURS = 36

STATUS_LABELS = {
    "ok": "正常",
    "paused": "節流中",
    "degraded": "部分異常",
    "down": "停止",
    "unknown": "未知",
}

STATUS_SORT = {
    "down": 0,
    "degraded": 1,
    "paused": 2,
    "unknown": 3,
    "ok": 4,
}


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def parse_time(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
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


def taipei_iso(value: dt.datetime) -> str:
    return value.astimezone(TAIPEI_TZ).isoformat(timespec="seconds")


def time_label(value: dt.datetime | None) -> str:
    if value is None:
        return "未記錄"
    return value.astimezone(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")


def file_mtime(path: Path) -> dt.datetime | None:
    if not path.exists():
        return None
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)


def hours_since(value: dt.datetime | None, now: dt.datetime) -> float | None:
    if value is None:
        return None
    return max(0.0, (now - value).total_seconds() / 3600)


def max_time(values: list[dt.datetime | None]) -> dt.datetime | None:
    parsed = [value for value in values if value is not None]
    return max(parsed) if parsed else None


def latest_seen_at(rows: list[dict[str, Any]]) -> dt.datetime | None:
    return max_time([parse_time(row.get("seen_at")) for row in rows])


def compact_error(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:220] if text else "未提供錯誤訊息"


def format_usd(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"${number:.2f}"


def source_counts(sources: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter = collections.Counter(str(source.get(field) or "unknown") for source in sources)
    return dict(sorted(counter.items()))


def enabled_watch_sources() -> list[dict[str, Any]]:
    payload = read_json(SOCIAL_SOURCES, {"sources": []})
    sources = payload.get("sources") if isinstance(payload, dict) else []
    return [
        source
        for source in sources
        if isinstance(source, dict)
        and source.get("enabled", True)
        and source.get("type") != "jsonl"
    ]


def probe_url(url: str, timeout: int = 6) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "HarmonicaStatusBot/1.0"})
    started = dt.datetime.now(dt.timezone.utc)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "ok": 200 <= int(response.status) < 400,
                "statusCode": int(response.status),
                "elapsedMs": int((dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "statusCode": int(exc.code),
            "elapsedMs": int((dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000),
            "error": compact_error(exc.reason),
        }
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        return {
            "ok": False,
            "statusCode": None,
            "elapsedMs": int((dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000),
            "error": compact_error(exc),
        }


def launch_agent_status() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/tw.observe.harmonica.pipeline"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "status": "unknown", "summary": compact_error(exc)}

    if result.returncode != 0:
        return {"available": False, "status": "unknown", "summary": compact_error(result.stderr)}

    state_match = re.search(r"state = ([^\n]+)", result.stdout)
    exit_match = re.search(r"last exit code = (-?\d+)", result.stdout)
    runs_match = re.search(r"runs = (\d+)", result.stdout)
    last_exit = int(exit_match.group(1)) if exit_match else None
    status = "ok" if last_exit in (0, None) else "degraded"
    return {
        "available": True,
        "status": status,
        "state": state_match.group(1).strip() if state_match else "unknown",
        "lastExitCode": last_exit,
        "runs": int(runs_match.group(1)) if runs_match else None,
    }


def apify_check() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "scripts/apify_facebook_fetcher.py", "--check"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=75,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": compact_error(exc)}

    if result.returncode != 0:
        return {"ok": False, "error": compact_error(result.stderr or result.stdout)}

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Apify check did not return JSON"}

    # Keep only public-safe operational metadata; never expose token source or raw auth details.
    keys = [
        "has_token",
        "auto_budget_pacing",
        "budget_pacing_mode",
        "sources_due_count",
        "sources_selected_count",
        "min_sources_per_run",
        "planned_run_budget_usd",
        "remote_monthly_usage_usd",
        "effective_remote_monthly_limit_usd",
        "remote_monthly_remaining_usd",
        "monthly_remaining_usd",
        "last_successful_run_at",
        "cadence_ready",
    ]
    return {"ok": True, **{key: raw.get(key) for key in keys if key in raw}}


def component(
    component_id: str,
    name: str,
    status: str,
    summary: str,
    details: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "name": name,
        "status": status,
        "label": STATUS_LABELS.get(status, status),
        "summary": summary,
        "details": details or [],
    }


def annotate_errors(
    errors: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    annotated = []
    for row in errors:
        source_id = str(row.get("source_id") or "")
        source = source_by_id.get(source_id, {})
        annotated.append(
            {
                "seenAt": taipei_iso(parse_time(row.get("seen_at")) or dt.datetime.now(dt.timezone.utc)),
                "sourceId": source_id,
                "sourceName": source.get("name") or row.get("source_name") or source_id or "unknown",
                "platform": source.get("platform") or row.get("platform") or row.get("source_type") or "unknown",
                "sourceType": row.get("source_type") or source.get("type") or "unknown",
                "error": compact_error(row.get("error")),
            }
        )
    return annotated


def youtube_success_times(youtube_ledger: dict[str, Any]) -> dict[str, dt.datetime]:
    sources = youtube_ledger.get("sources") if isinstance(youtube_ledger, dict) else {}
    if not isinstance(sources, dict):
        return {}
    recovered: dict[str, dt.datetime] = {}
    for source_id, state in sources.items():
        if not isinstance(state, dict) or state.get("last_status") != "ok":
            continue
        success_at = parse_time(state.get("last_success_at") or state.get("last_checked_at"))
        if success_at is not None:
            recovered[str(source_id)] = success_at
    return recovered


def youtube_error_superseded(row: dict[str, Any], recovered: dict[str, dt.datetime]) -> bool:
    if row.get("source_type") != "youtube_ytdlp":
        return False
    source_id = str(row.get("source_id") or "")
    error_seen_at = parse_time(row.get("seen_at"))
    recovered_at = recovered.get(source_id)
    return bool(error_seen_at and recovered_at and recovered_at >= error_seen_at)


def build_status() -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)
    sources = enabled_watch_sources()
    source_by_id = {str(source.get("id")): source for source in sources if source.get("id")}
    candidates = read_jsonl(SOCIAL_CANDIDATES)
    inbox = read_jsonl(SOCIAL_INBOX)
    errors = read_jsonl(SOCIAL_ERRORS)
    social_seen = read_json(SOCIAL_SEEN, {})
    latest_payload = read_json(LATEST_API, {})
    sources_payload = read_json(SOURCES_API, {})
    apify_ledger = read_json(APIFY_LEDGER, {})
    youtube_ledger = read_json(YOUTUBE_LEDGER, {})
    youtube_recovered_at = youtube_success_times(youtube_ledger)

    latest_generated_at = parse_time(latest_payload.get("generatedAt"))
    latest_data_mtime = file_mtime(LATEST_API)
    latest_error_at = max_time([parse_time(row.get("seen_at")) for row in errors])
    latest_social_seen_at = max_time(
        [latest_seen_at(candidates), latest_seen_at(inbox), latest_error_at, parse_time(social_seen.get("updated_at"))]
    )
    current_errors = []
    if latest_social_seen_at is not None:
        lower_bound = latest_social_seen_at - dt.timedelta(seconds=CURRENT_ERROR_WINDOW_SECONDS)
        current_errors = [
            row
            for row in errors
            if (seen_at := parse_time(row.get("seen_at"))) is not None and seen_at >= lower_bound
        ]
    elif latest_error_at is not None:
        current_errors = [row for row in errors if parse_time(row.get("seen_at")) == latest_error_at]
    current_errors = [row for row in current_errors if not youtube_error_superseded(row, youtube_recovered_at)]

    annotated_current_errors = annotate_errors(current_errors, source_by_id)
    current_error_platforms = collections.Counter(row["platform"] for row in annotated_current_errors)
    current_error_types = collections.Counter(row["sourceType"] for row in annotated_current_errors)

    launch_agent = launch_agent_status()
    rsshub_probe = probe_url("http://127.0.0.1:1200/")
    apify = apify_check()

    watch_platforms = source_counts(sources, "platform")
    watch_types = source_counts(sources, "type")
    updates_count = len(latest_payload.get("updates") or [])
    directory_count = int(sources_payload.get("count") or 0)
    latest_age = hours_since(latest_generated_at or latest_data_mtime, now)

    components: list[dict[str, Any]] = []

    pipeline_status = "ok"
    pipeline_details = [
        f"最新公開資料：{time_label(latest_generated_at or latest_data_mtime)}",
        f"pipeline.log 更新：{time_label(file_mtime(PIPELINE_LOG))}",
        f"pipeline.err.log 更新：{time_label(file_mtime(PIPELINE_ERR_LOG))}",
    ]
    if latest_age is None or latest_age > FRESH_PIPELINE_HOURS:
        pipeline_status = "degraded"
        pipeline_details.append(f"公開資料超過 {FRESH_PIPELINE_HOURS} 小時未更新")
    if launch_agent.get("available"):
        pipeline_details.append(
            f"LaunchAgent：{launch_agent.get('state')}，last exit {launch_agent.get('lastExitCode')}"
        )
        if launch_agent.get("status") == "degraded":
            pipeline_status = "degraded"
    else:
        pipeline_details.append("LaunchAgent：本次快照無法讀取")
    components.append(
        component(
            "pipeline",
            "主排程與輸出",
            pipeline_status,
            "每日 pipeline 已產生公開資料快照。" if pipeline_status == "ok" else "排程或輸出時間需要檢查。",
            pipeline_details,
        )
    )

    api_status = "ok" if updates_count and directory_count else "degraded"
    components.append(
        component(
            "public-api",
            "公開 API",
            api_status,
            f"latest.json 有 {updates_count} 筆更新，sources.json 有 {directory_count} 筆公開目錄。",
            [
                f"更新視窗：{latest_payload.get('updatesWindowDays') or '-'} 天",
                f"watch sources：{len(sources)}",
            ],
        )
    )

    components.append(
        component(
            "rsshub",
            "RSSHub 服務",
            "ok" if rsshub_probe.get("ok") else "degraded",
            "本機 RSSHub 入口回 200。" if rsshub_probe.get("ok") else "本機 RSSHub 入口無法正常回應。",
            [
                f"HTTP：{rsshub_probe.get('statusCode') or '無回應'}",
                f"耗時：{rsshub_probe.get('elapsedMs')} ms",
            ],
        )
    )

    ig_errors = current_error_platforms.get("instagram", 0) + current_error_types.get("rsshub_instagram_profile", 0)
    components.append(
        component(
            "instagram",
            "Instagram RSSHub",
            "degraded" if ig_errors else "ok",
            f"{watch_platforms.get('instagram', 0)} 個 Instagram 來源；最新抓取批次目前 {ig_errors} 個錯誤。",
            [f"最新社群觀測：{time_label(latest_social_seen_at)}"],
        )
    )

    x_errors = current_error_platforms.get("x", 0)
    components.append(
        component(
            "x-twitter",
            "X / Twitter RSS",
            "degraded" if x_errors else "ok",
            f"{watch_platforms.get('x', 0)} 個 X 來源；最新抓取批次目前 {x_errors} 個錯誤。",
            [
                "目前 route 依 RSSHub 設定抓取。",
                "若持續 503，通常要檢查 RSSHub 的 Twitter API 設定。",
            ],
        )
    )

    latest_apify_run = apify_ledger.get("last_run") or (apify_ledger.get("runs") or [None])[-1] if isinstance(apify_ledger, dict) else None
    apify_errors = current_error_types.get("apify", 0)
    apify_status = "ok"
    apify_summary = f"{watch_platforms.get('facebook', 0)} 個 Facebook 來源。"
    apify_details = []
    if isinstance(latest_apify_run, dict):
        apify_details.append(f"最近成功 run：{time_label(parse_time(latest_apify_run.get('finished_at')))}")
        apify_details.append(f"最近新增 inbox：{latest_apify_run.get('new_inbox_rows', 0)}")
    if not apify.get("ok"):
        apify_status = "degraded"
        apify_details.append(f"Apify check：{apify.get('error')}")
    elif not apify.get("has_token"):
        apify_status = "degraded"
        apify_details.append("Apify check：未偵測到 token")
    else:
        due = int(apify.get("sources_due_count") or 0)
        minimum = int(apify.get("min_sources_per_run") or 0)
        selected = int(apify.get("sources_selected_count") or 0)
        apify_details.extend(
            [
                f"due sources：{due}",
                f"selected this check：{selected}",
                f"min sources per run：{minimum}",
                f"遠端月額度剩餘：{format_usd(apify.get('remote_monthly_remaining_usd'))}",
                f"規劃單次預算：{format_usd(apify.get('planned_run_budget_usd'))}",
            ]
        )
        if selected == 0 and minimum and due < minimum:
            apify_status = "paused"
            apify_summary += " 目前依預算 pacing 暫停開 run，等待 due 來源累積。"
        else:
            apify_summary += " Apify token/quota check 正常。"
    if apify_errors:
        apify_status = "degraded"
        apify_summary += f" 最新抓取批次有 {apify_errors} 個 Apify 錯誤。"
    components.append(component("facebook-apify", "Facebook Apify", apify_status, apify_summary, apify_details))

    latest_youtube_run = youtube_ledger.get("last_run") or (youtube_ledger.get("runs") or [None])[-1] if isinstance(youtube_ledger, dict) else None
    youtube_errors = current_error_types.get("youtube_ytdlp", 0)
    if isinstance(latest_youtube_run, dict):
        youtube_error_count = int(latest_youtube_run.get("error_count") or 0)
        youtube_finished = parse_time(latest_youtube_run.get("finished_at"))
        youtube_new_rows = latest_youtube_run.get("new_inbox_rows", 0)
    else:
        youtube_error_count = 0
        youtube_finished = None
        youtube_new_rows = 0
    components.append(
        component(
            "youtube",
            "YouTube yt-dlp",
            "degraded" if youtube_errors or youtube_error_count else "ok",
            f"{watch_platforms.get('youtube', 0)} 個 YouTube 來源；最近 run error_count={youtube_error_count}。",
            [
                f"最近完成：{time_label(youtube_finished)}",
                f"最近新增 inbox：{youtube_new_rows}",
            ],
        )
    )

    other_rss_errors = sum(
        count
        for platform, count in current_error_platforms.items()
        if platform not in {"instagram", "x", "facebook", "youtube"}
    )
    components.append(
        component(
            "other-rss",
            "Threads / 其他 RSS",
            "degraded" if other_rss_errors else "ok",
            f"{watch_platforms.get('threads', 0)} 個 Threads 來源；其他 RSS 最新抓取批次目前 {other_rss_errors} 個錯誤。",
            [f"RSS 類型來源：{watch_types.get('rss', 0)}"],
        )
    )

    degraded_components = [item for item in components if item["status"] in {"down", "degraded"}]
    paused_components = [item for item in components if item["status"] == "paused"]
    if degraded_components:
        overall_status = "degraded"
        degraded_names = "、".join(item["name"] for item in degraded_components)
        overall_summary = f"核心 pipeline 有產出；需要注意：{degraded_names}。"
    else:
        overall_status = "ok"
        overall_summary = "核心資料抓取與公開 API 正常。"
    if paused_components:
        overall_summary += " Facebook Apify 目前是預算節流狀態。"

    platform_rows = []
    for platform, count in sorted(watch_platforms.items()):
        error_count = current_error_platforms.get(platform, 0)
        platform_rows.append(
            {
                "platform": platform,
                "sources": count,
                "currentErrors": error_count,
                "status": "degraded" if error_count else "ok",
            }
        )

    status = {
        "generatedAt": taipei_iso(now),
        "site": PUBLIC_BASE_URL,
        "overall": {
            "status": overall_status,
            "label": STATUS_LABELS[overall_status],
            "summary": overall_summary,
        },
        "metrics": {
            "updates": updates_count,
            "updatesWindowDays": latest_payload.get("updatesWindowDays"),
            "directoryEntries": directory_count,
            "watchSources": len(sources),
            "currentErrors": len(annotated_current_errors),
            "latestDataAt": taipei_iso(latest_generated_at) if latest_generated_at else "",
            "latestSocialObservationAt": taipei_iso(latest_social_seen_at) if latest_social_seen_at else "",
        },
        "watchSources": {
            "platforms": watch_platforms,
            "types": watch_types,
            "platformRows": platform_rows,
        },
        "components": components,
        "recentErrors": annotated_current_errors[-20:],
    }
    return status


def html_escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_badge(status: str, label: str | None = None) -> str:
    return f'<span class="status-badge status-{html_escape(status)}">{html_escape(label or STATUS_LABELS.get(status, status))}</span>'


def render_metric(label: str, value: Any, note: str = "") -> str:
    return f"""
      <article class="status-metric-card">
        <span>{html_escape(label)}</span>
        <strong>{html_escape(value)}</strong>
        <p>{html_escape(note)}</p>
      </article>
    """


def render_component_card(item: dict[str, Any]) -> str:
    details = "".join(f"<li>{html_escape(detail)}</li>" for detail in item.get("details", []))
    details_html = f'<ul class="status-detail-list">{details}</ul>' if details else ""
    return f"""
      <article class="status-component-card status-card-{html_escape(item.get('status'))}">
        <div class="status-component-head">
          <h2>{html_escape(item.get('name'))}</h2>
          {render_badge(str(item.get('status')), str(item.get('label')))}
        </div>
        <p>{html_escape(item.get('summary'))}</p>
        {details_html}
      </article>
    """


def render_platform_rows(rows: list[dict[str, Any]]) -> str:
    rendered = []
    for row in rows:
        status = str(row.get("status") or "unknown")
        rendered.append(
            f"""
            <tr>
              <th scope="row">{html_escape(row.get('platform'))}</th>
              <td>{html_escape(row.get('sources'))}</td>
              <td>{html_escape(row.get('currentErrors'))}</td>
              <td>{render_badge(status)}</td>
            </tr>
            """
        )
    return "\n".join(rendered)


def render_error_list(errors: list[dict[str, Any]]) -> str:
    if not errors:
        return '<div class="empty-state">最新抓取批次沒有記錄中的錯誤。</div>'
    items = []
    for row in sorted(errors, key=lambda item: (item.get("platform") or "", item.get("sourceName") or "")):
        items.append(
            f"""
            <article class="status-error-item">
              <div>
                <span class="feed-latest-meta">{html_escape(row.get('seenAt'))} · {html_escape(row.get('platform'))}</span>
                <strong>{html_escape(row.get('sourceName'))}</strong>
              </div>
              <p>{html_escape(row.get('error'))}</p>
            </article>
            """
        )
    return "\n".join(items)


def render_status_page(status: dict[str, Any]) -> str:
    overall = status["overall"]
    metrics = status["metrics"]
    component_cards = "\n".join(render_component_card(item) for item in status["components"])
    platform_rows = render_platform_rows(status["watchSources"]["platformRows"])
    error_list = render_error_list(status["recentErrors"])
    return f"""<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>抓資料狀態｜臺灣口琴觀測站</title>
    <meta name="description" content="臺灣口琴觀測站資料抓取、RSSHub、Apify、YouTube 與公開 API 的最新健康狀態。">
    <link rel="icon" href="/assets/favicon-20260623.svg?v={ASSET_VERSION}" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/styles.css?v={ASSET_VERSION}">
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="/" aria-label="臺灣口琴觀測站首頁">
        <img class="brand-logo" src="/assets/logo.svg?v={ASSET_VERSION}" alt="臺灣口琴觀測站" width="200" height="47">
      </a>
      <nav class="site-nav" aria-label="主要導覽">
        <a href="/">首頁</a>
        <a href="/directory/">資料索引</a>
        <a href="/status/">狀態</a>
      </nav>
    </header>

    <main class="status-page-main">
      <section class="feed-page-hero status-hero">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Status</p>
            <h1>抓資料狀態</h1>
          </div>
          <div class="feed-page-summary status-summary-panel">
            <div class="status-summary-line">
              {render_badge(overall["status"], overall["label"])}
              <strong>{html_escape(overall["summary"])}</strong>
            </div>
            <p>快照時間 {html_escape(status.get("generatedAt"))}</p>
            <div class="feed-links">
              <a href="/api/status.json">Status JSON</a>
              <a href="/api/latest.json">Latest API</a>
              <a href="/feeds/updates.xml">更新 RSS</a>
            </div>
          </div>
        </div>
      </section>

      <section class="band status-overview-band" aria-labelledby="status-overview-title">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Snapshot</p>
              <h2 id="status-overview-title">目前快照</h2>
            </div>
            <p class="data-date">資料時間 {html_escape(metrics.get("latestDataAt") or "未記錄")}</p>
          </div>
          <div class="status-metric-grid">
            {render_metric("公開更新", metrics.get("updates"), f"最近 {metrics.get('updatesWindowDays') or '-'} 天")}
            {render_metric("公開目錄", metrics.get("directoryEntries"), "sources.json")}
            {render_metric("監看來源", metrics.get("watchSources"), "social_sources.json")}
            {render_metric("目前錯誤", metrics.get("currentErrors"), "最新抓取批次")}
          </div>
        </div>
      </section>

      <section class="band status-component-band" aria-labelledby="status-components-title">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Collectors</p>
              <h2 id="status-components-title">元件狀態</h2>
            </div>
            <p class="data-date">最新社群觀測 {html_escape(metrics.get("latestSocialObservationAt") or "未記錄")}</p>
          </div>
          <div class="status-component-grid">
            {component_cards}
          </div>
        </div>
      </section>

      <section class="band status-platform-band" aria-labelledby="status-platform-title">
        <div class="band-inner split-layout">
          <div>
            <p class="section-kicker">Platforms</p>
            <h2 id="status-platform-title">平台來源</h2>
          </div>
          <div class="status-table-wrap">
            <table class="status-table">
              <thead>
                <tr>
                  <th scope="col">平台</th>
                  <th scope="col">來源數</th>
                  <th scope="col">目前錯誤</th>
                  <th scope="col">狀態</th>
                </tr>
              </thead>
              <tbody>
                {platform_rows}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="band status-errors-band" aria-labelledby="status-errors-title">
        <div class="band-inner">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Latest Errors</p>
              <h2 id="status-errors-title">最新錯誤</h2>
            </div>
            <p class="data-date">最多顯示 20 筆</p>
          </div>
          <div class="status-error-list">
            {error_list}
          </div>
        </div>
      </section>
    </main>

    <footer class="site-footer">
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
    </footer>
  </body>
</html>
"""


def main() -> int:
    status = build_status()
    STATUS_JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON_OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS_PAGE_OUT.parent.mkdir(parents=True, exist_ok=True)
    status_html = "\n".join(line.rstrip() for line in render_status_page(status).splitlines()) + "\n"
    STATUS_PAGE_OUT.write_text(status_html, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status["overall"]["status"],
                "components": {item["id"]: item["status"] for item in status["components"]},
                "status_json": str(STATUS_JSON_OUT.relative_to(PROJECT_ROOT)),
                "status_page": str(STATUS_PAGE_OUT.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
