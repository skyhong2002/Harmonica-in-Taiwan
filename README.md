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

The social watcher defaults to a 30-day public-post window. To rebuild the first
public RSS baseline with only the latest month of matching posts:

```bash
python3 scripts/run_pipeline.py --emit-initial --max-post-age-days 30
```

## Social Fetchers

YouTube uses `yt-dlp`. Install it for the same Python used by launchd:

```bash
python3 -m pip install --user yt-dlp
```

Facebook uses Apify's `apify/facebook-posts-scraper` through
`scripts/apify_facebook_fetcher.py`. It is deliberately conservative:

- default dry-run unless `--run` is passed;
- checks every enabled Facebook source when the Facebook fetch runs;
- runs the paid Facebook fetch at most once every 4 days by default, adjustable with `--min-run-spacing-days`;
- uses the remaining local calendar-day budget as the Apify run cap instead of a separate per-run cap;
- defaults to a USD 0.60 daily budget, adjustable with `--daily-budget-usd`;
- auto-sizes `maxItems` from the selected source count and `resultsLimit`;
- enforces a local calendar-day ledger and Apify account monthly usage checks;
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

The social watcher uses an LLM tagger before falling back to keyword matching.
It calls the OpenAI-compatible OpenCode Go chat-completions endpoint by default:

- base URL: `https://opencode.ai/zen/go/v1`
- model: `mimo-v2.5`
- cache: `state/social_llm_tags.json`

LLM token lookup order:

1. `HARMONICA_OPENCODE_GO_API_KEY`
2. `OPENCODE_GO_API_KEY`
3. `HARMONICA_LLM_API_KEY`
4. macOS Keychain `harmonica-opencode-go` / `harmonica`

Set `HARMONICA_ENABLE_LLM_TAGS=0` or pass `--skip-llm-tags` to
`scripts/run_pipeline.py` to disable LLM tagging for a run.

To rewrite existing candidate tags with the same LLM classifier:

```bash
python3 scripts/retag_social_candidates.py --write
python3 scripts/generate_rss_feeds.py
```

The retag script backs up `data/feeds/social_candidates.jsonl` before replacing
it. It skips `public-link-backfill` rows by default so source coverage rows stay
intact. Pass `--keep-irrelevant` to keep LLM-rejected rows for inspection instead
of removing them from the public candidate file.

Directory entries also have source-level tags for people, clubs, ensembles,
teaching sources, venues, and activity platforms. These are cached separately in
`state/source_llm_tags.json`:

```bash
python3 scripts/tag_directory_entries.py --write --refresh
python3 scripts/build_public_data.py
python3 scripts/generate_rss_feeds.py
```

The directory tagger does not edit the source CSV files. It writes a generated
cache that `scripts/build_public_data.py` merges into `site/data/site-data.js`
and `/api/sources.json`.

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

## Public Reports

Public additions, corrections, broken links, and source updates should start
from the site report page:

- `https://harmonica.observe.tw/submit/`

The report page builds a GitHub issue URL with query parameters so the final
GitHub Issue Form opens with the title and form fields pre-filled:

- `https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/new?template=content-correction.yml`

Only public, verifiable source material should be submitted. Do not include
private contact details, private group links, credentials, member data, or other
non-public information in issues.

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
```

It rebuilds public data, watches public feeds, and regenerates RSS daily at
00:00 in the Mac's local timezone.

To run one sync immediately after setup:

```bash
launchctl kickstart -k "gui/$(id -u)/tw.observe.harmonica.pipeline"
```
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
