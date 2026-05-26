$ErrorActionPreference = "Stop"

$repo = "https://github.com/xingyun7842/-.git"
$skillDir = Join-Path $env:USERPROFILE ".codex\skills\weread-optimizer"
$parent = Split-Path $skillDir

New-Item -ItemType Directory -Force -Path $parent | Out-Null

if (Test-Path $skillDir) {
    Write-Host "Updating existing skill at $skillDir"
    git -C $skillDir pull --ff-only
} else {
    Write-Host "Installing skill to $skillDir"
    git clone $repo $skillDir
}

Write-Host "Installed weread-optimizer"
