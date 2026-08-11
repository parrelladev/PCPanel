[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$serviceName = "PCPanelTelemetry"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

Remove-ItemProperty -Path $runKey -Name "PCPanelAgent" -ErrorAction SilentlyContinue

& sc.exe query $serviceName *> $null
if ($LASTEXITCODE -eq 0) {
    & sc.exe stop $serviceName | Out-Null
    $deadline = (Get-Date).AddSeconds(15)
    $stopped = $false
    do {
        Start-Sleep -Milliseconds 250
        & sc.exe query $serviceName 2>&1 | Out-String | ForEach-Object {
            $stopped = $_ -match "STOPPED"
        }
    } while (-not $stopped -and (Get-Date) -lt $deadline)
    & sc.exe delete $serviceName
    if ($LASTEXITCODE -ne 0) { throw "Failed to delete $serviceName." }
}

Write-Host "PCPanel Windows lifecycle registrations removed. User data was preserved."
