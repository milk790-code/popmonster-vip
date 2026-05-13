# 3Q貢丸 LINE Bot 一鍵安裝腳本（Windows PowerShell）
# 使用方式：在解壓後的資料夾，右鍵 PowerShell 開啟，執行 .\install.ps1

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  3Q貢丸 LINE Bot 安裝程序 v2.0" -ForegroundColor Cyan
Write-Host "  台灣在地品牌孵化所" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 檢查 Python
Write-Host "[1/4] 檢查 Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "錯誤：找不到 Python。請先安裝 Python 3.10+ from python.org" -ForegroundColor Red
    Read-Host "按 Enter 結束"
    exit 1
}
Write-Host "  $pythonVersion 已安裝" -ForegroundColor Green
Write-Host ""

# 2. 建立虛擬環境
Write-Host "[2/4] 建立虛擬環境..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "  .venv 已存在，跳過建立" -ForegroundColor Gray
} else {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "錯誤：建立虛擬環境失敗" -ForegroundColor Red
        Read-Host "按 Enter 結束"
        exit 1
    }
    Write-Host "  虛擬環境已建立於 .venv\" -ForegroundColor Green
}
Write-Host ""

# 3. 安裝套件
Write-Host "[3/4] 安裝套件..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "錯誤：套件安裝失敗" -ForegroundColor Red
    Read-Host "按 Enter 結束"
    exit 1
}
Write-Host "  套件安裝完成" -ForegroundColor Green
Write-Host ""

# 4. 處理 .env
Write-Host "[4/4] 設定環境變數..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  .env 已存在，跳過建立" -ForegroundColor Gray
} else {
    Copy-Item ".env.template" ".env"
    Write-Host "  已從範本建立 .env" -ForegroundColor Green
}
Write-Host ""

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  安裝完成！" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步："
Write-Host "  1. 用記事本或 VSCode 開啟 .env"
Write-Host "  2. 從 LINE Developers Console 取得兩個值貼進去"
Write-Host "  3. 存檔關閉"
Write-Host "  4. 雙擊 start.ps1 啟動伺服器"
Write-Host ""
Read-Host "按 Enter 結束"
