# Navigation, forms, accessibility heuristic evaluation — 2026-09-23

Scope: a first-time English, Traditional Chinese, Japanese, or Korean reader finding content and preferences, contributing Apify capacity, submitting a source, recovering from errors, and withdrawing authorization. This is an expert heuristic review with actual browser task execution, not interviews with people from those countries or a claim of full WCAG certification.

Browsers: Playwright Chromium, both `http://localhost:8330` and `https://harmonica.observe.tw`; widths 320, 390 and 1440, height 844; all four languages; light and dark; keyboard disclosure/escape/cancel/focus; an additional 320px/200% text-size reflow check. Every POST/DELETE and private session response in these checks was browser-mocked with fictitious values. No real contribution, report, Apify call, or credential was submitted.

## Findings and fixes

| ID | Severity (0–4) | Nielsen heuristic | Reproduction / effect | Fix and evidence |
| --- | --- | --- | --- | --- |
| [A11Y-1](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/14) | 3 | Visibility of system status; help users recognize/recover from errors | On `/contribute/?lang=en`, send a mocked `invalid_token` response. Focus lands on BODY, the emptied token is not marked invalid or associated with the message. On successful source submission focus also lands on BODY and only a temporary toast confirms acceptance. This loses the place of keyboard users and makes completion uncertain. | Field-specific failures focus the field and attach `aria-invalid` plus the persistent error description. General failures focus the status. Success remains in the form status with focus. Forms expose `aria-busy`, prevent duplicate requests, and keep the language selector disabled until the request completes. Background refresh cannot enable a pending submit. Four-language browser failure→correction→success checks and regression tests pass. |
| [A11Y-2](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/15) | 2 | Error prevention; user control and freedom; consistency | Open withdrawal from a mocked owned contribution. The native dialog lacks an accessible name/description and does not identify the contribution. The withdrawal control has no explicit pending protection. | The dialog title names the contribution with escaped text, and `aria-labelledby`/`aria-describedby` describe the action and existing-run caveat. Cancel/Escape remains the default, sends no request, and returns focus. Pending withdrawals are deduplicated; completion/error is persistent and focused. Browser and DOM tests verify exactly one DELETE, cancellation, and the updated revoked row. |
| [A11Y-3](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/16) | 2 | Recognition rather than recall; match with the real world | A shared URL can open in an unfamiliar script. The language selector is inside a text-only localized More disclosure, giving an English/Japanese/Korean newcomer no recognizable visual language cue. | A visible globe marks More; its title and accessible label list `English / 繁體中文 / 日本語 / 한국어`. The existing grouped menu and four native language names remain intact. Four-language/three-width/two-theme checks verify no clipping and Escape focus restoration. |
| [A11Y-4](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/18) | 2 | Flexibility and efficiency; consistency; minimalist design | At 320px with 200% text, English and Japanese brand names use `white-space:nowrap` and overflow horizontally. Primary links become crowded. | Localized brand and controls reflow, the navigation adapts its column minimum to text size, and appearance controls wrap. All four languages pass document-width checks at 200% and remain legible. The localized main name plus English signature remains unchanged. |

## Checks with no new finding

- The normal-size More menu stays inside all tested viewports; its content scrolls within the viewport. Clicking outside, moving focus outside, or pressing Escape closes it; Escape returns to the summary.
- Four languages remain independent of the source-country field. New source forms default to unknown country; the displayed country list is localized.
- Contribution terms explain cumulative USD budget, optional participation, possible provider charges, browser-based ownership, and cancellation limits. The minimum and maximum budget and explicit consent remain enforced by the existing inputs/API.
- Token fields remain password inputs, are cleared after a failed request, and are never added to storage by this change. Other user entries remain editable for recovery.
- Four-language form success/error/revocation feedback is translated using existing dictionaries.
- Native skip link, primary route indication, brand navigation, actual source submission status, and privacy links remain present.

## Validation artifacts

- `/tmp/harmonica-heuristic/accessibility-before.cjs` and `accessibility-before.json`: baseline browser reproduction and 24 navigation combinations.
- `/tmp/harmonica-heuristic/accessibility-dialog-before.png`: baseline unnamed withdrawal dialog.
- `/tmp/harmonica-heuristic/accessibility-after.cjs`: repeatable local/public browser mock acceptance.
- `/tmp/harmonica-heuristic/accessibility-after.json`: local results (24 language/viewport/theme combinations, four enlarged-text checks, plus scripted form workflows).
- `/tmp/harmonica-heuristic/accessibility-public-after.json`: public HTTPS results for the same tasks.
- `/tmp/harmonica-heuristic/accessibility-{en,zh-Hant,ja,ko}-200.png`: final enlarged-text screenshots.
- `/tmp/harmonica-heuristic/accessibility-drafts.cjs`: public HTTPS also confirms [#17](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/17): all form fields survive each of four locale changes; a pending request blocks native and programmatic locale changes; exactly one mocked POST; token absent from local/session storage.
- `node --test web/tests/shell.test.mjs web/tests/reporting.test.mjs`: 7 passed, including duplicate submission protection, field error focus, persistent completion, and named/cancelable withdrawal.

Limitations: screen-reader software and real assistive-technology users were not available; accessible naming/focus and keyboard behavior were verified in Chromium and DOM tests. Provider transactions were intentionally mocked, so these checks validate the website's interaction behavior rather than availability or billing behavior of Apify. The parent evaluation tracks other views, data accuracy, and translation issues separately.
