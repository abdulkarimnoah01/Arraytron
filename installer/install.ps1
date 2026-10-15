<#
.SYNOPSIS
  Installs (or updates, or removes) Arraytron for every supported Houdini on this PC (22.x with the Houdini 22 build, 20.5 and 21.x with the Houdini 20.5 / 21 build).

.DESCRIPTION
  Copies the plugin (the HDA, the demos and the documentation) into
  %LOCALAPPDATA%\Arraytron\versions\<version> and writes one small package file,
  arraytron.json, into each Houdini preferences folder (Documents\houdiniX.Y\packages).
  The package adds the plugin's otls folder for that Houdini generation to Houdini's path, so the node appears in the
  Tab menu of Solaris. Running a newer release the same way updates it; the previous
  version is kept for one release so it can be rolled back. Your scenes and Houdini
  settings are never touched. No administrator rights are needed.

  Double-click "Install Arraytron.cmd" for the normal case. Options:
    -Houdini 22.0     only these versions, for example 22.0 or 20.5 (default: every supported one found)
    -CreatePrefs      also prepare versions whose preferences folder does not exist yet
    -Uninstall        remove Arraytron
    -Quiet            no prompts or pause (used for testing and by scripts)
    -Documents, -InstallRoot   other locations (used for testing; the ARRAYTRON_DOCUMENTS
                               variable sets the default for -Documents)
#>
[CmdletBinding()]
param(
    [string]$Documents = $(if ($env:ARRAYTRON_DOCUMENTS) { $env:ARRAYTRON_DOCUMENTS } else { [Environment]::GetFolderPath('MyDocuments') }),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Arraytron'),
    [string[]]$Houdini = @(),
    [switch]$CreatePrefs,
    [switch]$Uninstall,
    [switch]$Quiet
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $here 'payload'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Say($text) { Write-Host $text }
function Parse-Version([string]$text) {
    if ($text -match '^\s*v?(\d+)\.(\d+)(?:\.(\d+))?') {
        return [version]::new([int]$Matches[1], [int]$Matches[2], $(if ($Matches[3]) { [int]$Matches[3] } else { 0 }))
    }
    return $null
}
function Supported([int]$major, [int]$minor, $info) {
    $low = Parse-Version $info.houdini.min; $high = Parse-Version $info.houdini.max_exclusive
    $v = [version]::new($major, $minor, 0)
    return ($v -ge [version]::new($low.Major, $low.Minor, 0)) -and ($v -lt [version]::new($high.Major, $high.Minor, 0))
}
function Pick-Build([int]$major, [int]$minor, $info) {
    # The payload holds one HDA per Houdini generation (folder h22 for Houdini 22, h205 for 20.5 and 21); VERSION.json lists their ranges.
    $v = [version]::new($major, $minor, 0)
    foreach ($build in $info.builds) {
        $low = Parse-Version $build.min; $high = Parse-Version $build.max_exclusive
        if (($v -ge [version]::new($low.Major, $low.Minor, 0)) -and ($v -lt [version]::new($high.Major, $high.Minor, 0))) { return $build }
    }
    return $null
}
function Find-Prefs($info) {
    $found = @()
    if (-not (Test-Path $Documents)) { return $found }
    foreach ($dir in Get-ChildItem -Path $Documents -Directory -ErrorAction SilentlyContinue) {
        if ($dir.Name -match '^houdini(\d+)\.(\d+)$') {
            $label = '{0}.{1}' -f $Matches[1], $Matches[2]
            if ($Houdini.Count -gt 0 -and $Houdini -notcontains $label) { continue }
            if (Supported ([int]$Matches[1]) ([int]$Matches[2]) $info) {
                $found += [pscustomobject]@{ Label = $label; Path = $dir.FullName; Build = (Pick-Build ([int]$Matches[1]) ([int]$Matches[2]) $info) }
            }
        }
    }
    if ($CreatePrefs) {
        foreach ($label in $Houdini) {
            $path = Join-Path $Documents ("houdini$label")
            if (-not (Test-Path $path) -and $label -match '^(\d+)\.(\d+)$' -and
                (Supported ([int]$Matches[1]) ([int]$Matches[2]) $info)) {
                New-Item -ItemType Directory -Path $path | Out-Null
                $found += [pscustomobject]@{ Label = $label; Path = $path; Build = (Pick-Build ([int]$Matches[1]) ([int]$Matches[2]) $info) }
            }
        }
    }
    return $found
}
function Finish([int]$code) {
    if (-not $Quiet) { Read-Host 'Press Enter to close' | Out-Null }
    exit $code
}

# ---------------------------------------------------------------- uninstall
if ($Uninstall) {
    $record = Join-Path $InstallRoot 'installed.json'
    $targets = @()
    if (Test-Path $record) { $targets += (Get-Content $record -Raw | ConvertFrom-Json).prefs }
    if (Test-Path $Documents) {
        foreach ($dir in Get-ChildItem -Path $Documents -Directory -ErrorAction SilentlyContinue) {
            if ($dir.Name -match '^houdini\d+\.\d+$') { $targets += $dir.FullName }
        }
    }
    foreach ($prefs in ($targets | Select-Object -Unique)) {
        $file = Join-Path $prefs 'packages\arraytron.json'
        if (Test-Path $file) { Remove-Item $file -Force; Say "Removed $file" }
    }
    if (Test-Path $InstallRoot) {
        for ($try = 1; $try -le 5 -and (Test-Path $InstallRoot); $try++) {
            try { Remove-Item $InstallRoot -Recurse -Force -ErrorAction Stop } catch { Start-Sleep -Seconds 2 }
        }
        if (Test-Path $InstallRoot) { Say "Could not remove $InstallRoot (a file is in use: close Houdini and run this again)."; Finish 1 }
        Say "Removed $InstallRoot"
    }
    Say 'Arraytron is removed. Your scenes were not touched. Restart Houdini.'
    Finish 0
}

# ------------------------------------------------------------------ install
if (-not (Test-Path (Join-Path $payload 'VERSION.json'))) {
    Say 'This installer must be run from the unpacked Arraytron folder (payload\VERSION.json is missing).'
    Finish 1
}
$info = Get-Content (Join-Path $payload 'VERSION.json') -Raw | ConvertFrom-Json
Say ("Installing Arraytron {0}" -f $info.version)

$prefsList = @(Find-Prefs $info)
if ($prefsList.Count -eq 0) {
    Say ("No Houdini {0} to {1} preferences folder was found in {2}." -f $info.houdini.min, $info.houdini.max_exclusive, $Documents)
    Say 'Start Houdini once so it creates its preferences folder, then run this again,'
    Say 'or run it with  -CreatePrefs -Houdini 22.0  (or 20.5, 21.0) to prepare a version in advance.'
    Finish 1
}

$destination = Join-Path $InstallRoot ('versions\' + $info.version)
if (Test-Path $destination) { Remove-Item $destination -Recurse -Force }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -Path (Join-Path $payload '*') -Destination $destination -Recurse -Force

$posix = $destination -replace '\\', '/'
$done = @()
foreach ($prefs in $prefsList) {
    $build = $prefs.Build
    if (-not (Test-Path (Join-Path $destination ($build.folder + '\otls')))) { Say ("The package has no {0} folder: this download is incomplete." -f $build.folder); Finish 1 }
    $package = @"
{
    "enable": "houdini_version >= '$($build.min)' and houdini_version < '$($build.max_exclusive)'",
    "env": [
        {"ARRAYTRON": "$posix"}
    ],
    "path": "`$ARRAYTRON/$($build.folder)"
}
"@
    $packages = Join-Path $prefs.Path 'packages'
    New-Item -ItemType Directory -Path $packages -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $packages 'arraytron.json'), $package, $Utf8)
    Say ("  Houdini {0}: ready, {1} build ({2})" -f $prefs.Label, $build.folder, $packages)
    $done += $prefs.Path
}

# Keep this version and the one before it (a one-step rollback); remove older ones.
$versionsRoot = Join-Path $InstallRoot 'versions'
$kept = Get-ChildItem $versionsRoot -Directory | Where-Object { Parse-Version $_.Name } |
        Sort-Object { Parse-Version $_.Name } -Descending
foreach ($old in ($kept | Select-Object -Skip 2)) { Remove-Item $old.FullName -Recurse -Force }

$record = [ordered]@{ version = $info.version; path = $posix; prefs = $done;
                      installed = (Get-Date -Format 'yyyy-MM-dd HH:mm') } | ConvertTo-Json
[System.IO.File]::WriteAllText((Join-Path $InstallRoot 'installed.json'), $record, $Utf8)

Say ''
Say ("Arraytron {0} is installed for Houdini {1}." -f $info.version, (($prefsList | ForEach-Object { $_.Label }) -join ', '))
if (Get-Process houdini, houdinifx, houdinicore -ErrorAction SilentlyContinue) {
    Say 'Houdini is running: restart it to load this version.'
}
Say 'In a Solaris (LOPs) network press Tab and type Arraytron.'
Say ("The demos are in {0}\demos (Houdini 22) and {0}\demos_h205 (Houdini 20.5 / 21); start with the all_demos scene." -f $destination)
Finish 0
