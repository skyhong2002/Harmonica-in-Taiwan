from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_public_data", ROOT / "scripts" / "build_public_data.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceProfileMatchingTests(unittest.TestCase):
    def test_profile_match_keys_include_title_and_explicit_name_aliases(self) -> None:
        keys = MODULE.profile_match_keys(
            {
                "name": "高雄市兒童口琴樂團 / 高雄市口琴協會",
                "title": "高雄市兒童口琴樂團",
                "aliases": ["高雄兒童口琴"],
                "id": "web_kaohsiung_childrens_harmonica",
            }
        )

        self.assertIn(MODULE.normalize_key("高雄市兒童口琴樂團"), keys)
        self.assertIn(MODULE.normalize_key("高雄市口琴協會"), keys)
        self.assertIn(MODULE.normalize_key("高雄兒童口琴"), keys)

    def test_profile_match_keys_include_durable_profile_id_aliases(self) -> None:
        keys = MODULE.profile_match_keys(
            {
                "id": "ig_hkharmonica",
                "name": "香港口琴協會 Hong Kong Harmonica Association",
            }
        )

        self.assertIn(MODULE.normalize_key("Breathe with the Harmonica"), keys)

    def test_aphf_profile_covers_related_people_and_ensemble(self) -> None:
        keys = MODULE.profile_match_keys(
            {
                "id": "manual_aphf_2026",
                "name": "亞太口琴節暨華夏口琴藝術節",
            }
        )

        self.assertIn(MODULE.normalize_key("傅泓亮"), keys)
        self.assertIn(MODULE.normalize_key("中國大眾音協口琴樂團"), keys)


if __name__ == "__main__":
    unittest.main()
