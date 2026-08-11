[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$compiler = Join-Path $projectRoot ".tools\InnoSetup\ISCC.exe"
$installerScript = Join-Path $projectRoot "packaging\PCPanel.iss"

if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw "Inno Setup 6.7.3 compiler was not found: $compiler"
}

foreach ($artifact in @(
    "dist\PCPanelAgent\PCPanelAgent.exe",
    "dist\PCPanelTelemetryService\PCPanelTelemetryService.exe"
)) {
    $path = Join-Path $projectRoot $artifact
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Packaged artifact was not found: $path"
    }
}

& $compiler $installerScript
if ($LASTEXITCODE -ne 0) { throw "PCPanel installer build failed." }

Write-Host "Installer: $(Join-Path $projectRoot 'dist\installer\PCPanelSetup.exe')"
