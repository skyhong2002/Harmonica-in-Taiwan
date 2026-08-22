from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_JS = PROJECT_ROOT / "site" / "assets" / "app.js"


class FeedArchiveSsrTests(unittest.TestCase):
    """Archive pages (/post/page/N/) ship server-rendered feed content for
    crawlers; the client must keep it instead of re-rendering page 1."""

    def setUp(self):
        self.source = APP_JS.read_text(encoding="utf-8")

    def test_archive_pages_are_detected_from_path(self):
        self.assertIn(
            'const feedArchiveStatic = /^\\/post\\/page\\/\\d+\\/?$/.test(window.location.pathname);',
            self.source,
        )

    def test_render_latest_feeds_keeps_static_archive_content(self):
        render = self.source.index("function renderLatestFeeds()")
        guard = self.source.index("if (feedArchiveStatic && !feedArchiveTakenOver) return;", render)
        home_mode = self.source.index('latestFeedGrid.dataset.feedMode === "home"', render)
        self.assertLess(guard, home_mode)

    def test_interacting_with_filters_takes_over_dynamically(self):
        self.assertIn("function bindFeedArchiveTakeover()", self.source)
        init = self.source.index("function init()")
        self.assertIn("bindFeedArchiveTakeover();", self.source[init:])


if __name__ == "__main__":
    unittest.main()
