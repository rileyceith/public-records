# Publishes the app on a temporary public https URL (Cloudflare quick tunnel).
# The app is only reachable while this script and your PC are running.
# Prerequisites: backend deps installed, `npm install` in frontend\, and `winget install Cloudflare.cloudflared`.
param([int]$Port = 8190)

$root = $PSScriptRoot
$api = Join-Path $root "backend"
$web = Join-Path $root "frontend"
$python = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

# Build the frontend so the API serves everything from one origin.
Push-Location $web
npm run build
Pop-Location

# A stable secret keeps ID hashes valid between runs; it is stored outside the project.
$secretFile = Join-Path $env:LOCALAPPDATA "public-records\id-hash-key.txt"
if (-not (Test-Path $secretFile)) {
    New-Item -ItemType Directory -Force (Split-Path $secretFile) | Out-Null
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [Convert]::ToBase64String($bytes) | Set-Content $secretFile
}
$env:ID_HASH_KEY = (Get-Content $secretFile -Raw).Trim()
$env:PUBLIC_MODE = "1"
$env:STATIC_DIR = Join-Path $web "dist"

$server = Start-Process $python -WorkingDirectory $api -PassThru -NoNewWindow -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $Port, "--proxy-headers"
try {
    Start-Sleep -Seconds 4
    cloudflared tunnel --url "http://127.0.0.1:$Port"
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
