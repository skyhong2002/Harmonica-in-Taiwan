#!/usr/bin/env python3
"""Build the public /submit/ page from its checked-in template."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.configure_submission_form import FORM_TITLE, RESPONDER_URI


TEMPLATE_PATH = PROJECT_ROOT / "templates" / "submit.html"
OUTPUT_PATH = PROJECT_ROOT / "site" / "submit" / "index.html"


def render_submit_page() -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.replace("__GOOGLE_FORM_URL__", RESPONDER_URI)
    rendered = rendered.replace("__GOOGLE_FORM_TITLE__", FORM_TITLE)
    if "__GOOGLE_FORM_" in rendered:
        raise ValueError("Unresolved Google Form placeholder in submit template")
    return rendered


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_submit_page(), encoding="utf-8")
    print(f"Built {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
