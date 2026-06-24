#!/usr/bin/env python3
"""Verify every enabled public source and directory entry has at least one row."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import build_public_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOCIAL_SOURCES = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
INBOX = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"
CANDIDATES = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def row_has_content(row: dict[str, Any]) -> bool:
    return bool(row.get("source_id") and (row.get("url") or row.get("text")))


def source_rows_by_id(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row_has_content(row):
            counts[str(row["source_id"])] += 1
    return counts


def row_match_keys(row: dict[str, Any]) -> set[str]:
    if not row_has_content(row):
        return set()
    return build_public_data.candidate_match_keys(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_config = read_json(SOCIAL_SOURCES, {"sources": []})
    sources = [
        source
        for source in source_config.get("sources", [])
        if source.get("enabled", True) and source.get("type") != "jsonl"
    ]
    inbox_rows = read_jsonl(INBOX)
    candidate_rows = read_jsonl(CANDIDATES)
    rows = inbox_rows + candidate_rows
    rows_by_source = source_rows_by_id(rows)

    missing_sources = [
        source
        for source in sources
        if rows_by_source[str(source.get("id") or "")] == 0
    ]

    row_keys = [row_match_keys(row) for row in rows]
    entries = build_public_data.build_entries()
    missing_entries: list[dict[str, Any]] = []
    for entry in entries:
        entry_keys = build_public_data.entry_match_keys(entry)
        if not any(entry_keys & keys for keys in row_keys):
            missing_entries.append(entry)

    summary = {
        "ok": not missing_sources and not missing_entries,
        "inboxRows": len(inbox_rows),
        "candidateRows": len(candidate_rows),
        "publicLinkBackfillRows": sum(
            1 for row in candidate_rows if row.get("raw_source") == "public-link-backfill"
        ),
        "socialSources": len(sources),
        "socialSourcesCovered": len(sources) - len(missing_sources),
        "socialSourcesMissing": len(missing_sources),
        "missingSourcesByType": dict(Counter(str(source.get("type") or "") for source in missing_sources)),
        "directoryEntries": len(entries),
        "directoryEntriesCovered": len(entries) - len(missing_entries),
        "directoryEntriesMissing": len(missing_entries),
        "missingSources": [
            {
                "id": source.get("id"),
                "type": source.get("type"),
                "name": source.get("name"),
                "url": source.get("url") or source.get("page") or source.get("username"),
            }
            for source in missing_sources
        ],
        "missingEntries": [
            {
                "id": entry.get("id"),
                "name": entry.get("name"),
                "links": entry.get("links"),
            }
            for entry in missing_entries
        ],
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif summary["ok"]:
        print(
            "OK: "
            f"{summary['socialSourcesCovered']}/{summary['socialSources']} social sources and "
            f"{summary['directoryEntriesCovered']}/{summary['directoryEntries']} directory entries covered."
        )
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
