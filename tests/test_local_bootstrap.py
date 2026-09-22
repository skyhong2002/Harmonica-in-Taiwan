import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_local
import build_status_page
import generate_rss_feeds


class LocalBootstrapTests(unittest.TestCase):
    def test_fresh_data_install_has_required_shells_and_honest_sync_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_local.seed_missing_artifacts(root)
            for path in ('index.html', 'post/index.html', 'scores/index.html', 'directory/index.html', 'scores/sources/index.html', 'score-sources/index.html'):
                self.assertTrue((root / 'site' / path).is_file())
            score_html = (root / 'site/scores/index.html').read_text()
            self.assertIn('"@type": "Dataset"', score_html)
            self.assertIn('https://harmonica.observe.tw/scores/#dataset', score_html)
            sync = json.loads((root / 'site/api/public-calendar-sync.json').read_text())
            self.assertEqual(sync['status'], 'not_configured')
            self.assertFalse(sync['enabled'])

    def test_bootstrap_uses_new_shell_but_preserves_existing_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'web').mkdir()
            (root / 'web/index.html').write_text('<html><head><title>New</title><link rel="canonical" href="https://old.example/"></head><body>New interface</body></html>')
            (root / 'site/api').mkdir(parents=True)
            (root / 'site/index.html').write_text('existing homepage')
            (root / 'site/api/public-calendar-sync.json').write_text('{"status":"existing"}')
            build_local.seed_missing_artifacts(root)
            self.assertEqual((root / 'site/index.html').read_text(), 'existing homepage')
            self.assertIn('New interface', (root / 'site/post/index.html').read_text())
            self.assertNotIn('old.example', (root / 'site/post/index.html').read_text())
            self.assertEqual(json.loads((root / 'site/api/public-calendar-sync.json').read_text())['status'], 'existing')

    def test_offline_feed_build_uses_cache_without_fetching(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(generate_rss_feeds, 'OFFLINE', True), patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            image_dir = Path(directory)
            url = 'https://example.org/avatar.png'
            digest = hashlib.sha256(url.encode()).hexdigest()[:20]
            self.assertEqual(generate_rss_feeds.cache_remote_image(url, image_dir, '/assets/source-avatars'), '')
            (image_dir / (digest + '.webp')).write_bytes(b'cached')
            self.assertEqual(generate_rss_feeds.cache_remote_image(url, image_dir, '/assets/source-avatars'), '/assets/source-avatars/' + digest + '.webp')
            source = {'id': 'sample', 'type': 'facebook_page_posts', 'url': 'https://example.org/profile', 'name': 'Sample'}
            self.assertEqual(generate_rss_feeds.fetch_source_profile(source)['name'], 'Sample')
            self.assertEqual(generate_rss_feeds.fetch_html_profile(source)['name'], 'Sample')

    def test_offline_status_never_checks_live_services_or_credentials(self):
        blocked = AssertionError('live check forbidden')
        with patch.object(build_status_page, 'launch_agent_status', side_effect=blocked), patch.object(build_status_page, 'probe_url', side_effect=blocked), patch.object(build_status_page, 'apify_check', side_effect=blocked), patch('apify_pool.crawl_schedule_snapshot', side_effect=blocked):
            status = build_status_page.build_status(offline=True)
        self.assertEqual(status['probeMode'], 'offline')
        self.assertFalse(status['crawlFrequency']['available'])
        self.assertEqual(next(c['status'] for c in status['components'] if c['id'] == 'facebook-apify'), 'unknown')

    def test_build_steps_explicitly_disable_network_and_inference(self):
        self.assertIn(['generate_rss_feeds.py', '--offline'], build_local.STEPS)
        self.assertIn(['build_status_page.py', '--offline'], build_local.STEPS)
        self.assertIn(['build_public_calendar_events.py', '--no-llm'], build_local.STEPS)
        self.assertIn(['backfill_public_source_pages.py', '--skip-fetch'], build_local.STEPS)


if __name__ == '__main__':
    unittest.main()
