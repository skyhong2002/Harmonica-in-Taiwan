# Harmonica in Taiwan - Workspace Rules

Whenever adding a new entry to the public watchlist (`data/sources/harmonica-source-watchlist-public.csv`):

1. **Avatar/Logo Retrieval**:
   - Extract the official profile picture/avatar of the added entry from their social media profiles (Facebook, Instagram, Threads, YouTube, etc.).
   - If direct graph API or CDN URLs are rate-limited or forbidden (e.g., 403), try scraping public pages (such as Threads profile `og:image` tags or unescaped HTML content).
   - Convert the extracted photo to WebP format, name it using the first 20 characters of the SHA-256 hash of the remote URL, and save it in `site/assets/source-avatars/`.

2. **Custom Description Integration**:
   - Retrieve the self-written bio/description (about section) from the entry's social media pages.
   - Cache this custom description and the WebP avatar path in `data/feeds/source_profiles.json` under keys matching the entry's platforms (e.g. `ig_username`, `threads_username`, `fb_page_id`).
   - Add the custom description under the computed fingerprints in `state/source_llm_tags.json` as `sourceSummary` so it overrides the default template description on the landing page.

3. **Build & Validation**:
   - Run the data pipeline using `.venv/bin/python scripts/run_pipeline.py --skip-watch --skip-calendar-sync --no-lock`.
   - Run verification scripts (`validate_public_outputs.py`, `check_source_coverage.py`, `validate_legacy_redirects.py`) to ensure no build errors.

4. **Deployment**:
   - Commit and push source files to the `main` branch.
   - Compile static pages locally onto the `gh-pages` branch using `publish_github_pages.py` and push them online.
