#!/usr/bin/env python3
"""Fetch one public Instagram profile's current stories with Instaloader.

The helper runs in a dedicated venv because the main pipeline intentionally uses
the macOS system Python. It writes normalized JSON to stdout and never prints
session cookies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.cookies
import json
import os
import sys
from pathlib import Path
from typing import Any

import instaloader


DEFAULT_SESSION_PATH = Path.home() / ".config" / "harmonica" / "instaloader-session"
DEFAULT_ENV_PATH = Path.home() / ".config" / "harmonica" / "rsshub.env"


def env_file_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        candidate, value = line.split("=", 1)
        if candidate.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def cookie_dict(value: str) -> dict[str, str]:
    jar = http.cookies.SimpleCookie()
    jar.load(value or "")
    return {key: morsel.value for key, morsel in jar.items() if morsel.value}


def login_user_path(session_path: Path) -> Path:
    return session_path.with_name(session_path.name + ".user")


def utc_iso(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat()


def load_authenticated_loader(session_path: Path, env_path: Path) -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=1,
        request_timeout=20,
        iphone_support=False,
    )
    user_path = login_user_path(session_path)
    if session_path.exists() and user_path.exists():
        login_user = user_path.read_text(encoding="utf-8").strip()
        if login_user:
            try:
                loader.load_session_from_file(login_user, filename=str(session_path))
                # This helper runs once per account. A separate test_login()
                # here would double the authenticated requests for every
                # source; the profile/Story request is the real session check.
                return loader
            except (OSError, instaloader.exceptions.InstaloaderException):
                pass

    raw_cookie = os.environ.get("HARMONICA_IG_COOKIE", "").strip()
    if not raw_cookie:
        raw_cookie = os.environ.get("IG_COOKIE", "").strip()
    if not raw_cookie:
        raw_cookie = env_file_value(env_path, "IG_COOKIE")
    cookies = cookie_dict(raw_cookie)
    if not cookies.get("sessionid"):
        raise RuntimeError("Instaloader session missing; refresh the Instagram login session")
    loader.context.update_cookies(cookies)
    login_user = loader.test_login()
    if not login_user:
        raise RuntimeError("Instaloader session rejected by Instagram; refresh the Instagram login session")
    loader.context.username = login_user
    session_path.parent.mkdir(parents=True, exist_ok=True)
    loader.save_session_to_file(filename=str(session_path))
    session_path.chmod(0o600)
    user_path.write_text(login_user + "\n", encoding="utf-8")
    user_path.chmod(0o600)
    return loader


def story_row(item: Any, username: str) -> dict[str, Any]:
    media_id = str(item.mediaid)
    image_url = str(item.url or "")
    video_url = str(item.video_url or "") if item.is_video else ""
    return {
        "id": media_id,
        "username": str(item.owner_username or username),
        "caption": str(item.caption or ""),
        "posted_at": utc_iso(item.date_utc),
        "expires_at": utc_iso(item.expiring_utc),
        "url": f"https://www.instagram.com/stories/{username}/{media_id}/",
        "images": [image_url] if image_url else [],
        "videos": [video_url] if video_url else [],
    }


def resolve_user_id(loader: instaloader.Instaloader, username: str, user_id: str = "") -> str:
    if user_id:
        return user_id
    for profile in instaloader.TopSearchResults(loader.context, username).get_profiles():
        if profile.username.casefold() == username.casefold():
            return str(profile.userid)
    return ""


def fetch_stories(
    loader: instaloader.Instaloader,
    username: str,
    limit: int,
    user_id: str = "",
) -> list[dict[str, Any]]:
    resolved_user_id = resolve_user_id(loader, username, user_id)
    if resolved_user_id:
        user_ids = [int(resolved_user_id)]
    else:
        profile = instaloader.Profile.from_username(loader.context, username)
        user_ids = [profile.userid]
    rows: list[dict[str, Any]] = []
    for story in loader.get_stories(userids=user_ids):
        for item in story.get_items():
            rows.append(story_row(item, username))
    rows.sort(key=lambda row: str(row.get("posted_at") or ""), reverse=True)
    return rows[: max(1, limit)]


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
        stories = fetch_stories(loader, username, args.limit, args.user_id.strip())
    except (OSError, RuntimeError, instaloader.exceptions.InstaloaderException) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "version": 1,
                "provider": "instaloader",
                "username": username,
                "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "stories": stories,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
