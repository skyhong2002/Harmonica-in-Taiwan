"""Canonical /source/ page slugs shared by the build and validation scripts."""

from __future__ import annotations

import re
from typing import Any


# Keep canonical URLs stable when metadata enrichment adds an English name.
SOURCE_SLUG_OVERRIDES = {
    "7": "7",
    "8": "8",
    "11": "11",
    "12": "12",
    "13": "13-donuts",
    "15": "15",
    "16": "16-dr-blue",
    "19": "19-bbg",
    "20": "20-miss-h",
    "21": "21-orion",
    "28": "28",
    "30": "30",
    "31": "31",
    "32": "32",
    "33": "33",
    "35": "35",
    "36": "36",
    "37": "37",
    "38": "38",
    "39": "39",
    "41": "41",
    "44": "44",
    "47": "47",
    "72": "72",
    "73": "73",
    "74": "74-opentix",
    "75": "75",
    "76": "76",
    "77": "77",
    "78": "78",
    "79": "79",
    "80": "80",
    "87": "87",
    "96": "96",
    "97": "97",
    "99": "99",
    "265": "265",
    "266": "266",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def source_public_id(entry: dict[str, Any]) -> str:
    entry_id = _clean(entry.get("id"))
    match = re.match(r"^watchlist-(\d+)$", entry_id)
    if match:
        return match.group(1)
    return entry_id


def make_slug(entry: dict[str, Any]) -> str:
    entry_id = source_public_id(entry)
    if entry_id in SOURCE_SLUG_OVERRIDES:
        return SOURCE_SLUG_OVERRIDES[entry_id]
    text = _clean(entry.get("nameEn")) or _clean(entry.get("name"))
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return f"{entry_id}-{text}" if text else entry_id
