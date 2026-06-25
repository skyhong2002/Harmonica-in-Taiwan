#!/usr/bin/env python3
"""Convert local raster site assets to WebP and rewrite local references."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
ASSETS_ROOT = SITE_ROOT / "assets"
RASTER_EXTS = {".jpg", ".jpeg", ".png", ".gif"}
TEXT_SKIP_EXTS = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".webp",
}
SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"}
DEFAULT_QUALITY = "82"


def find_binary(name: str) -> str:
    for candidate in (
        shutil.which(name),
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def converter_for(path: Path) -> list[str]:
    if path.suffix.casefold() == ".gif":
        binary = find_binary("gif2webp")
        return [binary, "-quiet"] if binary else []
    binary = find_binary("cwebp")
    return [binary, "-quiet"] if binary else []


def iter_raster_assets() -> list[Path]:
    return sorted(
        path
        for path in ASSETS_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in RASTER_EXTS
    )


def convert_one(path: Path, quality: str) -> tuple[Path, int, int]:
    output = path.with_suffix(".webp")
    command = converter_for(path)
    if not command:
        raise RuntimeError("missing cwebp/gif2webp; install the Homebrew webp package")

    tmp_output = output.with_name(output.name + ".tmp")
    if tmp_output.exists():
        tmp_output.unlink()
    try:
        subprocess.run(
            [*command, "-q", quality, str(path), "-o", str(tmp_output)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        ffmpeg = find_binary("ffmpeg")
        cwebp = find_binary("cwebp")
        if not ffmpeg or not cwebp:
            raise
        decoded = output.with_name(output.name + ".decoded.png")
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-update",
                    "1",
                    str(decoded),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [cwebp, "-quiet", "-q", quality, str(decoded), "-o", str(tmp_output)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            if decoded.exists():
                decoded.unlink()
    original_size = path.stat().st_size
    converted_size = tmp_output.stat().st_size
    tmp_output.replace(output)
    return output, original_size, converted_size


def replacement_pairs(conversions: dict[Path, Path]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for old_path, new_path in conversions.items():
        old_project = old_path.relative_to(PROJECT_ROOT).as_posix()
        new_project = new_path.relative_to(PROJECT_ROOT).as_posix()
        pairs.append((old_project, new_project))
        if old_path.is_relative_to(SITE_ROOT):
            old_site = old_path.relative_to(SITE_ROOT).as_posix()
            new_site = new_path.relative_to(SITE_ROOT).as_posix()
            pairs.append((old_site, new_site))
        if old_path.is_relative_to(ASSETS_ROOT):
            old_public = "/" + old_path.relative_to(SITE_ROOT).as_posix()
            new_public = "/" + new_path.relative_to(SITE_ROOT).as_posix()
            pairs.append((old_public, new_public))
    return sorted(set(pairs), key=lambda pair: len(pair[0]), reverse=True)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.casefold() in TEXT_SKIP_EXTS:
            continue
        files.append(path)
    return files


def rewrite_references(conversions: dict[Path, Path]) -> list[Path]:
    pairs = replacement_pairs(conversions)
    changed: list[Path] = []
    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = text
        for old, new in pairs:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)
    return changed


def remove_originals(conversions: dict[Path, Path]) -> int:
    removed = 0
    for old_path, new_path in conversions.items():
        if old_path != new_path and new_path.exists() and old_path.exists():
            old_path.unlink()
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--keep-originals", action="store_true")
    args = parser.parse_args()

    conversions: dict[Path, Path] = {}
    original_total = 0
    converted_total = 0
    failures: list[str] = []

    for path in iter_raster_assets():
        try:
            output, original_size, converted_size = convert_one(path, args.quality)
        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            failures.append(f"{path.relative_to(PROJECT_ROOT)}: {exc}")
            continue
        conversions[path] = output
        original_total += original_size
        converted_total += converted_size

    changed_files = rewrite_references(conversions)
    removed = 0 if args.keep_originals else remove_originals(conversions)

    print(
        json.dumps(
            {
                "converted": len(conversions),
                "failed": len(failures),
                "removed_originals": removed,
                "rewritten_files": len(changed_files),
                "original_bytes": original_total,
                "webp_bytes": converted_total,
                "saved_bytes": original_total - converted_total,
                "failures": failures[:20],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
