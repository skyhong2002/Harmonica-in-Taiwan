import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_description_translations import check_descriptions, LOCALES


class DescriptionCoverageTests(unittest.TestCase):
    def test_missing_translation_is_not_hidden_by_original_fallback(self):
        source = {'id': 'a', 'url': '/source/a/', 'summary': '原文', 'tags': ['演奏者'],
                  'summaries': {'zh-Hant': '原文'}, 'tagsLocalized': {'zh-Hant': ['演奏者']}}
        result = check_descriptions({'sources': [source]})
        self.assertEqual(result['complete'], 0)
        self.assertEqual(result['issues'][0]['missing'], ['summary:en', 'tags:en', 'summary:ja', 'tags:ja', 'summary:ko', 'tags:ko'])
        source.update(summaries={locale: 'Translation' for locale in LOCALES},
                      tagsLocalized={locale: ['Tag'] for locale in LOCALES})
        self.assertEqual(check_descriptions({'sources': [source]})['complete'], 1)
        source['tagsLocalized']['ko'] = []
        self.assertEqual(check_descriptions({'sources': [source]})['issues'][0]['missing'], ['tags:ko'])

    def test_empty_descriptions_do_not_require_invented_content(self):
        self.assertEqual(check_descriptions({'sources': [{'id': 'empty', 'summary': '', 'tags': []}]})['complete'], 1)

    def test_event_descriptions_are_checked_independently(self):
        event = {'id': 'event', 'description': 'Original', 'descriptions': {locale: 'Translated' for locale in LOCALES}}
        self.assertEqual(check_descriptions({'events': [event]})['completeEvents'], 1)
        del event['descriptions']['en']
        self.assertEqual(check_descriptions({'events': [event]})['issues'][0]['missing'], ['description:en'])


if __name__ == '__main__':
    unittest.main()
