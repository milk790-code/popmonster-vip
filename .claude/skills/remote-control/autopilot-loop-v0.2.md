# Oh My Night Crew v0.2 自動循環設計

本檔案存放 v0.2 版本的核心新增能力規格，包含自動循環啟動、通關密碼停止機制、中斷自動續跑保護。v0.1 環境（Claude.ai Project）無法實現本檔案描述的能力，需要在本機環境部署 Anthropic API 加 cron 排程才能啟用。

本檔案為週末實作的設計參考，不是今晚實戰需要的內容。

## 為何需要 v0.2

v0.1 在 Claude.ai Project 環境的根本限制是 Claude 為回合制執行，不會在背景持續運轉。一次觸發只能推進一輪，工作清單做完或上下文預算耗盡就自然結束，不會自動重啟。

陳學誼的真實需求是「即使中斷，最多中斷一小段時間，下一個小時又再次啟動並持續運行」「每個月固定重啟一次」「直到本人回到電腦輸入通關密碼才停止」。這需要超出 Claude.ai 環境能力的基礎設施。

v0.2 的核心新增為三件事。自動循環啟動的 cron 排程設計。通關密碼停止機制。中斷自動續跑的保護邏輯。

## 部署前提條件

第一個前提是 Anthropic API 金鑰。陳學誼需要在 Anthropic Console 申請個人 API key，存放於本機環境變數 `ANTHROPIC_API_KEY`。

第二個前提是本機環境支援 cron。macOS 與 Linux 原生支援。Windows 環境需改用 Task Scheduler 對應實作。

第三個前提是本機已安裝 Anthropic Python SDK 或 Node SDK。`pip install anthropic` 或 `npm install @anthropic-ai/sdk`。

第四個前提是 Oh My Night Crew 的 SKILL.md、takeover-content.md、safeguards.md 三份檔案存放於本機 `~/.claude/skills/oh-my-night-crew/` 目錄。

## 自動循環啟動邏輯

每 5 小時自動觸發一次夜班，每月 1 號晚上 10 點額外觸發一次保底啟動。

cron 設定範例。

```cron
# 每 5 小時整點觸發
0 */5 * * * /Users/[username]/.claude/skills/oh-my-night-crew/scripts/launcher.sh >> ~/takeover-cron.log 2>&1

# 每月 1 號晚上 10 點保底啟動
0 22 1 * * /Users/[username]/.claude/skills/oh-my-night-crew/scripts/launcher.sh --monthly >> ~/takeover-cron.log 2>&1
```

設定方式為 `crontab -e` 加入上述兩行，存檔離開即生效。

## launcher.sh 核心腳本

每次 cron 觸發執行此腳本。腳本第一步檢查通關密碼狀態，密碼有效則停止本輪。否則呼叫 Claude API 啟動夜班並接收完整輸出寫入報告。

```bash
#!/bin/bash
# Oh My Night Crew Launcher v0.2
# 由 cron 每 5 小時觸發一次

set -e

# 路徑設定
SKILL_DIR="$HOME/.claude/skills/oh-my-night-crew"
STOP_TOKEN_FILE="$HOME/.takeover-stop-token"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 通關密碼檢查
EXPECTED_PASSWORD="（陳學誼指定的通關密碼，啟用時填入）"

if [ -f "$STOP_TOKEN_FILE" ]; then
    ACTUAL_PASSWORD=$(cat "$STOP_TOKEN_FILE")
    if [ "$ACTUAL_PASSWORD" = "$EXPECTED_PASSWORD" ]; then
        echo "[$TIMESTAMP] 偵測到通關密碼，本輪夜班不啟動，等待手動觸發"
        exit 0
    fi
fi

# 環境檢查
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "[$TIMESTAMP] 錯誤：ANTHROPIC_API_KEY 未設定"
    exit 1
fi

# 心跳檔記錄啟動
echo "[$TIMESTAMP] Launcher 啟動，準備呼叫夜班" >> "$HOME/takeover-heartbeat.log"

# 呼叫 Claude API 啟動夜班
python3 "$SKILL_DIR/scripts/run_night_crew.py" \
    --skill-file "$SKILL_DIR/SKILL.md" \
    --content-file "$SKILL_DIR/takeover-content.md" \
    --safeguards-file "$SKILL_DIR/safeguards.md" \
    --output-dir "$HOME/Desktop" \
    --max-duration 14400 \
    --trigger-mode "${1:-cron}"

# 結束
echo "[$TIMESTAMP] Launcher 結束" >> "$HOME/takeover-heartbeat.log"
```

## run_night_crew.py 核心執行腳本

實際呼叫 Claude API 跑夜班並寫報告的 Python 腳本。完整版會包含工具調用迴圈讓 Claude 可以執行 bash 與檔案編輯。

骨架範例。

```python
#!/usr/bin/env python3
"""Oh My Night Crew 執行腳本 v0.2"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

import anthropic

def load_skill_files(skill_path, content_path, safeguards_path):
    """讀取三份技能檔案"""
    skill = Path(skill_path).read_text(encoding='utf-8')
    content = Path(content_path).read_text(encoding='utf-8')
    safeguards = Path(safeguards_path).read_text(encoding='utf-8')
    return skill, content, safeguards

def build_system_prompt(skill, content, safeguards):
    """組合完整 system prompt"""
    return f"""你是 Oh My Night Crew 夜班代理，現在被 cron 排程自動觸發。

{skill}

---

## 個人化偏好

{content}

---

## 可逆性保險規範

{safeguards}

---

現在執行模式為「自動循環觸發」，使用者陳學誼可能在睡覺或離線。
請依 SKILL.md 規範執行完整夜班流程，最後生成桌面報告。
"""

def run_night_shift(args):
    """執行一輪夜班"""
    skill, content, safeguards = load_skill_files(
        args.skill_file,
        args.content_file,
        args.safeguards_file,
    )
    
    system_prompt = build_system_prompt(skill, content, safeguards)
    
    client = anthropic.Anthropic()
    
    # 啟動夜班的初始 user message
    initial_message = f"夜班啟動。觸發模式：{args.trigger_mode}。時間：{datetime.now().isoformat()}。"
    
    # 進入工具調用迴圈
    # 完整版實作需要 bash tool、file tool、browser MCP 等工具的迴圈處理
    # 此處為骨架，實作時參考 Anthropic Computer Use 或 Claude Code 的 agent loop 模式
    
    # ...實際 agent loop 邏輯...
    
    # 結束後生成報告
    report_path = Path(args.output_dir) / f"夜班報告-{datetime.now().strftime('%Y-%m-%d-%H%M')}.md"
    # 寫入報告
    # ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-file', required=True)
    parser.add_argument('--content-file', required=True)
    parser.add_argument('--safeguards-file', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--max-duration', type=int, default=14400)
    parser.add_argument('--trigger-mode', default='cron')
    args = parser.parse_args()
    
    run_night_shift(args)

if __name__ == '__main__':
    main()
```

實作此腳本時建議參考 Anthropic 官方 Computer Use 範例與 Claude Code 開源實作，已有成熟的 agent loop 模式可借鑑。週末實作時可一起開發。

## 通關密碼機制

通關密碼機制讓陳學誼可以隨時停止自動循環，避免技能在不該運轉的時段持續推進。

啟用方式。陳學誼回到電腦執行單行指令寫入通關密碼。

```bash
echo "你的通關密碼字串" > ~/.takeover-stop-token
```

下一次 cron 觸發時，launcher.sh 偵測到密碼正確，本輪不啟動，但 cron 排程本身不停止。這意味著如果陳學誼之後刪除 stop-token 檔案（`rm ~/.takeover-stop-token`），下一次 cron 觸發又會恢復自動循環。

通關密碼的設計選擇。建議使用對陳學誼有意義且不容易誤輸入的字串，例如某個品牌口號的片段、某個重要日期的格式、或某個專屬代碼。避免使用簡單字串如 stop、pause 避免誤觸。

通關密碼存放於 launcher.sh 內的 EXPECTED_PASSWORD 變數，部署時填入。為了避免 launcher.sh 本身洩漏密碼，建議使用環境變數方式或外部設定檔。

進階版本可改為。

```bash
# launcher.sh 改用環境變數
EXPECTED_PASSWORD="${TAKEOVER_PASSWORD}"

# 環境變數設定於 ~/.zshrc 或 ~/.bashrc
export TAKEOVER_PASSWORD="實際密碼字串"
```

## 中斷自動續跑保護

cron 本身就具備這層保護，因為它每次觸發都是獨立執行，前一次中斷不會影響後一次。但需要額外處理「上一次未完成的工作」與「新一輪啟動」之間的銜接。

設計邏輯。每次 launcher.sh 啟動時，先檢查 `~/takeover-log/` 目錄是否有「未完成」狀態的工作項目，如有則優先續跑。

```bash
# launcher.sh 增加續跑檢查
PENDING_LOG="$HOME/takeover-log/pending.json"
if [ -f "$PENDING_LOG" ]; then
    echo "[$TIMESTAMP] 偵測到上輪未完成工作，本輪優先續跑"
    # 將 pending.json 內容傳給 run_night_crew.py 作為續跑起點
    python3 "$SKILL_DIR/scripts/run_night_crew.py" --resume "$PENDING_LOG" ...
else
    # 全新一輪
    python3 "$SKILL_DIR/scripts/run_night_crew.py" ...
fi
```

run_night_crew.py 在執行過程中持續更新 `~/takeover-log/pending.json`，記錄當前進行到哪個項目。執行完成則清除此檔案，未完成（被 cron 強制中斷或其他原因）則保留。

## 部署檢查清單

週末實作時依以下順序執行。

申請 Anthropic API key 並設定環境變數。

安裝 anthropic Python SDK。

建立 `~/.claude/skills/oh-my-night-crew/scripts/` 目錄，存放 launcher.sh 與 run_night_crew.py。

實作 run_night_crew.py 的 agent loop，可參考 Anthropic Computer Use 範例。

設定通關密碼，填入 launcher.sh 或環境變數。

測試 launcher.sh 手動執行，確認可正確呼叫 Claude API 並寫入桌面報告。

設定 crontab 排程。

第一晚實測，觀察 cron 是否如預期每 5 小時觸發、通關密碼是否能停止。

依實測回饋調整。

## 版本紀錄

v0.2 設計版，2026-05-16。待週末完整實作。
