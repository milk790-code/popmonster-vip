# SKILLS.md — Claude Code 技能速查表

> 找不到 skill 名稱、每次都要貼全名？這份就是給你查的。
>
> 三段：① Claude Code 內建 skills（10 個，已固定）② 你自訂 skills（Windows `%USERPROFILE%\.claude\skills\`，待你貼 `dir` 結果補完）③ popmonster 專屬 slash commands（連到 OPS.md）

---

## ① Claude Code 內建 skills（10 個）

在任何 session 都能直接叫，不需要安裝。

| 名稱 | 一句話用途 | 觸發時機 | 範例叫法 |
|---|---|---|---|
| `init` | 初始化新專案的 `CLAUDE.md` | 剛 clone 一個 repo / 從零起手新專案 | `/init` |
| `review` | 審核 pull request | 開了 PR 想先自我審查 | `/review` |
| `security-review` | 對當前 branch 做安全審查 | 推 PR 前 / 動到敏感邏輯後 | `/security-review` |
| `simplify` | 找可重用 / 可精簡的改動 | 寫完 feature 想瘦身 | `/simplify` |
| `claude-api` | Claude API / SDK 開發協助、prompt caching、模型升級 | 編 anthropic SDK 程式時自動觸發 | 直接寫 SDK code |
| `update-config` | 改 `settings.json`、hooks、權限、env vars | 想「以後每次 X 就 Y」/ 加 hook / 改 allowlist | `/update-config` |
| `keybindings-help` | 改 `~/.claude/keybindings.json` | 想改快捷鍵 / 加 chord | `/keybindings-help` |
| `fewer-permission-prompts` | 掃過往 transcript 加 allowlist 到 `.claude/settings.json` | 被權限提示煩到 | `/fewer-permission-prompts` |
| `session-start-hook` | 建 SessionStart hook（給 Claude Code on the web）| 想在 web session 預裝測試/lint 相依 | `/session-start-hook` |
| `loop` | 重複跑 prompt / slash command（如 `/loop 5m /foo`）| 定期 polling / babysit PR / 每 N 分鐘檢查一次 | `/loop 10m /review` |

**用法**：對話中打 `/<名字>`，例如 `/review`、`/simplify`。也可以直接描述需求（例如「請幫我審查這個 PR」），Claude 會自動觸發對應 skill。

---

## ② 你自訂 skills（Windows 機本機，38 個）— **待補**

OPS.md 提過你那邊有 38 個 skills、27 commands、19 agents，超出人類記憶量。要補進這張表，請在 Windows 上跑：

```cmd
dir %USERPROFILE%\.claude\skills /B
dir %USERPROFILE%\.claude\commands /B
dir %USERPROFILE%\.claude\agents /B
```

把三段輸出貼回 Claude Code 對話，我會：

1. 逐一讀 `~/.claude/skills/<名字>/SKILL.md` 的 frontmatter `description` 欄
2. 依「立即可用 / 一年沒叫過 / 重複功能」分類
3. 補完下方表格 + 標紅旗建議刪除的項目

<!-- TODO: 貼 dir 結果後我來補

預計表格欄位：

| 名稱 | 用途（從 SKILL.md description 抓）| 最近一次叫過？ | 建議 |
|---|---|---|---|
| (待補) | | | |

-->

### 為什麼 ② 區待補？

我（這個 session）跑在 Linux sandbox，**看不到你 Windows 的 `%USERPROFILE%`**。每次新 session 我都只看得到 system reminder 列出的「目前 session 可用」清單 — 那不是全部，是 Claude Code 替你過濾過的（依資料夾掃描結果）。你 Windows 那 38 個檔案在 sandbox 不存在，所以非靠你貼出來不可。

---

## ③ popmonster 專屬 slash commands（3 個）

詳見 [OPS.md](./OPS.md) 對應段落。

| 名稱 | 一句話用途 | 詳細 |
|---|---|---|
| `/popmonster-deploy` | 官網維護（verify、add-product、update-link、sync-sitemap）| [OPS.md L20–L30](./OPS.md) |
| `/browser` | 蝦皮後台輔助（list-products、caption、new-product、update-price、order-batch）| [OPS.md L32–L42](./OPS.md) |
| `/theme-factory` | 黑金主題視覺工廠（audit、sync-tokens、regenerate-product、brand-pack）| [OPS.md L44–L52](./OPS.md) |

預設行為：**永遠 dry-run，等使用者確認，不自動 push**。

---

## 常見錯誤排查

| 症狀 | 原因 / 修法 |
|---|---|
| 打 `/xxx` 顯示 "Unknown command" | 名字打錯，或那個 skill 不在 system reminder 列出的清單裡（可能只在某些工作目錄才載入）|
| 我（Claude）說「skill X 不可用」 | 該 skill 不在當前 session 的 available-skills 列。如果你確定有，重啟 Claude Code 試試 |
| 同一個 skill 有 plugin 版和本機版 | 用 `plugin:skill` 形式叫 plugin 版，或直接叫名字優先本機版 |

---

## 更新規則

- 內建 ① 區改動極少（Claude Code 版本升級時才會變）— 升 CLI 版本後我重掃並更新這份
- ② 區由你貼 `dir` 結果觸發更新
- ③ 區若新增 popmonster 專屬指令，從 `.claude/commands/` 自動掃出來加上
