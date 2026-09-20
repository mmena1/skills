[CmdletBinding()]
param(
    [switch]$Codex,
    [switch]$Devin,
    [switch]$All,
    [switch]$Experimental,
    [string]$HomePath = $HOME
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$ManagedMarker = '.skills-repo-managed'

function Test-InstalledPath {
    param([string]$Path)
    return $null -ne (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
}

function ConvertTo-NormalizedPath {
    param([string]$Path)
    if ($Path -match '^/([A-Za-z])/(.*)$') {
        $Path = $Matches[1] + ':\' + $Matches[2].Replace('/', '\')
    }
    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Test-PathWithinRepo {
    param([string]$Candidate)
    try {
        $resolved = ConvertTo-NormalizedPath $Candidate
        $repo = ConvertTo-NormalizedPath $RepoRoot
    } catch {
        return $false
    }
    return $resolved.Equals($repo, [System.StringComparison]::OrdinalIgnoreCase) -or
        $resolved.StartsWith($repo + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-LinkIntoRepo {
    param([string]$Path)
    if (-not (Test-InstalledPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.LinkType -or -not $item.Target) { return $false }
    foreach ($candidate in @($item.Target)) {
        $target = [string]$candidate
        if (-not $target) { continue }
        if (-not [System.IO.Path]::IsPathRooted($target)) {
            $target = Join-Path $item.Parent.FullName $target
        }
        if (Test-PathWithinRepo $target) { return $true }
    }
    return $false
}

function Test-ManagedCopy {
    param([string]$Path)
    $marker = Join-Path $Path $ManagedMarker
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { return $false }
    try {
        $recorded = (Get-Content -LiteralPath $marker -Raw).Trim()
        return Test-PathWithinRepo $recorded
    } catch {
        return $false
    }
}

function Remove-InstalledPath {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.LinkType -and $item.PSIsContainer) {
        [System.IO.Directory]::Delete($item.FullName)
    } elseif ($item.LinkType) {
        [System.IO.File]::Delete($item.FullName)
    } elseif ($item.PSIsContainer) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    } else {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Backup-InstalledPath {
    param([string]$Path)
    $backup = "$Path.bak-$Stamp"
    $suffix = 1
    while (Test-InstalledPath $backup) {
        $backup = "$Path.bak-$Stamp-$suffix"
        $suffix += 1
    }
    Write-Host "Backing up existing $Path to $backup"
    Move-Item -LiteralPath $Path -Destination $backup
}

function New-InstalledSkill {
    param([string]$Source, [string]$Destination)
    $action = 'Linked'
    try {
        New-Item -ItemType Junction -Path $Destination -Target $Source -ErrorAction Stop | Out-Null
    } catch {
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse
        Set-Content -LiteralPath (Join-Path $Destination $ManagedMarker) -Value $Source
        $action = 'Copied'
    }
    Write-Host "$action $Destination -> $Source"
    if ($action -eq 'Copied') {
        Write-Warning 'Link creation failed; rerun the installer after repository updates.'
    }
}

function Install-Skill {
    param([string]$Source, [string]$Destination)
    if (Test-InstalledPath $Destination) {
        if ((Test-LinkIntoRepo $Destination) -or (Test-ManagedCopy $Destination)) {
            Remove-InstalledPath $Destination
        } else {
            Backup-InstalledPath $Destination
        }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    New-InstalledSkill $Source $Destination
}

function Test-ManagedPath {
    param([string]$Path)
    return (Test-LinkIntoRepo $Path) -or (Test-ManagedCopy $Path)
}

function Sync-InstalledCollection {
    param([string]$DestinationRoot, [System.IO.DirectoryInfo[]]$Sources)
    $desired = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($source in $Sources) { [void]$desired.Add($source.Name) }
    foreach ($installed in @(Get-ChildItem -LiteralPath $DestinationRoot -Force -ErrorAction SilentlyContinue)) {
        if (-not $desired.Contains($installed.Name) -and (Test-ManagedPath $installed.FullName)) {
            Write-Host "Removing repository-managed skill absent from desired set: $($installed.FullName)"
            Remove-InstalledPath $installed.FullName
        }
    }
}

function Install-Collection {
    param([string]$DestinationRoot)
    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    $sources = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'skills') -Directory |
        Where-Object { $_.Name -ne 'experimental' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf) } |
        Sort-Object Name)
    if ($Experimental) {
        $sources += @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'skills/experimental') -Directory |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf } |
            Sort-Object Name)
    }
    Sync-InstalledCollection $DestinationRoot $sources
    foreach ($source in $sources) { Install-Skill $source.FullName (Join-Path $DestinationRoot $source.Name) }
}

$installCodex = $Codex -or $All
$installDevin = $Devin -or $All
if (-not $installCodex -and -not $installDevin) {
    $installCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.codex')) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.agents'))
    $installDevin = [bool](Get-Command devin -ErrorAction SilentlyContinue) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.config/devin'))
    if (-not $installCodex -and -not $installDevin) {
        throw 'No supported harness detected. Use -Codex, -Devin, or -All.'
    }
}

if ($installCodex) { Install-Collection (Join-Path $HomePath '.agents/skills') }
if ($installDevin) { Install-Collection (Join-Path $HomePath '.config/devin/skills') }

Write-Host 'Install complete.'
