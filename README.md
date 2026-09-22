# Harmonica Observatory · 口琴觀測站

> **目前介面方向（2026-09-23 最後指示，優先於所有舊交接文件）：**還原昨天以前原版口琴觀測站的版面：頂端導覽、有效限動、Google Calendar 官方嵌入，再接三欄 masonry 貼文。首頁與 `/post/` 都隨整個頁面共同垂直捲動；響應式目標為桌面三欄、641–900px 平板最多兩欄（可用寬度不足時單欄）、≤640px 單欄。保留米色底、綠色 Logo、四語介面與全球資料功能，不再採用竹梅的左側導覽、手機固定底部導覽或各欄獨立捲動。下方描述及驗收以此方向為準；舊版竹梅移植紀錄只作歷史參考。

跨國口琴活動、公開貼文、演奏者、樂團、社團、教學與樂譜來源索引。由原「臺灣口琴觀測站」擴充，使用竹梅活動觀測站 [skyhong2002/chumei](https://github.com/skyhong2002/chumei) 的公開資料瀏覽、社群 Apify 貢獻及額度管理模式，並保留既有來源網址、資料與 RSS。

介面提供 **繁體中文、English、日本語、한국어**。網站主字標依介面語言顯示 **口琴觀測站**、**Harmonica Observatory**、**ハーモニカ観測所**、**하모니카 관측소**。依使用者後續要求，繁中／日文／韓文版在主字標下搭配 **HARMONICA OBSERVATORY** 英文副標，英文版不重複顯示。瀏覽器標題、SEO 與 OG 品牌同步本地化。介面語言與國家篩選獨立；公開貼文、名稱和來源簡介保留原文與原始連結，不偽造翻譯或活動日期。

## 本機啟動

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/build_local.py
.venv/bin/python scripts/serve.py --host 127.0.0.1 --port 8330
```

開啟 **http://localhost:8330/**。已有建置資料的機器可直接啟動 `serve.py`。

`build_local.py` 不抓新資料、不啟動付費 actor、不呼叫 AI，也不 push；它由本機 CSV 與既有抓取快照建立網站資料。全新 clone 沒有私人 runtime 快照時，先提供 CSV 來源目錄與樂譜索引，後續由 pipeline 蒐集貼文。

macOS 常駐服務：

```bash
.venv/bin/python scripts/install_local_service.py --install \
  --public-origin https://harmonica.observe.tw
```

完整的 Caddy、DNS、HTTPS、備份、排程與復原方式見 [本機部署](deploy/local-hosting.md)。DNS 由維護者切換；應用程式不修改 DNS。

## 功能

介面恢復原版口琴觀測站的頂端導覽與貼文卡片排版，保留米色底與綠色識別。桌面使用三欄 masonry 貼文，窄螢幕減為兩欄或單欄，全部隨頁面共同垂直捲動；手機導覽位於頁面頂端。外觀可選淺色、深色或跟隨系統。

首頁 `/` 恢復原站的組合順序：**大型限動預覽 → Google Calendar 官方嵌入 → masonry 貼文**，整頁可向下瀏覽。`/post/` 是提供搜尋與篩選的完整動態頁，採相同卡片與整頁捲動方式。兩者不鎖定視窗，也不建立各欄獨立捲動的 deck；不加入大型行銷 hero。

- 全球來源目錄、關鍵字搜尋與國家篩選；來源詳細頁沿用穩定 permalink。
- 公開貼文與限時動態，保留原文及原始來源按鈕。限動直接顯示內容預覽；貼文圖片依河道寬度展開，完整保留海報比例，不以小縮圖或厚重外框搶走焦點。
- 有明確日期的活動、歷史活動與線上活動，保留活動原始時區。首頁沿用原版 Google Calendar 議程嵌入，可切換臺灣、海外與線上活動日曆，並提供 Google 原頁和各 ICS 訂閱連結；介面語言與瀏覽器時區獨立。活動清單與 ICS 仍保留 civil date、exclusive 結束日與當地時區語意。
- 樂譜分為比賽指定曲與出版者／譜集索引，支援搜尋、國家、學年度、編制、組別、出版來源與排序，篩選數量依實際資料計算。原始佐證與出版／洽詢入口分開保留；索引不代表每筆有可下載的完整樂譜，也不提供未授權檔案。
- RSS／ICS 與無登入公開 JSON API。
- Apify 額度貢獻：驗證、加密保存、累計美元上限、撤回、即時容量估算。
- 貼文、活動、來源與樂譜可從情境回報連結進入 `/submit/`，預填公開網址、名稱與已知國家；未知國家不預設臺灣。舊回報網址參數仍相容，回報只進本機待審核佇列，不會立即修改公開資料。
- 真實資料更新時間與各平台狀態，缺資料或額度未驗證時不捏造數值。

首頁使用 Google 官方 iframe；公開日曆 ID 由既有同步快照的白名單欄位提供，不公開憑證或本機路徑。這台主機已有三個 Google 公開日曆正常同步；本次恢復嵌入沿用既有設定。沒有新增獨立 `/calendar/` 路由、OAuth 登入或推播。

目前貢獻管理以原瀏覽器的安全 cookie 識別，非跨裝置 OAuth 帳號。清除 cookie 後，需在 Apify 撤銷原 token。容量與更新頻率是基於額度的估算，並非送達保證。

## 架構

```text
web/                       四語介面、共用元件、各頁視圖與語系
scripts/global_catalog.py  將現有資料轉成一致的全球公開模型
scripts/serve.py           本機 HTTP 路由、公開 API、同源與 CSRF 控制
scripts/community.py       加密 Apify token、貢獻預算、瀏覽器身份與回報
scripts/apify_pool.py      跨抓取程序的額度、原子預留與帳號輪替
scripts/llm_backend.py     本機 Codex 結構化分類與呼叫上限
data/sources/              可追蹤的公開 CSV，穩定 public_id 為來源識別
site/                      產生的 JSON、RSS、ICS、舊網址頁面及快取圖片
state/                     私有 SQLite、密鑰、額度與分類快取（不進 Git）
data/feeds/                本機抓取 inbox 與候選貼文（不進 Git）
```

HTTP 請求只讀快照；不會因訪客切換語言啟動 Codex 或 Apify。抓取程序與 web 服務分離，第三方暫時失敗時，仍可瀏覽已有資料。

### 資料與網址

- `data/sources/harmonica-source-watchlist-public.csv`：公開來源主清單。
- `data/sources/harmonica-clubs-public.csv`：學生社團。
- `data/sources/harmonica-score-publications.csv`：指定曲與官方佐證。
- `data/sources/harmonica-score-sources.csv`：出版／購譜線索。
- `data/sources/harmonica-public-calendar-overrides.csv`：有公開佐證的活動校正。
- `data/sources/source-url-aliases.csv`：既有來源 URL 別名。

`public_id` 不因排序或新插入資料而重編。`country` 是主所屬國家／地區，`region` 為較細地理資訊；未知地區不可默認為臺灣。新增來源應依 `.agents/AGENTS.md` 取得官方頭像、公開自介並驗證輸出。

### 抓取與 Apify

Facebook、Instagram 貼文與限時動態共用 Harmonica 自己的 Apify 池。YouTube、網站、RSS／RSSHub 仍使用原本的公開管道，不會因介面重構而停用。預算可用量、actor 每次上限與跨程序預留共同約束支出；未確認的結果保留預留，不能藉重試超支。

```bash
# 唯讀更新額度，不會啟動 actor
.venv/bin/python scripts/apify_pool.py --refresh

# 正式抓取／建置（可能消耗設定的 Apify／Codex 額度）
.venv/bin/python scripts/run_pipeline.py
```

見 [Apify 額度池](deploy/apify-pool.md) 與 [Instagram 抓取細節](deploy/instagram-public-ingestion.md)。新本機部署不需 `--publish-pages`；[舊 Pages 流程](deploy/github-pages.md) 保留作回退參考。

### 使用現有 Codex 額度

預設採 `HARMONICA_LLM_PROVIDER=codex`，使用維護者已登入的本機 CLI 整理資料。先於 Terminal 完成 `codex login`。採只讀、停用 shell／apps／網頁工具的結構化推論，預設所有程序共用每小時 12 次上限，結果沿用既有分類快取。

- 四語 UI 是固定語系檔，沒有訪客端 AI 翻譯費用。
- `HARMONICA_LLM_PROVIDER=disabled` 可完全停用新推論。
- 額度或登入不可用時保留快取，不自動改用付費 API。
- 只有明確指定 `HARMONICA_LLM_PROVIDER=openai` 才使用原 API key 與其獨立計費。

不會向訪客提供 Codex 登入憑證或任意推論入口。官方機制見 [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)。

## 公開 API

| 路徑 | 用途 |
| --- | --- |
| `/api/v1/health` | 本機服務健康 |
| `/api/v1/catalog` | 完整全球資料快照 |
| `/api/v1/sources` | 來源目錄 |
| `/api/v1/posts` | 原文貼文 |
| `/api/v1/events` | 日期與時區明確的活動 |
| `/api/v1/scores` | 指定曲 |
| `/api/v1/community` | 社群授權容量與抓取頻率估算 |

清單 API 支援 `q`、`country`（如 `JP`、`KR`）、`limit`（1–200）、`offset`。既有 `/api/sources.json`、`latest.json`、`scores.json` 等依然可讀。所有公開資料只含公開資訊及允許的彙整狀態，不輸出 token。

RSS／ICS 維持 `/feeds/updates.xml`、`events.xml`、`posts-videos.xml`、`sources.xml`、`student-clubs.xml`、`opportunities.xml`、`public-calendar.ics`、`overseas-calendar.ics`、`online-calendar.ics`。

## 驗證

```bash
.venv/bin/python -m unittest discover -s tests
npm --prefix web ci --ignore-scripts
npm --prefix web test
.venv/bin/python scripts/validate_public_outputs.py
.venv/bin/python scripts/check_source_coverage.py
.venv/bin/python scripts/validate_legacy_redirects.py
```

只 commit 原始碼、語系、公開來源 CSV 與部署說明；`site/api`、生成 HTML、抓取快照、圖片快取、token、SQLite、密鑰與 logs 不進 Git。

MIT License · Sky Hong。Chumei 的 MIT 授權模式與實作是本次重構的參考基礎；這個服務不共用其登入、資料庫、密鑰或其他帳號額度。

品牌、原版頂端導覽、限動／Google Calendar 首頁、整頁三欄貼文、樂譜篩選與情境回報已實作。本次整合通過 232 項 Python、65 項前端測試、91 項正式 HTTPS 檢查及真實桌面／平板／手機驗收；詳見 [原版版面還原驗收](deploy/original-layout-acceptance-2026-09-23.md)。較早的 [圖片與限動修正](deploy/media-home-acceptance-2026-09-23.md)、[竹梅 UI 驗收](deploy/ui-acceptance-2026-09-23.md) 及 [前輪交接 prompt](deploy/next-agent-prompt-2026-09-23.md) 僅記錄歷史快照；最新介面方向見 [UI 接手說明](web/CHUMEI_UI_HANDOFF.md)。

最新跨國使用與啟發式評估由三個平行代理完成，18 個確認問題已修正，包含日期／時區、篩選、跨語操作、表單與無障礙；完整 249 項 Python、80 項前端測試通過。詳見 [評估與 issue 對照](deploy/heuristic-evaluation-2026-09-23.md)。
