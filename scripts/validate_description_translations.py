#!/usr/bin/env python3
"""Check every current source biography against the validated public catalog.

Offline, read-only and safe to run after an import. A stale or missing translation
is an actionable failure, rather than silently counting an original as translated.
"""
from __future__ import annotations

import json

from global_catalog import build_catalog

LOCALES = ('zh-Hant', 'en', 'ja', 'ko')


def check_descriptions(catalog: dict) -> dict:
    issues = []
    sources = catalog.get('sources', [])
    complete = 0
    for source in sources:
        missing = []
        summaries = source.get('summaries', {})
        tags = source.get('tagsLocalized', {})
        for language in LOCALES:
            summary = summaries.get(language)
            if source.get('summary') and not (isinstance(summary, str) and summary.strip()):
                missing.append('summary:' + language)
            translated_tags = tags.get(language)
            if source.get('tags') and not (isinstance(translated_tags, list)
                    and len(translated_tags) == len(source['tags'])
                    and all(isinstance(tag, str) and tag.strip() for tag in translated_tags)):
                missing.append('tags:' + language)
        if missing:
            issues.append({'id': source['id'], 'url': source.get('url'), 'missing': missing})
        else:
            complete += 1
    events = catalog.get('events', [])
    complete_events = 0
    for event in events:
        missing = ['description:' + language for language in LOCALES
                   if event.get('description') and not str(event.get('descriptions', {}).get(language) or '').strip()]
        if missing:
            issues.append({'id': event['id'], 'url': event.get('url'), 'missing': missing})
        else:
            complete_events += 1
    return {'sources': len(sources), 'complete': complete, 'events': len(events),
            'completeEvents': complete_events, 'locales': list(LOCALES), 'issues': issues}


def main() -> int:
    report = check_descriptions(build_catalog())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report['issues']))


if __name__ == '__main__':
    raise SystemExit(main())
