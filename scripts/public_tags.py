"""Canonical public feed tags for harmonica.observe.tw updates."""

from __future__ import annotations

import re
from typing import Any, Iterable


TAG_VALUE_SPLIT_RE = re.compile(r"\s*(?:[,，、/／+&]|\band\b|\s+)\s*", re.IGNORECASE)
LEGACY_TAI = "\u53f0"
TAIWAN_ORTHOGRAPHY_REPLACEMENTS = (
    (f"{LEGACY_TAI}灣", "臺灣"),
    (f"{LEGACY_TAI}北", "臺北"),
    (f"{LEGACY_TAI}中", "臺中"),
    (f"{LEGACY_TAI}南", "臺南"),
)

PUBLIC_TAGS = (
    "口琴",
    "公開更新",
    "比賽",
    "交流",
    "成發",
    "招生",
    "限時動態",
    "音樂會",
    "報名",
    "寒訓",
    "補助",
    "演出",
    "甄選",
    "影片",
    "課程",
    "學生社團",
)
PUBLIC_TAG_SET = set(PUBLIC_TAGS)

TAG_ALIASES = {
    "harmonica": "口琴",
    "harp": "口琴",
    "成果發表": "成發",
    "成果展演": "成發",
    "發表會": "成發",
    "學生音樂比賽": "比賽",
    "全國學生音樂比賽": "比賽",
    "競賽": "比賽",
    "指定曲": "比賽",
    "獎助": "補助",
    "徵件": "補助",
    "徵選": "甄選",
    "甄試": "甄選",
    "社博": "招生",
    "迎新": "招生",
    "暑訓": "課程",
    "工作坊": "課程",
    "講座": "課程",
    "校慶": "演出",
    "實體活動": "演出",
    "活動": "演出",
    "event": "演出",
    "concert": "音樂會",
    "competition": "比賽",
    "grant": "補助",
    "funding": "補助",
    "lesson": "課程",
    "course": "課程",
    "workshop": "課程",
    "video": "影片",
    "新片": "影片",
    "首播": "影片",
    "上架": "影片",
    "發布": "影片",
    "發佈": "影片",
    "直播": "影片",
    "截止": "報名",
    "學校社團": "學生社團",
    "口琴社團": "學生社團",
    "student club": "學生社團",
    "instagram story": "限時動態",
    "story": "限時動態",
}
TAG_ALIAS_BY_KEY = {key.casefold(): value for key, value in TAG_ALIASES.items()}
TAG_ORDER = {tag: index for index, tag in enumerate(PUBLIC_TAGS)}


def normalize_taiwan_orthography(value: Any) -> str:
    text = str(value or "").strip()
    for source, target in TAIWAN_ORTHOGRAPHY_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def normalize_tag_value(value: Any) -> str:
    tag = normalize_taiwan_orthography(value)
    if not tag:
        return ""
    canonical = TAG_ALIAS_BY_KEY.get(tag.casefold(), tag)
    return canonical if canonical in PUBLIC_TAG_SET else ""


def raw_tag_values(value: Any) -> list[Any]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        return list(value)
    return []


def normalize_tag_values(value: Any, *, limit: int = 8) -> list[str]:
    tags: list[str] = []
    for raw in raw_tag_values(value):
        text = normalize_taiwan_orthography(raw)
        if not text:
            continue
        for tag in TAG_VALUE_SPLIT_RE.split(text):
            normalized = normalize_tag_value(tag)
            if normalized and normalized not in tags:
                tags.append(normalized)
            if len(tags) >= limit:
                return tags
    return tags


def sort_public_tags(values: Iterable[Any]) -> list[str]:
    tags: list[str] = []
    for value in values:
        for tag in normalize_tag_values(value, limit=len(PUBLIC_TAGS)):
            if tag not in tags:
                tags.append(tag)
    return sorted(tags, key=lambda tag: (TAG_ORDER.get(tag, len(TAG_ORDER)), tag))
