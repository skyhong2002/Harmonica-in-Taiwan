#!/usr/bin/env python3
"""Build bounded, shareable links into the public submission form."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any


PUBLIC_BASE_URL = "https://harmonica.observe.tw"
REPORT_KINDS = {"add-source", "correct", "event", "remove"}
REPORT_FIELD_LIMITS = {
    "name": 240,
    "source": 1500,
    "page": 1500,
    "desired": 2400,
    "event": 1800,
    "extra": 1800,
}


def clean_report_value(value: Any, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value or ""))
    return text.strip()[:limit]


def absolute_public_url(value: Any) -> str:
    text = clean_report_value(value, REPORT_FIELD_LIMITS["page"])
    if text.startswith("/"):
        return f"{PUBLIC_BASE_URL}{text}"
    return text


def report_url(
    kind: str,
    *,
    name: Any = "",
    source: Any = "",
    page: Any = "",
    desired: Any = "",
    event: Any = "",
    extra: Any = "",
) -> str:
    normalized_kind = kind if kind in REPORT_KINDS else "correct"
    values = {
        "kind": normalized_kind,
        "name": name,
        "source": source,
        "page": absolute_public_url(page),
        "desired": desired,
        "event": event,
        "extra": extra,
    }
    query = urllib.parse.urlencode(
        {
            key: clean_report_value(value, REPORT_FIELD_LIMITS.get(key, 120))
            for key, value in values.items()
            if value
        }
    )
    return f"/submit/?{query}" if query else "/submit/"
