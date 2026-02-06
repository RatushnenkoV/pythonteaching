# Python Trainer - Start Script
Set-Location $PSScriptRoot

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host ""
Write-Host "Starting server..." -ForegroundColor Green
Write-Host "Open http://localhost:5000 in browser" -ForegroundColor Yellow
Write-Host ""

python app.py
