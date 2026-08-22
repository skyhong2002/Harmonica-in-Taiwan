import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_public_data
import generate_seo_pages
import validate_legacy_redirects
from source_slugs import SOURCE_SLUG_OVERRIDES, make_slug

APP_JS = PROJECT_ROOT / "site" / "assets" / "app.js"


class SourceSlugTests(unittest.TestCase):
    def test_override_keeps_canonical_url_stable_after_english_name(self):
        entry = {"id": "watchlist-31", "name": "張晁滕", "nameEn": "Chao-Teng Chang"}
        self.assertEqual(make_slug(entry), "31")

    def test_non_override_slug_uses_english_name(self):
        entry = {"id": "watchlist-310", "name": "林金鳳", "nameEn": "Lin Jinfeng"}
        self.assertEqual(make_slug(entry), "310-lin-jinfeng")

    def test_chinese_only_name_falls_back_to_public_id(self):
        entry = {"id": "watchlist-999", "name": "口琴社", "nameEn": ""}
        self.assertEqual(make_slug(entry), "999")

    def test_generators_share_one_slug_implementation(self):
        self.assertIs(generate_seo_pages.make_slug, make_slug)
        self.assertIs(validate_legacy_redirects.make_slug, make_slug)
        self.assertIs(build_public_data.make_slug, make_slug)
        self.assertIs(generate_seo_pages.SOURCE_SLUG_OVERRIDES, SOURCE_SLUG_OVERRIDES)

    def test_app_js_prefers_embedded_canonical_slug(self):
        source = APP_JS.read_text(encoding="utf-8")
        fn = source.index("function makeSlug(entry)")
        slug_check = source.index("const canonicalSlug = (entry.slug || \"\").trim();", fn)
        computed = source.index("const rawEntryId", fn)
        self.assertLess(slug_check, computed)


if __name__ == "__main__":
    unittest.main()
