import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_public_outputs  # noqa: E402


class JavaScriptValidationTests(unittest.TestCase):
    @mock.patch.object(validate_public_outputs.shutil, "which", return_value="/node")
    @mock.patch.object(validate_public_outputs.subprocess, "run")
    def test_node_checks_a_copy_outside_the_site_directory(self, run_mock, which_mock):
        run_mock.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as directory:
            site_data = Path(directory) / "site" / "data"
            site_data.mkdir(parents=True)
            original = site_data / "feed-data.js"
            original.write_text("const value = 1;\n", encoding="utf-8")
            with mock.patch.object(validate_public_outputs, "SITE_DATA_DIR", site_data):
                errors = []
                validate_public_outputs.validate_js_files(errors)

        self.assertEqual(errors, [])
        checked_path = Path(run_mock.call_args.args[0][2])
        self.assertNotEqual(checked_path, original)
        self.assertEqual(checked_path.name, original.name)


if __name__ == "__main__":
    unittest.main()
