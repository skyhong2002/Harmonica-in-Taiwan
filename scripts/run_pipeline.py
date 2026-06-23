#!/usr/bin/env python3
"""Run the standalone public data pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(args: list[str]) -> None:
    subprocess.run(args, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-watch", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--emit-initial", action="store_true")
    parser.add_argument("--max-post-age-days", type=int, default=7)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    run([PYTHON, "scripts/build_public_data.py"])

    if not args.skip_watch:
        watch_args = [PYTHON, "scripts/social_feed_watchdog.py", "--max-post-age-days", str(args.max_post_age_days)]
        if args.baseline:
            watch_args.append("--baseline")
        if args.emit_initial:
            watch_args.append("--emit-initial")
        if args.verbose:
            watch_args.append("--verbose")
        run(watch_args)

    run([PYTHON, "scripts/generate_rss_feeds.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
