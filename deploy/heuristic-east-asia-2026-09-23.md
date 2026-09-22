# 東亞訪客啟發式評估與修正（2026-09-23）

評估者：獨立 East Asia agent。先以真實 Chromium/Playwright 瀏覽，再閱讀原始碼；不是只做字串檢查。使用日本語／Asia/Tokyo、한국어／Asia/Seoul、繁體中文／Asia/Taipei，桌面 1440×900 與手機 390×844。保留已定案首頁三欄排版，不以本評估另行重設計。

## 任務與方法

以 Nielsen 準則評估下列任務：找到日本或韓國的演奏者、從名錄到來源原文並追蹤、回到原國家篩選、按年度與編制找樂譜、切換出版者／譜集、查看活動當地日期與多日範圍、清除歷史活动篩選。判斷介面可用性與地域資訊，不假裝能代表實際日本／韓國受試者；此為專家啟發式檢查，非真人使用者研究。

嚴重度 0–4：0 無問題、1 小問題、2 中等、3 重大、4 無法完成。

| Issue | 嚴重度／準則 | 可重現問題 | 修正 |
| --- | --- | --- | --- |
| [#3](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/3) | 2／系統狀態可見、一致性 | `/events/?lang=ja` 國家選單日本顯示來源數 21，當時只有 3 活動。 | 各頁依實際資料類型、搜尋、平台、類別、追蹤與日期篩選計算；不因介面語言改國家。國家按當地名稱排序。 |
| [#4](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/4) | 2／符合使用者語言 | 日文與韓文名錄／詳頁「網站」仍是中文。手機國家只有 CN、KR 縮寫。 | 只將通用網站操作本地化，保留來源名稱及自訂連結標題；手機使用本地國名。 |
| [#5](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/5) | 2／識別優於記憶 | 樂譜年度只列 115、114，非臺灣訪客無法直接理解年份。 | 臺灣民國年加 1911 為西元起始年，例如 115 → 2026（民國 115）；原始 query 值保留。其他國家及已是西元的年份不轉換；跨國排序比較轉換後年份。沒有推論完整學期起訖日期。 |
| [#12](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/12) | 2／狀態可見 | 過往活動 The Power of Melody 是 9/6–9/9，但卡片只列 9/6 全天。 | 全天 exclusive end 減一個 civil day，呈現完整日期範圍，單日不重複。Tokyo、Seoul、Taipei、美洲 DST 測試不偏一天。 |
| [#13](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/13) | 1／使用者控制 | 僅切換過往活動後沒有清除篩選按鈕。 | 日期篩選也顯示 reset；重設回到 upcoming。 |
| [#6](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/6) | 3／真實世界對應、防止錯誤 | 橫濱 Christmas Concert 標為臺灣／Asia/Taipei、15:00+08。 | 明確 venue/city 優先；分類不再把理由「不是臺灣活動」的臺灣字樣當作肯定地點。舊快取唯讀重新正規化後產生日本／Asia/Tokyo、15:00+09。未知地點不補臺灣。 |
| [#19](https://github.com/skyhong2002/Harmonica-in-Taiwan/issues/19) | 3／真實世界對應 | 武陵來源原文「09/25（五）～09/28（一）」「每晚 20:30～21:30」，卻只出兩個端點活動且 9/28 結束時間為22:30。 | 明確每日、具標籤的日期／時間區塊、唯一短日期範圍與公告時間才展開四場；四晚均20:30–21:30。處理全形～、週幾括號、跨午夜與 AM/PM／東亞時段。若來源未公告 end，保留日曆占位並公開 endEstimated，介面明示未公告，ICS／Google 說明標示估計。 |

另與 root、全球河道 agent 協作網站快照來源辨識：來源詳頁保留原文，但標明「網站頁面快照」與觀測時間，不把抓取日稱為貼文發布日；預設河道國家數排除此類快照，明確選網站平台時仍可查閱。

## 驗證與證據

- 修改前真實三語四頁（名錄、樂譜、譜集、活動）手機檢視與截圖：`/tmp/harmonica-heuristic/east-asia-before.json`、`east-asia-*-_source_.png` 等。
- 三語 × 桌面／手機完整任務驗收：`/tmp/harmonica-heuristic/east-asia-accept.cjs`、`east-asia-results.json`、`east-asia-after-*.png`。追蹤只改獨立瀏覽器 localStorage；沒有正式回報、token 或貢獻 mutation。
- 13 項相關 Node tests：`node --test web/tests/views.test.mjs web/tests/scores.test.mjs`。
- 51 項 calendar Python tests：`.venv/bin/python -m unittest discover -s tests -p 'test*calendar*.py'`，包含地點誤判、否定理由、未知地區、online、防止離線網路推論、四晚演出、明確結束／跨午夜／估計占位及多語時間範圍。
- 純記憶體讀取真實快照及既有快取，已驗證橫濱重分類與武陵四晚正確輸出；沒有啟動 Apify、Codex、新抓取或外部行事曆寫入。離線重建、服務重啟與外部日曆同步由 root 統一進行。

資料覆蓋限制：出版／譜集目前未標示國家的資料保留「未知」，不依中文名稱或介面語言猜臺灣。保留原文可能仍包含中文／日文／韓文，通用操作及系統狀態以介面語言顯示。自動抽取並非完整活動資料保證；本次已修正所有上述可重現問題，未推論其他未公告的時間。

獨立 reviewer 額外驗證並修正：`11:30–1:00 PM` 正確為 11:30–13:00；飯店每日早餐與其他日期／時間混合的公告不自動展開為演出；美國紐約 Japan Society 場館名稱不會把既有國家／時區改成日本。未能無歧義配對的多場公告保守留待人工確認，不由最近的時間字樣推定。

公開介面驗收：同一六組三語／尺寸旅程已改用 `https://harmonica.observe.tw/` 全數通過；活動資料修正另由重建後公開 API 與頁面再次核對。

## 重建後正式資料驗收

`node /tmp/harmonica-heuristic/east-asia-data-accept.cjs` 已實際通過正式 HTTPS API 與 Chromium 手機頁面：

- 橫濱 Christmas Concert：`countryCode=JP`、`timezone=Asia/Tokyo`、`2026-12-13T15:00:00+09:00`。日本語頁面顯示15:00、Asia/Tokyo、終了時刻は未発表；沒有把推估17:00呈現為公告時間。
- 武陵：9月25、26、27、28四場，均 `20:30:00+08:00` 至 `21:30:00+08:00`，`endEstimated=false`。韓文手機清單實際顯示四場與完整時間範圍。
- 機器可讀驗收：`/tmp/harmonica-heuristic/east-asia-data-results.json`。
- 公開頁面截圖：`east-asia-yokohama-public.png`、`east-asia-wuling-public.png`，均在上述暫存證據目錄。

Google 官方 iframe 的遠端行事曆資料由 root 另行核對與同步；以上驗收確認的是本站正式 API 及活動頁面。
