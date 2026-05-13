# 3Q貢丸 LINE Bot 啟動腳本
# 使用方式：雙擊執行，或 PowerShell 跑 .\start.ps1

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  3Q貢丸 LINE Bot v2.0 啟動中..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Host "錯誤：找不到 .env，請先跑 install.ps1" -ForegroundColor Red
    Read-Host "按 Enter 結束"
    exit 1
}

$envContent = Get-Content ".env" -Raw
if ($envContent -match "LINE_CHANNEL_SECRET=\s*$" -or $envContent -match "LINE_CHANNEL_ACCESS_TOKEN=\s*$") {
    Write-Host "錯誤：.env 還有空白值" -ForegroundColor Red
    Read-Host "按 Enter 結束"
    exit 1
}

& .\.venv\Scripts\Activate.ps1

Write-Host "伺服器啟動於 port 8001" -ForegroundColor Green
Write-Host "另開 PowerShell 執行 ngrok http 8001" -ForegroundColor Yellow
Write-Host "停止：按 Ctrl+C" -ForegroundColor Gray
Write-Host ""

uvicorn main:app --host 0.0.0.0 --port 8001
