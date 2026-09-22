# 原版版面還原驗收（2026-09-23，最終介面指示）

此紀錄優先於今天較早的竹梅 UI 移植驗收。使用者最後要求恢復昨天以前原版口琴觀測站的排版：有效限動、日曆、三欄貼文一起隨頁面向下瀏覽。

## 已完成

- 先以真實 Chromium 載入原站 `site/index.html`、`site/assets/styles.css`、`site/assets/app.js` 作桌面／手機截圖，依原版尺寸恢復頂端導覽、綠色圖示、區段留白、限動卡及貼文卡。
- 首頁順序為有效限動 → 官方 Google Calendar agenda iframe → 完整貼文河道。沒有大型行銷 hero。
- 桌面 ≥901px 三欄 masonry，641–900px 依可用寬度最多兩欄，≤640px 單欄。貼文放入當下最短的一欄，三欄共用整頁捲動，不再鎖定高度或各自捲動。
- `/post/` 使用同一完整河道，首頁另保留限動與日曆。初始 24 篇，首次手動載入更多後可自動續載，保留手動按鈕。
- 卡片保留原文展開、來源頭像、平台、國家、活動連結、追蹤、分享、回報及原始連結。圖片全欄寬、依原比例顯示；載入失敗時仍可閱讀文字及原始來源。
- 限動只呈現有可驗證有效期限的紀錄；到期移除對應卡片，歷史資料不刪除。沒有資料時說明「尚未取得有效限動」，不聲稱來源没有發限動。
- 米色／綠色、四語單一字標、明暗／系統外觀、全球篩選、既有語言與追蹤儲存均保留。

## 實際驗證

- Node／DOM：65 項通過，涵蓋四語、IME、history、搜尋、篩選、追蹤、原文、限動到期、masonry、續載、Google Calendar 及社群表單。
- Python：232 項通過。
- 公開輸出、來源覆蓋、舊網址重導及 sitemap 驗證通過；本次 sitemap 400 URL，零錯誤。
- 正式 HTTPS：91 項 HTTP 檢查通過，包含四語路由、API、來源詳頁、所有新資產、RSS、ICS、session 與 308／404。
- Shell 真實瀏覽器：320／390／850／1440px × 四語 × 明暗，共 32 組通過；無水平溢出。
- 首頁真實瀏覽器：localhost／正式 HTTPS × 1440×900／390×844。當時兩則竹韻口琴社有效限動的照片、頭像、來源及期限吻合 catalog；Google 日曆實際載入活動，三個日曆勾選與 ICS 下載正常。
- 實際河道：1440px 三欄、850px 兩欄、390px 單欄；滾輪捲動整頁，圖片正常，搜尋、篩選、展開、追蹤及 24→48→72 篇續載正常。
- 社群表單使用瀏覽器攔截的隔離 mock，成功／錯誤／取消撤回／確認撤回及背景更新保留草稿與焦點均通過，沒有送出真實 mutation。

本機驗收證據位於 `/tmp/harmonica-ui-acceptance/`：`legacy-reference.json`、`legacy-*.png`、`restored-shell-report.json`、`restored-current-home.json`、`restored-current-*.png`、`public-restored-http.json`、`node-restored.log`、`python-restored.log`、`forms-report.json`。

## 範圍與限制

- Google Calendar 內容與內部外觀由 Google 官方 iframe 提供；網站明暗設定不控制其內部樣式。
- 限動數量與內容會隨真實到期及抓取更新改變。這次只還原介面，沒有為驗收重跑付費抓取或增加 Apify 預算。
- 原有社群身份仍為瀏覽器 cookie；本次沒有新增 OAuth 或推播，也沒有相關假按鈕。
- 使用既有 localhost 服務及 Caddy，沒有另開正式服務、發布 GitHub Pages 或改動竹梅。
- 未修改、刪除或提交 `deploy/instagram-monitoring.md`。
