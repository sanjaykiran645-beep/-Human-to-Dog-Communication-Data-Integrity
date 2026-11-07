# Start API (8000) and website (5173) in two new PowerShell windows.
$root = Split-Path -Parent $PSScriptRoot
$py = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  $py312 = "$env:LOCALAPPDATA\Python\pythoncore-3.12-64\python.exe"
  if (Test-Path $py312) { $py = $py312 }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; & '$py' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev -- --host 127.0.0.1 --port 5173"
Write-Host "Backend http://127.0.0.1:8000  |  Website http://127.0.0.1:5173"
