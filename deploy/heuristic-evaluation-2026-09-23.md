# 跨國使用與啟發式評估（2026-09-23）

本輪依使用者要求，以三個平行代理分別評估東亞使用者、全球英語內容與時間資訊、首次使用及無障礙操作；主代理整合、交叉審查資料解析、建立 GitHub issues、修正並驗收。這是實際瀏覽器任務檢查與程式檢查，沒有冒稱完成當地居民訪談。

## 評估範圍

- 語言／地區：繁體中文（臺灣）、日本語（日本）、한국어（韓國）、English（美國／英國），另外檢查德國等非英語來源的原文保留。
- 時區：Asia/Taipei、Asia/Tokyo、Asia/Seoul、America/Los_Angeles、Europe/London；語言不決定國家或時間帶。
- 裝置與操作：320／390px 手機、1440px 桌機、明暗模式、200% 文字放大、鍵盤、IME、歷史返回、空結果、媒體／API 失敗。
- 任務：閱讀原文與限動、尋找所在國家來源、追蹤、查看近期／過往活動及日曆、尋找樂譜、回報來源、提供與撤回額度。
- 依 Nielsen 十項原則檢查狀態可見、真實世界對應、控制與撤回、一致性、錯誤預防、辨識、效率、精簡呈現、錯誤復原、協助說明。嚴重度 S1 為輕微，S2 為中度，S3 為重大，S4 為阻斷。

## 確認問題與修正追蹤

| Issue | 嚴重度 | 問題 | 狀態 |
| --- | --- | --- | --- |
| [#3](https://github.com/skyhong2002/harmonica-observatory/issues/3) | S2 | 國家篩選數量與目前瀏覽內容不符 | 已修正並驗收 |
| [#4](https://github.com/skyhong2002/harmonica-observatory/issues/4) | S2 | 日文與韓文版的來源操作殘留中文「網站」 | 已修正並驗收 |
| [#5](https://github.com/skyhong2002/harmonica-observatory/issues/5) | S2 | 民國樂譜年度對國際訪客缺乏西元對照 | 已修正並驗收 |
| [#6](https://github.com/skyhong2002/harmonica-observatory/issues/6) | S3 | 日本橫濱活動被歸為臺灣及臺北時區 | 已修正並驗收 |
| [#7](https://github.com/skyhong2002/harmonica-observatory/issues/7) | S2 | Google 日曆外開連結沒有保留已選日曆 | 已修正並驗收 |
| [#8](https://github.com/skyhong2002/harmonica-observatory/issues/8) | S2 | 動態舊年份與連結活動時間資訊不足 | 已修正並驗收 |
| [#9](https://github.com/skyhong2002/harmonica-observatory/issues/9) | S2 | 追蹤河道空白時未引導追蹤來源 | 已修正並驗收 |
| [#10](https://github.com/skyhong2002/harmonica-observatory/issues/10) | S2 | 限動媒體載入失敗時缺乏可靠替代回饋 | 已修正並驗收 |
| [#11](https://github.com/skyhong2002/harmonica-observatory/issues/11) | S3 | 網站抓取時間被當作貼文發布時間且整頁導覽進入最新動態 | 已修正並驗收 |
| [#12](https://github.com/skyhong2002/harmonica-observatory/issues/12) | S2 | 多日活動未顯示結束日，容易誤判行程 | 已修正並驗收 |
| [#13](https://github.com/skyhong2002/harmonica-observatory/issues/13) | S1 | 只篩選過往活動時沒有清除篩選入口 | 已修正並驗收 |
| [#14](https://github.com/skyhong2002/harmonica-observatory/issues/14) | S3 | 表單回應遺失焦點且缺乏可辨識的持續結果 | 已修正並驗收 |
| [#15](https://github.com/skyhong2002/harmonica-observatory/issues/15) | S2 | 撤回確認沒有可及名稱與具體紀錄且缺少防重送 | 已修正並驗收 |
| [#16](https://github.com/skyhong2002/harmonica-observatory/issues/16) | S2 | 外國訪客難以發現藏在本地語言更多選單內的語言切換 | 已修正並驗收 |
| [#17](https://github.com/skyhong2002/harmonica-observatory/issues/17) | S3 | 切換介面語言會清除貢獻或提供來源表單草稿 | 已修正並驗收 |
| [#18](https://github.com/skyhong2002/harmonica-observatory/issues/18) | S2 | 放大文字時英日文 Logo 與導覽遭截斷 | 已修正並驗收 |
| [#19](https://github.com/skyhong2002/harmonica-observatory/issues/19) | S3 | 明確一小時的活動被加成兩小時，連續四晚日期也遺漏 | 已修正並驗收 |

| [#20](https://github.com/skyhong2002/harmonica-observatory/issues/20) | S3 | 全天改為定時活動時 Google 日曆同步失敗 | 已修正並驗收 |

## 修正細節與證據

- [東亞任務與活動資料](heuristic-east-asia-2026-09-23.md)
- [全球河道、時間與日曆](heuristic-global-feed-2026-09-23.md)
- [無障礙、表單與操作回饋](heuristic-accessibility-2026-09-23.md)
- 表單草稿只在語言切換的同步記憶體中搬移；不把 token 存進 URL、localStorage 或 sessionStorage。送出期間避免語言切換建立另一份可重送表單。
- 網站整頁觀測保留原文與原始連結，標記為 website_snapshot，發布時間未知；觀測時間明確另列。預設最新動態排除整頁快照，Web 篩選及來源頁仍可閱讀。RSS 不再把觀測時間標成 pubDate。
- 活動修正以明確城市、主辦原文日期與時間為依據；不把理由中的「不是臺灣」當成臺灣地點，不讓 Japan Society 場館字串蓋過 New York，不把住宿早餐日期／時間當演出。
- 日期僅在明確活動【日期】與【時間】、每日／每晚、短區間可辨認時展開。含糊資料保守處理；未公告結束時間時，網站及日曆明示結束時間為估計，避免使用者誤認公告。

## 整合驗收

18 個確認問題均已修正並驗收。嚴重度分布：S3 六項、S2 十一項、S1 一項。

- 完整 Python：249 項通過；完整 Node／DOM：80 項通過。
- 離線重建成功；公開輸出、來源覆蓋、舊路由重導及 sitemap 驗證通過，401 個 sitemap URL 零錯誤。
- 正式 HTTPS 91 項 HTTP 檢查通過。
- 東亞三語 × 桌機／手機共 6 組實際任務；US／UK 各 12 項河道／日曆檢查；四語快照、限動媒體失敗替代、四語表單、24 組導覽／明暗與四語 200% 文字放大均通過。
- Google Calendar 使用本站環境憑證，僅處理本站三份公開日曆，修正日期、時區與估計結束時間说明；保留無關事件。最後 read-back 比對所有公開來源事件日期、時區、標題與說明，並確認移至海外的活動不再重複出現在臺灣日曆。
- 全天／定時转换 PATCH 明確清除互斥欄位；同步實測與雙向回歸均通過。依據 [Google Calendar PATCH 文件](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch)。

整合證據位於 `/tmp/harmonica-heuristic/`：`python.log`、`node.log`、`http.log`、`build.log`、各代理 JSON／截圖及 `google-calendar-applied.json`。

## 執行限制與保護

所有表單 mutation 驗收使用瀏覽器 mock，沒有提交真 token 或回報。沒有為驗收新增 Apify／Codex 抓取、提高額度、改 DNS、改竹梅服務或發布 GitHub Pages。离線重建使用既有 pipeline lock，等待正常排程完成。保護原先未追蹤的 `deploy/instagram-monitoring.md`。

第三方日曆與原始媒體可能受 Google／來源站網路或登入限制；已提供原始連結及活動清單替代入口。沒有日期／國家佐證的來源維持未知。評估涵蓋上述任務與情境，不宣稱任何網站從此不存在其他問題。
