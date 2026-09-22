import json
from datetime import datetime, timezone
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import global_catalog as catalog


class CatalogTests(unittest.TestCase):
    def test_geography_never_defaults_unknown_to_taiwan(self):
        self.assertEqual(catalog.country_code('韓國'), 'KR')
        self.assertEqual(catalog.country_code('jp'), 'JP')
        self.assertEqual(catalog.country_code(''), 'UNKNOWN')
        self.assertEqual(catalog.country_code('unverified'), 'UNKNOWN')

    def test_website_observation_is_not_a_publication_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [{'key': 'web-old', 'platform': 'website', 'media_type': 'webpage_update',
                     'posted_at': '2026-09-22T14:00:00Z', 'seen_at': '2026-09-22T14:01:00Z',
                     'text': 'Original archived page text', 'link': 'https://example.org/2018/'}]
            (path / 'latest.json').write_text(json.dumps({'updates': rows}))
            post = catalog.build_catalog(path)['posts'][0]
            self.assertIsNone(post['publishedAt'])
            self.assertEqual(post['contentKind'], 'website_snapshot')
            self.assertEqual(post['observedAt'], rows[0]['seen_at'])
            self.assertEqual(post['text'], rows[0]['text'])

    def test_unsafe_links_are_not_exposed(self):
        for url in ['javascript:alert(1)', '//host/path', '/\\host', 'https://user:password@example.org', 'https://example.org\n/path']:
            self.assertEqual(catalog.public_url(url), '')
        self.assertEqual(catalog.public_url('/source/42-test/'), '/source/42-test/')

    def test_empty_install_and_malformed_snapshot_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'sources.json').write_text('{')
            result = catalog.build_catalog(path)
            self.assertEqual(result['stats']['sources'], 0)
            self.assertIsNone(result['generatedAt'])
            self.assertFalse(result['dataAvailability']['sources.json'])

    def test_sources_posts_dates_and_public_status_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            def put(name, value):
                (path / name).write_text(json.dumps(value))
            put('sources.json', {'entries': [{'id': 'watchlist-9', 'publicId': '9', 'slug': '9-seoul', 'name': '서울', 'country': '韓國', 'monitorSources': [{'id': 'ig_seoul'}]}]})
            put('latest.json', {'generatedAt': '2026-09-23T00:00:00Z', 'updates': [{'source_id': 'ig_seoul', 'link': 'https://example.org/post', 'text': 'Original 한국어', 'posted_at': '2026-09-20T12:00:00+09:00'}]})
            event = {'id': 'concert', 'title': '공연', 'start': '2026-10-01T19:00:00+09:00', 'timezone': 'Asia/Seoul', 'calendarReview': {'country': '韓國'}, 'evidenceUrl': 'https://example.org/event'}
            put('overseas-calendar-events.json', {'events': [event]})
            put('online-calendar-events.json', {'events': [dict(event, id='stream', calendarType='online')]})
            put('status.json', {'runtime': {'secret': 'NEVER-EXPOSE'}, 'metrics': {'watchSources': 1, 'secret': 'NEVER-EXPOSE'}, 'watchSources': {'platformRows': [{'platform': 'instagram', 'status': 'paused', 'sources': 1}]}})
            result = catalog.build_catalog(path)
            self.assertEqual(result['posts'][0]['countryCode'], 'KR')
            self.assertEqual(result['posts'][0]['sourceId'], 'watchlist-9')
            self.assertEqual(result['posts'][0]['text'], 'Original 한국어')
            self.assertEqual(result['sources'][0]['url'], '/source/9-seoul/')
            self.assertEqual(result['events'][0]['start'], event['start'])
            self.assertEqual(result['events'][1]['countryCode'], 'ONLINE')
            self.assertNotIn('NEVER-EXPOSE', json.dumps(result))
            self.assertEqual(result['status']['services'][0]['status'], 'paused')

    def test_calendar_embed_metadata_is_allowlisted_and_tracks_snapshot_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            before = catalog.snapshot_version(path)
            rows = [
                {'calendarId': 'public@group.calendar.google.com', 'calendarKey': 'taiwan', 'status': 'ok', 'credentials': 'PRIVATE'},
                {'calendarId': 'bad@example.org', 'calendarKey': 'overseas'},
                {'calendarId': 'public@group.calendar.google.com', 'calendarKey': 'online'},
                {'calendarId': 'another@group.calendar.google.com', 'calendarKey': 'untrusted'},
            ]
            (path / 'public-calendar-sync.json').write_text(json.dumps({'calendars': rows, 'generatedAt': '2026-09-23T00:00:00Z', 'lockFile': 'PRIVATE'}))
            result = catalog.build_catalog(path)
            self.assertEqual(result['calendars'], [{'id': 'public@group.calendar.google.com', 'key': 'taiwan', 'status': 'ok', 'updatedAt': '2026-09-23T00:00:00Z'}])
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertNotEqual(before, catalog.snapshot_version(path))

    def test_synthetic_source_backfills_never_become_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [{'id': 'page', 'media_type': 'source_page'},
                    {'id': 'directory', 'media_type': 'directory_source_page'},
                    {'id': 'raw', 'raw_source': 'public-link-backfill'},
                    {'key': 'fb_test:source_page:digest'},
                    {'post_id': 'source_page:digest'}, {'id': 'real', 'text': 'Actual post'}]
            (path / 'latest.json').write_text(json.dumps({'updates': rows}))
            result = catalog.build_catalog(path)
            self.assertEqual([row['id'] for row in result['posts']], ['real'])
            self.assertEqual(result['stats']['posts'], 1)

    def test_expired_stories_remain_archived_and_only_verified_current_story_is_active(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [{'id': name, 'story': True, 'story_expires_at': expiry, 'link': 'https://example.org/story'}
                    for name, expiry in [('past', '2026-09-22T00:00:00Z'), ('now', '2026-09-23T00:00:00Z'),
                                         ('future', '2026-09-24T00:00:00Z'), ('unknown', None),
                                         ('naive', '2026-09-24T00:00:00')]]
            (path / 'latest.json').write_text(json.dumps({'updates': rows}))
            result = catalog.build_catalog(path, now=datetime(2026, 9, 23, tzinfo=timezone.utc))
            self.assertEqual(len(result['posts']), 5)
            self.assertEqual([row['id'] for row in result['stories']], ['future'])
            by_id = {r['id']: r for r in result['posts']}
            self.assertEqual(by_id['past']['storyState'], 'expired')
            self.assertFalse(by_id['past']['sourceAvailable'])
            self.assertEqual(by_id['unknown']['storyState'], 'unknown')
            self.assertFalse(by_id['naive']['sourceAvailable'])
            self.assertTrue(by_id['future']['sourceAvailable'])

    def test_incomplete_valid_json_does_not_break_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'sources.json').write_text(json.dumps({'entries': [{'id': 'a', 'sourceTags': None, 'monitorSources': None}]}))
            (path / 'latest.json').write_text(json.dumps({'updates': None}))
            (path / 'status.json').write_text(json.dumps({'watchSources': [], 'metrics': []}))
            result = catalog.build_catalog(path)
            self.assertEqual(result['sources'][0]['tags'], [])
            self.assertEqual(result['posts'], [])
            self.assertEqual(result['status']['overall'], 'unknown')

    def test_timezone_offsets_sort_by_actual_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [{'id': 'older', 'posted_at': '2026-09-23T01:00:00+09:00'},
                    {'id': 'newer', 'posted_at': '2026-09-22T20:00:00Z'}]
            (path / 'latest.json').write_text(json.dumps({'updates': rows}))
            self.assertEqual([row['id'] for row in catalog.build_catalog(path)['posts']], ['newer', 'older'])

    def test_stale_status_is_last_known_not_current_health(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'status.json').write_text(json.dumps({'generatedAt': '2026-09-20T00:00:00Z', 'overall': {'status': 'ok'}}))
            status = catalog.build_catalog(path, now=datetime(2026, 9, 23, tzinfo=timezone.utc))['status']
            self.assertEqual(status['overall'], 'unknown')
            self.assertEqual(status['lastKnownOverall'], 'ok')
            self.assertEqual(status['snapshotState'], 'stale')
            self.assertEqual(status['provider'], 'mixed')
            self.assertFalse(status['schedulerVerified'])


if __name__ == '__main__':
    unittest.main()
