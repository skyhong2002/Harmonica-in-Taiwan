#!/usr/bin/env python3
"""Fetch a small, budget-capped batch of public Facebook posts through Apify."""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(os.environ.get("HARMONICA_OBSERVE_HOME", Path(__file__).resolve().parents[1])).expanduser()
DEFAULT_CONFIG = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
DEFAULT_INBOX = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"
DEFAULT_LEDGER = PROJECT_ROOT / "state" / "apify_facebook_fetcher.json"
DEFAULT_ERRORS = PROJECT_ROOT / "data" / "feeds" / "social_feed_errors.jsonl"

APIFY_BASE = "https://api.apify.com/v2"
FACEBOOK_POSTS_ACTOR = "apify/facebook-posts-scraper"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}

KEYCHAIN_CANDIDATES = [
    (
        os.environ.get("HARMONICA_APIFY_KEYCHAIN_SERVICE", "harmonica-observe-apify"),
        os.environ.get("HARMONICA_APIFY_KEYCHAIN_ACCOUNT", "harmonica"),
    ),
    ("bamboo-apify", "bamboo"),
]

PRIORITY_SOURCE_IDS = [
    "fb_ntubluesound",
    "fb_ntnu_harmonica",
    "fb_ncku_harmonica",
    "fb_nthuharmonica",
    "fb_fcu_harmonica",
    "fb_nutc_harmonica",
    "fb_csmu_bmharmonica",
    "fb_nkustharmonica",
    "fb_twharmonica",
    "fb_siriusharp",
    "fb_judys_harmonica_ensemble",
    "fb_punch_harp",
    "fb_harmonicasymphony",
    "fb_tcharmonicaa",
    "fb_harpdonuts",
    "fb_tcfsh_harmonica",
    "fb_hsnucozy",
]


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


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_errors(path: Path, errors: list[dict[str, Any]]) -> None:
    if not errors:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    append_jsonl(path, [{**error, "seen_at": now} for error in errors])


def read_token() -> tuple[str, str]:
    for key in ("HARMONICA_APIFY_API_TOKEN", "BAMBOO_APIFY_API_TOKEN", "APIFY_TOKEN", "APIFY_API_TOKEN"):
        value = os.environ.get(key)
        if value:
            return value.strip(), f"env:{key}"

    seen_pairs: set[tuple[str, str]] = set()
    for service, account in KEYCHAIN_CANDIDATES:
        if not service or not account or (service, account) in seen_pairs:
            continue
        seen_pairs.add((service, account))
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), f"keychain:{service}/{account}"
    return "", ""


def actor_api_id(actor_id: str) -> str:
    return actor_id.replace("/", "~")


def apify_request(
    method: str,
    path: str,
    token: str,
    *,
    query: dict[str, Any] | None = None,
    body: Any | None = None,
    timeout: int = 60,
) -> Any:
    params = dict(query or {})
    params["token"] = token
    url = APIFY_BASE + path + "?" + urllib.parse.urlencode(params)
    data = None
    headers = {"Accept": "application/json", "User-Agent": "HarmonicaObserveApifyFetcher/1.0"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Apify HTTP {exc.code}: {detail}") from exc
    return json.loads(raw) if raw else {}


def load_facebook_sources(config_path: Path, source_ids: list[str]) -> list[dict[str, Any]]:
    config = load_json(config_path, {"sources": []})
    selected = set(source_ids)
    sources: list[dict[str, Any]] = []
    for source in config.get("sources", []):
        if source.get("type") != "facebook_page_posts":
            continue
        if not source.get("enabled", True):
            continue
        if selected and source.get("id") not in selected:
            continue
        if not (source.get("page") or source.get("url")):
            continue
        sources.append(source)
    return sources


def ledger_runs(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    runs = ledger.get("runs")
    return runs if isinstance(runs, list) else []


def select_sources(sources: list[dict[str, Any]], ledger: dict[str, Any], max_sources: int) -> tuple[list[dict[str, Any]], int]:
    if max_sources <= 0 or max_sources >= len(sources):
        return sources, int(ledger.get("next_source_index") or 0)
    start = int(ledger.get("next_source_index") or 0) % len(sources)
    selected = [sources[(start + offset) % len(sources)] for offset in range(max_sources)]
    return selected, start


def select_priority_sources(sources: list[dict[str, Any]], max_sources: int) -> tuple[list[dict[str, Any]], int]:
    by_id = {str(source.get("id") or ""): source for source in sources}
    selected = [by_id[source_id] for source_id in PRIORITY_SOURCE_IDS if source_id in by_id]
    selected_ids = {str(source.get("id") or "") for source in selected}
    selected.extend(source for source in sources if str(source.get("id") or "") not in selected_ids)
    if max_sources > 0:
        selected = selected[:max_sources]
    return selected, 0


def facebook_url(source: dict[str, Any]) -> str:
    url = str(source.get("url") or "").strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    page = str(source.get("page") or "").strip().strip("/")
    if page.startswith("http://") or page.startswith("https://"):
        return page
    return f"https://www.facebook.com/{page}/"


def apify_input(sources: list[dict[str, Any]], results_limit: int, days_back: int, include_video_transcript: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "startUrls": [{"url": facebook_url(source)} for source in sources],
        "resultsLimit": results_limit,
        "captionText": include_video_transcript,
    }
    if days_back > 0:
        data["onlyPostsNewerThan"] = f"{days_back} days"
    return data


def estimate_max_charge_usd(results_limit: int, source_count: int) -> float:
    return round(0.006 + 0.005 * max(results_limit, source_count, 1), 4)


def fetch_user_limits(token: str) -> dict[str, Any]:
    data = apify_request("GET", "/users/me/limits", token, timeout=30).get("data", {})
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    limits = data.get("limits") if isinstance(data.get("limits"), dict) else {}
    return {
        "monthly_usage_usd": float(current.get("monthlyUsageUsd") or 0),
        "max_monthly_usage_usd": float(limits.get("maxMonthlyUsageUsd") or 0),
        "cycle": data.get("monthlyUsageCycle") or {},
    }


def run_cost(row: dict[str, Any]) -> float:
    for key in ("usage_total_usd", "platform_usage_total_usd", "remote_usage_delta_usd", "charged_usd"):
        value = row.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    for key in ("reserved_usd", "max_total_charge_usd"):
        value = row.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return 0.0


def budget_window_cost(ledger: dict[str, Any], since: dt.datetime) -> float:
    total = 0.0
    for row in ledger_runs(ledger):
        raw = str(row.get("started_at") or row.get("created_at") or "")
        try:
            started = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if started.tzinfo is None:
            started = started.replace(tzinfo=dt.timezone.utc)
        if started >= since:
            total += run_cost(row)
    return round(total, 6)


def enforce_budget(ledger: dict[str, Any], reserve_usd: float, daily_budget_usd: float, monthly_budget_usd: float) -> dict[str, float]:
    now = dt.datetime.now(dt.timezone.utc)
    day_cost = budget_window_cost(ledger, now - dt.timedelta(hours=24))
    month_cost = budget_window_cost(ledger, now - dt.timedelta(days=30))
    if day_cost + reserve_usd > daily_budget_usd:
        raise RuntimeError(
            f"Budget guard blocked run: 24h ledger {day_cost:.4f} + reserve {reserve_usd:.4f} > daily {daily_budget_usd:.4f} USD"
        )
    if month_cost + reserve_usd > monthly_budget_usd:
        raise RuntimeError(
            f"Budget guard blocked run: 30d ledger {month_cost:.4f} + reserve {reserve_usd:.4f} > monthly {monthly_budget_usd:.4f} USD"
        )
    return {"last_24h_usd": day_cost, "last_30d_usd": month_cost}


def enforce_remote_monthly_budget(limits: dict[str, Any], reserve_usd: float, monthly_budget_usd: float) -> dict[str, float]:
    current = float(limits.get("monthly_usage_usd") or 0)
    account_limit = float(limits.get("max_monthly_usage_usd") or 0)
    effective_limit = min(monthly_budget_usd, account_limit) if account_limit else monthly_budget_usd
    if current + reserve_usd > effective_limit:
        raise RuntimeError(
            f"Remote Apify budget guard blocked run: monthly usage {current:.4f} + reserve {reserve_usd:.4f} > limit {effective_limit:.4f} USD"
        )
    return {"remote_monthly_usage_usd": current, "remote_monthly_limit_usd": account_limit}


def compact_text(value: Any, limit: int = 1800) -> str:
    if value is None:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in str(value).splitlines()]
    if len(lines) <= 1:
        return re.sub(r"\s+", " ", str(value)).strip()[:limit]
    return "\n".join(line for line in lines if line).strip()[:limit]


def first_value(item: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    return ""


def nested_first_value(item: Any, names: list[str]) -> Any:
    if isinstance(item, dict):
        direct = first_value(item, names)
        if direct:
            return direct
        for value in item.values():
            nested = nested_first_value(value, names)
            if nested:
                return nested
    elif isinstance(item, list):
        for value in item[:12]:
            nested = nested_first_value(value, names)
            if nested:
                return nested
    return ""


def nested_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for key in ("text", "title", "description", "name", "url"):
            if value.get(key):
                parts.append(str(value[key]))
        return " ".join(parts)
    if isinstance(value, list):
        return " ".join(nested_text(item) for item in value[:8])
    return ""


def looks_like_image_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.casefold()
    suffix = Path(parsed.path).suffix.casefold()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return True
    return any(marker in host for marker in ("fbcdn.net", "cdninstagram.com", "ytimg.com"))


def nested_image_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str) and value.startswith(("http://", "https://")) and looks_like_image_url(value):
        urls.append(value)
    elif isinstance(value, dict):
        for key in ("image", "imageUrl", "image_url", "url", "thumbnail", "thumbnailUrl", "displayUrl", "mediaUrl"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.startswith(("http://", "https://")) and looks_like_image_url(raw):
                urls.append(raw)
        for key in ("attachments", "media", "images", "photos"):
            urls.extend(nested_image_urls(value.get(key)))
    elif isinstance(value, list):
        for item in value[:12]:
            urls.extend(nested_image_urls(item))
    result: list[str] = []
    for url in urls:
        if url not in result:
            result.append(url)
    return result


def is_actor_error_item(item: dict[str, Any]) -> bool:
    if not item.get("error"):
        return False
    has_post_fields = any(item.get(key) for key in ("url", "postUrl", "facebookUrl", "link", "permalink", "topLevelUrl"))
    return not has_post_fields


def parse_post_time(value: str) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        timestamp = int(raw)
        if timestamp > 10_000_000_000:
            timestamp = int(timestamp / 1000)
        try:
            return dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
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


def local_recent_filter(rows: list[dict[str, Any]], max_age_days: int, now: dt.datetime) -> tuple[list[dict[str, Any]], int, int]:
    if max_age_days <= 0:
        return rows, 0, 0
    cutoff = now - dt.timedelta(days=max_age_days)
    kept: list[dict[str, Any]] = []
    dropped_old = 0
    dropped_undated = 0
    for row in rows:
        posted = parse_post_time(str(row.get("posted_at") or ""))
        if posted is None:
            dropped_undated += 1
            continue
        if posted < cutoff:
            dropped_old += 1
            continue
        kept.append(row)
    return kept, dropped_old, dropped_undated


def match_source(item: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    urls = " ".join(
        compact_text(first_value(item, ["url", "postUrl", "facebookUrl", "pageUrl", "profileUrl", "userUrl", "link", "topLevelUrl"]))
        for _ in range(1)
    ).lower()
    for source in sources:
        page = str(source.get("page") or "").strip("/").lower()
        source_url = str(source.get("url") or "").strip("/").lower()
        if page and page in urls:
            return source
        if source_url and source_url in urls:
            return source
    account = compact_text(first_value(item, ["pageName", "profileName", "userName", "author", "ownerName"])).lower()
    for source in sources:
        name = str(source.get("name") or "").lower()
        if name and name in account:
            return source
    return sources[0] if len(sources) == 1 else None


def normalize_item(item: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    source = match_source(item, sources) or {"id": "apify_facebook_posts", "name": "Apify Facebook Posts", "page": ""}
    url = compact_text(first_value(item, ["url", "postUrl", "facebookUrl", "link", "permalink", "topLevelUrl"]))
    post_id = compact_text(first_value(item, ["postId", "id", "post_id", "legacyId", "shortCode"])) or url
    posted_at = compact_text(first_value(item, ["time", "timestamp", "date", "createdAt", "created_time", "publishedAt"]))
    text_parts = [
        first_value(item, ["text", "message", "caption", "content", "description", "title"]),
        nested_text(item.get("attachments")),
        nested_text(item.get("media")),
        nested_text(item.get("externalLinks")),
    ]
    images = nested_image_urls(item)
    source_avatar = compact_text(
        nested_first_value(item, ["profilePic", "profilePicture", "profileImage", "pageProfilePicture", "avatar", "authorProfilePic"])
    )
    return {
        "account": source.get("page") or source.get("url") or first_value(item, ["pageName", "profileName", "userName", "author"]),
        "image_url": images[0] if images else "",
        "images": images[:5],
        "platform": "facebook",
        "post_id": post_id,
        "posted_at": posted_at,
        "raw_source": FACEBOOK_POSTS_ACTOR,
        "source_avatar_url": source_avatar,
        "source_id": source.get("id") or "apify_facebook_posts",
        "source_name": source.get("name") or source.get("id") or "Apify Facebook Posts",
        "text": compact_text("\n".join(str(part) for part in text_parts if part)),
        "url": url,
    }


def existing_inbox_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = f"{row.get('source_id')}:{row.get('post_id') or row.get('url')}"
            keys.add(key)
    return keys


def filter_new_rows(rows: list[dict[str, Any]], inbox: Path) -> list[dict[str, Any]]:
    seen = existing_inbox_keys(inbox)
    result = []
    for row in rows:
        key = f"{row.get('source_id')}:{row.get('post_id') or row.get('url')}"
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def run_actor(
    token: str,
    sources: list[dict[str, Any]],
    *,
    results_limit: int,
    days_back: int,
    max_items: int,
    max_total_charge_usd: float,
    memory_mbytes: int,
    timeout_secs: int,
    poll_secs: float,
    include_video_transcript: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actor_id = actor_api_id(FACEBOOK_POSTS_ACTOR)
    body = apify_input(sources, results_limit, days_back, include_video_transcript)
    run_data = apify_request(
        "POST",
        f"/acts/{actor_id}/runs",
        token,
        query={
            "maxTotalChargeUsd": max_total_charge_usd,
            "maxItems": max_items,
            "memory": memory_mbytes,
            "timeout": timeout_secs,
            "restartOnError": "false",
        },
        body=body,
        timeout=60,
    ).get("data", {})
    run_id = run_data.get("id")
    if not run_id:
        raise RuntimeError(f"Apify did not return a run id: {run_data}")

    deadline = time.monotonic() + timeout_secs + 45
    while run_data.get("status") not in TERMINAL_STATUSES:
        if time.monotonic() > deadline:
            raise RuntimeError(f"Timed out waiting for Apify run {run_id}; current status={run_data.get('status')}")
        time.sleep(poll_secs)
        run_data = apify_request("GET", f"/actor-runs/{run_id}", token, timeout=30).get("data", {})

    dataset_id = run_data.get("defaultDatasetId")
    items: list[dict[str, Any]] = []
    if dataset_id and run_data.get("status") == "SUCCEEDED":
        items_data = apify_request(
            "GET",
            f"/datasets/{dataset_id}/items",
            token,
            query={"format": "json", "clean": "true", "limit": max_items},
            timeout=60,
        )
        items = items_data if isinstance(items_data, list) else []
    return run_data, items


def usage_total_usd(run_data: dict[str, Any]) -> float | None:
    for key in ("usageTotalUsd", "usageUsd", "costUsd"):
        value = run_data.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    usage = run_data.get("usage") or {}
    if isinstance(usage, dict):
        total = usage.get("totalUsd") or usage.get("totalUSd")
        if isinstance(total, (int, float)):
            return float(total)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--errors", type=Path, default=DEFAULT_ERRORS)
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--priority", action="store_true")
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--max-sources-per-run", type=int, default=5)
    parser.add_argument("--results-limit", type=int, default=5)
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--local-max-post-age-days", type=int, default=7)
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--max-total-charge-usd", type=float, default=0.04)
    parser.add_argument("--daily-budget-usd", type=float, default=0.15)
    parser.add_argument("--monthly-budget-usd", type=float, default=2.50)
    parser.add_argument("--memory-mbytes", type=int, default=1024)
    parser.add_argument("--timeout-secs", type=int, default=180)
    parser.add_argument("--poll-secs", type=float, default=5.0)
    parser.add_argument("--include-video-transcript", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    all_sources = load_facebook_sources(args.config, args.source_id)
    ledger = load_json(args.ledger, {"runs": [], "next_source_index": 0})
    max_sources = 0 if args.full_refresh else args.max_sources_per_run
    if args.priority and not args.source_id:
        sources, start_index = select_priority_sources(all_sources, max_sources)
    else:
        sources, start_index = select_sources(all_sources, ledger, max_sources)
    token, token_source = read_token()
    reserve = args.max_total_charge_usd
    budget_status = enforce_budget(ledger, reserve, args.daily_budget_usd, args.monthly_budget_usd)
    remote_budget_status: dict[str, Any] = {}
    if token:
        try:
            remote_limits = fetch_user_limits(token)
            remote_budget_status = enforce_remote_monthly_budget(remote_limits, reserve, args.monthly_budget_usd)
        except Exception as exc:
            if args.run:
                raise
            remote_budget_status = {"remote_budget_check_error": str(exc)}

    plan = {
        "actor": FACEBOOK_POSTS_ACTOR,
        "sources_total": len(all_sources),
        "sources_selected": [{"id": s.get("id"), "page": s.get("page"), "url": s.get("url"), "name": s.get("name")} for s in sources],
        "selected_start_index": start_index,
        "results_limit": args.results_limit,
        "days_back": args.days_back,
        "local_max_post_age_days": args.local_max_post_age_days,
        "max_items": args.max_items,
        "max_total_charge_usd": args.max_total_charge_usd,
        "reserve_usd_for_budget_guard": reserve,
        "estimated_actor_price_usd": estimate_max_charge_usd(args.results_limit, len(sources)),
        "daily_budget_usd": args.daily_budget_usd,
        "monthly_budget_usd": args.monthly_budget_usd,
        "ledger": str(args.ledger),
        "inbox": str(args.inbox),
        "has_token": bool(token),
        "token_source": token_source,
        **budget_status,
        **remote_budget_status,
    }

    if args.check or not args.run:
        print(json.dumps({"dry_run": not args.run, **plan}, ensure_ascii=False, indent=2))
        return 0

    if not token:
        raise SystemExit("Missing Apify token. Set HARMONICA_APIFY_API_TOKEN or store one in Keychain.")
    if not sources:
        raise SystemExit("No enabled facebook_page_posts sources selected.")
    if args.results_limit < 1 or args.results_limit > 20:
        raise SystemExit("--results-limit must stay between 1 and 20 for this budget-capped fetcher.")
    if args.max_items < 1 or args.max_items > 20:
        raise SystemExit("--max-items must stay between 1 and 20 for this budget-capped fetcher.")
    if args.max_total_charge_usd > 0.25:
        raise SystemExit("--max-total-charge-usd is capped at 0.25 by this safe fetcher.")

    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    errors: list[dict[str, Any]] = []
    remote_before = fetch_user_limits(token)
    try:
        run_data, items = run_actor(
            token,
            sources,
            results_limit=args.results_limit,
            days_back=args.days_back,
            max_items=args.max_items,
            max_total_charge_usd=args.max_total_charge_usd,
            memory_mbytes=args.memory_mbytes,
            timeout_secs=args.timeout_secs,
            poll_secs=args.poll_secs,
            include_video_transcript=args.include_video_transcript,
        )
        actor_error_items = [item for item in items if is_actor_error_item(item)]
        post_items = [item for item in items if not is_actor_error_item(item)]
        rows = [normalize_item(item, sources) for item in post_items]
        rows = [row for row in rows if row.get("url") or row.get("text")]
        rows, dropped_old, dropped_undated = local_recent_filter(
            rows,
            args.local_max_post_age_days,
            dt.datetime.now(dt.timezone.utc),
        )
        new_rows = filter_new_rows(rows, args.inbox)
        if not args.no_write:
            append_jsonl(args.inbox, new_rows)
    except Exception as exc:
        errors.append({"source_id": "apify_facebook_posts", "source_type": "apify", "error": str(exc)})
        append_errors(args.errors, errors)
        run_data = {"id": "", "status": "LOCAL_ERROR"}
        items = []
        actor_error_items = []
        post_items = []
        dropped_old = 0
        dropped_undated = 0
        new_rows = []

    try:
        remote_after = fetch_user_limits(token)
    except Exception:
        remote_after = {}
    platform_usage = usage_total_usd(run_data)
    remote_delta = None
    if remote_after:
        remote_delta = round(
            max(0.0, float(remote_after.get("monthly_usage_usd") or 0) - float(remote_before.get("monthly_usage_usd") or 0)),
            6,
        )
    charge_candidates = [
        value
        for value in (remote_delta, platform_usage)
        if isinstance(value, (int, float)) and value > 0
    ]
    charged = max(charge_candidates) if charge_candidates else 0.0
    if all_sources:
        ledger["next_source_index"] = (start_index + len(sources)) % len(all_sources)
    record = {
        "started_at": started_at,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "actor": FACEBOOK_POSTS_ACTOR,
        "run_id": run_data.get("id"),
        "status": run_data.get("status"),
        "source_ids": [source.get("id") for source in sources],
        "results_limit": args.results_limit,
        "days_back": args.days_back,
        "local_max_post_age_days": args.local_max_post_age_days,
        "max_items": args.max_items,
        "max_total_charge_usd": args.max_total_charge_usd,
        "reserved_usd": reserve,
        "usage_total_usd": charged,
        "platform_usage_total_usd": platform_usage,
        "remote_monthly_usage_before_usd": remote_before.get("monthly_usage_usd"),
        "remote_monthly_usage_after_usd": remote_after.get("monthly_usage_usd"),
        "remote_usage_delta_usd": remote_delta,
        "dataset_item_count": len(items),
        "actor_error_item_count": len(actor_error_items),
        "item_count": len(post_items),
        "dropped_old_rows": dropped_old,
        "dropped_undated_rows": dropped_undated,
        "new_inbox_rows": len(new_rows),
        "error_count": len(errors),
    }
    ledger.setdefault("runs", []).append(record)
    ledger["updated_at"] = record["finished_at"]
    ledger["runs"] = ledger_runs(ledger)[-200:]
    save_json(args.ledger, ledger)

    output = {
        "ok": not errors,
        "record": record,
        "new_rows": new_rows[:5],
        "actor_error_items": [
            {
                "inputUrl": item.get("inputUrl"),
                "error": item.get("error"),
                "errorDescription": item.get("errorDescription"),
            }
            for item in actor_error_items[:10]
        ],
        "errors": errors,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
