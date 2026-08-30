#!/usr/bin/env python3
"""Interactively create the local Instaloader session used by the pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

import instaloader

from instaloader_story_fetcher import DEFAULT_SESSION_PATH, login_user_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--login-user", required=True)
    parser.add_argument(
        "--load-cookies",
        metavar="BROWSER",
        help="Import the existing Instagram login from Chrome or another Instaloader-supported browser.",
    )
    parser.add_argument("--session-file", type=Path, default=DEFAULT_SESSION_PATH)
    args = parser.parse_args()
    login_user = args.login_user.strip().strip("@")
    if not login_user:
        parser.error("--login-user cannot be empty")

    loader = instaloader.Instaloader(
        quiet=False,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        max_connection_attempts=1,
        request_timeout=20,
        iphone_support=False,
    )
    if args.load_cookies:
        try:
            from instaloader.__main__ import import_session
        except ImportError as exc:
            raise RuntimeError("Instaloader browser-cookie support is unavailable") from exc
        import_session(args.load_cookies.casefold(), loader, None)
    else:
        loader.interactive_login(login_user)
    authenticated_user = loader.test_login()
    if not authenticated_user or authenticated_user.casefold() != login_user.casefold():
        raise RuntimeError("Instaloader login verification failed")

    session_path = args.session_file.expanduser()
    session_path.parent.mkdir(parents=True, exist_ok=True)
    loader.save_session_to_file(filename=str(session_path))
    session_path.chmod(0o600)
    user_path = login_user_path(session_path)
    user_path.write_text(authenticated_user + "\n", encoding="utf-8")
    user_path.chmod(0o600)
    print(f"Instaloader session ready: {session_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
