#!/usr/bin/env python3
"""Validate generated public outputs before publishing."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
FEEDS_DIR = SITE_ROOT / "feeds"
SITE_DATA_DIR = SITE_ROOT / "data"

REQUIRED_FILES = [
    API_DIR / "latest.json",
    API_DIR / "catalog.json",
    API_DIR / "events.json",
    API_DIR / "posts-videos.json",
    API_DIR / "student-clubs.json",
    API_DIR / "opportunities.json",
    API_DIR / "sources.json",
    API_DIR / "status.json",
    SITE_DATA_DIR / "site-data.js",
    SITE_DATA_DIR / "feed-data.js",
    FEEDS_DIR / "updates.xml",
    FEEDS_DIR / "sources.xml",
    SITE_ROOT / "index.html",
    SITE_ROOT / "status" / "index.html",
]

ASSET_REF_RE = re.compile(r"(?P<path>/assets/(?:feed-images|source-avatars)/[^\"'()<>\s?#]+)")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing required output: {path.relative_to(PROJECT_ROOT)}")


def validate_json_files(errors: list[str]) -> None:
    for path in sorted([*API_DIR.glob("*.json"), *FEEDS_DIR.glob("*.json")]):
        try:
            read_json(path)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {path.relative_to(PROJECT_ROOT)}:{exc.lineno}:{exc.colno}: {exc.msg}")


def validate_js_files(errors: list[str]) -> None:
    node = shutil.which("node")
    if not node:
        print("validate_public_outputs: node not found; skipping JS syntax checks", file=sys.stderr)
        return
    for path in sorted(SITE_DATA_DIR.glob("*.js")):
        result = subprocess.run([node, "--check", str(path)], cwd=PROJECT_ROOT)
        if result.returncode != 0:
            errors.append(f"invalid JS syntax: {path.relative_to(PROJECT_ROOT)}")


def validate_status_consistency(errors: list[str]) -> None:
    status_path = API_DIR / "status.json"
    sources_path = API_DIR / "sources.json"
    if not status_path.exists() or not sources_path.exists():
        return
    try:
        status = read_json(status_path)
        sources = read_json(sources_path)
    except json.JSONDecodeError:
        return
    metrics = status.get("metrics") if isinstance(status, dict) else {}
    stats = sources.get("stats") if isinstance(sources, dict) else {}

    directory_entries = metrics.get("directoryEntries") if isinstance(metrics, dict) else None
    source_count = sources.get("count") if isinstance(sources, dict) else None
    if directory_entries != source_count:
        errors.append(
            "status/source mismatch: "
            f"status.metrics.directoryEntries={directory_entries!r}, sources.count={source_count!r}"
        )

    watch_sources = metrics.get("watchSources") if isinstance(metrics, dict) else None
    stats_watch_sources = stats.get("watchSources") if isinstance(stats, dict) else {}
    total_sources = (
        stats.get("totalSources")
        if isinstance(stats, dict) and stats.get("totalSources") is not None
        else stats_watch_sources.get("totalSources") if isinstance(stats_watch_sources, dict) else None
    )
    if watch_sources != total_sources:
        errors.append(
            "status/source mismatch: "
            f"status.metrics.watchSources={watch_sources!r}, sources.stats.watchSources.totalSources={total_sources!r}"
        )


def asset_reference_files() -> list[Path]:
    paths: list[Path] = []
    paths.extend(API_DIR.glob("*.json"))
    paths.extend(FEEDS_DIR.glob("*.json"))
    paths.extend(FEEDS_DIR.glob("*.html"))
    paths.extend(SITE_DATA_DIR.glob("*.js"))
    paths.extend([SITE_ROOT / "index.html", SITE_ROOT / "status" / "index.html"])
    return sorted(path for path in paths if path.exists())


def validate_asset_references(errors: list[str]) -> None:
    missing: dict[str, set[str]] = {}
    for path in asset_reference_files():
        text = path.read_text(encoding="utf-8")
        for match in ASSET_REF_RE.finditer(text):
            asset_path = match.group("path")
            local_path = SITE_ROOT / asset_path.removeprefix("/")
            if not local_path.exists():
                missing.setdefault(asset_path, set()).add(str(path.relative_to(PROJECT_ROOT)))
    for asset_path, refs in sorted(missing.items()):
        ref_list = ", ".join(sorted(refs)[:5])
        extra = "" if len(refs) <= 5 else f", +{len(refs) - 5} more"
        errors.append(f"missing referenced asset: {asset_path} used by {ref_list}{extra}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-js", action="store_true", help="Skip node --check for generated JS bundles.")
    args = parser.parse_args()

    errors: list[str] = []
    validate_required_files(errors)
    validate_json_files(errors)
    if not args.skip_js:
        validate_js_files(errors)
    validate_status_consistency(errors)
    validate_asset_references(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Public outputs validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
