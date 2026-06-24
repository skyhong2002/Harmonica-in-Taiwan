#!/usr/bin/env python3
"""Run the standalone public data pipeline."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(args: list[str], *, optional: bool = False) -> None:
    try:
        subprocess.run(args, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        if not optional:
            raise
        print(f"Optional pipeline step failed with exit code {exc.returncode}: {' '.join(args)}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-watch", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--emit-initial", action="store_true")
    parser.add_argument("--max-post-age-days", type=int, default=30)
    parser.add_argument("--skip-source-build", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-facebook", action="store_true")
    parser.add_argument("--skip-llm-tags", action="store_true")
    parser.add_argument("--facebook-dry-run", action="store_true")
    parser.add_argument("--youtube-full-refresh", action="store_true")
    parser.add_argument("--facebook-priority", action="store_true")
    parser.add_argument("--facebook-full-refresh", action="store_true")
    parser.add_argument("--facebook-provider-days-back", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not args.skip_source_build:
        run([PYTHON, "scripts/build_social_sources.py"])

    if not args.skip_watch:
        if not args.skip_youtube:
            youtube_args = [
                PYTHON,
                "scripts/youtube_ytdlp_fetcher.py",
                "--max-post-age-days",
                str(args.max_post_age_days),
            ]
            if args.youtube_full_refresh:
                youtube_args.append("--full-refresh")
            if args.verbose:
                youtube_args.append("--verbose")
            run(youtube_args, optional=True)
        if not args.skip_facebook:
            provider_days_back = args.facebook_provider_days_back or args.max_post_age_days
            facebook_args = [
                PYTHON,
                "scripts/apify_facebook_fetcher.py",
                "--days-back",
                str(provider_days_back),
                "--local-max-post-age-days",
                str(args.max_post_age_days),
            ]
            if args.facebook_priority:
                facebook_args.append("--priority")
            if args.facebook_full_refresh:
                facebook_args.append("--full-refresh")
            if not args.facebook_dry_run and os.environ.get("HARMONICA_SKIP_APIFY_FACEBOOK", "") not in {"1", "true", "TRUE"}:
                facebook_args.append("--run")
            run(facebook_args, optional=True)

        watch_args = [PYTHON, "scripts/social_feed_watchdog.py", "--max-post-age-days", str(args.max_post_age_days)]
        if args.skip_llm_tags:
            watch_args.append("--no-llm-tags")
        if args.baseline:
            watch_args.append("--baseline")
        if args.emit_initial:
            watch_args.append("--emit-initial")
        if args.verbose:
            watch_args.append("--verbose")
        run(watch_args)

    run([PYTHON, "scripts/build_public_data.py"])
    run([PYTHON, "scripts/backfill_public_source_pages.py", "--skip-fetch"])
    run([PYTHON, "scripts/build_public_data.py"])
    run([PYTHON, "scripts/generate_rss_feeds.py"])
    run([PYTHON, "scripts/check_source_coverage.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
