#!/usr/bin/env python3
"""Publish the generated static site to the gh-pages branch."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = PROJECT_ROOT / "site"
DEFAULT_WORKTREE = PROJECT_ROOT.with_name(f"{PROJECT_ROOT.name}-gh-pages")
DEFAULT_BRANCH = "gh-pages"
DEFAULT_REMOTE = "origin"
DEFAULT_CNAME = "harmonica.observe.tw"
TAIPEI_TZ = dt.timezone(dt.timedelta(hours=8))


class PublishError(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    cwd: Path = PROJECT_ROOT,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
    )


def git(args: list[str], *, cwd: Path = PROJECT_ROOT, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=cwd, check=check, capture=capture)


def git_stdout(args: list[str], *, cwd: Path = PROJECT_ROOT, check: bool = True) -> str:
    result = git(args, cwd=cwd, check=check, capture=True)
    return result.stdout.strip()


def branch_exists(branch: str) -> bool:
    return git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], check=False).returncode == 0


def remote_branch_exists(remote: str, branch: str) -> bool:
    result = git(["ls-remote", "--exit-code", "--heads", remote, branch], check=False, capture=True)
    return result.returncode == 0


def ensure_clean_worktree(path: Path) -> None:
    status = git_stdout(["status", "--porcelain"], cwd=path)
    if status:
        raise PublishError(f"Deployment worktree is dirty: {path}")


def ensure_existing_worktree(path: Path, branch: str, remote: str) -> None:
    if git(["rev-parse", "--is-inside-work-tree"], cwd=path, check=False, capture=True).returncode != 0:
        raise PublishError(f"Path exists but is not a git worktree: {path}")
    current_branch = git_stdout(["branch", "--show-current"], cwd=path)
    if current_branch != branch:
        raise PublishError(f"Deployment worktree is on {current_branch or 'detached HEAD'}, expected {branch}: {path}")
    ensure_clean_worktree(path)
    if remote_branch_exists(remote, branch):
        git(["pull", "--ff-only", remote, branch], cwd=path)


def ensure_worktree(path: Path, branch: str, remote: str) -> None:
    if path.exists():
        ensure_existing_worktree(path, branch, remote)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists(branch):
        git(["worktree", "add", str(path), branch])
        ensure_existing_worktree(path, branch, remote)
        return

    if remote_branch_exists(remote, branch):
        git(["fetch", remote, f"{branch}:{branch}"])
        git(["worktree", "add", str(path), branch])
        ensure_existing_worktree(path, branch, remote)
        return

    git(["worktree", "add", "--detach", str(path), "HEAD"])
    git(["switch", "--orphan", branch], cwd=path)


def remove_worktree_contents(path: Path) -> None:
    for item in path.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()


def copy_site(site_dir: Path, worktree: Path, *, cname: str) -> None:
    if not site_dir.is_dir():
        raise PublishError(f"Site directory does not exist: {site_dir}")
    remove_worktree_contents(worktree)
    for item in site_dir.iterdir():
        if item.name == ".DS_Store":
            continue
        destination = worktree / item.name
        if item.is_dir() and not item.is_symlink():
            shutil.copytree(item, destination, ignore=shutil.ignore_patterns(".DS_Store"))
        else:
            shutil.copy2(item, destination)
    (worktree / ".nojekyll").write_text("", encoding="utf-8")
    if cname:
        (worktree / "CNAME").write_text(cname.strip() + "\n", encoding="utf-8")


def changed_files(path: Path) -> list[str]:
    status = git_stdout(["status", "--porcelain"], cwd=path)
    return [line for line in status.splitlines() if line.strip()]


def default_message() -> str:
    now = dt.datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    return f"Publish site snapshot {now}"


def repository_slug(remote: str) -> str:
    raw = git_stdout(["remote", "get-url", remote])
    value = raw.removesuffix(".git")
    if value.startswith("git@github.com:"):
        return value.split(":", 1)[1]
    if "github.com/" in value:
        return value.split("github.com/", 1)[1]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--worktree", type=Path, default=DEFAULT_WORKTREE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--cname", default=os.environ.get("HARMONICA_PAGES_CNAME", DEFAULT_CNAME))
    parser.add_argument("--message", default="")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    site_dir = args.site_dir if args.site_dir.is_absolute() else PROJECT_ROOT / args.site_dir
    worktree = args.worktree if args.worktree.is_absolute() else PROJECT_ROOT / args.worktree
    ensure_worktree(worktree, args.branch, args.remote)
    copy_site(site_dir, worktree, cname=args.cname)

    changes = changed_files(worktree)
    pushed = False
    committed = False
    commit = ""
    if changes:
        git(["add", "-A"], cwd=worktree)
        git(["commit", "-m", args.message or default_message()], cwd=worktree)
        committed = True
        commit = git_stdout(["rev-parse", "--short", "HEAD"], cwd=worktree)
        if not args.no_push:
            git(["push", "-u", args.remote, args.branch], cwd=worktree)
            pushed = True
    elif not args.no_push:
        git(["push", "-u", args.remote, args.branch], cwd=worktree)
        pushed = True
        commit = git_stdout(["rev-parse", "--short", "HEAD"], cwd=worktree)

    result: dict[str, Any] = {
        "repository": repository_slug(args.remote),
        "branch": args.branch,
        "worktree": str(worktree),
        "site_dir": str(site_dir),
        "cname": args.cname,
        "changed": bool(changes),
        "committed": committed,
        "pushed": pushed,
        "commit": commit,
        "changes": changes,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"Published {site_dir} to {args.remote}/{args.branch}"
            f" ({'changed' if changes else 'unchanged'}, commit={commit or 'none'}, pushed={pushed})."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublishError as exc:
        print(f"publish_github_pages.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
