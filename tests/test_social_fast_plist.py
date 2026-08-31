import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLIST_PATH = ROOT / "deploy" / "tw.observe.harmonica.social-fast.plist"


class SocialFastPlistTests(unittest.TestCase):
    def test_social_refresh_publishes_the_validated_snapshot(self):
        with PLIST_PATH.open("rb") as handle:
            plist = plistlib.load(handle)

        arguments = plist["ProgramArguments"]
        self.assertEqual(arguments[:2], ["/bin/zsh", "-lc"])
        self.assertIn("scripts/run_pipeline.py", arguments[2])
        self.assertIn("--publish-pages", arguments[2])
        self.assertEqual(plist["StartInterval"], 1800)


if __name__ == "__main__":
    unittest.main()
