[CmdletBinding()]
param(
    [switch]$Codex,
    [switch]$Devin,
    [switch]$Claude,
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

function Get-ManagedMarkerPath {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Container) { return Join-Path $Path $ManagedMarker }
    return "$Path$ManagedMarker"
}

function Test-ManagedCopy {
    param([string]$Path)
    return Test-MarkerIntoRepo (Get-ManagedMarkerPath $Path)
}

function Test-MarkerIntoRepo {
    param([string]$Marker)
    if (-not (Test-Path -LiteralPath $Marker -PathType Leaf)) { return $false }
    try {
        $recorded = (Get-Content -LiteralPath $Marker -Raw).Trim()
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
    $siblingMarker = "$Path$ManagedMarker"
    if (Test-Path -LiteralPath $siblingMarker -PathType Leaf) {
        Remove-Item -LiteralPath $siblingMarker -Force
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

function New-InstalledPath {
    param([string]$Source, [string]$Destination)
    $action = 'Linked'
    $isDirectory = Test-Path -LiteralPath $Source -PathType Container
    try {
        if ($env:SKILLS_INSTALLER_FORCE_COPY -eq '1') { throw 'Link creation disabled.' }
        if ($isDirectory) {
            New-Item -ItemType Junction -Path $Destination -Target $Source -ErrorAction Stop | Out-Null
        } else {
            New-Item -ItemType SymbolicLink -Path $Destination -Target $Source -ErrorAction Stop | Out-Null
        }
    } catch {
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse
        $marker = Get-ManagedMarkerPath $Destination
        Set-Content -LiteralPath $marker -Value $Source
        $action = 'Copied'
    }
    Write-Host "$action $Destination -> $Source"
    if ($action -eq 'Copied') {
        Write-Warning 'Link creation failed; rerun the installer after repository updates.'
    }
}

# The standalone mmena1/deep-review installer composed marked skill roots from links
# into its checkout and linked its native agents from there. Recognise exactly those
# installations so this repository's deep-review replaces them; anything else that
# occupies the same name is backed up.
$LegacyDeepReviewMarker = '.deep-review-managed'
$LegacyDeepReviewEntries = @($LegacyDeepReviewMarker, 'SKILL.md', 'protocol.md', 'GLOSSARY.md', 'references', 'reviewers', 'agents')
$LegacyDeepReviewDevinAgents = @('code-reviewer', 'code-reviewer-structural', 'code-reviewer-validator-static', 'code-reviewer-validator-probe')

# A standalone deep-review checkout: the shared protocol plus a harness wrapper.
function Test-DeepReviewCheckout {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'skills/deep-review/protocol.md') -PathType Leaf)) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Path 'harnesses/codex/skills/deep-review/SKILL.md') -PathType Leaf) -or
        (Test-Path -LiteralPath (Join-Path $Path 'harnesses/devin/skills/deep-review/SKILL.md') -PathType Leaf)
}

# True when the link at Path (symlink, junction, or hard link) shares its content
# with <checkout>/<Relative> in a deep-review checkout.
function Test-LinkIntoLegacyDeepReview {
    param([string]$Path, [string]$Relative)
    if (-not (Test-InstalledPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    $candidates = @($item.Target | Where-Object { $_ })
    if (-not $item.PSIsContainer) {
        # PowerShell 7 does not report a hard link's other names in Target, so ask fsutil,
        # which prints each name without its drive.
        $drive = [System.IO.Path]::GetPathRoot($item.FullName).TrimEnd('\')
        $candidates += @(fsutil hardlink list $item.FullName 2>$null | Where-Object { $_ } | ForEach-Object { $drive + $_ })
    }
    $suffix = '\' + $Relative.Replace('/', '\')
    foreach ($candidate in $candidates) {
        $target = [string]$candidate
        if (-not $target) { continue }
        if (-not [System.IO.Path]::IsPathRooted($target)) {
            $target = Join-Path (Split-Path -Parent $item.FullName) $target
        }
        try { $target = ConvertTo-NormalizedPath $target } catch { continue }
        if (-not $target.EndsWith($suffix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        $checkout = $target.Substring(0, $target.Length - $suffix.Length)
        if (Test-DeepReviewCheckout $checkout) { return $true }
    }
    return $false
}

function Test-LegacyDeepReviewSkillRoot {
    param([string]$Path)
    if ((Split-Path -Leaf $Path) -ne 'deep-review') { return $false }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item -or -not $item.PSIsContainer -or $item.LinkType) { return $false }
    $marker = Join-Path $Path $LegacyDeepReviewMarker
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { return $false }
    # The old installer recorded its checkout in the marker, as a Windows or Git Bash path.
    try { $recorded = ConvertTo-NormalizedPath ([string](Get-Content -LiteralPath $marker -Raw)).Trim() } catch { return $false }
    if (-not (Test-DeepReviewCheckout $recorded)) { return $false }
    foreach ($entry in @(Get-ChildItem -LiteralPath $Path -Force)) {
        if ($LegacyDeepReviewEntries -notcontains $entry.Name) { return $false }
    }
    return $true
}

function Test-LegacyDeepReviewInstallation {
    param([string]$Path)
    $name = Split-Path -Leaf $Path
    if ($name -eq 'deep-review') { return Test-LegacyDeepReviewSkillRoot $Path }
    if ($name -like 'deep-review-*.toml') { return Test-LinkIntoLegacyDeepReview $Path "harnesses/codex/agents/$name" }
    return $false
}

# Unlink each composed entry before removing the root so no link is followed.
function Remove-LegacyDeepReview {
    param([string]$Path)
    Write-Host "Replacing deep-review installation from the standalone repository: $Path"
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -and -not $item.LinkType) {
        foreach ($entry in @(Get-ChildItem -LiteralPath $Path -Force)) { Remove-InstalledPath $entry.FullName }
    }
    Remove-InstalledPath $Path
}

# A Devin agent the old installer linked from a checkout, or copied from one when
# the link failed: a directory holding only an AGENT.md from its generator.
function Test-LegacyDeepReviewDevinAgent {
    param([string]$Path)
    $name = Split-Path -Leaf $Path
    if (Test-LinkIntoLegacyDeepReview $Path "harnesses/devin/agents/$name") { return $true }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item -or -not $item.PSIsContainer -or $item.LinkType) { return $false }
    $entries = @(Get-ChildItem -LiteralPath $Path -Force)
    if ($entries.Count -ne 1 -or $entries[0].Name -ne 'AGENT.md' -or $entries[0].PSIsContainer) { return $false }
    $lines = @(Get-Content -LiteralPath $entries[0].FullName)
    return ($lines -ccontains "name: $name") -and ($lines -ccontains '<!-- BEGIN GENERATED: shared reviewer body -->')
}

# Devin names the old installation used that this repository does not install.
function Remove-LegacyDeepReviewDevin {
    param([string[]]$AgentRoots)
    $skillRoot = Join-Path $HomePath '.config/devin/skills/deep-review'
    if (Test-LegacyDeepReviewSkillRoot $skillRoot) { Remove-LegacyDeepReview $skillRoot }
    foreach ($agentRoot in $AgentRoots) {
        foreach ($name in $LegacyDeepReviewDevinAgents) {
            $path = Join-Path $agentRoot $name
            if (Test-LegacyDeepReviewDevinAgent $path) { Remove-LegacyDeepReview $path }
        }
    }
}

function Install-ManagedPath {
    param([string]$Source, [string]$Destination)
    if (Test-InstalledPath $Destination) {
        if ((Test-LinkIntoRepo $Destination) -or (Test-ManagedCopy $Destination)) {
            Remove-InstalledPath $Destination
        } elseif (Test-LegacyDeepReviewInstallation $Destination) {
            Remove-LegacyDeepReview $Destination
        } else {
            Backup-InstalledPath $Destination
        }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    New-InstalledPath $Source $Destination
}

function Test-ManagedPath {
    param([string]$Path)
    return (Test-LinkIntoRepo $Path) -or (Test-ManagedCopy $Path)
}

function Sync-InstalledCollection {
    param([string]$DestinationRoot, [string[]]$DesiredNames, [string]$Kind = 'skill')
    $desired = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $DesiredNames) { [void]$desired.Add($name) }
    foreach ($installed in @(Get-ChildItem -LiteralPath $DestinationRoot -Force -ErrorAction SilentlyContinue)) {
        if (-not $installed.PSIsContainer -and $installed.Name.EndsWith($ManagedMarker, [System.StringComparison]::OrdinalIgnoreCase)) {
            $markedPath = $installed.FullName.Substring(0, $installed.FullName.Length - $ManagedMarker.Length)
            if (-not (Test-InstalledPath $markedPath) -and (Test-MarkerIntoRepo $installed.FullName)) {
                Remove-Item -LiteralPath $installed.FullName -Force
            }
            continue
        }
        if (-not $desired.Contains($installed.Name) -and (Test-ManagedPath $installed.FullName)) {
            Write-Host "Removing repository-managed $Kind absent from desired set: $($installed.FullName)"
            Remove-InstalledPath $installed.FullName
        }
    }
}

function Get-SelectedSkills {
    $sources = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'skills') -Directory |
        Where-Object { $_.Name -ne 'experimental' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf) } |
        Sort-Object Name)
    if ($Experimental) {
        $sources += @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'skills/experimental') -Directory |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf } |
            Sort-Object Name)
    }
    return $sources
}

function Install-Collection {
    param([string]$DestinationRoot)
    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    $sources = @(Get-SelectedSkills)
    Sync-InstalledCollection $DestinationRoot @($sources | ForEach-Object { $_.Name })
    foreach ($source in $sources) { Install-ManagedPath $source.FullName (Join-Path $DestinationRoot $source.Name) }
}

# Generated native agents that selected skills ship for one harness:
# Codex <name>.toml files, Devin <name>/AGENT.md directories, and Claude <name>.md files.
function Get-SelectedAgents {
    param([string]$Harness)
    foreach ($skill in @(Get-SelectedSkills)) {
        $root = Join-Path $skill.FullName "harnesses/$Harness"
        if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
        foreach ($entry in @(Get-ChildItem -LiteralPath $root | Sort-Object Name)) {
            $isAgent = switch ($Harness) {
                'codex' { -not $entry.PSIsContainer -and $entry.Extension -eq '.toml' }
                'claude' { -not $entry.PSIsContainer -and $entry.Extension -eq '.md' }
                'devin' { $entry.PSIsContainer -and (Test-Path -LiteralPath (Join-Path $entry.FullName 'AGENT.md') -PathType Leaf) }
            }
            if ($isAgent) { $entry }
        }
    }
}

function Install-Agents {
    param([string]$Harness, [string]$DestinationRoot)
    $agents = @(Get-SelectedAgents $Harness)
    if (Test-Path -LiteralPath $DestinationRoot -PathType Container) {
        Sync-InstalledCollection $DestinationRoot @($agents | ForEach-Object { $_.Name }) 'agent'
    }
    if ($agents.Count -eq 0) { return }
    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    foreach ($agent in $agents) { Install-ManagedPath $agent.FullName (Join-Path $DestinationRoot $agent.Name) }
}

$installCodex = $Codex -or $All
$installDevin = $Devin -or $All
$installClaude = $Claude -or $All
if (-not $Codex -and -not $Devin -and -not $Claude -and -not $All) {
    $installCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.codex')) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.agents'))
    $installDevin = [bool](Get-Command devin -ErrorAction SilentlyContinue) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.config/devin'))
    $installClaude = [bool](Get-Command claude -ErrorAction SilentlyContinue) -or
        (Test-Path -LiteralPath (Join-Path $HomePath '.claude'))
    if (-not $installCodex -and -not $installDevin -and -not $installClaude) {
        throw 'No supported harness detected. Use -Codex, -Devin, -Claude, or -All.'
    }
}

if ($installCodex -or $installDevin) {
    Install-Collection (Join-Path $HomePath '.agents/skills')
}
if ($installDevin) {
    Sync-InstalledCollection (Join-Path $HomePath '.config/devin/skills') @()
}
if ($installClaude) { Install-Collection (Join-Path $HomePath '.claude/skills') }
$devinAgents = if ($env:APPDATA) { Join-Path $env:APPDATA 'devin/agents' } else { Join-Path $HomePath '.config/devin/agents' }
if ($installCodex) { Install-Agents 'codex' (Join-Path $HomePath '.codex/agents') }
if ($installDevin) {
    Install-Agents 'devin' $devinAgents
    Remove-LegacyDeepReviewDevin @((Join-Path $HomePath '.config/devin/agents'), $devinAgents)
}
if ($installClaude) { Install-Agents 'claude' (Join-Path $HomePath '.claude/agents') }

Write-Host 'Install complete.'
