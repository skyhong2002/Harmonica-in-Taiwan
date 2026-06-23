# Harmonica in Taiwan

Independent public site for `harmonica.observe.tw`.

This project is standalone. It contains its own public-safe source CSV files,
static site, and data build script.

## Structure

- `site/` - static web root served by Caddy.
- `site/data/site-data.js` - generated public data bundle consumed by the site.
- `data/sources/` - public-safe CSV sources. These exclude internal comments,
  watch policies, private credentials, member data, and repertoire links.
- `scripts/build_social_sources.py` - rebuilds public Facebook and YouTube watcher sources from the public CSV files.
- `scripts/youtube_ytdlp_fetcher.py` - fetches recent YouTube videos with `yt-dlp` into the normalized public inbox.
- `scripts/apify_facebook_fetcher.py` - fetches public Facebook posts through the budget-capped Apify fallback.
- `scripts/build_public_data.py` - rebuilds `site/data/site-data.js`.
- `scripts/social_feed_watchdog.py` - reads public RSS/RSSHub/JSONL sources and writes candidate updates.
- `scripts/generate_rss_feeds.py` - publishes RSS feeds under `site/feeds/`.
- `scripts/run_pipeline.py` - runs the standalone rebuild/watch/feed pipeline.
- `deploy/Caddyfile.snippet` - Caddy site block for this project.

## Rebuild

```bash
python3 scripts/build_public_data.py
python3 scripts/generate_rss_feeds.py
```

Or run the full standalone pipeline:

```bash
python3 scripts/run_pipeline.py
```

The social watcher defaults to a 7-day public-post window. To rebuild the first
public RSS baseline with only the latest week of matching posts:

```bash
python3 scripts/run_pipeline.py --emit-initial --max-post-age-days 7
```

## Social Fetchers

YouTube uses `yt-dlp`. Install it for the same Python used by launchd:

```bash
python3 -m pip install --user yt-dlp
```

Facebook uses Apify's `apify/facebook-posts-scraper` through
`scripts/apify_facebook_fetcher.py`. It is deliberately conservative:

- default dry-run unless `--run` is passed;
- rotates a small source batch each run;
- enforces `maxTotalChargeUsd`, `maxItems`, a local 24h/30d ledger, and Apify account monthly usage checks;
- writes only normalized public rows to `data/feeds/social_feed_inbox.jsonl`.

Token lookup order:

1. `HARMONICA_APIFY_API_TOKEN`
2. `BAMBOO_APIFY_API_TOKEN`
3. `APIFY_TOKEN` or `APIFY_API_TOKEN`
4. macOS Keychain `harmonica-observe-apify` / `harmonica`
5. macOS Keychain `bamboo-apify` / `bamboo`

Dry-run checks:

```bash
python3 scripts/build_social_sources.py --check
python3 scripts/youtube_ytdlp_fetcher.py --check
python3 scripts/apify_facebook_fetcher.py --check
```

## Local Preview

```bash
python3 -m http.server 8765 --directory site
```

Open `http://127.0.0.1:8765/`.

## Public Feeds

- `https://harmonica.observe.tw/feeds/updates.xml`
- `https://harmonica.observe.tw/feeds/events.xml` - 全臺灣的口琴實體活動
- `https://harmonica.observe.tw/feeds/posts-videos.xml` - 全臺灣的口琴相關貼文以及影片發布
- `https://harmonica.observe.tw/feeds/student-clubs.xml` - 全臺灣的口琴學生社團動態
- `https://harmonica.observe.tw/feeds/opportunities.xml` - 口琴社團需要知道的補助或是比賽資訊
- `https://harmonica.observe.tw/feeds/sources.xml`

## Public API

Bamboo Hermes should read the public JSON API instead of scraping social
sources directly:

- `https://harmonica.observe.tw/api/latest.json`
- `https://harmonica.observe.tw/api/catalog.json`
- `https://harmonica.observe.tw/api/events.json`
- `https://harmonica.observe.tw/api/posts-videos.json`
- `https://harmonica.observe.tw/api/student-clubs.json`
- `https://harmonica.observe.tw/api/opportunities.json`
- `https://harmonica.observe.tw/api/sources.json`

## Production

Caddy serves:

```text
/Users/skyhong/Documents/Harmonica-in-Taiwan/site
```

for `https://harmonica.observe.tw/`.

## Scheduler

The standalone pipeline can run through launchd:

```bash
cp deploy/tw.observe.harmonica.pipeline.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/tw.observe.harmonica.pipeline.plist
launchctl kickstart -k "gui/$(id -u)/tw.observe.harmonica.pipeline"
```

It rebuilds public data, watches public feeds, and regenerates RSS every 2 hours.
On macOS, a user LaunchAgent may need Full Disk Access permission before it can
read this project under `~/Documents`. If launchd reports `Operation not
permitted`, run the pipeline manually until the privacy permission is granted:

```bash
cd /Users/skyhong/Documents/Harmonica-in-Taiwan
python3 scripts/run_pipeline.py
```

To grant the permission, open System Settings -> Privacy & Security -> Full Disk
Access, use `+`, press Cmd+Shift+G in the file picker, and add:

- `/bin/zsh`
- `/Library/Developer/CommandLineTools/usr/bin/python3`
- `/usr/bin/python3` if it is selectable on this macOS version

After turning those entries on, reload the LaunchAgent and verify `last exit
code = 0`.

## License

MIT. See `LICENSE`.
