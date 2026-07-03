#!/usr/bin/env python3
"""Validate harmonica.observe.tw sitemap.xml URLs locally against generated files."""

import xml.etree.ElementTree as ET
import sys
import re
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
SITEMAP_XML = SITE_ROOT / "sitemap.xml"

def main() -> int:
    if not SITEMAP_XML.exists():
        print(f"Error: {SITEMAP_XML} does not exist. Run build/generation first.", file=sys.stderr)
        return 1

    try:
        root = ET.parse(SITEMAP_XML).getroot()
    except Exception as e:
        print(f"Error parsing sitemap.xml: {e}", file=sys.stderr)
        return 1

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("sm:url", ns)
    print(f"Validating {len(urls)} URLs in sitemap.xml...")

    errors = 0
    checked = 0

    for url_el in urls:
        loc_el = url_el.find("sm:loc", ns)
        if loc_el is None or not loc_el.text:
            print("Error: <url> element missing <loc>", file=sys.stderr)
            errors += 1
            continue

        loc = loc_el.text.strip()
        checked += 1

        # Match local file path
        # URL format: https://harmonica.observe.tw/path/
        if not loc.startswith("https://harmonica.observe.tw/"):
            print(f"Error: URL domain is invalid: {loc}", file=sys.stderr)
            errors += 1
            continue

        rel_path = loc.replace("https://harmonica.observe.tw/", "")
        decoded_rel_path = urllib.parse.unquote(rel_path)

        # Determine local path
        if decoded_rel_path == "":
            local_file = SITE_ROOT / "index.html"
        elif decoded_rel_path.endswith("/"):
            local_file = SITE_ROOT / decoded_rel_path / "index.html"
        else:
            local_file = SITE_ROOT / decoded_rel_path

        if not local_file.exists():
            print(f"Error: Local file does not exist for URL: {loc} -> {local_file.relative_to(PROJECT_ROOT)}", file=sys.stderr)
            errors += 1
            continue

        # Check file content
        try:
            content = local_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading file {local_file}: {e}", file=sys.stderr)
            errors += 1
            continue

        # Check canonical
        canonical_match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', content)
        if not canonical_match:
            print(f"Warning: Missing canonical link in {local_file.relative_to(PROJECT_ROOT)} for {loc}", file=sys.stderr)
            errors += 1
        else:
            canonical_href = canonical_match.group(1)
            # Support both relative and absolute canonicals, but absolute matching loc is preferred
            expected_canonical = loc
            if canonical_href != expected_canonical:
                print(f"Error: Canonical mismatch in {local_file.relative_to(PROJECT_ROOT)}: expected {expected_canonical}, got {canonical_href}", file=sys.stderr)
                errors += 1

        # Check for noindex
        if "noindex" in content.lower():
            # Ensure it is not in meta robots
            robots_match = re.search(r'<meta\s+name="robots"\s+content="([^"]*noindex[^"]*)"', content, re.IGNORECASE)
            if robots_match:
                print(f"Error: Found noindex robots meta in {local_file.relative_to(PROJECT_ROOT)}: {robots_match.group(0)}", file=sys.stderr)
                errors += 1

        # Check for redirect chain or redirect indicators
        # Redirect pages (like the ones we will build for legacy source URLs) should NOT be in sitemap.xml!
        if "http-equiv=\"refresh\"" in content:
            print(f"Error: Sitemap URL points to a redirect page: {loc} in {local_file.relative_to(PROJECT_ROOT)}", file=sys.stderr)
            errors += 1

    print(f"\nValidation completed: {checked} URLs checked, {errors} errors found.")
    return 1 if errors > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
