import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLIST_PATH = ROOT / "deploy" / "tw.observe.harmonica.calendar-maintenance.plist"


class CalendarMaintenancePlistTests(unittest.TestCase):
    def test_uses_stable_python_runtime_through_shell(self):
        with PLIST_PATH.open("rb") as handle:
            plist = plistlib.load(handle)

        arguments = plist["ProgramArguments"]
        self.assertEqual(arguments[:2], ["/bin/zsh", "-lc"])
        self.assertIn("harmonica-intake-venv/bin/python", arguments[2])
        self.assertNotIn("google-workspace-venv", arguments[2])
        self.assertIn("--history-days 365 --required", arguments[2])
        self.assertEqual(
            plist["EnvironmentVariables"]["HARMONICA_GOOGLE_CALENDAR_CLIENT"],
            "rest",
        )


if __name__ == "__main__":
    unittest.main()
