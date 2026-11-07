# CanineSense AI — first-time setup (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Get-PythonExe {
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  $py312 = "$env:LOCALAPPDATA\Python\pythoncore-3.12-64\python.exe"
  if (Test-Path $py312) { return $py312 }
  $pyAny = Get-ChildItem "$env:LOCALAPPDATA\Python\pythoncore-*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($pyAny) { return $pyAny.FullName }
  if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
  throw "Python 3.11+ not found. Install with: winget install Python.Python.3.12"
}

$py = Get-PythonExe
Write-Host "Using Python: $py"

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example — set CANINESENSE_SECRET_KEY before production."
}

& $py -m pip install -r backend/requirements.txt
& $py scripts/init_db.py
Set-Location frontend
npm install
npm run build
Set-Location ..
Write-Host "Setup complete. Use scripts/dev.ps1 to start the website."
