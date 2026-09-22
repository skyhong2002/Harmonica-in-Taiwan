# Current UI direction — 2026-09-23 final override

**最新使用者要求：還原昨天以前原版口琴觀測站的視覺與版面。此節優先於下方所有竹梅移植說明。**

- 頂部導覽後續重做為首頁、動態、活動、來源名錄、樂譜；「更多」將參與／訂閱、語言／外觀、狀態／關於／隱私分組，語言和三種外觀直接在同一層操作。
- 全站恢復原版頂端導覽；桌面頂欄、手機頁面頂端三欄導覽選單，不再使用竹梅左側欄或固定底部導覽。
- 首頁順序為 **有效限動內容預覽 → 既有 Google Calendar 官方 iframe → masonry 貼文卡片**；不加入大型行銷 hero 或手刻月曆。
- 首頁與 `/post/` 的貼文全部隨整個頁面共同垂直捲動。響應式目標：>900px 三欄、641–900px 平板最多兩欄（可用寬度不足時單欄）、≤640px 單欄；不是可增刪或各自捲動的竹梅 deck。
- 保留舊版米色底與綠色識別，以及繁中／英文／日文／韓文和全球資料。主語言字標依序為「口琴觀測站」、「Harmonica Observatory」、「ハーモニカ観測所」、「하모니카 관측소」。後續使用者要求加入英文識別：非英文版主標下顯示 HARMONICA OBSERVATORY，英文版不重複。介面語言與國家篩選獨立。
- 既有搜尋、IME、追蹤、原文展開、原始來源、Google 日曆／ICS、Apify 貢獻、情境回報與瀏覽器歷史功能須保留；不共用竹梅服務、帳號或憑證。

目前原版參考為此 repository 的 `site/index.html`、`site/assets/styles.css` 和 `site/assets/favicon-20260623.svg`。實作入口是 `web/assets/shell.js`、`legacy-layout.css`、`observatory-mark.svg`、`home.js`、`home.css`、`google-calendar.js`、`timeline.js` 和 `timeline.css`。Google 日曆 ID 取自公開 catalog 設定，不能帶入私人憑證；限動僅使用仍有效的 `catalog.stories`。

原版實際瀏覽器參考截圖位於 `/tmp/harmonica-ui-acceptance/legacy-{desktop,mobile}-{top,stories,feed}.png`。最新完整驗收由 [原版版面還原驗收](../deploy/original-layout-acceptance-2026-09-23.md) 記錄；下方舊測試數字只證明各歷史快照，不代表現在版面已通過最新驗收。

---

## Historical Chumei migration notes — superseded visual direction

以下內容保留為歷史來源對照。其中「最新」、「current」、「must match Chumei」、側欄、獨立捲動河道和實作順序，均是當時的指示，**不得覆蓋上方最終原版還原要求**。資料與安全契約仍可參考。

> 最新視覺修正：使用者否決手刻月曆與大量框線，首頁改回既有 Google Calendar 官方嵌入；限動使用大型內容預覽，貼文圖片全寬保留比例。以下原生月曆描述均屬歷史方向。

> 後續首頁例外：使用者明確要求保留原口琴站「限動 → 活動行事曆 → 河道」的首頁；`/post/` 才是竹梅式完整河道。四語 Logo 使用各自語言單一字標。這些最新決定優先於下方移植基準；完成紀錄見 [最新驗收](../deploy/acceptance-2026-09-23.md)。

> 最新要求：品牌維持 Harmonica Observatory／口琴觀測站。使用者於本輪進一步指定保留舊版米色底與綠色 Logo；竹梅仍是結構、排版與操作的參考，配色以此最新指示為準。以下為移植前的交接基準；最新驗收請見 `deploy/ui-acceptance-2026-09-23.md`。既有 `atlas-language`、`atlas-following` 儲存鍵與 schemaVersion 保留相容，不作對外品牌。

# Historical frontend handoff: match Chumei faithfully

## Historical acceptance status

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
