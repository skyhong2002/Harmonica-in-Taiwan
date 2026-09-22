import html
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_shell

TEMPLATE = '<!doctype html><html lang="en"><head><title>Harmonica Observatory</title><meta name="description" content="old"><link rel="canonical" href="https://old.example/"></head><body><!--SERVER_CONTENT--></body></html>'
ORIGIN = 'https://harmonica.observe.tw'


class RenderShellTests(unittest.TestCase):
    def catalog(self, name='Tokyo ensemble'):
        return {'sources': [{'id': 'watchlist-42', 'name': name, 'url': '/source/tokyo-42/',
                            'summary': 'Original public description & notes', 'country': 'Japan', 'region': 'Tokyo',
                            'links': [{'url': 'https://example.org/ensemble?a=1&b=2', 'label': 'Official website'}]}],
                'posts': [{'sourceId': 'watchlist-42', 'title': 'Concert & workshop', 'url': 'https://example.org/concert'}]}

    def test_four_locales_have_localized_metadata_and_alternate_links(self):
        for locale in render_shell.LOCALES:
            document = render_shell.render_document(TEMPLATE, '/source/', self.catalog(), ORIGIN, locale)
            self.assertIn('<html lang="' + locale + '">', document)
            self.assertIn(html.escape(render_shell.WORDS[locale]['source']), document)
            self.assertEqual(document.count('hreflang='), 4)
            self.assertNotIn('https://old.example/', document)
            self.assertNotIn('content="old"', document)
            self.assertIn('rel="canonical" href="' + ORIGIN + '/source/?lang=' + locale + '"', document)

    def test_brand_is_localized_consistently_in_page_and_open_graph_titles(self):
        brands = {'en': 'Harmonica Observatory', 'zh-Hant': '口琴觀測站',
                  'ja': 'ハーモニカ観測所', 'ko': '하모니카 관측소'}
        for locale, brand in brands.items():
            with self.subTest(locale=locale):
                document = render_shell.render_document(TEMPLATE, '/', self.catalog(), ORIGIN, locale)
                title = render_shell.WORDS[locale]['home'] + ' · ' + brand
                self.assertIn('<title>' + title + '</title>', document)
                self.assertIn('<meta property="og:title" content="' + title + '">', document)
                self.assertIn('<meta property="og:site_name" content="' + brand + '">', document)
                for other in brands.values():
                    if other != brand:
                        self.assertNotIn(other, document)

    def test_known_source_retains_original_content_without_javascript(self):
        document = render_shell.render_document(TEMPLATE, '/source/tokyo-42/', self.catalog(), ORIGIN, 'ja')
        self.assertIn('<h1>Tokyo ensemble</h1>', document)
        self.assertIn('Official website', document)
        self.assertIn('Concert &amp; workshop', document)
        self.assertIn('Japan · Tokyo', document)
        self.assertNotIn('<!--SERVER_CONTENT-->', document)

    def test_source_names_and_descriptions_are_escaped_as_text(self):
        catalog = self.catalog('Duo <North> & "South"')
        catalog['sources'][0]['summary'] = 'Description <em>literal markup</em>'
        document = render_shell.render_document(TEMPLATE, '/source/tokyo-42/', catalog, ORIGIN)
        self.assertIn('Duo &lt;North&gt; &amp; &quot;South&quot;', document)
        self.assertNotIn('<em>literal markup</em>', document)
        self.assertIn('&lt;em&gt;literal markup&lt;/em&gt;', document)

    def test_literal_backslash_in_source_name_does_not_become_regex_replacement(self):
        catalog = self.catalog(r'Ensemble \1')
        document = render_shell.render_document(TEMPLATE, '/source/tokyo-42/', catalog, ORIGIN)
        self.assertIn(r'<h1>Ensemble \1</h1>', document)
        self.assertIn(r'<title>Ensemble \1', document)

    def test_post_source_alias_resolves_the_same_canonical_source(self):
        document = render_shell.render_document(TEMPLATE, '/post/source/tokyo-42/', self.catalog(), ORIGIN, 'ko')
        self.assertIn('<h1>Tokyo ensemble</h1>', document)
        self.assertIn('rel="canonical" href="' + ORIGIN + '/source/tokyo-42/?lang=ko"', document)
        for locale in render_shell.LOCALES:
            self.assertIn('hreflang="' + locale + '" href="' + ORIGIN + '/source/tokyo-42/?lang=' + locale, document)

    def test_unrecognized_locale_falls_back_to_english(self):
        document = render_shell.render_document(TEMPLATE, '/', self.catalog(), ORIGIN, 'fr-CA')
        self.assertIn('<html lang="en">', document)
        self.assertIn('<h1>Home</h1>', document)


if __name__ == '__main__':
    unittest.main()
