<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="site/assets/logo-github-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="site/assets/logo.svg">
    <img src="site/assets/logo.svg" alt="臺灣口琴觀測站 Logo" width="360">
  </picture>
</p>

# 臺灣口琴觀測站

`harmonica.observe.tw` 是一個獨立的臺灣口琴公開資訊索引站。它整理公開可查的口琴活動、社團、樂團、演奏者、教學單位、場館、補助與比賽資訊，並把整理後的資料輸出成靜態網站、JSON API 與 RSS。

## 目前輸出

- 網站首頁：`https://harmonica.observe.tw/`
- 公開貼文：`https://harmonica.observe.tw/post/`
- 公開來源：`https://harmonica.observe.tw/source/`
- 比賽指定曲：`https://harmonica.observe.tw/scores/`
- 口琴譜源：`https://harmonica.observe.tw/scores/sources/`
- 資料回報：`https://harmonica.observe.tw/submit/`
- RSS 分類入口：`https://harmonica.observe.tw/feeds/`
- 公開 API：`https://harmonica.observe.tw/api/*.json`

首頁與 `/post/` 的「最新」河道由公開社群、YouTube、RSS/RSSHub 與整理後的候選更新資料產生；公開來源索引則由 `data/sources/` 下的公開 CSV 加上自動產生的標籤與更新狀態組成。

## 專案結構

```text
.
├── data/
│   ├── sources/                 # 人工維護的公開來源 CSV
│   └── feeds/                   # 本機 runtime feed inbox、候選更新與快取（不進 git）
├── scripts/                     # 資料建置、社群抓取、RSS/API 產生工具
├── site/                        # 本機靜態站輸出根目錄；main 只追蹤手寫/source assets
│   ├── api/                     # 產生出的公開 JSON API（不進 git）
│   ├── assets/                  # CSS、JS、logo、favicon；feed 圖片與頭貼快取不進 git
│   ├── data/                    # 前端讀取的 JS data bundle（不進 git）
│   ├── directory/               # 舊公開來源路徑轉址（產生輸出，不進 main）
│   ├── post/                    # 公開貼文河道（產生輸出，不進 main）
│   ├── source/                  # 公開來源索引、來源詳情與 facet 頁（產生輸出，不進 main）
│   ├── feeds/                   # RSS、分類頁與分類 JSON（不進 git）
│   ├── score-sources/           # 舊口琴譜源路徑轉址（產生輸出，不進 main）
│   ├── scores/                  # 學生音樂比賽指定曲索引頁；sources/ 為口琴譜源索引頁（產生輸出，不進 main）
│   └── submit/                  # 資料回報頁（產生輸出，不進 main）
├── state/                       # 本機執行狀態與分類快取（不進 git）
├── .github/ISSUE_TEMPLATE/      # 公開資料回報 issue form
└── README.md
```

重要檔案：

- `data/sources/harmonica-source-watchlist-public.csv`：公開來源主清單，包含演奏者、團體、教學、場館、活動平台等。
- `data/sources/harmonica-clubs-public.csv`：公開學生社團資料。
- `data/sources/harmonica-score-publications.csv`：全國學生音樂比賽口琴指定曲與出版、購譜線索，含官方歷年指定曲目 XLS 與近年 PDF 補充線索。
- `data/sources/harmonica-score-sources.csv`：指定曲以外的口琴譜源 metadata、購買／洽詢方式與公開佐證連結；不收錄譜檔或曲譜內容。
- `data/sources/harmonica-public-calendars.csv`：臺灣實體、國外實體與線上活動三個公開 Google Calendar 的 metadata。
- `data/sources/harmonica-public-calendar-overrides.csv`：公開貼文抽取不足時的日曆事件人工校正；只記 metadata、公開佐證連結與活動資訊。
- `scripts/build_public_calendar_events.py`：使用 `gpt-5.4-mini` 與規則驗證，從公開貼文抽出活動日期、場地與時區，分流為臺灣實體、國外實體與線上活動 JSON/ICS。
- `scripts/sync_google_calendar_events.py`：用本機 `.env` / Hermes Google Workspace OAuth 設定同步三類事件到各自的公開 Google Calendar。
- `data/feeds/social_sources.json`：由 CSV 轉出的公開社群監看來源設定。
- `data/feeds/social_feed_inbox.jsonl`：YouTube / Facebook 抓取工具正規化後的公開貼文 inbox。
- `data/feeds/social_candidates.jsonl`：watchdog 篩選後的公開候選更新。
- `site/assets/styles.css`、`site/assets/app.js` 與品牌圖檔：網站前端 source assets，保留在 `main`。
- `site/data/site-data.js`：前端資料索引使用的產生資料包，不保留在 `main`。
- `site/api/*.json`：給外部工具或 Bamboo Hermes 讀取的公開 API，不保留在 `main`。
- `site/feeds/*.xml` 與 `site/feeds/*.json`：公開 RSS 與對應 JSON，不保留在 `main`。

## 建置與發佈

這個 repo 的 `main` source of truth 是 `data/sources/*.csv`、`scripts/` 與網站 source assets。抓取狀態、LLM/cache、公開 API、RSS、前端 data bundle、SEO HTML、sitemap、feed 圖片與頭貼都是執行 pipeline 後產生的 publish output，預設不納入 `main`。

完整靜態網站發布內容由 `gh-pages` 分支保存。本機對應 worktree 通常是：

```bash
/Users/skyhong/Documents/Harmonica-in-Taiwan-gh-pages
```

本機或發佈機器要產生完整靜態站台時，執行：

```bash
python3 scripts/run_pipeline.py
```

`run_pipeline.py` 會依序重建監看來源、抓取公開更新、產生 `site/data`、`site/api`、`site/feeds`、`site/status`、SEO HTML 與圖片快取，最後執行：

```bash
python3 scripts/validate_public_outputs.py
```

驗證會檢查 generated JSON/JS 是否可解析、`status.json` 的公開目錄與監看來源數是否和 `sources.json` 一致，以及所有公開輸出引用的 feed 圖片/來源頭貼是否存在。驗證失敗時不要發佈該次輸出。

要發布正式站時使用：

```bash
python3 scripts/run_pipeline.py --publish-pages
```

或在已產生 `site/` 後執行：

```bash
python3 scripts/publish_github_pages.py
```

這會把 generated `site/` 快照複製到 `gh-pages` worktree 並推送發布分支；不要把 generated HTML/API/RSS 產物 commit 回 `main`。

SEO 舊網址轉址由 `data/sources/source-url-aliases.csv` 維護。Pipeline 會執行 `scripts/generate_cloudflare_redirects.py`，產生 `site/redirects/cloudflare-bulk-redirects.csv` 給 Cloudflare Bulk Redirects 匯入；這些 edge artifacts 屬於 publish output，不進 `main`。

公開來源 CSV 維護規則：

- `public_id` 是公開來源頁的穩定 ID，會決定 `/source/<id>-<slug>/` 的 canonical URL；不要因為 CSV 排序或插入列而重編既有 ID。
- 每一筆會輸出的來源都要填 `country`，放主所屬國家或地區，例如 `臺灣`、`日本`、`香港`。
- `region` 保留較細的地理或交流脈絡，例如 `臺灣/新竹`、`日本`、`香港/國際`。
- 公開 tag 必須是一格一個元素；不要把 `演出/音樂會`、`半音階、複音` 或 `教學 + 維修` 這類複合 tag 放成單一 tag。建置流程會自動拆分並在輸出前驗證。

## 資料怎麼蒐集與整理

觀測站以公開資料為主。資料來源大致分成三類：

- 人工整理的公開來源清單：包含學校社團、演奏者、樂團、教學單位、場館、活動平台與公開社群入口。
- 公開社群與影音更新：包含 Facebook 公開頁面、Instagram、YouTube 頻道，以及透過 RSSHub 轉出的少量 X/Threads 公開來源。
- 公開活動與機會資訊：包含演出、講座、工作坊、成發、徵件、比賽、補助與報名資訊。

資料整理流程會先把公開來源統一成目錄項目，再把近期公開更新整理成首頁河道、分類 RSS 與 JSON API。社群更新會依照來源、平台、時間、關鍵字與語意標籤分類，讓同一批資料可以同時服務網站瀏覽、RSS 訂閱與外部工具讀取。

站上顯示的資訊不是完整名冊，也不是官方認證資料庫；它更接近一個公開訊號索引。如果你發現社團、演奏者、活動或公開來源有缺漏、錯誤或失效連結，歡迎發 GitHub issue 回報。回報時最有幫助的是官方網站、公開社群頁、公開貼文、活動頁或其他公開來源。

## 公開 RSS

主要 RSS：

- `https://harmonica.observe.tw/feeds/updates.xml`：公開更新總河道。
- `https://harmonica.observe.tw/feeds/events.xml`：公開口琴活動線索。
- `https://harmonica.observe.tw/feeds/public-calendar.ics`：臺灣口琴實體活動的可訂閱 ICS。
- `https://harmonica.observe.tw/feeds/overseas-calendar.ics`：國外口琴實體活動的可訂閱 ICS。
- `https://harmonica.observe.tw/feeds/online-calendar.ics`：線上口琴活動的可訂閱 ICS。
- `https://harmonica.observe.tw/feeds/posts-videos.xml`：口琴相關貼文與影片發布。
- `https://harmonica.observe.tw/feeds/student-clubs.xml`：口琴學生社團動態。
- `https://harmonica.observe.tw/feeds/opportunities.xml`：補助、徵件、甄選、比賽與報名資訊。
- `https://harmonica.observe.tw/feeds/sources.xml`：公開來源索引。

對應 JSON 也會產生在 `site/feeds/*.json`。

## 公開 API

外部工具與 Bamboo Hermes 應優先讀公開 JSON API，不要直接抓網站 HTML：

- `https://harmonica.observe.tw/api/latest.json`
- `https://harmonica.observe.tw/api/catalog.json`
- `https://harmonica.observe.tw/api/events.json`
- `https://harmonica.observe.tw/api/public-calendar-events.json`
- `https://harmonica.observe.tw/api/overseas-calendar-events.json`
- `https://harmonica.observe.tw/api/online-calendar-events.json`
- `https://harmonica.observe.tw/api/public-calendar-sync.json`
- `https://harmonica.observe.tw/api/posts-videos.json`
- `https://harmonica.observe.tw/api/student-clubs.json`
- `https://harmonica.observe.tw/api/opportunities.json`
- `https://harmonica.observe.tw/api/sources.json`
- `https://harmonica.observe.tw/api/source/<public_id>.json`：單一公開來源的輕量貼文 feed，例如竹韻為 `/api/source/198.json`。
- `https://harmonica.observe.tw/api/scores.json`
- `https://harmonica.observe.tw/api/score-sources.json`

若遠端用 `curl` 驗證 API 時遇到 403，可以加類瀏覽器 User-Agent：

```bash
curl -A 'Mozilla/5.0' https://harmonica.observe.tw/api/sources.json
```

## 資料回報

公開新增、修正、失效連結與來源更新應從網站回報頁開始。回報頁直接嵌入由陽明交大竹韻口琴社帳號維護的 Google 表單，不需要 GitHub 帳號：

```text
https://harmonica.observe.tw/submit/
```

請只填公開可查資料，不要放私人電話、私人信箱、未公開群組連結、會員資料或憑證。表單題目與發布設定由 `scripts/configure_submission_form.py` 維護；OAuth token 留在本機 Hermes profile，不進 repo。

## License

MIT. See `LICENSE`.
