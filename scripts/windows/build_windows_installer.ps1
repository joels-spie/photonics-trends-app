param(
  [switch]$SkipDependencyInstall,
  [switch]$RequireCodeSigning,
  [switch]$CorporateArtifacts
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path "$PSScriptRoot/../..").Path

Write-Host "Building Photonics Trends Windows installer..." -ForegroundColor Cyan
Set-Location $repoRoot

if (-not $SkipDependencyInstall) {
  Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
  python -m pip install -r backend/requirements.txt
  python -m pip install pyinstaller

  Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
  Push-Location frontend
  npm install
  Pop-Location
}

Write-Host "Freezing backend into exe..." -ForegroundColor Cyan
pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name photonics-backend `
  --collect-all uvicorn `
  --add-data "config;config" `
  backend/run_server.py

Write-Host "Building Electron NSIS installer..." -ForegroundColor Cyan
Push-Location frontend
$packageScript = "package:win"
if ($CorporateArtifacts -and -not $RequireCodeSigning) {
  throw "Corporate artifacts require signing. Re-run with -RequireCodeSigning."
}
if ($CorporateArtifacts -and $RequireCodeSigning) {
  $packageScript = "package:win:corp"
} elseif ($RequireCodeSigning) {
  $packageScript = "package:win:signed"
}

npm run $packageScript
Pop-Location

Write-Host "Done. Installer output:" -ForegroundColor Green
Write-Host "$repoRoot/frontend/release/Photonics-Trends-Setup-0.1.0.exe"
