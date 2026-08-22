$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "Project: $ProjectRoot"
Write-Host "Python:  $Python"
Write-Host "ComfyUI health:"
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 5 | ConvertTo-Json -Depth 4
} catch {
    Write-Warning $_.Exception.Message
}
Write-Host "Gateway health:"
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5 | ConvertTo-Json -Depth 4
} catch {
    Write-Warning $_.Exception.Message
}
