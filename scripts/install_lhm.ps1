[CmdletBinding(DefaultParameterSetName = "Download")]
param(
    [Parameter(Mandatory, ParameterSetName = "Directory")]
    [string] $SourceDirectory,

    [Parameter(Mandatory, ParameterSetName = "Archive")]
    [string] $ArchivePath,

    [Parameter(Mandatory, ParameterSetName = "Archive")]
    [ValidatePattern("^[A-Fa-f0-9]{64}$")]
    [string] $Sha256,

    [switch] $Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$libsRoot = Join-Path $projectRoot "libs"
$destination = Join-Path $libsRoot "LibreHardwareMonitor"
$staging = Join-Path $libsRoot (".lhm-install-" + [guid]::NewGuid().ToString("N"))
$temporaryExtraction = $null
$temporaryArchive = $null

# Keep release and digest together. Updating LibreHardwareMonitor is an explicit,
# reviewable change instead of silently following GitHub's mutable "latest" URL.
$releaseVersion = "0.9.6"
$releaseUrl = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v$releaseVersion/LibreHardwareMonitor.zip"
$releaseSha256 = "086D9F1B5A99E643EDC2CFAAAC16051685B551E4C5AC0B32A57C58C0E529C001"

function Find-LhmDistribution {
    param([Parameter(Mandatory)][string] $Root)

    $dll = Get-ChildItem -LiteralPath $Root -Filter "LibreHardwareMonitorLib.dll" -File -Recurse |
        Select-Object -First 1
    if ($null -eq $dll) {
        throw "LibreHardwareMonitorLib.dll was not found under: $Root"
    }
    return $dll.Directory.FullName
}

try {
    if ((Test-Path -LiteralPath $destination) -and -not $Force) {
        throw "LibreHardwareMonitor is already installed at $destination. Use -Force to replace it."
    }

    if ($PSCmdlet.ParameterSetName -eq "Download") {
        $temporaryArchive = Join-Path ([System.IO.Path]::GetTempPath()) (
            "LibreHardwareMonitor-v$releaseVersion-" + [guid]::NewGuid().ToString("N") + ".zip"
        )
        Write-Host "Downloading LibreHardwareMonitor v$releaseVersion from the official GitHub release..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $releaseUrl -OutFile $temporaryArchive
        $resolvedArchive = $temporaryArchive
        $expectedHash = $releaseSha256
    }
    elseif ($PSCmdlet.ParameterSetName -eq "Archive") {
        $resolvedArchive = (Resolve-Path -LiteralPath $ArchivePath).Path
        $expectedHash = $Sha256
    }
    else {
        $resolvedSource = (Resolve-Path -LiteralPath $SourceDirectory).Path
        $distribution = Find-LhmDistribution -Root $resolvedSource
    }

    if ($PSCmdlet.ParameterSetName -in @("Download", "Archive")) {
        $actualHash = (Get-FileHash -LiteralPath $resolvedArchive -Algorithm SHA256).Hash
        if ($actualHash -ne $expectedHash) {
            throw "SHA-256 mismatch. Expected $expectedHash; received $actualHash."
        }
        $temporaryExtraction = Join-Path ([System.IO.Path]::GetTempPath()) (
            "pcpanel-lhm-" + [guid]::NewGuid().ToString("N")
        )
        New-Item -ItemType Directory -Path $temporaryExtraction | Out-Null
        Expand-Archive -LiteralPath $resolvedArchive -DestinationPath $temporaryExtraction
        $distribution = Find-LhmDistribution -Root $temporaryExtraction
    }
    New-Item -ItemType Directory -Path $libsRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $staging | Out-Null
    Copy-Item -Path (Join-Path $distribution "*") -Destination $staging -Recurse -Force

    $installedDll = Join-Path $staging "LibreHardwareMonitorLib.dll"
    if (-not (Test-Path -LiteralPath $installedDll -PathType Leaf)) {
        throw "The staged distribution does not contain LibreHardwareMonitorLib.dll."
    }

    if (Test-Path -LiteralPath $destination) {
        Remove-Item -LiteralPath $destination -Recurse -Force
    }
    Move-Item -LiteralPath $staging -Destination $destination

    Write-Host "LibreHardwareMonitor installed at: $destination"
    Write-Host "DLL: $(Join-Path $destination 'LibreHardwareMonitorLib.dll')"
    if ($PSCmdlet.ParameterSetName -eq "Download") {
        Write-Host "Source: LibreHardwareMonitor v$releaseVersion ($releaseUrl)"
    }
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ($null -ne $temporaryExtraction -and (Test-Path -LiteralPath $temporaryExtraction)) {
        Remove-Item -LiteralPath $temporaryExtraction -Recurse -Force
    }
    if ($null -ne $temporaryArchive -and (Test-Path -LiteralPath $temporaryArchive)) {
        Remove-Item -LiteralPath $temporaryArchive -Force
    }
}
