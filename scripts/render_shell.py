"""Small server-rendered entry view and localized metadata for the JS application.

The browser enhances the same routes. Known source URLs retain meaningful HTML,
canonical URLs and hreflang links without running JavaScript.
"""
from __future__ import annotations
import html
import json
import re
from urllib.parse import urlencode

LOCALES = ('zh-Hant', 'en', 'ja', 'ko')
WORDS = {
    'en': {'brand': 'Harmonica Observatory', 'home': 'Home', 'events': 'Events', 'post': 'Posts', 'source': 'Sources', 'scores': 'Scores', 'feeds': 'Subscribe', 'status': 'System status', 'contribute': 'Contribute API capacity', 'submit': 'Suggest a source', 'about': 'About', 'privacy': 'Privacy', 'description': 'Discover public harmonica events, artists, ensembles, clubs and scores around the world. Browse original sources across countries and languages.', 'original': 'Original sources', 'latest': 'Latest public posts', 'all': 'Browse all sources'},
    'zh-Hant': {'brand': '口琴觀測站', 'home': '首頁', 'events': '活動', 'post': '貼文', 'source': '來源', 'scores': '樂譜', 'feeds': '訂閱', 'status': '系統狀態', 'contribute': '貢獻 API 額度', 'submit': '回報來源', 'about': '關於', 'privacy': '隱私', 'description': '探索全球公開口琴活動、演奏者、樂團、社團與樂譜資訊，跨越國家與語言瀏覽原始來源，保留原文與活動時區。', 'original': '原始來源', 'latest': '最新公開貼文', 'all': '瀏覽所有來源'},
    'ja': {'brand': 'ハーモニカ観測所', 'home': 'ホーム', 'events': 'イベント', 'post': '投稿', 'source': '情報源', 'scores': '楽譜', 'feeds': '購読', 'status': '稼働状況', 'contribute': 'API 枠を提供', 'submit': '情報源を提案', 'about': 'このサイトについて', 'privacy': 'プライバシー', 'description': '世界のハーモニカイベント、演奏家、アンサンブル、クラブ、楽譜を探す公開情報サイト。国や言語を越えて原文と情報源を確認できます。', 'original': '元の情報源', 'latest': '最新の公開投稿', 'all': 'すべての情報源を見る'},
    'ko': {'brand': '하모니카 관측소', 'home': '홈', 'events': '행사', 'post': '게시물', 'source': '정보 출처', 'scores': '악보', 'feeds': '구독', 'status': '시스템 상태', 'contribute': 'API 할당량 기여', 'submit': '출처 제안', 'about': '소개', 'privacy': '개인정보', 'description': '전 세계 하모니카 행사, 연주자, 앙상블, 동아리와 악보를 탐색하세요. 국가와 언어를 넘어 원문과 공개 출처를 확인할 수 있습니다.', 'original': '원본 출처', 'latest': '최신 공개 게시물', 'all': '모든 출처 보기'},
}


SCORE_GUIDE = {
    'en': ('Find & buy music', 'Find books, sales announcements, music libraries and enquiry contacts.'),
    'zh-Hant': ('找譜與購譜', '找一本譜集、查看販售公告，或到曲庫與團隊網站詢問樂譜。'),
    'ja': ('楽譜の入手先', '楽譜集、販売案内、曲庫や問い合わせ先を探せます。'),
    'ko': ('악보 찾기·구매', '악보집, 판매 공지, 곡목 자료실과 문의처를 찾아보세요.'),
}


def normalize_locale(value: str) -> str:
    value = str(value or '').replace('_', '-').lower()
    if value.startswith('zh'):
        return 'zh-Hant'
    for lang in ('en', 'ja', 'ko'):
        if value == lang or value.startswith(lang + '-'):
            return lang
    return 'en'


def e(value: object) -> str:
    return html.escape(str(value or ''), quote=True)


def render_document(template: str, path: str, catalog: dict, origin: str, locale: str = 'en') -> str:
    locale = normalize_locale(locale)
    words = WORDS[locale]
    route = path.strip('/').split('/')[0] or 'home'
    route_id = path.rstrip('/').rsplit('/', 1)[-1]
    source = next((s for s in catalog.get('sources', []) if s.get('url') == path or
                   (path.startswith(('/source/', '/post/source/')) and
                    (str(s.get('id')) == route_id or
                     str(s.get('url') or '').rstrip('/').rsplit('/', 1)[-1] == route_id))), None)
    canonical_path = (source.get('url') or path) if source else path
    page = (source.get('name') or source.get('id') or words['source']) if source else words.get(route, words['home'])
    description = (source.get('summary') or words['description']) if source else words['description']
    score_guide = path.rstrip('/') == '/scores/sources'
    if score_guide:
        page, description = SCORE_GUIDE[locale]
    title = page + ' · ' + words['brand']
    canonical = origin.rstrip('/') + canonical_path
    canonical += '?' + urlencode({'lang': locale})
    document = re.sub(r'<html\b[^>]*>', '<html lang="' + locale + '">', template, count=1)
    document = re.sub(r'<title>.*?</title>', lambda _: '<title>' + e(title) + '</title>', document, count=1, flags=re.S)
    document = re.sub(r'<meta\s+name=["\']description["\'][^>]*>', '', document, flags=re.I)
    document = re.sub(r'<link\s+rel=["\']canonical["\'][^>]*>', '', document, flags=re.I)
    head = '\n<meta name="description" content="' + e(description) + '">\n'
    head += '<link rel="canonical" href="' + e(canonical) + '">\n'
    for language in LOCALES:
        href = origin.rstrip('/') + canonical_path + '?' + urlencode({'lang': language})
        head += '<link rel="alternate" hreflang="' + language + '" href="' + e(href) + '">\n'
    head += '<meta property="og:site_name" content="' + e(words['brand']) + '">\n'
    head += '<meta property="og:title" content="' + e(title) + '">\n'
    head += '<meta property="og:description" content="' + e(description) + '">\n'
    head += '<meta property="og:url" content="' + e(canonical) + '">\n'
    document = document.replace('</head>', head + '</head>', 1)
    nav = ' · '.join('<a href="/' + slug + '/?lang=' + locale + '">' + e(words[slug]) + '</a>'
                     for slug in ('events', 'post', 'source', 'scores', 'feeds', 'contribute'))
    content = '<section class="server-content" aria-label="' + e(page) + '"><nav>' + nav + '</nav><h1>' + e(page) + '</h1><p>' + e(description) + '</p>'
    if source:
        content += '<p>' + e(source.get('country')) + ' · ' + e(source.get('region')) + '</p><h2>' + e(words['original']) + '</h2><ul>'
        content += ''.join('<li><a href="' + e(link['url']) + '" rel="noreferrer">' + e(link.get('label') or link['url']) + '</a></li>' for link in source.get('links', []))
        content += '</ul><h2>' + e(words['latest']) + '</h2><ul>'
        content += ''.join('<li><a href="' + e(p['url']) + '">' + e(p['title']) + '</a></li>' for p in [p for p in catalog.get('posts', []) if p.get('sourceId') == source.get('id')][:12])
        content += '</ul>'
    elif score_guide:
        content += '<ul>' + ''.join('<li><a href="' + e(row.get('sourceUrl') or row.get('url')) + '">'
            + e(row.get('title') or row.get('name')) + '</a> · ' + e(row.get('name')) + '</li>'
            for row in catalog.get('scoreSources', [])[:24]) + '</ul>'
    else:
        content += '<ul>' + ''.join('<li><a href="' + e(s.get('url') or '/source/') + '?lang=' + locale + '">' + e(s.get('name') or s.get('id')) + '</a></li>' for s in catalog.get('sources', [])[:24]) + '</ul>'
    content += '<a href="/source/?lang=' + locale + '">' + e(words['all']) + '</a></section>'
    if '<!--SERVER_CONTENT-->' in document:
        document = document.replace('<!--SERVER_CONTENT-->', content)
    else:
        document = document.replace('</body>', '<noscript>' + content + '</noscript></body>', 1)
    return document
