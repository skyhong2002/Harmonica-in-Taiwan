# Harmonica Observatory UI acceptance — 2026-09-23

## Latest requirements and result

The public identity is **Harmonica Observatory / 口琴觀測站**, including the navigation, localized browser titles, server-rendered SEO, OG site name/title, RSS titles and README. Japanese and Korean interfaces retain the same English brand name. Original source names and post text remain unchanged.

The user clarified during implementation that **the old cream background and green logo should guide the palette**. The final light palette therefore uses `#f6f4ed` canvas and `#244c3e` forest green, with a warm dark mode and pale green text accents. Chumei remains the reference for layout and interaction. No promotional hero, globe illustration or card-grid substitute remains.

Implemented and browser-verified:

- 260px desktop navigation at ≥1080px, 76px icon rail at 700–1079px, 54px mobile header plus fixed bottom navigation and safe-area CSS.
- More menu, four-language picker, light/dark/system appearance, live system changes, persistent theme and keyboard navigation.
- Active-only story strip with an honest empty state. Default desktop columns show worldwide posts, followed sources and upcoming events. Columns can be added/removed, independently filtered and vertically scrolled; the deck scrolls horizontally. Mobile displays one combined feed.
- Search, country, platform, source type, followed sources and story archive facets. IME composition does not replace the focused input. First-feed facets live in the URL; additional columns are saved independently.
- Dense original post rows, complete text expansion/collapse, avatars, media below text, explicitly associated events, follow, native share/clipboard fallback and original links.
- Dense sortable directory with real catalog post counts, source profiles, events, scores, subscriptions, status, contribution and reporting views.
- Existing `atlas-language`, `atlas-following` and `atlas-columns` storage keys stay compatible. `harmonica-atlas/v1` remains a machine schema identifier to avoid breaking consumers; it is not used as site branding. New appearance preference is `observatory-appearance`, with legacy theme fallback.

## Verification performed in this round

- 224 Python tests passed. All six renderer tests were rerun after the OG metadata update.
- **37 Node/DOM tests passed**. Integration covers four-language independence, routing/history/SEO, IME, following, original-text safety, civil-date/DST semantics, column persistence/scrolling, shell themes, contribution error/success/cancel/withdraw and draft/focus preservation.
- `build_local.py` completed offline. Public outputs, source coverage, legacy redirects and all 396 sitemap URLs passed validation.
- Real Chromium reference captures: Chumei at 1440×900, 800×900 and 390×844, light/dark, before implementation. Its actual light appearance was selected explicitly because its server default is dark.
- Target home: 24 combinations of three sizes × two appearances × four languages; no page errors or horizontal document overflow. A further 192 combinations covered directory/detail/events/scores/collections/feeds/about/status. These broad layout checks preceded the final palette adjustment; bounded desktop/mobile/tablet captures then verified the final cream/green palette and unchanged geometry on public HTTPS.
- Real mouse wheel and CDP touch swipes moved the horizontal deck; column vertical scrolling left other columns unchanged. Following preserved scroll position. Add/remove, independent country filters, reload, IME, locale changes and browser Back were exercised.
- Real mobile browser contribution mutations were intercepted with isolated mocks. Invalid token, success, cancel without DELETE, confirmed withdrawal, operator-inclusive capacity, and background refresh retaining both draft and focused field passed. No real token or production submission was sent.
- 85 public HTTPS checks passed with normal certificate validation: four-language pages/SEO, known-source pages, APIs, every new asset, six RSS and three ICS feeds, secure session cookie, query-preserving 308 redirects, true 404s and private-path rejection. These checks made no mutations.

Evidence on this workstation: `state/ui-acceptance-2026-09-23/` retains the final screenshots, reference captures, scripts and logs outside Git. `/tmp/harmonica-ui-acceptance/` also contains reference/target screenshots, final public screenshots, JSON acceptance reports and test logs. Key files include `public-http.json`, `target-matrix.json`, `views-check.json`, `forms-report.json`, and `public-final-{desktop,tablet,mobile}-{light,dark}.png`. Browser screenshots are local artifacts rather than generated files committed to Git.

## Deployment and preserved work

The existing `tw.observe.harmonica.web` service was restarted after Python changes and remains bound to `127.0.0.1:8330`. Public `https://harmonica.observe.tw/` continues through its existing Caddy reverse proxy. No Caddy, DNS, other website, Chumei service, credentials or scheduler settings were modified in this round. No manual paid pipeline, Apify actor or Codex inference was started for verification.

Before editing, all 58 changed/untracked source files were saved outside the checkout to `/Users/skyhong/Documents/harmonica-worktree-backup-20260923-022549/` with a compressed archive, binary Git diff and SHA256 manifest. `deploy/instagram-monitoring.md` remains untouched and excluded from commits. The previous uncommitted local-runtime/data-provider work is retained with its tests.

## Deliberate limitations

- This is a structural adaptation of Chumei with Harmonica colors, global facets and four languages. School-specific identities and account assumptions are not copied.
- No dedicated calendar route, cross-device OAuth, push notifications or fake login controls were added. Existing events and ICS subscriptions remain available.
- Contribution ownership remains the original browser cookie. Clearing it can lose management access; Apify tokens can still be revoked at Apify. Withdrawal stops new tasks rather than cancelling already-started actors.
- Active stories may be empty; historical stories remain clearly archived. Source text retains its original language and may include imperfect publicly collected website text.
- Collection frequency is an estimate from verified pool capacity. Data counts can change with the independently running normal schedule and are not hardcoded in the interface.
- Browser emulation verifies responsive layout, safe-area declarations and touch behavior; it is not a physical notched-device test.
