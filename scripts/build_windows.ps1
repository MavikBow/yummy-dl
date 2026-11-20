<#
.SYNOPSIS
  Build dist\yummy-dl.exe (single file) with PyInstaller.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -BundleFfmpeg
    Also copies ffmpeg.exe (from PATH or -FfmpegPath) next to the exe and zips both into
    dist\yummy-dl-windows.zip.
#>
param(
    [switch]$BundleFfmpeg,
    [string]$FfmpegPath = "",
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venv = Join-Path $root ".venv-win"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    & $Python -m venv $venv
    if ($LASTEXITCODE) { throw "venv creation failed" }
}
$py = "$venv\Scripts\python.exe"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet . "pyinstaller>=6.10"
if ($LASTEXITCODE) { throw "pip install failed" }

& $py -m PyInstaller --noconfirm --clean --onefile --console `
    --name yummy-dl `
    --collect-submodules yummy_dl `
    --collect-submodules rich._unicode_data `
    --distpath dist --workpath build `
    src\yummy_dl\__main__.py
if ($LASTEXITCODE) { throw "PyInstaller failed" }

& dist\yummy-dl.exe --help | Out-Null
if ($LASTEXITCODE) { throw "built exe failed to run" }
Write-Host "Built dist\yummy-dl.exe"

if ($BundleFfmpeg) {
    if (-not $FfmpegPath) {
        $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
        if (-not $cmd) { throw "ffmpeg.exe not on PATH; pass -FfmpegPath" }
        $FfmpegPath = $cmd.Source
    }
    $stage = Join-Path $root "dist\yummy-dl"
    New-Item -ItemType Directory -Force $stage | Out-Null
    Copy-Item dist\yummy-dl.exe, $FfmpegPath, README.md $stage -Force
    $zip = "dist\yummy-dl-windows.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path "$stage\*" -DestinationPath $zip
    Write-Host "Built $zip (exe + ffmpeg)"
}
