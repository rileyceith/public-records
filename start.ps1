# Main entry point: starts the API (8186) and the web app (5178) in two windows, then opens the home page.
# Prerequisites: backend\.venv with requirements installed, and `npm install` run in frontend\.
$root = $PSScriptRoot
$api = Join-Path $root "backend"
$web = Join-Path $root "frontend"
$python = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Start-Process powershell -WorkingDirectory $api -ArgumentList "-NoExit", "-Command", "& '$python' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8186"
Start-Process powershell -WorkingDirectory $web -ArgumentList "-NoExit", "-Command", "`$env:API_PROXY_TARGET='http://127.0.0.1:8186'; npm run dev -- --host 127.0.0.1 --port 5178"

Start-Sleep -Seconds 4
Start-Process "http://127.0.0.1:5178/"
