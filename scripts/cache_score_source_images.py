#!/usr/bin/env python3
"""Cache reviewed score covers as small local previews; run explicitly, never on visits."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from urllib.parse import urlsplit
from generate_rss_feeds import convert_image_bytes_to_webp
from global_catalog import ROOT, SCORE_MEDIA, public_url


def cache_previews() -> tuple[int, int]:
    manifest = json.loads(SCORE_MEDIA.read_text(encoding='utf-8'))
    folder = ROOT / 'site' / 'assets' / 'feed-images'
    folder.mkdir(parents=True, exist_ok=True)
    succeeded = failed = 0
    for sid, row in manifest.get('sources', {}).items():
        url = public_url(row.get('imageUrl'), local=False)
        if not url:
            continue
        filename = 'score-' + hashlib.sha256(url.encode()).hexdigest()[:20] + '.webp'
        destination = folder / filename
        try:
            if not destination.is_file():
                with tempfile.TemporaryDirectory(prefix='harmonica-cover-') as directory:
                    downloaded = Path(directory) / 'image'
                    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                                    '--proto', '=https', '--proto-redir', '=https', '--max-time', '25',
                                    '--max-filesize', '6000000', '--user-agent', 'Mozilla/5.0',
                                    '--output', str(downloaded), url], check=True, capture_output=True)
                    extension = Path(urlsplit(url).path).suffix.lower() or '.jpg'
                    if not convert_image_bytes_to_webp(downloaded.read_bytes(), extension, destination):
                        raise ValueError('Image cannot be decoded as a preview')
            row['localImage'] = '/assets/feed-images/' + filename
            succeeded += 1
        except (OSError, ValueError, subprocess.SubprocessError):
            failed += 1
            print(f'{sid}: image unavailable; preserving existing cache/provenance')
    temporary = SCORE_MEDIA.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(SCORE_MEDIA)
    return succeeded, failed


if __name__ == '__main__':
    ok, failed = cache_previews()
    print(f'Score previews ready: {ok}; unavailable: {failed}')
