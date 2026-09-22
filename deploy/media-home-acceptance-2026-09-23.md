# Image-focused homepage and story publication — 2026-09-23

This correction follows the user's latest request: restore the original Google
Calendar embed, remove the manually drawn calendar and excess boxes, and show
larger real images. It supersedes the native-calendar portion of earlier reports.

## Completed changes

- The homepage keeps stories → calendar → posts. Active stories use actual
  portrait previews with source names, expiry times and original links. Empty
  data is described as not yet collected; archived stories never fill the strip.
  An open page removes a preview when its real expiry is reached.
- The original three public Google calendars appear in a compact 360 px official
  agenda iframe, with category toggles, four-language Google UI, browser timezone,
  the Google source page and ICS links. Public IDs come from an allowlisted
  catalog field derived from the existing synchronization snapshot. No local
  paths or credentials are exposed. The removed custom calendar has no remaining
  page assets or app bindings.
- Posts display images across the available row width with their original aspect
  ratio and without the previous 300/380 px height limits or image borders.
  Column boxes are removed; filters, sticky headers, independent vertical scroll,
  horizontal deck scroll and the mobile single feed remain functional.
- The two verified @nycu_harmonica stories were recovered from the already
  completed Apify run, cached and passed through the normal selected-source
  publication path into the public catalog and RSS. The video uses a preview
  frame; the original link opens the Instagram story.
- Story collection now uses 12-hour eligibility, interleaves refresh and discovery,
  and reserves sufficient result slots per target. Explicit account checks bypass
  polling delays without bypassing spending limits. Truncated, denied or unknown
  outcomes remain distinct from successfully finding no stories.

## Verified evidence

- 232 Python tests and 55 Node/DOM tests passed, including budget accounting,
  truncated story batches, cached-result ingestion, calendar metadata filtering,
  Google embed controls and actual story-expiry removal.
- 48 public Chromium combinations passed: home/post × desktop1440/tablet850/
  mobile390 × four languages × light/dark. Both real NYCU images loaded at native
  widths of at least 720 px. No document overflow or application errors occurred.
- All 24 homepage combinations loaded real Google agenda events. Category toggles
  changed only the iframe and preserved the feed DOM. The earlier sync snapshot
  saying 3/3 calendars succeeded was verified; no new external Calendar write was
  invoked for this correction.
- Public output, source-coverage and legacy-redirect validators passed; sitemap
  validation checked 400 URLs with zero errors. Both published preview URLs
  returned HTTP200 image/webp, and the source last-update time reflects the
  newly imported story.
- Actual homepage previews measured about 259×461 px on desktop and 160×284 px on
  mobile. Actual portrait post media measured about 458×814 and 362×644 px,
  preserving the 9:16 image without cropping. Wheel-based independent column and
  horizontal deck navigation were verified on the public site.
- Source-publication replay used only the cached NYCU source, disabled LLM tagging,
  and offline builders under the normal pipeline lock. Other source state and
  actor-run count were preserved. A scheduled pipeline already in progress was
  allowed to finish before the replay.

At verification on 2026-09-23 around 03:07 Asia/Taipei, the public catalog exposed
both stories. Their recorded expiry times are September 23 23:10:45 and
September 24 01:57:12 Asia/Taipei. Their disappearance after those times is correct.

Evidence files are retained locally under
`state/ui-acceptance-2026-09-23/media-home/` (ignored, not committed), including
`media-public-report.json`, actual screenshots and test logs. Existing encrypted
community state and unrelated `deploy/instagram-monitoring.md` were untouched.

## Remaining limits

The monthly operator cap stays US$4. A source being eligible after 12 hours is
not a promise that every monitored account can be scanned that often; actual
coverage remains budget-limited. Google controls its iframe appearance and
availability. Story videos link to Instagram for playback; locally cached
previews do not claim to be complete playable video archives.
