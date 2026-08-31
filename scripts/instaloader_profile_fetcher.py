#!/usr/bin/env python3
"""Fetch one public Instagram profile's recent posts with Instaloader."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import instaloader

from instaloader_story_fetcher import (
    DEFAULT_ENV_PATH,
    DEFAULT_SESSION_PATH,
    load_authenticated_loader,
    resolve_user_id,
    utc_iso,
)


def post_row(post: Any, username: str) -> dict[str, Any]:
    image_url = str(post.url or "")
    video_url = ""
    if post.is_video:
        try:
            video_url = str(post.video_url or "")
        except instaloader.exceptions.InstaloaderException:
            video_url = ""
    return {
        "id": str(post.mediaid),
        "username": username,
        "caption": str(post.caption or ""),
        "posted_at": utc_iso(post.date_utc),
        "url": f"https://www.instagram.com/p/{post.shortcode}/",
        "images": [image_url] if image_url else [],
        "videos": [video_url] if video_url else [],
    }


def fetch_posts(
    loader: instaloader.Instaloader,
    username: str,
    user_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    resolved_user_id = resolve_user_id(loader, username, user_id)
    if resolved_user_id:
        # Instaloader's current Profile.from_username() calls Instagram's
        # broken web_profile_info schema.  A minimal profile node plus the
        # durable user-id cache lets the authenticated timeline query run
        # without that endpoint.
        profile = instaloader.Profile(loader.context, {"id": resolved_user_id, "username": username})
        profile._has_full_metadata = True
    else:
        profile = instaloader.Profile.from_username(loader.context, username)
    rows: list[dict[str, Any]] = []
    for post in profile.get_posts():
        rows.append(post_row(post, username))
        if len(rows) >= max(1, limit):
            break
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--user-id", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--session-file",
        type=Path,
        default=Path(os.environ.get("HARMONICA_INSTALOADER_SESSION", DEFAULT_SESSION_PATH)),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(os.environ.get("HARMONICA_RSSHUB_ENV", DEFAULT_ENV_PATH)),
    )
    args = parser.parse_args()
    username = args.username.strip().strip("@/")
    if not username:
        print("Instaloader username is empty", file=sys.stderr)
        return 2
    try:
        loader = load_authenticated_loader(args.session_file.expanduser(), args.env_file.expanduser())
        posts = fetch_posts(loader, username, args.user_id.strip(), args.limit)
    except (OSError, RuntimeError, ValueError, instaloader.exceptions.InstaloaderException) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "version": 1,
                "provider": "instaloader",
                "username": username,
                "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "posts": posts,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
