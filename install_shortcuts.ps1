$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root "dist\SaveDates\SaveDates.exe"
$icon = Join-Path $root "assets\icon.ico"
$workDir = Join-Path $root "dist\SaveDates"
if (-not (Test-Path $exe)) {
    throw "Missing $exe"
}

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut([string]$path) {
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $exe
    $link.WorkingDirectory = $workDir
    $link.WindowStyle = 1
    $link.Description = "Save Dates"
    $link.IconLocation = "$icon,0"
    $link.Save()
    Write-Output $path
}

$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Save Dates.lnk"
$start = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Save Dates.lnk"
New-Shortcut $desktop
New-Shortcut $start
