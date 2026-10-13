$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "skills\auto-video-editor"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Skill source not found: $source"
}

$codexRoot = $env:CODEX_HOME
if ([string]::IsNullOrWhiteSpace($codexRoot)) {
    $codexRoot = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".codex"
}
$destination = Join-Path $codexRoot "skills\auto-video-editor"
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Get-ChildItem -LiteralPath $source | Copy-Item -Destination $destination -Recurse -Force
Write-Host "Installed auto-video-editor skill to $destination"
