import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("build_social_sources", SCRIPTS / "build_social_sources.py")
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
import build_public_data


class BuildSocialSourcesWebpageTests(unittest.TestCase):
    def test_every_current_public_entry_has_update_source(self):
        entries = build_public_data.build_entries()

        self.assertGreaterEqual(len(entries), 318)
        self.assertEqual(
            [entry["name"] for entry in entries if not entry.get("monitorSources")],
            [],
        )

    def test_entry_without_social_account_gets_scheduled_webpage_watcher(self):
        source = builder.parse_webpage_source(
            {
                "public_id": "249",
                "name": "上海豫園口琴樂團",
                "website_url": "https://www.harmonica.org.cn/news-show.asp?nlt=103&none=17",
            }
        )

        self.assertEqual(source["id"], "web_249")
        self.assertEqual(source["type"], "webpage_watch")
        self.assertEqual(source["platform"], "website")
        self.assertEqual(source["interval_hours"], 12)
        self.assertTrue(source["include_without_keywords"])

    def test_shared_program_page_keeps_entry_specific_watcher_keys(self):
        first = builder.parse_webpage_source(
            {"public_id": "265", "name": "林筱茹", "website_url": "https://example.com/program"}
        )
        second = builder.parse_webpage_source(
            {"public_id": "266", "name": "蔡景玫", "website_url": "https://example.com/program"}
        )

        self.assertNotEqual(builder.source_key(first), builder.source_key(second))

    def test_webpage_watcher_preserves_identity_bearing_query(self):
        source = builder.parse_webpage_source(
            {
                "public_id": "112",
                "name": "Kim Changsik",
                "website_url": "https://weissenbergwind.com/artists_show.php?item=4&id=15#profile",
            }
        )

        self.assertEqual(
            source["url"],
            "https://weissenbergwind.com/artists_show.php?item=4&id=15",
        )

    def test_webpage_watcher_preserves_www_hostname(self):
        source = builder.parse_webpage_source(
            {"public_id": "210", "name": "SPCC", "website_url": "https://www.spcc.edu.hk/news"}
        )

        self.assertEqual(source["url"], "https://www.spcc.edu.hk/news")

    def test_registry_update_url_override_replaces_unreachable_profile_url(self):
        source = builder.parse_webpage_source(
            {
                "public_id": "216",
                "name": "武漢理工大學學生星一口琴協會",
                "website_url": "https://youth.whut.edu.cn/stfc/legacy.shtml",
            }
        )

        self.assertEqual(source["url"], "http://youth.whut.edu.cn/")

    def test_invalid_webpage_url_is_not_accepted(self):
        self.assertIsNone(
            builder.parse_webpage_source(
                {"public_id": "1", "name": "Unsafe", "website_url": "file:///tmp/private"}
            )
        )

    def test_instagram_story_source_uses_instaloader(self):
        source = builder.parse_instagram_story_source(
            {"public_id": "54", "name": "CY Leo", "ig_url": "https://www.instagram.com/cy_leo/"}
        )

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual(source["type"], "rsshub_instagram_story")
        self.assertEqual(source["provider"], "instaloader")
        self.assertEqual(source["story_provider"], "instaloader")
        self.assertNotIn("route", source)
        self.assertNotIn("rsshub_base", source)

    def test_instagram_profile_source_uses_instaloader(self):
        source = builder.parse_instagram_source(
            {"public_id": "54", "name": "CY Leo", "ig_url": "https://www.instagram.com/cy_leo/"}
        )

        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual(source["type"], "rsshub_instagram_profile")
        self.assertEqual(source["provider"], "instaloader")
        self.assertNotIn("route", source)
        self.assertNotIn("rsshub_base", source)


if __name__ == "__main__":
    unittest.main()
