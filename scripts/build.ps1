[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Build Python was not found: $python"
}

Push-Location $projectRoot
try {
    & $python -m PyInstaller --clean --noconfirm packaging\PCPanelAgent.spec
    if ($LASTEXITCODE -ne 0) { throw "PCPanelAgent build failed." }

    & $python -m PyInstaller --clean --noconfirm packaging\PCPanelTelemetryService.spec
    if ($LASTEXITCODE -ne 0) { throw "PCPanelTelemetryService build failed." }
}
finally {
    Pop-Location
}

Write-Host "Artifacts:"
Write-Host "  $(Join-Path $projectRoot 'dist\PCPanelAgent\PCPanelAgent.exe')"
Write-Host "  $(Join-Path $projectRoot 'dist\PCPanelTelemetryService\PCPanelTelemetryService.exe')"
