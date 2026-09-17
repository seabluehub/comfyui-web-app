$ErrorActionPreference = "Stop"
$appDir = $PSScriptRoot
Set-Location $appDir

if (Test-Path "C:\Python31011\python.exe") {
    $python = "C:\Python31011\python.exe"
} else {
    $python = "python.exe"
}

Write-Host "Starting ComfyUI WebApp on http://127.0.0.1:8080 ..." -ForegroundColor Cyan
& $python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
