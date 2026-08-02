import importlib.util
import io
import socket
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("social_feed_watchdog", SCRIPTS / "social_feed_watchdog.py")
assert SPEC and SPEC.loader
watchdog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watchdog)


class FakeResponse:
    def __init__(self, body: str):
        self.body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)

    def open(self, request, timeout):
        return FakeResponse(next(self.responses))


class SocialFeedWatchdogThreadsTests(unittest.TestCase):
    def setUp(self):
        watchdog._THREADS_QUERY_METADATA_CACHE = None
        self.source = {
            "id": "threads_example",
            "name": "Example",
            "platform": "threads",
            "type": "rss",
            "username": "example",
            "limit": 5,
            "rsshub_base": "https://rss.observe.tw",
            "route": "/threads/{username}",
        }

    def test_query_metadata_discovers_current_doc_id_and_relay_variables(self):
        html = '<script src="https://static.cdninstagram.com/one.js"></script>'
        script = (
            '__d("BarcelonaProfileThreadsTabRefetchableDirectQuery_threadsRelayOperation",[], '
            '(function(t,n,r,o,a,i){a.exports="27422205010763282"}),null);'
            'name:"__relay_internal__pv__BarcelonaHasCommunitiesrelayprovider"'
        )

        doc_id, variables = watchdog.threads_query_metadata(FakeOpener([script]), html)

        self.assertEqual(doc_id, "27422205010763282")
        self.assertIn("__relay_internal__pv__BarcelonaHasCommunitiesrelayprovider", variables)

    def test_normalize_threads_graphql_posts_keeps_authored_posts_and_media(self):
        payload = {
            "data": {
                "mediaData": {
                    "edges": [
                        {
                            "node": {
                                "thread_items": [
                                    {
                                        "post": {
                                            "pk": "123",
                                            "code": "ABC123",
                                            "taken_at": 1_700_000_000,
                                            "caption": {"text": "口琴演出公告"},
                                            "user": {"username": "example", "profile_pic_url": "https://img/avatar.jpg"},
                                            "image_versions2": {"candidates": [{"url": "https://img/post.jpg"}]},
                                            "video_versions": [{"url": "https://video/post.mp4"}],
                                        }
                                    },
                                    {
                                        "post": {
                                            "pk": "reply",
                                            "code": "REPLY",
                                            "caption": {"text": "other user reply"},
                                            "user": {"username": "someone_else"},
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                }
            }
        }

        posts = watchdog.normalize_threads_graphql_posts(
            self.source,
            payload,
            source_feed_url="https://www.threads.com/@example",
        )

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["post_id"], "123")
        self.assertEqual(posts[0]["url"], "https://www.threads.com/@example/post/ABC123")
        self.assertEqual(posts[0]["images"], ["https://img/post.jpg"])
        self.assertEqual(posts[0]["videos"], ["https://video/post.mp4"])
        self.assertEqual(posts[0]["text"], "口琴演出公告")

    def test_rsshub_503_uses_threads_graphql_fallback(self):
        def rsshub_error(url, code):
            return urllib.error.HTTPError(
                url,
                code,
                "Service Unavailable",
                {},
                io.BytesIO(b"Error Message:<br/><code>Error: Failed to fetch thread data</code>"),
            )

        with (
            mock.patch.object(
                watchdog.urllib.request,
                "urlopen",
                side_effect=[
                    rsshub_error("https://rss.observe.tw/threads/example", 503),
                    rsshub_error("http://127.0.0.1:1200/threads/example", 503),
                ],
            ),
            mock.patch.object(watchdog, "fetch_threads_graphql", return_value=[]) as fallback,
        ):
            posts = watchdog.fetch_rss(self.source)

        self.assertEqual(posts, [])
        fallback.assert_called_once_with(self.source)

    def test_rsshub_socket_timeout_uses_threads_graphql_fallback(self):
        with (
            mock.patch.object(
                watchdog.urllib.request,
                "urlopen",
                side_effect=[socket.timeout("public timeout"), socket.timeout("local timeout")],
            ),
            mock.patch.object(watchdog, "fetch_threads_graphql", return_value=[]) as fallback,
        ):
            posts = watchdog.fetch_rss(self.source)

        self.assertEqual(posts, [])
        fallback.assert_called_once_with(self.source)


class SocialFeedWatchdogInstagramTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "ig_example",
            "name": "Example Instagram",
            "platform": "instagram",
            "type": "rsshub_instagram_profile",
            "username": "example",
            "source_profile_url": "https://www.instagram.com/example/",
        }

    def test_public_post_html_fallback_normalizes_metadata(self):
        body = """
        <meta property="og:url" content="https://www.instagram.com/p/ABC123/">
        <meta property="og:description" content="12 likes, 2 comments - example on July 31, 2026: &quot;口琴演出公告&quot;">
        <meta property="og:image" content="https://cdn.example/post.jpg">
        """
        with mock.patch.object(watchdog.urllib.request, "urlopen", return_value=FakeResponse(body)):
            post = watchdog.fetch_instagram_public_post(
                self.source,
                "https://www.instagram.com/p/ABC123/",
            )

        self.assertIsNotNone(post)
        assert post is not None
        self.assertEqual(post["post_id"], "ABC123")
        self.assertEqual(post["posted_at"], "2026-07-31T00:00:00+00:00")
        self.assertEqual(post["text"], "口琴演出公告")
        self.assertEqual(post["images"], ["https://cdn.example/post.jpg"])


if __name__ == "__main__":
    unittest.main()
