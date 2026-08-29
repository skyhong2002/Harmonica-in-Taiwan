import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import publish_github_pages  # noqa: E402


class PushWithRetryTests(unittest.TestCase):
    @staticmethod
    def result(returncode: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["git", "push"], returncode)

    @mock.patch.object(publish_github_pages.time, "sleep")
    @mock.patch.object(publish_github_pages, "git")
    def test_retries_transient_failures_with_backoff(self, git_mock, sleep_mock):
        git_mock.side_effect = [self.result(1), self.result(1), self.result(0)]

        publish_github_pages.push_with_retry(
            "origin", "gh-pages", cwd=ROOT, attempts=3, retry_seconds=2
        )

        self.assertEqual(git_mock.call_count, 3)
        sleep_mock.assert_has_calls([mock.call(2), mock.call(4)])
        git_mock.assert_called_with(
            ["push", "-u", "origin", "gh-pages"], cwd=ROOT, check=False
        )

    @mock.patch.object(publish_github_pages.time, "sleep")
    @mock.patch.object(publish_github_pages, "git")
    def test_raises_after_final_attempt(self, git_mock, sleep_mock):
        git_mock.return_value = self.result(128)

        with self.assertRaises(subprocess.CalledProcessError):
            publish_github_pages.push_with_retry(
                "origin", "gh-pages", cwd=ROOT, attempts=3, retry_seconds=1
            )

        self.assertEqual(git_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_count, 2)

    @mock.patch.object(publish_github_pages.time, "sleep")
    @mock.patch.object(publish_github_pages, "git")
    def test_remote_branch_lookup_retries_transport_failure(self, git_mock, sleep_mock):
        git_mock.side_effect = [self.result(128), self.result(0)]

        result = publish_github_pages.git_remote_with_retry(
            ["ls-remote"],
            cwd=ROOT,
            operation="branch lookup",
            success_returncodes=frozenset({0, 2}),
            attempts=3,
            retry_seconds=1,
        )

        self.assertEqual(result.returncode, 0)
        sleep_mock.assert_called_once_with(1)

    @mock.patch.object(publish_github_pages.time, "sleep")
    @mock.patch.object(publish_github_pages, "git")
    def test_missing_remote_branch_is_not_retried(self, git_mock, sleep_mock):
        git_mock.return_value = self.result(2)

        result = publish_github_pages.git_remote_with_retry(
            ["ls-remote"],
            cwd=ROOT,
            operation="branch lookup",
            success_returncodes=frozenset({0, 2}),
        )

        self.assertEqual(result.returncode, 2)
        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
