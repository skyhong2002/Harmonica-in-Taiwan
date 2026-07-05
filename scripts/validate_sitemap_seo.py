#!/usr/bin/env python3
"""Validate sitemap, canonical, and crawlability invariants for generated SEO pages."""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
SITEMAP_XML = SITE_ROOT / "sitemap.xml"
SOURCES_JSON = SITE_ROOT / "api" / "sources.json"
PUBLIC_BASE_URL = "https://harmonica.observe.tw"
SOURCE_INDEX_MAX_BYTES = 300_000


def local_file_for_url(loc: str) -> Path | None:
    if not loc.startswith(PUBLIC_BASE_URL + "/"):
        return None
    parsed = urllib.parse.urlparse(loc)
    decoded_path = urllib.parse.unquote(parsed.path.lstrip("/"))
    if decoded_path == "":
        return SITE_ROOT / "index.html"
    if decoded_path.endswith("/"):
        return SITE_ROOT / decoded_path / "index.html"
    return SITE_ROOT / decoded_path


def canonical_href(content: str) -> str:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', content)
    return match.group(1) if match else ""


def robots_noindex(content: str) -> str:
    match = re.search(
        r'<meta\s+name="robots"\s+content="([^"]*noindex[^"]*)"',
        content,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def validate_json_ld(content: str, rel_path: str, errors: list[str]) -> None:
    has_event_block = False
    is_event_page = "site/event/" in rel_path or "/event/" in rel_path
    
    for index, match in enumerate(
        re.finditer(
            r'<script\s+[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            content,
            re.DOTALL | re.IGNORECASE,
        ),
        start=1,
    ):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("@type") == "Event":
                has_event_block = True
                
                # 1. required fields: name, startDate, location
                for req in ["name", "startDate", "location"]:
                    val = data.get(req)
                    if not val:
                        errors.append(f"Event in {rel_path} is missing required field '{req}'")
                    elif isinstance(val, str) and not val.strip():
                        errors.append(f"Event in {rel_path} has empty required field '{req}'")
                
                # Check location structure
                loc = data.get("location")
                if isinstance(loc, dict):
                    if not loc.get("name") or not str(loc.get("name")).strip():
                        errors.append(f"Event in {rel_path} location has empty name")
                
                # 2. offers validation
                if "offers" in data:
                    offers = data["offers"]
                    if not isinstance(offers, dict):
                        errors.append(f"Event in {rel_path} offers is not an object")
                    else:
                        # must have url
                        if not offers.get("url") or not str(offers.get("url")).strip():
                            errors.append(f"Event in {rel_path} offers is missing 'url'")
                        # price and priceCurrency consistency
                        has_price = "price" in offers
                        has_currency = "priceCurrency" in offers
                        if has_price or has_currency:
                            if not has_price or offers.get("price") is None or str(offers.get("price")).strip() == "":
                                errors.append(f"Event in {rel_path} offers is missing 'price'")
                            if not has_currency or not offers.get("priceCurrency") or not str(offers.get("priceCurrency")).strip():
                                errors.append(f"Event in {rel_path} offers is missing 'priceCurrency'")

                # 3. image must be absolute URL
                if "image" in data:
                    img = data["image"]
                    if not img:
                        errors.append(f"Event in {rel_path} has empty 'image' field")
                    elif not (isinstance(img, str) and (img.startswith("http://") or img.startswith("https://"))):
                        errors.append(f"Event in {rel_path} 'image' is not an absolute URL: {img}")

                # 4. No empty string, null, empty object, or empty list allowed anywhere
                def check_empty_values(obj: Any, path_str: str) -> None:
                    if obj is None:
                        errors.append(f"Event in {rel_path} has null value at '{path_str}'")
                    elif isinstance(obj, str):
                        if not obj.strip():
                            errors.append(f"Event in {rel_path} has empty string at '{path_str}'")
                    elif isinstance(obj, dict):
                        if not obj:
                            errors.append(f"Event in {rel_path} has empty object at '{path_str}'")
                        for k, v in obj.items():
                            check_empty_values(v, f"{path_str}.{k}" if path_str else k)
                    elif isinstance(obj, list):
                        if not obj:
                            errors.append(f"Event in {rel_path} has empty list at '{path_str}'")
                        for i, item_val in enumerate(obj):
                            check_empty_values(item_val, f"{path_str}[{i}]")

                check_empty_values(data, "")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON-LD in {rel_path} block {index}: {exc.msg}")
            
    if is_event_page and not has_event_block:
        errors.append(f"Event page {rel_path} is missing JSON-LD block with @type: Event")


def validate_source_index(errors: list[str]) -> None:
    if not SOURCES_JSON.exists():
        errors.append(f"missing source API: {SOURCES_JSON.relative_to(PROJECT_ROOT)}")
        return
    if not (SITE_ROOT / "source" / "index.html").exists():
        errors.append("missing source index page: site/source/index.html")
        return
    payload = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else []
    expected_count = len(entries) if isinstance(entries, list) else 0
    source_index = SITE_ROOT / "source" / "index.html"
    content = source_index.read_text(encoding="utf-8")
    card_count = len(re.findall(r'<article\s+class="entry-card"', content))
    if card_count < expected_count:
        errors.append(
            "source index is not crawler-readable: "
            f"expected at least {expected_count} static .entry-card articles, found {card_count}"
        )
    size = source_index.stat().st_size
    if size > SOURCE_INDEX_MAX_BYTES:
        errors.append(
            "source index is too large: "
            f"{size} bytes exceeds {SOURCE_INDEX_MAX_BYTES} byte budget"
        )


def validate_dataset_structured_data(errors: list[str]) -> None:
    scores_index = SITE_ROOT / "scores" / "index.html"
    if not scores_index.exists():
        errors.append("missing scores index page: site/scores/index.html")
        return
    content = scores_index.read_text(encoding="utf-8")
    
    # Extract all application/ld+json blocks
    json_ld_blocks = []
    for match in re.finditer(
        r'<script\s+[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        content,
        re.DOTALL | re.IGNORECASE,
    ):
        raw = match.group(1).strip()
        try:
            json_ld_blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            pass # validate_json_ld will already catch JSON syntax errors
            
    # Look for Dataset type in json_ld_blocks
    dataset_block = None
    for block in json_ld_blocks:
        if isinstance(block, dict) and block.get("@type") == "Dataset":
            dataset_block = block
            break
            
    if not dataset_block:
        errors.append("site/scores/index.html is missing a JSON-LD block with @type: Dataset")
        return
        
    # Check dataset structured data properties
    description = dataset_block.get("description")
    if not description:
        errors.append("Dataset in site/scores/index.html is missing a description")
    elif len(description) < 50:
        errors.append(f"Dataset description in site/scores/index.html is too short ({len(description)} characters, expected >= 50)")
        
    url = dataset_block.get("url")
    expected_url = "https://harmonica.observe.tw/scores/"
    if url != expected_url:
        errors.append(f"Dataset url in site/scores/index.html: expected '{expected_url}', got '{url}'")
        
    dataset_id = dataset_block.get("@id")
    expected_id = "https://harmonica.observe.tw/scores/#dataset"
    if dataset_id != expected_id:
        errors.append(f"Dataset @id in site/scores/index.html: expected '{expected_id}', got '{dataset_id}'")


def sitemap_urls() -> tuple[list[str], list[str]]:
    if not SITEMAP_XML.exists():
        return [], [f"missing sitemap: {SITEMAP_XML.relative_to(PROJECT_ROOT)}"]
    try:
        root = ET.parse(SITEMAP_XML).getroot()
    except Exception as exc:
        return [], [f"error parsing sitemap.xml: {exc}"]
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    errors = []
    for url_el in root.findall("sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        if loc_el is None or not loc_el.text:
            errors.append("<url> element missing <loc>")
            continue
        urls.append(loc_el.text.strip())
    return urls, errors


def validate_sitemap_urls(urls: list[str], errors: list[str]) -> None:
    forbidden_paths = ("/watchlist-", "/post/source/", "/directory/", "/status/")
    for loc in urls:
        parsed = urllib.parse.urlparse(loc)
        if not loc.startswith(PUBLIC_BASE_URL + "/"):
            errors.append(f"URL domain is invalid: {loc}")
            continue
        if any(fragment in parsed.path for fragment in forbidden_paths):
            errors.append(f"sitemap contains forbidden non-canonical URL: {loc}")
            continue
        local_file = local_file_for_url(loc)
        if local_file is None:
            errors.append(f"could not map URL to local file: {loc}")
            continue
        if not local_file.exists():
            errors.append(f"local file does not exist for URL: {loc} -> {local_file.relative_to(PROJECT_ROOT)}")
            continue
        content = local_file.read_text(encoding="utf-8")
        rel_path = str(local_file.relative_to(PROJECT_ROOT))
        canonical = canonical_href(content)
        if canonical != loc:
            errors.append(f"canonical mismatch in {rel_path}: expected {loc}, got {canonical or '-'}")
        noindex = robots_noindex(content)
        if noindex:
            errors.append(f"sitemap URL points to noindex page: {loc} ({noindex})")
        if re.search(r'http-equiv=["\']refresh["\']', content, re.IGNORECASE):
            errors.append(f"sitemap URL points to a redirect page: {loc} in {rel_path}")
        validate_json_ld(content, rel_path, errors)


def main() -> int:
    urls, errors = sitemap_urls()
    print(f"Validating {len(urls)} URLs in sitemap.xml...")
    validate_sitemap_urls(urls, errors)
    validate_source_index(errors)
    validate_dataset_structured_data(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"\nValidation completed: {len(urls)} URLs checked, {len(errors)} errors found.")
        return 1
    print(f"\nValidation completed: {len(urls)} URLs checked, 0 errors found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
