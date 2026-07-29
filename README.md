# POP MONSTER 官方網站

`popmonster.vip` 是泡泡怪獸的公開品牌、汽車美容商品、施工教學、車主選品與系統導流入口。正式站由本 repository 的 `main` 分支透過 GitHub Pages 發布。

## 主要入口

| 路徑 | 用途 |
|---|---|
| `index.html` | 施工任務、32 款商品與 LINE 選品 |
| `systems.html` | 泡泡怪獸店家系統館、POP CARD 公開展示與 CreatorKit 自助工具入口 |
| `go.html` | POP 免費接線台的八個既有服務入口 |
| `brand.html` | 水墨品牌館 |
| `members.html` | 官網車主會員生態 |
| `guide/` | 汽車美容施工教學 |

## 泡泡怪獸宇宙邊界

- POP MONSTER 官網負責品牌、內容、商品、購物車與車主入口。
- POP CARD 負責店家的服務菜單、預約、會員、車輛、施工與帳本。
- 兩邊只共享公開品牌語言與導流，不共用登入、Cookie、會員資料、付款狀態或資料庫。
- POP CARD 目前從 `systems.html` 導向獨立公開展示；公開展示不等於正式商家系統切換。

架構圖與決策見 [`docs/architecture/popmonster-universe.md`](docs/architecture/popmonster-universe.md)。

## 本機檢查

```bash
python3 -m unittest discover -s tests -v
for file in js/*.js; do node --check "$file"; done
python3 -m py_compile main.py setup_richmenu.py
python3 -m http.server 4173 --bind 127.0.0.1
```

開啟 `http://127.0.0.1:4173/`、`/systems.html` 與 `/go.html` 進行瀏覽器檢查。

## 部署

- `main` push 會觸發 `.github/workflows/static.yml` 並正式發布 GitHub Pages。
- Pull request 與 `codex/**` 分支只產生部署 bundle，不會自動正式發布。
- 每日 `.github/workflows/site-healthcheck.yml` 會檢查正式站關鍵頁。

正式部署前必須確認：

1. 測試、JavaScript 語法與瀏覽器 QA 通過。
2. `systems.html` 的 POP CARD 網址仍可讀取。
3. 沒有未授權素材、秘密或客戶資料。
4. 經 owner 明確核准後才合併 `main`。

## 回滾

尚未合併時直接關閉 PR。已合併時 revert 對應整合 commit，再由 GitHub Pages 完成正式站回讀。
