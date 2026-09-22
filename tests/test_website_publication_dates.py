"""A page observation is not evidence of its publication date."""
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_rss_feeds as rss

class WebsitePublicationDatesTest(unittest.TestCase):
    def test_legacy_webpage_timestamp_is_not_exported_as_publication(self):
        with patch.object(rss, 'OFFLINE', True), patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            row = rss.public_update_row({'key': 'fixture', 'platform': 'website', 'media_type': 'webpage_update',
                'text': 'Original page text', 'url': 'https://example.org/2018/',
                'posted_at': '2026-09-22T00:00:00Z', 'seen_at': '2026-09-22T00:01:00Z'})
        self.assertEqual(row['posted_at'], '')
        channel = ET.Element('channel')
        rss.add_update_item(channel, row)
        self.assertIsNone(channel.find('item/pubDate'))
        self.assertIn('非發布日期', channel.findtext('item/description'))
        self.assertIn('Original page text', channel.findtext('item/description'))
