> 歷史驗收：此文件記錄前輪基礎功能／部署。新版介面與最終米色／綠色配色的驗收見 [ui-acceptance-2026-09-23.md](ui-acceptance-2026-09-23.md)。

# Harmonica Observatory acceptance — 2026-09-23

## Runtime and deployment

The local application listens on `127.0.0.1:8330` as the user LaunchAgent `tw.observe.harmonica.web`. It uses this checkout's `.venv/bin/python`. Its environment declares `HARMONICA_PUBLIC_ORIGIN=https://harmonica.observe.tw` and `HARMONICA_TRUST_PROXY=1`; only a loopback HTTPS reverse proxy is trusted. Browser sessions and encrypted contribution records are isolated under `state/community/`.

The service installer was exercised with mocked launchctl calls in three tests. The actual web LaunchAgent was installed and started during this deployment. `GET /api/v1/health`, `/api/v1/catalog`, `/api/v1/community` and `/api/v1/session` responded successfully on localhost. The ingestion LaunchAgents were temporarily unloaded while the migration was being checked, then restored; their verified final configuration is recorded below.

Install and start on this Mac:

```bash
.venv/bin/python scripts/install_local_service.py --install --public-origin https://harmonica.observe.tw
```

Inspect or restart after Python changes:

```bash
launchctl print gui/$(id -u)/tw.observe.harmonica.web
launchctl kickstart -k gui/$(id -u)/tw.observe.harmonica.web
curl --fail http://127.0.0.1:8330/api/v1/health
```

Logs are `logs/web.log` and `logs/web.err.log`. Request bodies, tokens and request paths are not logged by the application. An early community endpoint failure was traced to a running process holding an older imported module; restarting after the coordinated changes resolved it.

## TLS and DNS evidence

Both the local resolver and Cloudflare's `1.1.1.1` resolver returned `A 140.113.240.11` for `harmonica.observe.tw`, with no AAAA answer. The Mac's interface is `10.113.240.11`, behind the public address. No DNS records were changed by this deployment.

The previous certificate had expired. Recent Caddy renewal errors showed ACME validation reaching the old Cloudflare IPv6 destination and receiving 404. Once DNS pointed to the Mac, public HTTP requests reached Caddy. The existing active JSON configuration was force-reloaded through the admin API, with `Cache-Control: must-revalidate`, without modifying any site's configuration. The next normal certificate maintenance pass successfully completed ACME validation and renewed the Harmonica certificate. The force-reload procedure follows the [Caddy administration API](https://caddyserver.com/docs/api#post-load).

Verified using the system certificate trust store and hostname validation, with no TLS bypass:

- Issuer: Let's Encrypt YE1.
- Valid from: **2026-09-22 17:01:16 UTC**.
- Valid until: **2026-12-21 17:01:15 UTC**.
- Public HTTPS homepage returned 200 after renewal.
- The entire active Caddy configuration compared equal before and after certificate renewal.

A private `0600` backup is stored at `state/caddy-before-harmonica-tls-1790099539.json`. This runtime backup may contain configuration credentials and is not part of the repository or public site. Caddy's root LaunchDaemon passes macOS `plutil -lint`; Python's stricter plist XML parser rejected a harmless nonstandard DOCTYPE spelling, so no privileged daemon repair was required.

## Reverse proxy acceptance

**Deployed:** public Caddy now reverse-proxies Harmonica to the localhost application. The active route was changed with a scoped ETag-protected admin PATCH, which returned 200. The same Harmonica-only change was persisted to `/usr/local/etc/caddy/Caddyfile`. The full active configuration compared equal to the expected single-route change; all unrelated virtual hosts, TLS policies and credential expansions were preserved.

The prepared persistent target is the existing Harmonica block in `/usr/local/etc/caddy/Caddyfile`:

```caddyfile
harmonica.observe.tw {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8330
}
```

The candidate was successfully adapted by Caddy. Only this site's block changed; every other Caddyfile byte remained identical. The scoped admin API preserved existing credential expansions and unrelated services. `deploy/Caddyfile.snippet` contains the same target configuration.

Public acceptance verified actual JSON responses, not only status 200. Repeat the checks with:

```bash
curl --fail https://harmonica.observe.tw/api/v1/health
curl --fail --compressed https://harmonica.observe.tw/api/v1/community
curl --fail --compressed https://harmonica.observe.tw/api/v1/sources?limit=1
```

**37 public HTTPS checks passed** with normal certificate and hostname validation:

- JSON health returned `{"ok":true,"service":"harmonica","version":1}`; catalog, community and session APIs also returned JSON.
- The browser session cookie included Secure, HttpOnly and SameSite=Strict.
- English, Traditional Chinese, Japanese and Korean homepage, directory, contribution and known-source SSR pages returned the requested language.
- Application JavaScript, stylesheet and language/community modules loaded successfully.
- Source/update RSS and Taiwan/international/online ICS feeds were intact.
- Missing URLs and private `.env`/state paths returned real 404 responses.
- `/directory/` and `/score-sources/` redirected to the new equivalents while preserving locale queries.
- A cross-origin write was rejected with 403, without creating a submission.
- Same-origin CSRF-authenticated contribution/submission requests reached their validators and rejected missing consent/invalid URL with the expected 400 error codes. No real tokens, actor spend or public test submissions were created.

The live public catalog at this check contained **322 sources, 789 posts, 12 events, 797 score entries and 39 score collections**. Browser visual acceptance remains pending; native browser automation required an approval step unavailable at this checkpoint.

## Scheduler acceptance

Both `tw.observe.harmonica.pipeline` and `tw.observe.harmonica.social-fast` are loaded again in the current user's launchd domain. Readback verified:

- `StartInterval=1800` seconds on both jobs.
- `RunAtLoad=false`, so reloading their configuration did not initiate an extra paid crawl.
- Both execute this checkout's `.venv/bin/python` and set `HARMONICA_LLM_PROVIDER=codex`.
- Neither passes `--publish-pages`; generated outputs are served directly from this installation.
- Both were idle with `runs=0` and `last exit code=(never exited)` after restoration. Launchd exposed the interval but did not provide an exact next-fire timestamp. A new paid collection cycle was not forced for acceptance.

The last completed historical pipeline snapshot was `status=ok`, `Pipeline completed`, at **2026-09-23 00:58:58 Asia/Taipei** in `site/api/pipeline-runtime.json`. The last social-fetch snapshot completed successfully at **00:57:00**. These timestamps are distinguished from the newer offline rebuild; no fresh crawl success is inferred from rebuilding public pages.

A stale **empty** `state/social-fast.lock` directory, dated September 18, was preventing the fast scheduler from getting past its outer shell lock. Its historical log repeatedly reported `social-fast already running; skip`. With no pipeline process running, that stale empty directory was removed. No job was started as part of this cleanup. The redundant outer directory lock was removed from both the source and installed fast-scheduler plist. The job now uses `exec` and relies on `run_pipeline.py`'s existing PID/staleness-aware lock. The installed environment, arguments and 1800-second schedule were preserved; both plist files passed `plutil -lint`. The fast scheduler was re-bootstrapped with `RunAtLoad=false`, and readback again showed all three services loaded, the web service running, and both ingestion jobs idle with zero runs. Three focused scheduler tests pass, including regression coverage for the stale outer lock and preventing an extra crawl at configuration load.

Read-only follow-up:

```bash
launchctl print gui/$(id -u)/tw.observe.harmonica.pipeline
launchctl print gui/$(id -u)/tw.observe.harmonica.social-fast
curl --fail https://harmonica.observe.tw/api/pipeline-runtime.json
```


## Validation evidence

- **224 Python unit tests passed**, as reported by the integration runner.
- **114 local HTTP acceptance checks passed**, as reported by the integration runner.
- **13 Node frontend tests passed**, as reported by the frontend/integration runner.
- **37 public HTTPS acceptance checks passed** after the actual Caddy proxy switch.
- Additional targeted coverage includes encrypted storage, owner-only withdrawal, concurrent budget reservations, CSRF/Host/Origin controls, source-local event timezones, contribution revocation, moderation export, installation and server-rendered content.
- The renderer's literal-backslash source-name crash and legacy source-post alias mismatch were found and repaired; all six focused renderer tests pass.
- The moderation workflow has five passing tests. Export preserves original notes/country, creates an idempotent pending intake record, and does not perform inference, fetch URLs, publish content or change the public source registry.
- A completely isolated source copy, including new source files but excluding runtime snapshots, built successfully under macOS's network-denial sandbox. The normal public-output and SEO validators passed. It produced **322 sources, 797 score entries, 39 score collections, zero historical posts and one tracked manual event**. No private state or remote profile cache was created.
- `build_local.py` now passes explicit offline flags. Missing legacy HTML artifacts are seeded without replacing existing outputs. External calendar synchronization is marked `not_configured`; local JSON/ICS still builds normally.
- No real actor runs or new contributor tokens were used in tests. No Chumei database, identity, credentials or running service was modified.

The public proxy and restored scheduler configuration are verified. Browser visual results will be appended after the separate visual acceptance review.

## Rollback

The previous generated public site remains under `site/`; the migration does not delete it. To roll public traffic back, restore **only** the Harmonica site block and its matching active admin route to static serving:

```caddyfile
harmonica.observe.tw {
    encode zstd gzip
    root * "/Users/skyhong/Documents/Harmonica-in-Taiwan/site"
    try_files {path} {path}/ /index.html
    file_server
}
```

Use `state/Caddyfile.before-atlas` as a reference for that block and the corresponding Harmonica route in the private active-config backup. Patch the current route using its current admin API ETag; do not reload an older whole-server configuration over unrelated live changes. Keep the renewed TLS certificate. The web LaunchAgent can remain running on loopback during rollback.

To stop the new web process after traffic has been rolled back:

```bash
launchctl bootout gui/$(id -u)/tw.observe.harmonica.web
```

Keep `state/community/community.sqlite3` together with `state/community/encryption.key` when backing up or rolling back. These files contain the durable contribution authorization and accounting state; a code rollback should not replace them with an empty database.

## Final browser and UI handoff checkpoint

- Final checks: 224 Python tests and 26 Node/DOM tests passed; sitemap validation checked 396 URLs with zero errors. Offline local build and public-output validators passed.
- Real public-browser checks covered all 12 primary routes at 390×844, plus 1440×900 desktop and four-language examples. No horizontal document overflow in inspected routes. Country selection survives language changes; follows, source detail links/title/canonical, and enabled session forms were verified. Screenshots were saved by the collaborative browser tool.
- Mocked DOM tests cover contribution success/error/withdraw/cancel, source submissions, CSRF request contracts, IME and delayed session refresh preserving draft values and focus. They do not use actual contributed tokens or paid actors.
- The user explicitly approved Playwright after Computer Use could not obtain native windows. The purpose-built collaborative preview browser was subsequently discovered and successfully used against the public site.
- **The latest user direction requires UI fidelity to Chumei's deliberately designed interface. The current cream/green editorial visual design is NOT accepted as final.** Chumei was opened in a real browser and audited: desktop navigation rail, mobile bottom navigation, active stories and independently scrolling feed columns. Further style changes stopped so the next agent can implement a faithful structural adaptation rather than cosmetic overrides.
- Full continuation prompt: [next-agent-prompt-2026-09-23.md](next-agent-prompt-2026-09-23.md). Exact UI mapping: [CHUMEI_UI_HANDOFF.md](../web/CHUMEI_UI_HANDOFF.md).
