import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_pipeline  # noqa: E402


class GoogleWorkspacePythonTests(unittest.TestCase):
    def test_configured_runtime_wins(self):
        with mock.patch.dict(
            os.environ, {"HARMONICA_GOOGLE_WORKSPACE_PYTHON": "/custom/python"}
        ):
            self.assertEqual(run_pipeline.google_workspace_python(), "/custom/python")

    def test_existing_stable_runtime_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "python"
            runtime.touch()
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch.object(run_pipeline, "DEFAULT_GOOGLE_WORKSPACE_PYTHON", runtime),
            ):
                self.assertEqual(run_pipeline.google_workspace_python(), str(runtime))


if __name__ == "__main__":
    unittest.main()
