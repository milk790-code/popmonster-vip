# `/partner` 視覺審核證據

狀態：`BLOCKED_BROWSER_INSTANCE_UNAVAILABLE`

2026-07-18 本輪已啟動本機預覽並確認以下路徑回應 HTTP 200：

- `/partner.html?preview=1&src=direct`
- `/partner-demo.html`
- `/go.html`

使用者指定的 in-app Browser 在本輪回報沒有可用實例。依 Browser 技能，不以其他瀏覽器或來源碼推測冒充視覺驗收，因此本資料夾目前不放假截圖。

## Browser 恢復後必拍

1. `01-partner-mobile-390x844.png`：Hero、CTA、五席票與 90 天主線。
2. `02-partner-tablet-768x1024.png`：適配篩選與 90 天工位軌道。
3. `03-partner-desktop-1440x1000.png`：Hero 與費用／證據牆。
4. `04-partner-demo-mobile-390x844.png`：永久 Demo 標示與禁跳轉。
5. `05-partner-demo-desktop-1440x1000.png`：設定物件渲染與 preview lock。
6. `06-go-regression-390x844.png`、`07-go-regression-1440x1000.png`：既有 `/go` 回歸。

## 每個尺寸必驗

- `document.documentElement.scrollWidth <= window.innerWidth`
- 鍵盤可到達兩個 CTA、適配按鈕、證據來源、FAQ、分享與隱私選擇。
- `:focus-visible` 清楚可見。
- `prefers-reduced-motion: reduce` 下無必要動態。
- Console error 為 0；資源 404 為 0。
- Demo 點擊外部 CTA 後 URL 不變、事件為 0。

完成後把實測值與檔名回填 `docs/partner-v1.1/review-report.md`，才可移除此阻擋。
