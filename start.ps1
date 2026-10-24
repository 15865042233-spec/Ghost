param([switch]$Install)
$ErrorActionPreference = 'Stop'
$ghostRoot = $PSScriptRoot
Set-Location -LiteralPath $ghostRoot
foreach ($ghostName in @('.tmp', '.cache')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ghostRoot $ghostName) | Out-Null
}
$env:TEMP = Join-Path $ghostRoot '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $ghostRoot '.cache\pip'
$env:PYTHONDONTWRITEBYTECODE = '1'
$ghostPython = Join-Path $ghostRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $ghostPython)) {
    python -m venv (Join-Path $ghostRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
    $Install = $true
}
if ($Install) {
    & $ghostPython -m pip install --no-compile -r (Join-Path $ghostRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install dependencies.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $ghostRoot '.env'))) {
    Copy-Item -LiteralPath (Join-Path $ghostRoot '.env.example') -Destination (Join-Path $ghostRoot '.env')
}
Write-Host 'Ghost: http://127.0.0.1:8000'
Write-Host 'Enter your key in the project .env file, then restart this server.'
& $ghostPython -m uvicorn ghost.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
