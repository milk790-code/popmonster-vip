# Oh My Night Crew 可逆性保險

本檔案存放 Oh My Night Crew 技能執行時所依賴的可逆性保險基礎設施，包含快照機制、回收策略、還原指令、批次保護的具體腳本與規範。所有腳本以 bash 為主，假設執行環境為 macOS 或 Linux。Windows 環境的對應實作待 v0.2 補充。

## 基礎設施初始化

技能首次執行時自動建立以下目錄與檔案。後續執行如發現缺失自動補建。

```bash
mkdir -p ~/.takeover-snapshots
mkdir -p ~/takeover-log
mkdir -p ~/.takeover-trash
touch ~/takeover-heartbeat.log

# 確保 trash 指令存在，若無則安裝
if ! command -v trash &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS 安裝 trash
        brew install trash || echo "請手動安裝 trash 指令: brew install trash"
    fi
fi
```

## 第一層：預刪除快照機制

任何刪除動作執行前，Claude 先建立完整快照。本機檔案直接複製到快照目錄，雲端檔案先下載後快照，資料庫項目先匯出後快照。

本機檔案快照範例。

```bash
# 變數設定
SNAPSHOT_DIR="$HOME/.takeover-snapshots/$(date +%Y-%m-%d-%H%M%S)"
mkdir -p "$SNAPSHOT_DIR"

# 快照指定檔案
TARGET_FILE="/path/to/file.txt"
RELATIVE_PATH="${TARGET_FILE#$HOME/}"  # 保留相對路徑結構
SNAPSHOT_PATH="$SNAPSHOT_DIR/$RELATIVE_PATH"

mkdir -p "$(dirname "$SNAPSHOT_PATH")"
cp -p "$TARGET_FILE" "$SNAPSHOT_PATH"

# 紀錄到快照清單
echo "$(date -Iseconds) | $TARGET_FILE -> $SNAPSHOT_PATH | 刪除原因待補" >> "$SNAPSHOT_DIR/manifest.log"
```

雲端檔案快照範例（Google Drive 為例）。

```bash
# 使用 gdrive CLI 或 rclone 先下載再快照
# 此處假設已配置 rclone 連接 Google Drive 為 remote 名 gdrive
SNAPSHOT_DIR="$HOME/.takeover-snapshots/$(date +%Y-%m-%d-%H%M%S)/gdrive"
mkdir -p "$SNAPSHOT_DIR"

# 下載指定雲端檔案到本機快照
CLOUD_PATH="待刪除資料夾/檔案.docx"
rclone copy "gdrive:$CLOUD_PATH" "$SNAPSHOT_DIR/" --progress

# 紀錄
echo "$(date -Iseconds) | gdrive:$CLOUD_PATH -> $SNAPSHOT_DIR/" >> "$SNAPSHOT_DIR/../manifest.log"
```

快照保留期限為 90 天。技能每次啟動時自動清理超過 90 天的快照目錄。

```bash
find "$HOME/.takeover-snapshots" -maxdepth 1 -type d -mtime +90 -exec rm -rf {} \;
```

## 第二層：分層回收策略

本機刪除一律用 `trash` 指令而非 `rm`。

```bash
# 錯誤：永久刪除無法還原
# rm /path/to/file.txt

# 正確：送回收站可還原
trash /path/to/file.txt
```

雲端刪除依賴各服務本身的回收站機制，技能不主動清空雲端回收站。

Google Drive 預設回收站保留 30 天。Gmail 垃圾郵件保留 30 天。Google Photos 已刪除項目保留 60 天。技能不執行「永久刪除」「清空垃圾桶」類動作。

資料庫修改採軟刪除標記。若項目為資料庫紀錄，技能修改 `deleted_at` 欄位而非執行 DELETE。

```sql
-- 錯誤：永久刪除
-- DELETE FROM products WHERE id = 123;

-- 正確：軟刪除
UPDATE products SET deleted_at = NOW(), deleted_by = 'oh-my-night-crew' WHERE id = 123;
```

## 第三層：顯著刪除清單

技能每次執行的所有刪除動作記錄到當次快照目錄的 manifest.log，並彙整生成顯著刪除清單寫入夜班報告置頂。

清單格式範本。

```markdown
## 本次刪除清單

整體還原指令： `bash ~/Desktop/restore-20260516-235900.sh`

| 序號 | 檔案 | 原位置 | 刪除原因 | 快照路徑 | 一鍵還原 |
|------|------|--------|----------|----------|----------|
| 1 | screenshot_001.png | ~/Desktop | 三個月前截圖無使用紀錄 | ~/.takeover-snapshots/2026-05-16-235900/Desktop/screenshot_001.png | `cp ~/.takeover-snapshots/.../screenshot_001.png ~/Desktop/` |
| 2 | 草稿_v1.docx | ~/Documents/草稿 | 已有 v3 取代 v1 | ~/.takeover-snapshots/.../草稿/草稿_v1.docx | `cp ~/.takeover-snapshots/.../草稿_v1.docx ~/Documents/草稿/` |

如要還原全部，執行： `bash ~/Desktop/restore-20260516-235900.sh`
如要還原單項，從上方表格複製對應指令執行即可。
```

## 第四層：一鍵全還原腳本

技能在本輪執行結束生成 `~/Desktop/restore-YYYYMMDD-HHMMSS.sh`，包含本輪所有刪除動作的還原指令。

腳本模板。

```bash
#!/bin/bash
# Oh My Night Crew 本輪刪除動作還原腳本
# 生成時間：2026-05-16 23:59:00
# 對應快照目錄：~/.takeover-snapshots/2026-05-16-235900

set -e
echo "開始還原本輪刪除動作..."

SNAPSHOT_DIR="$HOME/.takeover-snapshots/2026-05-16-235900"

if [ ! -d "$SNAPSHOT_DIR" ]; then
    echo "錯誤：快照目錄不存在，無法還原"
    exit 1
fi

# 還原每個檔案到原位置
while IFS='|' read -r timestamp source target rest; do
    source=$(echo "$source" | xargs)
    target=$(echo "$target" | xargs)
    
    if [ -f "$target" ]; then
        echo "還原 $source <- $target"
        mkdir -p "$(dirname "$source")"
        cp -p "$target" "$source"
    fi
done < "$SNAPSHOT_DIR/manifest.log"

echo "還原完成。原快照目錄保留在 $SNAPSHOT_DIR，供後續查閱。"
echo "如確認還原無誤，可手動清理快照：rm -rf $SNAPSHOT_DIR"
```

## 批次刪除保護

任何單次執行中累積刪除超過 10 個檔案的批次動作自動降級為「生成刪除清單草稿等審」，不真正執行。

降級後產出格式範本。

```markdown
## 紅燈：批次刪除待審

偵測到本輪將執行的刪除動作累積超過 10 個檔案，已自動降級為待審草稿，未真正執行。

待刪除清單：
1. ~/Downloads/截圖_001.png （3 個月前無使用紀錄）
2. ~/Downloads/截圖_002.png （3 個月前無使用紀錄）
... [完整 47 項清單] ...

判斷依據：
- 所有檔案都位於 Downloads 資料夾
- 所有檔案都超過 90 天未存取
- 所有檔案類型均為截圖類

建議動作：
- 全部執行：回覆「執行批次刪除-序號 #1」
- 部分執行：回覆「執行 1-20」或「執行除了 #15、#32 以外」
- 全部取消：回覆「取消批次刪除-序號 #1」
- 重新評估：回覆「重新評估批次刪除」
```

## 修改前快照（不限刪除動作）

任何修改現有檔案的動作，執行前先建立修改前快照，存放於同一個本輪快照目錄。

```bash
# 變數設定
SNAPSHOT_DIR="$HOME/.takeover-snapshots/$(date +%Y-%m-%d-%H%M%S)"
mkdir -p "$SNAPSHOT_DIR/modifications"

# 修改前快照
TARGET_FILE="/path/to/file.txt"
RELATIVE_PATH="${TARGET_FILE#$HOME/}"
PRE_MOD_PATH="$SNAPSHOT_DIR/modifications/$RELATIVE_PATH"

mkdir -p "$(dirname "$PRE_MOD_PATH")"
cp -p "$TARGET_FILE" "$PRE_MOD_PATH"

# 紀錄修改原因
echo "$(date -Iseconds) | $TARGET_FILE | 修改原因：商品名稱優化" >> "$SNAPSHOT_DIR/modifications.log"

# 執行修改
# ... 實際修改動作 ...
```

修改類動作同樣納入一鍵還原腳本，但腳本中分為「還原刪除」與「還原修改」兩個區塊，供用戶選擇性執行。

## 敏感路徑檢查

任何動作執行前，先檢查目標路徑是否在敏感路徑清單中。

```bash
# 敏感路徑清單從 takeover-content.md 讀取
SENSITIVE_PATHS=(
    "$HOME/Documents/個人財務"
    "$HOME/Documents/合約"
    "$HOME/Documents/私人"
    "$HOME/Library/Keychains"
    "$HOME/.ssh"
    "$HOME/.aws"
    "$HOME/.gcp"
    "$HOME/.config/gh"
)

# 檢查函式
is_sensitive() {
    local target="$1"
    for sensitive in "${SENSITIVE_PATHS[@]}"; do
        if [[ "$target" == "$sensitive"* ]]; then
            return 0  # 是敏感路徑
        fi
    done
    
    # 檔名包含敏感關鍵字
    local basename=$(basename "$target")
    for keyword in password secret token api_key credentials 私密 勿動; do
        if [[ "$basename" == *"$keyword"* ]]; then
            return 0
        fi
    done
    
    return 1  # 非敏感
}

# 使用範例
if is_sensitive "$TARGET_FILE"; then
    echo "目標為敏感路徑，跳過操作"
    SENSITIVE_COUNT=$((SENSITIVE_COUNT + 1))
else
    # 執行操作
    :
fi
```

## 憑證與密碼掃描

任何檔案讀取前快速掃描是否含有 secret pattern。

```bash
# secret pattern 偵測函式
contains_secret() {
    local file="$1"
    # 跳過大檔案避免效能問題
    if [ $(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null) -gt 1048576 ]; then
        return 1
    fi
    
    # 常見 secret pattern
    grep -qE "(api[_-]?key|secret[_-]?key|access[_-]?token|password|client[_-]?secret|private[_-]?key|aws[_-]?access|bearer)" "$file" 2>/dev/null
}

# 使用範例
if contains_secret "$TARGET_FILE"; then
    echo "目標含有可能的密鑰，標記為高敏感，只整理不複製不分享"
    # 不將檔案內容寫入報告
fi
```

## 雲端同步衝突防護

修改雲端檔案前先檢查上次同步時間。

```bash
# 以 Google Drive 為例
last_sync=$(rclone lsjson "gdrive:$CLOUD_PATH" 2>/dev/null | jq -r '.[0].ModTime')
last_sync_epoch=$(date -d "$last_sync" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${last_sync%.*}" +%s 2>/dev/null)
now_epoch=$(date +%s)
diff_minutes=$(( (now_epoch - last_sync_epoch) / 60 ))

if [ $diff_minutes -lt 5 ]; then
    echo "目標檔案最近 5 分鐘內被修改，暫停操作避免同步衝突"
    DEFERRED_COUNT=$((DEFERRED_COUNT + 1))
else
    # 執行修改
    :
fi
```

## 心跳記錄

技能每完成主要里程碑時更新心跳檔。

```bash
HEARTBEAT_LOG="$HOME/takeover-heartbeat.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') | $MILESTONE | 進度 $CURRENT/$TOTAL | 移往下一項" >> "$HEARTBEAT_LOG"
```

心跳檔 append-only，不刪除舊紀錄。用戶可隨時 `tail -20 ~/takeover-heartbeat.log` 查看最近 20 條心跳。

## 工作日誌寫入

每個項目開始與結束時寫入對應日誌。

```bash
LOG_DIR="$HOME/takeover-log/$(date +%Y-%m-%d)"
mkdir -p "$LOG_DIR"

PROJECT_LOG="$LOG_DIR/${PROJECT_NAME}.md"

# 項目開始
cat >> "$PROJECT_LOG" << EOF
## $(date '+%H:%M:%S') - 開始

看到了什麼：$WHAT_I_SAW
判斷：$WHAT_I_JUDGED
計畫：$WHAT_I_PLAN

EOF

# 項目結束
cat >> "$PROJECT_LOG" << EOF
## $(date '+%H:%M:%S') - 結束

做了什麼：$WHAT_I_DID
發現什麼：$WHAT_I_FOUND
下一輪建議：$NEXT_SUGGESTION

EOF
```

## 報告生成模板

技能執行結束時生成桌面報告。完整報告檔案範例參見 SKILL.md 的「報告格式範本」區段。

報告檔案命名規則。

```bash
REPORT_FILE="$HOME/Desktop/夜班報告-$(date +%Y-%m-%d).md"
# 若同一天已有報告，加時間戳區分
if [ -f "$REPORT_FILE" ]; then
    REPORT_FILE="$HOME/Desktop/夜班報告-$(date +%Y-%m-%d-%H%M).md"
fi
```

## 緊急停止處理

收到緊急停止口令後，技能立即進入收尾。

```bash
# 中止當前操作（已開始但未完成的動作完成清理）
# 完成快照備份
# 生成報告
# 不再推進新工作

trap 'emergency_cleanup' SIGINT SIGTERM

emergency_cleanup() {
    echo "收到緊急停止信號，進入收尾..."
    # 寫入當前進度到日誌
    # 完成已開始的快照
    # 生成簡化版報告
    generate_report --emergency
    exit 0
}
```

## 版本紀錄

v0.1 初版，2026-05-16。

待 v0.2 補充項目：Windows 環境對應實作、雲端服務認證自動化檢查、批次操作的 transaction-like 機制、報告國際化支援。
