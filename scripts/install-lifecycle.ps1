[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $InstallRoot,

    [switch] $EnableServiceAutoStart,

    [switch] $EnableAgentAutoStart,

    [switch] $StartServiceNow
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$resolvedRoot = (Resolve-Path -LiteralPath $InstallRoot).Path
$serviceExe = Join-Path $resolvedRoot "PCPanelTelemetryService\PCPanelTelemetryService.exe"
$agentExe = Join-Path $resolvedRoot "PCPanelAgent\PCPanelAgent.exe"
$serviceName = "PCPanelTelemetry"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

foreach ($executable in @($serviceExe, $agentExe)) {
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Required executable was not found: $executable"
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Service registration requires an elevated PowerShell session."
}

& sc.exe query $serviceName *> $null
if ($LASTEXITCODE -eq 0) {
    throw "Service already exists: $serviceName"
}

$serviceStartMode = if ($EnableServiceAutoStart) { "auto" } else { "demand" }
& sc.exe create $serviceName binPath= ('"' + $serviceExe + '"') start= $serviceStartMode obj= "LocalSystem" DisplayName= "PCPanel Telemetry Service"
if ($LASTEXITCODE -ne 0) { throw "Failed to create $serviceName." }

try {
    if ($EnableAgentAutoStart) {
        New-Item -Path $runKey -Force | Out-Null
        Set-ItemProperty -Path $runKey -Name "PCPanelAgent" -Value ('"' + $agentExe + '"')
    }
    if ($StartServiceNow) {
        & sc.exe start $serviceName
        if ($LASTEXITCODE -ne 0) { throw "Failed to start $serviceName." }
    }
}
catch {
    & sc.exe delete $serviceName | Out-Null
    Remove-ItemProperty -Path $runKey -Name "PCPanelAgent" -ErrorAction SilentlyContinue
    throw
}

Write-Host "Service installed as LocalSystem (hardware-only privilege boundary): $serviceName"
Write-Host "Service startup: $(if ($EnableServiceAutoStart) { 'Automatic (consented)' } else { 'Manual' })"
Write-Host "Service started now: $($StartServiceNow.IsPresent)"
Write-Host "Agent startup at login: $(if ($EnableAgentAutoStart) { 'Enabled (consented)' } else { 'Disabled' })"
if ($EnableAgentAutoStart) {
    Write-Host "Agent executable: $agentExe"
}
