> 後續首頁例外：使用者明確要求保留原口琴站「限動 → 活動行事曆 → 河道」的首頁；`/post/` 才是竹梅式完整河道。四語 Logo 使用各自語言單一字標。這些最新決定優先於下方移植基準；完成紀錄見 [最新驗收](../deploy/acceptance-2026-09-23.md)。

> 最新要求：品牌維持 Harmonica Observatory／口琴觀測站。使用者於本輪進一步指定保留舊版米色底與綠色 Logo；竹梅仍是結構、排版與操作的參考，配色以此最新指示為準。以下為移植前的交接基準；最新驗收請見 `deploy/ui-acceptance-2026-09-23.md`。既有 `atlas-language`、`atlas-following` 儲存鍵與 schemaVersion 保留相容，不作對外品牌。

# Frontend handoff: match Chumei faithfully

## Acceptance status

The current `web/` implementation is a verified functional baseline, **not the accepted visual design**. The user's latest instruction is to keep the interface as close as possible to their deliberately designed **Chumei Observatory** interface. The current cream/green editorial landing hero, globe illustration, statistics strip, horizontal navigation, and masonry-style cards are not that interface. Do not polish that visual direction further or claim UI parity.

Reference repository (READ ONLY): `/Users/skyhong/Projects/chumei`.
Reference production: **https://chumei.observe.tw/** (confirmed from its README, canonical URL, and live browser).
Target repository: `/Users/skyhong/Documents/Harmonica-in-Taiwan`.
Target production: https://harmonica.observe.tw/ . Target local runtime: http://127.0.0.1:8330/ .

## What the reference actually does

Live desktop and freshly reloaded mobile pages were inspected on 2026-09-23 Asia/Taipei. The reference uses the system appearance; screenshots happened to be dark mode. Match both light and dark modes, not only a black screenshot.

- Desktop ≥1080px: fixed 260px left navigation with icons and labels. Account and More actions at the bottom.
- Tablet 700–1079px: 76px icon navigation rail.
- Mobile ≤699px: 54px brand bar with filter on the left and search on the right; fixed bottom navigation with safe-area padding. More opens a menu. There is no hamburger-grid replacement for the bottom navigation.
- Homepage opens directly into content: horizontal active-story strip, then a feed deck. No promotional hero, atlas illustration, stats strip, or large section headings.
- Desktop deck locks the outer viewport, keeps each column independently vertically scrollable, and permits horizontal deck scrolling. Columns are 420px, or 490px at wide desktop, with 12px gaps. Each column has its own sticky header, filters, and remove control; users can add columns. This is functional composition, not a three-column card grid.
- Mobile default is a single combined feed with compact controls. Reload after resizing when inspecting the reference: resizing its initially desktop page without reloading can temporarily retain the wrong deck layout.
- Feed rows are Threads-like: 36px avatar, inline author/topic/time/platform, original text at ~0.95rem/1.6, six-line expansion, media beneath the text, linked event rows, and compact follow/share/original actions. Rows are separated by fine rules, not individual raised cards.
- Directory is a dense sortable row/table layout with avatars, follow, name, categories, external platforms, counts, and last update. The current Observatory source cards are a different design.
- Source detail is a constrained reading-width profile header plus compact event/post rows.
- Appearance menu offers light/dark/system. The school-specific brand-order control is not appropriate to copy into Harmonica.

Reference screenshots (local tool artifacts, not committed):

- Desktop: `/Users/skyhong/.t3/userdata/browser-artifacts/browser-screenshot-chumei-observe-tw-muczvqt9-50b155ff.png`
- Mobile fresh load, 390×844 CSS pixels: `/Users/skyhong/.t3/userdata/browser-artifacts/browser-screenshot-chumei-observe-tw-muczw5y8-ce0af978.png`

## Concrete source map

Paths below are relative to the Chumei repository unless stated otherwise. Line numbers are current reference pointers and may shift.

| Reference | Important implementation | Target adaptation |
|---|---|---|
| `site/assets/tokens.css:1` (181 lines) | NYCU LIFE token palette, spacing, type scale, light/dark/system theme | Port tokens to a dedicated `web/assets/tokens.css`, preserving the chosen Chumei appearance. Add only global/localization essentials. |
| `site/assets/site.css:36–218` | App shell, 260/76px rails, 54px mobile top bar, bottom nav, More and appearance panel | Replace `web/assets/app.js:95` navigation and current header/footer CSS. Prefer an extracted shell module. |
| `site/assets/app.js:99–179` | Appearance settings and system appearance changes | Adapt independently from the school brand-order option; persist an Observatory-scoped theme key. |
| `site/index.html:29–75` | Reference navigation, story strip, compact filter controls, SSR feed DOM | Match semantic structure with translated labels and actual Observatory routes. |
| `site/assets/site.css:446–490` | Story strip rings, count, responsive layout | Use **catalog.stories active-only**. Never populate with expired `catalog.posts` stories. Hide or honestly show empty when none active. |
| `site/assets/site.css:1260–1375` | Feed filter popover, mobile global search overlay | Replace large current filter bars on homepage/feed with matching controls; keep country separate from locale. |
| `site/assets/site.css:1380–1451` | Feed row, avatar, inline header, original text, media, event row | Replace `web/assets/views.js:21` postCard markup. Preserve escaped original content and original-source link. |
| `site/assets/site.css:1456–1655` | Independent column deck, sticky headers, filters, scrolling, add/remove | New `web/assets/river.js` recommended. Do not fake this with a static CSS grid. |
| `site/assets/app.js:700–1260` | Post rendering, saved column model, filter menus, deck navigation, touch scrolling | Extract/adapt bounded behaviors; do not copy the whole 3192-line file with school IDs/auth assumptions. |
| `site/assets/app.js:770–835` | `feedCol`, `defaultCols`, `loadCols`, `saveCols`, mobile overview | Replace school facet with country/region. Preserve a locale-independent column model and store it under `atlas-columns`. Suggested sensible defaults: worldwide updates, followed sources, upcoming events; do not map languages to countries automatically. |
| `site/assets/site.css:1033–1149`, `1628–1654`, `2015–2027` | Source directory rows, table header, sorting indicators, responsive follow controls | Replace `views.js:18` sourceCard + sources branch of app listView with row/table directory. |
| `site/assets/site.css:1159–1206` | Source profile / org page | Adapt `views.js:128` sourceDetail without losing pagination, official links, original bio, follow state, or localized shell. |
| `site/assets/site.css:709`, `903–1028`, `2028–2103` | Event rows and desktop calendar/month/day panel | Existing Observatory `/events/` data can drive rows. A real `/calendar/` route is not yet implemented and needs server routing + tests if brought into scope. |
| `scripts/auth_server.py:2188–2375` | Actual contribution page is dynamic here (not `site/contribute/index.html`) | Restyle `web/assets/community.js` around the reference layout while retaining **Observatory's own verified budget/session/consent/revocation contracts**. Do not copy Chumei account identity/quota promises that Observatory does not implement. |

## Current modules worth preserving

- `web/assets/i18n.js`: complete English / Traditional Chinese / Japanese / Korean labels with interpolation parity; detection by URL, saved preference, browser language. Country display uses `Intl.DisplayNames`. Original source content remains original.
- `web/assets/utils.js`: escaping, safe URLs, original-source links, platform/type normalization, correct civil-date and event-local timezone handling. All-day end is exclusive. Do not regress DST boundary tests.
- `web/assets/app.js`: SPA routes, independent country/language filters, search including IME composition, local followed-source state, pagination, source titles, canonical/hreflang/OG updates, browser history.
- `web/assets/community.js`: session-bound ownership, CSRF mutations, password token field, explicit total USD budget cap, consent, token clearing on failure/success, owner revoke confirmation, real pool availability, honest before/after collection estimates. Late session refresh now **updates surrounding data without replacing a typed form**.
- `web/tests/catalog_contract.test.mjs` and `web/tests/app_dom.test.mjs`: 26 passing checks including four-language parity, real catalog rendering, escaped originals, story archive flags, event-local date/DST, true pool totals, IME, follow persistence, form success/error/revocation and delayed-refresh draft preservation.

Current views: `/`, `/post/`, `/events/`, `/source/`, `/source/:slug/`, `/post/source/:id/`, `/scores/`, `/scores/sources/`, `/feeds/`, `/status/`, `/contribute/`, `/submit/`, `/about/`, `/privacy/`.

Backend API contracts are in the parent handoff and `scripts/serve.py`, `scripts/community.py`, `scripts/global_catalog.py`; use those instead of Chumei endpoints. The current source directory URL aliases and original content must remain usable.

## Suggested next implementation order

1. Take fresh reference screenshots at 1440×900 and 390×844, in light and dark; compare against target at identical dimensions. Read the reference code before changing target markup.
2. Port the design tokens and app shell first, with four-language navigation and language/appearance controls in the reference More panel. Keep all current functional routes reachable.
3. Replace homepage and `/post/` with the actual column river, including persisted country/platform/follow/type/search facets and accessible add/remove controls. Mobile uses a single readable feed. Remove current editorial hero/stats/illustration/banner composition.
4. Match post row typography, action placement, original content expansion, media, and original-source links. Add active story strip only from active catalog stories.
5. Convert directory/detail/events/scores/subscriptions/status/contribution forms to the same Chumei structural language. Use actual API capacity and ownership states; never fabricate follow counts, calendar entries, actor quotas, or collection cadence.
6. Add calendar/story dedicated routes only with complete empty/archive/timezone semantics and server integration, not placeholder navigation.
7. Re-run `npm --prefix web ci && npm --prefix web test`, backend tests in parent handoff, and real browser acceptance for all locales, both appearances, desktop/tablet/mobile, keyboard, IME, mobile safe areas, independently scrolling columns, touch/trackpad deck navigation, filtering, browser history, follow and contributions. Never expose a real token in screenshots/logs.
8. Publish via the existing local runtime + Caddy flow and verify `https://harmonica.observe.tw` publicly. Parent task owns commits/push/runtime coordination.

## Last verified baseline evidence

Before the user corrected the visual direction, the existing editorial implementation had:

- 26/26 `npm --prefix web test` checks passing.
- Browser checks of all 12 primary routes at 390×844 with no horizontal document overflow or `undefined`/`NaN` text; English/Chinese/Japanese/Korean route samples, including enabled session-backed forms.
- Desktop 1440×900 inspected; mobile menu, country JP filter (21 actual sources at that snapshot), KO→JA switch preserving country, follow persistence, source detail original links/title/canonical, and real capacity display verified.
- No application console errors in inspected screenshots.

Those checks establish functionality only. **They do not establish that the visual design satisfies the user's latest Chumei-parity requirement.**
