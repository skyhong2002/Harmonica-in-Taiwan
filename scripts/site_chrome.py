"""Shared static-site chrome used by every generated public page."""

from __future__ import annotations

import re


ASSET_VERSION = "20260822-canonical-source-slug-v1"
BRAND_LOGO_HTML = (
    f'<img class="brand-logo" src="/assets/logo.svg?v={ASSET_VERSION}" '
    'alt="臺灣口琴觀測站" width="200" height="47">'
)

_SITE_HEADER_RE = re.compile(
    r"(?ms)^[ \t]*<header class=\"site-header\">.*?</header>"
)
_ASSET_VERSION_RE = re.compile(
    r'(?P<asset>(?:(?:https://harmonica\.observe\.tw)?/)?'
    r'(?:assets|data)/[^"\'\s?]+)\?v=[A-Za-z0-9._-]+'
)


def render_header() -> str:
    """Render the canonical public navigation header."""

    return f"""    <header class="site-header">
      <a class="brand" href="/" aria-label="臺灣口琴觀測站首頁">
        {BRAND_LOGO_HTML}
      </a>
      <nav class="site-nav" aria-label="主要導覽">
        <a href="/post/">公開貼文</a>
        <a href="/source/">公開來源</a>
        <a href="/scores/">比賽指定曲</a>
        <a href="/status/">狀態</a>
        <a href="/submit/">資料回報</a>
      </nav>
    </header>"""


def replace_site_headers(document: str) -> str:
    """Replace any existing site header with the canonical one."""

    return _SITE_HEADER_RE.sub(render_header(), document)


def replace_asset_versions(document: str) -> str:
    """Bump only first-party asset URLs, never query strings on external links."""

    return _ASSET_VERSION_RE.sub(
        lambda match: f"{match.group('asset')}?v={ASSET_VERSION}",
        document,
    )


def normalize_document(document: str) -> str:
    """Apply the shared header and first-party asset version to one document."""

    return replace_asset_versions(replace_site_headers(document))
