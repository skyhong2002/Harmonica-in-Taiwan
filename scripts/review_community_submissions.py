#!/usr/bin/env python3
"""Review the local public-link inbox without exposing contributor identities.

Export a reviewed row into the existing verified intake queue; this command does
not fetch URLs, run AI, publish content, create issues or modify public CSVs.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json

import community
import submission_intake as intake


STATUSES = ('pending', 'reviewing', 'accepted', 'rejected')


def export_submission(identifier: str, name: str, kind: str, *, intake_path=None) -> dict:
    name = str(name).strip()
    if not name or len(name) > 500:
        raise ValueError('A verified public name of 1 to 500 characters is required')
    if kind not in ('source', 'event', 'correction'):
        raise ValueError('Unsupported submission kind')
    with community.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM submissions WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise ValueError('Submission not found')
        if row['status'] not in ('pending', 'reviewing'):
            raise ValueError('Only pending or reviewing submissions can be exported')
        answers = {
            intake.REPORT_TYPE: {'source': '新增來源或社團', 'event': '新增活動', 'correction': '資料修正'}[kind],
            intake.TARGET_NAME: name.strip(), intake.PRIMARY_URL: row['url'],
            intake.DESIRED_RESULT: row['note'] + '\nCountry code: ' + row['country'],
            intake.EVENT_DETAILS: row['note'] if kind == 'event' else '',
            intake.PUBLIC_CONFIRMATION: 'Operator reviewed this public link for intake',
        }
        store = intake.IntakeStore(intake_path or intake.DEFAULT_STATE_DB)
        try:
            inserted = store.ingest('local-' + row['id'], dt.datetime.fromtimestamp(row['created'], dt.timezone.utc).isoformat(), answers)
        finally:
            store.close()
        conn.execute("UPDATE submissions SET status='reviewing' WHERE id=?", (identifier,))
    return {'id': identifier, 'intakeId': 'local-' + identifier, 'inserted': inserted, 'status': 'reviewing'}


def list_submissions(status: str = 'pending') -> list[dict]:
    if status not in STATUSES:
        raise ValueError('Unsupported status')
    with community.connect() as conn:
        return [dict(row) for row in conn.execute(
            'SELECT id,url,note,country,status,created FROM submissions WHERE status=? ORDER BY created', (status,))]


def mark_submission(identifier: str, status: str) -> dict:
    if status not in STATUSES:
        raise ValueError('Unsupported status')
    with community.connect() as conn:
        cursor = conn.execute('UPDATE submissions SET status=? WHERE id=?', (status, identifier))
        if not cursor.rowcount:
            raise ValueError('Submission not found')
    return {'id': identifier, 'status': status}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    listing = commands.add_parser('list')
    listing.add_argument('--status', choices=['pending', 'reviewing', 'accepted', 'rejected'], default='pending')
    export = commands.add_parser('export')
    export.add_argument('id')
    export.add_argument('--name', required=True)
    export.add_argument('--kind', choices=['source', 'event', 'correction'], default='source')
    mark = commands.add_parser('mark')
    mark.add_argument('id')
    mark.add_argument('status', choices=['pending', 'reviewing', 'accepted', 'rejected'])
    args = parser.parse_args()
    try:
        if args.command == 'export':
            result = export_submission(args.id, args.name, args.kind)
        elif args.command == 'list':
            result = list_submissions(args.status)
        else:
            result = mark_submission(args.id, args.status)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
